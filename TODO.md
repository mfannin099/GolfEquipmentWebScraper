# Club Price Tracker - TODO

## MVP application

Goal: a user picks brand / club type / site and either searches the stored history or triggers a live scrape.

The pieces already in place: `run_final_scrape.scrape()` returns rows without touching the DB, `run_final_scrape.save()` persists them, `--brand` accepts free text, and WAL mode lets the app read while a scrape writes. Streamlit is the shortest path — one file, no callbacks, `st.dataframe` handles the table for free.

**Build in this order:**

- [ ] **1. Read-only view first.** `app.py` with sidebar filters (brand, club type, site, date range, on-sale-only) running a `SELECT` against `data/club_prices.db`. No scraping. This is genuinely most of the value and needs no new backend code.
  - Add a `query_history()` to `database.py` rather than putting SQL in the UI.
  - Open the connection read-only (`file:...?mode=ro` URI) so the app can never corrupt history.
  - `@st.cache_data` the query, keyed on the filters, or every widget change re-runs it.
- [ ] **2. Price history chart.** With `run_timestamp` per row, a line chart per listing is the payoff of collecting history. Needs 3+ runs to look like anything.
- [ ] **3. Live scrape button.** Calls `scrape()` directly, renders rows, doesn't save.
  - Must pass `max_variant_lookups=0` or a page load waits on rate-limited product requests. A full combination is ~8s with the cap at 0; ~15s at 5.
  - Restrict to one brand + one club type + one site per click. The full matrix is ~15 minutes and will time out.
  - `st.spinner` + a row count, or it looks hung.
- [ ] **4. Deal view.** Biggest `discount_pct` in the most recent run, and anything cheaper than its own previous price — `price_alerts.log_price_drops()` already has that logic; return the drops instead of only logging them.

**Decisions to make when starting:**
- Where the app file lives — a sibling `app/` directory keeps Streamlit's dependency out of the scraper package.
- Whether a scrape is triggered from the UI at all, or the app stays read-only and collection is purely scheduled. Read-only is safer and simpler; scheduling covers freshness.
- SQLite is single-writer. Fine for one local user; if the app is ever hosted for several, scraping needs to move behind a queue.

## Scheduling the scraper

Nothing about `run_final_scrape.py` needs to change to be scheduled — it's already a plain CLI with a proper exit code (1 when nothing was scraped) and `--log-file`.

- [ ] **Fix these two first — they matter much more once runs are unattended:**
  - `run_final_scrape.py` holds every combination in memory and only calls `save()` at the end, so a crash on the last of 84 combinations discards the whole ~15-minute run. Save per combination (or per brand).
  - `RateLimiter` is per scraper instance, so the 1.5s floor only applies *within* one brand/club-type combination — each new combination's first request goes out immediately. A per-site shared limiter would hold the real floor. Worth fixing before running unattended and repeatedly against someone else's site.
- [ ] **Pick a scheduler.** `launchd` is the right one for macOS — `cron` exists but Apple has deprecated it, and it won't run if the machine is asleep at the scheduled time whereas `launchd` catches up on wake.
  - A `~/Library/LaunchAgents/com.mattfannin.clubprices.plist` with `StartCalendarInterval` (daily, off-peak).
  - Must invoke by absolute path — `launchd` gets a minimal environment, so bare `uv` or `run_final_scrape` won't resolve. Either `/full/path/.venv/bin/run_final_scrape` (the installed console script) or `/full/path/to/uv run --project /full/path run_final_scrape`.
  - `WorkingDirectory` no longer matters for imports now that `club_price_tracker` is a real package with relative imports — `DB_PATH`/`LOG_DIR` resolve from `__file__` either way.
  - Redirect `StandardOutPath`/`StandardErrorPath`, or a failure is silent.
- [ ] **Decide the cadence.** Daily is plenty — prices don't move hourly, and each run is ~900 rows, so a year of daily runs is ~330k rows. SQLite handles that without trouble.
- [ ] **Raise `MAX_VARIANT_LOOKUPS` for scheduled runs** (`--max-variant-lookups all`) — nobody's waiting on it, and it's the only way `description`/`stock_status` get filled in beyond the first few results. Expect a much longer run; check total wall time before committing to a schedule.
- [ ] **Notice failures.** A silent scheduled job that stopped working weeks ago is worse than no job. Simplest version: have the run write a row count somewhere the app displays, so a stale "last run" date is visible.
- [ ] If this ever needs to run when the laptop doesn't, it's a GitHub Actions cron + committing the DB, or a small always-on host. Both are a bigger change than they look, because the DB stops being local.

## Scrapers

- [ ] **Build a golfdirectnow.com scraper** - viable, Shopify-based. Also Cloudflare-fronted but no challenge triggered by plain `requests`. Standard Shopify `/search?q={query}` and `/collections/golf-clubs` both return server-rendered `.card__` product cards with real names (confirmed `Callaway Elyte X Driver` for query `Callaway driver`) and prices under `.price__regular .price-item--regular` (format `$ 399.99`, note the space after `$`). Adding it is a new `BaseScraper` subclass plus one entry in `run_final_scrape.SCRAPERS` - it then joins the matrix and the CLI's `--site` choices automatically.
- [ ] Link the 18 birdies project on github... allow user to pull 18 birdies data and analyze

## Data quality & coverage

- [ ] Cross-site product matching: the same club shows up as unrelated rows per site. `sku` is populated on both sites and carlsgolfland's doubles as the MPN, so check how far SKU/MPN matching gets before falling back to name normalization (stripping "- ON SALE", "2026", etc.).
- [ ] Track a rolling low/high per listing, not just the previous price, so "cheapest it's ever been" is answerable.
- [ ] Ratings are tgw.com-only. carlsgolfland's `data-bv-product-id` is a Bazaarvoice product ID, so their public API may supply rating/review count without a browser.
- [ ] `TgwScraper` ignores `max_pages` - `/l/search` returns everything in one response for the queries tried so far. Confirm that holds for broader searches.
- [ ] Some listings have a null `price` because the site shows "Add To Cart To See Price" (MAP pricing). Worth confirming the product page doesn't expose it.

## Code quality

- [ ] Local parser tests using saved HTML fixtures, so selector logic can be iterated without hitting live sites. The biggest remaining gap: every check costs real requests, and a broken selector is only caught by noticing a result count drop.
