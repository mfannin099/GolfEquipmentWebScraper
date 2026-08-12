"""Shared plumbing for the per-site club scrapers.

Subclasses set SITE, implement run(), and return dicts whose keys match
database.COLUMNS minus run_timestamp/extracted_date, which
run_final_scrape.save() stamps on.
"""

import json
import re

import requests
from bs4 import BeautifulSoup, Tag

from .config import (
    BRAND_ALIASES,
    CLUB_TYPE_KEYWORDS,
    MAX_VARIANT_LOOKUPS,
    MENS_ONLY_EXCLUDE_TERMS,
    NON_CLUB_TERMS,
    RATE_LIMIT_SECONDS,
    VARIANT_TARGETS,
    build_query,
)
from .rate_limiter import RateLimiter

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ClubPriceTracker/0.1)"}
REQUEST_TIMEOUT = 15

# Sentinel: None is already meaningful for max_variant_lookups (no cap),
# so a separate value is needed for "not specified".
USE_CONFIG_DEFAULT = object()


def extract_json_blob(html: str, marker: str) -> dict | None:
    """Pulls the first JSON object appearing after `marker`.

    Neither site exposes an API, so variant/price data comes from a JS
    object literal embedded in the page. Walks forward tracking brace
    depth; braces inside strings are rare enough not to matter here.

    None when the marker is absent or the blob doesn't parse, so callers
    fall back to listing-page data rather than failing the run.
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
    """None unless there's a real markdown: both sites sometimes set a
    "was" price equal to or below the current one.
    """
    if not original or not current or original <= current:
        return None
    return round((original - current) / original * 100, 1)


def clean_text(source: str | Tag | None) -> str | None:
    """Flattens an HTML fragment to single-spaced plain text.

    Takes raw markup (tgw.com's JSON holds an HTML string) or an
    already-parsed element (carlsgolfland's lives in the page).
    """
    if source is None:
        return None
    if isinstance(source, str):
        if not source.strip():
            return None
        source = BeautifulSoup(source, "html.parser")
    return re.sub(r"\s+", " ", source.get_text(" ", strip=True)).strip() or None


class BaseScraper:
    """One site, one brand, one club type. SITE also selects the site's
    entry in config.VARIANT_TARGETS.
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
        # The brand plus any sub-brand it sells clubs under.
        self.brand_terms = [
            term.lower() for term in (brand, *BRAND_ALIASES.get(brand, ()))
        ]
        # An unlisted club type matches anything.
        self.club_type_keywords = CLUB_TYPE_KEYWORDS.get(club_type, [""])
        self.max_pages = max_pages
        # Per-instance, so concurrent scrapes with different caps can't
        # interfere.
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
        """Filters loose search results down to right-handed men's clubs
        of the requested brand and type.

        Applied during the listing parse, so rejects never reach the
        results or cost a product-page request.
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
        """Trims the listings worth a product-page request - one
        rate-limited request each. See config.MAX_VARIANT_LOOKUPS.
        """
        if self.max_variant_lookups is None:
            return candidates
        return candidates[:self.max_variant_lookups]

    def run(self) -> list[dict]:
        raise NotImplementedError
