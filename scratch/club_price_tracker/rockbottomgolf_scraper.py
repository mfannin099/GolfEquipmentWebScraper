"""Scrapes club name + price from rockbottomgolf.com search results.

rockbottomgolf.com sits behind a Cloudflare JS challenge, so plain
requests gets a "Just a moment..." page instead of real HTML - this
needs a real browser (Selenium) to render first. Cloudflare's bot
detection also flags headless Chrome, so this defaults to a visible
(non-headless) browser window.

Some prices are hidden behind MAP pricing policy ("Add To Cart To See
Price"); the discounted price is still present in the page's HTML
(just visually hidden), so we read it directly from the DOM.

iron_set is handled by filtering listing names (this site lists each
iron-set size, e.g. "(7 Iron Set)", as its own product/listing entry).
fairway_wood_7 isn't - loft is a same-page dropdown - so for that
club_type we open each product page and select the matching loft
option to read its price.

Sale/discount info (a "Their Price $X - Save $Y (Z% Off)" block) is
already present right on the listing card, so on_sale/original_price/
discount_pct come for free with no extra product-page visit. Stock
status isn't shown on the listing, and isn't worth an extra request on
a Cloudflare-fronted site just for that, so it's always None here
(carlsgolfland.com's scraper does report it).
"""

import re
from urllib.parse import quote

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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

BASE_URL = "https://www.rockbottomgolf.com"
SITE = "rockbottomgolf.com"

# "Their Price $549.99 - Save $310.00 (56% Off)"
SAVINGS_RE = re.compile(r"Their Price\s*\$([\d,]+\.\d+).*?\(([\d.]+)%\s*Off\)", re.IGNORECASE | re.DOTALL)


