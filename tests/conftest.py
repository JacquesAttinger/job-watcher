# Last edited: 2026-09-15 16:35 CDT
"""Shared fixtures: sample feeds and an isolated state directory."""

from __future__ import annotations

import urllib.error
import urllib.request
from email.message import Message
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


class FakeClock:
    """Stand-in for the time module: sleep() advances monotonic() without waiting."""

    def __init__(self) -> None:
        self.now = 100.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def clock(monkeypatch) -> FakeClock:
    """Make notify's pacing and retry sleeps instant, and reset the pacing state."""
    fake = FakeClock()
    monkeypatch.setattr(notify, "time", fake)
    monkeypatch.setattr(notify, "_last_post", 0.0)
    return fake


class FakeResponse:
    def __init__(self, status: int = 200) -> None:
        self.status = status

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc_info) -> None:
        return None


def http_error(code: int, retry_after: str | None = None) -> urllib.error.HTTPError:
    headers = Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError(notify.NTFY_ENDPOINT, code, "scripted", headers, None)


class FakeUrlopen:
    """Script urlopen outcomes for ntfy POSTs; every other URL succeeds.

    ``script`` holds HTTPError instances or None (success), consumed in order.
    Once it is empty, further ntfy POSTs succeed.
    """

    def __init__(self) -> None:
        self.script: list[urllib.error.HTTPError | None] = []
        self.calls: list[urllib.request.Request] = []

    def __call__(self, request: urllib.request.Request, timeout=None) -> FakeResponse:
        self.calls.append(request)
        if request.full_url == notify.NTFY_ENDPOINT and self.script:
            outcome = self.script.pop(0)
            if outcome is not None:
                raise outcome
        return FakeResponse()

    def ntfy_calls(self) -> list[urllib.request.Request]:
        return [r for r in self.calls if r.full_url == notify.NTFY_ENDPOINT]


@pytest.fixture
def fake_urlopen(monkeypatch, clock) -> FakeUrlopen:
    fake = FakeUrlopen()
    monkeypatch.setattr(notify.urllib.request, "urlopen", fake)
    return fake
