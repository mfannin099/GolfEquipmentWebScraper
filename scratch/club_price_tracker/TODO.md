# Club Price Tracker - TODO

## Done
- [x] Confirmed carlsgolfland.com is scrapeable with plain `requests` + BeautifulSoup (no Cloudflare protection).
- [x] Confirmed rockbottomgolf.com requires Selenium - it's behind a Cloudflare JS challenge, and headless Chrome gets blocked, so it needs a visible browser window.
- [x] Built parameterized scrapers for both sites keyed off `config.py` (`BRANDS`, `CLUB_TYPES`) so new brands/club types don't require code changes.
- [x] Verified name+price extraction for Callaway drivers, fairway woods, and iron sets on both sites.
- [x] **Loft/set-specific variant pricing**: both scrapers now resolve an exact price for `fairway_wood_7` (and `iron_set` on carlsgolfland) instead of the general product-family price. carlsgolfland reads the embedded `jsonConfig` price map on each product page; rockbottomgolf selects the matching loft dropdown option and reads the updated price. `config.VARIANT_TARGETS` controls which option/label is matched per site - adjust if you want a different loft or set makeup (e.g. "4-pw" instead of "5-pw").
- [x] **Rate limiting**: both scrapers throttle requests via `rate_limiter.RateLimiter` (`config.RATE_LIMIT_SECONDS`, default 1.5s between requests) instead of hammering either site back-to-back.
- [x] **Capped per-product variant lookups**: `config.MAX_VARIANT_LOOKUPS` (default 5) limits how many listing results get the expensive per-product-page variant resolution per run, so a test run doesn't sit there visiting every result on a Cloudflare-fronted site. Set to `None` for no cap once the pipeline needs full coverage.
- [x] Hardened rockbottomgolf's per-product variant lookup against Selenium/Cloudflare flakiness ("window already closed" mid-run) with retries (3 attempts) and an automatic browser restart between attempts.

## Known issue
- [ ] **rockbottomgolf.com can throttle/lock out a session entirely**: after enough rapid automated Chrome sessions in a short window (e.g. repeated test runs during development), Cloudflare stopped resolving its JS challenge at all - even a real, visible, non-headless browser got stuck on "Just a moment..." indefinitely. `RATE_LIMIT_SECONDS` and `MAX_VARIANT_LOOKUPS` reduce how much load we put on it per run, but don't fully prevent this if you run the scraper repeatedly back-to-back while testing. If a run hangs on `_wait_for_results`, wait a while (get more than one Cloudflare cooldown period) before trying again rather than immediately retrying.

## Next up
- [ ] Add pagination support end-to-end (rockbottomgolf scraper only grabs page 1 by default; wire up `max_pages` the way carlsgolfland's is).
- [ ] Persist results over time (SQLite, like the Detroit Putter Co. retailer scraper) instead of overwriting a single CSV, so price history can be tracked. Include a "date pulled" column so historical runs are comparable. Add date scrapped, append transactions, create some sort of key to check for duplicate
- [ ] Add more brands beyond Callaway (TaylorMade, Titleist, etc.) - just extend `BRANDS` in `config.py`, no scraper changes needed.
- [ ] Decide on a run cadence (e.g. daily) and wire up scheduling once the pipeline is stable.
- [ ] Review what additional pieces of data can be gathered for both sites (e.g. shaft/flex options, stock status, sale badges) beyond name + price... focus on just Mens clubs
- [ ] Look for sales, deals, etc for clubs
- [ ] Look into other websites that may not have the cloudflare issueß

## Ideas / further improvements
- [ ] **Filter to Men's clubs by default**: listings currently include Women's/Ladies and Left-Handed variants (e.g. "Callaway Womens Quantum Max Driver", "...(Left Handed)") mixed in with the results we actually want. Add a `hand`/`gender` filter in `config.py` (default Right-hand, Men's) and apply it in `_parse_page`/`scrape_current_page` so those get excluded up front instead of needing manual cleanup after the fact. Directly supports the "focus on just Mens clubs" note above.
- [ ] **Local parser tests using saved HTML fixtures**: save a few real response bodies (listing page + product page) to disk and write tests against them instead of hitting the live sites on every code change. Would let us iterate on selector/parsing logic without repeatedly tripping rockbottomgolf's Cloudflare throttle during development - directly mitigates the "Known issue" above.
- [ ] **Dedup key for persisted history**: once results are stored over time (see SQLite item above), define a natural key - e.g. `(site, brand, club_type, variant, name)` - so re-running on the same day updates that row's price instead of inserting a duplicate, while still keeping one row per `date_pulled` for trend history.
- [ ] **Price-drop / deal alerting**: once history is persisted, compare each new pull against the stored low or previous price for that club and flag anything that dropped (start with a printed/logged summary, could grow into an email or Slack notification). Builds on "Look for sales, deals, etc for clubs" above.
- [ ] **Cross-site product matching**: normalize product names (strip site-specific suffixes like "- ON SALE", "2026", "Left Handed") so the same real-world club can be compared side-by-side between carlsgolfland and rockbottomgolf, instead of showing up as unrelated rows in the same CSV.
- [ ] **Structured logging instead of print()**: swap the scrapers' `print()` calls for the standard `logging` module so a scheduled/unattended run can log to a file and be reviewed later, rather than only ever showing up in stdout.
- [ ] **Simple CLI for one-off runs**: add `argparse` support to run a single brand/club_type/site combo on demand (e.g. `uv run python test_scrapers.py --site carlsgolfland --club-type driver`) instead of always running the full brand x club_type x site matrix or editing code to test one combination.
- [ ] **Look for a lighter-weight path into rockbottomgolf.com**: check whether a sitemap.xml, RSS/product feed, or a specific page type sits outside the Cloudflare challenge - could reduce how much of the flow needs Selenium at all, even if product-page variant lookups still do.