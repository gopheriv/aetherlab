"""Load the fonts bundled with AetherLab's desktop UI."""

from __future__ import annotations

import sys
from pathlib import Path

from aetherlab.ui.qt_compat import QtGui, QtWidgets

_INSTALLED_PROPERTY = "aetherlab_ui_fonts_installed"


def install_ui_fonts() -> None:
    """Register bundled fonts once per Qt application, preserving later choices."""
    app = QtWidgets.QApplication.instance()
    if app is None or app.property(_INSTALLED_PROPERTY):
        return
    candidates = set()
    for root in (
        Path(__file__).resolve().parents[2],
        Path(getattr(sys, "_MEIPASS", ".")),
    ):
        candidates.update([
            root / "assets" / "fonts" / "DejaVuSans.ttf",
            root / "assets" / "fonts" / "DejaVuSans-Bold.ttf",
        ])
    loaded = False
    for path in sorted(candidates):
        if path.exists():
            loaded = QtGui.QFontDatabase.addApplicationFont(str(path)) >= 0 or loaded
    # Prefer the native Windows UI face; keep the bundled font as the
    # cross-platform fallback for Cyrillic and Kazakh glyphs.
    if sys.platform == "win32":
        app.setFont(QtGui.QFont("Segoe UI", 10))
    elif loaded:
        app.setFont(QtGui.QFont("DejaVu Sans", 10))
    # Qt discards application fonts when this instance is destroyed. A module
    # flag outlives that database and can leave later PDF exports with no glyphs.
    app.setProperty(_INSTALLED_PROPERTY, True)
