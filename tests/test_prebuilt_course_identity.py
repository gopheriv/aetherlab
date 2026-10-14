"""A shared prepared lesson keeps multilingual histories without modifying reads."""
from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from aetherlab.services.course_mode import CourseProgressStore, lesson_key
from aetherlab.services.ent_lesson_catalog import (
    accelerated_motion_5min_plan,
    accelerated_motion_plan,
)


def _legacy_history(path):
    start = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
    ru = replace(accelerated_motion_5min_plan("ru"), model_name="")
    en = replace(accelerated_motion_5min_plan("en"), model_name="")
    raw = {"schema": "aetherlab.course_progress.v1", "lessons": {}}
    for language, plan, correct, instant in (("ru", ru, True, start), ("en", en, False, start + timedelta(minutes=2))):
        single_path = path.with_name(f"legacy-{language}.json")
        CourseProgressStore(single_path).record_quiz_answer(
            plan, 0, correct, plan.questions[0].answer if correct else plan.questions[0].choices[-1], now=instant,
        )
        single = json.loads(single_path.read_text(encoding="utf-8"))["lessons"]
        legacy_key = "high_school:" + (re.sub(r"[^a-z0-9]+", "-", plan.topic.lower()).strip("-") or "lesson")
        entry = next(iter(single.values()))
        entry.pop("model_name", None)
        raw["lessons"][legacy_key] = entry
    for key, entry in raw["lessons"].items():
        entry["custom_teacher_note"] = "Preserve " + key
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return raw


def test_legacy_language_histories_merge_on_read_without_rewriting_bytes(tmp_path):
    path = tmp_path / "progress.json"
    original = _legacy_history(path)
    before = path.read_bytes()
    store = CourseProgressStore(path)
    for language in ("kk", "ru", "en"):
        summary = store.summary(accelerated_motion_5min_plan(language))
        assert summary.attempts == 2 and summary.correct == 1
    assert path.read_bytes() == before
    assert len(store.due_reviews(now=datetime(2026, 11, 1, tzinfo=timezone.utc))) == 1
    assert len(store.evaluation_events()) == 2
    assert len(original["lessons"]) == 2


def test_first_successful_write_preserves_legacy_records_and_does_not_double_count(tmp_path):
    path = tmp_path / "progress.json"
    original = _legacy_history(path)
    plan = accelerated_motion_5min_plan("en")
    store = CourseProgressStore(path)
    store.record_quiz_answer(plan, 0, True, plan.questions[0].answer)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert set(saved["lessons"]) == {lesson_key(plan)}
    entry = saved["lessons"][lesson_key(plan)]
    snapshots = {item["source_key"]: item["entry"] for item in entry["legacy_progress_records"]}
    assert snapshots == original["lessons"]
    assert store.summary(plan).attempts == 3 and store.summary(plan).correct == 2
    assert len(store.evaluation_events()) == 3
    store.record_quiz_answer(plan, 1, True, plan.questions[1].answer)
    assert store.summary(plan).attempts == 4
    assert len(store.evaluation_events()) == 4


def test_unrelated_v1_and_ambiguous_topic_records_are_not_relabelled(tmp_path):
    path = tmp_path / "progress.json"
    store = CourseProgressStore(path)
    v1 = accelerated_motion_plan("ru")
    store.record_quiz_answer(v1, 0, True, v1.questions[0].answer)
    original = json.loads(path.read_text(encoding="utf-8"))
    original["lessons"]["high_school:5"] = {"topic": "Other five-minute topic", "audience": "high_school", "attempts": 7, "correct": 3}
    path.write_text(json.dumps(original), encoding="utf-8")
    prepared = accelerated_motion_5min_plan("en")
    store.record_quiz_answer(prepared, 0, True, prepared.questions[0].answer)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["lessons"][lesson_key(v1)] == original["lessons"][lesson_key(v1)]
    assert saved["lessons"]["high_school:5"] == original["lessons"]["high_school:5"]
    assert store.summary(prepared).attempts == 1


