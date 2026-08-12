"""Scrapes club listings from tgw.com (The Golf Warehouse).

Cloudflare-fronted but only as a CDN/WAF - no JS challenge for a plain
`requests` call with a browser User-Agent. Search at `/l/search?k=`
returns server-rendered `.product-tile` cards carrying price and, when
discounted, the "was" price, so sale detection needs no product page.

Tiles also give the SKU (the anchor's `pid`), the image, and - on about
half of listings - a star rating and review count.

Product pages embed a `var productJson = {...}` blob whose `Variants`
resolve the exact loft or set composition, plus stock status, a full
`Description`, and full-precision `ReviewData`.
"""

import re
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

from .config import BRANDS, CLUB_TYPES
from .scraper_base import (
    BaseScraper,
    clean_text,
    discount_pct,
    extract_json_blob,
    parse_money,
)

BASE_URL = "https://www.tgw.com"
PRODUCT_JSON_MARKER = "var productJson="

# "4.7 out of 5 star rating (199 reviews )". Unreviewed tiles omit the
# element rather than showing a zero.
RATING_RE = re.compile(r"([\d.]+)\s*out of\s*5.*?\(\s*([\d,]+)", re.S)


def _parse_rating(text: str | None) -> tuple[float | None, int | None]:
    if not text:
        return None, None
    match = RATING_RE.search(text)
    if not match:
        return None, None
    return float(match.group(1)), int(match.group(2).replace(",", ""))


def _tile_image_url(img) -> str | None:
    """Tiles past the first couple are lazy-loaded: `src` is a placeholder
    and the real URL sits in `data-src`.
    """
    if img is None:
        return None
    src = img.get("data-src") or img.get("src")
    if not src or "placeholder" in src:
        return None
    return urljoin(BASE_URL, src)


