"""Shared plumbing for the per-site club scrapers.

Every site needs the same things - a rate-limited GET with a browser
User-Agent, a way to pull an embedded JSON blob out of a <script> tag, the
same money/discount arithmetic, and the same "is this actually a men's
club from the brand we asked for?" filter. Keeping one copy here means a
new site's scraper is just its own parsing logic, and a fix to the shared
parts lands everywhere at once.

Subclasses set SITE, implement run(), and return a list of dicts whose
keys match database.COLUMNS (minus run_timestamp/extracted_date, which
scrape.save() stamps on).
"""

import json
import re

import requests
from bs4 import BeautifulSoup, Tag

from config import (
    BRAND_ALIASES,
    CLUB_TYPE_KEYWORDS,
    MAX_VARIANT_LOOKUPS,
    MENS_ONLY_EXCLUDE_TERMS,
    NON_CLUB_TERMS,
    RATE_LIMIT_SECONDS,
    VARIANT_TARGETS,
    build_query,
)
from rate_limiter import RateLimiter

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ClubPriceTracker/0.1)"}
REQUEST_TIMEOUT = 15

# Distinguishes "caller said nothing, use the configured default" from
# "caller explicitly passed None", which means no cap at all. A plain
# None default couldn't tell those apart.
USE_CONFIG_DEFAULT = object()


def extract_json_blob(html: str, marker: str) -> dict | None:
    """Pulls the first JSON object that appears after `marker`.

    Neither site exposes an API, so variant/price data has to come out of a
    JS object literal embedded in the page ("jsonConfig" on carlsgolfland,
    "var productJson=" on tgw.com). Those objects contain nested braces and
    brace characters inside strings are rare enough not to matter here, so
    this walks forward tracking depth rather than trying to regex a
    balanced match.

    Returns None when the marker is absent or the blob doesn't parse, so a
    caller falls back to listing-page data instead of failing the run.
    """
    marker_idx = html.find(marker)
    if marker_idx == -1:
        return None

    start = html.index("{", marker_idx)
    depth = 0
    for i in range(start, len(html)):
        if html[i] == "{":
            depth += 1
        elif html[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def parse_money(text: str | None) -> float | None:
    """"$1,299.99" -> 1299.99. None when there's nothing parseable."""
    if not text:
        return None
    try:
        return float(text.replace("$", "").replace(",", "").strip())
    except (AttributeError, ValueError):
        return None


def discount_pct(original: float | None, current: float | None) -> float | None:
    """None unless there's a real markdown to report - both sites sometimes
    populate a "was" price equal to (or below) the current one.
    """
    if not original or not current or original <= current:
        return None
    return round((original - current) / original * 100, 1)


def clean_text(source: str | Tag | None) -> str | None:
    """Flattens an HTML fragment to single-spaced plain text.

    Takes either raw markup (tgw.com hands back an HTML string inside its
    JSON) or an already-parsed element (carlsgolfland's description lives
    in the page itself, so re-parsing it would be wasted work).
    """
    if source is None:
        return None
    if isinstance(source, str):
        if not source.strip():
            return None
        source = BeautifulSoup(source, "html.parser")
    return re.sub(r"\s+", " ", source.get_text(" ", strip=True)).strip() or None


class BaseScraper:
    """One site, one brand, one club type.

    Subclasses set SITE (which also selects the site's entry in
    config.VARIANT_TARGETS) and implement run().
    """

    SITE: str = ""

    def __init__(
        self,
        brand: str,
        club_type: str,
        max_pages: int = 1,
        max_variant_lookups: int | None = USE_CONFIG_DEFAULT,
    ):
        self.brand = brand
        self.club_type = club_type
        self.query = build_query(brand, club_type)
        self.results: list[dict] = []
        self.rate_limiter = RateLimiter(RATE_LIMIT_SECONDS)
        self.variant_target = VARIANT_TARGETS.get(self.SITE, {}).get(club_type)
        # Names that count as this brand: the brand itself plus any
        # sub-brand it sells clubs under (Titleist -> Scotty Cameron).
        self.brand_terms = [
            term.lower() for term in (brand, *BRAND_ALIASES.get(brand, ()))
        ]
        # An unlisted club type matches anything, so a new type still
        # collects data before its keywords are tuned.
        self.club_type_keywords = CLUB_TYPE_KEYWORDS.get(club_type, [""])
        self.max_pages = max_pages
        # Per-instance rather than read off config at call time, so two
        # scrapes running with different caps can't interfere - which
        # matters as soon as this is driven by concurrent app requests
        # rather than one CLI process.
        self.max_variant_lookups = (
            MAX_VARIANT_LOOKUPS if max_variant_lookups is USE_CONFIG_DEFAULT
            else max_variant_lookups
        )

    def _get(self, url: str) -> requests.Response:
        self.rate_limiter.wait()
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp

    def _is_wanted(self, name: str) -> bool:
        """Both sites' search does loose keyword matching and happily
        returns other brands and accessories, so results get filtered down
        to actual right-handed men's clubs from the brand that was asked
        for.

        Applied during the listing parse so unwanted rows never reach the
        results or cost an extra product-page request.
        """
        name_lower = name.lower()
        if not any(term in name_lower for term in self.brand_terms):
            return False
        if not any(term in name_lower for term in self.club_type_keywords):
            return False
        if any(term in name_lower for term in MENS_ONLY_EXCLUDE_TERMS):
            return False
        return not any(term in name_lower for term in NON_CLUB_TERMS)

    def _capped(self, candidates: list[dict]) -> list[dict]:
        """Trims the list of listings worth an extra product-page request.

        Product pages are where descriptions, stock status and exact
        variant prices live, but they cost one request each - this is what
        keeps a test run from sitting there hammering a site for minutes.
        """
        if self.max_variant_lookups is None:
            return candidates
        return candidates[:self.max_variant_lookups]

    def run(self) -> list[dict]:
        raise NotImplementedError