def test_failed_migration_save_keeps_original_language_files(tmp_path, monkeypatch):
    from aetherlab.services import course_mode

    path = tmp_path / "progress.json"
    _legacy_history(path)
    before = path.read_bytes()
    def refused(*_args, **_kwargs):
        raise PermissionError("Temporary write refusal")
    monkeypatch.setattr(course_mode, "atomic_write_json", refused)
    plan = accelerated_motion_5min_plan("ru")
    with pytest.raises(PermissionError):
        CourseProgressStore(path).record_quiz_answer(plan, 0, True, plan.questions[0].answer)
    assert path.read_bytes() == before
    assert CourseProgressStore(path).summary(plan).attempts == 2


def test_unreadable_course_history_never_looks_empty_or_gets_overwritten(tmp_path, monkeypatch):
    path = tmp_path / "progress.json"
    _legacy_history(path)
    before = path.read_bytes()
    actual_read = Path.read_text
    def refused(target, *args, **kwargs):
        if target == path:
            raise PermissionError("Temporary read refusal")
        return actual_read(target, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", refused)
    store = CourseProgressStore(path)
    plan = accelerated_motion_5min_plan("ru")
    with pytest.raises(PermissionError):
        store.summary(plan)
    with pytest.raises(PermissionError):
        store.record_quiz_answer(plan, 0, True, plan.questions[0].answer)
    assert path.read_bytes() == before


def test_unreadable_course_write_preserves_the_complete_old_history(tmp_path, monkeypatch):
    path = tmp_path / "progress.json"
    _legacy_history(path)
    before = path.read_bytes()
    actual_read = Path.read_text
    def refused(target, *args, **kwargs):
        if target == path:
            raise PermissionError("Temporary read refusal")
        return actual_read(target, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", refused)
    plan = accelerated_motion_5min_plan("ru")
    raised = False
    try:
        CourseProgressStore(path).record_quiz_answer(plan, 0, True, plan.questions[0].answer)
    except PermissionError:
        raised = True
    assert path.read_bytes() == before
    assert raised


def test_reintroduced_exact_old_alias_does_not_count_history_twice(tmp_path):
    path = tmp_path / "progress.json"
    original = _legacy_history(path)
    plan = accelerated_motion_5min_plan("ru")
    store = CourseProgressStore(path)
    store.record_quiz_answer(plan, 0, True, plan.questions[0].answer)
    saved = json.loads(path.read_text(encoding="utf-8"))
    saved["lessons"].update(original["lessons"])
    path.write_text(json.dumps(saved), encoding="utf-8")
    before = path.read_bytes()
    assert store.summary(plan).attempts == 3
    assert len(store.evaluation_events()) == 3
    assert path.read_bytes() == before
    store.record_quiz_answer(plan, 1, True, plan.questions[1].answer)
    assert store.summary(plan).attempts == 4


def test_changed_previously_migrated_alias_requires_review_without_writing(tmp_path):
    path = tmp_path / "progress.json"
    original = _legacy_history(path)
    plan = accelerated_motion_5min_plan("ru")
    store = CourseProgressStore(path)
    store.record_quiz_answer(plan, 0, True, plan.questions[0].answer)
    saved = json.loads(path.read_text(encoding="utf-8"))
    key, old = next(iter(original["lessons"].items()))
    old["attempts"] += 1
    saved["lessons"][key] = old
    path.write_text(json.dumps(saved), encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="review"):
        store.summary(plan)
    with pytest.raises(ValueError, match="review"):
        store.record_quiz_answer(plan, 1, True, plan.questions[1].answer)
    assert path.read_bytes() == before


def test_real_windows_read_lock_preserves_existing_course_history(tmp_path):
    import os

    msvcrt = pytest.importorskip("msvcrt", reason="Physical Windows byte-range lock check requires Windows")

    path = tmp_path / "progress.json"
    _legacy_history(path)
    before = path.read_bytes()
    plan = accelerated_motion_5min_plan("ru")
    with path.open("r+b") as held:
        msvcrt.locking(held.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            with pytest.raises(OSError):
                CourseProgressStore(path).summary(plan)
            with pytest.raises(OSError):
                CourseProgressStore(path).record_quiz_answer(plan, 0, True, plan.questions[0].answer)
        finally:
            held.seek(0, os.SEEK_SET)
            msvcrt.locking(held.fileno(), msvcrt.LK_UNLCK, 1)
    assert path.read_bytes() == before
