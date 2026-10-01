"""Lightweight course progress for lesson quiz results."""

from __future__ import annotations

import json
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from aetherlab.core.atomic_json import atomic_write_json, path_lock

DEFAULT_REVIEW_INTERVALS_DAYS = (1, 3, 7, 14)


@dataclass(frozen=True)
class CourseSummary:
    attempts: int
    correct: int
    score: float
    missed_concepts: list[str]
    next_topic: str
    message: str
    due_count: int = 0


class CourseProgressStore:
    """JSON-backed quiz progress keyed by lesson topic and audience."""

    def __init__(
        self, path: Path, review_intervals_days: str | tuple[int, ...] | list[int] | None = None
    ) -> None:
        self.path = Path(path)
        self.review_intervals_days = parse_review_intervals(review_intervals_days)

    def record_quiz_answer(
        self,
        plan: Any,
        question_index: int,
        correct: bool,
        choice: str,
        *,
        confidence_level: str = "medium",
        now: datetime | None = None,
    ) -> CourseSummary:
        with path_lock(self.path):
            data = self._load()
            lessons = data.setdefault("lessons", {})
            key = lesson_key(plan)
            entry = lessons.get(key)
            if not isinstance(entry, dict):
                entry = {
                    "title": str(getattr(plan, "title", "")),
                    "topic": str(getattr(plan, "topic", "")),
                    "audience": str(getattr(plan, "audience", "")),
                    "attempts": 0,
                    "correct": 0,
                    "questions": {},
                }
                lessons[key] = entry
            now_dt = _as_utc(now)
            now_iso = now_dt.isoformat(timespec="seconds")
            confidence = _normalize_confidence(confidence_level)
            questions = entry.get("questions")
            if not isinstance(questions, dict):
                questions = {}
                entry["questions"] = questions
            q_entry = questions.get(str(question_index))
            if not isinstance(q_entry, dict):
                q_entry = {}
                questions[str(question_index)] = q_entry
            q_entry["prompt"] = _question_prompt(plan, question_index)
            q_entry["concept"] = _question_concept(plan, question_index)
            answer, why, choices = _question_answer(plan, question_index)
            q_entry["answer"] = answer
            q_entry["why"] = why
            q_entry["choices"] = choices
            q_entry.setdefault("first_attempt_at", now_iso)
            q_entry["attempts"] = _count(q_entry.get("attempts")) + 1
            q_entry["last_choice"] = str(choice)
            q_entry["last_correct"] = bool(correct)
            q_entry["last_at"] = now_iso
            q_entry["confidence_level"] = confidence
            streak = _count(q_entry.get("review_streak"))
            if correct and confidence != "low":
                q_entry["correct"] = _count(q_entry.get("correct")) + 1
                streak += 1
            else:
                if not correct:
                    q_entry["misses"] = _count(q_entry.get("misses")) + 1
                streak = 0
            q_entry["review_streak"] = streak
            interval = _review_interval_days(
                streak, correct and confidence != "low", self.review_intervals_days
            )
            q_entry["review_interval_days"] = interval
            q_entry["due_at"] = (now_dt + timedelta(days=interval)).isoformat(timespec="seconds")
            _append_attempt_event(q_entry, {
                "kind": "quiz",
                "at": now_iso,
                "correct": bool(correct),
                "confidence_level": confidence,
                "scheduled_interval_days": interval,
            })
            entry["attempts"] = _count(entry.get("attempts")) + 1
            if correct:
                entry["correct"] = _count(entry.get("correct")) + 1
            entry["last_at"] = now_iso
            self._save(data)
            return self.summary(plan)

    def summary(self, plan: Any) -> CourseSummary:
        with path_lock(self.path):
            data = self._load()
        lessons = data.get("lessons", {})
        if not isinstance(lessons, dict):
            lessons = {}
        entry = lessons.get(lesson_key(plan), {})
        if not isinstance(entry, dict):
            entry = {}
        attempts = _count(entry.get("attempts"))
        correct = _count(entry.get("correct"))
        score = (correct / attempts) if attempts else 0.0
        questions = entry.get("questions", {})
        if not isinstance(questions, dict):
            questions = {}
        missed = [
            str(q.get("concept", "")).strip()
            for q in questions.values()
            if isinstance(q, dict) and not bool(q.get("last_correct", True))
        ]
        missed_concepts = _dedupe([m for m in missed if m])
        next_topic = _next_topic(plan, missed_concepts)
        if not attempts:
            message = "Course progress starts when you answer a quiz question."
        elif missed_concepts:
            message = (
                f"Quiz score {correct}/{attempts}. Review "
                f"{missed_concepts[0]} next."
            )
        else:
            message = (
                f"Quiz score {correct}/{attempts}. Ready for {next_topic}."
            )
        due_count = sum(
            1 for q in questions.values()
            if isinstance(q, dict) and _is_due(q.get("due_at"), datetime.now(timezone.utc))
        )
        return CourseSummary(
            attempts=attempts,
            correct=correct,
            score=score,
            missed_concepts=missed_concepts,
            next_topic=next_topic,
            message=message,
            due_count=due_count,
        )

    def due_reviews(
        self, *, now: datetime | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Return locally stored review prompts that are due, oldest first."""
        now_dt = _as_utc(now)
        with path_lock(self.path):
            data = self._load()
        lessons = data.get("lessons", {})
        if not isinstance(lessons, dict):
            return []
        due: list[dict[str, Any]] = []
        for key, lesson in lessons.items():
            if not isinstance(lesson, dict):
                continue
            questions = lesson.get("questions", {})
            if not isinstance(questions, dict):
                continue
            for index, question in questions.items():
                if not isinstance(question, dict) or not _is_due(question.get("due_at"), now_dt):
                    continue
                due.append({
                    "lesson_key": str(key),
                    "lesson_title": str(lesson.get("title") or lesson.get("topic") or key),
                    "question_index": str(index),
                    "prompt": str(question.get("prompt", "")),
                    "concept": str(question.get("concept", "")),
                    "answer": str(question.get("answer", "")),
                    "why": str(question.get("why", "")),
                    "choices": [str(x) for x in question.get("choices", [])]
                    if isinstance(question.get("choices"), list) else [],
                    "due_at": str(question.get("due_at", "")),
                    "review_streak": _count(question.get("review_streak")),
                })
        due.sort(key=lambda item: item["due_at"])
        # Round-robin concepts so a long run of due questions from one lesson
        # does not crowd out retrieval practice on other recent topics.
        groups: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
        for item in due:
            concept_key = str(item.get("concept") or item.get("lesson_key") or "").casefold()
            groups[concept_key].append(item)
        mixed: list[dict[str, Any]] = []
        while groups:
            for concept_key in list(groups):
                mixed.append(groups[concept_key].popleft())
                if not groups[concept_key]:
                    del groups[concept_key]
        return mixed[:max(0, int(limit))]

    def record_review_result(
        self, review: dict[str, Any], recalled: bool, *, now: datetime | None = None
    ) -> int:
        """Reschedule a reviewed prompt after the learner self-rates recall."""
        now_dt = _as_utc(now)
        with path_lock(self.path):
            data = self._load()
            lessons = data.setdefault("lessons", {})
            lesson = lessons.get(str(review.get("lesson_key", "")), {})
            questions = lesson.get("questions", {}) if isinstance(lesson, dict) else {}
            question = questions.get(str(review.get("question_index", ""))) if isinstance(questions, dict) else None
            if not isinstance(question, dict):
                return 0
            streak = _count(question.get("review_streak"))
            if recalled:
                streak += 1
            else:
                streak = 0
            interval = _review_interval_days(
                streak, bool(recalled), self.review_intervals_days
            )
            question["review_streak"] = streak
            question["review_interval_days"] = interval
            question["last_review_at"] = now_dt.isoformat(timespec="seconds")
            question["due_at"] = (now_dt + timedelta(days=interval)).isoformat(timespec="seconds")
            first_at = _parse_datetime(question.get("first_attempt_at"))
            days_since_first = (
                max(0.0, (now_dt - first_at).total_seconds() / 86400.0)
                if first_at is not None else None
            )
            _append_attempt_event(question, {
                "kind": "spaced_review",
                "at": now_dt.isoformat(timespec="seconds"),
                "recalled": bool(recalled),
                "days_since_first_attempt": (
                    round(days_since_first, 4) if days_since_first is not None else None
                ),
                "scheduled_interval_days": interval,
            })
            self._save(data)
        return interval

    def evaluation_events(self) -> list[dict[str, Any]]:
        """Return de-identified quiz/review events for a local delayed-recall study."""
        with path_lock(self.path):
            data = self._load()
        lessons = data.get("lessons", {})
        if not isinstance(lessons, dict):
            return []
        events: list[dict[str, Any]] = []
        for lesson_key_value, lesson in lessons.items():
            if not isinstance(lesson, dict):
                continue
            questions = lesson.get("questions", {})
            if not isinstance(questions, dict):
                continue
            for question_index, question in questions.items():
                if not isinstance(question, dict):
                    continue
                for event in question.get("attempt_history", []):
                    if not isinstance(event, dict):
                        continue
                    events.append({
                        "lesson_key": str(lesson_key_value),
                        "lesson_title": str(lesson.get("title", "")),
                        "concept": str(question.get("concept", "")),
                        "question_index": str(question_index),
                        **event,
                    })
        events.sort(key=lambda item: str(item.get("at", "")))
        return events

    def due_review_count(self, *, now: datetime | None = None) -> int:
        return len(self.due_reviews(now=now, limit=10000))

    def _load(self) -> dict[str, Any]:
        with path_lock(self.path):
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                return {"schema": "aetherlab.course_progress.v1", "lessons": {}}
        if not isinstance(payload, dict):
            return {"schema": "aetherlab.course_progress.v1", "lessons": {}}
        if not isinstance(payload.get("lessons"), dict):
            payload["lessons"] = {}
        return payload

    def _save(self, data: dict[str, Any]) -> None:
        with path_lock(self.path):
            atomic_write_json(self.path, data)


def lesson_key(plan: Any) -> str:
    topic = str(getattr(plan, "topic", "") or getattr(plan, "title", "")).lower()
    audience = str(getattr(plan, "audience", "undergrad")).lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", topic).strip("-") or "lesson"
    return f"{audience}:{normalized}"


def _count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _as_utc(value: datetime | None) -> datetime:
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _review_interval_days(
    streak: int,
    correct: bool,
    intervals: tuple[int, ...] = DEFAULT_REVIEW_INTERVALS_DAYS,
) -> int:
    if not correct:
        return intervals[0]
    return intervals[min(max(0, streak - 1), len(intervals) - 1)]


def parse_review_intervals(
    value: str | tuple[int, ...] | list[int] | None,
) -> tuple[int, ...]:
    if value is None or value == "":
        return DEFAULT_REVIEW_INTERVALS_DAYS
    try:
        items = value.split(",") if isinstance(value, str) else list(value)
        values = sorted({int(str(item).strip()) for item in items})
        values = [item for item in values if 1 <= item <= 365][:8]
    except (TypeError, ValueError):
        values = []
    return tuple(values) or DEFAULT_REVIEW_INTERVALS_DAYS


def _normalize_confidence(value: Any) -> str:
    confidence = str(value or "medium").strip().lower()
    return confidence if confidence in {"low", "medium", "high"} else "medium"


def _append_attempt_event(question: dict[str, Any], event: dict[str, Any]) -> None:
    history = question.get("attempt_history")
    if not isinstance(history, list):
        history = []
        question["attempt_history"] = history
    history.append(event)
    del history[:-500]


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return _as_utc(datetime.fromisoformat(str(value)))
    except (TypeError, ValueError):
        return None


def _is_due(value: Any, now: datetime) -> bool:
    if not value:
        return False
    try:
        due = datetime.fromisoformat(str(value))
        due = _as_utc(due)
        return due <= _as_utc(now)
    except (TypeError, ValueError):
        return False


def _question_prompt(plan: Any, question_index: int) -> str:
    questions = list(getattr(plan, "questions", []) or [])
    if 0 <= question_index < len(questions):
        return str(getattr(questions[question_index], "q", ""))
    return ""


def _question_concept(plan: Any, question_index: int) -> str:
    objectives = list(getattr(plan, "objectives", []) or [])
    if objectives:
        return str(objectives[min(question_index, len(objectives) - 1)])
    prompt = _question_prompt(plan, question_index)
    if prompt:
        words = re.findall(r"[A-Za-z][A-Za-z'-]{2,}", prompt)
        return " ".join(words[:5]) or str(getattr(plan, "topic", "the topic"))
    return str(getattr(plan, "topic", "") or "the topic")


def _question_answer(plan: Any, question_index: int) -> tuple[str, str, list[str]]:
    questions = list(getattr(plan, "questions", []) or [])
    if 0 <= question_index < len(questions):
        question = questions[question_index]
        return (
            str(getattr(question, "answer", "")),
            str(getattr(question, "why", "")),
            [str(choice) for choice in getattr(question, "choices", []) or []],
        )
    return "", "", []


def _next_topic(plan: Any, missed_concepts: list[str]) -> str:
    if missed_concepts:
        return f"Review: {missed_concepts[0]}"
    topic = str(getattr(plan, "topic", "") or getattr(plan, "title", "this topic"))
    lower = topic.lower()
    if "kepler" in lower or "orbit" in lower:
        return "Orbital energy and escape velocity"
    if "pendulum" in lower:
        return "Driven oscillations and resonance"
    if "wave" in lower:
        return "Interference and standing waves"
    if "field" in lower or "charge" in lower:
        return "Electric potential and equipotentials"
    if "oscillator" in lower or "spring" in lower:
        return "Forced oscillators and resonance"
    return f"Next layer of {topic}"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.lower()
        if key not in seen:
            seen.add(key)
            out.append(value)
    return out
