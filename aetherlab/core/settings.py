"""Application settings loaded from environment variables."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AppSettings:
    data_dir: Path
    cache_path: Path
    chroma_path: Path
    library_path: Path
    openai_api_key: str | None
    openai_base_url: str | None
    llm_model: str
    llm_timeout_seconds: float = 60.0
    provider_source: str = "environment"


def _path_from_env(name: str, default: Path) -> Path:
    value = os.getenv(name)
    return Path(value).expanduser() if value else default


def load_settings() -> AppSettings:
    data_dir = _path_from_env("AETHERLAB_DATA_DIR", _default_data_dir())
    cache_path = _path_from_env("AETHERLAB_CACHE_PATH", data_dir / "cache.sqlite3")
    chroma_path = _path_from_env("AETHERLAB_CHROMA_PATH", _default_chroma_path())
    library_path = _path_from_env("AETHERLAB_LIBRARY_DIR", data_dir / "library")
    qwen = load_qwen_settings()

    env_model = os.getenv("AETHERLAB_LLM_MODEL")
    llm_model = env_model or qwen.get("model") or "gpt-5.5"
    api_key = (
        os.getenv("AETHERLAB_OPENAI_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or qwen.get("api_key")
    )
    base_url = (
        os.getenv("AETHERLAB_OPENAI_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or qwen.get("base_url")
    )

    return AppSettings(
        data_dir=data_dir,
        cache_path=cache_path,
        chroma_path=chroma_path,
        library_path=library_path,
        openai_api_key=api_key,
        openai_base_url=base_url,
        llm_model=llm_model,
        llm_timeout_seconds=float(os.getenv("AETHERLAB_LLM_TIMEOUT", "60")),
        provider_source=qwen.get("source", "environment") if api_key or base_url or env_model else "environment",
    )


def load_qwen_settings(path: Path | None = None) -> dict[str, str]:
    """Load Qwen/OpenAI-compatible provider settings without logging secrets."""

    settings_path = path or Path(os.getenv("QWEN_SETTINGS_PATH", Path.home() / ".qwen" / "settings.json"))
    if not settings_path.exists():
        return {}

    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    model_name = str(_nested_get(payload, ["model", "name"]) or "")
    providers = _nested_get(payload, ["modelProviders", "openai"]) or []
    provider = _find_provider(providers, model_name)
    env_key = str(provider.get("envKey", "DASHSCOPE_API_KEY")) if provider else "DASHSCOPE_API_KEY"
    api_key = _nested_get(payload, ["env", env_key]) or os.getenv(env_key)

    result: dict[str, str] = {"source": str(settings_path)}
    if model_name:
        result["model"] = model_name
    if provider and provider.get("baseUrl"):
        result["base_url"] = str(provider["baseUrl"])
    if isinstance(api_key, str) and api_key.strip():
        result["api_key"] = api_key.strip()
    return result


def _default_data_dir() -> Path:
    """Stable per-user data directory, independent of the launch working dir."""
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "AetherLab"
    return Path.home() / ".aetherlab"


def _default_chroma_path() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "AetherLab" / "chroma"
    return Path.home() / ".aetherlab" / "chroma"


def _nested_get(payload: dict[str, Any], path: list[str]) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _find_provider(providers: Any, model_name: str) -> dict[str, Any] | None:
    if not isinstance(providers, list):
        return None
    for provider in providers:
        if isinstance(provider, dict) and provider.get("id") == model_name:
            return provider
    for provider in providers:
        if isinstance(provider, dict):
            return provider
    return None
