# Club Price Tracker - TODO

## Roadmap (next up, in order)
1. **Long-term storage** - move off per-run CSV overwrites into SQLite (pattern already proven in the Detroit Putter Co. retailer scraper), so price history is actually queryable. Needs a dedup key - `(site, brand, club_type, variant, name, run_timestamp)` - so reruns don't just pile up duplicate rows. `run_timestamp` in `test_scrapers.py` is a step toward this but isn't real history yet.
2. **API layer** - once storage is queryable, expose it over an API rather than everyone reading CSVs/the DB directly. Not yet scoped (framework, auth, read-only vs. write) - revisit once storage lands.
3. **Frontend for search** - a simple UI for a user to search/filter tracked clubs (by brand, club type, price range, on-sale) against the API above. Not yet scoped - revisit once the API exists.
4. **Investigate golfnow.com** - confirmed scope: this is NBC Sports' **tee-time booking platform**, not an equipment retailer - a different domain (courses/tee-times, not brands/clubs) from everything else in this tracker. Needs its own scoping pass (what data, what site protections, how/whether it plugs into the same storage & API) before any scraper work starts; do not assume it slots into the existing `config.py`/`BRANDS`/`CLUB_TYPES` model.

Price-drop/deal alerting (compare each pull against the stored low/previous price, flag drops - start with a printed/logged summary, could grow into email/Slack) and cross-site product matching (normalize names - strip suffixes like "- ON SALE", "2026", "Left Handed" - so the same real-world club can be compared side-by-side across sites) both depend on storage landing first (#1) - revisit after.

## Site coverage
- **Scraping now:** carlsgolfland.com and tgw.com - both plain `requests` + BeautifulSoup, no Cloudflare JS challenge, no lockouts.
- **Surveyed, not yet built** (see `git log` / prior TODO revisions for the full curl-verification notes if needed):
  - `globalgolf.com` - no Cloudflare (IIS). Browse `/golf-clubs/{brand}/` category pages and filter by keyword; its own search endpoint is client-side AJAX, don't rely on it.
  - `golfdirectnow.com` - Shopify, Cloudflare-fronted but no JS challenge. Standard `/search?q=` + `.card__` markup.
  - `worldwidegolfshops.com` - VTEX, no Cloudflare. Gzip-encoded responses regardless of `Accept-Encoding` - use a client that auto-decompresses.
  - `2ndswing.com` - no Cloudflare, Magento-based. **Used/pre-owned marketplace**, not new-club MSRP - per-unit inventory (condition + price per physical club), not a family/variant model like the sites above. A complementary addition, not a replacement.
  - `pgatoursuperstore.com` - unresolved. A plain `requests` call only got a bare 302 redirect with no body; needs a re-check following the redirect.
- **Ruled out:** `puetzgolf.com`, `dickssportinggoods.com`, `golfgalaxy.com`, `austad.com` - all blocked (Cloudflare challenge or generic 403/"Site Maintenance" bot detection). `golfdiscount.com` - no Cloudflare, but a Vue SPA with an empty HTML shell pre-render, would need Selenium/Playwright anyway.

## Backlog

### Data enrichment
- [ ] Shaft/flex option data: 2ndswing.com exposes this for free; carlsgolfland's `jsonConfig` blob (already fetched for variant/discount lookups) has it too, extractable the same way `variant_label` is now. tgw.com's `productJson` blob also has it (`ClubFlexCode`, `ClubShaftCode`/`ClubShaftDescription` per variant) - not yet pulled into results.
- [ ] Extend `description` (currently tgw.com-only) to carlsgolfland.com - its product page doesn't expose it in `jsonConfig`, needs a separate selector for wherever the marketing copy lives there.
- [ ] Customer reviews (ratings/text): deliberately left out of the description work. tgw.com's `productJson` already carries `AverageRating`/`NumberOfReviews`/`NewestReviews` per-variant on the same request used for description, so this is cheap to add later (parsing only, no new requests). Revisit if reviews become a priority.

### Code quality & tooling
- [ ] Add pagination support to tgw.com's scraper (only grabs the first `/l/search` results page today, ~96 tiles - carlsgolfland's `max_pages` pattern already handles this and could be ported over if a query ever needs more than one page).
- [ ] Local parser tests using saved HTML fixtures, so selector/parsing logic can be iterated on without hitting live sites on every change.
- [ ] Simple CLI (`argparse`) to run a single brand/club_type/site combo on demand instead of always running the full matrix.

## Done
- [x] **Structured logging** (`logging_config.py`) - `test_scrapers.py` logs to console always, and to a timestamped file under `scratch/club_price_tracker/logs/` (gitignored) when its `WRITE_LOGS_TO_FILE` flag is set to `True`, so a run can be reviewed later without rerunning it. Per-site scrape failures are caught and logged with a traceback instead of killing the whole run.
- [x] **tgw.com scraper** (`tgw_scraper.py`) - Cloudflare-fronted but not JS-challenge-protected, so plain `requests` works, no Selenium, no lockouts across a full 18-combo test run. Search via `/l/search?k={query}` (`.product-tile` cards); listing page already carries real + "was" price for free sale/discount detection, no extra request needed (unlike carlsgolfland). Product pages embed a `var productJson = {...}` blob (mirrors carlsgolfland's `jsonConfig`) used for variant resolution (`SetComposition` string for iron_set, numeric `ClubLoft` for fairway_wood_7 - tgw doesn't label wood variants by number, 21.0° is a "7 wood"), stock status (`HasBackorderMessage`/`InventoryMessage`/`StockMessage`), and description.
- [x] **`description` field added** (tgw.com only, per-product marketing copy from `productJson.Description`, cleaned to plain text) - fetched on every listing visited for product-page detail, capped by `config.MAX_VARIANT_LOOKUPS` same as variant/stock lookups, so no extra requests beyond what carlsgolfland-style detail lookups already cost.
- [x] Both sites scrapeable without browser automation: carlsgolfland.com and tgw.com, both plain `requests` + BeautifulSoup.
- [x] Parameterized scrapers keyed off `config.py` (`BRANDS`, `CLUB_TYPES`) - name/price extraction verified for drivers, fairway woods, and iron sets on both sites.
- [x] Loft/set-specific variant pricing (`fairway_wood_7`, `iron_set`) instead of family-level pricing, via `config.VARIANT_TARGETS`, on both sites.
- [x] Rate limiting (`config.RATE_LIMIT_SECONDS`) and a cap on per-product detail lookups (`config.MAX_VARIANT_LOOKUPS`) so a run doesn't hammer either site.
- [x] More brands added (`config.BRANDS`: Callaway, TaylorMade, Titleist, Ping, Cobra, Mizuno) - no scraper changes needed.
- [x] Men's-only filtering (`config.MENS_ONLY_EXCLUDE_TERMS`) applied in both scrapers' listing parse.
- [x] Sale badges, discount %, and stock status (`on_sale`, `original_price`, `discount_pct`, `stock_status`) on both scrapers, with minimal extra requests.
- [x] `run_timestamp` column added to `test_scrapers.py`'s CSV output for tracking runs over time.
- [x] Site survey for the Cloudflare-lockout problem - see "Site coverage" above for the outcome.
