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

### `data/`
Scraper output: `detroit_putters.csv`, `detroit_accessories.csv`, `retailers.db`, and `club_prices.db` (the club price tracker's append-only history; gitignored, since it grows with every run).

### `club_price_tracker/`
A parameterized club price tracker covering tgw.com and carlsgolfland.com, driven by a shared config so new brands/club types don't require code changes:

- **`config.py`** — `BRANDS` (Callaway, TaylorMade, Titleist, Ping, Cobra, Mizuno) and `CLUB_TYPES` (drivers, 7-woods, iron sets). `build_query()` combines a brand + club type into a search string. Also holds `MENS_ONLY_EXCLUDE_TERMS` (filters out women's/junior/left-handed listings), `VARIANT_TARGETS` (which loft/set-makeup option to resolve an exact price for), `RATE_LIMIT_SECONDS`, and `MAX_VARIANT_LOOKUPS` (caps how many listings get an extra product-page request per run).
- **`carlsgolfland_scraper.py`** — `CarlsGolflandScraper` scrapes name, price, sale status, discount %, and stock status via plain `requests` + BeautifulSoup. The site isn't behind Cloudflare, so no browser automation is needed; it follows the site's search redirect to its Searchspring-powered results page and paginates with `?p=N`. Products flagged "ON SALE" or needing a specific loft/set variant get one extra product-page request (capped by `MAX_VARIANT_LOOKUPS`) to read exact pricing/discount/stock off the page's embedded `jsonConfig` data.
- **`tgw_scraper.py`** — `TgwScraper` scrapes the same fields via plain `requests` + BeautifulSoup, plus a `description` field. tgw.com is Cloudflare-fronted but not JS-challenge-protected, so no browser automation is needed. It searches via `/l/search?k=`, where the listing cards already carry both current and "was" price for free sale/discount detection. Every listing (capped by `MAX_VARIANT_LOOKUPS`) gets one product-page request to read the page's embedded `productJson` blob, which resolves the exact loft/set variant (`ClubLoft` degrees for fairway woods, `SetComposition` for iron sets), stock status, and the product description.
- **`scraper_base.py`** — shared plumbing every site scraper needs: a rate-limited GET with a browser User-Agent, `extract_json_blob()` for pulling an embedded JS object literal out of a `<script>` tag (neither site exposes an API), money/discount arithmetic, HTML-to-text flattening, and the brand + men's-only listing filter. A new site's scraper is then just its own parsing logic.
- **`database.py`** — SQLite persistence for price history. A single `SCHEMA` list is the source of truth: it generates the `CREATE TABLE` statement, the `INSERT`, and the Python row validator, so a column can't be added to one and forgotten in the others. Validation rejects unknown columns (catching a scraper quietly renaming a field), missing required values, uncoercible types, and out-of-range values, normalizing scraper types and CSV strings alike. Appends are idempotent — a unique index over `(site, brand, club_type, name, variant, run_timestamp)` plus `INSERT OR IGNORE` means a rerun can't pile up duplicates. Also exposes `latest_prices()`, which resolves each listing's most recent price in SQL rather than scanning all history in Python.
- **`price_alerts.py`** — compares a run against each listing's last recorded price (via `latest_prices()`) and logs any drops. Logger-only for now.
- **`logging_config.py`** — `get_logger()` sets up console logging always, plus a timestamped file under `logs/` (gitignored) when called with `write_to_file=True`.
- **`test_scrapers.py`** — runs every brand × club type combination against both sites and appends the results to `data/club_prices.db`. Every row carries the run's `run_timestamp` and an `extracted_date`, so the table accumulates queryable price history instead of being overwritten. Invalid rows are logged and skipped rather than aborting the run. Set its `WRITE_LOGS_TO_FILE` flag to `True` to also write the run's log lines to `logs/`.

Each result row carries: `site`, `brand`, `club_type`, `name`, `variant`, `sku`, `price`, `original_price`, `discount_pct`, `on_sale`, `stock_status`, `rating`, `review_count`, `image_url`, `description`, and `link`. `sku` comes free off both sites' listing pages (tgw.com's `pid` attribute, carlsgolfland's `data-bv-product-id`, which doubles as the MPN) and is the best available handle for matching the same club across sites. `rating`/`review_count` are tgw.com-only — carlsgolfland renders its star ratings client-side via Bazaarvoice, so they never appear in the HTML a plain request gets back.

## Status

This is early-stage/exploratory work — data collection is functional for Detroit Putter Co. (putters, accessories, retailers) and for men's driver/fairway-wood/iron-set prices (Callaway, TaylorMade, Titleist, Ping, Cobra, Mizuno) on tgw.com/carlsgolfland.com, including SKU, sale/discount/stock status, product descriptions, images, and (tgw.com only) ratings.

The club price tracker now runs scraping → validation → storage end to end: every run appends validated rows to `data/club_prices.db`, so price history is queryable and price-drop detection works off real history. The Detroit Putter Co. scrapers still write standalone CSVs and aren't wired into that pipeline (see `TODO.md` for open items).

## Setup

Dependencies are managed with [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

Selenium requires a compatible Chrome/Chromedriver installation on your machine (the scrapers use `webdriver.Chrome()` directly, relying on Selenium Manager to resolve the driver).

## Usage

```bash
# Run the combined putter + accessory scrape (skips if data/ CSVs already exist)
uv run python scratch/detroit_putter_co/test_script_detroit_putter.py

# Scrape and clean retailer locations into data/retailers.db
uv run python scratch/detroit_putter_co/detroit_putters_retailers.py

# Run the club price tracker against both sites for every configured
# brand/club type, appending the results to data/club_prices.db
cd club_price_tracker && uv run python test_scrapers.py
```

Querying the history:

```bash
sqlite3 data/club_prices.db "SELECT extracted_date, site, name, price FROM club_prices WHERE on_sale = 1 ORDER BY discount_pct DESC LIMIT 10"
```
