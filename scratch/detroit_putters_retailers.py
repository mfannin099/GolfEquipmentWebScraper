## TODO - scrape retailers page 
## TODO - clean
## TODO - parse their websites/create some sort of search


from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class RetailerScraper:

    URL = "https://detroitputterco.com/pages/retailer-locations-1"

    def __init__(self, timeout=10, headless=False):
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless")
        self.driver = webdriver.Chrome(options=options)
        self.timeout = timeout
        self.retailers = []

    def load_page(self):
        self.driver.get(self.URL)
        WebDriverWait(self.driver, self.timeout).until(
            EC.presence_of_element_located((By.CLASS_NAME, "rich-text__text"))
        )

    def parse_retailers(self):
        div = self.driver.find_element(By.CLASS_NAME, "rich-text__text")
        paragraphs = div.find_elements(By.TAG_NAME, "p")

        for p in paragraphs:
            name = p.find_element(By.TAG_NAME, "strong").text.strip()
            address = self.driver.execute_script(
                "return arguments[0].lastChild.textContent;", p
            ).strip()
            self.retailers.append({"name": name, "address": address})

    def print_retailers(self):
        for r in self.retailers:
            print(f"{r['name']}")
            print(f"  {r['address']}")
            print()

    def run(self):
        try:
            self.load_page()
            self.parse_retailers()
            self.print_retailers()
        finally:
            self.driver.quit()


if __name__ == "__main__":
    scraper = RetailerScraper(timeout=10, headless=False)
    scraper.run()