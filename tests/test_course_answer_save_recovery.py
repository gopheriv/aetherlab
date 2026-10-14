"""A graded lesson answer remains retryable after storage/acknowledgment failure."""
from __future__ import annotations

import os
from dataclasses import replace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aetherlab.services.course_mode import CourseProgressStore
from aetherlab.services.ent_lesson_catalog import accelerated_motion_5min_plan
from aetherlab.services.lesson_pipeline import _prebuilt_5min_bundle
from aetherlab.ui.qt_compat import QtWidgets

_APP = None


def _window(root, language, monkeypatch):
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from aetherlab.core.settings import load_settings
    from aetherlab.ui.main_window import MainWindow

    monkeypatch.setenv("AETHERLAB_DATA_DIR", str(root))
    monkeypatch.setenv("AETHERLAB_DISABLE_LEGACY_ENV", "1")
    settings = replace(load_settings(), data_dir=root, cache_path=root / "cache.sqlite3",
                       chroma_path=root / "chroma", library_path=root / "library",
                       openai_api_key="", fallback_api_key="", github_token="", reference_sources_path=None)
    window = MainWindow(settings)
    monkeypatch.setattr(window.lesson_view, "set_video", lambda _path: None)
    window.command_bar.set_language(language)
    window.on_lesson_ready(_prebuilt_5min_bundle(accelerated_motion_5min_plan(language)))
    return window


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("failure", ("write", "acknowledgment"))
def test_failed_answer_save_keeps_grade_and_retries_exactly_once(language, failure, tmp_path, monkeypatch):
    from aetherlab.services import course_mode

    window = _window(tmp_path, language, monkeypatch)
    bundle = window._last_lesson
    card = window.lesson_view._question_cards[0]
    target = window.active_student_profile.course_progress_path
    def refused(*_args, **_kwargs):
        raise PermissionError("Temporary storage refusal")
    try:
        with monkeypatch.context() as patch:
            if failure == "write":
                patch.setattr(course_mode, "atomic_write_json", refused)
            else:
                patch.setattr(window.course_progress, "summary", refused)
            next(button for button in card._group.buttons() if button.text() == card._q.answer).click()
        assert card._answered
        assert hasattr(card, "_save_retry") and not card._save_retry.isHidden()
        assert card._save_status.text()
        assert all(not button.isEnabled() for button in card._group.buttons())
        already_saved = CourseProgressStore(target).summary(bundle.plan).attempts
        assert already_saved == (0 if failure == "write" else 1)
        card._save_retry.click()
        assert card._save_retry.isHidden() and not card._save_status.text()
        assert CourseProgressStore(target).summary(bundle.plan).attempts == 1
        assert len(CourseProgressStore(target).evaluation_events()) == 1
    finally:
        # An intentionally failed assertion must not open an interactive close
        # warning in this offscreen test process.
        if hasattr(window, "_pending_lesson_answers"):
            window._pending_lesson_answers.clear()
        window.close()


