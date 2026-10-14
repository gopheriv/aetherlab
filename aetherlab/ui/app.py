"""Application launcher."""

from __future__ import annotations

import sys
from pathlib import Path

from aetherlab.core.settings import load_settings
from aetherlab.ui.qt_compat import QtGui, QtWidgets, require_qt


def _icon_path() -> Path | None:
    """Locate the bundled .ico both in a source checkout and a frozen dist."""
    candidates = [
        Path(__file__).resolve().parents[2] / "assets" / "aetherlab.ico",  # repo
        Path(getattr(sys, "_MEIPASS", ".")) / "assets" / "aetherlab.ico",  # PyInstaller
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def run_app(argv: list[str] | None = None) -> int:
    require_qt()
    from aetherlab.ui.main_window import MainWindow

    # Without an explicit AppUserModelID, the Windows taskbar groups the app
    # under python.exe and shows the Python icon instead of ours.
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "PhysLab.Workbench"
            )
        except Exception:  # noqa: BLE001 — cosmetic only
            pass

    app = QtWidgets.QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("PhysLab")
    app.setApplicationDisplayName("PhysLab")
    icon = _icon_path()
    if icon is not None:
        app.setWindowIcon(QtGui.QIcon(str(icon)))
    window = MainWindow(settings=load_settings())
    window.show()
    return app.exec()
