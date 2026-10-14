"""Confirmation controls follow the lesson locale; dismiss preserves an attempt."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aetherlab.services.ent_physics_bank import mock_questions_for_language, questions_for_language
from aetherlab.services.ent_practice_progress import (
    _active_session_path,
    load_active_session,
    save_active_session,
)
from aetherlab.ui.exam_practice import ExamPracticeDialog
from aetherlab.ui.qt_compat import QtCore, QtWidgets

_APP = None
_LABELS = {
    "kk": ("Жалғастыру", "Қайта бастау", "Бас тарту", "Сынақты аяқтау", "Сынақты жалғастыру"),
    "ru": ("Продолжить попытку", "Начать заново", "Отмена", "Завершить пробник", "Продолжить пробник"),
    "en": ("Resume attempt", "Start again", "Cancel", "Finish mock", "Continue mock"),
}


def _app():
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_dismissing_resume_preserves_exact_saved_answers_and_localizes_buttons(language, tmp_path):
    app = _app()
    path = tmp_path / f"resume-{language}.json"
    first = ExamPracticeDialog(language, progress_path=path)
    first._begin_session(mock_questions_for_language(language)[:2], "timed")
    first._answer_widgets[0].setChecked(True)
    first.close()
    state_path = _active_session_path(path)
    before = state_path.read_bytes()
    dialog = ExamPracticeDialog(language, progress_path=path)
    observations = []

    def dismiss():
        box = app.activeModalWidget()
        observations.append((tuple(button.text() for button in box.buttons()), box.escapeButton().text() if box.escapeButton() else None))
        box.reject()  # Native close/Escape, not an explicit Start again click.

    QtCore.QTimer.singleShot(0, dismiss)
    dialog._start()
    assert state_path.exists() and state_path.read_bytes() == before, "Closing Resume discards the saved attempt"
    assert not dialog._questions and dialog._stack.currentIndex() == 0
    assert set(observations[0][0]) == set(_LABELS[language][:3])
    assert observations[0][1] == _LABELS[language][2]
    assert load_active_session(path)["answers"][0] == (0,)
    dialog.close()


@pytest.mark.parametrize("choice", ("Yes", "No"))
def test_explicit_resume_or_start_again_uses_the_chosen_attempt(choice, tmp_path):
    app = _app()
    path = tmp_path / f"explicit-{choice}.json"
    first = ExamPracticeDialog("ru", progress_path=path)
    first._begin_session(mock_questions_for_language("ru")[:2], "timed")
    first._answer_widgets[0].setChecked(True)
    first.close()
    saved = load_active_session(path)
    dialog = ExamPracticeDialog("ru", progress_path=path)
    QtCore.QTimer.singleShot(0, lambda: app.activeModalWidget().button(getattr(QtWidgets.QMessageBox.StandardButton, choice)).click())
    dialog._start()
    if choice == "Yes":
        assert dialog._attempt_id == saved["attempt_id"]
        assert dialog._answers[0] == (0,) and dialog._mode == "timed"
    else:
        assert dialog._attempt_id != saved["attempt_id"]
        assert all(answer is None for answer in dialog._answers)
    dialog.close()


def test_unresumable_question_ids_are_not_silently_discarded(tmp_path):
    app = _app()
    path = tmp_path / "unknown.json"
    assert save_active_session(path, {
        # A valid exercise ID passes storage validation but is not in the
        # timed mock bank. Invalid global IDs are rejected by the loader.
        "question_ids": [questions_for_language("ru", "kinematics")[0]["id"]], "answers": [(0,)], "index": 0,
        "language": "ru", "mode": "timed", "seconds_left": 1000,
    })
    state_path = _active_session_path(path)
    before = state_path.read_bytes()
    dialog = ExamPracticeDialog("ru", progress_path=path)
    QtCore.QTimer.singleShot(0, lambda: app.activeModalWidget().button(QtWidgets.QMessageBox.StandardButton.Yes).click())
    dialog._start()
    assert not dialog._questions and state_path.read_bytes() == before
    assert not dialog._storage_notice.isHidden()
    dialog.close()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_timed_finish_is_localized_and_defaults_to_continue(language, tmp_path):
    app = _app()
    path = tmp_path / f"finish-{language}.json"
    dialog = ExamPracticeDialog(language, progress_path=path)
    dialog._begin_session(mock_questions_for_language(language)[:2], "timed")
    observations = []

    def decline():
        box = app.activeModalWidget()
        observations.append((tuple(button.text() for button in box.buttons()), box.defaultButton().text()))
        box.button(QtWidgets.QMessageBox.StandardButton.No).click()

    QtCore.QTimer.singleShot(0, decline)
    dialog._request_finish()
    assert set(observations[0][0]) == set(_LABELS[language][3:])
    assert observations[0][1] == _LABELS[language][4]
    assert not dialog._session_finished and dialog._timer.isActive()
    QtCore.QTimer.singleShot(0, lambda: app.activeModalWidget().button(QtWidgets.QMessageBox.StandardButton.Yes).click())
    dialog._request_finish()
    assert dialog._session_finished and not dialog._timer.isActive()
    dialog.close()
