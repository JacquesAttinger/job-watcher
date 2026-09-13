# Last edited: 2026-09-13 12:48 CDT
"""Outbound signals: ntfy.sh pushes and healthchecks.io pings.

Secrets come from the environment (cloud) or a local .env (never committed):
  NTFY_TOPIC   the ntfy topic name (long and random)
  HC_PING_URL  the healthchecks.io ping URL for the job-watcher check
"""

from __future__ import annotations

import json
import os
import urllib.request

from .state import REPO_ROOT

NTFY_ENDPOINT = "https://ntfy.sh"
ENV_PATH = REPO_ROOT / ".env"


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
    with urllib.request.urlopen(request, timeout=30) as response:
        return 200 <= response.status < 300


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
