# Last edited: 2026-09-13 12:48 CDT
import json

import pytest

from watcher import cli, state


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
    assert sent == []


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
