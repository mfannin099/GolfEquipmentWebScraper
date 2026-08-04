"""Driver script to sanity-check both site scrapers side by side.

Every run appends its full result set to data/club_prices.db, so the table
accumulates real price history rather than being overwritten. Rows are
stamped with the run's `run_timestamp` and an `extracted_date`, and the
DB's unique index makes the append idempotent - a listing returned twice
in one run can't land twice.

Run from this directory: `uv run python test_scrapers.py`
"""

from datetime import datetime
from functools import partial

from carlsgolfland_scraper import CarlsGolflandScraper
from tgw_scraper import TgwScraper
from config import BRANDS, CLUB_TYPES
from database import DB_PATH, connect, insert_rows, latest_prices, row_count, validate_rows
from logging_config import get_logger
from price_alerts import log_price_drops

# Set True to also write this run's log lines to a timestamped file
# under logs/ (gitignored), so a run can be reviewed later without
# rerunning it.
WRITE_LOGS_TO_FILE = False

logger = get_logger(__name__, write_to_file=WRITE_LOGS_TO_FILE)

# Each entry is called as scraper(brand, club_type).run(). Add a site here
# and it joins the matrix - nothing below needs touching.
SITE_SCRAPERS = (
    ("carlsgolfland.com", partial(CarlsGolflandScraper, max_pages=1)),
    ("tgw.com", TgwScraper),
)


def scrape_all() -> list[dict]:
    """Runs every brand x club type against every site. A site failing one
    combination is logged and skipped so the rest of the matrix still runs.
    """
    results = []
    for brand in BRANDS:
        for club_type in CLUB_TYPES:
            for site, scraper in SITE_SCRAPERS:
                logger.info("Scraping %s: %s %s...", site, brand, club_type)
                try:
                    rows = scraper(brand, club_type).run()
                except Exception:
                    logger.error("%s %s %s failed", site, brand, club_type, exc_info=True)
                    continue
                logger.info("%s %s %s: %d results", site, brand, club_type, len(rows))
                results += rows
    return results


if __name__ == "__main__":
    run_timestamp = datetime.now().isoformat(timespec="seconds")
    logger.info("Starting club price tracker run (run_timestamp=%s)", run_timestamp)

    scraped = scrape_all()
    for row in scraped:
        row["run_timestamp"] = run_timestamp

    # Unlike migrate_csv_to_db.py, a bad row here is logged and dropped
    # rather than aborting: a malformed listing shouldn't cost the run
    # everything else it just spent minutes collecting.
    rows, errors = validate_rows(scraped)
    for message in errors[:20]:
        logger.warning("Skipping invalid row - %s", message)
    if len(errors) > 20:
        logger.warning("... and %d more invalid row(s)", len(errors) - 20)

    logger.info("Run complete: %d valid of %d scraped results", len(rows), len(scraped))

    with connect() as conn:
        drops = log_price_drops(latest_prices(conn), rows, logger)
        inserted = insert_rows(conn, rows)
        total = row_count(conn)

    logger.info("Flagged %d price drop(s) against prior history", drops)
    logger.info(
        "Appended %d row(s) to %s (%d skipped as duplicates); history now %d rows",
        inserted, DB_PATH.name, len(rows) - inserted, total,
    )
