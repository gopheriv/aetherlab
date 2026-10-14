"""Small local-only goals, mock history, and mistake queue for ENT practice."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from aetherlab.core.atomic_json import atomic_write_json, path_lock
from aetherlab.services.ent_physics_bank import ENT_TOPIC_IDS, EXERCISES, QUESTIONS
from aetherlab.services.gamification import COMPANION_IDS

_MAX_ATTEMPTS = 100
_QUESTION_IDS = {question.id for question in (*EXERCISES, *QUESTIONS)}
_LEVELS = {"beginner", "intermediate", "advanced"}
_ACTIVE_SESSION_VERSION = 1
_PROCTOR_EVENT_TYPES = {
    "face_not_visible",
    "multiple_faces",
    "camera_unavailable",
    "camera_lost",
    "app_focus_lost",
}


def _attempt_id(value: Any) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return ""


def _active_session_path(path: Path) -> Path:
    return Path(path).with_name(Path(path).name + ".active-exam.json")


def save_active_session(path: Path | None, session: dict[str, Any]) -> bool:
    """Atomically save only the current local attempt so a student can resume it."""
    if path is None or not isinstance(session, dict):
        return False
    question_ids = session.get("question_ids")
    answers = session.get("answers")
    if not isinstance(question_ids, list) or not question_ids or len(question_ids) > 500:
        return False
    if not isinstance(answers, list) or len(answers) != len(question_ids):
        return False
    safe_answers: list[list[int] | None] = []
    for answer in answers:
        if answer is None:
            safe_answers.append(None)
            continue
        if not isinstance(answer, (list, tuple)) or len(answer) > 12:
            return False
        try:
            values = [int(item) for item in answer]
        except (TypeError, ValueError, OverflowError):
            return False
        if any(item < -1 or item > 100 for item in values):
            return False
        safe_answers.append(values)
    mode = str(session.get("mode", ""))
    language = str(session.get("language", ""))
    if mode not in {"practice", "timed", "mistake_review"} or language not in {"kk", "ru", "en"}:
        return False
    try:
        index = max(0, min(int(session.get("index", 0)), len(question_ids) - 1))
        remaining = max(0, min(int(session.get("seconds_left", 0)), 24 * 60 * 60))
    except (TypeError, ValueError, OverflowError):
        return False
    proctor_events: list[dict[str, str]] = []
    raw_events = session.get("proctor_events", [])
    if isinstance(raw_events, list):
        for event in raw_events[:100]:
            if not isinstance(event, dict):
                continue
            event_type = str(event.get("type", ""))
            event_at = str(event.get("at", ""))
            if event_type not in _PROCTOR_EVENT_TYPES:
                continue
            try:
                datetime.fromisoformat(event_at.replace("Z", "+00:00"))
            except ValueError:
                continue
            proctor_events.append({"type": event_type, "at": event_at[:40]})
    payload = {
        "version": _ACTIVE_SESSION_VERSION,
        "question_ids": [str(item)[:100] for item in question_ids],
        "answers": safe_answers,
        "index": index,
        "seconds_left": remaining,
        "mode": mode,
        "language": language,
        "full_mock": bool(session.get("full_mock")),
        "proctor_enabled": bool(session.get("proctor_enabled")),
        "proctor_events": proctor_events,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "attempt_id": _attempt_id(session.get("attempt_id")),
        "completion_pending": bool(session.get("completion_pending")),
    }
    target = _active_session_path(Path(path))
    with path_lock(target):
        atomic_write_json(target, payload)
    return True


def load_active_session(path: Path | None) -> dict[str, Any] | None:
    """Load a validated attempt; elapsed wall time counts against timed exams."""
    if path is None:
        return None
    target = _active_session_path(Path(path))
    with path_lock(target):
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return None
    if not isinstance(payload, dict) or payload.get("version") != _ACTIVE_SESSION_VERSION:
        return None
    ids, answers = payload.get("question_ids"), payload.get("answers")
    mode, language = payload.get("mode"), payload.get("language")
    if (
        not isinstance(ids, list) or not ids or len(ids) > 500
        or not isinstance(answers, list) or len(answers) != len(ids)
        or mode not in {"practice", "timed", "mistake_review"}
        or language not in {"kk", "ru", "en"}
    ):
        return None
    try:
        index = int(payload.get("index", 0))
        seconds_left = max(0, min(int(payload.get("seconds_left", 0)), 24 * 60 * 60))
        if mode == "timed":
            saved_at = datetime.fromisoformat(str(payload.get("saved_at", "")))
            if saved_at.tzinfo is None:
                saved_at = saved_at.replace(tzinfo=timezone.utc)
            seconds_left = max(
                0,
                min(24 * 60 * 60, seconds_left - int((datetime.now(timezone.utc) - saved_at).total_seconds())),
            )
    except (TypeError, ValueError, OverflowError):
        return None
    if not 0 <= index < len(ids):
        return None
    if any(not isinstance(item, str) or item not in _QUESTION_IDS for item in ids):
        return None
    clean_answers: list[tuple[int, ...] | None] = []
    for answer in answers:
        if answer is None:
            clean_answers.append(None)
            continue
        if not isinstance(answer, list) or len(answer) > 12:
            return None
        try:
            values = tuple(int(item) for item in answer)
        except (TypeError, ValueError, OverflowError):
            return None
        if any(item < -1 or item > 100 for item in values):
            return None
        clean_answers.append(values)
    clean_events: list[dict[str, str]] = []
    raw_events = payload.get("proctor_events", [])
    if isinstance(raw_events, list):
        for event in raw_events[:100]:
            if not isinstance(event, dict):
                continue
            event_type = str(event.get("type", ""))
            event_at = str(event.get("at", ""))
            if event_type not in _PROCTOR_EVENT_TYPES:
                continue
            try:
                datetime.fromisoformat(event_at.replace("Z", "+00:00"))
            except ValueError:
                continue
            clean_events.append({"type": event_type, "at": event_at[:40]})
    return {
        "question_ids": list(ids),
        "answers": clean_answers,
        "index": index,
        "seconds_left": seconds_left,
        "mode": mode,
        "language": language,
        "full_mock": bool(payload.get("full_mock")),
        "proctor_enabled": bool(payload.get("proctor_enabled")),
        "proctor_events": clean_events,
        "attempt_id": _attempt_id(payload.get("attempt_id")),
        "completion_pending": bool(payload.get("completion_pending")),
    }


def clear_active_session(path: Path | None) -> None:
    if path is None:
        return
    target = _active_session_path(Path(path))
    with path_lock(target):
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass


def _empty_payload() -> dict[str, Any]:
    return {
        "version": 2,
        "goals": {
            "target_score": None,
            "exam_date": "",
            "weekly_question_goal": None,
            "weekly_mock_day": None,
            "preparation_level": "beginner",
        },
        "attempts": [],
        "mistake_question_ids": [],
        "companion_choice": "",
        "companion_total_points": None,
    }


def _read_payload(target: Path) -> dict[str, Any]:
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    defaults = _empty_payload()
    defaults.update(payload)
    return defaults


@dataclass(frozen=True)
class ProgressSnapshot:
    goals: dict[str, Any]
    attempts: list[dict[str, Any]]
    mistake_ids: tuple[str, ...]
    companion_choice: str | None
    companion_points: int
    recovered_values: bool = False


def _clean_attempts(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    cleaned = []
    for item in raw[-_MAX_ATTEMPTS:]:
        if not isinstance(item, dict):
            continue
        attempt = dict(item)
        try:
            for key, maximum in (("score", 200), ("possible_points", 200), ("question_count", 500)):
                if key in attempt:
                    value = int(attempt[key])
                    if not 0 <= value <= maximum:
                        raise ValueError("invalid attempt aggregate")
                    attempt[key] = value
        except (TypeError, ValueError, OverflowError):
            continue
        if attempt.get("full_mock") is True and attempt.get("score", 0) > 50:
            attempt["full_mock"] = False
        cleaned.append(attempt)
    return cleaned


def load_progress_snapshot(path: Path | None) -> ProgressSnapshot:
    """Read one consistent file snapshot; IO errors are never empty progress."""
    if path is None:
        payload = _empty_payload()
    else:
        target = Path(path)
        with path_lock(target):
            payload = _read_payload(target)
    raw_attempts = payload.get("attempts", [])
    attempts = _clean_attempts(raw_attempts)
    raw_ids = payload.get("mistake_question_ids", [])
    ids = tuple(sorted({str(item) for item in raw_ids if str(item) in _QUESTION_IDS})) if isinstance(raw_ids, list) else ()
    choice = str(payload.get("companion_choice", "") or "")
    raw_points = payload.get("companion_total_points")
    recovered = (len(raw_attempts[-_MAX_ATTEMPTS:]) != len(attempts)) if isinstance(raw_attempts, list) else True
    points = _sum_attempt_scores(raw_attempts)
    try:
        if raw_points is not None:
            points = max(0, int(raw_points))
    except (TypeError, ValueError, OverflowError):
        recovered = True
    goals = _clean_goals(payload.get("goals"))
    raw_goals = payload.get("goals")
    if isinstance(raw_goals, dict):
        recovered = recovered or any(raw_goals.get(key) not in (None, "") and goals[key] is None for key in ("target_score", "weekly_question_goal", "weekly_mock_day"))
    return ProgressSnapshot(goals, attempts, ids,
                            choice if choice in COMPANION_IDS else None, points, recovered)


def _write_payload(target: Path, payload: dict[str, Any]) -> None:
    payload["version"] = 2
    atomic_write_json(target, payload)


def _clean_goals(goals: dict[str, Any] | None) -> dict[str, Any]:
    raw = goals if isinstance(goals, dict) else {}
    target = raw.get("target_score")
    weekly = raw.get("weekly_question_goal")
    mock_day = raw.get("weekly_mock_day")
    try:
        target = int(target) if target not in (None, "") else None
    except (TypeError, ValueError, OverflowError):
        target = None
    try:
        weekly = int(weekly) if weekly not in (None, "") else None
    except (TypeError, ValueError, OverflowError):
        weekly = None
    if target is not None and not 1 <= target <= 50:
        target = None
    if weekly is not None and not 1 <= weekly <= 500:
        weekly = None
    try:
        mock_day = int(mock_day) if mock_day not in (None, "") else None
    except (TypeError, ValueError, OverflowError):
        mock_day = None
    if mock_day is not None and not 0 <= mock_day <= 6:
        mock_day = None
    exam_date = str(raw.get("exam_date", "") or "").strip()
    try:
        date.fromisoformat(exam_date) if exam_date else None
    except ValueError:
        exam_date = ""
    level = str(raw.get("preparation_level", "beginner"))
    if level not in _LEVELS:
        level = "beginner"
    return {
        "target_score": target,
        "exam_date": exam_date,
        "weekly_question_goal": weekly,
        "weekly_mock_day": mock_day,
        "preparation_level": level,
    }


def load_goals(path: Path | None) -> dict[str, Any]:
    return load_progress_snapshot(path).goals


def save_goals(path: Path | None, goals: dict[str, Any]) -> dict[str, Any]:
    """Persist learner preferences locally; no account or network is involved."""
    cleaned = _clean_goals(goals)
    if path is None:
        return cleaned
    target = Path(path)
    with path_lock(target):
        payload = _read_payload(target)
        payload["goals"] = cleaned
        _write_payload(target, payload)
    return cleaned


def load_attempts(path: Path | None) -> list[dict[str, Any]]:
    return load_progress_snapshot(path).attempts


def load_mistake_ids(path: Path | None) -> tuple[str, ...]:
    return load_progress_snapshot(path).mistake_ids


def load_companion_choice(path: Path | None) -> str | None:
    return load_progress_snapshot(path).companion_choice


def save_companion_choice(path: Path | None, companion_id: str) -> str:
    """Save one of the three supported companions to this profile's progress."""
    choice = str(companion_id or "")
    if choice not in COMPANION_IDS:
        raise ValueError("unknown_companion")
    if path is not None:
        target = Path(path)
        with path_lock(target):
            payload = _read_payload(target)
            payload["companion_choice"] = choice
            _write_payload(target, payload)
    return choice


