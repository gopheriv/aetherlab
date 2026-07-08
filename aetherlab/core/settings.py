"""Application settings.

Provider resolution precedence:
1. Environment variables (AETHERLAB_* / OPENAI_*)
2. The app's own config file (saved by the in-app Settings dialog)
3. ~/.qwen/settings.json (legacy autoload)
"""

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
    llm_context_window: int = 250_000
    # Optional vision-capable model (same OpenAI-compatible endpoint) used by
    # the scene critic to look at rendered frames. None disables the critique
    # loop entirely (renders ship uncritiqued, as before).
    vision_model: str | None = None
    # v3: pull supplementary references from the web (Wikipedia) alongside the
    # local textbook library. Fail-soft and time-boxed; disable for offline use.
    web_references: bool = True
    web_ref_timeout: float = 8.0
    # Narration (the narration↔visual sync feature): synthesize a voiceover fit
    # to the rendered video. Fail-soft — off, or missing edge-tts/ffmpeg, keeps
    # the silent render.
    narration_enabled: bool = False
    tts_voice: str = "en-US-AndrewMultilingualNeural"
    tts_rate: str = "+8%"
    # Pluggable render backend. Local is today's behavior; cloud/auto are
    # additive and fail soft to local when GitHub Actions is unavailable.
    render_mode: str = "local"  # local | cloud | auto
    cloud_provider: str = "github_actions"
    github_repo: str = ""
    github_token: str = ""
    github_workflow: str = "render.yml"
    github_branch: str = "renders"
    github_oauth_client_id: str = ""
    cloud_render_threshold: float = 3.0
    cloud_poll_seconds: int = 8
    cloud_render_timeout: int = 1800
    visual_critic_max_passes: int = 2
    visual_critic_keyframes: int = 6
    min_quality_score: float = 0.0
    scene_candidates: int = 1
    scene_candidate_concurrency: int = 2
    # When a vision critic is configured, run the multi-candidate quality
    # tournament by default (cheap-first escalation keeps it near one render).
    # Independent of scene_candidates, which is the explicit power-user override.
    auto_tournament: bool = True
    provider_source: str = "environment"


OLLAMA_OPENAI_BASE_URL = "http://localhost:11434/v1"


def _path_from_env(name: str, default: Path) -> Path:
    value = os.getenv(name)
    return Path(value).expanduser() if value else default


def app_config_path() -> Path:
    """Location of the app-native config file written by the Settings dialog."""
    return _path_from_env("AETHERLAB_DATA_DIR", _default_data_dir()) / "settings.json"


def load_app_config() -> dict[str, str]:
    """Read the config saved by the in-app Settings dialog (may not exist)."""
    path = app_config_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        k: str(v)
        for k, v in payload.items()
        if isinstance(v, (str, int, float)) and str(v).strip()
    }


def save_app_config(values: dict[str, str | None]) -> Path:
    """Persist Settings-dialog values. Empty/None values are dropped."""
    path = app_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_app_config()
    for key, value in values.items():
        if value is None or not str(value).strip():
            existing.pop(key, None)
        else:
            existing[key] = str(value).strip()
    path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return path


