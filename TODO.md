# Club Price Tracker - TODO


- [ ] **Build a golfdirectnow.com scraper** - viable, Shopify-based. Also Cloudflare-fronted but no challenge triggered by plain `requests`. Standard Shopify `/search?q={query}` and `/collections/golf-clubs` both return server-rendered `.card__` product cards with real names (confirmed `Callaway Elyte X Driver` for query `Callaway driver`) and prices under `.price__regular .price-item--regular` (format `$ 399.99`, note the space after `$`). Straightforward Shopify scraping pattern, well-documented elsewhere. Survived 5 rapid repeat requests with no blocking.
- [ ] Link the 18 birdies project on github... allow user to pull 18 birdies data and analyze
- [ ] create front end application for user to pull data based on search query

## Backlog

### Data persistence & tracking
- [x] Persist results over time in SQLite instead of overwriting a single CSV, so price history is queryable. `club_price_tracker/database.py` — one `SCHEMA` spec generates the DDL, the INSERT, and the row validator; `test_scrapers.py` appends to `data/club_prices.db` with a `run_timestamp` and `extracted_date` per row.
- [x] Define a dedup key once persisted - `(site, brand, club_type, name, variant, run_timestamp)`, enforced as a UNIQUE index + `INSERT OR IGNORE` so reruns are idempotent rather than piling up duplicates.
- [x] Price-drop/deal alerting: `price_alerts.log_price_drops()` compares each pull against that listing's last recorded price (resolved in SQL by `database.latest_prices()`) and logs drops. Still logger-only — email/Slack would be the next step.
- [ ] Cross-site product matching: normalize names (strip suffixes like "- ON SALE", "2026", "Left Handed") so the same real-world club can be compared side-by-side across sites instead of showing up as unrelated rows. The `sku` column is now populated on both sites and carlsgolfland's doubles as the MPN, so start by checking how far SKU/MPN matching gets before falling back to name normalization.
- [ ] Now that history has more than one run per product, track a rolling low/high per listing (not just the previous price) so "cheapest it's ever been" is answerable.

### Data coverage
- [ ] `MAX_VARIANT_LOOKUPS = 5` caps product-page visits per brand/club-type combo, so `description`, `stock_status` and true discount info only land on the first few results of each. Consider raising it (or making it a CLI flag) for real collection runs as opposed to test runs.
- [ ] Ratings are tgw.com-only — carlsgolfland renders them client-side via Bazaarvoice. Its `data-bv-product-id` is the Bazaarvoice product ID, so their public API may be able to supply rating/review count without a browser.

### Code quality & tooling
- [ ] Add pagination support to rockbottomgolf's scraper (only grabs page 1 today; carlsgolfland's `max_pages` pattern already handles this).
- [ ] Local parser tests using saved HTML fixtures, so selector/parsing logic can be iterated on without hitting live sites (and without risking rockbottomgolf's Cloudflare throttle) on every change.
- [ ] Structured logging instead of `print()`, so a run's output can be reviewed from a file later.
- [ ] Simple CLI (`argparse`) to run a single brand/club_type/site combo on demand instead of always running the full matrix.
- [ ] Look for a lighter-weight path into rockbottomgolf.com (sitemap.xml, RSS/product feed, or a page type that sits outside the Cloudflare challenge).
