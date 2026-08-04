"""Shared plumbing for the per-site club scrapers.

Every site needs the same things - a rate-limited GET with a browser
User-Agent, a way to pull an embedded JSON blob out of a <script> tag, the
same money/discount arithmetic, and the same "is this actually a men's
club from the brand we asked for?" filter. Keeping one copy here means a
new site's scraper is just its own parsing logic, and a fix to the shared
parts lands everywhere at once.

Subclasses set SITE, implement run(), and return a list of dicts whose
keys match database.COLUMNS (minus run_timestamp/extracted_date, which
test_scrapers.py stamps on).
"""

import json
import re

import requests
from bs4 import BeautifulSoup, Tag

from config import (
    MENS_ONLY_EXCLUDE_TERMS,
    RATE_LIMIT_SECONDS,
    VARIANT_TARGETS,
    build_query,
)
from rate_limiter import RateLimiter

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ClubPriceTracker/0.1)"}
REQUEST_TIMEOUT = 15


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

    def __init__(self, brand: str, club_type: str):
        self.brand = brand
        self.club_type = club_type
        self.query = build_query(brand, club_type)
        self.results: list[dict] = []
        self.rate_limiter = RateLimiter(RATE_LIMIT_SECONDS)
        self.variant_target = VARIANT_TARGETS.get(self.SITE, {}).get(club_type)

    def _get(self, url: str) -> requests.Response:
        self.rate_limiter.wait()
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp

    def _is_wanted(self, name: str) -> bool:
        """Both sites' search does loose keyword matching and happily
        returns other brands, so results get filtered down to actual
        right-handed men's clubs from the brand that was asked for.

        Applied during the listing parse so unwanted rows never reach the
        results or cost an extra product-page request.
        """
        name_lower = name.lower()
        if self.brand.lower() not in name_lower:
            return False
        return not any(term in name_lower for term in MENS_ONLY_EXCLUDE_TERMS)

    def run(self) -> list[dict]:
        raise NotImplementedError
