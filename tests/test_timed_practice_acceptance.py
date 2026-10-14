"""Native timed-mode observations represented as focused regressions."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aetherlab.ui.exam_practice import ExamPracticeDialog
from aetherlab.ui.qt_compat import QtWidgets

_APP = None


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_timed_setup_hides_session_size_label_and_restores_practice_selection(language, tmp_path):
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    dialog = ExamPracticeDialog(language, progress_path=tmp_path / f"{language}.json")
    field = dialog._session_size.parentWidget()
    label = field.findChild(QtWidgets.QLabel)
    assert label is not None and label.text()
    dialog._session_size.setCurrentIndex(dialog._session_size.findData(100))
    dialog._mode_combo.setCurrentIndex(dialog._mode_combo.findData("timed"))
    assert field.isHidden(), "Timed setup leaves a Session size label without its control"
    next_language = {"kk": "ru", "ru": "en", "en": "kk"}[language]
    dialog._language_combo.setCurrentIndex(dialog._language_combo.findData(next_language))
    field = dialog._session_size.parentWidget()
    assert dialog._mode_combo.currentData() == "timed" and field.isHidden()
    dialog._mode_combo.setCurrentIndex(dialog._mode_combo.findData("practice"))
    assert not field.isHidden() and not dialog._session_size.isHidden()
    assert dialog._session_size.currentData() == 100
    dialog.close()
    direct = ExamPracticeDialog(language, progress_path=tmp_path / f"direct-{language}.json", start_mode="timed")
    assert direct._session_size.parentWidget().isHidden()
    direct.close()
