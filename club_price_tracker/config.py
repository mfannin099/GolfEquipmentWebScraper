"""Shared config for the multi-site golf club price tracker.

Add a brand to BRANDS or a club type to CLUB_TYPES and every scraper
picks it up automatically.
"""

BRANDS = [
    "Callaway",
    "TaylorMade",
    "Titleist",
    "Ping",
    "Cobra",
    "Mizuno",
]

# club type -> search term
CLUB_TYPES = {
    "driver": "driver",
    "fairway_wood_3": "3 wood",
    "fairway_wood_7": "7 wood",
    "hybrid": "hybrid",
    "iron_set": "iron set",
    "wedge": "wedge",
    "putter": "putter",
}

# Sub-brands a parent brand's clubs are sold under. tgw.com lists them
# under the sub-brand only ("Scotty Cameron Newport Putter"), so without
# these the brand filter drops every one. The `brand` column keeps the
# parent brand either way.
BRAND_ALIASES = {
    "Titleist": ["Scotty Cameron", "Vokey"],
    "Callaway": ["Odyssey"],
}

# Accessories both sites' search mixes in with actual clubs.
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

# Non-standard lines. The tracker is scoped to right-handed men's clubs;
# clear this list to widen that.
MENS_ONLY_EXCLUDE_TERMS = [
    "women",
    "ladies",
    "junior",
    "girl",
    "left handed",
    "lh ",
    "(lh)",
]

# At least one of these must appear in a listing name for it to count as
# the club type. Search is loose enough that "Titleist putter" on tgw.com
# returns 42 drivers and fairway woods out of 44 results.
CLUB_TYPE_KEYWORDS = {
    "driver": ["driver"],
    "fairway_wood_3": ["fairway", "wood"],
    "fairway_wood_7": ["fairway", "wood"],
    "hybrid": ["hybrid"],
    "iron_set": ["iron"],
    "wedge": ["wedge"],
    "putter": ["putter"],
}

# Minimum seconds between requests to a site.
RATE_LIMIT_SECONDS = 1.5

# Which variant to price, for club types sold as one product with a
# loft/set-makeup picker. Each site models variants differently: a
# dropdown option label on carlsgolfland, a set composition or numeric
# loft on tgw.com. A club type with no entry keeps the listing page's
# family-level price.
VARIANT_TARGETS = {
    "carlsgolfland.com": {
        "fairway_wood_3": "3 wood",
        "fairway_wood_7": "7 wood",
        "iron_set": "5-pw",
    },
    "tgw.com": {
        # tgw.com labels woods by loft degree, not number.
        "fairway_wood_3": "15.0",
        "fairway_wood_7": "21.0",
        "iron_set": "5-pw",
    },
}

# Cap on product-page requests per brand/club-type combination. Those
# pages are the only source of descriptions, stock status and exact
# variant prices, but cost one rate-limited request each. None = no cap.
MAX_VARIANT_LOOKUPS = 5


def build_query(brand: str, club_type: str) -> str:
    if club_type not in CLUB_TYPES:
        raise ValueError(f"Unknown club_type '{club_type}'. Options: {list(CLUB_TYPES)}")
    return f"{brand} {CLUB_TYPES[club_type]}"
