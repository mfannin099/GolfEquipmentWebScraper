"""Scrapes club name + price from tgw.com (The Golf Warehouse) search results.

Fronted by Cloudflare, but only as a CDN/WAF - no JS challenge is served
to a plain `requests` call with a browser User-Agent, unlike
rockbottomgolf.com (which this scraper replaces). Search lives at
`/l/search?k=<query>` and returns fully server-rendered `.product-tile`
cards with real prices, and (when discounted) both the sale and
"was" price right on the card - no product-page visit needed for
basic sale detection, unlike carlsgolfland.com.

The `/l/search` endpoint does loose keyword matching and mixes in
accessories (headcovers, shafts, grips) alongside actual clubs for
queries like "TaylorMade 7 wood" - NON_CLUB_TERMS filters those out.

fairway_wood_7 and iron_set still need a product-page visit to resolve
the specific variant, same as the other two sites - each product page
embeds a `var productJson = {...}` blob (mirrors carlsgolfland's
jsonConfig) with a `Variants` list. iron_set variants carry a
`SetComposition` string (e.g. "#5-PW"); fairway_wood_7 variants carry a
numeric `ClubLoft` (a "7 wood" is loft 21.0 - TGW doesn't label wood
variants by number, only by degree). The same productJson blob also
carries a rich HTML `Description` field, pulled down as `description`
on every result (not just sale/variant ones) since it's the same
request either way.

Listing tiles also carry three fields for free, no product-page visit
needed: the SKU (the `pid` attribute on the card's anchor), the product
image, and - on roughly half of listings - a star rating and review
count. The product page's `ReviewData` block carries the same rating at
full precision, so it wins when a product page is fetched anyway.
"""

import json
import re
from urllib.parse import quote, urljoin

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

BASE_URL = "https://www.tgw.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ClubPriceTracker/0.1)"}
SITE = "tgw.com"

NON_CLUB_TERMS = ["headcover", "shaft", "grip", " bag", "glove", "towel"]

# e.g. "4.7 out of 5 star rating (199 reviews )" - tiles without any
# reviews yet omit the element entirely rather than showing a zero.
RATING_RE = re.compile(r"([\d.]+)\s*out of\s*5.*?\(\s*([\d,]+)", re.S)


def _extract_product_json(html: str) -> dict | None:
    marker = "var productJson="
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


def _clean_description(html: str | None) -> str | None:
    if not html:
        return None
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text) or None


def _parse_money(text: str | None) -> float | None:
    if not text:
        return None
    try:
        return float(text.replace("$", "").replace(",", "").strip())
    except ValueError:
        return None


def _parse_rating(text: str | None) -> tuple[float | None, int | None]:
    if not text:
        return None, None
    match = RATING_RE.search(text)
    if not match:
        return None, None
    return float(match.group(1)), int(match.group(2).replace(",", ""))


def _tile_image_url(img) -> str | None:
    """Everything past the first couple of tiles is lazy-loaded: `src` holds
    a placeholder graphic and the real URL sits in `data-src`. Reading only
    `src` would leave images on ~95% of a page's results.
    """
    if img is None:
        return None
    src = img.get("data-src") or img.get("src")
    if not src or "placeholder" in src:
        return None
    return urljoin(BASE_URL, src)


class TgwScraper:
    def __init__(self, brand: str, club_type: str):
        self.brand = brand
        self.club_type = club_type
        self.query = build_query(brand, club_type)
        self.results = []
        self.rate_limiter = RateLimiter(RATE_LIMIT_SECONDS)
        self.variant_target = VARIANT_TARGETS.get(SITE, {}).get(club_type)

    def _get(self, url: str) -> requests.Response:
        self.rate_limiter.wait()
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp

    def _search_url(self) -> str:
        return f"{BASE_URL}/l/search?k={quote(self.query)}"

    @staticmethod
    def _discount_pct(old_price, final_price):
        if not old_price or not final_price or old_price <= final_price:
            return None
        return round((old_price - final_price) / old_price * 100, 1)

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
            name_lower = name.lower()

            if self.brand.lower() not in name_lower:
                continue
            if any(term in name_lower for term in MENS_ONLY_EXCLUDE_TERMS):
                continue
            if any(term in name_lower for term in NON_CLUB_TERMS):
                continue

            price = _parse_money(tile.select_one(".regular-price").get_text() if tile.select_one(".regular-price") else None)
            was_price = _parse_money(tile.select_one(".was-price .price").get_text() if tile.select_one(".was-price .price") else None)

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
                "discount_pct": self._discount_pct(was_price, price),
                "on_sale": was_price is not None,
                "stock_status": None,
                "rating": rating,
                "review_count": review_count,
                "image_url": _tile_image_url(tile.select_one(".product-image img")),
                "description": None,
                "link": urljoin(BASE_URL, link_el["href"]),
                "site": SITE,
            })
        return True

    def _match_variant(self, variants: list[dict]) -> dict | None:
        """Picks the variant matching self.variant_target - a SetComposition
        substring for iron_set, a ClubLoft degree match for fairway_wood_7.
        Returns None if there's no variant_target or no match found.
        """
        if not self.variant_target or not variants:
            return None

        candidates = []
        if self.club_type == "iron_set":
            target = self.variant_target.lower()
            candidates = [
                v for v in variants
                if v.get("SetComposition") and target in v["SetComposition"].lower()
            ]
        elif self.club_type == "fairway_wood_7":
            target_loft = float(self.variant_target)
            candidates = [
                v for v in variants
                if v.get("ClubLoft") is not None and float(v["ClubLoft"]) == target_loft
            ]

        if not candidates:
            return None
        return min(candidates, key=lambda v: _parse_money(v.get("Price")) or float("inf"))

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
        obj = _extract_product_json(resp.text)
        if not obj:
            return details

        details["description"] = _clean_description(obj.get("Description"))

        # Full-precision rating/review count, versus the tile's rounded
        # one-decimal display value.
        review_data = obj.get("ReviewData") or {}
        total_reviews = review_data.get("TotalReviews")
        if total_reviews:
            details["rating"] = round(float(review_data["AverageRating"]), 2)
            details["review_count"] = int(total_reviews)

        variants = obj.get("Variants") or []
        match = self._match_variant(variants)

        if match:
            price = _parse_money(match.get("Price"))
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
            # Variant-level SKU, more specific than the tile's product-level
            # one (which points at the default variant).
            details["variant_sku"] = match.get("Sku")
            details["original_price"] = original
            details["discount_pct"] = self._discount_pct(original, price)
            details["stock_status"] = self._variant_stock_status(match)
        elif variants:
            details["stock_status"] = self._variant_stock_status(variants[0])

        return details

    def run(self):
        resp = self._get(self._search_url())
        self._parse_page(resp.text)

        # Every result gets a product-page visit (capped by
        # MAX_VARIANT_LOOKUPS) since description enrichment is wanted
        # everywhere here, not just for sale items - unlike
        # carlsgolfland, tgw.com isn't Cloudflare-throttled so the extra
        # requests are cheap.
        targets = self.results if MAX_VARIANT_LOOKUPS is None else self.results[:MAX_VARIANT_LOOKUPS]
        for result in targets:
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
