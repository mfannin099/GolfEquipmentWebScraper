"""Shared config for the multi-site golf club price tracker.

Add a brand to BRANDS or a club type to CLUB_TYPES and every scraper
in this package picks it up automatically.
"""

BRANDS = [
    "Callaway",
    "TaylorMade",
    "Titleist",
    "Ping",
    "Cobra",
    "Mizuno",
]

# key -> search term used to build each site's query string
CLUB_TYPES = {
    "driver": "driver",
    "fairway_wood_7": "7 wood",
    "iron_set": "iron set",
}

# Case-insensitive substrings that mark a listing as not a standard
# right-handed men's club (women's/junior/left-handed lines). Tracker is
# scoped to men's clubs for now - filtered out in each scraper's listing
# parse so they never make it into results or cost an extra product-page
# request. Clear this list (or override per-run) if that scope changes.
MENS_ONLY_EXCLUDE_TERMS = [
    "women",
    "ladies",
    "junior",
    "girl",
    "left handed",
    "lh ",
    "(lh)",
]


def build_query(brand: str, club_type: str) -> str:
    if club_type not in CLUB_TYPES:
        raise ValueError(f"Unknown club_type '{club_type}'. Options: {list(CLUB_TYPES)}")
    return f"{brand} {CLUB_TYPES[club_type]}"


# Minimum seconds between requests to a given site, so scrapers don't
# pull pages/product-variant data faster than a real shopper would.
RATE_LIMIT_SECONDS = 1.5

# fairway_wood_7 and iron_set are usually sold as one product with a
# loft/set-makeup picker rather than a distinct listing per variant, so a
# plain name/price scrape of the search results returns the *family*
# price, not the price for our specific target. These are the substrings
# (case-insensitive) used to pick out the right variant per site - the two
# sites model "which variant" differently (a dropdown option label on
# carlsgolfland vs. a suffix baked into the product name on
# rockbottomgolf), so the target string differs accordingly. Adjust these
# if you want a different loft or set makeup (e.g. "4-pw" instead of
# "5-pw").
VARIANT_TARGETS = {
    "carlsgolfland.com": {
        "fairway_wood_7": "7 wood",
        "iron_set": "5-pw",
    },
    "rockbottomgolf.com": {
        "fairway_wood_7": "#7 wood",
        "iron_set": "7 iron set",
    },
}

# Some data only exists on the product page, not the listing page: exact
# variant price (fairway_wood_7 on both sites, iron_set on carlsgolfland),
# stock status, and true discount/MSRP for carlsgolfland (its listing page
# never shows a struck-through "was" price, only the current one - see
# carlsgolfland_scraper.CarlsGolflandScraper._fetch_product_details).
# Every one of those requires opening a separate page per listing result,
# so this caps how many of those extra requests a single run makes -
# only the first N eligible listing results get product-page detail; the
# rest keep whatever the listing page showed (no stock/discount info, and
# a family-level price where a variant applies). Keeps a test run from
# sitting there hammering a Cloudflare-fronted site for minutes. Set to
# None for no cap.
MAX_VARIANT_LOOKUPS = 5