def load_settings() -> AppSettings:
    # app_config_path() keys off env/default only, so honoring app_cfg's own
    # data_dir override here is safe (no recursion) and lets the Settings
    # dialog's Data path field persist across restarts.
    app_cfg = load_app_config()
    legacy_env = load_legacy_env()
    data_dir = _path_from_env(
        "AETHERLAB_DATA_DIR",
        Path(app_cfg["data_dir"]).expanduser() if app_cfg.get("data_dir") else _default_data_dir(),
    )
    cache_path = _path_from_env("AETHERLAB_CACHE_PATH", data_dir / "cache.sqlite3")
    chroma_path = _path_from_env("AETHERLAB_CHROMA_PATH", _default_chroma_path())
    library_path = _path_from_env(
        "AETHERLAB_LIBRARY_DIR",
        (
            Path(app_cfg["library_path"]).expanduser()
            if app_cfg.get("library_path")
            else data_dir / "library"
        ),
    )
    # The ~/.qwen autoload is a developer-machine convenience: a student's app
    # must never silently inherit provider credentials from an unrelated tool.
    # Opt back in with AETHERLAB_QWEN_AUTOLOAD=1.
    qwen = load_qwen_settings() if os.getenv("AETHERLAB_QWEN_AUTOLOAD") == "1" else {}

    preset = (os.getenv("AETHERLAB_PROVIDER") or app_cfg.get("provider_preset") or "").lower()

    env_model = _first_env("AETHERLAB_LLM_MODEL", "MANIM_MODEL", "GPT_MODEL", "CHAT_MODEL")
    legacy_model = _first_mapping(legacy_env, "MANIM_MODEL", "GPT_MODEL", "CHAT_MODEL")
    llm_model = env_model or app_cfg.get("model") or legacy_model or qwen.get("model") or "gpt-5.5"
    api_key = (
        _first_env("AETHERLAB_OPENAI_API_KEY", "OPENAI_API_KEY", "GPT_API_KEY", "DASHSCOPE_API_KEY")
        or app_cfg.get("api_key")
        or _first_mapping(legacy_env, "OPENAI_API_KEY", "GPT_API_KEY", "DASHSCOPE_API_KEY")
        or qwen.get("api_key")
    )
    base_url = (
        _first_env("AETHERLAB_OPENAI_BASE_URL", "OPENAI_BASE_URL", "GPT_BASE_URL", "LLM_BASE_URL")
        or app_cfg.get("base_url")
        or _first_mapping(legacy_env, "OPENAI_BASE_URL", "GPT_BASE_URL", "LLM_BASE_URL")
        or qwen.get("base_url")
    )

    # The "ollama" preset fills whatever the tiers above left unset: Ollama's
    # OpenAI-compatible endpoint needs no real key, just a placeholder.
    if preset == "ollama":
        base_url = base_url or OLLAMA_OPENAI_BASE_URL
        api_key = api_key or "ollama"

    if env_model or _first_env(
        "AETHERLAB_OPENAI_API_KEY",
        "OPENAI_API_KEY",
        "GPT_API_KEY",
        "DASHSCOPE_API_KEY",
    ):
        source = "environment"
    elif preset == "ollama":
        source = "ollama-local"
    elif app_cfg.get("api_key") or app_cfg.get("model") or app_cfg.get("base_url"):
        source = str(app_config_path())
    elif legacy_env and (legacy_env.get("OPENAI_API_KEY") or legacy_env.get("GPT_API_KEY")):
        source = str(_legacy_env_path() or "legacy manim-bot .env")
    else:
        source = qwen.get("source", "environment")

    cloud_enabled = _as_bool(
        os.getenv("CLOUD_RENDER_ENABLED"),
        legacy_env.get("CLOUD_RENDER_ENABLED"),
        default=False,
    )

    return AppSettings(
        data_dir=data_dir,
        cache_path=cache_path,
        chroma_path=chroma_path,
        library_path=library_path,
        openai_api_key=api_key,
        openai_base_url=base_url,
        llm_model=llm_model,
        llm_timeout_seconds=float(_first_env("AETHERLAB_LLM_TIMEOUT", "LLM_TIMEOUT") or "60"),
        vision_model=(
            _first_env("AETHERLAB_VISION_MODEL", "VISION_MODEL")
            or app_cfg.get("vision_model")
            or None
        ),
        web_references=_as_bool(
            os.getenv("AETHERLAB_WEB_REFS"), app_cfg.get("web_references"), default=True
        ),
        narration_enabled=_as_bool(
            os.getenv("AETHERLAB_NARRATION"),
            os.getenv("VOICEOVER_ENABLED"),
            os.getenv("TTS_ENABLED"),
            app_cfg.get("narration_enabled"),
            default=False,
        ),
        tts_voice=(
            _first_env("AETHERLAB_TTS_VOICE", "TTS_VOICE")
            or app_cfg.get("tts_voice")
            or "en-US-AndrewMultilingualNeural"
        ),
        tts_rate=_first_env("AETHERLAB_TTS_RATE", "TTS_RATE") or app_cfg.get("tts_rate") or "+8%",
        render_mode=_render_mode(
            os.getenv("AETHERLAB_RENDER_MODE")
            or app_cfg.get("render_mode")
            or ("auto" if cloud_enabled else None)
        ),
        cloud_provider=(
            os.getenv("AETHERLAB_CLOUD_PROVIDER")
            or app_cfg.get("cloud_provider")
            or "github_actions"
        ),
        github_repo=(
            _first_env("AETHERLAB_RENDER_REPO", "CLOUD_RENDER_REPO")
            or app_cfg.get("github_repo")
            or _first_mapping(legacy_env, "CLOUD_RENDER_REPO")
            or ""
        ),
        github_token=(
            _first_env("AETHERLAB_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN")
            or app_cfg.get("github_token")
            or _first_mapping(legacy_env, "GITHUB_TOKEN", "GH_TOKEN")
            or ""
        ),
        github_workflow=_workflow_name(
            _first_env("AETHERLAB_GITHUB_WORKFLOW", "CLOUD_RENDER_WORKFLOW")
            or app_cfg.get("github_workflow")
            or _first_mapping(legacy_env, "CLOUD_RENDER_WORKFLOW")
            or "render.yml"
        ),
        github_branch=(
            _first_env("AETHERLAB_GITHUB_BRANCH", "CLOUD_RENDER_BRANCH")
            or app_cfg.get("github_branch")
            or _first_mapping(legacy_env, "CLOUD_RENDER_BRANCH")
            or "renders"
        ),
        github_oauth_client_id=(
            os.getenv("AETHERLAB_GITHUB_CLIENT_ID")
            or app_cfg.get("github_oauth_client_id")
            or ""
        ),
        cloud_render_threshold=_as_float(
            os.getenv("AETHERLAB_CLOUD_RENDER_THRESHOLD"),
            app_cfg.get("cloud_render_threshold"),
            default=3.0,
        ),
        cloud_poll_seconds=_as_int(
            os.getenv("AETHERLAB_CLOUD_POLL_SECONDS"),
            os.getenv("CLOUD_RENDER_POLL"),
            app_cfg.get("cloud_poll_seconds"),
            legacy_env.get("CLOUD_RENDER_POLL"),
            default=8,
        ),
        cloud_render_timeout=_as_int(
            os.getenv("AETHERLAB_CLOUD_RENDER_TIMEOUT"),
            os.getenv("CLOUD_RENDER_TIMEOUT"),
            app_cfg.get("cloud_render_timeout"),
            legacy_env.get("CLOUD_RENDER_TIMEOUT"),
            default=1800,
        ),
        visual_critic_max_passes=_as_int(
            os.getenv("AETHERLAB_VISUAL_CRITIC_MAX_PASSES"),
            os.getenv("VISUAL_CRITIC_MAX_PASSES"),
            app_cfg.get("visual_critic_max_passes"),
            default=2,
        ),
        visual_critic_keyframes=_as_int(
            os.getenv("AETHERLAB_VISUAL_CRITIC_KEYFRAMES"),
            os.getenv("VISUAL_CRITIC_KEYFRAMES"),
            app_cfg.get("visual_critic_keyframes"),
            default=6,
        ),
        min_quality_score=_as_float(
            os.getenv("AETHERLAB_MIN_QUALITY_SCORE"),
            app_cfg.get("min_quality_score"),
            default=0.0,
        ),
        scene_candidates=_as_int(
            os.getenv("AETHERLAB_SCENE_CANDIDATES"),
            app_cfg.get("scene_candidates"),
            default=1,
        ),
        scene_candidate_concurrency=_as_int(
            os.getenv("AETHERLAB_SCENE_CANDIDATE_CONCURRENCY"),
            app_cfg.get("scene_candidate_concurrency"),
            default=2,
        ),
        auto_tournament=_as_bool(
            os.getenv("AETHERLAB_AUTO_TOURNAMENT"),
            app_cfg.get("auto_tournament"),
            default=True,
        ),
        provider_source=source,
    )


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return None