def load_companion_points(path: Path | None) -> int:
    return load_progress_snapshot(path).companion_points


def _sum_attempt_scores(attempts: Any) -> int:
    if not isinstance(attempts, list):
        return 0
    total = 0
    for attempt in attempts:
        if not isinstance(attempt, dict):
            continue
        try:
            total += max(0, int(attempt.get("score", 0) or 0))
        except (TypeError, ValueError, OverflowError):
            continue
    return total


def record_attempt(
    path: Path | None,
    *,
    language: str,
    topic_results: dict[str, dict[str, int]],
    question_results: dict[str, bool] | None = None,
    score: int = 0,
    possible_points: int = 0,
    mode: str = "practice",
    full_mock: bool = False,
    integrity_events: list[dict[str, Any]] | None = None,
    proctor_enabled: bool | None = None,
    attempt_id: str | None = None,
) -> list[dict[str, Any]]:
    """Store aggregate results and wrong question IDs, never selected answers."""
    if path is None:
        return []
    target = Path(path)
    safe_results: dict[str, dict[str, int]] = {}
    for topic, values in topic_results.items():
        if topic not in ENT_TOPIC_IDS or not isinstance(values, dict):
            continue
        try:
            correct = max(0, min(int(values.get("correct", 0)), 100))
            total = max(correct, min(int(values.get("total", 0)), 100))
            points = max(0, min(int(values.get("points", correct)), 200))
            max_points = max(points, min(int(values.get("max_points", total)), 200))
        except (TypeError, ValueError, OverflowError):
            continue
        safe_results[topic] = {
            "correct": correct,
            "total": total,
            "points": points,
            "max_points": max_points,
        }

    q_results = {
        str(question_id): bool(correct)
        for question_id, correct in (question_results or {}).items()
        if str(question_id) in _QUESTION_IDS
    }
    safe_language = language if language in {"kk", "ru", "en"} else "kk"
    allowed_modes = {"practice", "timed", "mistake_review"}
    safe_mode = mode if mode in allowed_modes else "practice"
    # A full UNT mock is still capped at 50 in the UI; topic practice can now
    # contain 100 items, so preserve its larger total instead of truncating it.
    safe_score = max(0, min(int(score), 200))
    safe_possible = max(safe_score, min(int(possible_points), 200))

    with path_lock(target):
        payload = _read_payload(target)
        attempts = payload.get("attempts", [])
        attempts = [item for item in attempts if isinstance(item, dict)] if isinstance(attempts, list) else []
        identity = _attempt_id(attempt_id)
        if identity and any(item.get("attempt_id") == identity for item in attempts):
            return attempts[-_MAX_ATTEMPTS:]
        lifetime_points = payload.get("companion_total_points")
        if lifetime_points is None:
            lifetime_points = _sum_attempt_scores(attempts)
        try:
            lifetime_points = max(0, int(lifetime_points))
        except (TypeError, ValueError, OverflowError):
            lifetime_points = _sum_attempt_scores(attempts)
        existing_mistakes = payload.get("mistake_question_ids", [])
        mistakes = {str(item) for item in existing_mistakes if str(item) in _QUESTION_IDS} \
            if isinstance(existing_mistakes, list) else set()
        for question_id, correct in q_results.items():
            if correct:
                mistakes.discard(question_id)
            else:
                mistakes.add(question_id)

        completed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        safe_events: list[dict[str, str]] = []
        if isinstance(integrity_events, list):
            for event in integrity_events[:100]:
                if not isinstance(event, dict):
                    continue
                event_type = str(event.get("type", ""))
                event_at = str(event.get("at", ""))
                if event_type not in _PROCTOR_EVENT_TYPES:
                    continue
                try:
                    datetime.fromisoformat(event_at.replace("Z", "+00:00"))
                except ValueError:
                    continue
                safe_events.append({"type": event_type, "at": event_at[:40]})
        attempt = {
            "completed_at": completed_at,
            "language": safe_language,
            "mode": safe_mode,
            "full_mock": bool(full_mock),
            "score": safe_score,
            "possible_points": safe_possible,
            "question_count": len(q_results),
            "topics": safe_results,
            "missed_question_ids": sorted(
                question_id for question_id, correct in q_results.items() if not correct
            ),
        }
        if proctor_enabled is not None:
            attempt["proctor_enabled"] = bool(full_mock and proctor_enabled)
        if safe_events:
            attempt["integrity_events"] = safe_events
        if identity:
            attempt["attempt_id"] = identity
        attempts.append(attempt)
        payload["attempts"] = attempts[-_MAX_ATTEMPTS:]
        payload["mistake_question_ids"] = sorted(mistakes)
        payload["goals"] = _clean_goals(payload.get("goals"))
        payload["companion_total_points"] = lifetime_points + safe_score
        _write_payload(target, payload)
        return payload["attempts"]


