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
    "fairway_wood_3": "3 wood",
    "fairway_wood_7": "7 wood",
    "hybrid": "hybrid",
    "iron_set": "iron set",
    "wedge": "wedge",
    "putter": "putter",
}

# Sub-brands that a parent brand's clubs are actually sold under. Both
# sites' search finds them for a "Titleist putter" query, but the product
# names carry only the sub-brand - tgw.com lists "Scotty Cameron Super
# Select Newport Putter" with no "Titleist" anywhere in it, so the
# brand-name filter would throw away every one of them. carlsgolfland
# happens to prefix the parent brand ("Titleist Scotty Cameron ...") but
# that's not something to rely on.
#
# A row's `brand` column stays the parent brand, which is what makes
# putters comparable across sites.
BRAND_ALIASES = {
    "Titleist": ["Scotty Cameron", "Vokey"],
    "Callaway": ["Odyssey"],
}

# Case-insensitive substrings marking a listing as an accessory rather
# than a club. Both sites' search does loose keyword matching, so a query
# like "TaylorMade 3 wood" returns headcovers and bags alongside actual
# clubs - and "Callaway putter" on carlsgolfland returns package sets.
# Filtered out during the listing parse so they never reach the results
# or cost a product-page request.
NON_CLUB_TERMS = [
    "headcover",
    "head cover",
    "shaft",
    "grip",
    " bag",
    "glove",
    "towel",
    "package set",
    "piece set",
    "alignment stick",
    "divot tool",
    "ball marker",
]

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


# Words that must appear in a listing name for it to count as this club
# type. Both sites' search is keyword-based and loose enough that a
# "Titleist putter" query on tgw.com comes back mostly drivers and
# fairway woods - without this, 42 of 44 results would be stored with
# club_type="putter", making the column useless for filtering.
#
# Any one keyword matching is enough.
CLUB_TYPE_KEYWORDS = {
    "driver": ["driver"],
    "fairway_wood_3": ["fairway", "wood"],
    "fairway_wood_7": ["fairway", "wood"],
    "hybrid": ["hybrid"],
    "iron_set": ["iron"],
    "wedge": ["wedge"],
    "putter": ["putter"],
}


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
# price, not the price for our specific target. These are the values
# used to pick out the right variant per site - each site models "which
# variant" differently (a dropdown option label on carlsgolfland, a
# SetComposition string + numeric loft on tgw.com), so the target shape
# differs accordingly. Adjust these if you want a different loft or set
# makeup (e.g. "4-pw" instead of "5-pw").
# A club type with no entry here (driver, hybrid, wedge, putter) keeps
# whatever the listing page showed - those are either sold as a single
# listing per spec already, or their variants (wedge loft, putter length)
# aren't something the tracker picks a canonical one of yet.
VARIANT_TARGETS = {
    "carlsgolfland.com": {
        "fairway_wood_3": "3 wood",
        "fairway_wood_7": "7 wood",
        "iron_set": "5-pw",
    },
    "tgw.com": {
        # Unlike carlsgolfland, tgw.com doesn't label fairway wood
        # variants by number ("7 wood") - only by loft degree. 15.0 and
        # 21.0 are the standard lofts for a 3 wood and a 7 wood.
        # tgw_scraper._match_variant treats a numeric target as a loft.
        "fairway_wood_3": "15.0",
        "fairway_wood_7": "21.0",
        "iron_set": "5-pw",
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
