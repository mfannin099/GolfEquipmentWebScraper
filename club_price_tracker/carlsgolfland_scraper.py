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

The listing page never shows a struck-through "was" price - only the
current one - so true discount/MSRP info also requires a product-page
visit; it's read off the same jsonConfig blob (oldPrice vs finalPrice)
already being fetched for variant resolution, plus a stock-status
element on the page. See _fetch_product_details.
"""

import json
import re
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from config import (
    BRANDS,
    CLUB_TYPES,
    VARIANT_TARGETS,
    RATE_LIMIT_SECONDS,
    MAX_VARIANT_LOOKUPS,
    MENS_ONLY_EXCLUDE_TERMS,
    build_query,
)
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
            name_lower = name.lower()
            if self.brand.lower() not in name_lower:
                continue

            if any(term in name_lower for term in MENS_ONLY_EXCLUDE_TERMS):
                continue

            price_el = item.select_one("[data-price-amount]")
            price = float(price_el["data-price-amount"]) if price_el else None

            self.results.append({
                "brand": self.brand,
                "club_type": self.club_type,
                "name": name,
                "variant": None,
                "price": price,
                "original_price": None,
                "discount_pct": None,
                "on_sale": "on sale" in name_lower,
                "stock_status": None,
                "link": name_el.get("href"),
                "site": SITE,
            })
        return True

    @staticmethod
    def _discount_pct(old_price, final_price):
        if not old_price or old_price <= final_price:
            return None
        return round((old_price - final_price) / old_price * 100, 1)

    def _fetch_product_details(self, product_url: str) -> dict:
        """Open a product page and pull everything the listing page can't
        show: the exact variant price (when self.variant_target is set),
        true MSRP/discount (the listing never shows a "was" price), and
        stock status.
        """
        details = {
            "variant_price": None,
            "variant_label": None,
            "original_price": None,
            "discount_pct": None,
            "stock_status": None,
        }

        resp = self._get(product_url)
        soup = BeautifulSoup(resp.text, "html.parser")

        stock_el = soup.select_one(".product-info-stock-sku .stock")
        if stock_el:
            details["stock_status"] = stock_el.get_text(strip=True)

        cfg = _extract_json_config(resp.text)
        if not cfg:
            return details

        price_info = None

        if self.variant_target:
            target = self.variant_target.lower()
            match = None
            for attr_id, attr in cfg.get("attributes", {}).items():
                for option in attr.get("options", []):
                    if target in option["label"].lower():
                        match = (attr_id, str(option["id"]), option["label"])
                        break
                if match:
                    break

            if match:
                attr_id, option_id, label = match
                candidates = []
                for product_id, attr_selection in cfg.get("index", {}).items():
                    if attr_selection.get(attr_id) == option_id:
                        info = cfg.get("optionPrices", {}).get(product_id)
                        if info:
                            candidates.append(info)
                if candidates:
                    price_info = min(candidates, key=lambda i: i["finalPrice"]["amount"])
                    details["variant_price"] = price_info["finalPrice"]["amount"]
                    details["variant_label"] = label
        else:
            price_info = cfg.get("prices")

        if price_info:
            final_price = price_info["finalPrice"]["amount"]
            old_price = price_info.get("oldPrice", {}).get("amount")
            details["original_price"] = old_price
            details["discount_pct"] = self._discount_pct(old_price, final_price)

        return details

    def run(self):
        for page in range(1, self.max_pages + 1):
            resp = self._get(self._page_url(page))
            found_items = self._parse_page(resp.text)
            if not found_items:
                break

        # Which listings are worth an extra product-page request: when
        # there's a variant to resolve, every listing needs one to get an
        # accurate price; otherwise only items already flagged "ON SALE"
        # by name are worth the trip, to pull real MSRP/discount + stock.
        if self.variant_target:
            candidates = self.results
        else:
            candidates = [r for r in self.results if r["on_sale"]]

        targets = candidates if MAX_VARIANT_LOOKUPS is None else candidates[:MAX_VARIANT_LOOKUPS]
        for result in targets:
            details = self._fetch_product_details(result["link"])
            if details["variant_price"] is not None:
                result["price"] = details["variant_price"]
                result["variant"] = details["variant_label"]
            result["original_price"] = details["original_price"]
            result["discount_pct"] = details["discount_pct"]
            result["stock_status"] = details["stock_status"]

        return self.results


if __name__ == "__main__":
    for club_type in CLUB_TYPES:
        for brand in BRANDS:
            scraper = CarlsGolflandScraper(brand, club_type, max_pages=1)
            results = scraper.run()
            print(f"\n=== {brand} {club_type} ({len(results)} results) ===")
            for r in results:
                print(f"  {r['name']} [{r['variant']}]: {r['price']} "
                      f"(sale={r['on_sale']}, was={r['original_price']}, "
                      f"-{r['discount_pct']}%, stock={r['stock_status']})")
