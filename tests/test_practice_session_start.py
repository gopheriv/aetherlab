"""A different setup action must not silently replace an interrupted attempt."""
import os
import stat
from uuid import uuid4

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

from aetherlab.services.ent_physics_bank import mock_questions_for_language, questions_for_language
from aetherlab.services.ent_practice_progress import (
    _active_session_path,
    load_active_session,
    load_attempts,
    record_attempt,
    save_active_session,
)
from aetherlab.ui.exam_practice import ExamPracticeDialog
from aetherlab.ui.qt_compat import QtWidgets

_APP = None


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("mode", ("practice", "timed", "mistake_review"))
@pytest.mark.parametrize("choice", ("Cancel", "Yes", "No"))
def test_review_mistakes_resolves_saved_attempt_before_replacement(language, mode, choice, tmp_path, monkeypatch):
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert _APP.platformName() == "offscreen"
    path = tmp_path / "student.json"
    review_question = next(q for q in mock_questions_for_language(language) if q["kind"] == "multi")
    record_attempt(path, language=language, topic_results={},
                   question_results={review_question["id"]: False}, score=0, possible_points=2)
    questions = (questions_for_language(language) if mode == "practice" else mock_questions_for_language(language))[:2]
    attempt_id = str(uuid4())
    assert save_active_session(path, {
        "question_ids": [q["id"] for q in questions], "answers": [questions[0]["correct_indices"], None],
        "index": 1, "seconds_left": 120, "mode": mode, "language": language, "attempt_id": attempt_id,
    })
    before = _active_session_path(path).read_bytes()
    confirmations = []
    dialog = ExamPracticeDialog(language, progress_path=path)
    monkeypatch.setattr(dialog, "_confirm_exam_action", lambda action: (
        confirmations.append(action) or getattr(QtWidgets.QMessageBox.StandardButton, choice)))
    try:
        dialog._mistakes_button.click()
        assert confirmations == ["resume"], "Mistake review bypassed the saved-attempt decision"
        state = load_active_session(path)
        if choice == "Cancel":
            assert _active_session_path(path).read_bytes() == before
            assert not dialog._questions and dialog._stack.currentIndex() == 0
        elif choice == "Yes":
            assert dialog._attempt_id == attempt_id and dialog._mode == mode
            assert dialog._answers == [tuple(questions[0]["correct_indices"]), None]
            assert dialog._index == 1 and dialog._seconds_left <= 120
            assert state["attempt_id"] == attempt_id
        else:
            assert dialog._mode == "mistake_review" and dialog._attempt_id != attempt_id
            assert [q["id"] for q in dialog._questions] == [review_question["id"]]
            assert state["attempt_id"] == dialog._attempt_id
    finally:
        dialog._timer.stop()
        dialog._session_finished = True
        dialog.close()
        dialog.deleteLater()
        _APP.processEvents()


@pytest.fixture
def saved_attempt(tmp_path, monkeypatch):
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert _APP.platformName() == "offscreen"
    monkeypatch.setattr("aetherlab.services.mathtext.render_math", lambda *a, **k: None)
    opened = []

    def create(language, *, pending=False, valid_bank=True, mistake=True, saved_language=None):
        path = tmp_path / f"student-{len(opened)}.json"
        old_language = saved_language or language
        question = mock_questions_for_language(old_language)[0]
        if mistake:
            record_attempt(path, language=old_language, topic_results={},
                           question_results={question["id"]: False})
        saved_question = question if valid_bank else questions_for_language(old_language)[0]
        attempt_id = str(uuid4())
        assert save_active_session(path, {
            "question_ids": [saved_question["id"]], "answers": [saved_question["correct_indices"]],
            "index": 0, "seconds_left": 120, "mode": "timed", "language": old_language,
            "attempt_id": attempt_id, "completion_pending": pending,
        })
        dialog = ExamPracticeDialog(language, progress_path=path)
        opened.append(dialog)
        return dialog, path, attempt_id

    yield create
    for dialog in opened:
        dialog._timer.stop()
        dialog._session_finished = True
        dialog.close()
        dialog.deleteLater()
    _APP.processEvents()


def trigger(dialog, origin):
    (dialog._start_button if origin == "start" else dialog._mistakes_button).click()


