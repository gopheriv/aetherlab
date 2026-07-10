"""Lightweight course progress for lesson quiz results."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aetherlab.core.atomic_json import atomic_write_json, path_lock


@dataclass(frozen=True)
class CourseSummary:
    attempts: int
    correct: int
    score: float
    missed_concepts: list[str]
    next_topic: str
    message: str


class CourseProgressStore:
    """JSON-backed quiz progress keyed by lesson topic and audience."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def record_quiz_answer(
        self,
        plan: Any,
        question_index: int,
        correct: bool,
        choice: str,
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
            now = datetime.now(timezone.utc).isoformat()
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
            q_entry["attempts"] = _count(q_entry.get("attempts")) + 1
            q_entry["last_choice"] = str(choice)
            q_entry["last_correct"] = bool(correct)
            q_entry["last_at"] = now
            if correct:
                q_entry["correct"] = _count(q_entry.get("correct")) + 1
            else:
                q_entry["misses"] = _count(q_entry.get("misses")) + 1
            entry["attempts"] = _count(entry.get("attempts")) + 1
            if correct:
                entry["correct"] = _count(entry.get("correct")) + 1
            entry["last_at"] = now
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
        return CourseSummary(
            attempts=attempts,
            correct=correct,
            score=score,
            missed_concepts=missed_concepts,
            next_topic=next_topic,
            message=message,
        )

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
