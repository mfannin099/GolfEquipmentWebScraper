"""Scrapes club name + price from rockbottomgolf.com search results.

rockbottomgolf.com sits behind a Cloudflare JS challenge, so plain
requests gets a "Just a moment..." page instead of real HTML - this
needs a real browser (Selenium) to render first. Cloudflare's bot
detection also flags headless Chrome, so this defaults to a visible
(non-headless) browser window.

Some prices are hidden behind MAP pricing policy ("Add To Cart To See
Price"); the discounted price is still present in the page's HTML
(just visually hidden), so we read it directly from the DOM.
"""

import time
from urllib.parse import quote

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config import BRANDS, CLUB_TYPES, build_query

BASE_URL = "https://www.rockbottomgolf.com"


class RockBottomGolfScraper:
    def __init__(self, brand: str, club_type: str, headless: bool = False, timeout: int = 20):
        self.brand = brand
        self.club_type = club_type
        self.query = build_query(brand, club_type)
        self.timeout = timeout
        self.results = []

        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        self.driver = webdriver.Chrome(options=options)

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

    def scrape_current_page(self):
        cards = self.driver.find_elements(By.CSS_SELECTOR, "li.product")
        for card in cards:
            try:
                name = card.find_element(
                    By.CSS_SELECTOR, "h3.card-title a"
                ).get_attribute("textContent").strip()
            except Exception:
                continue

            if self.brand.lower() not in name.lower():
                continue

            link = card.find_element(By.CSS_SELECTOR, "h3.card-title a").get_attribute("href")
            price = self.parse_price(card)

            self.results.append({
                "brand": self.brand,
                "club_type": self.club_type,
                "name": name,
                "price": price,
                "link": link,
                "site": "rockbottomgolf.com",
            })

    def run(self, max_pages: int = 1):
        self.driver.get(self._search_url())
        self._wait_for_results()
        self.scrape_current_page()

        for _ in range(max_pages - 1):
            next_buttons = self.driver.find_elements(By.LINK_TEXT, "Next")
            if not next_buttons:
                break
            next_buttons[0].click()
            time.sleep(2)
            self._wait_for_results()
            self.scrape_current_page()

        self.driver.quit()
        return self.results


if __name__ == "__main__":
    for club_type in CLUB_TYPES:
        for brand in BRANDS:
            scraper = RockBottomGolfScraper(brand, club_type)
            results = scraper.run()
            print(f"\n=== {brand} {club_type} ({len(results)} results) ===")
            for r in results:
                print(f"  {r['name']}: {r['price']}")
