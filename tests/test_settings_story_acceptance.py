"""Executable user-story matrices for settings environment and persistence."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def _clean_settings_env(monkeypatch, root: Path) -> None:
    import os

    for name in tuple(os.environ):
        if name.startswith(("AETHERLAB_", "OPENAI_", "QWEN_", "DASHSCOPE_", "MANIM_", "GPT_", "CHAT_", "LLM_")):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AETHERLAB_DATA_DIR", str(root / "data"))
    monkeypatch.setenv("AETHERLAB_DISABLE_LEGACY_ENV", "1")
    monkeypatch.setenv("AETHERLAB_QWEN_AUTOLOAD", "0")
    monkeypatch.setenv("QWEN_SETTINGS_PATH", str(root / "qwen.json"))


def test_f06_explicit_environment_paths_and_provider_fields(tmp_path, monkeypatch):
    from aetherlab.core.settings import load_settings

    _clean_settings_env(monkeypatch, tmp_path)
    paths = {
        "AETHERLAB_CACHE_PATH": str(tmp_path / "cache.sqlite3"),
        "AETHERLAB_CHROMA_PATH": str(tmp_path / "chroma"),
        "AETHERLAB_LIBRARY_DIR": str(tmp_path / "library"),
    }
    for name, value in paths.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("AETHERLAB_LLM_MODEL", "owned-model")
    monkeypatch.setenv("AETHERLAB_OPENAI_API_KEY", "owned-api-secret")
    monkeypatch.setenv("AETHERLAB_OPENAI_BASE_URL", "https://provider.example/v1")

    settings = load_settings()
    assert settings.data_dir == tmp_path / "data"
    assert settings.cache_path == Path(paths["AETHERLAB_CACHE_PATH"])
    assert settings.chroma_path == Path(paths["AETHERLAB_CHROMA_PATH"])
    assert settings.library_path == Path(paths["AETHERLAB_LIBRARY_DIR"])
    assert (settings.llm_model, settings.openai_api_key, settings.openai_base_url) == (
        "owned-model", "owned-api-secret", "https://provider.example/v1",
    )


def test_f06_compatible_environment_aliases_feed_the_same_client_policy(tmp_path, monkeypatch):
    from aetherlab.core.settings import load_settings
    from aetherlab.services.model_policy import openai_client_kwargs

    _clean_settings_env(monkeypatch, tmp_path)
    monkeypatch.setenv("MANIM_MODEL", "compat-model")
    monkeypatch.setenv("GPT_API_KEY", "compat-secret")
    monkeypatch.setenv("GPT_BASE_URL", "https://compat.example/v1")
    monkeypatch.setenv("AETHERLAB_LLM_TIMEOUT", "17")
    monkeypatch.setenv("AETHERLAB_LLM_MAX_RETRIES", "1")
    settings = load_settings()
    assert (settings.llm_model, settings.openai_api_key, settings.openai_base_url) == (
        "compat-model", "compat-secret", "https://compat.example/v1",
    )
    kwargs = openai_client_kwargs(settings)
    assert kwargs["timeout"] == 17.0 and kwargs["max_retries"] == 1


def test_f06_timeout_and_retry_bounds_are_explicit_and_authoritative(tmp_path, monkeypatch):
    from aetherlab.core.settings import load_settings
    from aetherlab.services.model_policy import effective_llm_retries, effective_llm_timeout

    _clean_settings_env(monkeypatch, tmp_path)
    for raw, expected in (("1", 5.0), ("600", 600.0), ("1800", 1800.0), ("99999", 1800.0)):
        monkeypatch.setenv("AETHERLAB_LLM_TIMEOUT", raw)
        settings = load_settings()
        assert settings.llm_timeout_seconds == expected
        assert effective_llm_timeout(settings) == expected
    for raw, expected in (("-2", 0), ("0", 0), ("1", 1), ("9", 1)):
        monkeypatch.setenv("AETHERLAB_LLM_MAX_RETRIES", raw)
        settings = load_settings()
        assert effective_llm_retries(settings) == expected


def test_f07_settings_round_trip_drops_empty_values_and_survives_reload(tmp_path, monkeypatch):
    from aetherlab.core.settings import load_settings, save_app_config

    _clean_settings_env(monkeypatch, tmp_path)
    path = save_app_config({
        "model": "saved-model", "base_url": "https://saved.example/v1",
        "library_path": str(tmp_path / "books"), "api_key": "saved-secret",
        "blank": "  ", "unset": None,
    })
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "blank" not in payload and "unset" not in payload
    settings = load_settings()
    assert settings.llm_model == "saved-model"
    assert settings.openai_base_url == "https://saved.example/v1"
    assert settings.openai_api_key == "saved-secret"
    assert settings.library_path == tmp_path / "books"


def test_f07_concurrent_saves_merge_without_partial_temporary_files(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from aetherlab.core.settings import app_config_path, load_app_config, save_app_config

    _clean_settings_env(monkeypatch, tmp_path)
    writers = 6
    gate = Barrier(writers)

    def save(index: int) -> None:
        gate.wait(timeout=10)
        save_app_config({f"choice_{index}": str(index)})

    with ThreadPoolExecutor(max_workers=writers) as pool:
        list(pool.map(save, range(writers)))
    config = load_app_config()
    assert all(config.get(f"choice_{index}") == str(index) for index in range(writers))
    assert not list(app_config_path().parent.glob(".settings.json.*.tmp"))


def test_f07_unreadable_config_refuses_overwrite_and_preserves_saved_bytes(tmp_path, monkeypatch):
    from aetherlab.core.settings import app_config_path, save_app_config

    _clean_settings_env(monkeypatch, tmp_path)
    path = app_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"model": "keep-this"}), encoding="utf-8")
    before = path.read_bytes()
    original = Path.read_text

    def deny_selected_config(target, *args, **kwargs):
        if target == path:
            raise PermissionError("owned settings read refusal")
        return original(target, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", deny_selected_config)
    with pytest.raises(PermissionError):
        save_app_config({"render_mode": "cloud"})
    assert path.read_bytes() == before


def test_f08_environment_wins_over_saved_and_opted_in_qwen_sources(tmp_path, monkeypatch):
    from aetherlab.core.settings import load_settings, save_app_config

    _clean_settings_env(monkeypatch, tmp_path)
    qwen = tmp_path / "qwen.json"
    qwen.write_text(json.dumps({
        "model": {"name": "qwen-owned"},
        "modelProviders": {"openai": [{"id": "qwen-owned", "baseUrl": "https://qwen.example/v1", "envKey": "QWEN_KEY"}]},
        "env": {"QWEN_KEY": "qwen-secret"},
    }), encoding="utf-8")
    monkeypatch.setenv("AETHERLAB_QWEN_AUTOLOAD", "1")
    monkeypatch.setenv("QWEN_SETTINGS_PATH", str(qwen))
    save_app_config({"model": "saved-model", "api_key": "saved-secret", "base_url": "https://saved.example/v1"})
    monkeypatch.setenv("AETHERLAB_LLM_MODEL", "environment-model")
    monkeypatch.setenv("AETHERLAB_OPENAI_API_KEY", "environment-secret")
    settings = load_settings()
    assert settings.llm_model == "environment-model"
    assert settings.openai_api_key == "environment-secret"
    assert settings.openai_base_url == "https://saved.example/v1"
    assert settings.provider_source == "environment"
    assert "environment" in settings.api_key_source


def test_f08_saved_config_wins_over_opted_in_qwen_and_reports_its_source(tmp_path, monkeypatch):
    from aetherlab.core.settings import load_settings, save_app_config

    _clean_settings_env(monkeypatch, tmp_path)
    qwen = tmp_path / "qwen.json"
    qwen.write_text(json.dumps({
        "model": {"name": "qwen-owned"},
        "modelProviders": {"openai": [{"id": "qwen-owned", "baseUrl": "https://qwen.example/v1", "envKey": "QWEN_KEY"}]},
        "env": {"QWEN_KEY": "qwen-secret"},
    }), encoding="utf-8")
    monkeypatch.setenv("AETHERLAB_QWEN_AUTOLOAD", "1")
    monkeypatch.setenv("QWEN_SETTINGS_PATH", str(qwen))
    save_app_config({"model": "saved-model", "api_key": "saved-secret", "base_url": "https://saved.example/v1"})
    settings = load_settings()
    assert (settings.llm_model, settings.openai_api_key, settings.openai_base_url) == (
        "saved-model", "saved-secret", "https://saved.example/v1",
    )
    assert settings.provider_source == str(Path(tmp_path / "data" / "settings.json"))


def test_f08_blank_environment_values_fall_through_to_saved_provider(tmp_path, monkeypatch):
    from aetherlab.core.settings import load_settings, save_app_config

    _clean_settings_env(monkeypatch, tmp_path)
    save_app_config({"model": "saved-model", "api_key": "saved-secret", "base_url": "https://saved.example/v1"})
    for name in ("AETHERLAB_LLM_MODEL", "AETHERLAB_OPENAI_API_KEY", "AETHERLAB_OPENAI_BASE_URL"):
        monkeypatch.setenv(name, "  ")
    settings = load_settings()
    assert (settings.llm_model, settings.openai_api_key, settings.openai_base_url) == (
        "saved-model", "saved-secret", "https://saved.example/v1",
    )
    assert settings.provider_source.endswith("settings.json")


def test_f08_provider_warnings_never_echo_environment_or_saved_secrets(tmp_path, monkeypatch):
    from aetherlab.core.settings import load_settings, save_app_config

    _clean_settings_env(monkeypatch, tmp_path)
    save_app_config({"api_key": "saved-secret-owned"})
    monkeypatch.setenv("AETHERLAB_OPENAI_API_KEY", "environment-secret-owned")
    settings = load_settings()
    diagnostics = " ".join((settings.provider_warning, settings.api_key_source, settings.provider_source))
    assert settings.api_key_source.endswith("AETHERLAB_OPENAI_API_KEY")
    assert "overrides" in settings.provider_warning
    assert "saved-secret-owned" not in diagnostics
    assert "environment-secret-owned" not in diagnostics


@pytest.mark.parametrize("names,field,value", [
    (("AETHERLAB_LLM_MODEL", "MANIM_MODEL", "GPT_MODEL", "CHAT_MODEL"), "llm_model", "alias-model"),
    (("AETHERLAB_OPENAI_API_KEY", "OPENAI_API_KEY", "GPT_API_KEY", "DASHSCOPE_API_KEY"), "openai_api_key", "alias-owned-key"),
    (("AETHERLAB_OPENAI_BASE_URL", "OPENAI_BASE_URL", "GPT_BASE_URL", "LLM_BASE_URL"), "openai_base_url", "https://alias.example/v1"),
], ids=["model", "key", "url"])
def test_f06_every_provider_alias_and_first_nonblank_winner(tmp_path, monkeypatch, names, field, value):
    from aetherlab.core.settings import load_settings

    _clean_settings_env(monkeypatch, tmp_path)
    for selected in names:
        for name in names:
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv(selected, "  " + value + "  ")
        assert getattr(load_settings(), field) == value
    for name in names:
        monkeypatch.setenv(name, "lower")
    monkeypatch.setenv(names[0], value)
    assert getattr(load_settings(), field) == value
    monkeypatch.setenv(names[0], "  ")
    assert getattr(load_settings(), field) == "lower"


def test_f06_legacy_cloud_aliases_and_visual_controls(tmp_path, monkeypatch):
    from aetherlab.core import settings as module

    _clean_settings_env(monkeypatch, tmp_path)
    legacy = tmp_path / "owned.env"
    legacy.write_text("MANIM_MODEL=legacy-model\nGPT_API_KEY=legacy-unused-key\n"
        "LLM_BASE_URL=https://legacy.example/v1\nLLM_TIMEOUT=41\nCLOUD_RENDER_ENABLED=true\n"
        "CLOUD_RENDER_REPO=owned/repo\nGH_TOKEN=owned-unused-token\n"
        "CLOUD_RENDER_WORKFLOW=.github/workflows/owned.yml\nCLOUD_RENDER_BRANCH=owned-branch\n"
        "CLOUD_RENDER_POLL=12\nCLOUD_RENDER_TIMEOUT=321\n", encoding="utf-8")
    monkeypatch.delenv("AETHERLAB_DISABLE_LEGACY_ENV")
    monkeypatch.setattr(module, "_legacy_env_path", lambda: legacy)
    for name, value in {"VISION_MODEL": "vision-owned", "VISUAL_CRITIC_MAX_PASSES": "3",
                        "VISUAL_CRITIC_KEYFRAMES": "9", "AETHERLAB_SCENE_CANDIDATES": "4",
                        "AETHERLAB_SCENE_CANDIDATE_CONCURRENCY": "2", "AETHERLAB_AUTO_TOURNAMENT": "false"}.items():
        monkeypatch.setenv(name, value)
    before = legacy.read_bytes()
    loaded = module.load_settings()
    assert (loaded.llm_model, loaded.openai_api_key, loaded.openai_base_url, loaded.llm_timeout_seconds) == (
        "legacy-model", "legacy-unused-key", "https://legacy.example/v1", 41)
    assert (loaded.render_mode, loaded.github_repo, loaded.github_token, loaded.github_workflow,
            loaded.github_branch, loaded.cloud_poll_seconds, loaded.cloud_render_timeout) == (
        "auto", "owned/repo", "owned-unused-token", "owned.yml", "owned-branch", 12, 321)
    assert (loaded.vision_model, loaded.visual_critic_max_passes, loaded.visual_critic_keyframes,
            loaded.scene_candidates, loaded.scene_candidate_concurrency, loaded.auto_tournament) == (
        "vision-owned", 3, 9, 4, 2, False)
    assert legacy.read_bytes() == before


def test_f06_client_factory_passes_bounded_policy_to_primary_and_backup(tmp_path, monkeypatch):
    import openai
    from aetherlab.core.settings import load_settings
    from aetherlab.services.llm_client import make_client

    _clean_settings_env(monkeypatch, tmp_path)
    for name, value in {"AETHERLAB_OPENAI_API_KEY": "primary-unused-key",
            "AETHERLAB_OPENAI_BASE_URL": "https://primary.example/v1", "AETHERLAB_LLM_TIMEOUT": "19",
            "AETHERLAB_LLM_MAX_RETRIES": "1", "AETHERLAB_FALLBACK_OPENAI_API_KEY": "backup-unused-key",
            "AETHERLAB_FALLBACK_OPENAI_BASE_URL": "https://backup.example/v1",
            "AETHERLAB_FALLBACK_LLM_MODEL": "backup-model"}.items():
        monkeypatch.setenv(name, value)
    captured = []
    monkeypatch.setattr(openai, "AsyncOpenAI", lambda **kwargs: captured.append(kwargs) or object())
    client = make_client(load_settings())
    assert client.has_fallback and len(captured) == 2
    for index, kind in enumerate(("primary", "backup")):
        assert captured[index] == {"api_key": kind + "-unused-key", "base_url": f"https://{kind}.example/v1",
                                   "timeout": 19.0, "max_retries": 1}


def test_f06_ollama_fills_only_missing_provider_fields(tmp_path, monkeypatch):
    from aetherlab.core.settings import load_settings, save_app_config, OLLAMA_OPENAI_BASE_URL

    _clean_settings_env(monkeypatch, tmp_path)
    save_app_config({"provider_preset": "ollama"})
    loaded = load_settings()
    assert (loaded.openai_api_key, loaded.openai_base_url) == ("ollama", OLLAMA_OPENAI_BASE_URL)
    monkeypatch.setenv("OPENAI_API_KEY", "explicit-unused-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://explicit.example/v1")
    loaded = load_settings()
    assert (loaded.openai_api_key, loaded.openai_base_url) == ("explicit-unused-key", "https://explicit.example/v1")


def test_f08_legacy_tier_and_per_field_fallback(tmp_path, monkeypatch):
    from aetherlab.core import settings as module

    _clean_settings_env(monkeypatch, tmp_path)
    monkeypatch.delenv("AETHERLAB_DISABLE_LEGACY_ENV")
    legacy = tmp_path / "owned.env"
    legacy.write_text("GPT_MODEL=legacy-model\nDASHSCOPE_API_KEY=legacy-unused-key\n"
                      "LLM_BASE_URL=https://legacy.example/v1\n", encoding="utf-8")
    monkeypatch.setattr(module, "_legacy_env_path", lambda: legacy)
    monkeypatch.setenv("AETHERLAB_QWEN_AUTOLOAD", "1")
    monkeypatch.setattr(module, "load_qwen_settings", lambda: {
        "model": "lower-model", "api_key": "lower-unused-key", "base_url": "https://lower.example/v1",
        "source": "owned Qwen"})
    before = legacy.read_bytes()
    loaded = module.load_settings()
    assert (loaded.llm_model, loaded.openai_api_key, loaded.openai_base_url) == (
        "legacy-model", "legacy-unused-key", "https://legacy.example/v1")
    assert loaded.provider_source == str(legacy)
    assert loaded.api_key_source == "legacy .env: DASHSCOPE_API_KEY"
    module.save_app_config({"model": "saved-model"})
    monkeypatch.setenv("OPENAI_BASE_URL", "https://environment.example/v1")
    loaded = module.load_settings()
    assert (loaded.llm_model, loaded.openai_api_key, loaded.openai_base_url) == (
        "saved-model", "legacy-unused-key", "https://environment.example/v1")
    assert loaded.provider_source == "environment"
    assert loaded.api_key_source == "legacy .env: DASHSCOPE_API_KEY"
    assert legacy.read_bytes() == before


@pytest.mark.parametrize("payload", [None, b"\xff\xfe", b"[]", b"{"], ids=["missing", "utf8", "shape", "json"])
def test_f08_bad_lower_files_are_skipped_without_rewriting(tmp_path, monkeypatch, payload):
    import os
    from aetherlab.core import settings as module

    _clean_settings_env(monkeypatch, tmp_path)
    monkeypatch.delenv("AETHERLAB_DISABLE_LEGACY_ENV")
    monkeypatch.setenv("AETHERLAB_QWEN_AUTOLOAD", "1")
    legacy, qwen = tmp_path / "owned.env", tmp_path / "qwen.json"
    monkeypatch.setattr(module, "_legacy_env_path", lambda: legacy)
    if payload is not None:
        legacy.write_bytes(payload)
        qwen.write_bytes(payload)
    before = dict(os.environ)
    loaded = module.load_settings()
    assert loaded.llm_model == "gpt-5.5"
    assert loaded.openai_api_key is None and loaded.openai_base_url is None
    assert loaded.api_key_source == "none"
    assert dict(os.environ) == before
    for path in (legacy, qwen):
        assert path.read_bytes() == payload if payload is not None else not path.exists()


def test_f08_url_only_environment_and_saved_fields_name_the_highest_used_tier(tmp_path, monkeypatch):
    from aetherlab.core import settings as module

    _clean_settings_env(monkeypatch, tmp_path)
    path = module.save_app_config({"provider_preset": "ollama", "model": "saved-model"})
    assert module.load_settings().provider_source == str(path)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://explicit.example/v1")
    loaded = module.load_settings()
    assert loaded.openai_base_url == "https://explicit.example/v1"
    assert loaded.provider_source == "environment"
    assert loaded.api_key_source == "Ollama local (no secret)"
