"""Localization and illustration regressions for secondary study surfaces."""

from __future__ import annotations

import math
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aetherlab.ui.qt_compat import QtCore, QtWidgets

_APP = None


def _app() -> QtWidgets.QApplication:
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


def test_library_history_and_settings_follow_the_selected_language() -> None:
    from aetherlab.core.settings import load_settings
    from aetherlab.ui.library_panel import LibraryPanel
    from aetherlab.ui.main_window import SettingsDialog
    from aetherlab.ui.navigation import HistoryPanel

    _app()
    library = LibraryPanel()
    history = HistoryPanel()
    for language, title, clear_label in (
        ("kk", "Кітапхана", "Тазалау"),
        ("ru", "Библиотека", "Очистить"),
        ("en", "Library", "Clear"),
    ):
        library.set_language(language)
        history.set_language(language)
        assert library._title.text() == title
        assert history._clear_btn.text() == clear_label

    history.add_entry("Review Newton's laws", "cache-key", "rendered", 2)
    assert history._list.count() == 1
    history._clear_btn.click()
    assert history._list.count() == 0
    assert history._history_stack.currentWidget() is history._empty

    settings = SettingsDialog(load_settings())
    for language, provider_label, ollama_option in (
        ("kk", "Провайдер", "Жергілікті Ollama"),
        ("ru", "Провайдер", "Локальная Ollama"),
        ("en", "Provider", "Local Ollama"),
    ):
        settings.set_language(language)
        labels = [label.text() for label in settings.findChildren(QtWidgets.QLabel)]
        assert provider_label in labels
        assert settings._preset_combo.itemText(1) == ollama_option
    settings.close()
    library.close()
    history.close()


def test_command_lab_and_lesson_controls_retranslate_without_losing_values() -> None:
    from aetherlab.ui.command_bar import CommandBar
    from aetherlab.ui.lesson_view import LessonView
    from aetherlab.ui.simulation_panel import SimulationPanel

    _app()
    command = CommandBar()
    duration_index = command._duration.findData(120.0)
    command._duration.setCurrentIndex(duration_index)
    command.set_language("en")
    assert command._duration.itemText(duration_index) == "2 min"
    assert command.get_duration_target() == 120.0
    assert command.get_render_quality() == "m"

    simulation = SimulationPanel()
    lesson = LessonView()
    simulation.set_language("kk")
    lesson.set_language("kk")
    assert simulation._view_buttons[0].text() == "Көрініс"
    assert simulation._save_video_btn.text() == "Сақтау"
    assert lesson._empty.text().startswith("Тақырып енгізіп")
    assert lesson._video_empty_overlay.text() == "Бұл сабақтың бейнесі әлі жасалмаған."
    simulation.set_language("en")
    lesson.set_language("en")
    assert simulation._view_buttons[0].text() == "Canvas"
    assert lesson._tabs.tabText(0) == "Video"
    command.close()
    simulation.close()
    lesson.close()


def test_orbit_electrons_stay_on_their_paths_and_art_has_clearance() -> None:
    from aetherlab.ui.study_visuals import OrbitArt

    for orbit_angle, point_angle in ((-32, 0), (32, 180), (90, 0)):
        point = OrbitArt.orbit_point(orbit_angle, point_angle)
        rotation = math.radians(-orbit_angle)
        x = point.x() * math.cos(rotation) - point.y() * math.sin(rotation)
        y = point.x() * math.sin(rotation) + point.y() * math.cos(rotation)
        assert (x / 91) ** 2 + (y / 37) ** 2 == pytest.approx(1.0, abs=1e-9)

    for width, height in ((130, 130), (220, 150), (240, 220)):
        scale = OrbitArt.drawing_scale(width, height)
        assert min(width, height) / 2 - 101 * scale >= 20

    _app()
    art = OrbitArt()
    assert art.testAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
