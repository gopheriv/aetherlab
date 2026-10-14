"""Native discovery: changing a translation must not unlock a graded answer."""
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_route = runpy.run_path(str(ROOT / "tests/test_prebuilt_student_routes.py"))


@pytest.mark.parametrize("language,target", (("kk", "ru"), ("ru", "en"), ("en", "kk")))
@pytest.mark.parametrize("correct", (True, False))
def test_translation_keeps_graded_choice_and_does_not_add_an_attempt(language, target, correct, tmp_path, monkeypatch):
    from aetherlab.services.ent_lesson_catalog import accelerated_motion_5min_plan
    from aetherlab.services.lesson_pipeline import _prebuilt_5min_bundle

    window = _route["_window"](tmp_path, language, monkeypatch)
    window.on_lesson_ready(_prebuilt_5min_bundle(accelerated_motion_5min_plan(language)))
    card = window.lesson_view._question_cards[0]
    card._confidence.setCurrentIndex(card._confidence.findData("low"))
    index = 0 if correct else 1
    card._group.buttons()[index].click()
    path = window.active_student_profile.course_progress_path
    before = path.read_bytes()
    try:
        window._on_title_language_changed(target)
        translated = window.lesson_view._question_cards[0]
        assert translated is not card
        assert translated._answered, "Changing language unlocked an already graded question"
        assert translated._group.buttons()[index].isChecked()
        assert all(not button.isEnabled() for button in translated._group.buttons())
        assert translated.confidence_level() == "low"
        assert window.lesson_view.confidence_for_question(0) == "low"
        assert translated._feedback.text() and translated._save_retry.isHidden()
        translated._group.buttons()[index].click()
        summary = window.course_progress.summary(window._last_lesson.plan)
        assert summary.attempts == 1 and summary.correct == int(correct)
        assert path.read_bytes() == before
    finally:
        window.close()


@pytest.mark.parametrize("reload_kind", ("same_language", "changed_content"))
def test_fresh_lesson_attempt_is_not_locked_by_translation_restore(reload_kind, tmp_path, monkeypatch):
    from dataclasses import replace
    from aetherlab.services.ent_lesson_catalog import accelerated_motion_5min_plan
    from aetherlab.services.lesson_pipeline import _prebuilt_5min_bundle

    window = _route["_window"](tmp_path, "ru", monkeypatch)
    plan = accelerated_motion_5min_plan("ru")
    window.on_lesson_ready(_prebuilt_5min_bundle(plan))
    window.lesson_view._question_cards[0]._group.buttons()[0].click()
    before = window.active_student_profile.course_progress_path.read_bytes()
    replacement = _prebuilt_5min_bundle(accelerated_motion_5min_plan("en") if reload_kind == "changed_content" else plan)
    if reload_kind == "changed_content":
        replacement.plan = replace(replacement.plan, prebuilt_content_hash="different-accepted-content")
    try:
        window.on_lesson_ready(replacement)
        fresh = window.lesson_view._question_cards[0]
        assert not fresh._answered and not fresh._feedback.text()
        assert all(button.isEnabled() for button in fresh._group.buttons())
        assert window.active_student_profile.course_progress_path.read_bytes() == before
    finally:
        window.close()
