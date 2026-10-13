"""An unavailable allowance file must not grant or erase AI attempts."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aetherlab.services.ai_help_quota import consume_ai_help, remaining_ai_help
from aetherlab.ui.qt_compat import QtWidgets

_APP = None


def _read_refusal(monkeypatch, target):
    original = Path.read_text

    def read(path, *args, **kwargs):
        if path == target:
            raise PermissionError("allowance temporarily unreadable")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)


def _window(root):
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from aetherlab.core.settings import load_settings
    from aetherlab.ui.main_window import MainWindow

    settings = replace(load_settings(), data_dir=root, cache_path=root / "cache.sqlite3", chroma_path=root / "chroma", library_path=root / "library", openai_api_key="test-key", reference_sources_path=None)
    return MainWindow(settings)


def test_unreadable_allowance_never_grants_or_overwrites_used_attempts(tmp_path, monkeypatch) -> None:
    target = tmp_path / "ai_help_quota.json"
    target.write_text(json.dumps({"date": date.today().isoformat(), "used": 10}), encoding="utf-8")
    before = target.read_bytes()
    with monkeypatch.context() as patch:
        _read_refusal(patch, target)
        with pytest.raises(PermissionError):
            remaining_ai_help(target)
        with pytest.raises(PermissionError):
            consume_ai_help(target)
    assert target.read_bytes() == before
    assert remaining_ai_help(target) == 0


def test_unknown_allowance_badge_disables_only_ai_and_translates(tmp_path) -> None:
    window = _window(tmp_path)
    for language in ("kk", "ru", "en"):
        window.command_bar.set_language(language)
        window.command_bar.set_ai_quota(None)
        assert "—/10" in window.command_bar._ai_quota.text()
        assert not window.command_bar.run_button.isEnabled()
        assert not window.command_bar.learn_button.isEnabled()
        assert window.command_bar.practice_button.isEnabled()
        assert window.command_bar._ai_quota.toolTip()
    window.close()


def test_main_window_read_failure_preserves_counter_and_recovers_on_refresh(tmp_path, monkeypatch) -> None:
    for language in ("kk", "ru", "en"):
        window = _window(tmp_path / language)
        window.command_bar.set_language(language)
        assert window._try_consume_ai_help()
        target = window.active_student_profile.ai_help_quota_path
        before = target.read_bytes()
        with monkeypatch.context() as patch:
            _read_refusal(patch, target)
            assert not window._try_consume_ai_help()
            window._refresh_ai_help_quota()
        assert target.read_bytes() == before
        assert "—/10" in window.command_bar._ai_quota.text()
        assert not window.command_bar.run_button.isEnabled()
        assert window.command_bar.practice_button.isEnabled()
        failure_message = window.statusBar().currentMessage()
        window._refresh_ai_help_quota()
        assert "9/10" in window.command_bar._ai_quota.text()
        assert window.command_bar.run_button.isEnabled()
        assert window.statusBar().currentMessage() != failure_message
        window.close()


def test_main_window_write_failure_does_not_claim_consumption(tmp_path, monkeypatch) -> None:
    from aetherlab.services import ai_help_quota

    window = _window(tmp_path)
    assert window._try_consume_ai_help()
    target = window.active_student_profile.ai_help_quota_path
    before = target.read_bytes()

    def refused(*_args, **_kwargs):
        raise PermissionError("allowance destination unavailable")

    with monkeypatch.context() as patch:
        patch.setattr(ai_help_quota, "atomic_write_json", refused)
        assert not window._try_consume_ai_help()
    assert target.read_bytes() == before
    assert "—/10" in window.command_bar._ai_quota.text()
    assert window.worker is None
    window._refresh_ai_help_quota()
    assert "9/10" in window.command_bar._ai_quota.text()
    window.close()


def test_window_starts_with_unavailable_allowance_and_keeps_practice_enabled(tmp_path, monkeypatch) -> None:
    target = tmp_path / "ai_help_quota.json"
    with monkeypatch.context() as patch:
        _read_refusal(patch, target)
        window = _window(tmp_path)
    assert "—/10" in window.command_bar._ai_quota.text()
    assert not window.command_bar.run_button.isEnabled()
    assert window.command_bar.practice_button.isEnabled()
    window._refresh_ai_help_quota()
    assert "10/10" in window.command_bar._ai_quota.text()
    window.close()
