# Golf Equipment Web Scraper

Tracks men's golf club prices across [tgw.com](https://www.tgw.com) and [carlsgolfland.com](https://www.carlsgolfland.com), parameterized by brand and club type, and accumulates the results as queryable price history in SQLite.

Plain `requests` + BeautifulSoup — neither site needs browser automation, so there's no Selenium/Chrome dependency.

## What's in here

### `club_price_tracker/`
The tracker, driven by a shared config so new brands/club types don't require code changes:

- **`config.py`** — `BRANDS` (Callaway, TaylorMade, Titleist, Ping, Cobra, Mizuno) and `CLUB_TYPES` (drivers, 7-woods, iron sets). `build_query()` combines a brand + club type into a search string. Also holds `MENS_ONLY_EXCLUDE_TERMS` (filters out women's/junior/left-handed listings), `VARIANT_TARGETS` (which loft/set-makeup option to resolve an exact price for), `RATE_LIMIT_SECONDS`, and `MAX_VARIANT_LOOKUPS` (caps how many listings get an extra product-page request per run).
- **`scraper_base.py`** — shared plumbing every site scraper needs: a rate-limited GET with a browser User-Agent, `extract_json_blob()` for pulling an embedded JS object literal out of a `<script>` tag (neither site exposes an API), money/discount arithmetic, HTML-to-text flattening, and the brand + men's-only listing filter. A new site's scraper is then just its own parsing logic.
- **`carlsgolfland_scraper.py`** — `CarlsGolflandScraper` scrapes name, price, sale status, discount %, and stock status. The site isn't behind Cloudflare; it follows the site's search redirect to its Searchspring-powered results page and paginates with `?p=N`. Products flagged "ON SALE" or needing a specific loft/set variant get one extra product-page request (capped by `MAX_VARIANT_LOOKUPS`) to read exact pricing/discount/stock off the page's embedded `jsonConfig` data.
- **`tgw_scraper.py`** — `TgwScraper` scrapes the same fields plus a `description`. tgw.com is Cloudflare-fronted but not JS-challenge-protected. It searches via `/l/search?k=`, where the listing cards already carry both current and "was" price for free sale/discount detection. Every listing (capped by `MAX_VARIANT_LOOKUPS`) gets one product-page request to read the page's embedded `productJson` blob, which resolves the exact loft/set variant (`ClubLoft` degrees for fairway woods, `SetComposition` for iron sets), stock status, review data, and the product description.
- **`database.py`** — SQLite persistence for price history. A single `SCHEMA` list is the source of truth: it generates the `CREATE TABLE` statement, the `INSERT`, and the Python row validator, so a column can't be added to one and forgotten in the others. Validation rejects unknown columns (catching a scraper quietly renaming a field), missing required values, uncoercible types, and out-of-range values. Appends are idempotent — a unique index over `(site, brand, club_type, name, variant, run_timestamp)` plus `INSERT OR IGNORE` means a rerun can't pile up duplicates. Also exposes `latest_prices()`, which resolves each listing's most recent price in SQL rather than scanning all history in Python.
- **`price_alerts.py`** — compares a run against each listing's last recorded price (via `latest_prices()`) and logs any drops. Logger-only for now.
- **`rate_limiter.py`** — minimum interval between requests to a site, so a run doesn't pull pages faster than a real shopper would.
- **`logging_config.py`** — `get_logger()` sets up console logging always, plus a timestamped file under `logs/` (gitignored) when called with `write_to_file=True`.
- **`test_scrapers.py`** — the entry point. Runs every brand × club type combination against both sites and appends the results to `data/club_prices.db`. Every row carries the run's `run_timestamp` and an `extracted_date`, so the table accumulates queryable price history instead of being overwritten. Invalid rows are logged and skipped rather than aborting the run. Set its `WRITE_LOGS_TO_FILE` flag to `True` to also write the run's log lines to `logs/`.

### `data/`
`club_prices.db` — the append-only price history. Gitignored, since it grows with every run.

## The data

Each row carries: `site`, `brand`, `club_type`, `name`, `variant`, `sku`, `price`, `original_price`, `discount_pct`, `on_sale`, `stock_status`, `rating`, `review_count`, `image_url`, `description`, and `link`, plus `run_timestamp` and `extracted_date`.

`sku` comes free off both sites' listing pages (tgw.com's `pid` attribute, carlsgolfland's `data-bv-product-id`, which doubles as the MPN) and is the best available handle for matching the same club across sites. `rating`/`review_count` are tgw.com-only — carlsgolfland renders its star ratings client-side via Bazaarvoice, so they never appear in the HTML a plain request gets back.

## Status

Early-stage but functional end to end: scraping → validation → storage runs for men's driver/fairway-wood/iron-set prices across six brands on both sites, including SKU, sale/discount/stock status, descriptions, images, and (tgw.com only) ratings. Price history is queryable and price-drop detection works off real history.

`MAX_VARIANT_LOOKUPS` is currently the main coverage limiter — `description` and `stock_status` only land on the first few results per brand/club-type combo. See `TODO.md` for open items.

## Setup

Dependencies are managed with [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Usage

```bash
cd club_price_tracker && uv run python test_scrapers.py
```

Either scraper can also be run standalone to eyeball its output for every brand/club type, without touching the database:

```bash
cd club_price_tracker && uv run python tgw_scraper.py
```

Querying the history:

```bash
sqlite3 data/club_prices.db "SELECT extracted_date, site, name, price, discount_pct FROM club_prices WHERE on_sale = 1 ORDER BY discount_pct DESC LIMIT 10"
```
