"""Learning-first progression rules for the student companion UI.

These are product heuristics, not validated measures of subject mastery. The
UI deliberately calls a topic "confident" rather than "mastered" and exposes
the question-count and accuracy rule to learners.
"""

from __future__ import annotations

from dataclasses import dataclass

MIN_QUESTIONS_FOR_CONFIDENCE = 5
CONFIDENCE_ACCURACY = 0.80
COMPANION_IDS = ("quantum", "photon", "lab_bot")
# Kept as a compatibility alias for callers from older app builds.
PET_IDS = COMPANION_IDS
PET_POINT_MILESTONES = (50, 150)


@dataclass(frozen=True)
class CompanionProgress:
    points: int
    stage: int
    level: int
    next_milestone: int | None
    progress_to_milestone: float


def topic_confidence(correct: int, total: int) -> str:
    """Classify topic progress without presenting a small sample as mastery."""
    safe_total = max(0, int(total))
    safe_correct = min(safe_total, max(0, int(correct)))
    if safe_total == 0:
        return "not_started"
    if safe_total >= MIN_QUESTIONS_FOR_CONFIDENCE and safe_correct / safe_total >= CONFIDENCE_ACCURACY:
        return "confident"
    return "practicing"


def companion_progress(points: int) -> CompanionProgress:
    """Return companion evolution from all-time points earned in practice.

    One 50-point full UNT mock unlocks the growing form; 150 points unlocks
    the final form. Topic selection does not affect companion identity or progress.
    """
    safe_points = max(0, int(points))
    if safe_points >= PET_POINT_MILESTONES[-1]:
        return CompanionProgress(safe_points, 2, 3, None, 1.0)
    if safe_points >= PET_POINT_MILESTONES[0]:
        next_milestone = PET_POINT_MILESTONES[-1]
        progress = (safe_points - PET_POINT_MILESTONES[0]) / (
            PET_POINT_MILESTONES[-1] - PET_POINT_MILESTONES[0]
        )
        return CompanionProgress(safe_points, 1, 2, next_milestone, progress)
    return CompanionProgress(
        safe_points,
        0,
        1,
        PET_POINT_MILESTONES[0],
        safe_points / PET_POINT_MILESTONES[0],
    )
