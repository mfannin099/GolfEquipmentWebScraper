# Club Price Tracker - TODO


- [ ] **Build a golfdirectnow.com scraper** - viable, Shopify-based. Also Cloudflare-fronted but no challenge triggered by plain `requests`. Standard Shopify `/search?q={query}` and `/collections/golf-clubs` both return server-rendered `.card__` product cards with real names (confirmed `Callaway Elyte X Driver` for query `Callaway driver`) and prices under `.price__regular .price-item--regular` (format `$ 399.99`, note the space after `$`). Straightforward Shopify scraping pattern, well-documented elsewhere. Survived 5 rapid repeat requests with no blocking.
- [ ] Link the 18 birdies project on github... allow user to pull 18 birdies data and analyze
- [ ] create front end application for user to pull data based on search query

## Backlog

### Data persistence & tracking
- [ ] Persist results over time in SQLite (like the Detroit Putter Co. retailer scraper) instead of overwriting a single CSV, so price history is queryable. `run_timestamp` (in `test_scrapers.py`) is a step toward this but isn't real history yet.
- [ ] Define a dedup key once persisted - e.g. `(site, brand, club_type, variant, name, run_timestamp)` - so reruns don't just pile up duplicate rows.
- [ ] Price-drop/deal alerting: once history exists, compare each pull against the stored low/previous price and flag drops (start with a printed/logged summary; could grow into email/Slack).
- [ ] Cross-site product matching: normalize names (strip suffixes like "- ON SALE", "2026", "Left Handed") so the same real-world club can be compared side-by-side acros33s sites instead of showing up as unrelated rows.

### Code quality & tooling
- [ ] Add pagination support to rockbottomgolf's scraper (only grabs page 1 today; carlsgolfland's `max_pages` pattern already handles this).
- [ ] Local parser tests using saved HTML fixtures, so selector/parsing logic can be iterated on without hitting live sites (and without risking rockbottomgolf's Cloudflare throttle) on every change.
- [ ] Structured logging instead of `print()`, so a run's output can be reviewed from a file later.
- [ ] Simple CLI (`argparse`) to run a single brand/club_type/site combo on demand instead of always running the full matrix.
- [ ] Look for a lighter-weight path into rockbottomgolf.com (sitemap.xml, RSS/product feed, or a page type that sits outside the Cloudflare challenge).
