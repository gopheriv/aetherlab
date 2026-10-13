"""Per-student daily allowance for explicit AI help requests.

This is a local-app product limit, not a server-side enforcement mechanism.
Background model calls and exam/practice actions never consume this allowance.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from aetherlab.core.atomic_json import atomic_write_json, path_lock

DAILY_AI_HELP_LIMIT = 10


def _read_usage(path: Path, today: date) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        raw = {}
    if not isinstance(raw, dict) or raw.get("date") != today.isoformat():
        return {"version": 1, "date": today.isoformat(), "used": 0}
    try:
        used = int(raw.get("used", 0))
    except (TypeError, ValueError):
        used = 0
    return {"version": 1, "date": today.isoformat(), "used": max(0, used)}


def daily_ai_help_usage(path: Path, *, today: date | None = None) -> int:
    """Return today's number of accepted AI help attempts for this student."""
    current_day = today or date.today()
    target = Path(path)
    with path_lock(target):
        return int(_read_usage(target, current_day)["used"])


def remaining_ai_help(
    path: Path,
    *,
    limit: int = DAILY_AI_HELP_LIMIT,
    today: date | None = None,
) -> int:
    """Return today's remaining requests, clamped to the configured limit."""
    safe_limit = max(0, int(limit))
    return max(0, safe_limit - daily_ai_help_usage(path, today=today))


def consume_ai_help(
    path: Path,
    *,
    limit: int = DAILY_AI_HELP_LIMIT,
    today: date | None = None,
) -> tuple[bool, int]:
    """Atomically reserve one request; return ``(allowed, remaining)``."""
    current_day = today or date.today()
    safe_limit = max(0, int(limit))
    target = Path(path)
    with path_lock(target):
        usage = _read_usage(target, current_day)
        used = int(usage["used"])
        if used >= safe_limit:
            return False, 0
        usage["used"] = used + 1
        atomic_write_json(target, usage)
        return True, max(0, safe_limit - int(usage["used"]))
