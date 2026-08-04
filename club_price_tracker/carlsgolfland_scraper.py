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

The listing page does carry the SKU for free, on each card's
`data-bv-product-id` (a Bazaarvoice hook), along with the product image.
That SKU doubles as the product's MPN in the page's JSON-LD, which makes
it the best available handle for matching a club across sites. The
neighbouring star rating is *not* usable - Bazaarvoice renders it in the
browser, so it never appears in the HTML a plain request gets back.
"""

import json
from urllib.parse import quote

from bs4 import BeautifulSoup

from config import BRANDS, CLUB_TYPES, MAX_VARIANT_LOOKUPS
from scraper_base import BaseScraper, clean_text, discount_pct, extract_json_blob

BASE_URL = "https://www.carlsgolfland.com"
JSON_CONFIG_MARKER = '"jsonConfig"'

# schema.org availability URLs -> the same wording tgw.com's scraper
# reports, so stock_status means one thing across sites.
AVAILABILITY_LABELS = {
    "instock": "In Stock",
    "outofstock": "Out of Stock",
    "backorder": "Back Order",
    "preorder": "Pre-Order",
    "limitedavailability": "Limited Availability",
    "discontinued": "Discontinued",
    "soldout": "Out of Stock",
}


def _product_availability(soup: BeautifulSoup) -> str | None:
    """Reads stock status out of the page's JSON-LD Product block.

    Backs up the `.stock` element, which is present on some product pages
    and empty on others.
    """
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(data, dict) or data.get("@type") != "Product":
            continue
        offers = data.get("offers") or []
        if isinstance(offers, dict):
            offers = [offers]
        for offer in offers:
            availability = offer.get("availability")
            if availability:
                key = availability.rsplit("/", 1)[-1].lower()
                return AVAILABILITY_LABELS.get(key, availability.rsplit("/", 1)[-1])
    return None


def _product_description(soup: BeautifulSoup) -> str | None:
    """The product page's real description tab. Preferred over the JSON-LD
    `description`, which is just SEO boilerplate ("Shop Now and Save Big
    on ... at Carl's Golfland").
    """
    return clean_text(soup.select_one(".product.attribute.description"))


class CarlsGolflandScraper(BaseScraper):
    SITE = "carlsgolfland.com"

    def __init__(self, brand: str, club_type: str, max_pages: int = 3):
        super().__init__(brand, club_type)
        self.max_pages = max_pages

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
            if not self._is_wanted(name):
                continue

            price_el = item.select_one("[data-price-amount]")
            price = float(price_el["data-price-amount"]) if price_el else None

            sku_el = item.select_one("[data-bv-product-id]")
            image_el = item.select_one("img.product-image-photo")

            self.results.append({
                "brand": self.brand,
                "club_type": self.club_type,
                "name": name,
                "variant": None,
                "sku": sku_el.get("data-bv-product-id") if sku_el else None,
                "price": price,
                "original_price": None,
                "discount_pct": None,
                "on_sale": "on sale" in name.lower(),
                "stock_status": None,
                # Bazaarvoice renders ratings client-side, so there's
                # nothing to read here - see the module docstring.
                "rating": None,
                "review_count": None,
                "image_url": image_el.get("src") if image_el else None,
                "description": None,
                "link": name_el.get("href"),
                "site": self.SITE,
            })
        return True

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
            "description": None,
        }

        resp = self._get(product_url)
        soup = BeautifulSoup(resp.text, "html.parser")

        details["description"] = _product_description(soup)

        stock_el = soup.select_one(".product-info-stock-sku .stock")
        stock_text = stock_el.get_text(strip=True) if stock_el else None
        details["stock_status"] = stock_text or _product_availability(soup)

        cfg = extract_json_blob(resp.text, JSON_CONFIG_MARKER)
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
            details["discount_pct"] = discount_pct(old_price, final_price)

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
            result["description"] = details["description"]

        return self.results


if __name__ == "__main__":
    for club_type in CLUB_TYPES:
        for brand in BRANDS:
            scraper = CarlsGolflandScraper(brand, club_type, max_pages=1)
            results = scraper.run()
            print(f"\n=== {brand} {club_type} ({len(results)} results) ===")
            for r in results:
                print(f"  {r['name']} [{r['variant']}] sku={r['sku']}: {r['price']} "
                      f"(sale={r['on_sale']}, was={r['original_price']}, "
                      f"-{r['discount_pct']}%, stock={r['stock_status']})")