def test_operation_identity_rejects_a_changed_retry_without_an_extra_attempt(tmp_path):
    plan = accelerated_motion_5min_plan("ru")
    store = CourseProgressStore(tmp_path / "progress.json")
    first = store.record_quiz_answer(plan, 0, True, plan.questions[0].answer, operation_id="owned-test-request")
    second = store.record_quiz_answer(plan, 0, True, plan.questions[0].answer, operation_id="owned-test-request")
    assert first.attempts == second.attempts == 1
    before = store.path.read_bytes()
    with pytest.raises(ValueError):
        store.record_quiz_answer(plan, 1, True, plan.questions[1].answer, operation_id="owned-test-request")
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_pending_answers_block_unconfirmed_close_and_allow_explicit_discard(language, tmp_path, monkeypatch):
    from aetherlab.services import course_mode
    from aetherlab.ui.qt_compat import QtGui

    window = _window(tmp_path, language, monkeypatch)
    card = window.lesson_view._question_cards[0]
    def refused(*_args, **_kwargs):
        raise PermissionError("Temporary storage refusal")
    with monkeypatch.context() as patch:
        patch.setattr(course_mode, "atomic_write_json", refused)
        card._group.buttons()[0].click()
    dialogs = []
    def keep(dialog):
        dialogs.append(dialog)
        assert dialog.buttonRole(dialog.defaultButton()) == QtWidgets.QMessageBox.ButtonRole.RejectRole
        assert dialog.escapeButton() is dialog.defaultButton()
        dialog.defaultButton().click()
        return dialog.result()
    monkeypatch.setattr(QtWidgets.QMessageBox, "exec", keep)
    try:
        event = QtGui.QCloseEvent()
        window.closeEvent(event)
        assert not event.isAccepted() and window._pending_lesson_answers
        assert dialogs and dialogs[0].windowTitle()
        def discard(dialog):
            next(button for button in dialog.buttons()
                 if dialog.buttonRole(button) == QtWidgets.QMessageBox.ButtonRole.DestructiveRole).click()
            return dialog.result()
        monkeypatch.setattr(QtWidgets.QMessageBox, "exec", discard)
        event = QtGui.QCloseEvent()
        window.closeEvent(event)
        assert event.isAccepted() and not window._pending_lesson_answers
        assert not window.active_student_profile.course_progress_path.exists()
    finally:
        window._pending_lesson_answers.clear()
        window.close()


def test_review_read_failure_is_reported_without_escaping_a_qt_callback(tmp_path, monkeypatch):
    window = _window(tmp_path, "ru", monkeypatch)
    def refused(*_args, **_kwargs):
        raise PermissionError("Temporary read refusal")
    monkeypatch.setattr(window.course_progress, "due_reviews", refused)
    try:
        window._review_due_questions()
        assert "историю повторения" in window.statusBar().currentMessage()
    finally:
        window.close()


def test_pending_grade_stays_with_its_profile_and_restores_on_return(tmp_path, monkeypatch):
    from aetherlab.services import course_mode
    from aetherlab.ui.profile_dialog import StudentProfileDialog

    window = _window(tmp_path, "ru", monkeypatch)
    first = window.active_student_profile
    card = window.lesson_view._question_cards[0]
    def refused(*_args, **_kwargs):
        raise PermissionError("Temporary write refusal")
    with monkeypatch.context() as patch:
        patch.setattr(course_mode, "atomic_write_json", refused)
        next(button for button in card._group.buttons() if button.text() == card._q.answer).click()
    second = window.student_profile_store.create_profile("Second audit learner")
    selected = [second]
    def choose(dialog):
        dialog.profile_combo.setCurrentIndex(dialog.profile_combo.findData(selected[0].id))
        dialog.use_button.click()
        return dialog.result()
    monkeypatch.setattr(StudentProfileDialog, "exec", choose)
    try:
        window._manage_student_profiles()
        second_card = window.lesson_view._question_cards[0]
        assert not second_card._answered and second_card._save_retry.isHidden()
        next(button for button in second_card._group.buttons() if button.text() == second_card._q.answer).click()
        second_before = second.course_progress_path.read_bytes()
        selected[0] = first
        window._manage_student_profiles()
        restored = window.lesson_view._question_cards[0]
        assert restored._answered and not restored._save_retry.isHidden()
        restored._save_retry.click()
        assert window.course_progress.summary(window._last_lesson.plan).attempts == 1
        assert second.course_progress_path.read_bytes() == second_before
    finally:
        window._pending_lesson_answers.clear()
        window.close()


def test_cancelled_due_review_does_not_claim_a_saved_response(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone

    from aetherlab.ui.widgets import _LessonCheckDialog

    window = _window(tmp_path, "ru", monkeypatch)
    plan = window._last_lesson.plan
    window.course_progress.record_quiz_answer(plan, 0, True, plan.questions[0].answer,
                                              now=datetime.now(timezone.utc) - timedelta(days=10))
    before = window.course_progress.path.read_bytes()
    monkeypatch.setattr(_LessonCheckDialog, "exec", lambda dialog: QtWidgets.QDialog.DialogCode.Rejected)
    try:
        window._review_due_questions()
        assert "saved" not in window.statusBar().currentMessage().lower()
        assert window.course_progress.path.read_bytes() == before
    finally:
        window.close()