class TgwScraper(BaseScraper):
    SITE = "tgw.com"

    def _search_url(self) -> str:
        return f"{BASE_URL}/l/search?k={quote(self.query)}"

    def _parse_page(self, html: str):
        soup = BeautifulSoup(html, "html.parser")
        tiles = soup.select(".product-tile")
        if not tiles:
            return False

        for tile in tiles:
            name_el = tile.select_one(".product-name span")
            link_el = tile.select_one("a.anchor-container")
            if not name_el or not link_el:
                continue
            name = name_el.get_text(strip=True)
            if not self._is_wanted(name):
                continue

            price_el = tile.select_one(".regular-price")
            was_price_el = tile.select_one(".was-price .price")
            price = parse_money(price_el.get_text() if price_el else None)
            was_price = parse_money(was_price_el.get_text() if was_price_el else None)

            rating_el = tile.select_one(".rating-count")
            rating, review_count = _parse_rating(rating_el.get_text(" ", strip=True) if rating_el else None)

            self.results.append({
                "brand": self.brand,
                "club_type": self.club_type,
                "name": name,
                "variant": None,
                "sku": link_el.get("pid") or None,
                "price": price,
                "original_price": was_price,
                "discount_pct": discount_pct(was_price, price),
                "on_sale": was_price is not None,
                "stock_status": None,
                "rating": rating,
                "review_count": review_count,
                "image_url": _tile_image_url(tile.select_one(".product-image img")),
                "description": None,
                "link": urljoin(BASE_URL, link_el["href"]),
                "site": self.SITE,
            })
        return True

    def _match_variant(self, variants: list[dict]) -> dict | None:
        """Picks the variant matching self.variant_target.

        The target's shape picks the field, not club_type: numeric
        ("21.0") is a ClubLoft in degrees, anything else ("5-PW") a
        SetComposition substring. So a new loft-based club type needs only
        a config.VARIANT_TARGETS entry - keying on club_type meant an
        unrecognised type silently matched nothing.
        """
        if not self.variant_target or not variants:
            return None

        try:
            target_loft = float(self.variant_target)
        except ValueError:
            target_loft = None

        if target_loft is not None:
            candidates = [
                v for v in variants
                if v.get("ClubLoft") is not None and float(v["ClubLoft"]) == target_loft
            ]
        else:
            target = self.variant_target.lower()
            candidates = [
                v for v in variants
                if v.get("SetComposition") and target in v["SetComposition"].lower()
            ]

        if not candidates:
            return None
        return min(candidates, key=lambda v: parse_money(v.get("Price")) or float("inf"))

    @staticmethod
    def _variant_stock_status(variant: dict) -> str | None:
        if variant.get("HasBackorderMessage") and variant.get("InventoryMessage"):
            return variant["InventoryMessage"]
        if variant.get("StockMessage"):
            return variant["StockMessage"]
        return "In Stock"

    def _fetch_product_details(self, product_url: str) -> dict:
        """Opens a product page and pulls the description and review data
        (every call) plus, when self.variant_target is set, the exact
        variant's price, original price/discount, SKU, and stock status.
        """
        details = {
            "description": None,
            "rating": None,
            "review_count": None,
            "variant_price": None,
            "variant_label": None,
            "variant_sku": None,
            "original_price": None,
            "discount_pct": None,
            "stock_status": None,
        }

        resp = self._get(product_url)
        obj = extract_json_blob(resp.text, PRODUCT_JSON_MARKER)
        if not obj:
            return details

        details["description"] = clean_text(obj.get("Description"))

        # Full precision, versus the tile's rounded display value.
        review_data = obj.get("ReviewData") or {}
        total_reviews = review_data.get("TotalReviews")
        if total_reviews:
            details["rating"] = round(float(review_data["AverageRating"]), 2)
            details["review_count"] = int(total_reviews)

        variants = obj.get("Variants") or []
        match = self._match_variant(variants)

        if match:
            price = parse_money(match.get("Price"))
            original = match.get("OriginalPrice") or obj.get("OriginalPrice")
            # OriginalPrice is sometimes populated equal to the current
            # price when there's no real "was" price - only report it
            # when it actually reflects a discount.
            if original and price and original <= price:
                original = None
            details["variant_price"] = price
            details["variant_label"] = (
                match.get("SetComposition") if self.club_type == "iron_set"
                else f'{match.get("ClubLoft")}°'
            )
            # More specific than the tile's product-level SKU.
            details["variant_sku"] = match.get("Sku")
            details["original_price"] = original
            details["discount_pct"] = discount_pct(original, price)
            details["stock_status"] = self._variant_stock_status(match)
        elif variants:
            details["stock_status"] = self._variant_stock_status(variants[0])

        return details

    def run(self):
        # max_pages is ignored: /l/search returns everything in one
        # response.
        resp = self._get(self._search_url())
        self._parse_page(resp.text)

        # Every result is a candidate: descriptions are wanted
        # everywhere, not just on sale items.
        for result in self._capped(self.results):
            details = self._fetch_product_details(result["link"])
            result["description"] = details["description"]
            if details["review_count"] is not None:
                result["rating"] = details["rating"]
                result["review_count"] = details["review_count"]
            if details["variant_price"] is not None:
                result["price"] = details["variant_price"]
                result["variant"] = details["variant_label"]
                result["original_price"] = details["original_price"]
                result["discount_pct"] = details["discount_pct"]
                result["on_sale"] = details["discount_pct"] is not None
                if details["variant_sku"]:
                    result["sku"] = details["variant_sku"]
            if details["stock_status"] is not None:
                result["stock_status"] = details["stock_status"]

        return self.results


if __name__ == "__main__":
    for club_type in CLUB_TYPES:
        for brand in BRANDS:
            scraper = TgwScraper(brand, club_type)
            results = scraper.run()
            print(f"\n=== {brand} {club_type} ({len(results)} results) ===")
            for r in results:
                print(f"  {r['name']} [{r['variant']}] sku={r['sku']}: {r['price']} "
                      f"(sale={r['on_sale']}, was={r['original_price']}, "
                      f"-{r['discount_pct']}%, stock={r['stock_status']}, "
                      f"rating={r['rating']} of {r['review_count']} reviews)")
