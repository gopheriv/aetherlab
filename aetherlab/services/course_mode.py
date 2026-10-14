"""Lightweight course progress for lesson quiz results."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict, deque
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from aetherlab.core.atomic_json import atomic_write_json, path_lock
from aetherlab.core.lesson_messages import lesson_message

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
    legacy_history_uncertain: bool = False


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
        operation_id: str | None = None,
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
                    "model_name": str(getattr(plan, "model_name", "")),
                }
                lessons[key] = entry
            operation = str(operation_id or "").strip()
            request = {
                "question_index": int(question_index), "correct": bool(correct),
                "choice": str(choice), "confidence_level": _normalize_confidence(confidence_level),
            }
            if operation:
                ledger = entry.setdefault("quiz_operation_ids", {})
                if not isinstance(ledger, dict):
                    raise ValueError("Lesson save operation ledger is unavailable")
                if operation in ledger:
                    if ledger[operation] != request:
                        raise ValueError("Lesson save retry differs from the original answer")
                    return self.summary(plan)
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
            correct_before = _quiz_correct_count(q_entry)
            q_entry["attempts"] = _count(q_entry.get("attempts")) + 1
            q_entry["correct"] = correct_before + int(bool(correct))
            q_entry["last_choice"] = str(choice)
            q_entry["last_correct"] = bool(correct)
            q_entry["last_at"] = now_iso
            q_entry["confidence_level"] = confidence
            streak = _count(q_entry.get("review_streak"))
            if correct and confidence != "low":
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
            if operation:
                entry["quiz_operation_ids"][operation] = request
            self._save(data)
            return self.summary(plan)

    def summary(self, plan: Any, *, language: str | None = None) -> CourseSummary:
        with path_lock(self.path):
            data = self._load()
        lessons = data.get("lessons", {})
        if not isinstance(lessons, dict):
            lessons = {}
        entry = lessons.get(lesson_key(plan), {})
        if not isinstance(entry, dict):
            entry = {}
        legacy_uncertain = bool(not entry and data.get("legacy_topic_history_uncertain")
                                and _generic_unicode_topic(getattr(plan, "topic", ""), getattr(plan, "model_name", "")))
        attempts = _count(entry.get("attempts"))
        correct = _count(entry.get("correct"))
        score = (correct / attempts) if attempts else 0.0
        questions = entry.get("questions", {})
        if not isinstance(questions, dict):
            questions = {}
        missed = [
            str(q.get("concept", "")).strip()
            for q in questions.values()
            if isinstance(q, dict) and not _latest_objective_correct(q)
        ]
        missed_concepts = _dedupe([m for m in missed if m])
        language = language or getattr(plan, "language", "en")
        next_topic = _next_topic(plan, missed_concepts, language=language)
        if legacy_uncertain:
            message = lesson_message(language, "course_legacy")
        elif not attempts:
            message = lesson_message(language, "course_start")
        elif missed_concepts:
            message = lesson_message(language, "course_review", correct=correct, attempts=attempts, concept=missed_concepts[0])
        else:
            message = lesson_message(language, "course_next", correct=correct, attempts=attempts, topic=next_topic)
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
            legacy_history_uncertain=legacy_uncertain,
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
            if lesson.get("legacy_identity_ambiguous"):
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
        self,
        review: dict[str, Any],
        recalled: bool,
        *,
        correct: bool | None = None,
        now: datetime | None = None,
    ) -> int:
        """Reschedule a prompt and retain self-reported or objective recall evidence."""
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
                "correct": bool(correct) if isinstance(correct, bool) else None,
                "recall_mode": "objective_mcq" if isinstance(correct, bool) else "self_reported",
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
            if lesson.get("legacy_identity_ambiguous"):
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
            except (FileNotFoundError, json.JSONDecodeError, UnicodeError):
                return {"schema": "aetherlab.course_progress.v1", "lessons": {}}
        if not isinstance(payload, dict):
            return {"schema": "aetherlab.course_progress.v1", "lessons": {}}
        if not isinstance(payload.get("lessons"), dict):
            payload["lessons"] = {}
        return _project_generic_legacy_history(_normalize_prebuilt_progress(payload))

    def _save(self, data: dict[str, Any]) -> None:
        with path_lock(self.path):
            atomic_write_json(self.path, data)


def lesson_key(plan: Any) -> str:
    from aetherlab.services.ent_lesson_catalog import ACCELERATED_MOTION_5MIN_VERSION

    if getattr(plan, "model_name", "") == ACCELERATED_MOTION_5MIN_VERSION:
        return "high_school:constant-acceleration-5min"
    topic = str(getattr(plan, "topic", "") or getattr(plan, "title", "")).lower()
    audience = str(getattr(plan, "audience", "undergrad")).lower()
    if _generic_unicode_topic(topic, getattr(plan, "model_name", "")):
        identity = unicodedata.normalize("NFC", topic.casefold().strip())
        return f"{audience}:topic-{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:24]}"
    normalized = re.sub(r"[^a-z0-9]+", "-", topic).strip("-") or "lesson"
    return f"{audience}:{normalized}"


def _generic_unicode_topic(topic: str, model_name: str = "") -> bool:
    from aetherlab.services.ent_lesson_catalog import (
        ACCELERATED_MOTION_5MIN_VERSION,
        ACCELERATED_MOTION_VERSION,
        accelerated_motion_plan,
    )

    if model_name in {ACCELERATED_MOTION_VERSION, ACCELERATED_MOTION_5MIN_VERSION}:
        return False
    value = str(topic or "").strip().casefold()
    if value in {accelerated_motion_plan(language).topic.casefold() for language in ("kk", "ru", "en")}:
        return False
    return any(character.isalpha() and not character.isascii() for character in value)


def _project_generic_legacy_history(data: dict[str, Any]) -> dict[str, Any]:
    """Retain unverifiable old mixed-topic totals; never pretend to split them."""
    for key, entry in data["lessons"].items():
        if not isinstance(entry, dict):
            continue
        topic = str(entry.get("topic", ""))
        audience = str(entry.get("audience", "undergrad")).lower()
        old_slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-") or "lesson"
        if key == f"{audience}:{old_slug}" and _generic_unicode_topic(topic, str(entry.get("model_name", ""))):
            if not entry.get("legacy_identity_ambiguous"):
                original = deepcopy(entry)
                records = entry.get("legacy_progress_records", [])
                entry["legacy_progress_records"] = deepcopy(records) if isinstance(records, list) else []
                entry["legacy_progress_records"].append({"source_key": key, "entry": original})
            entry["legacy_identity_ambiguous"] = True
            data["legacy_topic_history_uncertain"] = True
    return data


def _normalize_prebuilt_progress(data: dict[str, Any]) -> dict[str, Any]:
    """Project old language keys onto one identity; write only during a mutation.

    Only the known v2 topic labels at their old keys qualify. Full original
    records, including unknown fields, are retained when aliases are merged.
    Other lessons, ambiguous five-minute labels and v1 keys remain untouched.
    """
    canonical = "high_school:constant-acceleration-5min"
    aliases = {"high_school:5", "high_school:uniformly-accelerated-motion-5-minute-video"}
    topics = {
        "Теңүдемелі қозғалыс · 5 минуттық видео",
        "Равноускоренное движение · 5-минутное видео",
        "Uniformly accelerated motion · 5-minute video",
    }
    lessons = data["lessons"]
    candidates = [
        (key, entry) for key, entry in lessons.items()
        if key in aliases and isinstance(entry, dict)
        and entry.get("audience") == "high_school" and entry.get("topic") in topics
    ]
    if not candidates:
        return data
    if canonical in lessons:
        entry = lessons[canonical]
        if not isinstance(entry, dict) or entry.get("topic") not in topics:
            raise ValueError("Prepared lesson progress identity conflicts with an existing record")
        snapshots = entry.get("legacy_progress_records", [])
        prior_aliases = {item.get("source_key"): item.get("entry") for item in snapshots
                         if isinstance(item, dict)} if isinstance(snapshots, list) else {}
        duplicate_keys = []
        remaining = []
        for key, legacy in candidates:
            if key in prior_aliases:
                if legacy != prior_aliases[key]:
                    raise ValueError("Previously migrated lesson history has changed; review the old and current records")
                duplicate_keys.append(key)
            else:
                remaining.append((key, legacy))
        for key in duplicate_keys:
            lessons.pop(key)
        candidates = remaining
        if not candidates:
            return data
        candidates.insert(0, (canonical, entry))
    ordered = sorted(candidates, key=lambda item: _progress_timestamp(item[1]))
    merged: dict[str, Any] = {}
    for _key, entry in ordered:
        merged.update(deepcopy(entry))
    for field in ("attempts", "correct"):
        merged[field] = sum(_count(entry.get(field)) for _key, entry in candidates)
    questions: dict[str, Any] = {}
    for _key, entry in ordered:
        for index, question in (entry.get("questions") or {}).items() if isinstance(entry.get("questions"), dict) else ():
            if index not in questions or not isinstance(question, dict) or not isinstance(questions[index], dict):
                questions[index] = deepcopy(question)
                continue
            previous = questions[index]
            latest = max((previous, question), key=_progress_timestamp)
            combined = {**deepcopy(previous), **deepcopy(question), **deepcopy(latest)}
            for field in ("attempts", "correct", "misses"):
                combined[field] = _count(previous.get(field)) + _count(question.get(field))
            first = [value for value in (previous.get("first_attempt_at"), question.get("first_attempt_at")) if _parse_datetime(value)]
            if first:
                combined["first_attempt_at"] = min(first, key=lambda value: _parse_datetime(value).timestamp())
            history = []
            for record in (previous, question):
                events = record.get("attempt_history")
                if isinstance(events, list):
                    history.extend(deepcopy(events))
            combined["attempt_history"] = sorted(history, key=lambda event: str(event.get("at", "")) if isinstance(event, dict) else "")
            questions[index] = combined
    merged["questions"] = questions
    operations = {}
    for _key, entry in candidates:
        ledger = entry.get("quiz_operation_ids", {})
        if not isinstance(ledger, dict):
            raise ValueError("Legacy lesson save operation ledger is unavailable")
        for operation, request in ledger.items():
            if operation in operations and operations[operation] != request:
                raise ValueError("Legacy lesson save operations conflict")
            operations[operation] = deepcopy(request)
    if operations:
        merged["quiz_operation_ids"] = operations
    archived = deepcopy(lessons.get(canonical, {}).get("legacy_progress_records", []))
    if not isinstance(archived, list):
        archived = []
    archived.extend({"source_key": key, "entry": deepcopy(entry)} for key, entry in candidates if key != canonical)
    if canonical in lessons:
        archived.append({"source_key": canonical, "entry": {
            key: deepcopy(value) for key, value in lessons[canonical].items() if key != "legacy_progress_records"
        }})
    merged["legacy_progress_records"] = archived
    for key, _entry in candidates:
        lessons.pop(key)
    lessons[canonical] = merged
    return data


def _progress_timestamp(record: dict[str, Any]) -> float:
    parsed = [_parse_datetime(record.get(key)) for key in ("last_at", "last_review_at")]
    return max((value.timestamp() for value in parsed if value is not None), default=0.0)


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


def _quiz_correct_count(question: dict[str, Any]) -> int:
    history = question.get("attempt_history")
    if isinstance(history, list):
        quizzes = [event for event in history if isinstance(event, dict) and event.get("kind") == "quiz"]
        if len(quizzes) == _count(question.get("attempts")) and all(isinstance(event.get("correct"), bool) for event in quizzes):
            return sum(event["correct"] for event in quizzes)
    return _count(question.get("correct"))


def _latest_objective_correct(question: dict[str, Any]) -> bool:
    correct = bool(question.get("last_correct", True))
    latest = _parse_datetime(question.get("last_at"))
    history = question.get("attempt_history")
    for event in history if isinstance(history, list) else []:
        if not isinstance(event, dict) or event.get("kind") not in {"quiz", "spaced_review"} or not isinstance(event.get("correct"), bool):
            continue
        at = _parse_datetime(event.get("at"))
        if at is not None and (latest is None or at >= latest):
            latest, correct = at, event["correct"]
    return correct


def _next_topic(plan: Any, missed_concepts: list[str], *, language: str | None = None) -> str:
    language = language or getattr(plan, "language", "en")
    if missed_concepts:
        return lesson_message(language, "next_review", concept=missed_concepts[0])
    topic = str(getattr(plan, "topic", "") or getattr(plan, "title", "this topic"))
    lower = topic.lower()
    if any(term in lower for term in ("kepler", "orbit", "кеплер", "орбит")):
        return lesson_message(language, "next_orbit")
    if any(term in lower for term in ("pendulum", "маятник")):
        return lesson_message(language, "next_pendulum")
    if any(term in lower for term in ("wave", "волна", "волны", "толқын")):
        return lesson_message(language, "next_wave")
    if any(term in lower for term in ("field", "charge", "поле", "заряд", "өріс")):
        return lesson_message(language, "next_field")
    if any(term in lower for term in ("oscillator", "spring", "осциллятор", "пружин", "серіппе")):
        return lesson_message(language, "next_oscillator")
    return lesson_message(language, "next_more", topic=topic)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.lower()
        if key not in seen:
            seen.add(key)
            out.append(value)
    return out
