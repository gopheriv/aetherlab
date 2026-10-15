"""Real offscreen controls must replace old stored answers after clearing."""
import os
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import fitz
import pytest

from aetherlab.services import ent_practice_progress as progress
from aetherlab.services.ent_physics_bank import mock_questions_for_language
from aetherlab.services.ent_practice_progress import load_active_session, load_attempts
from aetherlab.ui.exam_practice import ExamPracticeDialog
from aetherlab.ui.qt_compat import QtWidgets

_APP = None


def app():
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert _APP.platformName() == "offscreen", "This probe must never create native test windows"
    return _APP


def choose(dialog, answer):
    if dialog._questions[dialog._index]["kind"] == "matching":
        for row, index in enumerate(answer):
            widget = dialog._answer_widgets[row]
            widget.setCurrentIndex(widget.findData(index))
    else:
        for index in answer:
            dialog._answer_widgets[index].click()


def clear(dialog):
    if dialog._questions[dialog._index]["kind"] == "matching":
        for widget in dialog._answer_widgets:
            widget.setCurrentIndex(widget.findData(-1))
    else:
        for widget in dialog._answer_widgets:
            if widget.isChecked():
                widget.click()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("kind", ("multi", "matching"))
@pytest.mark.parametrize("mode", ("practice", "timed", "mistake_review"))
@pytest.mark.parametrize("route", ("next", "previous", "autosave", "close", "finish"))
def test_cleared_controls_replace_saved_answer(language, kind, mode, route, tmp_path, monkeypatch):
    application = app()
    # This case verifies answer capture/scoring/storage. Formula typesetting has
    # its own independent acceptance checks; the normal readable fallback runs.
    monkeypatch.setattr("aetherlab.services.mathtext.render_math", lambda *a, **k: None)
    bank = mock_questions_for_language(language)
    target = next(question for question in bank if question["kind"] == kind)
    others = [question for question in bank if question["id"] != target["id"]][:2]
    questions = (others[0], target, others[1]) if route == "previous" else (target, *others)
    target_index = 1 if route == "previous" else 0
    path = tmp_path / "student.json"
    dialog = ExamPracticeDialog(language, progress_path=path)
    monkeypatch.setattr(dialog, "_confirm_exam_action", lambda _: QtWidgets.QMessageBox.StandardButton.Yes)
    try:
        dialog._begin_session(questions, mode)
        if target_index:
            dialog._next.click()
        choose(dialog, target["correct_indices"])
        assert dialog._read_answer() == tuple(target["correct_indices"])
        dialog._next.click()
        dialog._back.click()
        assert dialog._index == target_index
        assert dialog._answers[target_index] == tuple(target["correct_indices"])
        clear(dialog)
        assert dialog._read_answer() is None
        if route == "next":
            dialog._next.click()
        elif route == "previous":
            dialog._back.click()
        elif route == "autosave":
            assert dialog._persist_active_session()
        elif route == "close":
            dialog.reject()
        else:
            dialog._finish.click()
        application.processEvents()
        assert dialog._answers[target_index] is None, "A cleared response still grades/saves the previous selection"
        if route == "finish":
            attempt = load_attempts(path)[-1]
            assert attempt["score"] == 0
            assert attempt["possible_points"] == (0 if mode == "practice" else 4)
            assert load_active_session(path) is None
            assert dialog._stack.currentIndex() == 2
        else:
            saved = load_active_session(path)
            assert saved is not None and saved["answers"][target_index] is None
    finally:
        dialog._timer.stop()
        dialog._session_finished = True
        dialog.close()
        dialog.deleteLater()
        application.processEvents()


@pytest.fixture
def make_dialog(tmp_path, monkeypatch):
    application = app()
    monkeypatch.setattr("aetherlab.services.mathtext.render_math", lambda *a, **k: None)
    opened = []

    def create(language, questions, mode, *, full_mock=False):
        path = tmp_path / f"student-{len(opened)}.json"
        dialog = ExamPracticeDialog(language, progress_path=path)
        opened.append(dialog)
        monkeypatch.setattr(dialog, "_confirm_exam_action", lambda _: QtWidgets.QMessageBox.StandardButton.Yes)
        dialog._full_mock = full_mock
        dialog._begin_session(questions, mode)
        return dialog, path

    yield create
    for dialog in opened:
        dialog._timer.stop()
        dialog._session_finished = True
        dialog.close()
        dialog.deleteLater()
    application.processEvents()


