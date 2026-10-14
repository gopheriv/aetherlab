"""Saved Settings default quality applies to the command bar at startup (Stage B)."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TEST_APP = None


def _app():
    from aetherlab.ui.fonts import install_ui_fonts
    from aetherlab.ui.qt_compat import QtWidgets

    # Keep one application alive: dropping it deletes every C++ widget wrapper.
    global _TEST_APP
    _TEST_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    install_ui_fonts()
    return _TEST_APP


def _make_window(tmp_path: Path, saved: dict | None):
    from aetherlab.core.settings import load_settings
    from aetherlab.ui.main_window import MainWindow

    if saved is not None:
        (tmp_path / "settings.json").write_text(json.dumps(saved), encoding="utf-8")
    app = _app()
    settings = replace(load_settings(), data_dir=tmp_path / "data", openai_api_key="test")
    window = MainWindow(settings)
    app.processEvents()
    return window


def test_saved_high_quality_restored_at_startup(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AETHERLAB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AETHERLAB_DISABLE_LEGACY_ENV", "1")
    window = _make_window(tmp_path, {"default_quality": "h"})
    try:
        assert window.command_bar.get_render_quality() == "h"
    finally:
        window.close()


def test_missing_saved_quality_falls_back_to_standard(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AETHERLAB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AETHERLAB_DISABLE_LEGACY_ENV", "1")
    window = _make_window(tmp_path, None)
    try:
        assert window.command_bar.get_render_quality() == "m"
    finally:
        window.close()


def test_invalid_saved_quality_falls_back_to_standard(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AETHERLAB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AETHERLAB_DISABLE_LEGACY_ENV", "1")
    window = _make_window(tmp_path, {"default_quality": "xx"})
    try:
        assert window.command_bar.get_render_quality() == "m"
    finally:
        window.close()
