# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Tracks men's golf club prices across tgw.com and carlsgolfland.com, parameterized by brand and club type, and accumulates results as queryable price history in SQLite. Plain `requests` + BeautifulSoup — neither site needs browser automation.

## Commands

Dependencies are managed with `uv` (creates/manages `.venv/` itself):

```bash
uv sync
```

Run the scraper via the `run_final_scrape` console script (`[project.scripts]` in `pyproject.toml`, resolving to `club_price_tracker.run_final_scrape:main`) — works from anywhere in the repo, no `cd` needed:

```bash
uv run run_final_scrape                                                    # full matrix: every brand x club type x both sites
uv run run_final_scrape --brand Titleist --club-type putter
uv run run_final_scrape --brand Srixon --club-type driver --dry-run        # scrape without writing to the DB
uv run run_final_scrape --site tgw.com --max-variant-lookups all           # uncap product-page requests
uv run run_final_scrape --help
```

`--brand` accepts any free-text search term, not just the six in `config.py`. `--club-type` is restricted to `config.CLUB_TYPES` keys.

`club_price_tracker` is a real package (`__init__.py`, relative imports between its modules) built with hatchling. `uv sync` installs it editable into `.venv`, so `DB_PATH`/`LOG_DIR` — computed from `__file__` — still resolve to the real source tree, not a copied build artifact. Running a module directly as a script (e.g. `python club_price_tracker/tgw_helper.py`) no longer works because of the relative imports; use `uv run python -m club_price_tracker.tgw_helper` instead if you need to exercise one scraper standalone.

There is no test suite and no lint/typecheck config in this repo — don't assume `pytest`, `ruff`, or `mypy` are wired up unless you add them.

Query history directly with sqlite3:

```bash
sqlite3 data/club_prices.db "SELECT extracted_date, site, name, price, discount_pct FROM club_prices WHERE on_sale = 1 ORDER BY discount_pct DESC LIMIT 10"
```

## Architecture

Everything lives in `club_price_tracker/`, all flat modules (no package/`__init__.py`), importing each other directly by module name:

- **`run_final_scrape.py`** — entry point. `scrape()` runs the brand x club_type x site matrix and returns raw, unsaved rows (a UI can call this alone to preview results); `save()` stamps a `run_timestamp`, validates, checks for price drops, and appends to SQLite. The CLI (`main()`) chains both. `SCRAPERS` (a dict keyed by each scraper class's `SITE`) is the single place a new site joins both the matrix and the `--site` CLI choices.
- **`config.py`** — the only file to edit to change *what* gets tracked: `BRANDS`, `CLUB_TYPES` (club type -> search term), plus four filter lists (`BRAND_ALIASES`, `NON_CLUB_TERMS`, `MENS_ONLY_EXCLUDE_TERMS`, `CLUB_TYPE_KEYWORDS`) and `VARIANT_TARGETS` (which loft/set-makeup variant to price per site, since each site models variants differently).
- **`main_scraper.py`** — `BaseScraper`, which every site scraper subclasses. Provides rate-limited `_get()`, `_is_wanted()` (applies the config filter lists before a listing costs a product-page request), `_capped()` (enforces `MAX_VARIANT_LOOKUPS`), and shared parsing helpers (`extract_json_blob` for the embedded-JS-object pattern both sites use, `parse_money`, `discount_pct`, `clean_text`). Subclasses set `SITE` and implement `run()`, returning dicts whose keys match `database.COLUMNS` minus `run_timestamp`/`extracted_date`.
- **`tgw_helper.py`** / **`carlsgolfland_helper.py`** — one `BaseScraper` subclass per site. Both parse a listing page for name/price/SKU/image, then optionally visit product pages (capped by `MAX_VARIANT_LOOKUPS`) for description, exact variant price, and stock status. Each site's page structure and embedded-JSON shape differ significantly — read the module docstring before touching selectors.
- **`database.py`** — SQLite persistence. `SCHEMA` (a tuple of `Column` definitions) is the single source of truth: it generates the `CREATE TABLE` DDL, the `INSERT`, and the row validator, so a column can't be added to one and forgotten in the others. Sets `journal_mode=WAL` so reads and writes don't block each other. Appends are idempotent via a `UNIQUE` index over `(site, brand, club_type, name, variant, run_timestamp)` + `INSERT OR IGNORE` — no separate dedup pass needed.
- **`price_alerts.py`** — compares a run's rows against `database.latest_prices()` (each listing's most recent price) and logs anything cheaper. Logger-only for now; not persisted.
- **`rate_limiter.py`** — minimum interval between requests to one site. Currently instantiated per scraper instance (per brand/club-type combination), so the floor only holds *within* one combination, not across a whole run — see `TODO.md` before scheduling unattended runs.
- **`logging_config.py`** — console logging always on; `write_to_file=True` (or `--log-file`) additionally writes to a timestamped file under `club_price_tracker/logs/` (gitignored).

### Data flow

`scrape()` → list of raw dicts → `save()` stamps `run_timestamp`/`extracted_date` → `database.validate_rows()` coerces/validates against `SCHEMA` (invalid rows are logged and dropped, not fatal) → `price_alerts.log_price_drops()` runs against pre-insert history → `database.insert_rows()` appends.

### Filtering (why results need it)

Both sites' search is loose keyword matching. `BaseScraper._is_wanted()` applies `config.py`'s four filter lists during listing parse, before a candidate can cost a product-page request:
- `CLUB_TYPE_KEYWORDS` — the club type's own word must appear in the name (without it, a brand+putter search returns mostly drivers/woods).
- `NON_CLUB_TERMS` — drops headcovers, bags, gloves, package sets.
- `BRAND_ALIASES` — tgw.com lists Titleist putters as "Scotty Cameron" and Callaway's as "Odyssey" with no parent brand in the name; the `brand` column still records the parent.
- `MENS_ONLY_EXCLUDE_TERMS` — women's/junior/left-handed lines (tracker is scoped to right-handed men's clubs by design).

### Field notes

- `sku` is populated on both sites and is the best cross-site matching handle (carlsgolfland's doubles as the MPN).
- `rating`/`review_count` are tgw.com-only — carlsgolfland renders stars client-side via Bazaarvoice.
- A null `price` usually means MAP pricing ("Add To Cart To See Price"), not a parse failure.
- `description` and `stock_status` only populate for the first `MAX_VARIANT_LOOKUPS` results per combination, since each needs its own product-page request.

## Adding a new site scraper

Subclass `BaseScraper`, set `SITE`, implement `run()` returning dicts matching `database.COLUMNS` (minus `run_timestamp`/`extracted_date`), then add one entry to `run_final_scrape.SCRAPERS`. That's the entire integration point — it joins the matrix and the CLI's `--site` choices automatically.
