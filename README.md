# Golf Equipment Web Scraper

Scrapers for tracking golf equipment data across a few sites:

- Product/retailer data for [Detroit Putter Co.](https://detroitputterco.com) (Selenium).
- Club price tracking across [rockbottomgolf.com](https://www.rockbottomgolf.com) and [carlsgolfland.com](https://www.carlsgolfland.com), parameterized by brand and club type.

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
A parameterized club price tracker covering rockbottomgolf.com and carlsgolfland.com, driven by a shared config so new brands/club types don't require code changes:

- **`config.py`** — `BRANDS` (Callaway, TaylorMade, Titleist, Ping, Cobra, Mizuno) and `CLUB_TYPES` (drivers, 7-woods, iron sets). `build_query()` combines a brand + club type into a search string. Also holds `MENS_ONLY_EXCLUDE_TERMS` (filters out women's/junior/left-handed listings), `VARIANT_TARGETS` (which loft/set-makeup option to resolve an exact price for), `RATE_LIMIT_SECONDS`, and `MAX_VARIANT_LOOKUPS` (caps how many listings get an extra product-page request per run).
- **`carlsgolfland_scraper.py`** — `CarlsGolflandScraper` scrapes name, price, sale status, discount %, and stock status via plain `requests` + BeautifulSoup. The site isn't behind Cloudflare, so no browser automation is needed; it follows the site's search redirect to its Searchspring-powered results page and paginates with `?p=N`. Products flagged "ON SALE" or needing a specific loft/set variant get one extra product-page request (capped by `MAX_VARIANT_LOOKUPS`) to read exact pricing/discount/stock off the page's embedded `jsonConfig` data.
- **`rockbottomgolf_scraper.py`** — `RockBottomGolfScraper` scrapes the same fields via Selenium. rockbottomgolf.com sits behind a Cloudflare JS challenge, so it needs a real browser to render, and headless Chrome gets flagged by Cloudflare's bot detection — it defaults to a visible browser window, with retry/auto-restart around per-product lookups since that combination can be flaky. Some prices are hidden behind "Add To Cart To See Price" (MAP policy), but the real price is still present in the page's HTML, just visually hidden, so it's read directly from the DOM; sale/discount info comes from the listing card's "Save $X (Y% Off)" block, at no extra request cost.
- **`test_scrapers.py`** — runs every brand × club type combination against both sites and saves results to `club_prices.csv`.
- **`TODO.md`** — known gaps, next steps, and alternate-site research for this tracker (see below).

### `data/`
Scraper output: `detroit_putters.csv`, `detroit_accessories.csv`, and `retailers.db`.

## Status

This is early-stage/exploratory work — data collection is functional for Detroit Putter Co. (putters, accessories, retailers) and for men's driver/fairway-wood/iron-set prices (Callaway, TaylorMade, Titleist, Ping, Cobra, Mizuno) on rockbottomgolf.com/carlsgolfland.com, including sale/discount/stock status. There's no unified pipeline yet tying scraping → cleaning → storage together (results are still per-run CSVs, not queryable history), the Rhoback script is just a scratch experiment, and rockbottomgolf.com's Cloudflare protection makes it the fragile half of the club price tracker (see `scratch/club_price_tracker/TODO.md`).

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
