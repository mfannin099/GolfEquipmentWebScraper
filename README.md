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

- **`config.py`** — `BRANDS` and `CLUB_TYPES` (currently drivers, 7-woods, and iron sets for Callaway). `build_query()` combines a brand + club type into a search string.
- **`carlsgolfland_scraper.py`** — `CarlsGolflandScraper` scrapes name + price via plain `requests` + BeautifulSoup. The site isn't behind Cloudflare, so no browser automation is needed; it follows the site's search redirect to its Searchspring-powered results page and paginates with `?p=N`.
- **`rockbottomgolf_scraper.py`** — `RockBottomGolfScraper` scrapes the same fields via Selenium. rockbottomgolf.com sits behind a Cloudflare JS challenge, so it needs a real browser to render, and headless Chrome gets flagged by Cloudflare's bot detection — it defaults to a visible browser window. Some prices are hidden behind "Add To Cart To See Price" (MAP policy), but the real price is still present in the page's HTML, just visually hidden, so it's read directly from the DOM.
- **`test_scrapers.py`** — runs every brand × club type combination against both sites and saves results to `club_prices.csv`.
- **`TODO.md`** — known gaps and next steps for this tracker (see below).

### `data/`
Scraper output: `detroit_putters.csv`, `detroit_accessories.csv`, and `retailers.db`.

## Status

This is early-stage/exploratory work — data collection is functional for Detroit Putter Co. (putters, accessories, retailers) and for Callaway club prices on rockbottomgolf.com/carlsgolfland.com, but there's no unified pipeline yet tying scraping → cleaning → storage together, the Rhoback script is just a scratch experiment, and the club price tracker still needs loft/set-variant-specific pricing (see `scratch/club_price_tracker/TODO.md`).

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
