"""Scrapes club name + price from carlsgolfland.com search results.

Not Cloudflare-protected, so plain requests + BeautifulSoup works (no
Selenium needed). Site search redirects "/catalogsearch/result/?q=..."
to a Searchspring-powered "/search/<query>" page; pagination is "?p=N".

fairway_wood_7 and iron_set are sold as one configurable product with a
loft/set-makeup dropdown rather than a distinct listing per variant, so
the search-result price is for the product family, not our specific
target. Each product page embeds a "jsonConfig" blob mapping every
attribute-option combination to its own simple-product price - we pull
that down and pick out the variant matching config.VARIANT_TARGETS.
"""

import json
import re
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from config import BRANDS, CLUB_TYPES, VARIANT_TARGETS, RATE_LIMIT_SECONDS, MAX_VARIANT_LOOKUPS, build_query
from rate_limiter import RateLimiter

BASE_URL = "https://www.carlsgolfland.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ClubPriceTracker/0.1)"}
SITE = "carlsgolfland.com"


def _extract_json_config(html: str) -> dict | None:
    marker = '"jsonConfig"'
    marker_idx = html.find(marker)
    if marker_idx == -1:
        return None

    start = html.index("{", marker_idx)
    depth = 0
    for i in range(start, len(html)):
        if html[i] == "{":
            depth += 1
        elif html[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(html[start:i + 1])
    return None


class CarlsGolflandScraper:
    def __init__(self, brand: str, club_type: str, max_pages: int = 3):
        self.brand = brand
        self.club_type = club_type
        self.query = build_query(brand, club_type)
        self.max_pages = max_pages
        self.results = []
        self.rate_limiter = RateLimiter(RATE_LIMIT_SECONDS)
        self.variant_target = VARIANT_TARGETS.get(SITE, {}).get(club_type)

    def _get(self, url: str) -> requests.Response:
        self.rate_limiter.wait()
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp

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
                "variant": None,
                "price": price,
                "link": name_el.get("href"),
                "site": SITE,
            })
        return True

    def _resolve_variant_price(self, product_url: str):
        """Look up the price for the option matching self.variant_target.

        Returns (price, matched_option_label), or (None, None) if the
        product has no configurable options or nothing matches.
        """
        resp = self._get(product_url)
        cfg = _extract_json_config(resp.text)
        if not cfg:
            return None, None

        target = self.variant_target.lower()
        match = None
        for attr_id, attr in cfg.get("attributes", {}).items():
            for option in attr.get("options", []):
                if target in option["label"].lower():
                    match = (attr_id, str(option["id"]), option["label"])
                    break
            if match:
                break
        if not match:
            return None, None

        attr_id, option_id, label = match
        candidate_prices = []
        for product_id, attr_selection in cfg.get("index", {}).items():
            if attr_selection.get(attr_id) == option_id:
                price_info = cfg.get("optionPrices", {}).get(product_id)
                if price_info:
                    candidate_prices.append(price_info["finalPrice"]["amount"])

        if not candidate_prices:
            return None, None
        return min(candidate_prices), label

    def run(self):
        for page in range(1, self.max_pages + 1):
            resp = self._get(self._page_url(page))
            found_items = self._parse_page(resp.text)
            if not found_items:
                break

        if self.variant_target:
            targets = self.results if MAX_VARIANT_LOOKUPS is None else self.results[:MAX_VARIANT_LOOKUPS]
            for result in targets:
                price, label = self._resolve_variant_price(result["link"])
                if price is not None:
                    result["price"] = price
                    result["variant"] = label

        return self.results


if __name__ == "__main__":
    for club_type in CLUB_TYPES:
        for brand in BRANDS:
            scraper = CarlsGolflandScraper(brand, club_type, max_pages=1)
            results = scraper.run()
            print(f"\n=== {brand} {club_type} ({len(results)} results) ===")
            for r in results:
                print(f"  {r['name']} [{r['variant']}]: {r['price']}")