@pytest.mark.skipif(os.name != "nt", reason="Windows read-only unlink semantics")
@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("origin", ("start", "mistakes"))
def test_restart_refusal_preserves_snapshot_and_retry(language, origin, saved_attempt, monkeypatch):
    dialog, path, attempt_id = saved_attempt(language)
    active = _active_session_path(path)
    before = active.read_bytes()
    decisions = []
    monkeypatch.setattr(dialog, "_confirm_exam_action", lambda action: (
        decisions.append(action) or QtWidgets.QMessageBox.StandardButton.No))
    active.chmod(stat.S_IREAD)
    try:
        trigger(dialog, origin)
        assert not dialog._questions and dialog._stack.currentIndex() == 0
        assert dialog._storage_notice.text() == dialog._storage_text["restart_error"]
        assert active.read_bytes() == before
    finally:
        active.chmod(stat.S_IREAD | stat.S_IWRITE)
    trigger(dialog, origin)
    assert decisions == ["resume", "resume"]
    assert dialog._questions and dialog._attempt_id != attempt_id
    assert not dialog._storage_notice.text()
    assert load_active_session(path)["attempt_id"] == dialog._attempt_id


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("origin", ("start", "mistakes"))
def test_unreadable_snapshot_blocks_both_entry_points_and_retry_resumes(language, origin, saved_attempt, monkeypatch):
    dialog, path, attempt_id = saved_attempt(language)
    active = _active_session_path(path)
    before = active.read_bytes()
    original_read = type(active).read_text
    decisions = []
    monkeypatch.setattr(dialog, "_confirm_exam_action", lambda action: (
        decisions.append(action) or QtWidgets.QMessageBox.StandardButton.Yes))

    def denied(candidate, *args, **kwargs):
        if candidate == active:
            raise PermissionError("owned snapshot read refusal")
        return original_read(candidate, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(type(active), "read_text", denied)
        trigger(dialog, origin)
    assert not decisions and not dialog._questions
    assert dialog._storage_notice.text() == dialog._storage_text["resume_error"]
    assert active.read_bytes() == before
    trigger(dialog, origin)
    assert decisions == ["resume"]
    assert dialog._attempt_id == attempt_id and dialog._mode == "timed"
    assert not dialog._storage_notice.text()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("origin", ("start", "mistakes"))
def test_unresumable_snapshot_is_not_replaced_by_review(language, origin, saved_attempt, monkeypatch):
    dialog, path, _attempt_id = saved_attempt(language, valid_bank=False)
    active = _active_session_path(path)
    before = active.read_bytes()
    monkeypatch.setattr(dialog, "_confirm_exam_action", lambda _: QtWidgets.QMessageBox.StandardButton.Yes)
    trigger(dialog, origin)
    assert not dialog._questions and dialog._stack.currentIndex() == 0
    assert dialog._storage_notice.text() == dialog._storage_text["resume_error"]
    assert active.read_bytes() == before


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("origin", ("start", "mistakes"))
def test_resuming_pending_result_from_setup_records_once(language, origin, saved_attempt, monkeypatch):
    dialog, path, attempt_id = saved_attempt(language, pending=True)
    monkeypatch.setattr(dialog, "_confirm_exam_action", lambda _: QtWidgets.QMessageBox.StandardButton.Yes)
    trigger(dialog, origin)
    assert dialog._session_finished and dialog._stack.currentIndex() == 2
    assert dialog._mode == "timed" and dialog._attempt_id == attempt_id
    assert load_active_session(path) is None
    attempts = load_attempts(path)
    assert len(attempts) == 2  # one seeded mistake plus the completed saved attempt
    assert sum(attempt.get("attempt_id") == attempt_id for attempt in attempts) == 1
    dialog._finish_session()
    assert len(load_attempts(path)) == 2


@pytest.mark.parametrize("language,old_language", (("kk", "ru"), ("ru", "en"), ("en", "kk")))
@pytest.mark.parametrize("origin", ("start", "mistakes"))
def test_resume_uses_saved_language_for_both_setup_actions(language, old_language, origin, saved_attempt, monkeypatch):
    dialog, path, attempt_id = saved_attempt(language, saved_language=old_language)
    monkeypatch.setattr(dialog, "_confirm_exam_action", lambda _: QtWidgets.QMessageBox.StandardButton.Yes)
    trigger(dialog, origin)
    assert dialog._language == old_language and dialog._attempt_id == attempt_id
    assert load_active_session(path)["language"] == old_language


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_empty_mistakes_never_replace_a_saved_attempt(language, saved_attempt, monkeypatch):
    dialog, path, _attempt_id = saved_attempt(language, mistake=False)
    active = _active_session_path(path)
    before = active.read_bytes()
    assert not dialog._mistakes_button.isEnabled()
    monkeypatch.setattr(dialog, "_confirm_exam_action", lambda _: pytest.fail("No replacement action is available"))
    dialog._start_mistake_review()
    assert not dialog._questions and active.read_bytes() == before


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("origin", ("start", "mistakes"))
def test_removal_verification_failure_blocks_start_until_retry(language, origin, saved_attempt, monkeypatch):
    dialog, path, attempt_id = saved_attempt(language)
    original_load = load_active_session
    reads, decisions = [], []

    def interrupted_verification(candidate):
        reads.append(candidate)
        if len(reads) == 2:
            raise PermissionError("owned verification-read interruption")
        return original_load(candidate)

    monkeypatch.setattr("aetherlab.ui.exam_practice.load_active_session", interrupted_verification)
    monkeypatch.setattr(dialog, "_confirm_exam_action", lambda action: (
        decisions.append(action) or QtWidgets.QMessageBox.StandardButton.No))
    trigger(dialog, origin)
    assert not dialog._questions and dialog._stack.currentIndex() == 0
    assert dialog._storage_notice.text() == dialog._storage_text["restart_error"]
    assert not _active_session_path(path).exists()
    trigger(dialog, origin)
    assert decisions == ["resume"]  # removal already succeeded on the first try
    assert dialog._questions and dialog._attempt_id != attempt_id
    assert not dialog._storage_notice.text()
    assert original_load(path)["attempt_id"] == dialog._attempt_id
