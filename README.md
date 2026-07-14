# Golf Equipment Web Scraper

Selenium-based scrapers for [Detroit Putter Co.](https://detroitputterco.com), collecting product and retailer data into CSV files and a SQLite database for downstream analysis.

## What's in here

### `detroit_putter_co_class.py`
Two scraper classes built on Selenium + pandas:

- **`DetroitPutterScraper`** — visits the "Our Putters" collection page, then loads each putter's product page to pull name, price, product URL, and spec details (weight, loft, lie, head, shaft, grip, headcover) parsed out of the description section. Results are collected into a pandas `DataFrame` and saved to CSV.
- **`DetroitAccessoryScraper`** — same pattern applied to the "Accessories & Gear" page: name, price, link, and a concatenated text description scraped from each product page.

Both classes follow a `run()` → `build_dataframe()` → `save()` workflow, with per-item error handling so one failed product page doesn't kill the whole run.

### `scratch/`
Working scripts and early drafts, not part of the "stable" package:

- **`detroit_putters_retailers.py`** — `RetailerScraper` pulls the physical retailer list from the site's "Retailer Locations" page and saves it to a `retailers.db` SQLite table. A companion `dataCleaning` class normalizes and splits the raw address strings into `street`/`city`/`state`/`zip` columns via regex. The `__main__` block loads from the DB if it already exists, otherwise scrapes fresh.
- **`test_script_detroit_putter.py`** — driver script that checks whether `data/detroit_putters.csv` and `data/detroit_accessories.csv` already exist; if not, runs the two scraper classes from `detroit_putter_co_class.py` and saves the output. Has TODOs for building a proper data cleaning pipeline and exploring more Selenium capabilities.
- **`test_script_rhoback.py`** — a rougher, one-off exploratory scrape of Rhoback.com's new-arrivals collection (not integrated with the class-based scrapers).

### `data/`
Scraper output: `detroit_putters.csv`, `detroit_accessories.csv`, and `retailers.db`.

## Status

This is early-stage/exploratory work — data collection is functional for Detroit Putter Co. (putters, accessories, retailers), but there's no unified pipeline yet tying scraping → cleaning → storage together, and the Rhoback script is just a scratch experiment.

## Setup

Dependencies are managed with [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

Selenium requires a compatible Chrome/Chromedriver installation on your machine (the scrapers use `webdriver.Chrome()` directly, relying on Selenium Manager to resolve the driver).

## Usage

```bash
# Run the combined putter + accessory scrape (skips if data/ CSVs already exist)
uv run python scratch/test_script_detroit_putter.py

# Scrape and clean retailer locations into data/retailers.db
uv run python scratch/detroit_putters_retailers.py
```
