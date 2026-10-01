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
    print("survived", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
