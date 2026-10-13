"""Localized profile/goal controls must match their actual local semantics."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aetherlab.services.student_profiles import StudentProfileStore
from aetherlab.ui.exam_practice import ExamPracticeDialog
from aetherlab.ui.profile_dialog import StudentProfileDialog
from aetherlab.ui.qt_compat import QtWidgets
from aetherlab.ui.shared_widgets import TitleBar
from aetherlab.ui.student_views import StudentDashboard

_APP = None


def _app():
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_goal_suffix_follows_language_and_preserves_unsaved_values(language, tmp_path):
    _app()
    suffixes = {"kk": " / апта", "ru": " / неделю", "en": " / week"}
    dialog = ExamPracticeDialog(language, progress_path=tmp_path / "progress.json")
    dialog._weekly_goal.setValue(80)
    assert dialog._weekly_goal.suffix() == suffixes[language]
    for target in ("en", "ru", "kk"):
        dialog._language_combo.setCurrentIndex(dialog._language_combo.findData(target))
        assert dialog._weekly_goal.value() == 80
        assert dialog._weekly_goal.suffix() == suffixes[target]
    dialog.close()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_profile_accessible_labels_follow_ui_language_and_identity(language, tmp_path):
    _app()
    dashboard = StudentDashboard(tmp_path / "progress.json", language, profile_name="Audit Alpha")
    title = TitleBar()
    title.set_profile("Audit Alpha")
    for target in (language, "en", "ru", "kk"):
        dashboard.set_language(target)
        title.set_language(target)
        for button in (dashboard.profile_button, title.profile_button):
            assert button.name == "Audit Alpha"
            assert button.toolTip() in button.accessibleName()
            assert "Audit Alpha" in button.accessibleName()
            if target != "en":
                assert "Open profile" not in button.accessibleName()
        dashboard.set_profile("Audit Beta")
        title.set_profile("Audit Beta")
        assert "Audit Beta" in title.profile_button.accessibleName()
        assert "Audit Beta" in dashboard.profile_button.accessibleName()
        dashboard.set_profile("Audit Alpha")
        title.set_profile("Audit Alpha")
    dialog = StudentProfileDialog(StudentProfileStore(tmp_path / "profiles"), language)
    labels = [widget.text() for widget in dialog.findChildren(QtWidgets.QLabel)]
    if language == "kk":
        assert "Пайдаланушы аты" in labels and "Username" not in labels
    assert dialog.avatar.accessibleName().startswith({"kk": "Профиль суреті", "ru": "Фото профиля", "en": "Profile photo"}[language])
    dialog.close()
    dashboard.close()
    title.close()
