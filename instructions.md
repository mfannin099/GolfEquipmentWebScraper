# Pulling Data — Quick Guide

How to get golf club price data out of this codebase, either live from the sites or from
accumulated history in SQLite.

## 1. One-time setup

```bash
uv sync
```

Installs `club_price_tracker` editable into `.venv/` and resolves the `scrape` console script.

## 2. Run a scrape

```bash
uv run scrape                                            # full matrix: all brands x all club types x both sites (~15 min)
uv run scrape --brand Titleist --club-type putter        # one brand, one club type, both sites
uv run scrape --brand Srixon --club-type driver --dry-run # preview only, nothing written to the DB
uv run scrape --site tgw.com --max-variant-lookups all    # uncap product-page requests for complete descriptions/stock
```

Useful flags:
- `--brand` — any free-text search term (not limited to `config.BRANDS`).
- `--club-type` — restricted to `config.CLUB_TYPES` keys: `driver`, `fairway_wood_3`, `fairway_wood_7`, `hybrid`, `iron_set`, `wedge`, `putter`.
- `--site` — `tgw.com`, `carlsgolfland.com`, or both (default).
- `--max-variant-lookups N|all` — how many product pages to visit per combination for exact variant price, description, and stock status. Default is `config.MAX_VARIANT_LOOKUPS`; each lookup is a separate rate-limited request, so `all` on the full matrix is slow.
- `--dry-run` — scrape and log results without touching `data/club_prices.db`.
- `--log-file` — also write this run's logs to a timestamped file under `club_price_tracker/logs/`.

Run `uv run scrape --help` for the full list.

## 3. Query stored history

Every successful (non-dry-run) run appends to `data/club_prices.db`. Reruns of the same
scrape don't create duplicates (unique index on `site, brand, club_type, name, variant, run_timestamp`).

```bash
# Current best deals
sqlite3 data/club_prices.db "SELECT extracted_date, site, name, price, discount_pct FROM club_prices WHERE on_sale = 1 ORDER BY discount_pct DESC LIMIT 10"

# Price history for one listing
sqlite3 data/club_prices.db "SELECT extracted_date, price FROM club_prices WHERE name LIKE '%Scotty Cameron%' ORDER BY extracted_date"

# Row count / freshness check
sqlite3 data/club_prices.db "SELECT MAX(extracted_date), COUNT(*) FROM club_prices"
```

Columns: `site, brand, club_type, name, variant, sku, price, original_price, discount_pct,
on_sale, stock_status, rating, review_count, image_url, description, link, run_timestamp,
extracted_date`. `sku` is the best cross-site matching key. A null `price` usually means MAP
pricing ("Add To Cart To See Price"), not a parse failure.

## 4. Pulling data programmatically (no CLI)

```python
from club_price_tracker.scrape import scrape, save

rows = scrape(["Titleist"], ["putter"], ["tgw.com"], max_variant_lookups=0)  # live, unsaved
summary = save(rows)  # stamps run_timestamp, validates, checks for price drops, appends to DB
```

This is the same split the CLI uses internally, and what any future UI (see `TODO.md`'s MVP
app plan) should call.

## Notes

- No test suite or lint config exists in this repo yet — don't assume `pytest`/`ruff`/`mypy` are wired up.
- Full architecture and module-by-module details live in `CLAUDE.md` and `README.md`; this file only covers the "how do I get data" path.