def _first_mapping(values: dict[str, str], *names: str) -> str | None:
    for name in names:
        value = values.get(name)
        if value is not None and value.strip():
            return value.strip()
    return None


def _workflow_name(value: str | None) -> str:
    name = Path(str(value or "render.yml").strip()).name
    return name or "render.yml"


def load_legacy_env(path: Path | None = None) -> dict[str, str]:
    """Read a legacy manim-bot .env as a compatibility fallback.

    The parsed values never mutate os.environ and are lower precedence than the
    app config. This lets migrations reuse provider/cloud settings without
    silently overriding an explicit AetherLab choice.
    """
    env_path = path or _legacy_env_path()
    if not env_path or not env_path.exists():
        return {}
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    result: dict[str, str] = {}
    for line in lines:
        item = line.strip()
        if not item or item.startswith("#") or "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value:
            result[key] = value
    return result


def _legacy_env_path() -> Path | None:
    if _as_bool(os.getenv("AETHERLAB_DISABLE_LEGACY_ENV"), default=False):
        return None
    explicit = os.getenv("AETHERLAB_LEGACY_ENV_PATH") or os.getenv("MANIM_BOT_ENV_PATH")
    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    root = Path(__file__).resolve().parents[2]
    candidates.extend([
        root / ".env",
        root.parent / "manim-bot" / ".env",
    ])
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _as_bool(*values, default: bool) -> bool:
    """First non-None value coerced to bool ('0'/'false'/'no'/'off' → False)."""
    for v in values:
        if v is None:
            continue
        if isinstance(v, bool):
            return v
        s = str(v).strip().lower()
        if s in ("0", "false", "no", "off", ""):
            return False
        return True
    return default


def _as_float(*values, default: float) -> float:
    for v in values:
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return default


def _as_int(*values, default: int) -> int:
    for v in values:
        if v is None:
            continue
        try:
            return int(v)
        except (TypeError, ValueError):
            continue
    return default


def _render_mode(value: str | None) -> str:
    mode = str(value or "local").strip().lower()
    return mode if mode in {"local", "cloud", "auto"} else "local"


def load_qwen_settings(path: Path | None = None) -> dict[str, str]:
    """Load Qwen/OpenAI-compatible provider settings without logging secrets."""

    settings_path = path or Path(
        os.getenv("QWEN_SETTINGS_PATH", Path.home() / ".qwen" / "settings.json")
    )
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
