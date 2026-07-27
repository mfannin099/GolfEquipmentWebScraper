# Club Price Tracker - TODO

## Priority: reduce reliance on Cloudflare-protected sites
Status: **rockbottomgolf.com has been dropped and replaced by tgw.com** (2026-07-27) - see "Done" below. Its Selenium scraper (`rockbottomgolf_scraper.py`) is removed entirely; `test_scrapers.py` now runs carlsgolfland.com + tgw.com. This section stays open for further diversifying beyond those two.

### 2026-07-27 site survey - verified with live curl checks (plain `requests`, no Selenium)

Checked status codes, headers (`server`, `cf-ray`), body content for JS-challenge markers, real price/product markup, and repeat-request behavior (5 back-to-back requests, no lockout on any of these).

- [ ] **Build a globalgolf.com scraper** - next candidate if a 3rd/4th source is wanted. `server: Microsoft-IIS/10.0`, no Cloudflare at all. Category pages (`/golf-clubs/{brand}/`) are fully server-rendered with real prices in the raw HTML (`class="price"`, `data-url="/golf-clubs/{id}-{slug}/"`), both new and used prices per listing. The site's own search endpoint (`/search/?q=...`) appears to be a client-side/AJAX widget (results list renders as an empty `<div class="hide resultsList box">` in the raw HTML) - don't rely on it. Instead browse `/golf-clubs/{brand}/` category pages (already brand-scoped, matches `config.BRANDS`) and filter listing titles by club-type keyword client-side, same idea as the `MENS_ONLY_EXCLUDE_TERMS` filtering already done in-repo. Survived 5 rapid repeat requests with no blocking.
- [ ] **Build a golfdirectnow.com scraper** - also viable, Shopify-based. Also Cloudflare-fronted but no challenge triggered by plain `requests`. Standard Shopify `/search?q={query}` and `/collections/golf-clubs` both return server-rendered `.card__` product cards with real names (confirmed `Callaway Elyte X Driver` for query `Callaway driver`) and prices under `.price__regular .price-item--regular` (format `$ 399.99`, note the space after `$`). Straightforward Shopify scraping pattern, well-documented elsewhere. Survived 5 rapid repeat requests with no blocking.
- [x] **worldwidegolfshops.com** - inspected. No Cloudflare (VTEX platform, fronted by CloudFront/nginx). Real server-rendered listings with `sellingPrice` data on category pages like `/golf-clubs/drivers`. Note it returns gzip-encoded bodies regardless of `Accept-Encoding`, so any HTTP client must decompress (`curl --compressed`, or `requests` which handles this automatically) - a naive raw byte read will look like garbage. Viable candidate, not yet prioritized since globalgolf/golfdirectnow have more directly search-queryable endpoints.
- [ ] **2ndswing.com scraper** - still a candidate from the prior pass. No Cloudflare, fully server-rendered (plain `requests` works), Magento-based (`.product-item` cards, same pattern as carlsgolfland). It's a **used/pre-owned marketplace** though, not new-club MSRP - each listing is one physical club with its own condition, price, and "WAS" price baked right into the card text (e.g. `Tour Edge | Hot Launch E523 | $91.99 | WAS | $137.99 | Mint | Dexterity: Right | Loft: 15° | Flex: Ladies | Shaft: ...`). Richer per-listing data than either current site, but a different product category (used vs. new) - a complementary addition, not a replacement. Would need its own `club_type` handling since it's per-unit inventory, not a family/variant model.
- [x] **puetzgolf.com** - ruled out. Returns a straight `403` with Cloudflare `challenge-platform` markers on a plain request - same class of problem as rockbottomgolf, not worth adding.
- [ ] **Re-check pgatoursuperstore.com** - a plain `requests` call only got a bare 302 redirect with no body; re-check following the redirect before concluding anything.
- [x] **tgw.com built and shipped** - see `tgw_scraper.py` and "Done" below.

## Backlog

### Data persistence & tracking
- [ ] Persist results over time in SQLite (like the Detroit Putter Co. retailer scraper) instead of overwriting a single CSV, so price history is queryable. `run_timestamp` (in `test_scrapers.py`) is a step toward this but isn't real history yet.
- [ ] Define a dedup key once persisted - e.g. `(site, brand, club_type, variant, name, run_timestamp)` - so reruns don't just pile up duplicate rows.
- [ ] Price-drop/deal alerting: once history exists, compare each pull against the stored low/previous price and flag drops (start with a printed/logged summary; could grow into email/Slack).
- [ ] Cross-site product matching: normalize names (strip suffixes like "- ON SALE", "2026", "Left Handed") so the same real-world club can be compared side-by-side across sites instead of showing up as unrelated rows.

