# # TODO: Create similar feature but for accessories
# # TODO: Create a class that will handle pulling for putters and accessories
import sys
import os
sys.path.append('..')

from detroit_putter_co_class import DetroitPutterScraper

putter_scraper = DetroitPutterScraper()
df=putter_scraper.run()
print(df)
print(df.shape)

putter_scraper.save(filename="detroit_putters", filepath=r"../data/")

