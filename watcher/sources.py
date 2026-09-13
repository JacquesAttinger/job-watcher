# Last edited: 2026-09-13 12:48 CDT
"""Fetch and normalize the three internship lists. One parser per source.

All three feeds are plain files on raw.githubusercontent.com, which is on the
cloud environment's default allowlist. No HTML scraping.
"""

from __future__ import annotations

import json
import re
import urllib.request
from collections.abc import Callable

from .models import Posting

SIMPLIFY_URL = (
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json"
)
ZSHAH_URL = (
    "https://raw.githubusercontent.com/zshah101/"
    "Automated-List-Of-Summer-2027-and-Fall-2026-Tech-Internships/main/docs/api/jobs.json"
)
JOBRIGHT_URL = (
    "https://raw.githubusercontent.com/jobright-ai/2026-Software-Engineer-Internship/master/README.md"
)

USER_AGENT = "job-watcher/1.0 (+https://github.com/JacquesAttinger/job-watcher)"
UNSTATED_TERMS = {"", "n/a", "not stated", "none", "null"}


def fetch_text(url: str, timeout: int = 90) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def _clean_terms(values: list[str] | None) -> list[str]:
    return [v for v in (values or []) if v and v.strip().lower() not in UNSTATED_TERMS]


def parse_simplify(text: str) -> list[Posting]:
    """Only active + visible rows become postings.

    Inactive rows are left out on purpose: when a listing flips back to active
    it is new to us again and should alert.
    """
    rows = json.loads(text)
    postings = []
    for row in rows:
        if not (row.get("active") and row.get("is_visible")):
            continue
        postings.append(
            Posting(
                source="simplify",
                source_id=str(row.get("id", "")),
                company=row.get("company_name", "") or "",
                title=row.get("title", "") or "",
                url=row.get("url", "") or "",
                terms=_clean_terms(row.get("terms")),
                category=row.get("category") or None,
                degrees=list(row.get("degrees") or []),
                locations=[loc for loc in (row.get("locations") or []) if loc],
                sponsorship=row.get("sponsorship") or None,
            )
        )
    return postings


def parse_zshah(text: str) -> list[Posting]:
    payload = json.loads(text)
    postings = []
    for row in payload.get("jobs", []):
        location = row.get("location") or ""
        postings.append(
            Posting(
                source="zshah",
                source_id=str(row.get("id", "")),
                company=row.get("company", "") or "",
                title=row.get("title", "") or "",
                url=row.get("url", "") or "",
                terms=_clean_terms(row.get("seasons") or [row.get("season") or ""]),
                category=row.get("category") or None,
                degrees=[],
                locations=[location] if location else [],
                sponsorship=row.get("sponsorship") or None,
            )
        )
    return postings


# | **[Company](url)** | **[Title](url)** | Location | Work Model | Date |
_JOBRIGHT_ROW_RE = re.compile(
    r"^\|\s*\*\*\[(?P<company>[^\]]+)\]\([^)]*\)\*\*\s*\|"
    r"\s*\*\*\[(?P<title>[^\]]+)\]\((?P<url>[^)]+)\)\*\*\s*\|"
    r"\s*(?P<location>[^|]*)\|\s*(?P<model>[^|]*)\|\s*(?P<date>[^|]*)\|",
    re.MULTILINE,
)
_JOBRIGHT_ID_RE = re.compile(r"/jobs/info/([0-9a-f]+)")


def parse_jobright(text: str) -> list[Posting]:
    postings = []
    for match in _JOBRIGHT_ROW_RE.finditer(text):
        url = match.group("url").strip()
        id_match = _JOBRIGHT_ID_RE.search(url)
        location = match.group("location").strip()
        postings.append(
            Posting(
                source="jobright",
                source_id=id_match.group(1) if id_match else url,
                company=match.group("company").strip(),
                title=match.group("title").strip(),
                url=url,
                terms=[],
                category=None,
                degrees=[],
                locations=[location] if location else [],
                sponsorship=None,
            )
        )
    return postings


SOURCES: dict[str, tuple[str, Callable[[str], list[Posting]]]] = {
    "simplify": (SIMPLIFY_URL, parse_simplify),
    "zshah": (ZSHAH_URL, parse_zshah),
    "jobright": (JOBRIGHT_URL, parse_jobright),
}


def fetch_all(
    fetch: Callable[[str], str] | None = None,
) -> tuple[list[Posting], dict[str, str]]:
    """Return every posting from every source, plus {source: error} for failures.

    A failing source never blocks the others. An empty parse also counts as a
    failure, because a format change would otherwise look like "no listings".
    """
    fetch = fetch or fetch_text
    postings: list[Posting] = []
    errors: dict[str, str] = {}
    for name, (url, parser) in SOURCES.items():
        try:
            parsed = parser(fetch(url))
        except Exception as exc:  # noqa: BLE001 - any failure is reported, not raised
            errors[name] = f"{type(exc).__name__}: {exc}"[:200]
            continue
        if not parsed:
            errors[name] = "parsed 0 postings (format change?)"
            continue
        postings.extend(parsed)
    return postings, errors
