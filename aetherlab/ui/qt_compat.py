"""Central optional PyQt6 import shim."""

from __future__ import annotations

try:
    from PyQt6 import QtCore, QtGui, QtWidgets
except Exception as exc:
    QtCore = None
    QtGui = None
    QtWidgets = None
    QT_IMPORT_ERROR = exc
else:
    QT_IMPORT_ERROR = None


def require_qt() -> None:
    if QT_IMPORT_ERROR is not None:
        missing_package = isinstance(QT_IMPORT_ERROR, ModuleNotFoundError) and QT_IMPORT_ERROR.name == "PyQt6"
        diagnosis = "PyQt6 is not installed." if missing_package else "PyQt6 could not be loaded. Repair the GUI dependency."
        raise RuntimeError(
            f"{diagnosis} Install PhysLab (PyQt6 is a core dependency) with: "
            "python -m pip install -e .  —  or just: python -m pip install PyQt6"
        ) from QT_IMPORT_ERROR
