# Last edited: 2026-09-15 16:35 CDT
"""notify.publish: pacing between ntfy POSTs and retry on HTTP 429."""

import urllib.error

import pytest

from tests.conftest import http_error
from watcher import notify


@pytest.fixture(autouse=True)
def topic(monkeypatch, tmp_path):
    monkeypatch.setenv("NTFY_TOPIC", "test-topic")
    monkeypatch.setattr(notify, "ENV_PATH", tmp_path / ".env")


def test_429_then_success_retries_once(fake_urlopen, clock):
    fake_urlopen.script = [http_error(429), None]
    assert notify.publish("t", "m") is True
    assert len(fake_urlopen.ntfy_calls()) == 2
    assert clock.sleeps == [notify.RETRY_DEFAULT_WAIT]


def test_429_honours_retry_after_header_with_a_cap(fake_urlopen, clock):
    fake_urlopen.script = [http_error(429, retry_after="3"), None]
    notify.publish("t", "m")
    assert clock.sleeps == [3.0]

    clock.sleeps.clear()
    clock.now += notify.PUBLISH_INTERVAL  # so no pacing sleep muddies the next assertion
    fake_urlopen.script = [http_error(429, retry_after="600"), None]
    notify.publish("t", "m")
    assert clock.sleeps == [notify.RETRY_MAX_WAIT]


def test_429_on_every_attempt_raises_after_retry_limit(fake_urlopen, clock):
    fake_urlopen.script = [http_error(429)] * notify.RETRY_ATTEMPTS
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        notify.publish("t", "m")
    assert excinfo.value.code == 429
    assert len(fake_urlopen.ntfy_calls()) == notify.RETRY_ATTEMPTS
    assert clock.sleeps == [notify.RETRY_DEFAULT_WAIT] * (notify.RETRY_ATTEMPTS - 1)


def test_non_429_error_is_not_retried(fake_urlopen, clock):
    fake_urlopen.script = [http_error(500)]
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        notify.publish("t", "m")
    assert excinfo.value.code == 500
    assert len(fake_urlopen.ntfy_calls()) == 1
    assert clock.sleeps == []


def test_consecutive_posts_are_spaced_out(fake_urlopen, clock):
    notify.publish("first", "m")
    assert clock.sleeps == []  # nothing to wait for on the first POST
    notify.publish("second", "m")
    assert clock.sleeps == [notify.PUBLISH_INTERVAL]
    clock.now += notify.PUBLISH_INTERVAL * 5  # enough real time has passed
    notify.publish("third", "m")
    assert clock.sleeps == [notify.PUBLISH_INTERVAL]


def test_dry_run_never_touches_the_network_or_the_clock(fake_urlopen, clock, capsys):
    assert notify.publish("t", "m", dry_run=True) is True
    assert fake_urlopen.calls == []
    assert clock.sleeps == []
    assert "[dry-run] ntfy" in capsys.readouterr().out
