"""Bounded policy for OpenAI-compatible model clients.

Provider SDK retries multiply long read timeouts, so every asynchronous model
client shares this policy instead of inheriting the SDK defaults implicitly.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aetherlab.core.settings import AppSettings


MIN_LLM_TIMEOUT_SECONDS = 5.0
MAX_LLM_TIMEOUT_SECONDS = 900.0
MAX_LLM_RETRIES = 1

_HYBRID_QWEN_RE = re.compile(r"^qwen3\.[567]-(?:plus|max|flash)(?:$|-)")
_THINKING_ONLY_MODELS = {
    "qwen3.7-max-preview",
    "qwen3.7-max-2026-05-17",
}


def effective_llm_timeout(settings: "AppSettings") -> float:
    """Return the configured timeout inside the supported safety bounds."""
    try:
        value = float(getattr(settings, "llm_timeout_seconds", 60.0) or 60.0)
    except (TypeError, ValueError):
        value = 60.0
    return max(MIN_LLM_TIMEOUT_SECONDS, min(MAX_LLM_TIMEOUT_SECONDS, value))


def effective_llm_retries(settings: "AppSettings") -> int:
    """Return 0 or 1 retries; never inherit the SDK's larger default."""
    try:
        value = int(getattr(settings, "llm_max_retries", 0) or 0)
    except (TypeError, ValueError):
        value = 0
    return max(0, min(MAX_LLM_RETRIES, value))


def openai_client_kwargs(settings: "AppSettings") -> dict[str, Any]:
    """Keyword arguments shared by synchronous-compatible async clients."""
    return {
        "api_key": settings.openai_api_key,
        "base_url": settings.openai_base_url,
        "timeout": effective_llm_timeout(settings),
        "max_retries": effective_llm_retries(settings),
    }


def _model_id(model: str | None) -> str:
    return str(model or "").strip().lower().rsplit("/", 1)[-1]


def is_thinking_only_model(model: str | None) -> bool:
    name = _model_id(model)
    return (
        name in _THINKING_ONLY_MODELS
        or name.startswith("qwq")
        or name.startswith("deepseek-r1")
        or "thinking-only" in name
    )


def is_hybrid_qwen_model(model: str | None) -> bool:
    name = _model_id(model)
    return bool(_HYBRID_QWEN_RE.match(name)) and "coder" not in name and not is_thinking_only_model(name)


def codegen_request_kwargs(settings: "AppSettings") -> dict[str, Any]:
    """Disable default-on Qwen thinking for non-streaming scene codegen."""
    return non_thinking_request_kwargs(settings.llm_model)


def non_thinking_request_kwargs(model: str | None) -> dict[str, Any]:
    """Disable hybrid Qwen thinking for bounded structured-output calls."""
    if is_hybrid_qwen_model(model):
        return {"extra_body": {"enable_thinking": False}}
    return {}


def model_codegen_warning(model: str | None, timeout: float = 60.0) -> str:
    name = _model_id(model)
    if not name or "coder" in name:
        return ""
    if is_thinking_only_model(name):
        return (
            f"{model} is thinking-only. Full scene codegen remains bounded to "
            f"{int(timeout)}s; use qwen3-coder-plus for faster, more reliable scenes."
        )
    if is_hybrid_qwen_model(name):
        return (
            f"{model} enables thinking by default. AetherLab disables thinking for "
            "scene codegen; qwen3-coder-plus is still the recommended code model."
        )
    return ""


def active_provider_name(settings: "AppSettings") -> str:
    base = str(settings.openai_base_url or "").lower()
    model = _model_id(settings.llm_model)
    if not settings.openai_api_key:
        return "Offline"
    if getattr(settings, "provider_source", "") == "ollama-local" or "11434" in base:
        return "Ollama"
    if "dashscope" in base or "aliyun" in base or "alibabacloud" in base or model.startswith("qwen"):
        return "Qwen / DashScope"
    if "api.openai.com" in base or (not base and model.startswith(("gpt-", "o1", "o3", "o4"))):
        return "OpenAI"
    return "OpenAI-compatible endpoint"
