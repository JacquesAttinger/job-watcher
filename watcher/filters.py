# Last edited: 2026-09-13 12:48 CDT
"""Deterministic hard exclusions. Anything that survives goes to Claude for judgment.

The rules are deliberately loose: it is cheap for Claude to drop a borderline
posting, and expensive for Jacques to miss a real one.
"""

from __future__ import annotations

import re

from .models import Posting

ALLOWED_TERMS = {"summer 2027", "fall 2026", "winter 2027"}

EXCLUDED_CATEGORIES = {
    "hardware",
    "hardware engineering",
    "quant",
    "product",
    "product management",
    "other",
}

ELIGIBLE_DEGREES = {"bachelor's", "bachelors", "associate's", "associates"}

# Suffix match, lowercase. "Toronto, ON, Canada" -> non-US. "London, UK" -> non-US.
NON_US_COUNTRIES = (
    "canada",
    "uk",
    "united kingdom",
    "england",
    "india",
    "germany",
    "france",
    "ireland",
    "singapore",
    "australia",
    "japan",
    "china",
    "netherlands",
    "israel",
    "switzerland",
    "spain",
    "poland",
    "brazil",
    "mexico",
    "italy",
    "sweden",
    "denmark",
    "taiwan",
    "korea",
    "south korea",
    "hong kong",
)

TITLE_EXCLUDE_RE = re.compile(
    r"\b(phd|ph\.d\.?|mba|analyst|sales|marketing|recruit\w*|mechanical|electrical|civil"
    r"|graduate|grad|masters?|communications|sustainability|business (?:analytics|intelligence))\b",
    re.IGNORECASE,
)


def is_non_us(location: str) -> bool:
    text = location.strip().lower().rstrip(".")
    if not text:
        return False
    return any(text == c or text.endswith(", " + c) or text.endswith(" " + c) for c in NON_US_COUNTRIES)


def exclusion_reason(posting: Posting) -> str | None:
    """Return why a posting is dropped, or None when Claude should see it."""
    terms = {t.strip().lower() for t in posting.terms}
    if terms and not (terms & ALLOWED_TERMS):
        return f"term not wanted: {sorted(terms)}"

    degrees = {d.strip().lower() for d in posting.degrees}
    if degrees and not (degrees & ELIGIBLE_DEGREES):
        return f"not bachelor's-eligible: {sorted(degrees)}"

    category = (posting.category or "").strip().lower()
    if category in EXCLUDED_CATEGORIES:
        return f"category excluded: {posting.category}"

    if posting.locations and all(is_non_us(loc) for loc in posting.locations):
        return f"all locations outside the US: {posting.locations}"

    title_hit = TITLE_EXCLUDE_RE.search(posting.title)
    if title_hit:
        return f"title matched exclusion: {title_hit.group(0)!r}"

    return None
