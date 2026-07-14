"""Shared config for the multi-site golf club price tracker.

Add a brand to BRANDS or a club type to CLUB_TYPES and every scraper
in this package picks it up automatically.
"""

BRANDS = [
    "Callaway",
]

# key -> search term used to build each site's query string
CLUB_TYPES = {
    "driver": "driver",
    "fairway_wood_7": "7 wood",
    "iron_set": "iron set",
}


def build_query(brand: str, club_type: str) -> str:
    if club_type not in CLUB_TYPES:
        raise ValueError(f"Unknown club_type '{club_type}'. Options: {list(CLUB_TYPES)}")
    return f"{brand} {CLUB_TYPES[club_type]}"