### Code quality & tooling
- [ ] Add pagination support to tgw.com's scraper (only grabs the first `/l/search` results page today, ~96 tiles - carlsgolfland's `max_pages` pattern already handles this and could be ported over if a query ever needs more than one page).
- [ ] Local parser tests using saved HTML fixtures, so selector/parsing logic can be iterated on without hitting live sites on every change.
- [ ] Structured logging instead of `print()`, so a run's output can be reviewed from a file later.
- [ ] Simple CLI (`argparse`) to run a single brand/club_type/site combo on demand instead of always running the full matrix.

### Data enrichment
- [ ] Shaft/flex option data: 2ndswing.com exposes this for free; carlsgolfland's `jsonConfig` blob (already fetched for variant/discount lookups) also has it and could be extracted the same way `variant_label` is now. tgw.com's `productJson` blob has this too (`ClubFlexCode`, `ClubShaftCode`/`ClubShaftDescription` per variant) - not yet pulled into results.
- [ ] Extend `description` (currently tgw.com-only, see Done below) to carlsgolfland.com - its product page doesn't expose it in `jsonConfig`, would need a separate selector for whatever holds the marketing copy there.
- [ ] Customer reviews (ratings/text) were deliberately left out of the `description` work below - tgw.com's `productJson` blob does carry `AverageRating`/`NumberOfReviews`/`NewestReviews` per-variant already fetched for description, so pulling review data in later is cheap (no new requests), just parsing. Revisit if reviews become a priority.

## Done
- [x] **2026-07-27: rockbottomgolf.com replaced by tgw.com.** `tgw_scraper.py` added, `rockbottomgolf_scraper.py` deleted, `test_scrapers.py`/`config.py` updated. tgw.com is Cloudflare-fronted but not JS-challenge-protected - plain `requests` works, no Selenium, no lockouts observed across a full 18-combo test run. Search via `/l/search?k={query}` (`.product-tile` cards); listing page already carries real + "was" price for free sale/discount detection, no extra request needed (unlike carlsgolfland). Product pages embed a `var productJson = {...}` blob (mirrors carlsgolfland's `jsonConfig`) used for: variant resolution (`SetComposition` string for iron_set, numeric `ClubLoft` for fairway_wood_7 - tgw doesn't label wood variants by number, 21.0° is a "7 wood"), stock status (`HasBackorderMessage`/`InventoryMessage`/`StockMessage`), and the new `description` field (see below).
- [x] **2026-07-27: `description` field added** (tgw.com only, per-product marketing copy from the `productJson.Description` HTML, cleaned to plain text) - fetched on every listing visited for product-page detail, capped by `config.MAX_VARIANT_LOOKUPS` same as variant/stock lookups, so no extra requests beyond what carlsgolfland-style detail lookups already cost. Reviews were explicitly scoped out of this pass (see Data enrichment above).
- [x] Both sites scrapeable: carlsgolfland.com via plain `requests` + BeautifulSoup (no Cloudflare); tgw.com likewise (Cloudflare-fronted but no JS challenge).
- [x] Parameterized scrapers keyed off `config.py` (`BRANDS`, `CLUB_TYPES`) - name/price extraction verified for drivers, fairway woods, and iron sets on both sites.
- [x] Loft/set-specific variant pricing (`fairway_wood_7`, `iron_set`) instead of family-level pricing, via `config.VARIANT_TARGETS`, on both carlsgolfland and tgw.
- [x] Rate limiting (`config.RATE_LIMIT_SECONDS`) and a cap on per-product detail lookups (`config.MAX_VARIANT_LOOKUPS`) so a run doesn't hammer either site.
- [x] More brands added (`config.BRANDS`: Callaway, TaylorMade, Titleist, Ping, Cobra, Mizuno) - no scraper changes needed.
- [x] Men's-only filtering (`config.MENS_ONLY_EXCLUDE_TERMS`) applied in both scrapers' listing parse.
- [x] Sale badges, discount %, and stock status (`on_sale`, `original_price`, `discount_pct`, `stock_status`) on both scrapers, with minimal extra requests.
- [x] `run_timestamp` column added to `test_scrapers.py`'s CSV output for tracking runs over time.
- [x] Investigated alternate sites for the Cloudflare issue - see "Priority" section above for what came out of it.

## Reference: sites checked, not investigated further
- **dickssportinggoods.com**, **golfgalaxy.com**, **austad.com** - all returned 403/blocked ("Site Maintenance" title, likely bot detection rather than literal maintenance). Not Cloudflare specifically, but blocked all the same.
- **golfdiscount.com** - no Cloudflare, but it's a Vue single-page app; the HTML `requests` gets back is an empty shell before client-side rendering, so it'd need Selenium/Playwright anyway. Deprioritized.
