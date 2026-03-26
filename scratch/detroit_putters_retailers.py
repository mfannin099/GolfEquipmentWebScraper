
## TODO - clean address, location from the dataframe in the dataCleaning class, lower case strings amd remove punctation if it exists


from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import sqlite3
import os
import re

pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)
pd.set_option("display.max_colwidth", None)

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

    def create_df(self):
        self.df = pd.DataFrame(self.retailers, columns=['name', 'address'])
        return self.df

    def save_to_db(self, db_name="retailers.db"):
        conn = sqlite3.connect(db_name)
        self.df.to_sql("retailers", conn, if_exists="replace",index=False)
        conn.close()
        print(f"Saved {len(self.df)} retailers to {db_name}")

    def run(self):
        try:
            self.load_page()
            self.parse_retailers()
            self.print_retailers()
            df = self.create_df()
            self.save_to_db("../data/retailers.db")
        finally:
            self.driver.quit()


class dataCleaning:

    def __init__(self,df):
        self.df = df.copy()

    def parse_address(self):
        # Regex pattern to extract street, city, state, zip
        pattern = r"^(.+),\s*(.+),\s*([A-Z]{2})\s*(\d{5})$"
        
        extracted = self.df["address"].str.extract(pattern)
        extracted.columns = ["street", "city", "state", "zip"]
        
        self.df = pd.concat([self.df, extracted], axis=1)
        return self.df

    def run_clean(self):
        self.parse_address()

        return self.df

if __name__ == "__main__":
    db_path = "../data/retailers.db"

    if os.path.exists(db_path):
        print("DB already exists, loading from file...")

        # Loading from Sqllite
        conn = sqlite3.connect(db_path)
        df = pd.read_sql("SELECT * FROM retailers", conn)
        conn.close()

        # Begin cleaning
        cleaner = dataCleaning(df)
        clean_df = cleaner.parse_address()
        print(clean_df)

    else:
        print("DB not found, scraping...")
        scraper = RetailerScraper(timeout=3, headless=False)
        scraper.run()
        print(scraper.df)