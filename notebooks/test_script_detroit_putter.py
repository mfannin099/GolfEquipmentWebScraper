from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re

def parse_specs(description_div):
    spec_divs = description_div.find_elements(By.CSS_SELECTOR, "div.yj6qo")
    specs = {
        'weight': 'N/A',
        'loft': 'N/A',
        'lie': 'N/A',
        'head': 'N/A',
        'shaft': 'N/A',
        'grip': 'N/A',
        'headcover': 'N/A'
    }
    
    for div in spec_divs:
        text = div.get_attribute('textContent').strip()
        text = text.replace('\xa0', ' ')  # Remove non-breaking spaces
        
        if not text:
            continue
            
        # Split on dashes (3 or more)
        parts = re.split(r'-{3,}', text)
        
        if len(parts) >= 2:
            label = parts[0].strip().upper()
            value = parts[1].strip()
            
            if 'WEIGHT' in label:
                specs['weight'] = value
            elif 'LOFT' in label:
                specs['loft'] = value
            elif 'LIE' in label:
                specs['lie'] = value
            elif 'HEAD' in label:
                specs['head'] = value
            elif 'SHAFT' in label:
                specs['shaft'] = value
            elif 'GRIP' in label:
                specs['grip'] = value
            elif 'HEADCOVER' in label:
                specs['headcover'] = value

    # Also check <p> tags for weight
    paragraphs = description_div.find_elements(By.CSS_SELECTOR, "p")
    for p in paragraphs:
        text = p.get_attribute('textContent').strip().replace('\xa0', ' ')
        parts = re.split(r'-{3,}', text)
        if len(parts) >= 2:
            label = parts[0].strip().upper()
            value = parts[1].strip()
            if 'WEIGHT' in label and specs['weight'] == 'N/A':
                specs['weight'] = value

    return specs

# Set up the driver
driver = webdriver.Chrome()

driver.get("https://detroitputterco.com/")

driver.get("https://detroitputterco.com/collections/our-putters")
time.sleep(1) 

# ORIGINAL (JUST PULLING NAME/PRICE FROM LINE 12 LINK)
# ## Extract Putter Information (Name/Price)
putter_list = driver.find_element(By.CSS_SELECTOR, "ul#Slider-template--16677983912180__86207359-2a79-492b-b434-6794b1dff016")
putters = putter_list.find_elements(By.CSS_SELECTOR, "li.grid__item")
print(f"Found {len(putters)} products\n")

# for putter in putters:
#     try:
#         card_info = putter.find_element(By.CSS_SELECTOR, "div.card__information")

#         name_element = card_info.find_element(By.CSS_SELECTOR, "h3 a.full-unstyled-link")
#         name = name_element.get_attribute('textContent').strip()
        

#         price_element = putter.find_element(By.CSS_SELECTOR, "span.price-item--regular")
#         price = price_element.get_attribute('textContent').strip()

#         print(name)
#         print(price)

#     except Exception as e:
#         print(f"Error extracting putter: {e}")
#         continue


putter_name = []
putter_price = []
putter_link = []
putter_weight = []
putter_loft = []
putter_lie = []
putter_head = []
putter_shaft = []
putter_grip = []
putter_headcover = []

for index in range(len(putters)):
    try:
        print(f"Processing putter {index + 1}/{len(putters)}...")
        
        # Get basic info from listing page
        putter_list = driver.find_element(By.CSS_SELECTOR, "ul#Slider-template--16677983912180__86207359-2a79-492b-b434-6794b1dff016")
        putters = putter_list.find_elements(By.CSS_SELECTOR, "li.grid__item")
        putter = putters[index]
        
        card_info = putter.find_element(By.CSS_SELECTOR, "div.card__information")

        # Name information
        name_element = card_info.find_element(By.CSS_SELECTOR, "h3 a.full-unstyled-link")
        name = name_element.get_attribute('textContent').strip()
        putter_name.append(name)

        
        price_element = putter.find_element(By.CSS_SELECTOR, "span.price-item--regular")
        price = price_element.get_attribute('textContent').strip()
        putter_price.append(price)
        
        # Get the product link
        product_link = name_element.get_attribute('href')
        putter_link.append(product_link)

        print(f"Name: {name}")
        print(f"Price: {price}")
        print(f"Link: {product_link}")
        print(f"Clicking into product page...")
        
        # Click into the product page
        driver.get(product_link)
        time.sleep(2)  # Wait for page to load
        
        # NOW WE'RE ON THE PRODUCT PAGE - scrape detailed info
        print(f"Current URL: {driver.current_url}")

        ## TODO: Look at inspect element to see what can be pulled

        description_div = driver.find_element(By.CSS_SELECTOR, "div.product__description.rte.quick-add-hidden")
        spec_divs = description_div.find_elements(By.CSS_SELECTOR, "div.yj6qo")
        for div in spec_divs:
            text = div.get_attribute('textContent').strip()
            if text:
                print(repr(text))  # repr() shows hidden characters

        # Weight is in a <p> tag
        # paragraphs = description_div.find_elements(By.CSS_SELECTOR, "p")
        # weight = "N/A"
        # for p in paragraphs:
        #     text = p.get_attribute('textContent').strip()
        #     if 'WEIGHT' in text:
        #         weight = text.split('---')[-1].strip().lstrip('-').strip()

        # # Rest of specs are in yj6qo divs
        # spec_divs = description_div.find_elements(By.CSS_SELECTOR, "div.yj6qo")
        # specs = {}
        # for div in spec_divs:
        #     text = div.get_attribute('textContent').strip()
        #     if '---' in text and text:
        #         parts = text.split('---')
        #         if len(parts) == 2:
        #             label = parts[0].strip()
        #             value = parts[1].strip().lstrip('-').strip()
        #             specs[label] = value

        # # Access each value
        # weight = weight
        # head = specs.get('HEAD', 'N/A')
        # shaft = specs.get('SHAFT', 'N/A')
        # grip = specs.get('GRIP', 'N/A')
        # headcover = specs.get('HEADCOVER', 'N/A')

        # print(f"Weight: {weight}")
        # print(f"Head: {head}")
        # print(f"Shaft: {shaft}")
        # print(f"Grip: {grip}")
        # print(f"Headcover: {headcover}")




        ## Returnig to the listing page
        print("Going back to listing page...")
        driver.get("https://detroitputterco.com/collections/our-putters")
        time.sleep(2)


    except Exception as e:
        driver.get("https://detroitputterco.com/collections/our-putters")
        time.sleep(2)
        print(f"Error extracting putter: {e}")
        continue





driver.close()




# TODO: Create similar feature but for accessories
# TODO: Create a class that will handle pulling for putters and accessories