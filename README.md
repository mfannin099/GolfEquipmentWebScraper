# Golf Equipment Web Scraper

Tracks men's golf club prices across [tgw.com](https://www.tgw.com) and [carlsgolfland.com](https://www.carlsgolfland.com), parameterized by brand and club type, and accumulates the results as queryable price history in SQLite.

Plain `requests` + BeautifulSoup — neither site needs browser automation, so there's no Selenium or Chrome dependency.

## Files

Everything lives in `club_price_tracker/`:

| File | What it does |
|---|---|
| **`scrape.py`** | **Entry point.** CLI + the `scrape()` / `save()` functions the whole pipeline runs through. |
| `config.py` | Brands, club types, search filters, rate limit, variant targets. The only file you edit to change *what* gets tracked. |
| `scraper_base.py` | `BaseScraper` + shared helpers: rate-limited GET, embedded-JSON extraction, money/discount math, the listing filter. |
| `tgw_scraper.py` | tgw.com listing + product-page parsing. |
| `carlsgolfland_scraper.py` | carlsgolfland.com listing + product-page parsing. |
| `database.py` | SQLite schema, validation, inserts. `SCHEMA` generates the DDL, the INSERT, and the row validator. |
| `price_alerts.py` | Compares a run against each listing's last recorded price and logs drops. |
| `rate_limiter.py` | Minimum interval between requests to a site. |
| `logging_config.py` | Console logging, plus an optional timestamped file under `logs/`. |

`data/club_prices.db` holds the price history. It's gitignored — it grows with every run, and the `-wal`/`-shm` files beside it are SQLite's write-ahead log (see below).

## Usage

Run everything — every configured brand × club type against both sites:

```bash
uv run scrape
```

Narrow it down. `--brand` takes any search term, not just the six in `config.py`:

```bash
uv run scrape --brand Titleist --club-type putter
```

Preview without writing to the database:

```bash
uv run scrape --brand Srixon --club-type driver --dry-run
```

`--max-variant-lookups` controls how many product pages get visited per combination — that's where descriptions, stock status and exact variant prices come from, at one rate-limited request each. `all` lifts the cap for a full collection run:

```bash
uv run scrape --site tgw.com --max-variant-lookups all
```

`uv run scrape --help` lists the rest (`--site`, `--max-pages`, `--db`, `--log-file`). `scrape` is a console script defined in `pyproject.toml`'s `[project.scripts]` — it resolves to `club_price_tracker.scrape:main` and can be run from anywhere in the repo, no `cd` needed.

## The data

Each row carries: `site`, `brand`, `club_type`, `name`, `variant`, `sku`, `price`, `original_price`, `discount_pct`, `on_sale`, `stock_status`, `rating`, `review_count`, `image_url`, `description`, `link`, plus `run_timestamp` and `extracted_date`.

Tracked club types: `driver`, `fairway_wood_3`, `fairway_wood_7`, `hybrid`, `iron_set`, `wedge`, `putter`.

```bash
sqlite3 data/club_prices.db "SELECT extracted_date, site, name, price, discount_pct FROM club_prices WHERE on_sale = 1 ORDER BY discount_pct DESC LIMIT 10"
```

Notes on the fields:

- **`sku`** is populated on both sites (tgw.com's `pid` attribute, carlsgolfland's `data-bv-product-id`, which doubles as the MPN). It's the best handle for matching the same club across sites.
- **`rating`/`review_count`** are tgw.com-only — carlsgolfland renders its stars client-side via Bazaarvoice, so they never appear in the HTML a plain request gets back.
- **A null `price`** usually means the listing says "Add To Cart To See Price" (MAP pricing), not a parse failure.
- **`description` and `stock_status`** only appear on the first `MAX_VARIANT_LOOKUPS` results per combination, since each needs its own product-page request.

### Why appends are safe

Every run appends its full result set rather than overwriting. A `UNIQUE` index over `(site, brand, club_type, name, variant, run_timestamp)` plus `INSERT OR IGNORE` means rerunning the same scrape can't create duplicates, while a *later* run legitimately adds new history.

### Why WAL mode

`database.py` sets `journal_mode=WAL`, which is what creates `club_prices.db-wal` (pending writes) and `club_prices.db-shm` (a shared-memory index into it). Under WAL, readers don't block the writer and vice versa — so a dashboard can query the DB while a scrape is running instead of failing with `database is locked`. SQLite removes both files on a clean close; don't delete a `-wal` by hand while a connection is open.

## Filtering

Both sites' search is loose keyword matching, so raw results need filtering. `config.py` holds four lists that do it, applied in `BaseScraper._is_wanted` before anything costs a product-page request:

- `CLUB_TYPE_KEYWORDS` — the club type's own word must appear in the name. Without it, "Titleist putter" on tgw.com returns 42 drivers and fairway woods out of 44 results.
- `NON_CLUB_TERMS` — drops headcovers, bags, gloves, package sets.
- `BRAND_ALIASES` — tgw.com lists Titleist putters as "Scotty Cameron" and Callaway's as "Odyssey", with no parent brand in the name. The `brand` column still records the parent.
- `MENS_ONLY_EXCLUDE_TERMS` — women's/junior/left-handed lines.

## Setup

Dependencies are managed with [uv](https://docs.astral.sh/uv/), which creates and manages the `.venv/` directory itself:

```bash
uv sync
```
