# Last edited: 2026-09-13 12:48 CDT
"""Durable records: alerts.csv and one markdown summary per run."""

from __future__ import annotations

import csv
from pathlib import Path

from .state import REPO_ROOT

ALERTS_CSV = REPO_ROOT / "alerts.csv"
RUNS_DIR = REPO_ROOT / "runs"
CSV_COLUMNS = ["stamp", "source", "company", "title", "terms", "location", "sponsorship", "url"]


def append_alerts(stamp: str, postings: list[dict]) -> None:
    is_new = not ALERTS_CSV.exists()
    with ALERTS_CSV.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        if is_new:
            writer.writeheader()
        for posting in postings:
            writer.writerow(
                {
                    "stamp": stamp,
                    "source": posting["source"],
                    "company": posting["company"],
                    "title": posting["title"],
                    "terms": "; ".join(posting.get("terms") or []),
                    "location": "; ".join(posting.get("locations") or []),
                    "sponsorship": posting.get("sponsorship") or "",
                    "url": posting["url"],
                }
            )


def _row(posting: dict, decision: dict | None, alerted: bool) -> str:
    verdict = "ALERTED" if alerted else ("dropped by Claude" if decision else "no decision")
    terms = ", ".join(posting.get("terms") or []) or "term unstated"
    location = "; ".join(posting.get("locations") or []) or "location unstated"
    return (
        f"- **{posting['company']} — {posting['title']}** · {terms} · {location} · "
        f"{posting['source']} · {verdict}\n  {posting['url']}"
    )


def write_run_summary(
    stamp: str,
    pending: dict,
    decisions: dict[str, dict],
    alerted_keys: list[str],
    error_pushes: list[str],
) -> Path:
    RUNS_DIR.mkdir(exist_ok=True)
    path = RUNS_DIR / f"{stamp}.md"
    candidates = pending.get("candidates", [])
    lines = [
        f"<!-- Last edited: {stamp} -->",
        f"# Run {stamp}",
        "",
        f"- new keys observed: {len(pending.get('new_keys', []))}",
        f"- candidates after hard exclusions: {len(candidates)}",
        f"- alerted: {len(alerted_keys)}",
        f"- source errors: {pending.get('source_errors') or 'none'}",
        f"- error pushes sent: {error_pushes or 'none'}",
        "",
        "## Candidates",
        "",
    ]
    if not candidates:
        lines.append("_none_")
    for posting in candidates:
        key = posting["key"]
        lines.append(_row(posting, decisions.get(key), key in alerted_keys))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
