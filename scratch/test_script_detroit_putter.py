# TODO: Create Data Pipeline/cleaning pipeline
# TODO: Look more into what selenium can do


import sys
import os
import pandas as pd
sys.path.append('..')

from detroit_putter_co_class import DetroitPutterScraper, DetroitAccessoryScraper

filepath_to_check = r"../data/detroit_putters.csv"
filepath_to_check2 = r"../data/detroit_accessories.csv"

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
        putter_scraper.save(filename="detroit_putters", filepath=r"../data/")
    else:
        print("Putter data already exists, loading from file...")
        df = pd.read_csv(filepath_to_check)

    if not os.path.exists(filepath_to_check2):
        print("Accessory data not found, scraping...")
        acc_scraper = DetroitAccessoryScraper()
        df2 = acc_scraper.run()
        acc_scraper.save(filename="detroit_accessories", filepath=r"../data/")
    else:
        print("Accessory data already exists, loading from file...")
        df2 = pd.read_csv(filepath_to_check2)

