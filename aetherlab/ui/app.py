"""Application launcher."""

from __future__ import annotations

import sys

from aetherlab.core.settings import load_settings
from aetherlab.ui.qt_compat import QtWidgets, require_qt


def run_app(argv: list[str] | None = None) -> int:
    require_qt()
    from aetherlab.ui.main_window import MainWindow

    app = QtWidgets.QApplication(argv if argv is not None else sys.argv)
    window = MainWindow(settings=load_settings())
    window.show()
    return app.exec()
