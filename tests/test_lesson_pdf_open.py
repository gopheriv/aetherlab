"""The attached-PDF action reports the actual opener outcome in the UI language."""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aetherlab.ui.main_window import MainWindow
from aetherlab.ui.qt_compat import QtGui, QtWidgets

_APP = None


def _app():
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("accepted", (False, True))
def test_study_pdf_reports_real_dispatch_outcome(language, accepted, tmp_path, monkeypatch):
    _app()
    pdf = tmp_path / "guide.pdf"
    pdf.write_bytes(b"%PDF-1.4\n% synthetic local URL dispatch fixture\n")
    messages, urls = [], []
    shell = SimpleNamespace(
        _last_lesson=SimpleNamespace(pdf_path=str(pdf)),
        command_bar=SimpleNamespace(get_language=lambda: language),
        statusBar=lambda: SimpleNamespace(showMessage=messages.append),
    )
    monkeypatch.setattr(QtGui.QDesktopServices, "openUrl", lambda url: urls.append(url) or accepted)
    MainWindow._open_study_pdf(shell)
    assert len(urls) == 1 and Path(urls[0].toLocalFile()) == pdf
    if accepted:
        assert "guide.pdf" in messages[-1]
        assert {"kk": "жіберілді", "ru": "передан", "en": "sent"}[language] in messages[-1]
    else:
        assert {"kk": "мүмкін болмады", "ru": "Не удалось", "en": "Could not"}[language] in messages[-1]
        assert "opened" not in messages[-1].lower()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_missing_study_pdf_does_not_launch_an_opener(language, tmp_path, monkeypatch):
    _app()
    messages, urls = [], []
    shell = SimpleNamespace(
        _last_lesson=SimpleNamespace(pdf_path=str(tmp_path / "missing.pdf")),
        command_bar=SimpleNamespace(get_language=lambda: language),
        statusBar=lambda: SimpleNamespace(showMessage=messages.append),
    )
    monkeypatch.setattr(QtGui.QDesktopServices, "openUrl", lambda url: urls.append(url) or True)
    MainWindow._open_study_pdf(shell)
    assert not urls
    assert {"kk": "тіркелмеген", "ru": "не прикреплён", "en": "attached"}[language] in messages[-1]


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_study_pdf_accessible_label_matches_visible_action(language, tmp_path):
    from aetherlab.services.ent_lesson_catalog import accelerated_motion_5min_plan
    from aetherlab.services.lesson_pipeline import _prebuilt_5min_bundle
    from aetherlab.ui.lesson_view import LessonView

    _app()
    view = LessonView()
    view.set_lesson(_prebuilt_5min_bundle(accelerated_motion_5min_plan(language)))
    assert view._pdf_btn.accessibleName() == view._pdf_btn.text()
    view.close()
