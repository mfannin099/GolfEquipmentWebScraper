# Club Price Tracker - TODO

## Priority: reduce reliance on Cloudflare-protected sites
rockbottomgolf.com repeatedly locks out sessions after a burst of automated runs (see "Known issues" below), which has cost real dev time this project. Finding/adding sites that don't have this problem is the current top priority over new features.

- [ ] **Build a 2ndswing.com scraper** - strongest candidate found so far. No Cloudflare, fully server-rendered (plain `requests` works), Magento-based (`.product-item` cards, same pattern as carlsgolfland). It's a **used/pre-owned marketplace** though, not new-club MSRP - each listing is one physical club with its own condition, price, and "WAS" price baked right into the card text (e.g. `Tour Edge | Hot Launch E523 | $91.99 | WAS | $137.99 | Mint | Dexterity: Right | Loft: 15° | Flex: Ladies | Shaft: ...`). Richer per-listing data than either current site, but a different product category (used vs. new) - a complementary addition, not a rockbottomgolf replacement. Would need its own `club_type` handling since it's per-unit inventory, not a family/variant model.
- [ ] **Inspect globalgolf.com and worldwidegolfshops.com** - confirmed no Cloudflare challenge and real HTML returned, but listing/price selectors haven't been inspected yet. Do that before ruling either in or out.
- [ ] **Re-check pgatoursuperstore.com** - a plain `requests` call only got a bare 302 redirect with no body; re-check following the redirect before concluding anything.
- [ ] **Decide rockbottomgolf.com's fate**: keep hardening around the lockouts, or deprioritize/drop it once 1-2 Cloudflare-free sources are in place? Revisit once the sites above have been evaluated.

## Known issues (rockbottomgolf.com)
- [ ] **Can throttle/lock out a session entirely** after a burst of automated Chrome sessions in a short window (e.g. repeated test runs during development) - Cloudflare stops resolving its JS challenge at all, even for a real, visible, non-headless browser. `RATE_LIMIT_SECONDS` and `MAX_VARIANT_LOOKUPS` reduce load per run but don't fully prevent this with repeated back-to-back runs. If `_wait_for_results` hangs, wait out a cooldown period rather than retrying immediately.
- [ ] **New sale/discount/men's-filter code needs a live end-to-end re-run** once the above cooldown clears - it hit that exact lockout mid-verification. The sale-parsing regex (`SAVINGS_RE`) is verified offline against real captured markup and the men's filter reuses logic already confirmed live on carlsgolfland, but neither has been confirmed live on rockbottomgolf itself yet.

## Backlog

### Data persistence & tracking
- [ ] Persist results over time in SQLite (like the Detroit Putter Co. retailer scraper) instead of overwriting a single CSV, so price history is queryable. `run_timestamp` (in `test_scrapers.py`) is a step toward this but isn't real history yet.
- [ ] Define a dedup key once persisted - e.g. `(site, brand, club_type, variant, name, run_timestamp)` - so reruns don't just pile up duplicate rows.
- [ ] Price-drop/deal alerting: once history exists, compare each pull against the stored low/previous price and flag drops (start with a printed/logged summary; could grow into email/Slack).
- [ ] Cross-site product matching: normalize names (strip suffixes like "- ON SALE", "2026", "Left Handed") so the same real-world club can be compared side-by-side across sites instead of showing up as unrelated rows.

### Code quality & tooling
- [ ] Add pagination support to rockbottomgolf's scraper (only grabs page 1 today; carlsgolfland's `max_pages` pattern already handles this).
- [ ] Local parser tests using saved HTML fixtures, so selector/parsing logic can be iterated on without hitting live sites (and without risking rockbottomgolf's Cloudflare throttle) on every change.
- [ ] Structured logging instead of `print()`, so a run's output can be reviewed from a file later.
- [ ] Simple CLI (`argparse`) to run a single brand/club_type/site combo on demand instead of always running the full matrix.
- [ ] Look for a lighter-weight path into rockbottomgolf.com (sitemap.xml, RSS/product feed, or a page type that sits outside the Cloudflare challenge).

### Data enrichment
- [ ] Shaft/flex option data: 2ndswing.com exposes this for free; carlsgolfland's `jsonConfig` blob (already fetched for variant/discount lookups) also has it and could be extracted the same way `variant_label` is now.

## Done
- [x] Both sites scrapeable: carlsgolfland.com via plain `requests` + BeautifulSoup (no Cloudflare); rockbottomgolf.com via Selenium (Cloudflare JS challenge, needs a visible browser window - headless gets flagged).
- [x] Parameterized scrapers keyed off `config.py` (`BRANDS`, `CLUB_TYPES`) - name/price extraction verified for drivers, fairway woods, and iron sets on both sites.
- [x] Loft/set-specific variant pricing (`fairway_wood_7`, `iron_set` on carlsgolfland) instead of family-level pricing, via `config.VARIANT_TARGETS`.
- [x] Rate limiting (`config.RATE_LIMIT_SECONDS`) and a cap on per-product detail lookups (`config.MAX_VARIANT_LOOKUPS`) so a run doesn't hammer either site.
- [x] rockbottomgolf's per-product lookup hardened against Selenium/Cloudflare flakiness with retries + automatic browser restart.
- [x] More brands added (`config.BRANDS`: Callaway, TaylorMade, Titleist, Ping, Cobra, Mizuno) - no scraper changes needed.
- [x] Men's-only filtering (`config.MENS_ONLY_EXCLUDE_TERMS`) applied in both scrapers' listing parse.
- [x] Sale badges, discount %, and stock status (`on_sale`, `original_price`, `discount_pct`, `stock_status`) on both scrapers, with minimal extra requests.
- [x] `run_timestamp` column added to `test_scrapers.py`'s CSV output for tracking runs over time.
- [x] Investigated alternate sites for the Cloudflare issue - see "Priority" section above for what came out of it.

## Reference: sites checked, not investigated further
- **dickssportinggoods.com**, **golfgalaxy.com**, **austad.com** - all returned 403/blocked ("Site Maintenance" title, likely bot detection rather than literal maintenance). Not Cloudflare specifically, but blocked all the same.
- **golfdiscount.com** - no Cloudflare, but it's a Vue single-page app; the HTML `requests` gets back is an empty shell before client-side rendering, so it'd need Selenium/Playwright anyway. Deprioritized.
