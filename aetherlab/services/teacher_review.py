"""Local teacher-facing summaries of completed UNT mock attempts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from aetherlab.services.ent_practice_progress import full_mock_history, load_attempts
from aetherlab.services.student_profiles import StudentProfile

_PROCTOR_EVENT_TYPES = {
    "face_not_visible",
    "multiple_faces",
    "camera_unavailable",
    "camera_lost",
    "app_focus_lost",
}


@dataclass(frozen=True)
class LocalMockReviewEntry:
    student_name: str
    class_name: str
    score: int
    completed_at: str
    proctor_enabled: bool | None
    integrity_events: tuple[tuple[str, str], ...]


def local_school_mock_review(
    profiles: list[StudentProfile], school_id: str,
) -> list[LocalMockReviewEntry]:
    """Return full mock scores and allowlisted camera flags for local profiles.

    No selected answers, video, or data from the leaderboard server is read.
    Camera metadata remains a set of review signals, not a cheating verdict.
    """
    school_key = " ".join(str(school_id or "").casefold().split())
    if not school_key:
        return []

    entries: list[LocalMockReviewEntry] = []
    for profile in profiles:
        profile_school_key = " ".join(str(profile.school_id or "").casefold().split())
        if profile_school_key != school_key:
            continue
        for attempt in full_mock_history(load_attempts(profile.progress_path)):
            try:
                score = max(0, min(50, int(attempt.get("score", 0))))
            except (TypeError, ValueError):
                continue
            events: list[tuple[str, str]] = []
            raw_events = attempt.get("integrity_events", [])
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
                    events.append((event_type, event_at[:40]))
            completed_at = str(attempt.get("completed_at", ""))
            try:
                datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
            except ValueError:
                completed_at = ""
            enabled_value = attempt.get("proctor_enabled")
            proctor_enabled = enabled_value if isinstance(enabled_value, bool) else None
            entries.append(LocalMockReviewEntry(
                student_name=profile.name,
                class_name=profile.class_name,
                score=score,
                completed_at=completed_at,
                proctor_enabled=proctor_enabled,
                integrity_events=tuple(events),
            ))
    entries.sort(key=lambda item: item.completed_at, reverse=True)
    return entries
