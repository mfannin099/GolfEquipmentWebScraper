# Club Price Tracker - TODO

- [ ] **Build a golfdirectnow.com scraper** - viable, Shopify-based. Also Cloudflare-fronted but no challenge triggered by plain `requests`. Standard Shopify `/search?q={query}` and `/collections/golf-clubs` both return server-rendered `.card__` product cards with real names (confirmed `Callaway Elyte X Driver` for query `Callaway driver`) and prices under `.price__regular .price-item--regular` (format `$ 399.99`, note the space after `$`). Straightforward Shopify scraping pattern, well-documented elsewhere. Survived 5 rapid repeat requests with no blocking. Adding it is a new `BaseScraper` subclass plus one entry in `scrape.SCRAPERS` - it then joins the matrix and the CLI's `--site` choices automatically.
- [ ] Link the 18 birdies project on github... allow user to pull 18 birdies data and analyze

## Frontend application (end goal)

- [ ] Build a UI (Streamlit / Dash / similar) that lets a user either **query the stored history** in `data/club_prices.db` or **trigger a live scrape** with parameters they choose (brand, club type, site).
  - `scrape.py` is already shaped for this: `scrape()` returns rows without touching the database (live query), `save()` persists them (collection run), and neither needs the CLI. The app imports them rather than shelling out.
  - `--brand` accepts any search term, not just `config.BRANDS`, so a free-text brand box works today.
  - The DB runs in WAL mode, so the app can read while a scrape is writing without hitting `database is locked`.
  - Open question: for a live scrape the request has to finish inside a page load, so `max_variant_lookups` needs to stay low (each lookup is a rate-limited request). Worth deciding whether live queries skip product-page enrichment entirely and only show listing-page fields.

## Backlog

### Data persistence & tracking
- [x] Persist results over time in SQLite instead of overwriting a single CSV, so price history is queryable. `club_price_tracker/database.py` - one `SCHEMA` spec generates the DDL, the INSERT, and the row validator; `scrape.py` appends to `data/club_prices.db` with a `run_timestamp` and `extracted_date` per row.
- [x] Define a dedup key once persisted - `(site, brand, club_type, name, variant, run_timestamp)`, enforced as a UNIQUE index + `INSERT OR IGNORE` so reruns are idempotent rather than piling up duplicates.
- [x] Price-drop/deal alerting: `price_alerts.log_price_drops()` compares each pull against that listing's last recorded price (resolved in SQL by `database.latest_prices()`) and logs drops. Still logger-only - email/Slack would be the next step.
- [ ] Cross-site product matching: normalize names (strip suffixes like "- ON SALE", "2026", "Left Handed") so the same real-world club can be compared side-by-side across sites instead of showing up as unrelated rows. The `sku` column is now populated on both sites and carlsgolfland's doubles as the MPN, so start by checking how far SKU/MPN matching gets before falling back to name normalization.
- [ ] Now that history has more than one run per product, track a rolling low/high per listing (not just the previous price) so "cheapest it's ever been" is answerable.

### Data coverage
- [ ] `MAX_VARIANT_LOOKUPS = 5` still caps product-page visits per combination by default, so `description`, `stock_status` and true discount info only land on the first few results of each. `scrape.py --max-variant-lookups all` lifts the cap for a real collection run; consider whether the *default* should be higher now that it's overridable per run.
- [ ] Ratings are tgw.com-only - carlsgolfland renders them client-side via Bazaarvoice. Its `data-bv-product-id` is the Bazaarvoice product ID, so their public API may be able to supply rating/review count without a browser.
- [ ] `TgwScraper` ignores `max_pages` - `/l/search` returns its whole result set in one response, so there's no page 2 to fetch today. Worth confirming that holds for queries with more matches than a driver search returns.

### Code quality & tooling
- [x] Structured logging instead of `print()` - `logging_config.get_logger()`, with `scrape.py --log-file` to also write a run to `logs/`.
- [x] Simple CLI to run a single brand/club_type/site combo on demand instead of always running the full matrix - `scrape.py`, which replaced `test_scrapers.py`.
- [ ] `scrape.py` collects every combination into memory and only calls `save()` at the end, so a crash on the last combination throws away the whole run - currently ~15 minutes and 84 combinations for the full matrix. Save per combination (or per brand) instead, so a failure keeps whatever already succeeded.
- [ ] `RateLimiter` is per scraper instance, so the 1.5s floor only applies *within* one brand/club-type combination - the first request of each new combination goes out immediately after the last one. Across 84 combinations that's a fair bit faster than intended; a per-site shared limiter would hold the real floor.
- [ ] Local parser tests using saved HTML fixtures, so selector/parsing logic can be iterated on without hitting live sites on every change. This is the biggest remaining gap: every check today costs real requests against both sites, and a selector breaking is only caught by noticing a result count drop.
