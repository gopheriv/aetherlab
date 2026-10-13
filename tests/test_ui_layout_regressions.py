"""Responsive layout regressions from the UNT UI review."""

from __future__ import annotations

import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aetherlab.ui.qt_compat import QtCore, QtWidgets

_TEST_APP = None


def _app() -> QtWidgets.QApplication:
    from aetherlab.ui.fonts import install_ui_fonts

    # Keep one application alive: destroying it clears Qt's bundled font database.
    global _TEST_APP
    _TEST_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    install_ui_fonts()
    return _TEST_APP


def test_studio_palette_tokens_match_theme_defaults() -> None:
    from aetherlab.ui import style
    from aetherlab.ui.theme import DEFAULT_PRESET, Theme, get_preset

    assert DEFAULT_PRESET == "Studio Light"
    assert Theme().accent == style.CYAN == "#486A91"
    assert get_preset(DEFAULT_PRESET).bg == style.BG_DEEPEST == "#F4F7FB"
    assert "#F8F3EE" not in style.AETHERLAB_QSS


def test_ai_empty_state_fits_narrow_reference_width() -> None:
    from aetherlab.ui.shared_widgets import EmptyStateView

    app = _app()
    view = EmptyStateView()
    view.resize(558, 466)
    view.show()
    app.processEvents()

    assert view.width() == 558
    assert view._example_columns == 2
    assert view._ent_card.geometry().right() < view.width()
    assert view._setup_strip.geometry().right() < view.width()
    assert view._ent_title.text() == "UNT · Physics"
    assert view._key_label.toolTip() == "No API key configured"
    assert view._lib_label.toolTip() == "No books indexed"

    view.close()


def test_dashboard_reflows_cards_and_keeps_vertical_scroll_available(tmp_path) -> None:
    from aetherlab.ui.student_views import StudentDashboard

    app = _app()
    dashboard = StudentDashboard(tmp_path / "progress.json", language="en")
    dashboard.resize(676, 500)
    dashboard.show()
    app.processEvents()

    scroll = dashboard.findChild(QtWidgets.QScrollArea)
    assert scroll is not None
    content = scroll.widget()
    assert content is not None
    assert dashboard._metric_columns == 2
    assert dashboard._recommendation_columns == 1
    assert dashboard.companion_panel.isVisible()
    assert not dashboard.companion_panel.isWindow()
    assert dashboard.companion_panel.parentWidget() is content
    assert scroll.horizontalScrollBarPolicy() == QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert scroll.verticalScrollBar().maximum() > 0
    assert all(card.height() >= card.minimumSizeHint().height() for card in dashboard._recommendation_card_widgets)
    assert all(
        card.mapTo(content, QtCore.QPoint(0, 0)).x() + card.width() <= content.width()
        for card in dashboard._recommendation_card_widgets
    )

    dashboard.close()


def test_compact_sidebar_fits_short_window_without_overlapping_items() -> None:
    from aetherlab.ui.navigation import SidebarNav

    app = _app()
    sidebar = SidebarNav()
    sidebar.set_language("kk")
    sidebar.resize(92, 460)
    sidebar.show()
    app.processEvents()

    assert sidebar._dense
    assert all(first.geometry().bottom() < second.geometry().top()
               for first, second in zip(sidebar._buttons, sidebar._buttons[1:]))
    assert sidebar._buttons[-1].geometry().bottom() < sidebar.height()
    sidebar.close()


def test_main_student_shell_reflows_across_laptop_and_desktop_sizes(tmp_path) -> None:
    from dataclasses import replace

    from aetherlab.core.settings import load_settings
    from aetherlab.ui.main_window import PAGE_STUDENT_HOME, MainWindow

    app = _app()
    window = MainWindow(replace(load_settings(), data_dir=tmp_path, openai_api_key="test"))
    window.setMinimumSize(640, 480)
    window.show()
    for width, height in ((960, 640), (1280, 720), (1440, 900), (1920, 1080)):
        window.resize(width, height)
        app.processEvents()
        for language in ("kk", "ru", "en"):
            window._on_title_language_changed(language)
            window.sidebar.select(0)
            app.processEvents()
            assert window._workspace.currentIndex() == PAGE_STUDENT_HOME
            assert window.sidebar.label_for(0)
            assert window.student_dashboard.companion_panel.isVisible()
            assert not window.student_dashboard.companion_panel.isWindow()
            assert window.sidebar._buttons[-1].geometry().bottom() < window.sidebar.height()
    window.close()


