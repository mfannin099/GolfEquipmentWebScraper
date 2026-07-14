"""Driver script to sanity-check both site scrapers side by side.

Run from this directory: `uv run python test_scrapers.py`
"""

import pandas as pd

from carlsgolfland_scraper import CarlsGolflandScraper
from rockbottomgolf_scraper import RockBottomGolfScraper
from config import BRANDS, CLUB_TYPES

if __name__ == "__main__":
    all_results = []

    for brand in BRANDS:
        for club_type in CLUB_TYPES:
            print(f"\nScraping carlsgolfland.com: {brand} {club_type}...")
            all_results += CarlsGolflandScraper(brand, club_type, max_pages=1).run()

            print(f"Scraping rockbottomgolf.com: {brand} {club_type}...")
            all_results += RockBottomGolfScraper(brand, club_type).run()

    df = pd.DataFrame(all_results)
    print("\n", df)
    df.to_csv("club_prices.csv", index=False)
    print("\nSaved to club_prices.csv")
