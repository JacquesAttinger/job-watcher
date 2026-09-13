# Last edited: 2026-09-13 12:48 CDT
"""Read and write the small JSON state files under state/."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / "state"
SEEN_PATH = STATE_DIR / "seen.json"
ERRORS_PATH = STATE_DIR / "errors.json"
PENDING_PATH = STATE_DIR / "pending.json"
DECISIONS_PATH = STATE_DIR / "decisions.json"


def _read_json(path: Path, default):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def seen_exists() -> bool:
    return SEEN_PATH.exists()


def load_seen() -> set[str]:
    return set(_read_json(SEEN_PATH, {"keys": []}).get("keys", []))


def save_seen(keys: set[str]) -> None:
    _write_json(SEEN_PATH, {"keys": sorted(keys)})


def load_errors() -> dict[str, str]:
    return _read_json(ERRORS_PATH, {})


def save_errors(errors: dict[str, str]) -> None:
    _write_json(ERRORS_PATH, errors)


def write_pending(payload: dict) -> None:
    _write_json(PENDING_PATH, payload)


def read_pending() -> dict:
    if not PENDING_PATH.exists():
        raise FileNotFoundError("state/pending.json missing: run `scan` first")
    return _read_json(PENDING_PATH, {})


def read_decisions() -> dict[str, dict]:
    return _read_json(DECISIONS_PATH, {})


def clear_transient() -> None:
    for path in (PENDING_PATH, DECISIONS_PATH):
        if path.exists():
            path.unlink()
