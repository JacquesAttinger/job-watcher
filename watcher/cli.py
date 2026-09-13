# Last edited: 2026-09-13 12:48 CDT
"""Command line entry point: `python -m watcher.cli {scan|send|seed|test}`.

scan  fetch feeds, diff against state/seen.json, apply hard exclusions,
      write state/pending.json for Claude to review.
send  read state/pending.json + state/decisions.json, push ntfy alerts,
      append alerts.csv, write runs/<stamp>.md, update seen.json, commit, ping.
seed  scan + send on a repo with no seen.json yet (bootstrap only).
test  push one test message and ping healthchecks. Touches no state.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import UTC, datetime, timedelta

from . import notify, report, state
from .filters import exclusion_reason
from .sources import fetch_all

REPO_WEB = "https://github.com/JacquesAttinger/job-watcher"
MAX_PUSHES = 8
ERROR_PUSH_INTERVAL = timedelta(hours=24)


def _now() -> datetime:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("America/Chicago"))
    except Exception:  # noqa: BLE001 - tzdata missing: fall back to UTC
        return datetime.now(UTC)


def now_stamp() -> str:
    return _now().strftime("%Y-%m-%d-%H%M")


# ---------------------------------------------------------------- scan


def cmd_scan(args: argparse.Namespace) -> int:
    postings, errors = fetch_all()
    bootstrap = not state.seen_exists()
    seen = state.load_seen()

    fresh: dict[str, object] = {}
    for posting in postings:
        if posting.key in seen or posting.key in fresh:
            continue
        fresh[posting.key] = posting

    candidates: list[dict] = []
    excluded = 0
    if not bootstrap:
        for posting in fresh.values():
            if exclusion_reason(posting):
                excluded += 1
            else:
                candidates.append(posting.to_dict())

    pending = {
        "stamp": now_stamp(),
        "bootstrap": bootstrap,
        "total_listings": len(postings),
        "new_keys": sorted(fresh),
        "excluded_count": excluded,
        "candidates": candidates,
        "source_errors": errors,
    }
    state.write_pending(pending)
    _print_scan(pending)
    return 0


def _print_scan(pending: dict) -> None:
    print(f"stamp={pending['stamp']} bootstrap={pending['bootstrap']}")
    print(
        f"listings={pending['total_listings']} new={len(pending['new_keys'])} "
        f"excluded={pending['excluded_count']} candidates={len(pending['candidates'])}"
    )
    if pending["source_errors"]:
        print(f"source errors: {pending['source_errors']}")
    for i, c in enumerate(pending["candidates"], 1):
        terms = ", ".join(c["terms"]) or "term unstated"
        loc = "; ".join(c["locations"]) or "location unstated"
        cat = c["category"] or "category unstated"
        print(f"{i:>3}. [{c['source']}] {c['company']} — {c['title']} | {terms} | {loc} | {cat}")
        print(f"     key={c['key']}")


# ---------------------------------------------------------------- send


def cmd_send(args: argparse.Namespace) -> int:
    try:
        return _send(args)
    except Exception:
        try:
            notify.ping_healthcheck("fail", dry_run=args.dry_run)
        except Exception as ping_exc:  # noqa: BLE001
            print(f"healthchecks fail-ping also failed: {ping_exc}", file=sys.stderr)
        raise


def _send(args: argparse.Namespace) -> int:
    pending = state.read_pending()
    stamp = pending["stamp"]
    dry = args.dry_run
    decisions: dict[str, dict] = {}
    alerted: list[str] = []

    if pending["bootstrap"]:
        notify.publish(
            "job-watcher armed",
            f"tracking {pending['total_listings']} listings across 3 sources",
            click=REPO_WEB,
            tags=["white_check_mark"],
            dry_run=dry,
        )
    else:
        decisions = state.read_decisions()
        if pending["candidates"] and not decisions:
            raise RuntimeError(
                "candidates exist but state/decisions.json is missing or empty; "
                "review pending.json first so nothing gets marked seen without a verdict"
            )
        alerted = _push_alerts(stamp, pending, decisions, dry)

    error_pushes = _push_source_errors(pending, dry)
    if dry:
        print(f"[dry-run] would mark {len(pending['new_keys'])} keys seen, write runs/{stamp}.md")
    else:
        if alerted:
            chosen = [c for c in pending["candidates"] if c["key"] in alerted]
            report.append_alerts(stamp, chosen)
        summary = report.write_run_summary(stamp, pending, decisions, alerted, error_pushes)
        print(f"summary: {summary}")
        state.save_seen(state.load_seen() | set(pending["new_keys"]))
        state.clear_transient()
        if not args.no_git:
            _git_commit_push(stamp, len(alerted))
    notify.ping_healthcheck(dry_run=dry)
    print(f"done: {len(alerted)} alerts, {len(pending['new_keys'])} keys marked seen")
    return 0


def _default_body(c: dict) -> str:
    parts = [
        ", ".join(c.get("terms") or []) or "term unstated",
        "; ".join(c.get("locations") or []) or "location unstated",
        c["source"],
    ]
    if c.get("sponsorship"):
        parts.append(f"sponsorship: {c['sponsorship']}")
    return " · ".join(parts)


def _push_alerts(stamp: str, pending: dict, decisions: dict, dry: bool) -> list[str]:
    chosen = [c for c in pending["candidates"] if decisions.get(c["key"], {}).get("alert")]
    for c in chosen[:MAX_PUSHES]:
        decision = decisions[c["key"]]
        title = (decision.get("title") or f"{c['company']} — {c['title']}").strip()
        body = (decision.get("body") or _default_body(c)).strip()
        notify.publish(title, body, click=c["url"], dry_run=dry)
    overflow = len(chosen) - MAX_PUSHES
    if overflow > 0:
        notify.publish(
            f"and {overflow} more new postings",
            f"run {stamp}: {len(chosen)} matches total. Tap to open the full list.",
            click=f"{REPO_WEB}/blob/main/runs/{stamp}.md",
            tags=["page_facing_up"],
            dry_run=dry,
        )
    return [c["key"] for c in chosen]


def _push_source_errors(pending: dict, dry: bool) -> list[str]:
    errors: dict[str, str] = pending.get("source_errors") or {}
    if not errors:
        return []
    last_pushed = state.load_errors()
    now = _now()
    pushed: list[str] = []
    for source, message in errors.items():
        previous = last_pushed.get(source)
        if previous and now - datetime.fromisoformat(previous) < ERROR_PUSH_INTERVAL:
            continue
        notify.publish(
            f"job-watcher: {source} failed",
            message,
            click=f"{REPO_WEB}/tree/main/runs",
            priority=4,
            tags=["warning"],
            dry_run=dry,
        )
        last_pushed[source] = now.isoformat()
        pushed.append(source)
    if pushed and not dry:
        state.save_errors(last_pushed)
    return pushed


def _git(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *argv], cwd=state.REPO_ROOT, text=True, capture_output=True)


def _git_commit_push(stamp: str, alert_count: int) -> None:
    paths = ["state", "runs"]
    if report.ALERTS_CSV.exists():
        paths.append("alerts.csv")
    _git("add", "-A", "--", *paths)
    commit = _git("commit", "-m", f"watch: {stamp}, {alert_count} alerts")
    if commit.returncode != 0:
        raise RuntimeError(f"git commit failed: {commit.stderr.strip() or commit.stdout.strip()}")
    for attempt in (1, 2):
        push = _git("push", "origin", "HEAD:main")
        if push.returncode == 0:
            return
        print(f"git push attempt {attempt} failed: {push.stderr.strip()}", file=sys.stderr)
        _git("pull", "--rebase", "origin", "main")
    raise RuntimeError("git push failed twice; state is committed locally but not on main")


# ---------------------------------------------------------------- test / seed


def cmd_test(args: argparse.Namespace) -> int:
    notify.publish(
        "job-watcher test OK",
        f"manual test at {now_stamp()} Central. Tap to open the repo.",
        click=REPO_WEB,
        tags=["white_check_mark"],
        dry_run=args.dry_run,
    )
    notify.ping_healthcheck(dry_run=args.dry_run)
    print("test message sent")
    return 0


def cmd_seed(args: argparse.Namespace) -> int:
    if state.seen_exists():
        print("state/seen.json already exists; seed is only for a fresh repo", file=sys.stderr)
        return 2
    cmd_scan(args)
    return cmd_send(args)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="watcher", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, handler in (("scan", cmd_scan), ("send", cmd_send), ("seed", cmd_seed), ("test", cmd_test)):
        p = sub.add_parser(name)
        p.add_argument("--dry-run", action="store_true", help="print instead of pushing/committing")
        p.add_argument("--no-git", action="store_true", help="skip git commit/push")
        p.set_defaults(handler=handler)
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
