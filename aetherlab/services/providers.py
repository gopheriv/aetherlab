"""LLM provider discovery and connectivity checks.

Students shouldn't need an API key to use AetherLab's AI features: Ollama
serves an OpenAI-compatible endpoint locally, so if it's installed we can
offer it as a one-click provider. This module owns detection ("is Ollama
running, which models does it have?") and a cheap connectivity test for
whatever provider is configured.

Leaf module: stdlib + (lazily) the openai client for test_connection. No Qt.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aetherlab.core.settings import AppSettings

log = logging.getLogger(__name__)

OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"


def detect_ollama(timeout: float = 2.0) -> list[str]:
    """Return the locally installed Ollama model names, or [] when Ollama is
    absent/unreachable. Never raises — absence is a normal state."""
    try:
        request = urllib.request.Request(
            OLLAMA_TAGS_URL, headers={"User-Agent": "AetherLab provider probe"}
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        models = payload.get("models", [])
        names = [
            str(m.get("name", "")).strip()
            for m in models
            if isinstance(m, dict) and str(m.get("name", "")).strip()
        ]
        return names
    except Exception as exc:  # noqa: BLE001 — any failure means "not available"
        log.debug("Ollama not detected: %s", exc)
        return []


def test_connection(settings: "AppSettings", timeout: float = 20.0) -> tuple[bool, str]:
    """One-token chat ping against the configured provider.

    Returns (ok, human message). Never raises — this backs a Settings-dialog
    button and must always produce a displayable result.
    """
    if not settings.openai_api_key:
        return False, "No API key configured."
    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=timeout,
            max_retries=0,
        )
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
        )
        model = getattr(response, "model", "") or settings.llm_model
        return True, f"Connected — {model} responded."
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        if len(message) > 160:
            message = message[:157] + "..."
        return False, f"Connection failed: {message}"
