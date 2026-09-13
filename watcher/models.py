# Last edited: 2026-09-13 12:48 CDT
"""Posting model and the cross-source dedupe key."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

_PUNCT_RE = re.compile(r"[^a-z0-9 ]+")
_WS_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace. Used for dedupe keys."""
    lowered = (text or "").lower().replace("&", " and ")
    stripped = _PUNCT_RE.sub(" ", lowered)
    return _WS_RE.sub(" ", stripped).strip()


@dataclass
class Posting:
    source: str
    source_id: str
    company: str
    title: str
    url: str
    terms: list[str] = field(default_factory=list)
    category: str | None = None
    degrees: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    sponsorship: str | None = None

    @property
    def key(self) -> str:
        """Same company + same title in two sources is one posting."""
        company = normalize_text(self.company)
        title = normalize_text(self.title)
        if not company:
            return f"url|{self.url}"
        return f"{company}|{title}"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["key"] = self.key
        return data

    @classmethod
    def from_dict(cls, data: dict) -> Posting:
        fields = {k: v for k, v in data.items() if k != "key"}
        return cls(**fields)
