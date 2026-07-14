# Club Price Tracker - TODO

## Done
- [x] Confirmed carlsgolfland.com is scrapeable with plain `requests` + BeautifulSoup (no Cloudflare protection).
- [x] Confirmed rockbottomgolf.com requires Selenium - it's behind a Cloudflare JS challenge, and headless Chrome gets blocked, so it needs a visible browser window.
- [x] Built parameterized scrapers for both sites keyed off `config.py` (`BRANDS`, `CLUB_TYPES`) so new brands/club types don't require code changes.
- [x] Verified name+price extraction for Callaway drivers, fairway woods, and iron sets on both sites.

## Next up
- [ ] **Loft-specific variant pricing**: fairway wood / iron set searches currently return the general product family (e.g. "Callaway Quantum Max Fairway Woods 2026" covers 3W/5W/7W/9W as a configurable product), not the price for a specific 7-wood or a specific 3-10 iron set. Need to open each product page and select the matching loft/set option (via the product's Magento swatch or the shop's option picker) to get the exact price for that variant.
- [ ] **MAP-hidden prices on carlsgolfland.com**: "Add to Cart for Price" items return `price=None` from the listing page - unlike rockbottomgolf.com, the real price isn't in the listing HTML at all. Need to check whether it shows up after simulating "add to cart" (may require a session/cart API call) or just visiting the product page.
- [ ] Add pagination support end-to-end (rockbottomgolf scraper only grabs page 1 by default; wire up `max_pages` the way carlsgolfland's is).
- [ ] Persist results over time (SQLite, like the Detroit Putter Co. retailer scraper) instead of overwriting a single CSV, so price history can be tracked.
- [ ] Add more brands beyond Callaway (TaylorMade, Titleist, etc.) - just extend `BRANDS` in `config.py`, no scraper changes needed.
- [ ] Add retry/backoff handling for network errors and Cloudflare challenge timeouts.
- [ ] Decide on a run cadence (e.g. daily) and wire up scheduling once the pipeline is stable.
