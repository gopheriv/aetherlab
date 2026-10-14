"""Different Unicode topics cannot share an ASCII-stripped progress bucket."""
from __future__ import annotations

import json

from aetherlab.core.models import LessonPlan, LessonQuestion
from aetherlab.services.course_mode import CourseProgressStore, lesson_key


def _plan(topic):
    return LessonPlan(topic=topic, title=topic, audience="high_school", model_name="authored-test",
                      questions=[LessonQuestion(q=topic, choices=["A", "B"], answer="A", why="Example")])


def test_distinct_unicode_topics_keep_their_own_attempts(tmp_path):
    first = _plan("Explain Кинематика for UNT")
    second = _plan("Explain Динамика for UNT")
    assert lesson_key(first) != lesson_key(second)
    store = CourseProgressStore(tmp_path / "progress.json")
    store.record_quiz_answer(first, 0, True, "A")
    store.record_quiz_answer(second, 0, False, "B")
    assert store.summary(first).attempts == store.summary(second).attempts == 1
    assert store.summary(first).correct == 1 and store.summary(second).correct == 0


def test_ambiguous_old_unicode_history_is_preserved_without_guessing_attribution(tmp_path):
    first = _plan("Explain Кинематика for UNT")
    second = _plan("Explain Динамика for UNT")
    path = tmp_path / "progress.json"
    old = {"schema": "aetherlab.course_progress.v1", "lessons": {
        "high_school:explain-for-unt": {
            "title": first.title, "topic": first.topic, "audience": "high_school",
            "attempts": 2, "correct": 1, "questions": {}, "teacher_note": "Keep this history",
        }
    }}
    path.write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
    before = path.read_bytes()
    store = CourseProgressStore(path)
    for plan in (first, second):
        summary = store.summary(plan)
        assert summary.legacy_history_uncertain
        assert summary.attempts == 0 and "earlier" in summary.message.lower()
    assert path.read_bytes() == before
    store.record_quiz_answer(second, 0, True, "A")
    saved = json.loads(path.read_text(encoding="utf-8"))
    retained = saved["lessons"]["high_school:explain-for-unt"]
    assert all(retained[key] == value for key, value in old["lessons"]["high_school:explain-for-unt"].items())
    assert retained["legacy_progress_records"][0]["entry"] == old["lessons"]["high_school:explain-for-unt"]
    assert store.summary(second).attempts == 1 and not store.summary(second).legacy_history_uncertain