def question_pair(language, kind):
    bank = mock_questions_for_language(language)
    target = next(question for question in bank if question["kind"] == kind)
    other = next(question for question in bank if question["id"] != target["id"])
    return target, other


def saved_then_cleared(dialog, target):
    choose(dialog, target["correct_indices"])
    dialog._next.click()
    dialog._back.click()
    assert dialog._answers[0] == tuple(target["correct_indices"])
    clear(dialog)
    assert dialog._read_answer() is None


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("kind", ("multi", "matching"))
@pytest.mark.parametrize("mode", ("practice", "mistake_review"))
def test_check_of_cleared_response_never_keeps_old_points(language, kind, mode, make_dialog):
    target, other = question_pair(language, kind)
    dialog, path = make_dialog(language, (target, other), mode)
    saved_then_cleared(dialog, target)
    dialog._check.click()
    assert dialog._answers[0] is None
    assert 0 not in dialog._checked
    assert dialog._feedback.text() == dialog._t["choose"]
    assert dialog._persist_active_session()
    assert load_active_session(path)["answers"][0] is None
    dialog._finish.click()
    assert load_attempts(path)[-1]["score"] == 0


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("mode", ("practice", "timed", "mistake_review"))
@pytest.mark.parametrize("route", ("navigate", "autosave", "finish"))
def test_partial_matching_keeps_one_point_and_placeholder(language, mode, route, make_dialog):
    target, other = question_pair(language, "matching")
    dialog, path = make_dialog(language, (target, other), mode)
    choose(dialog, target["correct_indices"])
    dialog._next.click()
    dialog._back.click()
    row = dialog._answer_widgets[1]
    row.setCurrentIndex(row.findData(-1))
    expected = (target["correct_indices"][0], -1)
    if route == "navigate":
        dialog._next.click()
        dialog._back.click()
        assert dialog._read_answer() == expected
    else:
        assert dialog._persist_active_session()
    assert load_active_session(path)["answers"][0] == expected
    dialog._finish.click()
    assert dialog._answers[0] == expected
    attempt = load_attempts(path)[-1]
    assert attempt["score"] == 1
    assert attempt["possible_points"] == (2 if mode == "practice" else 3)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("kind", ("multi", "matching"))
@pytest.mark.parametrize("mode", ("practice", "mistake_review"))
def test_checked_answer_remains_committed(language, kind, mode, make_dialog):
    target, other = question_pair(language, kind)
    dialog, path = make_dialog(language, (target, other), mode)
    choose(dialog, target["correct_indices"])
    dialog._check.click()
    assert 0 in dialog._checked
    dialog._next.click()
    dialog._back.click()
    assert all(not control.isEnabled() for control in dialog._answer_widgets)
    # A programmatic widget reset must not rewrite an already checked response.
    if kind == "matching":
        clear(dialog)
    else:
        for control in dialog._answer_widgets:
            control.setChecked(False)
    dialog._capture_current_answer()
    dialog._check_answer()
    assert dialog._persist_active_session()
    assert load_active_session(path)["answers"][0] == tuple(target["correct_indices"])
    dialog._finish.click()
    assert load_attempts(path)[-1]["score"] == 2


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("kind", ("multi", "matching"))
@pytest.mark.parametrize("mode", ("practice", "timed", "mistake_review"))
def test_pending_result_retry_preserves_cleared_response(language, kind, mode, make_dialog, monkeypatch):
    target, other = question_pair(language, kind)
    dialog, path = make_dialog(language, (target, other), mode)
    saved_then_cleared(dialog, target)

    def denied(*args, **kwargs):
        raise PermissionError("owned result write refusal")

    with monkeypatch.context() as patch:
        patch.setattr("aetherlab.ui.exam_practice.record_attempt", denied)
        dialog._finish.click()
    assert dialog._completion_pending and not dialog._session_finished
    assert load_active_session(path)["answers"][0] is None
    assert not dialog._choices_host.isEnabled()
    # Retry must use the frozen result even if controls are changed in code.
    if kind == "matching":
        choose(dialog, target["correct_indices"])
    else:
        for index in target["correct_indices"]:
            dialog._answer_widgets[index].setChecked(True)
    dialog._finish.click()
    assert dialog._session_finished and dialog._answers[0] is None
    assert load_attempts(path)[-1]["score"] == 0
    dialog._finish_session()
    assert len(load_attempts(path)) == 1


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("kind", ("multi", "matching"))
def test_full_mock_clear_is_unanswered_and_scores_48_of_50(language, kind, make_dialog):
    questions = mock_questions_for_language(language)
    dialog, path = make_dialog(language, questions, "timed", full_mock=True)
    target_index = next(index for index, question in enumerate(questions) if question["kind"] == kind)
    assert len(questions) == 40 and not dialog._proctor_enabled
    assert dialog._seconds_left == 90 * 60
    for index, question in enumerate(questions):
        assert dialog._index == index
        choose(dialog, question["correct_indices"])
        if index < len(questions) - 1:
            dialog._next.click()
    while dialog._index > target_index:
        dialog._back.click()
    clear(dialog)
    dialog._finish.click()
    attempt = load_attempts(path)[-1]
    assert attempt["score"] == 48 and attempt["possible_points"] == 50
    assert attempt["full_mock"] is True
    assert dialog._answers[target_index] is None
    assert dialog._format_answer(None, questions[target_index]) in dialog._review.toPlainText()
    assert "48" in dialog._score.text() and "50" in dialog._score.text()
    assert load_active_session(path) is None


