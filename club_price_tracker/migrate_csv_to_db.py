"""One-off backfill of the legacy club_prices.csv into SQLite.

test_scrapers.py writes straight to data/club_prices.db now, so this only
needs running once to carry the CSV's existing price history over. It's
safe to run again anyway - the dedup index means already-imported rows are
ignored rather than duplicated.

    uv run python migrate_csv_to_db.py

Strict by design: if any row fails schema validation nothing is written,
since a partial import of historical data is harder to reason about later
than a failed one. The CSV predates the sku/rating/review_count/image_url
columns, so those land as NULL for migrated rows.

Run from this directory: `uv run python migrate_csv_to_db.py`
"""

import csv
import sys
from pathlib import Path

from database import DB_PATH, connect, insert_rows, row_count, validate_rows
from logging_config import get_logger

CSV_PATH = Path(__file__).parent / "club_prices.csv"

logger = get_logger(__name__)


def main() -> int:
    if not CSV_PATH.exists():
        logger.error("No CSV to migrate at %s", CSV_PATH)
        return 1

    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        csv_rows = list(csv.DictReader(handle))
    logger.info("Read %d rows from %s", len(csv_rows), CSV_PATH.name)

    rows, errors = validate_rows(csv_rows)
    if errors:
        logger.error("%d row(s) failed validation - nothing written:", len(errors))
        for message in errors[:20]:
            logger.error("  %s", message)
        if len(errors) > 20:
            logger.error("  ... and %d more", len(errors) - 20)
        return 1

    with connect() as conn:
        before = row_count(conn)
        inserted = insert_rows(conn, rows)
        after = row_count(conn)

    logger.info(
        "Migrated %d row(s) into %s (%d skipped as duplicates); table now holds %d rows",
        inserted, DB_PATH, len(rows) - inserted, after,
    )
    if before:
        logger.info("Database already held %d rows before this run", before)
    return 0


if __name__ == "__main__":
    sys.exit(main())