class RockBottomGolfScraper:
    def __init__(self, brand: str, club_type: str, headless: bool = False, timeout: int = 20):
        self.brand = brand
        self.club_type = club_type
        self.query = build_query(brand, club_type)
        self.timeout = timeout
        self.results = []
        self.rate_limiter = RateLimiter(RATE_LIMIT_SECONDS)
        self.variant_target = VARIANT_TARGETS.get(SITE, {}).get(club_type)
        self.headless = headless

        self.driver = self._new_driver()

    def _new_driver(self):
        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        return webdriver.Chrome(options=options)

    def _restart_driver(self):
        try:
            self.driver.quit()
        except Exception:
            pass
        self.driver = self._new_driver()

    def _get(self, url: str):
        self.rate_limiter.wait()
        self.driver.get(url)

    def _search_url(self) -> str:
        return f"{BASE_URL}/search.php?search_query={quote(self.query)}"

    def _wait_for_results(self):
        WebDriverWait(self.driver, self.timeout).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, "li.product") or
            "no results" in d.page_source.lower()
        )

    def parse_price(self, card) -> float | None:
        try:
            price_text = card.find_element(
                By.CSS_SELECTOR, "span.price--withoutTax"
            ).get_attribute("textContent").strip()
        except Exception:
            return None
        price_text = price_text.replace("$", "").replace(",", "")
        try:
            return float(price_text)
        except ValueError:
            return None

    def parse_savings(self, card) -> tuple[float | None, float | None]:
        """Reads the "Their Price $X - Save $Y (Z% Off)" block already on
        the listing card, if present. Returns (original_price, discount_pct).
        """
        try:
            text = card.find_element(
                By.CSS_SELECTOR, ".card-text--price"
            ).get_attribute("textContent")
        except Exception:
            return None, None

        match = SAVINGS_RE.search(text.replace("\n", " "))
        if not match:
            return None, None
        return float(match.group(1).replace(",", "")), float(match.group(2))

    def scrape_current_page(self):
        cards = self.driver.find_elements(By.CSS_SELECTOR, "li.product")
        for card in cards:
            try:
                name = card.find_element(
                    By.CSS_SELECTOR, "h3.card-title a"
                ).get_attribute("textContent").strip()
            except Exception:
                continue

            name_lower = name.lower()
            if self.brand.lower() not in name_lower:
                continue

            if any(term in name_lower for term in MENS_ONLY_EXCLUDE_TERMS):
                continue

            # For iron sets, the set size is baked into the listing name
            # (e.g. "(7 Iron Set)") rather than a same-page variant, so
            # filtering here is enough - no product page visit needed.
            if self.club_type == "iron_set" and self.variant_target:
                if self.variant_target.lower() not in name_lower:
                    continue

            link = card.find_element(By.CSS_SELECTOR, "h3.card-title a").get_attribute("href")
            price = self.parse_price(card)
            original_price, discount_pct = self.parse_savings(card)

            self.results.append({
                "brand": self.brand,
                "club_type": self.club_type,
                "name": name,
                "variant": None,
                "price": price,
                "original_price": original_price,
                "discount_pct": discount_pct,
                "on_sale": discount_pct is not None,
                "stock_status": None,
                "link": link,
                "site": SITE,
            })

    def _resolve_variant_price(self, product_url: str):
        """Open a product page, select the loft option matching
        self.variant_target, and read the resulting price.

        Returns (price, matched_option_text), or (None, None) if the
        product has no matching loft selector.
        """
        self._get(product_url)

        # The product page needs a beat to render past the Cloudflare
        # challenge; without this wait, the select/price search below can
        # run before the DOM exists and silently find nothing.
        WebDriverWait(self.driver, self.timeout).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, 'select[id^="attribute_select_"]') or
            d.find_elements(By.CSS_SELECTOR, "[data-product-price-without-tax]")
        )

        target = self.variant_target.lower()
        matching_select = None
        matching_value = None
        matching_text = None

        for select_el in self.driver.find_elements(By.CSS_SELECTOR, 'select[id^="attribute_select_"]'):
            for option in select_el.find_elements(By.TAG_NAME, "option"):
                if target in option.text.strip().lower():
                    matching_select = select_el
                    matching_value = option.get_attribute("value")
                    matching_text = option.text.strip()
                    break
            if matching_select:
                break

        if not matching_select or not matching_value:
            return None, None

        Select(matching_select).select_by_value(matching_value)

        try:
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-product-price-without-tax]"))
            )
        except Exception:
            return None, None

        price_text = self.driver.find_element(
            By.CSS_SELECTOR, "[data-product-price-without-tax]"
        ).get_attribute("textContent").strip().replace("$", "").replace(",", "")

        try:
            return float(price_text), matching_text
        except ValueError:
            return None, None

    def _resolve_variant_price_with_retry(self, name: str, product_url: str, attempts: int = 3):
        """Wraps _resolve_variant_price with retries, restarting the
        browser if the session/window died (observed with rapid
        back-to-back product-page navigations on this Cloudflare-fronted
        site).
        """
        for attempt in range(1, attempts + 1):
            try:
                return self._resolve_variant_price(product_url)
            except WebDriverException as e:
                print(f"  [{name}] browser error on attempt {attempt}/{attempts}: {e}")
                self._restart_driver()
            except Exception as e:
                print(f"  [{name}] variant lookup failed: {e}")
                return None, None
        print(f"  [{name}] giving up after {attempts} attempts, keeping listing price")
        return None, None

    def run(self, max_pages: int = 1):
        self._get(self._search_url())
        self._wait_for_results()
        self.scrape_current_page()

        for _ in range(max_pages - 1):
            next_buttons = self.driver.find_elements(By.LINK_TEXT, "Next")
            if not next_buttons:
                break
            self.rate_limiter.wait()
            next_buttons[0].click()
            self._wait_for_results()
            self.scrape_current_page()

        if self.club_type == "fairway_wood_7" and self.variant_target:
            targets = self.results if MAX_VARIANT_LOOKUPS is None else self.results[:MAX_VARIANT_LOOKUPS]
            for result in targets:
                price, label = self._resolve_variant_price_with_retry(result["name"], result["link"])
                if price is not None:
                    result["price"] = price
                    result["variant"] = label

        try:
            self.driver.quit()
        except Exception:
            pass
        return self.results


if __name__ == "__main__":
    for club_type in CLUB_TYPES:
        for brand in BRANDS:
            scraper = RockBottomGolfScraper(brand, club_type)
            results = scraper.run()
            print(f"\n=== {brand} {club_type} ({len(results)} results) ===")
            for r in results:
                print(f"  {r['name']} [{r['variant']}]: {r['price']} "
                      f"(sale={r['on_sale']}, was={r['original_price']}, -{r['discount_pct']}%)")
