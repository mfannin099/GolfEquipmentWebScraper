## TODO - scrape retailers page 
## TODO - clean
## TODO - parse their websites/create some sort of search


from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

driver = webdriver.Chrome()

# Website URL: 
driver.get("https://detroitputterco.com/pages/retailer-locations-1")

WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.CLASS_NAME, "rich-text__text"))
)

div = driver.find_element(By.CLASS_NAME, "rich-text__text")
paragraphs = div.find_elements(By.TAG_NAME, "p")


retailers = []

for p in paragraphs:
    name = p.find_element(By.TAG_NAME, "strong").text.strip()
    address = driver.execute_script(
        "return arguments[0].lastChild.textContent;", p
    ).strip()

    retailers.append({"name": name, "address": address})

for r in retailers:
    print(f"{r['name']}")
    print(f"  {r['address']}")
    print()

    driver.quit()