"""School-code leaderboard built from completed local UNT mock exams."""

from __future__ import annotations

from dataclasses import dataclass

from aetherlab.services.ent_practice_progress import full_mock_history, load_attempts
from aetherlab.services.student_profiles import StudentProfile


@dataclass(frozen=True)
class MockScore:
    score: int
    completed_at: str


@dataclass(frozen=True)
class SchoolLeaderboardEntry:
    rank: int | None
    name: str
    class_name: str
    best_score: int | None
    latest_score: int | None
    mock_count: int
    scores: tuple[MockScore, ...]
    is_current_user: bool


def school_leaderboard(
    profiles: list[StudentProfile],
    school_id: str,
    *,
    current_profile_id: str = "",
) -> list[SchoolLeaderboardEntry]:
    """Rank profiles sharing a school code by best completed 50-point mock.

    Each profile contributes only complete full-mock results. Results are read
    from its own local progress file; practice-by-topic scores are excluded.
    """
    school_key = " ".join(str(school_id or "").casefold().split())
    if not school_key:
        return []

    entries: list[SchoolLeaderboardEntry] = []
    for profile in profiles:
        profile_school_key = " ".join(str(profile.school_id or "").casefold().split())
        if profile_school_key != school_key:
            continue
        scores = []
        for attempt in full_mock_history(load_attempts(profile.progress_path)):
            try:
                score = max(0, min(50, int(attempt.get("score", 0))))
            except (TypeError, ValueError):
                continue
            scores.append(MockScore(score, str(attempt.get("completed_at", ""))))
        scores.sort(key=lambda item: item.completed_at, reverse=True)
        best_score = max((item.score for item in scores), default=None)
        entries.append(SchoolLeaderboardEntry(
            rank=None,
            name=profile.name,
            class_name=profile.class_name,
            best_score=best_score,
            latest_score=scores[0].score if scores else None,
            mock_count=len(scores),
            scores=tuple(scores),
            is_current_user=profile.id == current_profile_id,
        ))

    entries.sort(key=lambda item: item.name.casefold())
    entries.sort(
        key=lambda item: (
            item.best_score is not None,
            item.best_score if item.best_score is not None else -1,
            item.latest_score if item.latest_score is not None else -1,
        ),
        reverse=True,
    )

    ranked: list[SchoolLeaderboardEntry] = []
    previous_score: int | None = None
    previous_rank: int | None = None
    for index, entry in enumerate(entries, start=1):
        if entry.best_score is None:
            rank = None
        elif entry.best_score == previous_score:
            rank = previous_rank
        else:
            rank = index
            previous_score = entry.best_score
            previous_rank = rank
        ranked.append(SchoolLeaderboardEntry(
            rank=rank,
            name=entry.name,
            class_name=entry.class_name,
            best_score=entry.best_score,
            latest_score=entry.latest_score,
            mock_count=entry.mock_count,
            scores=entry.scores,
            is_current_user=entry.is_current_user,
        ))
    return ranked
