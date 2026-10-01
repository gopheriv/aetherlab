"""Subprocess repro: a Settings task signal queued after its dialog is destroyed.

Exits 0 when the queued signal is delivered safely; a regression (a lambda slot
touching the deleted dialog) ends the process with an access violation instead.
Run by tests/test_bugcheck_regressions.py in a child process.
"""

from __future__ import annotations

import os
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6 import QtWidgets, sip  # noqa: E402

import aetherlab.services.render_backend as render_backend  # noqa: E402
from aetherlab.core.settings import load_settings  # noqa: E402
from aetherlab.ui.main_window import SettingsDialog  # noqa: E402


def main() -> int:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    os.environ["AETHERLAB_DATA_DIR"] = tempfile.mkdtemp(prefix="aetherlab_repro_")
    settings = replace(load_settings(), render_mode="cloud", github_repo="owner/render",
                       github_token="ghp_" + "x" * 24)
    render_backend.CloudRenderBackend.available = lambda _self: (False, "offline in repro")
    for _round in range(5):
        dialog = SettingsDialog(settings)
        dialog._test_cloud_render()
        dialog._cloud_task.wait(3.0)      # worker done: succeeded/finished are queued
        sip.delete(dialog)                # destroy the C++ dialog before delivery
        app.processEvents()               # deliver the queued signals
    print("settings dialog survived", flush=True)

    # Same race on the main window's export task (the second crash site on CI).
    from aetherlab.ui.main_window import MainWindow

    for _round in range(3):
        window = MainWindow(settings)
        window._start_export_task("Exporting…", lambda _cancel, _progress: "exported")
        window._export_task.wait(3.0)    # export done: its signals are queued
        # Close it the way the app does: closeEvent joins the window's own
        # threads (e.g. the Ollama probe). Destroying a window with a running
        # QThread aborts by design, which is not the race under test.
        window.close()
        sip.delete(window)               # gone before the queued signals arrive
        app.processEvents()
    print("survived", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
