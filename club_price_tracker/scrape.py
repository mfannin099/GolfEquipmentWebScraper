"""Scrape club prices for a chosen set of brands / club types / sites.

Entry point for the tracker. With no arguments it runs the full matrix
(every configured brand x club type against both sites) and appends the
results to data/club_prices.db:

    uv run python scrape.py

Narrow it down with flags - useful when iterating on one site's parsing,
or pulling a single brand on demand:

    uv run python scrape.py --brand Titleist --club-type driver
    uv run python scrape.py --site tgw.com --max-variant-lookups all
    uv run python scrape.py --brand Srixon --club-type driver --dry-run

Every row is stamped with the run's `run_timestamp` and an
`extracted_date`, so the table accumulates queryable price history rather
than being overwritten. The DB's unique index makes the append idempotent
- a listing returned twice in one run can't land twice.

The work is split into scrape() and save() rather than one do-everything
function so a caller can use either half on its own. A UI wanting to show
live results for a user's query calls scrape() and renders the rows
without touching the database; a scheduled collection run calls both.
"""

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

from carlsgolfland_scraper import CarlsGolflandScraper
from config import BRANDS, CLUB_TYPES, MAX_VARIANT_LOOKUPS
from database import DB_PATH, connect, insert_rows, latest_prices, row_count, validate_rows
from logging_config import get_logger
from price_alerts import log_price_drops
from scraper_base import USE_CONFIG_DEFAULT
from tgw_scraper import TgwScraper

# Site name -> scraper class. Keys come off the classes themselves so a
# --site value can't drift from what actually lands in the DB's `site`
# column. Add a site here and it joins the matrix and the CLI at once.
SCRAPERS = {
    CarlsGolflandScraper.SITE: CarlsGolflandScraper,
    TgwScraper.SITE: TgwScraper,
}


def variant_cap(value: str) -> int | None:
    """argparse type for --max-variant-lookups.

    Maps the CLI spelling straight onto the value scrape() takes, so the
    flag and the keyword argument can't drift apart: "all" -> None
    (uncapped), an integer -> that many. Omitting the flag entirely is
    what falls back to config.MAX_VARIANT_LOOKUPS.
    """
    if value.lower() == "all":
        return None
    try:
        count = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected an integer or 'all', got {value!r}")
    if count < 0:
        raise argparse.ArgumentTypeError("cannot be negative (use 'all' for no cap)")
    return count


@dataclass(frozen=True, slots=True)
class SaveSummary:
    scraped: int
    valid: int
    inserted: int
    duplicates: int
    drops: int
    history_rows: int


def scrape(
    brands: Iterable[str],
    club_types: Iterable[str],
    sites: Iterable[str] | None = None,
    *,
    max_pages: int = 1,
    max_variant_lookups: int | None = USE_CONFIG_DEFAULT,
    logger=None,
) -> list[dict]:
    """Runs the requested brand x club type x site combinations.

    Returns raw scraper rows - not stamped with a run_timestamp, not
    validated, not saved. One combination failing is logged and skipped so
    the rest of the matrix still runs; a single site being down shouldn't
    cost the whole run.
    """
    logger = logger or get_logger(__name__)
    sites = list(sites) if sites is not None else list(SCRAPERS)

    results: list[dict] = []
    for brand in brands:
        for club_type in club_types:
            for site in sites:
                logger.info("Scraping %s: %s %s...", site, brand, club_type)
                try:
                    rows = SCRAPERS[site](
                        brand,
                        club_type,
                        max_pages=max_pages,
                        max_variant_lookups=max_variant_lookups,
                    ).run()
                except Exception:
                    logger.error("%s %s %s failed", site, brand, club_type, exc_info=True)
                    continue
                logger.info("%s %s %s: %d results", site, brand, club_type, len(rows))
                results += rows
    return results


