"""Offscreen-Qt regression tests for UI bugs found in the feature audit.

Covers: F62 (negative parameter support), F71 (settings Apply actually applies),
F73 (cancel keeps Run disabled until the worker finishes).
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtWidgets = pytest.importorskip("PyQt6.QtWidgets", reason="PyQt6 required")

from aetherlab.core.settings import AppSettings  # noqa: E402
from aetherlab.ui.widgets import CommandBar, ParameterDock  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def _settings(tmp_path, api_key=None):
    return AppSettings(
        data_dir=tmp_path, cache_path=tmp_path / "c.sqlite3",
        chroma_path=tmp_path / "chroma", library_path=tmp_path / "library",
        openai_api_key=api_key, openai_base_url=None,
        llm_model="test-model", llm_timeout_seconds=5.0,
    )


# ── F62: negative parameter values must be representable ────────────────────


def test_parameter_dock_supports_negative_values(qapp):
    dock = ParameterDock()
    dock.set_variables({"charge": -1.0})
    _, spinbox, _, _ = dock._sliders["charge"]
    assert spinbox.value() == pytest.approx(-1.0)
    assert spinbox.minimum() < 0, "spinbox must allow negatives for negative originals"


def test_parameter_dock_slider_round_trips_negative(qapp):
    dock = ParameterDock()
    got: list[tuple[str, float]] = []
    dock.parameter_changed.connect(lambda n, v: got.append((n, v)))
    dock.set_variables({"charge": -1.0})
    slider, spinbox, _, _ = dock._sliders["charge"]
    # Move slider to its minimum -> most negative value, spinbox follows.
    slider.setValue(0)
    assert got and got[-1][1] < 0
    assert spinbox.value() == pytest.approx(got[-1][1])


def test_parameter_dock_positive_params_stay_non_negative(qapp):
    dock = ParameterDock()
    dock.set_variables({"mass": 1.0})
    slider, spinbox, _, _ = dock._sliders["mass"]
    assert spinbox.minimum() == 0.0, "positive params must not allow negative (e.g. mass)"
    slider.setValue(0)
    assert spinbox.value() == pytest.approx(0.0)


def test_parameter_dock_reset_restores_negative_original(qapp):
    dock = ParameterDock()
    dock.set_variables({"charge": -1.0})
    dock._on_spinbox_change("charge", 0.5)
    dock._reset_param("charge", -1.0)
    _, spinbox, _, _ = dock._sliders["charge"]
    assert spinbox.value() == pytest.approx(-1.0)


# ── F71: Settings dialog values must actually be applied ────────────────────


def test_apply_settings_updates_main_window(qapp, tmp_path):
    from aetherlab.ui.main_window import MainWindow

    window = MainWindow(settings=_settings(tmp_path))
    try:
        window._apply_settings({
            "model": "new-model", "api_key": "new-key", "base_url": "http://new",
            "library_path": str(tmp_path / "lib2"), "data_dir": str(tmp_path),
        })
        assert window.settings.llm_model == "new-model"
        assert window.settings.openai_api_key == "new-key"
        assert window.settings.openai_base_url == "http://new"
        assert window.settings.library_path == tmp_path / "lib2"
        assert "new-model" in window.statusBar().currentMessage()
    finally:
        window.close()


# ── F73: cancelling must not re-enable Run while the worker runs ────────────


def test_set_cancelling_keeps_run_disabled(qapp):
    bar = CommandBar()
    bar.set_busy(True)
    bar.set_cancelling()
    assert not bar.run_button.isEnabled(), "Run must stay disabled while cancelling"
    assert not bar.cancel_button.isEnabled(), "Cancel must not be re-clickable"
    assert "Cancelling" in bar.cancel_button.text()
    # Worker finished -> set_busy(False) restores everything.
    bar.set_busy(False)
    assert bar.run_button.isEnabled()
    assert bar.cancel_button.isEnabled()
    assert "Cancel" in bar.cancel_button.text()


# ── WP8: live theme switching restyles app + canvas + persists ──────────────


def test_apply_theme_live_switch_and_persist(qapp, tmp_path):
    import json

    from aetherlab.ui.live_canvas import _resolve_color
    from aetherlab.ui.main_window import MainWindow
    from aetherlab.ui.theme import current_theme, get_preset

    window = MainWindow(settings=_settings(tmp_path))
    try:
        assert "#06B6D4" in window.styleSheet()  # default accent
        light = get_preset("Solar Light")
        window._apply_theme(light)

        assert current_theme().name == "Solar Light"
        assert light.accent in window.styleSheet()
        assert "#06B6D4" not in window.styleSheet()
        # Canvas curve role now resolves to the new palette.
        assert _resolve_color("curve1") == light.curve1
        # Persisted for next launch, including the scene palette for renders.
        prefs = json.loads((tmp_path / "ui_prefs.json").read_text(encoding="utf-8"))
        assert prefs["theme"]["accent"] == light.accent
        assert prefs["scene_palette"]["background"] == light.bg
    finally:
        window.close()


def test_startup_loads_persisted_theme(qapp, tmp_path):
    from aetherlab.ui.main_window import MainWindow
    from aetherlab.ui.theme import get_preset, save_theme

    save_theme(get_preset("Emerald"), tmp_path)
    window = MainWindow(settings=_settings(tmp_path))
    try:
        assert get_preset("Emerald").accent in window.styleSheet()
    finally:
        window.close()


def test_appearance_editor_round_trip(qapp):
    from aetherlab.ui.main_window import AppearanceEditor
    from aetherlab.ui.theme import get_preset

    editor = AppearanceEditor(get_preset("Nebula"))
    theme = editor.theme()
    assert theme.accent == get_preset("Nebula").accent
    assert theme.name == "Nebula"
