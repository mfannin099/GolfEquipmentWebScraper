from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re
import pandas as pd

class DetroitPutterScraper:
    BASE_URL = "https://detroitputterco.com"
    COLLECTION_URL = "https://detroitputterco.com/collections/our-putters"
    PUTTER_LIST_CSS = "ul#Slider-template--16677983912180__86207359-2a79-492b-b434-6794b1dff016"

    def __init__(self):
        self.driver = webdriver.Chrome()
        self.putter_name = []
        self.putter_price = []
        self.putter_link = []
        self.putter_weight = []
        self.putter_loft = []
        self.putter_lie = []
        self.putter_head = []
        self.putter_shaft = []
        self.putter_grip = []
        self.putter_headcover = []
        self.df = None

    def load_collection(self):
        self.driver.get(self.BASE_URL)
        self.driver.get(self.COLLECTION_URL)
        time.sleep(1)

    def get_putters(self):
        putter_list = self.driver.find_element(By.CSS_SELECTOR, self.PUTTER_LIST_CSS)
        return putter_list.find_elements(By.CSS_SELECTOR, "li.grid__item")

    def parse_specs(self, description_div):
        specs = {
            'weight': 'N/A', 'loft': 'N/A', 'lie': 'N/A',
            'head': 'N/A', 'shaft': 'N/A', 'grip': 'N/A', 'headcover': 'N/A'
        }

        spec_divs = description_div.find_elements(By.CSS_SELECTOR, "div.yj6qo")
        for div in spec_divs:
            text = div.get_attribute('textContent').strip().replace('\xa0', ' ')
            if not text:
                continue
            parts = re.split(r'-{3,}', text)
            if len(parts) >= 2:
                label = parts[0].strip().upper()
                value = parts[1].strip()
                if 'WEIGHT' in label:    specs['weight'] = value
                elif 'LOFT' in label:    specs['loft'] = value
                elif 'LIE' in label:     specs['lie'] = value
                elif 'HEAD' in label:    specs['head'] = value
                elif 'SHAFT' in label:   specs['shaft'] = value
                elif 'GRIP' in label:    specs['grip'] = value
                elif 'HEADCOVER' in label: specs['headcover'] = value

        # Also check <p> tags for weight
        for p in description_div.find_elements(By.CSS_SELECTOR, "p"):
            text = p.get_attribute('textContent').strip().replace('\xa0', ' ')
            parts = re.split(r'-{3,}', text)
            if len(parts) >= 2 and 'WEIGHT' in parts[0].upper() and specs['weight'] == 'N/A':
                specs['weight'] = parts[1].strip()

        return specs
    
    def scrape_putter(self, index):
        putters = self.get_putters()
        putter = putters[index]
        card_info = putter.find_element(By.CSS_SELECTOR, "div.card__information")

        name_element = card_info.find_element(By.CSS_SELECTOR, "h3 a.full-unstyled-link")
        name = name_element.get_attribute('textContent').strip()
        price = putter.find_element(By.CSS_SELECTOR, "span.price-item--regular").get_attribute('textContent').strip()
        product_link = name_element.get_attribute('href')

        print(f"Name: {name} | Price: {price} | Link: {product_link}")

        self.driver.get(product_link)
        time.sleep(2)

        description_div = self.driver.find_element(By.CSS_SELECTOR, "div.product__description.rte.quick-add-hidden")
        specs = self.parse_specs(description_div)
        print(specs)

        self.putter_name.append(name)
        self.putter_price.append(price)
        self.putter_link.append(product_link)
        self.putter_weight.append(specs['weight'])
        self.putter_loft.append(specs['loft'])
        self.putter_lie.append(specs['lie'])
        self.putter_head.append(specs['head'])
        self.putter_shaft.append(specs['shaft'])
        self.putter_grip.append(specs['grip'])
        self.putter_headcover.append(specs['headcover'])

    def build_dataframe(self):
        self.df = pd.DataFrame({
            'Name': self.putter_name,
            'Price': self.putter_price,
            'Link': self.putter_link,
            'Weight': self.putter_weight,
            'Loft': self.putter_loft,
            'Lie': self.putter_lie,
            'Head': self.putter_head,
            'Shaft': self.putter_shaft,
            'Grip': self.putter_grip,
            'Headcover': self.putter_headcover
        })
        return self.df
    
    def run(self):
        self.load_collection()
        putters = self.get_putters()
        print(f"Found {len(putters)} putters\n")

        for index in range(len(putters)):
            try:
                print(f"Processing putter {index + 1}/{len(putters)}...")
                self.scrape_putter(index)
                self.driver.get(self.COLLECTION_URL)
                time.sleep(2)
            except Exception as e:
                print(f"Error on putter {index + 1}: {e}")
                self.driver.get(self.COLLECTION_URL)
                time.sleep(2)
                continue

        self.build_dataframe()
        self.driver.close()
        return self.df

    def save(self, filename="detroit_putter_co", filepath=None):
        if self.df is None:
            print("No dataframe to save. Run build_dataframe() first.")
            return

        if filepath:
            full_path = f"{filepath}/{filename}"
        else:
            full_path = filename
            
        self.df.to_csv(f"{full_path}.csv", index=False)
        print(f"Saved to {full_path}.csv")