@pytest.mark.skipif(os.name != "nt", reason="Windows read-only replacement semantics")
@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("kind", ("multi", "matching"))
def test_read_only_snapshot_keeps_old_bytes_and_retry_saves_clear(language, kind, make_dialog):
    import stat
    target, other = question_pair(language, kind)
    dialog, path = make_dialog(language, (target, other), "timed")
    saved_then_cleared(dialog, target)
    active = progress._active_session_path(path)
    before = active.read_bytes()
    active.chmod(stat.S_IREAD)
    try:
        assert not dialog._persist_active_session()
        assert active.read_bytes() == before
        assert dialog._storage_notice.text() == dialog._storage_text["session_error"]
        assert dialog._answers[0] is None
    finally:
        active.chmod(stat.S_IWRITE | stat.S_IREAD)
    assert dialog._persist_active_session()
    assert load_active_session(path)["answers"][0] is None
    assert not dialog._storage_notice.text()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("kind", ("multi", "matching"))
@pytest.mark.parametrize("mode", ("timed", "mistake_review"))
def test_reopen_restores_cleared_answer_in_same_attempt(language, kind, mode, make_dialog):
    target, other = question_pair(language, kind)
    dialog, path = make_dialog(language, (target, other), mode)
    saved_then_cleared(dialog, target)
    attempt_id = dialog._attempt_id
    dialog.reject()
    state = load_active_session(path)
    assert state is not None and state["answers"][0] is None
    resumed, _unused = make_dialog(language, (target, other), mode)
    resumed._progress_path = path
    assert resumed._resume_active_session(state)
    assert resumed._attempt_id == attempt_id
    assert resumed._answers[0] is None and resumed._read_answer() is None
    assert resumed._seconds_left <= state["seconds_left"]
    resumed._finish.click()
    assert load_attempts(path)[-1]["score"] == 0
    assert load_active_session(path) is None


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("kind", ("multi", "matching"))
def test_expiry_and_pdf_use_cleared_answer(language, kind, tmp_path, monkeypatch):
    application = app()
    bank = mock_questions_for_language(language)
    target = next(question for question in bank if question["kind"] == kind)
    other = next(question for question in bank if question["kind"] == "single")
    path = tmp_path / "student.json"
    pdf = tmp_path / "report.pdf"
    dialog = ExamPracticeDialog(language, progress_path=path)
    notices = []
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *a: (str(pdf), ""))
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", lambda *a: notices.append(a[-1]))
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", lambda *a: pytest.fail(str(a[-1])))
    try:
        dialog._begin_session((target, other), "timed")
        choose(dialog, target["correct_indices"])
        dialog._next.click()
        dialog._back.click()
        clear(dialog)
        assert dialog._read_answer() is None
        dialog._deadline_monotonic = time.monotonic() - 1
        dialog._tick()
        assert dialog._session_finished and not dialog._timer.isActive()
        attempt = load_attempts(path)[-1]
        assert attempt["score"] == 0 and attempt["possible_points"] == 3
        assert load_active_session(path) is None
        assert dialog._t["not_answered"] in dialog._review.toPlainText()
        dialog._save_pdf()
        assert pdf.exists() and len(notices) == 1
        with fitz.open(pdf) as report:
            text = " ".join(page.get_text() for page in report)
            assert "0/3" in text and dialog._t["not_answered"] in text
            assert all(abs(page.rect.width - 595.3) < 2 for page in report)
            assert sum(len(page.get_images()) for page in report) > 0
        assert dialog._answers == [None, None]
    finally:
        dialog._timer.stop()
        dialog._session_finished = True
        dialog.close()
        dialog.deleteLater()
        application.processEvents()
