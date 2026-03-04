# TODO: Create similar feature but for accessories
# TODO: Create Data Pipeline/cleaning pipeline
# TODO: Look more into what selenium can do


import sys
import os
import pandas as pd
sys.path.append('..')

from detroit_putter_co_class import DetroitPutterScraper

filepath_to_check = r"../data/detroit_putters.csv"

if os.path.exists(filepath_to_check):
    print("Data already exists, loading from file...")
    df = pd.read_excel(filepath_to_check)
    print(df)
    print(df.shape)
else:
    putter_scraper = DetroitPutterScraper()
    df=putter_scraper.run()
    putter_scraper.save(filename="detroit_putters", filepath=r"../data/")