def test_empty_progress_hides_mock_history_and_disables_review(tmp_path) -> None:
    from aetherlab.ui.student_views import ProgressOverview

    app = _app()
    progress = ProgressOverview(tmp_path / "progress.json", language="en")
    progress.show()
    app.processEvents()

    assert not progress.mock_history_card.isVisible()
    assert not progress.review_button.isEnabled()
    assert progress.rows.count() == 2  # illustration card and stretch
    assert progress.findChild(QtWidgets.QFrame, "ProgressEmpty").isVisible()

    progress.close()


def test_topic_search_filter_and_lesson_route_work_together(tmp_path) -> None:
    from aetherlab.services.ent_practice_progress import record_attempt
    from aetherlab.ui.student_views import TopicCatalogView

    app = _app()
    path = tmp_path / "progress.json"
    record_attempt(path, language="en", topic_results={"kinematics": {"correct": 1, "total": 1}}, score=1, possible_points=1)
    view = TopicCatalogView(path, language="en")
    view.resize(960, 640)
    view.show()
    app.processEvents()
    view.search.setText("kinematics")
    assert view.rows.count() == 1
    destinations = []
    view.learn_topic_requested.connect(destinations.append)
    card = view.rows.itemAt(0).widget()
    next(button for button in card.findChildren(QtWidgets.QPushButton) if button.text() == "Study").click()
    assert destinations == ["constant_acceleration"]
    view.filter.setCurrentIndex(view.filter.findData("new"))
    assert view.rows.count() == 0
    view.search.clear()
    assert view.rows.count() == 24
    view.close()


def test_practice_mode_cards_fit_and_single_answers_are_exclusive(tmp_path) -> None:
    from aetherlab.ui.exam_practice import ExamPracticeDialog

    app = _app()
    for language in ("kk", "ru", "en"):
        dialog = ExamPracticeDialog(language, progress_path=tmp_path / f"{language}.json")
        dialog.resize(640, 580)
        dialog.show()
        app.processEvents()
        scroll = dialog.findChild(QtWidgets.QScrollArea, "PracticeScroll")
        assert scroll.widget().width() <= scroll.viewport().width()
        dialog._mode_buttons[1].click()
        assert dialog._mode_combo.currentData() == "timed"
        dialog._mode_buttons[0].click()
        dialog._start()
        dialog._answer_widgets[0].click()
        dialog._answer_widgets[1].click()
        assert dialog._read_answer() == (1,)
        assert sum(control.isChecked() for control in dialog._answer_widgets) == 1
        assert not dialog._feedback.isVisible()
        dialog._check_answer()
        assert dialog._feedback.isVisible()
        dialog.close()


def test_closing_rail_practice_restores_the_previous_destination(tmp_path, monkeypatch) -> None:
    from dataclasses import replace

    from aetherlab.core.settings import load_settings
    from aetherlab.ui.main_window import PAGE_TOPICS, MainWindow

    app = _app()
    window = MainWindow(replace(load_settings(), data_dir=tmp_path, openai_api_key="test"))
    window.sidebar.select(1)
    monkeypatch.setattr(window, "open_exam_practice", lambda *_: None)
    window.sidebar.select(2)
    app.processEvents()
    assert window.sidebar.selected_index() == 1
    assert window._workspace.currentIndex() == PAGE_TOPICS
    assert window.title_bar.page_title.text() == window.sidebar.label_for(1)
    window.close()


def test_topic_cards_never_show_as_desktop_windows(tmp_path) -> None:
    from aetherlab.ui.student_views import TopicCatalogView

    app = _app()
    shown_windows = []

    class WatchShows(QtCore.QObject):
        def eventFilter(self, obj, event):  # noqa: N802
            if event.type() == QtCore.QEvent.Type.Show and isinstance(obj, QtWidgets.QWidget):
                if obj.isWindow() and obj.objectName() == "StudentCard":
                    shown_windows.append(obj)
            return False

    watcher = WatchShows()
    app.installEventFilter(watcher)
    try:
        view = TopicCatalogView(tmp_path / "progress.json", "kk")
        view.resize(1320, 750)
        view.show()
        for language in ("kk", "ru", "en"):
            view.set_language(language)
            view.search.setText("kinematics")
            view.search.clear()
            view.refresh()
            app.processEvents()
        assert not shown_windows
        assert all(card.parentWidget() is view.scroll.widget() for card, _, _ in view.cards)
        view.scroll.verticalScrollBar().setValue(view.scroll.verticalScrollBar().maximum())
        view.search.setText("kinematics")
        assert view.scroll.verticalScrollBar().value() == 0
        view.close()
    finally:
        app.removeEventFilter(watcher)


