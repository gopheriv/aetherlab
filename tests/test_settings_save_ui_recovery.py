import json
import os
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_route = runpy.run_path(str(ROOT / "tests/test_prebuilt_student_routes.py"))


@pytest.fixture(autouse=True)
def _isolated_provider_environment(monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(("AETHERLAB_", "OPENAI_", "QWEN_", "DASHSCOPE_", "MANIM_", "GPT_", "CHAT_", "LLM_")):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AETHERLAB_DISABLE_LEGACY_ENV", "1")


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("failure", ("read", "write"))
def test_settings_save_failure_keeps_draft_and_retry_commits(language, failure, tmp_path, monkeypatch):
    from aetherlab.core import settings
    from aetherlab.ui.main_window import SettingsDialog
    from aetherlab.ui.qt_compat import QtWidgets

    window = _route["_window"](tmp_path, language, monkeypatch)
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"unknown_option": "keep", "model": "old"}), encoding="utf-8")
    before = path.read_bytes()
    previous = window.settings
    dialogs = []
    def accept(dialog):
        if not dialogs:
            dialog._model_edit.setText("owned-draft-model")
        else:
            assert dialog is dialogs[0]
            assert dialog._model_edit.text() == "owned-draft-model"
        dialogs.append(dialog)
        return QtWidgets.QDialog.DialogCode.Accepted
    monkeypatch.setattr(SettingsDialog, "exec", accept)
    def refused(*args, **kwargs):
        raise PermissionError("Owned settings write refused")
    original_read = Path.read_text
    def read_refused(target, *args, **kwargs):
        if target == path:
            raise PermissionError("Owned settings read refused")
        return original_read(target, *args, **kwargs)
    try:
        with monkeypatch.context() as patch:
            if failure == "write":
                patch.setattr(settings, "atomic_write_json", refused)
            else:
                patch.setattr(Path, "read_text", read_refused)
            window._open_settings()
        assert window.settings is previous and path.read_bytes() == before
        assert {"kk": "сақтау мүмкін болмады", "ru": "Не удалось сохранить", "en": "Could not save"}[language] in window.statusBar().currentMessage()
        assert "Owned settings write refused" not in window.statusBar().currentMessage()
        window._open_settings()
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["model"] == "owned-draft-model" and saved["unknown_option"] == "keep"
        assert window.settings.llm_model == "owned-draft-model"
    finally:
        window.close()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_failed_settings_draft_can_be_cancelled_without_applying_it(language, tmp_path, monkeypatch):
    from aetherlab.core import settings
    from aetherlab.ui.main_window import SettingsDialog
    from aetherlab.ui.qt_compat import QtWidgets

    window = _route["_window"](tmp_path, language, monkeypatch)
    original_model = window.settings.llm_model
    captured = []
    def accept(dialog):
        dialog._model_edit.setText("cancelled-draft")
        captured.append(dialog)
        return QtWidgets.QDialog.DialogCode.Accepted
    monkeypatch.setattr(SettingsDialog, "exec", accept)
    def refused(*args, **kwargs):
        raise PermissionError("Owned save refusal")
    try:
        with monkeypatch.context() as patch:
            patch.setattr(settings, "atomic_write_json", refused)
            window._open_settings()
        def cancel(dialog):
            assert dialog is captured[0] and dialog._model_edit.text() == "cancelled-draft"
            return QtWidgets.QDialog.DialogCode.Rejected
        monkeypatch.setattr(SettingsDialog, "exec", cancel)
        window._open_settings()
        assert window.settings.llm_model == original_model
        assert getattr(window, "_settings_save_draft", None) is None
        assert not (tmp_path / "settings.json").exists()
    finally:
        window.close()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_ollama_save_failure_keeps_provider_inactive_and_retry_works(language, tmp_path, monkeypatch):
    from aetherlab.core import settings

    for name in ("AETHERLAB_PROVIDER", "AETHERLAB_LLM_MODEL", "AETHERLAB_OPENAI_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    window = _route["_window"](tmp_path, language, monkeypatch)
    window._ollama_models = ["owned-local-model"]
    previous = window.settings
    messages = []
    monkeypatch.setattr(window.toast, "show_message", lambda level, text: messages.append((level, text)))
    def refused(*args, **kwargs):
        raise PermissionError("fixture-private-token-must-stay-private")
    try:
        with monkeypatch.context() as patch:
            patch.setattr(settings, "atomic_write_json", refused)
            window._enable_ollama()
        assert window.settings is previous
        assert messages and all(level != "success" for level, _ in messages)
        assert "fixture-private-token" not in str(messages) + window.statusBar().currentMessage()
        window._enable_ollama()
        assert window.settings.llm_model == "owned-local-model"
        uses_local_sentinel = window.settings.openai_api_key == "ollama"
        assert uses_local_sentinel, "Retry must activate the local Ollama sentinel"
    finally:
        window.close()
