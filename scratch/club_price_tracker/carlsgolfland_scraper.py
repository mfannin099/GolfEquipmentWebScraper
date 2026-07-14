"""Scrapes club name + price from carlsgolfland.com search results.

Not Cloudflare-protected, so plain requests + BeautifulSoup works (no
Selenium needed). Site search redirects "/catalogsearch/result/?q=..."
to a Searchspring-powered "/search/<query>" page; pagination is "?p=N".
"""

import time
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from config import BRANDS, CLUB_TYPES, build_query

BASE_URL = "https://www.carlsgolfland.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ClubPriceTracker/0.1)"}


class CarlsGolflandScraper:
    def __init__(self, brand: str, club_type: str, max_pages: int = 3, delay: float = 1.0):
        self.brand = brand
        self.club_type = club_type
        self.query = build_query(brand, club_type)
        self.max_pages = max_pages
        self.delay = delay
        self.results = []

    def _page_url(self, page: int) -> str:
        url = f"{BASE_URL}/search/{quote(self.query)}"
        return url if page == 1 else f"{url}?p={page}"

    def _parse_page(self, html: str):
        soup = BeautifulSoup(html, "html.parser")
        items = soup.select(".product-item")
        if not items:
            return False

        for item in items:
            name_el = item.select_one(".product-item-name a")
            if not name_el:
                continue
            name = name_el.get_text(strip=True)

            # Only keep results that actually mention the brand - search
            # can return loosely related products too.
            if self.brand.lower() not in name.lower():
                continue

            price_el = item.select_one("[data-price-amount]")
            price = float(price_el["data-price-amount"]) if price_el else None

            self.results.append({
                "brand": self.brand,
                "club_type": self.club_type,
                "name": name,
                "price": price,
                "link": name_el.get("href"),
                "site": "carlsgolfland.com",
            })
        return True

    def run(self):
        for page in range(1, self.max_pages + 1):
            resp = requests.get(self._page_url(page), headers=HEADERS, timeout=15)
            resp.raise_for_status()
            found_items = self._parse_page(resp.text)
            if not found_items:
                break
            time.sleep(self.delay)
        return self.results


if __name__ == "__main__":
    for club_type in CLUB_TYPES:
        for brand in BRANDS:
            scraper = CarlsGolflandScraper(brand, club_type, max_pages=1)
            results = scraper.run()
            print(f"\n=== {brand} {club_type} ({len(results)} results) ===")
            for r in results:
                print(f"  {r['name']}: {r['price']}")
