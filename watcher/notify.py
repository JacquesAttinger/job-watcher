# Last edited: 2026-09-15 16:25 CDT
"""Outbound signals: ntfy.sh pushes and healthchecks.io pings.

Secrets come from the environment (cloud) or a local .env (never committed):
  NTFY_TOPIC   the ntfy topic name (long and random)
  HC_PING_URL  the healthchecks.io ping URL for the job-watcher check
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

from .state import REPO_ROOT

NTFY_ENDPOINT = "https://ntfy.sh"
ENV_PATH = REPO_ROOT / ".env"

# ntfy.sh rate-limits anonymous publishes per source IP with a small burst
# allowance, so real POSTs are spaced out and a 429 is retried with backoff.
PUBLISH_INTERVAL = 1.0  # seconds between consecutive real POSTs
RETRY_ATTEMPTS = 3  # total attempts per message on HTTP 429
RETRY_DEFAULT_WAIT = 2.0  # seconds to wait when 429 carries no Retry-After
RETRY_MAX_WAIT = 10.0  # cap on an honoured Retry-After

_last_post = 0.0


def load_env() -> None:
    """Fill os.environ from .env without overriding real environment variables."""
    if not ENV_PATH.exists():
        return
    for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def ntfy_topic() -> str:
    load_env()
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        raise RuntimeError("NTFY_TOPIC is not set (environment or .env)")
    return topic


def hc_ping_url() -> str | None:
    load_env()
    return os.environ.get("HC_PING_URL", "").strip() or None


def publish(
    title: str,
    message: str,
    click: str | None = None,
    priority: int = 3,
    tags: list[str] | None = None,
    dry_run: bool = False,
) -> bool:
    """POST one JSON message to ntfy. Returns True when accepted."""
    payload = {
        "topic": ntfy_topic(),
        "title": title[:120],
        "message": message[:400],
        "priority": priority,
        "tags": tags or ["briefcase"],
    }
    if click:
        payload["click"] = click
    if dry_run:
        print(f"[dry-run] ntfy: {json.dumps(payload, ensure_ascii=False)}")
        return True
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        NTFY_ENDPOINT, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    for attempt in range(1, RETRY_ATTEMPTS):
        try:
            return _post(request)
        except urllib.error.HTTPError as exc:
            if exc.code != 429:
                raise
            wait = _retry_wait(exc)
            print(f"ntfy 429 on attempt {attempt}/{RETRY_ATTEMPTS}, retrying in {wait:.1f}s", file=sys.stderr)
            time.sleep(wait)
    return _post(request)  # last attempt: any error propagates to the caller


def _post(request: urllib.request.Request) -> bool:
    _pace()
    with urllib.request.urlopen(request, timeout=30) as response:
        return 200 <= response.status < 300


def _pace() -> None:
    """Sleep so consecutive real POSTs are at least PUBLISH_INTERVAL apart."""
    global _last_post
    remaining = PUBLISH_INTERVAL - (time.monotonic() - _last_post)
    if remaining > 0:
        time.sleep(remaining)
    _last_post = time.monotonic()


def _retry_wait(exc: urllib.error.HTTPError) -> float:
    """Honour a numeric Retry-After header (capped), else use the default wait."""
    header = exc.headers.get("Retry-After") if exc.headers else None
    try:
        seconds = float(header) if header else RETRY_DEFAULT_WAIT
    except ValueError:  # HTTP-date form; not worth parsing for a 2s default
        seconds = RETRY_DEFAULT_WAIT
    return min(max(seconds, 0.0), RETRY_MAX_WAIT)


def ping_healthcheck(kind: str = "", dry_run: bool = False) -> None:
    """kind: "" for success, "fail" for failure, "start" at run start."""
    base = hc_ping_url()
    if not base:
        print("healthchecks: HC_PING_URL not set, skipping ping")
        return
    url = base.rstrip("/") + (f"/{kind}" if kind else "")
    if dry_run:
        print(f"[dry-run] healthchecks ping: {url}")
        return
    request = urllib.request.Request(url, headers={"User-Agent": "job-watcher/1.0"})
    with urllib.request.urlopen(request, timeout=20):
        pass
