"""Progress IO errors must preserve attempts and permit a safe retry."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aetherlab.services import ent_practice_progress as progress
from aetherlab.services.ent_physics_bank import questions_for_language
from aetherlab.ui.exam_practice import ExamPracticeDialog
from aetherlab.ui.qt_compat import QtWidgets

_APP = None


def _app():
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


def _deny_read(monkeypatch, target):
    original = Path.read_text

    def read(path, *args, **kwargs):
        if path == target:
            raise PermissionError("progress temporarily unavailable")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)


def _deny_write(*args, **kwargs):
    raise PermissionError("progress temporarily unwritable")


def test_mutations_do_not_replace_unreadable_progress(tmp_path, monkeypatch):
    path = tmp_path / "progress.json"
    progress.record_attempt(path, language="en", topic_results={}, score=12)
    progress.save_goals(path, {"target_score": 45})
    before = path.read_bytes()
    with monkeypatch.context() as patch:
        _deny_read(patch, path)
        for operation in (
            lambda: progress.save_goals(path, {"target_score": 50}),
            lambda: progress.save_companion_choice(path, "photon"),
            lambda: progress.record_attempt(path, language="en", topic_results={}, score=20),
        ):
            with pytest.raises(PermissionError):
                operation()
            assert path.read_bytes() == before
    assert progress.load_companion_points(path) == 12
    assert progress.load_goals(path)["target_score"] == 45


def test_goals_save_failure_keeps_draft_and_never_claims_success(tmp_path, monkeypatch):
    _app()
    for language in ("kk", "ru", "en"):
        path = tmp_path / f"{language}.json"
        progress.save_goals(path, {"target_score": 40})
        dialog = ExamPracticeDialog(language, progress_path=path)
        dialog._target_score.setValue(48)
        with monkeypatch.context() as patch:
            patch.setattr(progress, "atomic_write_json", _deny_write)
            dialog._save_goals()
        assert dialog._target_score.value() == 48
        assert dialog._storage_notice.text() == dialog._storage_text["goals_error"]
        assert progress.load_goals(path)["target_score"] == 40
        dialog._save_goals()
        assert progress.load_goals(path)["target_score"] == 48
        assert not dialog._storage_notice.text()
        dialog.close()


def test_result_failure_freezes_answers_and_retry_records_once(tmp_path, monkeypatch):
    _app()
    for language in ("kk", "ru", "en"):
        path = tmp_path / f"result-{language}.json"
        questions = questions_for_language(language, "kinematics")[:2]
        dialog = ExamPracticeDialog(language, progress_path=path)
        dialog._begin_session(questions, "practice")
        dialog._answer_widgets[questions[0]["correct_indices"][0]].setChecked(True)
        with monkeypatch.context() as patch:
            patch.setattr(progress, "atomic_write_json", _deny_write)
            dialog._finish_session()
        assert not dialog._session_finished
        assert dialog._completion_pending
        assert dialog._answers[0] == tuple(questions[0]["correct_indices"])
        assert not dialog._choices_host.isEnabled()
        assert not dialog._back.isEnabled() and not dialog._next.isEnabled()
        assert dialog._storage_notice.text() == dialog._storage_text["result_error"]
        assert dialog._finish.text() == dialog._storage_text["retry_result"]
        dialog._request_finish()
        assert dialog._session_finished
        assert dialog._stack.currentIndex() == 2
        assert len(progress.load_attempts(path)) == 1
        dialog._finish_session()
        assert len(progress.load_attempts(path)) == 1
        dialog.close()


def test_autosave_failure_is_visible_and_close_retries_current_answer(tmp_path, monkeypatch):
    _app()
    path = tmp_path / "active.json"
    questions = questions_for_language("en", "kinematics")[:2]
    dialog = ExamPracticeDialog("en", progress_path=path)
    dialog._begin_session(questions, "practice")
    dialog.show()
    dialog._answer_widgets[questions[0]["correct_indices"][0]].setChecked(True)
    with monkeypatch.context() as patch:
        patch.setattr(progress, "atomic_write_json", _deny_write)
        assert not dialog._persist_active_session()
        assert dialog._storage_notice.text() == dialog._storage_text["session_error"]
        dialog.close()
        assert dialog.isVisible()
    dialog.close()
    assert not dialog.isVisible()
    state = progress.load_active_session(path)
    assert state is not None and state["answers"][0] == tuple(questions[0]["correct_indices"])


def test_unreadable_resume_is_not_treated_as_no_attempt(tmp_path, monkeypatch):
    _app()
    path = tmp_path / "resume.json"
    dialog = ExamPracticeDialog("ru", progress_path=path)
    dialog._begin_session(questions_for_language("ru", "kinematics")[:2], "practice")
    dialog.close()
    active = path.with_name(path.name + ".active-exam.json")
    before = active.read_bytes()
    reopened = ExamPracticeDialog("ru", progress_path=path)
    with monkeypatch.context() as patch:
        _deny_read(patch, active)
        reopened._start()
    assert reopened._stack.currentIndex() == 0
    assert reopened._storage_notice.text() == reopened._storage_text["resume_error"]
    assert active.read_bytes() == before
    reopened.close()


def test_pending_result_resumes_frozen_and_stale_session_cannot_duplicate(tmp_path, monkeypatch):
    _app()
    path = tmp_path / "pending.json"
    questions = questions_for_language("en", "kinematics")[:2]
    dialog = ExamPracticeDialog("en", progress_path=path)
    dialog._begin_session(questions, "practice")
    dialog._answer_widgets[questions[0]["correct_indices"][0]].setChecked(True)
    original = progress.atomic_write_json

    def fail_history(target, payload):
        if target == path:
            raise PermissionError("history denied")
        return original(target, payload)

    with monkeypatch.context() as patch:
        patch.setattr(progress, "atomic_write_json", fail_history)
        dialog._finish_session()
        dialog.close()
        state = progress.load_active_session(path)
        assert state is not None and state["completion_pending"]
        reopened = ExamPracticeDialog("en", progress_path=path)
        assert reopened._resume_active_session(state)
        assert reopened._completion_pending and not reopened._choices_host.isEnabled()
    # A failed cleanup may leave the active snapshot even after a valid commit.
    with monkeypatch.context() as patch:
        patch.setattr("aetherlab.ui.exam_practice.clear_active_session", lambda path: None)
        reopened._request_finish()
    assert len(progress.load_attempts(path)) == 1
    stale = progress.load_active_session(path)
    another = ExamPracticeDialog("en", progress_path=path)
    assert another._resume_active_session(stale)
    assert another._session_finished
    assert len(progress.load_attempts(path)) == 1
    assert progress.load_companion_points(path) == 1
    reopened.close()
    another.close()


def test_companion_save_failure_retains_confirmed_choice(tmp_path, monkeypatch):
    _app()
    from aetherlab.ui.companion_dialog import CompanionPickerDialog
    from aetherlab.ui.student_views import StudentDashboard

    notices = []
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", lambda *args: notices.append(args[2]))
    def select(dialog):
        dialog._select_companion("photon")
        return QtWidgets.QDialog.DialogCode.Accepted
    monkeypatch.setattr(CompanionPickerDialog, "exec", select)
    for language in ("kk", "ru", "en"):
        path = tmp_path / f"companion-{language}.json"
        progress.save_companion_choice(path, "lab_bot")
        dashboard = StudentDashboard(path, language=language)
        before = path.read_bytes()
        with monkeypatch.context() as patch:
            _deny_read(patch, path)
            dashboard._choose_companion()
        assert dashboard.companion_id == "lab_bot"
        assert dashboard.companion_art.companion_id == "lab_bot"
        assert path.read_bytes() == before
        assert notices[-1]
        dashboard._choose_companion()
        assert progress.load_companion_choice(path) == "photon"
        dashboard.close()


def test_expired_mock_save_failure_stops_timer_and_retries_without_new_answers(tmp_path, monkeypatch):
    _app()
    from aetherlab.services.ent_physics_bank import mock_questions_for_language

    path = tmp_path / "expired.json"
    dialog = ExamPracticeDialog("en", progress_path=path)
    questions = mock_questions_for_language("en")[:2]
    dialog._begin_session(questions, "timed", seconds_left=1)
    dialog._answer_widgets[questions[0]["correct_indices"][0]].setChecked(True)
    original = progress.atomic_write_json

    def fail_history(target, payload):
        if target == path:
            raise PermissionError("history denied")
        return original(target, payload)

    with monkeypatch.context() as patch:
        patch.setattr(progress, "atomic_write_json", fail_history)
        dialog._deadline_monotonic = 0
        dialog._tick()
    assert not dialog._timer.isActive()
    assert dialog._seconds_left == 0
    assert dialog._completion_pending and not dialog._session_finished
    frozen = list(dialog._answers)
    dialog._next_question()
    dialog._previous()
    dialog._check_answer()
    assert dialog._index == 0 and dialog._answers == frozen
    state = progress.load_active_session(path)
    assert state["completion_pending"] and state["seconds_left"] == 0
    # Retry must not show the ordinary early-finish confirmation at timeout.
    monkeypatch.setattr(dialog, "_confirm_exam_action", lambda *args: pytest.fail("unexpected confirmation"))
    dialog._request_finish()
    assert dialog._session_finished and len(progress.load_attempts(path)) == 1
    assert dialog._answers == frozen
    dialog.close()


def test_successful_result_with_failed_cleanup_resumes_completed_snapshot(tmp_path, monkeypatch):
    _app()
    path = tmp_path / "committed.json"
    questions = questions_for_language("en", "kinematics")[:2]
    dialog = ExamPracticeDialog("en", progress_path=path)
    dialog._begin_session(questions, "practice")
    dialog._answer_widgets[questions[0]["correct_indices"][0]].setChecked(True)
    with monkeypatch.context() as patch:
        patch.setattr("aetherlab.ui.exam_practice.clear_active_session", lambda path: None)
        dialog._finish_session()
    assert dialog._session_finished
    state = progress.load_active_session(path)
    assert state is not None and state["completion_pending"]
    assert state["answers"][0] == tuple(questions[0]["correct_indices"])
    reopened = ExamPracticeDialog("en", progress_path=path)
    assert reopened._resume_active_session(state)
    assert reopened._session_finished and reopened._stack.currentIndex() == 2
    assert not reopened._choices_host.isEnabled()
    assert len(progress.load_attempts(path)) == 1
    assert progress.load_companion_points(path) == 1
    assert reopened._answers == dialog._answers
    dialog.close()
    reopened.close()