def test_cancelled_timed_practice_stops_without_saving_a_result(tmp_path) -> None:
    from aetherlab.services.ent_practice_progress import load_attempts
    from aetherlab.ui.exam_practice import ExamPracticeDialog

    app = _app()
    path = tmp_path / "progress.json"
    dialog = ExamPracticeDialog("en", progress_path=path)
    dialog.show()
    dialog._mode_buttons[1].click()
    dialog._start()
    assert dialog._timer.isActive()
    dialog.reject()
    app.processEvents()
    assert not dialog._timer.isActive()
    assert load_attempts(path) == []
    dialog.deleteLater()


def test_language_changes_keep_unsaved_practice_setup(tmp_path) -> None:
    from aetherlab.services.ent_practice_progress import load_goals
    from aetherlab.ui.exam_practice import ExamPracticeDialog

    app = _app()
    path = tmp_path / "progress.json"
    dialog = ExamPracticeDialog("en", progress_path=path)
    dialog._topic_combo.setCurrentIndex(dialog._topic_combo.findData("fluids"))
    dialog._difficulty_combo.setCurrentIndex(dialog._difficulty_combo.findData("C"))
    dialog._mode_buttons[1].click()
    dialog._target_score.setValue(42)
    dialog._weekly_goal.setValue(80)
    dialog._weekly_mock_day.setCurrentIndex(dialog._weekly_mock_day.findData(4))
    exam_date = QtCore.QDate(2027, 6, 20)
    dialog._exam_date.setDate(exam_date)
    dialog._prep_level.setCurrentIndex(1)
    level = dialog._prep_level.currentData()
    for language in ("kk", "ru", "en"):
        dialog._language_combo.setCurrentIndex(dialog._language_combo.findData(language))
        app.processEvents()
        assert dialog._topic_combo.currentData() == "fluids"
        assert dialog._difficulty_combo.currentData() == "C"
        assert dialog._mode_combo.currentData() == "timed"
        assert dialog._mode_buttons[1].isChecked()
        assert dialog._target_score.value() == 42
        assert dialog._weekly_goal.value() == 80
        assert dialog._weekly_mock_day.currentData() == 4
        assert dialog._exam_date.date() == exam_date
        assert dialog._prep_level.currentData() == level
    dialog._save_goals()
    assert load_goals(path)["weekly_mock_day"] == 4
    dialog.close()
    dialog.deleteLater()


def test_weekly_mock_day_dashboard_reminds_and_offers_timed_shortcut(tmp_path) -> None:
    from aetherlab.services.ent_practice_progress import save_goals
    from aetherlab.ui.exam_practice import ExamPracticeDialog
    from aetherlab.ui.student_views import StudentDashboard

    app = _app()
    path = tmp_path / "progress.json"
    today = date.today()
    save_goals(path, {"weekly_mock_day": today.weekday()})
    dashboard = StudentDashboard(path, language="en")
    assert "Today" in dashboard.weekly_mock_label.text()
    assert not dashboard.weekly_mock_button.isHidden()
    requested = []
    dashboard.weekly_mock_requested.connect(lambda: requested.append(True))
    dashboard.weekly_mock_button.click()
    assert requested == [True]

    timed_dialog = ExamPracticeDialog(
        "en", progress_path=path, start_mode="timed"
    )
    assert timed_dialog._mode_combo.currentData() == "timed"
    assert timed_dialog._mode_buttons[1].isChecked()
    timed_dialog.close()
    timed_dialog.deleteLater()

    next_day = (today.weekday() + 2) % 7
    save_goals(path, {"weekly_mock_day": next_day})
    dashboard.refresh()
    assert "in 2 days" in dashboard.weekly_mock_label.text()
    assert dashboard.weekly_mock_button.isHidden()
    dashboard.close()
    app.processEvents()


