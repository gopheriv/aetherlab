"""Exercise real menu actions offscreen; these are authored physics examples."""
from __future__ import annotations

import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from aetherlab.ui.qt_compat import QtWidgets

_APP = None
NUMERICAL_DATA = [
    ["0", "2", "5"], ["2", "3"], ["2", "5", "10"],
    ["2", "3", "1", "0"], ["200", "0.5"], ["0.2", "4200", "20"],
    ["12", "6"], ["2", "4", "12"], ["5", "2"], ["20", "30"],
]
FIRST_WORDS = {"kk": "Дене", "ru": "Тело", "en": "A body"}


@pytest.mark.parametrize("language", ["kk", "ru", "en"])
def test_examples_follow_selected_language_and_keep_identical_physics_data(monkeypatch, language, tmp_path):
    global _APP
    from aetherlab.ui.command_bar import CommandBar
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    bar = CommandBar()
    bar.set_language(language)
    submitted, learned = [], []
    bar.submitted.connect(submitted.append)
    bar.learn_requested.connect(lambda *args: learned.append(args))
    menus = []
    selection = [None]
    def inspect_menu(menu, *args):
        menus.append(menu)
        assert len(menu.actions()) == 10
        if selection[0] is not None:
            menu.actions()[selection[0]].trigger()
    monkeypatch.setattr(QtWidgets.QMenu, "exec", inspect_menu)
    try:
        for index, expected in enumerate(NUMERICAL_DATA):
            selection[0] = index
            bar._show_examples_menu()
            prompt = bar.input.text()
            assert re.findall(r"\d+(?:\.\d+)?", prompt) == expected
            assert menus[-1].actions()[index].text() == (prompt[:64] + "…" if len(prompt) > 64 else prompt)
            assert bar.focusWidget() is bar.input
            if index == 0:
                assert prompt.startswith(FIRST_WORDS[language])
        assert not submitted and not learned
        before = bar.input.text()
        selection[0] = None
        bar._show_examples_menu()
        assert bar.input.text() == before
        # The next menu must follow a language switch in the same widget.
        switched = "ru" if language == "kk" else "kk"
        bar.set_language(switched)
        selection[0] = 0
        bar._show_examples_menu()
        assert bar.input.text().startswith(FIRST_WORDS[switched])
        assert not submitted and not learned
    finally:
        bar.close()
        bar.deleteLater()
        _APP.processEvents()
