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
- [ ] **MAP-hidden prices on carlsgolfland.com**: "Add to Cart for Price" items return `price=None` even after variant resolution for some products - unlike rockbottomgolf.com, the real price isn't in that product's `jsonConfig` at all for those SKUs. Need to check whether it shows up after simulating "add to cart" (may require a session/cart API call) or just isn't exposed pre-checkout.
- [ ] Add pagination support end-to-end (rockbottomgolf scraper only grabs page 1 by default; wire up `max_pages` the way carlsgolfland's is).
- [ ] Persist results over time (SQLite, like the Detroit Putter Co. retailer scraper) instead of overwriting a single CSV, so price history can be tracked. Include a "date pulled" column so historical runs are comparable.
- [ ] Add more brands beyond Callaway (TaylorMade, Titleist, etc.) - just extend `BRANDS` in `config.py`, no scraper changes needed.
- [ ] Decide on a run cadence (e.g. daily) and wire up scheduling once the pipeline is stable.
- [ ] Review what additional pieces of data can be gathered for both sites (e.g. shaft/flex options, stock status, sale badges) beyond name + price.