def test_dashboard_weekly_mock_shortcut_opens_timed_practice(tmp_path) -> None:
    from dataclasses import replace

    from aetherlab.core.settings import load_settings
    from aetherlab.services.ent_practice_progress import save_goals
    from aetherlab.ui.main_window import MainWindow

    _app()
    settings = replace(
        load_settings(),
        data_dir=tmp_path,
        cache_path=tmp_path / "cache.sqlite3",
        chroma_path=tmp_path / "chroma",
        library_path=tmp_path / "library",
        openai_api_key="test-key",
        reference_sources_path=None,
    )
    window = MainWindow(settings)
    save_goals(
        window.ent_progress_path,
        {"weekly_mock_day": date.today().weekday()},
    )
    window.student_dashboard.refresh()
    opened = []
    window.open_exam_practice = lambda language, **kwargs: opened.append((language, kwargs))
    window.student_dashboard.weekly_mock_button.click()
    assert opened == [("kk", {"start_mode": "timed"})]
    window.close()


def test_practice_filters_prevent_empty_sets_and_results_save_once(tmp_path) -> None:
    from aetherlab.services.ent_practice_progress import load_attempts
    from aetherlab.ui.exam_practice import ExamPracticeDialog

    app = _app()
    path = tmp_path / "progress.json"
    dialog = ExamPracticeDialog("en", progress_path=path)
    dialog._mode_buttons[1].click()  # only the 40-question mock bank is a fixed, small bank
    dialog._difficulty_combo.setCurrentIndex(dialog._difficulty_combo.findData("C"))
    # The statics subset of the full mock contains only basic questions, so
    # advanced difficulty must become unavailable and fall back to all levels.
    dialog._topic_combo.setCurrentIndex(dialog._topic_combo.findData("statics"))
    assert dialog._difficulty_combo.currentData() == ""
    assert not dialog._difficulty_combo.model().item(dialog._difficulty_combo.findData("C")).isEnabled()
    dialog._start()
    assert dialog._questions
    dialog._finish_session()
    dialog._show_results()
    app.processEvents()
    assert len(load_attempts(path)) == 1
    dialog.close()
    dialog.deleteLater()


def test_review_action_opens_mistakes_and_disposes_dialogs(tmp_path, monkeypatch) -> None:
    from dataclasses import replace

    from aetherlab.core.settings import load_settings
    from aetherlab.services.ent_physics_bank import QUESTIONS
    from aetherlab.services.ent_practice_progress import record_attempt
    from aetherlab.ui.exam_practice import ExamPracticeDialog
    from aetherlab.ui.main_window import MainWindow

    app = _app()
    window = MainWindow(replace(load_settings(), data_dir=tmp_path, openai_api_key="test"))
    question = QUESTIONS[0]
    record_attempt(window.ent_progress_path, language="en", topic_results={question.topic: {"total": 1, "correct": 0}},
                   question_results={question.id: False}, score=0, possible_points=1)
    window.sidebar.select(3)
    opened = []

    def close_review(dialog):
        opened.append((dialog._mode, [item["id"] for item in dialog._questions]))
        dialog.reject()
        return QtWidgets.QDialog.DialogCode.Rejected

    monkeypatch.setattr(ExamPracticeDialog, "exec", close_review)
    for _ in range(2):
        window.progress_overview.review_button.click()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
        assert not window.findChildren(ExamPracticeDialog)
    assert opened == [("mistake_review", [question.id])] * 2
    window.close()
    app.processEvents()


def test_narrow_tutor_status_and_examples_fit_in_all_languages() -> None:
    from aetherlab.ui.fonts import install_ui_fonts
    from aetherlab.ui.shared_widgets import EmptyStateView
    from aetherlab.ui.style import AETHERLAB_QSS

    app = _app()
    install_ui_fonts()
    for language in ("en", "ru", "kk"):
        view = EmptyStateView()
        view.setStyleSheet(AETHERLAB_QSS)
        view.set_language(language)
        view.offer_ollama(1)
        view.resize(558, 466)
        view.show()
        app.processEvents()
        assert (view.width(), view.height()) == (558, 466)
        assert view._status_columns == 1
        assert view._setup_strip.geometry().bottom() < view.height()
        assert all(button.geometry().width() >= button.minimumSizeHint().width() for button in view._example_buttons)
        assert all(button.height() >= button.minimumSizeHint().height() for button in view._example_buttons)
        if language == "ru":
            assert all(button.width() == view._examples_widget.width() for button in view._example_buttons)
        view.close()
        view.deleteLater()
