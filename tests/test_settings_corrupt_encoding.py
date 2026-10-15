"""Exercise corrupt settings through their actual read/save entry points."""
import json
import os
from pathlib import Path

import pytest

from aetherlab.core import settings


def _isolated(tmp_path, monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(("AETHERLAB_", "OPENAI_", "QWEN_", "DASHSCOPE_", "MANIM_", "GPT_", "CHAT_")):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AETHERLAB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AETHERLAB_DISABLE_LEGACY_ENV", "1")
    monkeypatch.setenv("QWEN_SETTINGS_PATH", str(tmp_path / "qwen.json"))
    return tmp_path


def test_invalid_utf8_app_config_uses_defaults_without_rewriting(tmp_path, monkeypatch):
    isolated = _isolated(tmp_path, monkeypatch)
    path = isolated / "settings.json"
    path.write_bytes(b"\xff\xfeinvalid config")
    before = path.read_bytes()
    assert settings.load_app_config() == {}
    assert settings.load_settings().data_dir == isolated
    assert path.read_bytes() == before


def test_invalid_utf8_opted_in_qwen_uses_defaults_without_rewriting(tmp_path, monkeypatch):
    isolated = _isolated(tmp_path, monkeypatch)
    path = isolated / "qwen.json"
    path.write_bytes(b"\xffinvalid qwen")
    before = path.read_bytes()
    monkeypatch.setenv("AETHERLAB_QWEN_AUTOLOAD", "1")
    assert settings.load_qwen_settings(path) == {}
    assert settings.load_settings().openai_api_key is None
    assert path.read_bytes() == before


def test_invalid_utf8_legacy_env_uses_defaults_without_mutating_environment(tmp_path, monkeypatch):
    isolated = _isolated(tmp_path, monkeypatch)
    path = isolated / "legacy.env"
    path.write_bytes(b"\xffAETHERLAB_LLM_MODEL=unexpected")
    before = path.read_bytes()
    monkeypatch.setenv("AETHERLAB_DISABLE_LEGACY_ENV", "0")
    monkeypatch.setenv("AETHERLAB_LEGACY_ENV_PATH", str(path))
    environment = dict(os.environ)
    assert settings.load_legacy_env(path) == {}
    assert settings.load_settings().data_dir == isolated
    assert dict(os.environ) == environment and path.read_bytes() == before


def test_cannot_save_over_config_that_could_not_be_read(tmp_path, monkeypatch):
    isolated = _isolated(tmp_path, monkeypatch)
    path = isolated / "settings.json"
    path.write_text(json.dumps({"llm_model": "keep model", "custom_note": "preserve"}), encoding="utf-8")
    before = path.read_bytes()
    original = Path.read_text
    def denied(target, *args, **kwargs):
        if target == path:
            raise PermissionError("Owned configuration cannot be read")
        return original(target, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", denied)
    with pytest.raises(PermissionError):
        settings.save_app_config({"render_mode": "cloud"})
    assert path.read_bytes() == before
