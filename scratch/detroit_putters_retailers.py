from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import sqlite3
import os
import string
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
    _punct_table = str.maketrans("", "", string.punctuation)

    def __init__(self, df):
        self.df = df.copy()

    def _normalize_text(self, series):
        return (
            series.astype("string")
            .str.lower()
            .str.translate(self._punct_table)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )

    def clean_address_location(self):
        address = (
            self.df["address"]
            .astype("string")
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )

        extracted = address.str.extract(
            r"^(.*?),\s*(.*?),\s*([A-Z]{2})\s*(\d{5})(?:-\d{4})?$"
        )
        extracted.columns = ["street", "city", "state", "zip"]

        self.df["address"] = self._normalize_text(extracted["street"].fillna(address))
        self.df["location"] = (
            self._normalize_text(extracted["city"].fillna(""))
            .str.cat(self._normalize_text(extracted["state"].fillna("")), sep=" ")
            .str.cat(extracted["zip"].fillna("").astype("string"), sep=" ")
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )
        self.df = pd.concat([self.df, extracted], axis=1)
        return self.df

    def run_clean(self):
        self.clean_address_location()

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
        clean_df = cleaner.run_clean()
        print(clean_df)

    else:
        print("DB not found, scraping...")
        scraper = RetailerScraper(timeout=3, headless=False)
        scraper.run()
        print(scraper.df)
