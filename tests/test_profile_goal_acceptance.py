"""Localized profile/goal controls must match their actual local semantics."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aetherlab.services.student_profiles import StudentProfileStore
from aetherlab.ui.exam_practice import ExamPracticeDialog
from aetherlab.ui.profile_dialog import _COPY, StudentProfileDialog
from aetherlab.ui.qt_compat import QtCore, QtGui, QtWidgets
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
        assert "username" not in _COPY[language]["invalid_username"].lower()
        assert "username" not in _COPY[language]["duplicate_username"].lower()
    assert dialog.avatar.accessibleName().startswith({"kk": "Профиль суреті", "ru": "Фото профиля", "en": "Profile photo"}[language])
    dialog.close()
    dashboard.close()
    title.close()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_unset_exam_calendar_opens_today_without_assigning_a_goal_date(language, tmp_path):
    from PyQt6 import QtTest

    app = _app()
    dialog = ExamPracticeDialog(language, progress_path=tmp_path / "calendar.json")
    dialog.show()
    app.processEvents()
    edit = dialog._exam_date
    before = edit.date()
    assert before == edit.minimumDate()
    calendar = edit.calendarWidget()
    QtTest.QTest.mouseClick(edit, QtCore.Qt.MouseButton.LeftButton,
                          pos=QtCore.QPoint(edit.width() - 8, edit.height() // 2))
    app.processEvents()
    assert calendar.isVisible()
    today = QtCore.QDate.currentDate()
    assert (calendar.yearShown(), calendar.monthShown()) == (today.year(), today.month())
    assert edit.date() == before, "Opening the calendar silently assigns a date"
    month_button = calendar.findChild(QtWidgets.QToolButton, "qt_calendar_monthbutton")
    assert month_button is not None
    assert month_button.palette().color(QtGui.QPalette.ColorRole.ButtonText).name() == "#18283d"
    view = calendar.findChild(QtWidgets.QAbstractItemView)
    assert view.palette().color(QtGui.QPalette.ColorRole.Base).name() == "#ffffff"
    assert view.palette().color(QtGui.QPalette.ColorRole.Text).name() == "#18283d"
    calendar.window().hide()
    chosen = QtCore.QDate(2027, 3, 15)
    edit.setDate(chosen)
    QtTest.QTest.mouseClick(edit, QtCore.Qt.MouseButton.LeftButton,
                          pos=QtCore.QPoint(edit.width() - 8, edit.height() // 2))
    app.processEvents()
    assert (calendar.yearShown(), calendar.monthShown()) == (2027, 3)
    assert edit.date() == chosen
    calendar.window().hide()
    dialog.close()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_exam_calendar_has_readable_text_and_selection_colors(language, tmp_path):
    from PyQt6 import QtTest

    app = _app()
    dialog = ExamPracticeDialog(language, progress_path=tmp_path / "palette.json")
    dialog.show()
    app.processEvents()
    edit = dialog._exam_date
    QtTest.QTest.mouseClick(edit, QtCore.Qt.MouseButton.LeftButton,
                          pos=QtCore.QPoint(edit.width() - 8, edit.height() // 2))
    app.processEvents()
    calendar = edit.calendarWidget()
    view = calendar.findChild(QtWidgets.QAbstractItemView)
    assert view.palette().color(QtGui.QPalette.ColorRole.Base).name() == "#ffffff"
    assert view.palette().color(QtGui.QPalette.ColorRole.Text).name() == "#18283d"
    assert view.palette().color(QtGui.QPalette.ColorRole.Highlight).name() == "#486a91"
    assert view.palette().color(QtGui.QPalette.ColorRole.HighlightedText).name() == "#ffffff"
    calendar.window().hide()
    dialog.close()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_failed_goal_resave_replaces_old_success_and_preserves_draft(language, tmp_path, monkeypatch):
    from aetherlab.ui import exam_practice

    _app()
    path = tmp_path / "resave.json"
    dialog = ExamPracticeDialog(language, progress_path=path)
    dialog._weekly_goal.setValue(80)
    dialog._save_goals()
    before = path.read_bytes()
    assert dialog._topic_hint.text() == dialog._t["goals_saved"]
    dialog._weekly_goal.setValue(90)
    save = exam_practice.save_goals

    def fail_save(*args, **kwargs):
        raise PermissionError("Isolated goal file is locked")

    monkeypatch.setattr(exam_practice, "save_goals", fail_save)
    dialog._save_goals()
    error = exam_practice._STORAGE_TEXT[language]["goals_error"]
    assert dialog._topic_hint.text() == error
    assert dialog._weekly_goal.value() == 90
    assert path.read_bytes() == before
    monkeypatch.setattr(exam_practice, "save_goals", save)
    dialog._save_goals()
    assert dialog._topic_hint.text() == dialog._t["goals_saved"]
    assert path.read_bytes() != before
    dialog.close()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_goal_calendar_uses_selected_language_after_rebuild(language, tmp_path):
    _app()
    dialog = ExamPracticeDialog(language, progress_path=tmp_path / "locale.json")
    for target in (language, "ru", "en", "kk"):
        locale = QtCore.QLocale({"kk": "kk_KZ", "ru": "ru_RU", "en": "en_US"}[target])
        dialog._language_combo.setCurrentIndex(dialog._language_combo.findData(target))
        assert dialog._exam_date.locale().language() == locale.language()
        assert dialog._exam_date.calendarWidget().locale().language() == locale.language()
    dialog.close()
