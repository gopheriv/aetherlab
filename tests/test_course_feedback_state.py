"""Feedback follows recorded answers, objective review and selected content language."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from aetherlab.core.models import LessonPlan, LessonQuestion
from aetherlab.services.course_mode import CourseProgressStore


def _plan(language):
    return LessonPlan(
        title="Audit", topic={"kk": "Маятник", "ru": "Маятник", "en": "Pendulum"}[language],
        language=language, audience="high_school", model_name="authored-feedback-test",
        objectives=[{"kk": "Тербеліс периоды", "ru": "Период колебаний", "en": "Oscillation period"}[language]],
        questions=[LessonQuestion(q="Audit check", answer="A", choices=["A", "B"], why="Controlled fixture")],
    )


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_empty_course_does_not_claim_readiness_or_a_scored_attempt(language, tmp_path):
    store = CourseProgressStore(tmp_path / "course.json")
    summary = store.summary(_plan(language))
    prefix = {"kk": "Курс прогресі", "ru": "Прогресс курса", "en": "Course progress"}[language]
    assert summary.attempts == summary.correct == 0
    assert summary.message.startswith(prefix)
    assert "0/0" not in summary.message
    assert not store.path.exists()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_wrong_answer_recommends_review_instead_of_readiness(language, tmp_path):
    plan = _plan(language)
    store = CourseProgressStore(tmp_path / "course.json")
    summary = store.record_quiz_answer(plan, 0, False, "B")
    review = {"kk": "Қайталаңыз", "ru": "Повторите", "en": "Review"}[language]
    assert summary.missed_concepts == plan.objectives
    assert "0/1" in summary.message and review in summary.message
    assert plan.objectives[0] in summary.message
    assert summary.next_topic.startswith({"kk": "Қайталау:", "ru": "Повторить:", "en": "Review:"}[language])
    assert "Ready for" not in summary.message


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_correct_answer_has_localized_followup_without_losing_totals(language, tmp_path):
    store = CourseProgressStore(tmp_path / "course.json")
    summary = store.record_quiz_answer(_plan(language), 0, True, "A")
    target = {
        "kk": "Мәжбүрлі тербелістер және резонанс",
        "ru": "Вынужденные колебания и резонанс",
        "en": "Driven oscillations and resonance",
    }[language]
    assert summary.attempts == summary.correct == 1 and not summary.missed_concepts
    assert summary.next_topic == target
    assert "1/1" in summary.message and target in summary.message


def test_low_confidence_changes_review_schedule_without_erasing_a_correct_answer(tmp_path):
    plan = _plan("en")
    store = CourseProgressStore(tmp_path / "course.json", review_intervals_days="2,5,10")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    store.record_quiz_answer(plan, 0, True, "A", confidence_level="low", now=start)
    record = next(iter(store._load()["lessons"].values()))
    question = record["questions"]["0"]
    assert record["correct"] == question["correct"] == 1
    assert question["review_streak"] == 0 and question["review_interval_days"] == 2
    assert question["attempt_history"][0]["correct"] is True
    store.record_quiz_answer(plan, 0, True, "A", confidence_level="high", now=start + timedelta(days=1))
    record = next(iter(store._load()["lessons"].values()))
    assert record["correct"] == record["questions"]["0"]["correct"] == 2


@pytest.mark.parametrize("complete", (False, True))
def test_question_counters_repair_only_when_the_full_quiz_history_is_available(complete, tmp_path):
    plan = _plan("en")
    store = CourseProgressStore(tmp_path / "course.json")
    store.record_quiz_answer(plan, 0, True, "A", confidence_level="low")
    data = json.loads(store.path.read_text(encoding="utf-8"))
    lesson = next(iter(data["lessons"].values()))
    question = lesson["questions"]["0"]
    question["correct"] = 0 if complete else 1
    if not complete:
        question["attempts"] = lesson["attempts"] = 2
    question["teacher_note"] = "Keep original metadata"
    store.path.write_text(json.dumps(data), encoding="utf-8")
    before = store.path.read_bytes()
    store.summary(plan)
    assert store.path.read_bytes() == before
    store.record_quiz_answer(plan, 0, True, "A", confidence_level="high")
    question = next(iter(store._load()["lessons"].values()))["questions"]["0"]
    assert question["correct"] == 2
    assert question["teacher_note"] == "Keep original metadata"


@pytest.mark.parametrize("mode", ("objective_correct", "self_reported", "objective_wrong"))
def test_review_feedback_uses_latest_objective_evidence_only(mode, tmp_path):
    plan = _plan("en")
    store = CourseProgressStore(tmp_path / "course.json")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    store.record_quiz_answer(plan, 0, False, "B", now=start)
    due = store.due_reviews(now=start + timedelta(days=1))[0]
    correct = True if mode == "objective_correct" else False if mode == "objective_wrong" else None
    store.record_review_result(due, mode != "objective_wrong", correct=correct, now=start + timedelta(days=1))
    summary = store.summary(plan)
    assert summary.missed_concepts == ([] if mode == "objective_correct" else plan.objectives)
    assert summary.attempts == 1 and summary.correct == 0  # historical quiz totals stay separate
    question = next(iter(store._load()["lessons"].values()))["questions"]["0"]
    assert question["last_choice"] == "B" and question["last_correct"] is False
    store.record_quiz_answer(plan, 0, False, "B", now=start + timedelta(days=3))
    assert store.summary(plan).missed_concepts == plan.objectives


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_summary_language_override_does_not_write_or_change_the_plan(language, tmp_path):
    plan = _plan("en")
    store = CourseProgressStore(tmp_path / "course.json")
    store.record_quiz_answer(plan, 0, True, "A")
    before = store.path.read_bytes()
    summary = store.summary(plan, language=language)
    assert summary.correct == summary.attempts == 1 and "1/1" in summary.message
    if language != "en":
        assert "Quiz score" not in summary.message and "Next:" not in summary.message
    assert plan.language == "en" and store.path.read_bytes() == before


def test_lesson_message_catalog_has_the_same_keys_and_preserves_literal_titles():
    from aetherlab.core.lesson_messages import _TEXT, lesson_message

    assert set(_TEXT) == {"kk", "ru", "en"}
    assert all(set(messages) == set(_TEXT["en"]) for messages in _TEXT.values())
    values = {"index": 1, "total": 2, "title": "Literal {title}", "name": "Book.pdf",
              "correct": 1, "attempts": 2, "concept": "Concept", "topic": "Topic"}
    for language in _TEXT:
        for key in _TEXT[language]:
            assert lesson_message(language, key, **values).strip()
        assert "Literal {title}" in lesson_message(language, "stage_chapter", **values)
    assert lesson_message("ru-RU", "review_none") == _TEXT["ru"]["review_none"]
