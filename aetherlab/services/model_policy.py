"""Bounded policy for OpenAI-compatible model clients.

Provider SDK retries multiply long read timeouts, so every asynchronous model
client shares this policy instead of inheriting the SDK defaults implicitly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aetherlab.core.settings import AppSettings


MIN_LLM_TIMEOUT_SECONDS = 5.0
MAX_LLM_TIMEOUT_SECONDS = 900.0
MAX_LLM_RETRIES = 1


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