def save(
    rows: Sequence[dict],
    *,
    run_timestamp: str | None = None,
    db_path: Path | str = DB_PATH,
    logger=None,
) -> SaveSummary:
    """Stamps, validates, alerts on price drops, and appends to the DB.

    An invalid row is logged and dropped rather than aborting: one
    malformed listing shouldn't cost everything else a run just spent
    minutes collecting.
    """
    logger = logger or get_logger(__name__)
    run_timestamp = run_timestamp or datetime.now().isoformat(timespec="seconds")

    for row in rows:
        row["run_timestamp"] = run_timestamp

    valid, errors = validate_rows(rows)
    for message in errors[:20]:
        logger.warning("Skipping invalid row - %s", message)
    if len(errors) > 20:
        logger.warning("... and %d more invalid row(s)", len(errors) - 20)

    with connect(db_path) as conn:
        # Read the previous prices before inserting, or this run's own rows
        # would be what each listing gets compared against.
        drops = log_price_drops(latest_prices(conn), valid, logger)
        inserted = insert_rows(conn, valid)
        history_rows = row_count(conn)

    return SaveSummary(
        scraped=len(rows),
        valid=len(valid),
        inserted=inserted,
        duplicates=len(valid) - inserted,
        drops=drops,
        history_rows=history_rows,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scrape golf club prices into data/club_prices.db.",
        epilog=(
            "With no arguments, runs every configured brand x club type against "
            "both sites."
        ),
    )
    parser.add_argument(
        "--brand", nargs="+", default=list(BRANDS), metavar="NAME",
        # Deliberately not restricted to config.BRANDS: both sites take an
        # arbitrary search term, so a one-off pull for a brand that isn't
        # tracked routinely should just work.
        help=f"Brands to scrape (any search term works). Default: {', '.join(BRANDS)}",
    )
    parser.add_argument(
        "--club-type", nargs="+", choices=list(CLUB_TYPES), default=list(CLUB_TYPES),
        metavar="TYPE",
        # Restricted, unlike --brand: each club type needs an entry in
        # CLUB_TYPES for its search term and in VARIANT_TARGETS to resolve
        # the right loft/set variant.
        help=f"Club types to scrape. Choices: {', '.join(CLUB_TYPES)}",
    )
    parser.add_argument(
        "--site", nargs="+", choices=list(SCRAPERS), default=list(SCRAPERS),
        metavar="SITE",
        help=f"Sites to scrape. Choices: {', '.join(SCRAPERS)}",
    )
    parser.add_argument(
        "--max-pages", type=int, default=1, metavar="N",
        help="Listing pages per combination (carlsgolfland.com only; "
             "tgw.com's search returns one page). Default: 1",
    )
    parser.add_argument(
        "--max-variant-lookups", type=variant_cap, default=USE_CONFIG_DEFAULT,
        metavar="N|all",
        help="Cap on product-page requests per combination - these are what "
             "fetch descriptions, stock status and exact variant prices. "
             "Pass 'all' for no cap (slow but complete). Default: config's "
             f"MAX_VARIANT_LOOKUPS ({MAX_VARIANT_LOOKUPS})",
    )
    parser.add_argument(
        "--db", type=Path, default=DB_PATH, metavar="PATH",
        help=f"Database to append to. Default: {DB_PATH}",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Scrape and report, but don't write to the database.",
    )
    parser.add_argument(
        "--log-file", action="store_true",
        help="Also write this run's log lines to a timestamped file under logs/.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # Built before anything else logs: get_logger() attaches handlers on
    # the first call for a given name and returns the same logger after
    # that, so a file handler has to be requested up front or not at all.
    logger = get_logger(__name__, write_to_file=args.log_file)

    run_timestamp = datetime.now().isoformat(timespec="seconds")
    logger.info(
        "Starting run (run_timestamp=%s): %d brand(s) x %d club type(s) x %d site(s)",
        run_timestamp, len(args.brand), len(args.club_type), len(args.site),
    )

    rows = scrape(
        args.brand,
        args.club_type,
        args.site,
        max_pages=args.max_pages,
        max_variant_lookups=args.max_variant_lookups,
        logger=logger,
    )

    if not rows:
        logger.error("No results scraped - nothing to save.")
        return 1

    if args.dry_run:
        logger.info("Dry run: %d row(s) scraped, nothing written.", len(rows))
        for row in rows:
            logger.info(
                "  %s | %s [%s] $%s (sale=%s, stock=%s)",
                row["site"], row["name"], row["variant"] or "-",
                row["price"], row["on_sale"], row["stock_status"] or "-",
            )
        return 0

    summary = save(rows, run_timestamp=run_timestamp, db_path=args.db, logger=logger)
    logger.info("Flagged %d price drop(s) against prior history", summary.drops)
    logger.info(
        "Appended %d of %d valid row(s) to %s (%d skipped as duplicates); "
        "history now %d rows",
        summary.inserted, summary.valid, Path(args.db).name,
        summary.duplicates, summary.history_rows,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
