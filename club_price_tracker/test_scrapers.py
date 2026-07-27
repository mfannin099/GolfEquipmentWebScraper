"""Driver script to sanity-check both site scrapers side by side.

Run from this directory: `uv run python test_scrapers.py`
"""

from datetime import datetime

import pandas as pd

from carlsgolfland_scraper import CarlsGolflandScraper
from tgw_scraper import TgwScraper
from config import BRANDS, CLUB_TYPES
from logging_config import get_logger

# Set True to also write this run's log lines to a timestamped file
# under logs/ (gitignored), so a run can be reviewed later without
# rerunning it.
WRITE_LOGS_TO_FILE = False

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

    df = pd.DataFrame(all_results)
    df.insert(0, "run_timestamp", run_timestamp)
    logger.info("Run complete: %d total results", len(df))
    df.to_csv("club_prices.csv", index=False)
    logger.info("Saved to club_prices.csv")
