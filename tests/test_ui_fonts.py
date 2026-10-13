"""Bundled fonts belong to a Qt application lifetime, not a Python module."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_fonts_reinstall_for_recreated_application_and_keep_custom_font(tmp_path):
    script = r'''
import sys
from pathlib import Path

import fitz
from PyQt6 import QtGui, QtWidgets, sip

from aetherlab.services.ent_practice_pdf import export_practice_pdf
from aetherlab.ui.fonts import install_ui_fonts

registered = []
register = QtGui.QFontDatabase.addApplicationFont
def recording_register(path):
    registered.append(path)
    return register(path)
QtGui.QFontDatabase.addApplicationFont = recording_register
app = QtWidgets.QApplication([])
install_ui_fonts()
assert "DejaVu Sans" in QtGui.QFontDatabase.families()
first_count = len(registered)
assert first_count > 0
sip.delete(app)

app = QtWidgets.QApplication([])
install_ui_fonts()
assert len(registered) == first_count * 2, "fonts were not registered for the new Qt instance"
assert "DejaVu Sans" in QtGui.QFontDatabase.families(), "bundled fonts were lost after Qt restart"
app.setFont(QtGui.QFont("Arial", 13))
install_ui_fonts()
assert app.font().family() == "Arial" and app.font().pointSize() == 13

for language, title in (("ru", "Подготовка"), ("kk", "дайындық"), ("en", "Physics practice")):
    output = Path(sys.argv[1]) / f"recreated-{language}.pdf"
    export_practice_pdf(output, language=language, questions=(), user_answers=[],
                        topic_names={}, topic_progress={}, score=0)
    with fitz.open(output) as document:
        text = " ".join(" ".join(page.get_text() for page in document).split())
        assert title in text, (language, text)
        assert "NCT free practice portal" in text
'''
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_font_installer_does_not_register_before_application(monkeypatch):
    from aetherlab.ui import fonts

    calls = []
    monkeypatch.setattr(fonts.QtWidgets.QApplication, "instance", lambda: None)
    monkeypatch.setattr(fonts.QtGui.QFontDatabase, "addApplicationFont", lambda path: calls.append(path) or 0)
    fonts.install_ui_fonts()
    assert calls == []
