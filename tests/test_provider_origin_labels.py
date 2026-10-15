"""The active provider label follows the effective endpoint, not a stale preset."""
from dataclasses import replace

import pytest

from aetherlab.core.settings import AppSettings, load_settings, save_app_config
from aetherlab.services.model_policy import active_provider_name


@pytest.fixture
def settings_template(tmp_path):
    return AppSettings(data_dir=tmp_path, cache_path=tmp_path / "cache.sqlite3",
        chroma_path=tmp_path / "chroma", library_path=tmp_path / "library",
        openai_api_key="owned-unused-key", openai_base_url=None, llm_model="owned-model")


@pytest.mark.parametrize("base,model,source,expected", [
    ("https://api.openai.com/v1", "gpt-model", "ollama-local", "OpenAI"),
    ("https://api.openai.com/v1", "qwen-model", "environment", "OpenAI"),
    ("https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "qwen-model", "ollama-local", "Qwen / DashScope"),
    ("http://localhost:11434/v1", "qwen-model", "environment", "Ollama"),
    ("http://127.0.0.1:11434/v1", "local-model", "ollama-local", "Ollama"),
    ("http://[::1]:11434/v1", "local-model", "environment", "Ollama"),
    ("http://owned-server.invalid:11434/v1", "local-model", "environment", "Ollama"),
    ("https://owned-compatible.invalid/v1", "qwen-model", "ollama-local", "OpenAI-compatible endpoint"),
    ("https://owned-compatible.invalid/path/11434", "custom", "environment", "OpenAI-compatible endpoint"),
    ("https://owned-compatible.invalid/v1?service=11434", "custom", "environment", "OpenAI-compatible endpoint"),
    ("https://api.openai.com.evil.invalid/v1", "gpt-model", "environment", "OpenAI-compatible endpoint"),
    ("https://dashscope.evil.invalid/v1", "qwen-model", "environment", "OpenAI-compatible endpoint"),
    ("https://owned-compatible.invalid/v1", "qwen-model", "environment", "OpenAI-compatible endpoint"),
    (None, "gpt-model", "environment", "OpenAI"),
    (None, "qwen-model", "environment", "OpenAI"),
    ("http://localhost:invalid/v1", "custom", "environment", "OpenAI-compatible endpoint"),
    ("http://[invalid/v1", "custom", "environment", "OpenAI-compatible endpoint"),
])
def test_provider_identity_uses_effective_endpoint(base, model, source, expected, settings_template):
    settings = replace(settings_template, openai_api_key="owned-unused-key", openai_base_url=base,
                       llm_model=model, provider_source=source)
    assert active_provider_name(settings) == expected


def test_missing_key_remains_offline_even_for_a_known_endpoint(settings_template):
    settings = replace(settings_template, openai_api_key=None, openai_base_url="https://api.openai.com/v1")
    assert active_provider_name(settings) == "Offline"


def test_env_endpoint_overrides_saved_ollama_without_mislabeling_or_mutation(tmp_path, monkeypatch):
    monkeypatch.setenv("AETHERLAB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AETHERLAB_DISABLE_LEGACY_ENV", "1")
    monkeypatch.setenv("AETHERLAB_QWEN_AUTOLOAD", "0")
    save_app_config({"provider_preset": "ollama", "model": "qwen-model", "api_key": "owned-saved-key"})
    before = (tmp_path / "settings.json").read_bytes()
    monkeypatch.setenv("AETHERLAB_OPENAI_BASE_URL", "https://api.openai.com/v1")
    settings = load_settings()
    assert settings.openai_base_url == "https://api.openai.com/v1"
    assert active_provider_name(settings) == "OpenAI"
    assert (tmp_path / "settings.json").read_bytes() == before


@pytest.mark.parametrize("language", ["kk", "ru", "en"])
def test_settings_panel_shows_effective_provider_without_key_values(settings_template, language, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from aetherlab.ui.provider_status import ProviderStatusPanel
    from aetherlab.ui.qt_compat import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    settings = replace(settings_template, openai_base_url="https://api.openai.com/v1",
                       provider_source="ollama-local", llm_model="qwen-model", api_key_source="owned config")
    panel = ProviderStatusPanel(settings)
    try:
        panel.set_language(language)
        assert "OpenAI" in panel.active_label.text()
        assert "Ollama" not in panel.active_label.text()
        assert "owned config" in panel.source_label.text()
        assert settings.openai_api_key not in panel.active_label.text() + panel.source_label.text() + panel.warning_label.text()
    finally:
        panel.close()
        panel.deleteLater()
        app.processEvents()
