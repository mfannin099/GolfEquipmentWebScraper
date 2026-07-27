# Golf Equipment Web Scraper

Scrapers for tracking golf equipment data across a few sites:

- Product/retailer data for [Detroit Putter Co.](https://detroitputterco.com) (Selenium).
- Club price tracking across [tgw.com](https://www.tgw.com) and [carlsgolfland.com](https://www.carlsgolfland.com), parameterized by brand and club type.

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

### `scratch/club_price_tracker/`
A parameterized club price tracker covering tgw.com and carlsgolfland.com, driven by a shared config so new brands/club types don't require code changes:

- **`config.py`** — `BRANDS` (Callaway, TaylorMade, Titleist, Ping, Cobra, Mizuno) and `CLUB_TYPES` (drivers, 7-woods, iron sets). `build_query()` combines a brand + club type into a search string. Also holds `MENS_ONLY_EXCLUDE_TERMS` (filters out women's/junior/left-handed listings), `VARIANT_TARGETS` (which loft/set-makeup option to resolve an exact price for), `RATE_LIMIT_SECONDS`, and `MAX_VARIANT_LOOKUPS` (caps how many listings get an extra product-page request per run).
- **`carlsgolfland_scraper.py`** — `CarlsGolflandScraper` scrapes name, price, sale status, discount %, and stock status via plain `requests` + BeautifulSoup. The site isn't behind Cloudflare, so no browser automation is needed; it follows the site's search redirect to its Searchspring-powered results page and paginates with `?p=N`. Products flagged "ON SALE" or needing a specific loft/set variant get one extra product-page request (capped by `MAX_VARIANT_LOOKUPS`) to read exact pricing/discount/stock off the page's embedded `jsonConfig` data.
- **`tgw_scraper.py`** — `TgwScraper` scrapes the same fields via plain `requests` + BeautifulSoup, plus a `description` field. tgw.com is Cloudflare-fronted but not JS-challenge-protected, so no browser automation is needed. It searches via `/l/search?k=`, where the listing cards already carry both current and "was" price for free sale/discount detection. Every listing (capped by `MAX_VARIANT_LOOKUPS`) gets one product-page request to read the page's embedded `productJson` blob, which resolves the exact loft/set variant (`ClubLoft` degrees for fairway woods, `SetComposition` for iron sets), stock status, and the product description.
- **`test_scrapers.py`** — runs every brand × club type combination against both sites and saves results to `club_prices.csv`.
- **`TODO.md`** — known gaps, next steps, and alternate-site research for this tracker (see below).

### `data/`
Scraper output: `detroit_putters.csv`, `detroit_accessories.csv`, and `retailers.db`.

## Status

This is early-stage/exploratory work — data collection is functional for Detroit Putter Co. (putters, accessories, retailers) and for men's driver/fairway-wood/iron-set prices (Callaway, TaylorMade, Titleist, Ping, Cobra, Mizuno) on tgw.com/carlsgolfland.com, including sale/discount/stock status and (tgw.com only) product descriptions. There's no unified pipeline yet tying scraping → cleaning → storage together (results are still per-run CSVs, not queryable history), and the Rhoback script is just a scratch experiment (see `scratch/club_price_tracker/TODO.md` for open items).

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

# Run the club price tracker against both sites for every configured brand/club type
cd scratch/club_price_tracker && uv run python test_scrapers.py
```
