# Last edited: 2026-09-13 12:48 CDT
"""Shared fixtures: sample feeds and an isolated state directory."""

from __future__ import annotations

from pathlib import Path

import pytest

from watcher import notify, report, sources, state

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def feed_text() -> dict[str, str]:
    return {
        sources.SIMPLIFY_URL: (FIXTURES / "simplify_sample.json").read_text(),
        sources.ZSHAH_URL: (FIXTURES / "zshah_sample.json").read_text(),
        sources.JOBRIGHT_URL: (FIXTURES / "jobright_sample.md").read_text(),
    }


@pytest.fixture
def fake_fetch(feed_text, monkeypatch):
    """Route every fetch to the fixtures instead of the network."""

    def fetch(url: str) -> str:
        return feed_text[url]

    monkeypatch.setattr(sources, "fetch_text", fetch)
    return fetch


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    """Point every state/report path at a temp dir so tests never touch the repo."""
    monkeypatch.setattr(state, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(state, "SEEN_PATH", tmp_path / "state" / "seen.json")
    monkeypatch.setattr(state, "ERRORS_PATH", tmp_path / "state" / "errors.json")
    monkeypatch.setattr(state, "PENDING_PATH", tmp_path / "state" / "pending.json")
    monkeypatch.setattr(state, "DECISIONS_PATH", tmp_path / "state" / "decisions.json")
    monkeypatch.setattr(report, "ALERTS_CSV", tmp_path / "alerts.csv")
    monkeypatch.setattr(report, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setenv("NTFY_TOPIC", "test-topic")
    monkeypatch.delenv("HC_PING_URL", raising=False)
    monkeypatch.setattr(notify, "ENV_PATH", tmp_path / ".env")
    return tmp_path


@pytest.fixture
def sent(monkeypatch) -> list[dict]:
    """Capture ntfy publishes instead of sending them."""
    calls: list[dict] = []

    def publish(title, message, click=None, priority=3, tags=None, dry_run=False):
        calls.append({"title": title, "message": message, "click": click, "priority": priority})
        return True

    monkeypatch.setattr(notify, "publish", publish)
    return calls
