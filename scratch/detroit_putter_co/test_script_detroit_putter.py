# TODO: Create Data Pipeline/cleaning pipeline
# TODO: Look more into what selenium can do


import sys
import os
from pathlib import Path

import pandas as pd

# Resolved from this file rather than the working directory: the relative
# "../data" this used to rely on broke when the script moved down into
# scratch/detroit_putter_co/, and it only ever worked when run from one
# specific directory anyway.
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
sys.path.append(str(ROOT))

from detroit_putter_co_class import DetroitPutterScraper, DetroitAccessoryScraper

filepath_to_check = DATA_DIR / "detroit_putters.csv"
filepath_to_check2 = DATA_DIR / "detroit_accessories.csv"

if os.path.exists(filepath_to_check) and os.path.exists(filepath_to_check2):
    print("Data already exists, loading from file...")
    df = pd.read_csv(filepath_to_check)
    print(df)
    print(df.columns)
    print(df.shape)

    df2 = pd.read_csv(filepath_to_check2)
    print(df2)
    print(df2.columns)
    print(df2.shape)

else:
    if not os.path.exists(filepath_to_check):
        print("Putter data not found, scraping...")
        putter_scraper = DetroitPutterScraper()
        df = putter_scraper.run()
        putter_scraper.save(filename="detroit_putters", filepath=str(DATA_DIR))
    else:
        print("Putter data already exists, loading from file...")
        df = pd.read_csv(filepath_to_check)

    if not os.path.exists(filepath_to_check2):
        print("Accessory data not found, scraping...")
        acc_scraper = DetroitAccessoryScraper()
        df2 = acc_scraper.run()
        acc_scraper.save(filename="detroit_accessories", filepath=str(DATA_DIR))
    else:
        print("Accessory data already exists, loading from file...")
        df2 = pd.read_csv(filepath_to_check2)

