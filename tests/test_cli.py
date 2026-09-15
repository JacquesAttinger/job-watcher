# Last edited: 2026-09-15 16:40 CDT
import json
import urllib.error

import pytest

from tests.conftest import http_error
from watcher import cli, notify, state


def _args(**overrides):
    base = {"dry_run": False, "no_git": True}
    base.update(overrides)
    return type("Args", (), base)()


def test_bootstrap_seeds_seen_and_sends_one_armed_push(fake_fetch, isolated_state, sent):
    assert cli.cmd_seed(_args()) == 0
    seen = state.load_seen()
    assert len(seen) > 0
    assert len(sent) == 1 and sent[0]["title"] == "job-watcher armed"
    assert not state.PENDING_PATH.exists()


def test_second_run_finds_nothing_new(fake_fetch, isolated_state, sent):
    cli.cmd_seed(_args())
    sent.clear()
    cli.cmd_scan(_args())
    pending = state.read_pending()
    assert pending["new_keys"] == [] and pending["candidates"] == []
    cli.cmd_send(_args())
    assert len(sent) == 1 and sent[0]["title"] == "job-watcher: nothing new"


def test_new_posting_flows_to_candidates_then_alert(fake_fetch, isolated_state, sent):
    cli.cmd_seed(_args())
    sent.clear()
    # Forget one key so it looks new again.
    seen = state.load_seen()
    salesforce_key = next(k for k in seen if k.startswith("salesforce|"))
    state.save_seen(seen - {salesforce_key})

    cli.cmd_scan(_args())
    pending = state.read_pending()
    assert [c["key"] for c in pending["candidates"]] == [salesforce_key]

    state.DECISIONS_PATH.write_text(
        json.dumps({salesforce_key: {"alert": True, "title": "Salesforce — SWE Intern"}})
    )
    cli.cmd_send(_args())
    assert len(sent) == 1
    assert sent[0]["title"] == "Salesforce — SWE Intern"
    assert sent[0]["click"].startswith("http")
    assert salesforce_key in state.load_seen()
    csv_text = (isolated_state / "alerts.csv").read_text()
    assert "Salesforce" in csv_text
    assert list((isolated_state / "runs").glob("*.md"))


def test_send_refuses_when_candidates_have_no_decisions(fake_fetch, isolated_state, sent):
    cli.cmd_seed(_args())
    seen = state.load_seen()
    key = next(k for k in seen if k.startswith("salesforce|"))
    state.save_seen(seen - {key})
    cli.cmd_scan(_args())
    with pytest.raises(RuntimeError, match="decisions.json"):
        cli.cmd_send(_args())
    assert key not in state.load_seen()  # nothing marked seen without a verdict


def test_alert_cap_adds_overflow_push(isolated_state, sent, monkeypatch):
    candidates = [
        {
            "key": f"k{i}",
            "source": "simplify",
            "company": f"Co{i}",
            "title": "SWE Intern",
            "url": f"https://x/{i}",
            "terms": ["Summer 2027"],
            "locations": ["NYC"],
            "sponsorship": None,
            "category": "Software",
            "degrees": [],
        }
        for i in range(10)
    ]
    state.write_pending(
        {
            "stamp": "2026-09-13-1300",
            "bootstrap": False,
            "total_listings": 10,
            "new_keys": [c["key"] for c in candidates],
            "excluded_count": 0,
            "candidates": candidates,
            "source_errors": {},
        }
    )
    state.DECISIONS_PATH.write_text(json.dumps({c["key"]: {"alert": True} for c in candidates}))
    cli.cmd_send(_args())
    assert len(sent) == cli.MAX_PUSHES + 1
    assert sent[-1]["title"].startswith("and 2 more")


def test_source_error_pushes_once_per_day(isolated_state, sent):
    pending = {
        "stamp": "2026-09-13-1300",
        "bootstrap": False,
        "total_listings": 0,
        "new_keys": [],
        "excluded_count": 0,
        "candidates": [],
        "source_errors": {"zshah": "HTTPError: 404"},
    }
    state.write_pending(pending)
    cli.cmd_send(_args())
    state.write_pending(pending)
    cli.cmd_send(_args())
    assert len(sent) == 1 and sent[0]["priority"] == 4


def test_send_aborts_and_fail_pings_when_ntfy_stays_rate_limited(
    fake_fetch, isolated_state, fake_urlopen, monkeypatch
):
    monkeypatch.setenv("HC_PING_URL", "https://hc-ping.com/test-uuid")
    cli.cmd_seed(_args())  # the armed push goes through the (unscripted, succeeding) fake
    seen_before = state.load_seen()
    key = next(k for k in seen_before if k.startswith("salesforce|"))
    state.save_seen(seen_before - {key})
    cli.cmd_scan(_args())
    state.DECISIONS_PATH.write_text(json.dumps({key: {"alert": True}}))

    fake_urlopen.calls.clear()
    fake_urlopen.script = [http_error(429)] * notify.RETRY_ATTEMPTS
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        cli.cmd_send(_args())

    assert excinfo.value.code == 429
    assert len(fake_urlopen.ntfy_calls()) == notify.RETRY_ATTEMPTS
    assert [r.full_url for r in fake_urlopen.calls if "hc-ping" in r.full_url] == [
        "https://hc-ping.com/test-uuid/fail"
    ]
    assert key not in state.load_seen()  # nothing marked seen: the next run retries the alert
    assert state.PENDING_PATH.exists()


def test_send_recovers_when_a_429_clears_on_retry(fake_fetch, isolated_state, fake_urlopen):
    cli.cmd_seed(_args())
    seen_before = state.load_seen()
    key = next(k for k in seen_before if k.startswith("salesforce|"))
    state.save_seen(seen_before - {key})
    cli.cmd_scan(_args())
    state.DECISIONS_PATH.write_text(json.dumps({key: {"alert": True}}))

    fake_urlopen.calls.clear()
    fake_urlopen.script = [http_error(429), None]
    assert cli.cmd_send(_args()) == 0
    assert len(fake_urlopen.ntfy_calls()) == 2
    assert key in state.load_seen()
