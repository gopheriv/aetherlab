"""Client and local settings for the optional shared school leaderboard."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from aetherlab.core.atomic_json import atomic_write_json, path_lock
from aetherlab.services.ent_practice_progress import full_mock_history, load_attempts
from aetherlab.services.school_leaderboard import MockScore, SchoolLeaderboardEntry
from aetherlab.services.student_profiles import StudentProfile

_STUDENT_ID = re.compile(r"^[a-f0-9]{64}$")
_MAX_RESPONSE_BYTES = 1_000_000


class LeaderboardError(RuntimeError):
    """A safe, user-displayable leaderboard connection or response error."""


def validate_server_url(value: str) -> str:
    """Normalize a server URL and require HTTPS outside a private network."""
    raw = str(value or "").strip().rstrip("/")
    if not raw:
        return ""
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("invalid_url")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("invalid_url") from exc
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("invalid_url")
    if parsed.path not in {"", "/"}:
        raise ValueError("invalid_url")
    host = parsed.hostname.casefold()
    local_http = host == "localhost" or host.endswith(".local")
    try:
        local_http = local_http or ipaddress.ip_address(host).is_private or ipaddress.ip_address(host).is_loopback
    except ValueError:
        pass
    if parsed.scheme != "https" and not local_http:
        raise ValueError("https_required")
    return raw


class LeaderboardSettingsStore:
    """Persist the optional endpoint in the user's application data folder."""

    def __init__(self, data_dir: Path) -> None:
        self.path = Path(data_dir) / "leaderboard_settings.json"

    def get_server_url(self) -> str:
        override = self.environment_override()
        if override is not None:
            return override
        with path_lock(self.path):
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return ""
        try:
            return validate_server_url(payload.get("server_url", ""))
        except (AttributeError, ValueError):
            return ""

    def set_server_url(self, value: str) -> str:
        normalized = validate_server_url(value)
        with path_lock(self.path):
            atomic_write_json(self.path, {"version": 1, "server_url": normalized})
        # The saved preference remains available when the override is removed;
        # callers must nevertheless act on the same effective URL as the getter.
        override = self.environment_override()
        return normalized if override is None else override

    @staticmethod
    def environment_override() -> str | None:
        """None means no override; an empty string means an invalid override."""
        raw = os.getenv("AETHERLAB_LEADERBOARD_URL", "").strip()
        if not raw:
            return None
        try:
            return validate_server_url(raw)
        except ValueError:
            return ""


def _participant_id(profile: StudentProfile) -> str:
    """Create the same pseudonymous participant key on each of a student's devices."""
    username = " ".join(str(profile.username or "").casefold().split())
    school_id = " ".join(str(profile.school_id or "").casefold().split())
    if not username or not school_id:
        raise LeaderboardError("A username and school ID are required to join the leaderboard.")
    return hashlib.sha256(f"{school_id}\0{username}".encode("utf-8")).hexdigest()


def _submission(profile: StudentProfile) -> dict:
    scores = []
    for attempt in full_mock_history(load_attempts(profile.progress_path)):
        try:
            score = max(0, min(50, int(attempt.get("score", 0))))
        except (TypeError, ValueError):
            continue
        completed_at = str(attempt.get("completed_at", ""))
        if completed_at:
            scores.append({"score": score, "completed_at": completed_at})
    return {
        "school_id": str(profile.school_id or "").strip(),
        "student_id": _participant_id(profile),
        "name": profile.name,
        "class_name": profile.class_name,
        "scores": scores,
    }


def _request_json(url: str, payload: dict) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read(4096).decode("utf-8")).get("error", "")
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            detail = ""
        raise LeaderboardError(str(detail or f"Server returned HTTP {exc.code}.")) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise LeaderboardError("Could not connect to the leaderboard server.") from exc
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise LeaderboardError("The leaderboard server response is too large.")
    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LeaderboardError("The leaderboard server returned invalid data.") from exc
    if not isinstance(result, dict) or not isinstance(result.get("entries"), list):
        raise LeaderboardError("The leaderboard server returned invalid data.")
    return result


def sync_school_leaderboard(
    server_url: str,
    profile: StudentProfile,
) -> list[SchoolLeaderboardEntry]:
    """Share this profile's complete mock scores and return its school ranking."""
    base_url = validate_server_url(server_url)
    if not base_url:
        raise LeaderboardError("Configure a leaderboard server URL first.")
    response = _request_json(
        f"{base_url}/api/v1/leaderboard/sync",
        _submission(profile),
    )
    entries = []
    for raw in response["entries"]:
        if not isinstance(raw, dict):
            continue
        student_id = str(raw.get("student_id", ""))
        if not _STUDENT_ID.fullmatch(student_id):
            continue
        raw_scores = raw.get("scores", [])
        scores = []
        if isinstance(raw_scores, list):
            for item in raw_scores:
                if not isinstance(item, dict):
                    continue
                try:
                    score = max(0, min(50, int(item.get("score", 0))))
                except (TypeError, ValueError):
                    continue
                scores.append(MockScore(score, str(item.get("completed_at", ""))))
        best_score = max((item.score for item in scores), default=None)
        latest_score = max(
            scores,
            key=lambda item: item.completed_at,
            default=None,
        )
        try:
            rank = int(raw["rank"]) if raw.get("rank") is not None else None
        except (TypeError, ValueError):
            rank = None
        entries.append(SchoolLeaderboardEntry(
            rank=rank,
            name=str(raw.get("name", ""))[:80],
            class_name=str(raw.get("class_name", ""))[:24],
            best_score=best_score,
            latest_score=latest_score.score if latest_score else None,
            mock_count=len(scores),
            scores=tuple(sorted(scores, key=lambda item: item.completed_at, reverse=True)),
            is_current_user=student_id == _participant_id(profile),
        ))
    return entries
