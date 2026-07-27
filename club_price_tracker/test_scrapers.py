"""Driver script to sanity-check both site scrapers side by side.

Run from this directory: `uv run python test_scrapers.py`
"""

from datetime import datetime
from pathlib import Path

import pandas as pd

from carlsgolfland_scraper import CarlsGolflandScraper
from tgw_scraper import TgwScraper
from config import BRANDS, CLUB_TYPES
from logging_config import get_logger
from price_alerts import log_price_drops

# Set True to also write this run's log lines to a timestamped file
# under logs/ (gitignored), so a run can be reviewed later without
# rerunning it.
WRITE_LOGS_TO_FILE = False

# Every run appends its full result set as new rows (run_timestamp
# marks when each row was parsed), so club_prices.csv accumulates real
# price history instead of being overwritten each time.
CSV_PATH = Path(__file__).parent / "club_prices.csv"

# Guards against a single run appending the exact same row twice (e.g.
# a scraping bug returning the same listing more than once) - not a
# cross-run dedup, since run_timestamp is the same for every row in one
# run anyway. See price_alerts.PRODUCT_KEY for the cross-run matching
# used by price-drop alerting.
DEDUP_KEY = ["site", "brand", "club_type", "variant", "name", "run_timestamp"]

logger = get_logger(__name__, write_to_file=WRITE_LOGS_TO_FILE)

if __name__ == "__main__":
    run_timestamp = datetime.now().isoformat(timespec="seconds")
    logger.info("Starting club price tracker run (run_timestamp=%s)", run_timestamp)
    all_results = []

    for brand in BRANDS:
        for club_type in CLUB_TYPES:
            logger.info("Scraping carlsgolfland.com: %s %s...", brand, club_type)
            try:
                results = CarlsGolflandScraper(brand, club_type, max_pages=1).run()
                logger.info("carlsgolfland.com %s %s: %d results", brand, club_type, len(results))
                all_results += results
            except Exception:
                logger.error("carlsgolfland.com %s %s failed", brand, club_type, exc_info=True)

            logger.info("Scraping tgw.com: %s %s...", brand, club_type)
            try:
                results = TgwScraper(brand, club_type).run()
                logger.info("tgw.com %s %s: %d results", brand, club_type, len(results))
                all_results += results
            except Exception:
                logger.error("tgw.com %s %s failed", brand, club_type, exc_info=True)

    new_df = pd.DataFrame(all_results)
    new_df.insert(0, "run_timestamp", run_timestamp)
    new_df = new_df.drop_duplicates(subset=DEDUP_KEY, keep="last")
    logger.info("Run complete: %d results", len(new_df))

    file_exists = CSV_PATH.exists()
    history_df = pd.read_csv(CSV_PATH) if file_exists else pd.DataFrame()

    log_price_drops(history_df, new_df, logger)

    new_df.to_csv(CSV_PATH, mode="a" if file_exists else "w", header=not file_exists, index=False)
    logger.info("Appended %d rows to %s (history now %d rows)", len(new_df), CSV_PATH.name, len(history_df) + len(new_df))