def aggregate_topic_progress(attempts: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    progress = {
        topic: {"correct": 0, "total": 0, "points": 0, "max_points": 0}
        for topic in ENT_TOPIC_IDS
    }
    for attempt in attempts:
        topics = attempt.get("topics", {}) if isinstance(attempt, dict) else {}
        if not isinstance(topics, dict):
            continue
        for topic, values in topics.items():
            if topic not in progress or not isinstance(values, dict):
                continue
            try:
                correct = max(0, int(values.get("correct", 0)))
                total = max(correct, int(values.get("total", 0)))
                points = max(0, int(values.get("points", correct)))
                max_points = max(points, int(values.get("max_points", total)))
            except (TypeError, ValueError, OverflowError):
                continue
            progress[topic]["correct"] += correct
            progress[topic]["total"] += total
            progress[topic]["points"] += points
            progress[topic]["max_points"] += max_points
    return progress


def weekly_question_count(attempts: list[dict[str, Any]], *, today: date | None = None) -> int:
    """Count attempted items in the current ISO week from local history."""
    now = today or datetime.now(timezone.utc).date()
    year_week = now.isocalendar()[:2]
    total = 0
    for attempt in attempts:
        if not isinstance(attempt, dict):
            continue
        try:
            completed = datetime.fromisoformat(str(attempt.get("completed_at", "")))
            if completed.isocalendar()[:2] == year_week:
                total += max(0, int(attempt.get("question_count", 0)))
        except (TypeError, ValueError, OverflowError):
            continue
    return total


def full_mock_history(attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only complete 40-item, 50-point mixed mock results."""
    results = []
    for item in attempts:
        if not isinstance(item, dict) or item.get("full_mock") is not True:
            continue
        try:
            if int(item.get("possible_points", 0) or 0) == 50:
                results.append(item)
        except (TypeError, ValueError, OverflowError):
            continue
    return results
