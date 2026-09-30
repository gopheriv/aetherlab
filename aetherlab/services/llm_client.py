"""Model client with an automatic backup provider.

``make_client(settings)`` returns an object with the same
``client.chat.completions.create(**kwargs)`` shape as ``openai.AsyncOpenAI``.
Every request goes to the primary provider first. When the primary fails with
a transport or API error (a gateway cutting a long request, a timeout, a quota
or server error, a rejected parameter) or returns an empty reply, the same
request is retried once on the backup provider from ``settings.fallback_*``.

The retry is rebuilt for the backup's own model family. The model name is
swapped, and the temperature is re-derived from what the caller originally
asked for (``PolicyTemperature.wanted``), not from the primary's pin. Pathway
request flags such as thinking toggles are recomputed for the backup model. A
scene-generation client (``purpose="scene"``) asks a MiniMax backup to write
code with thinking off: with thinking on, M3 spent its whole token budget
reasoning and returned no code, both in the M6 comparison and in the first
live failover.

Pathways with ``stream_requests`` (the Kimi gateway) are streamed and
reassembled into an ordinary reply under the same overall deadline, because
that gateway dropped long non-streamed requests while streamed ones finished.

Why: the Kimi K3 gateway worked on one day and cut 3 of 4 codegen requests at
6 minutes on the day before. Without a backup, such a day silently turns every
AI scene into the built-in template.
"""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from typing import Any

from aetherlab.services import model_policy

log = logging.getLogger(__name__)

DROP_RETRIES = 2
DROP_BACKOFF_S = 5.0


class FailoverChatClient:
    """``AsyncOpenAI``-compatible chat client: primary first, backup on failure."""

    def __init__(self, settings: Any, purpose: str = "general") -> None:
        import openai

        self.settings = settings
        self.purpose = purpose
        self._primary = openai.AsyncOpenAI(**model_policy.openai_client_kwargs(settings))
        self._fallback_settings = model_policy.fallback_settings(settings)
        self._fallback = (
            openai.AsyncOpenAI(**model_policy.openai_client_kwargs(self._fallback_settings))
            if self._fallback_settings is not None else None
        )
        # APITimeoutError is an APIConnectionError; TimeoutError is the stream deadline.
        self._failover_errors = (openai.APIConnectionError, openai.APIStatusError, TimeoutError)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        # Which model actually answered the most recent request (for diagnostics).
        self.last_served_by: str | None = None
        self.last_failover_reason: str = ""

    @property
    def has_fallback(self) -> bool:
        return self._fallback is not None

    async def _create(self, **kwargs: Any) -> Any:
        self.last_failover_reason = ""
        try:
            response = await self._send_primary(kwargs)
        except self._failover_errors as exc:
            if self._fallback is None:
                raise
            reason = f"{type(exc).__name__}: {str(exc)[:200]}"
        else:
            if self._fallback is None or not _unusable(response):
                self.last_served_by = str(kwargs.get("model") or "")
                return response
            reason = "empty reply from the primary model"
        backup = self._fallback_kwargs(kwargs)
        log.warning(
            "Primary model %s failed (%s); retrying once on backup model %s.",
            kwargs.get("model"), reason, backup["model"],
        )
        self.last_failover_reason = reason
        response = await self._send(self._fallback, self._fallback_settings, backup)
        self.last_served_by = str(backup["model"])
        return response

    async def _send_primary(self, kwargs: dict[str, Any]) -> Any:
        """The primary request; a dropped connection is retried when there is no backup.

        MiniMax regularly drops connections (TLS EOF) for a few minutes at a time;
        one drop used to turn a whole AI scene into the built-in template. A drop
        fails fast, so retrying is cheap. A timeout already spent the full budget
        and is never retried. With a backup configured, failing over is the retry.
        """
        import openai

        for drop in range(DROP_RETRIES + 1):
            try:
                return await self._send(self._primary, self.settings, kwargs)
            except openai.APIConnectionError as exc:
                if (isinstance(exc, openai.APITimeoutError) or self._fallback is not None
                        or drop == DROP_RETRIES):
                    raise
                log.warning("Connection to %s dropped (%s); retrying (%d/%d).",
                            kwargs.get("model"), exc, drop + 1, DROP_RETRIES)
                await asyncio.sleep(DROP_BACKOFF_S * (drop + 1))
        raise RuntimeError("unreachable")

    async def _send(self, client: Any, settings: Any, kwargs: dict[str, Any]) -> Any:
        if kwargs.get("stream") or not model_policy.settings_pathway(settings).stream_requests:
            return await client.chat.completions.create(**kwargs)
        deadline = model_policy.effective_llm_timeout(settings)
        return await asyncio.wait_for(_collect_stream(client, kwargs), timeout=deadline)

    def _fallback_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        fb = self._fallback_settings
        backup = dict(kwargs)
        backup["model"] = fb.llm_model
        if "temperature" in backup:
            backup["temperature"] = model_policy.request_temperature(fb, backup["temperature"])
        # extra_body only ever carries the primary pathway's request flags
        # (thinking toggles); rebuild them for the backup model.
        backup.pop("extra_body", None)
        thinking = False if self.purpose == "scene" else None
        backup.update(model_policy.codegen_request_kwargs(fb, minimax_thinking=thinking))
        return backup


async def _collect_stream(client: Any, kwargs: dict[str, Any]) -> Any:
    """Stream one completion and reassemble it into a non-streamed reply shape."""
    stream = await client.chat.completions.create(**kwargs, stream=True)
    text: list[str] = []
    reasoning: list[str] = []
    finish = None
    model = kwargs.get("model")
    async for chunk in stream:
        model = getattr(chunk, "model", None) or model
        for choice in getattr(chunk, "choices", None) or []:
            delta = getattr(choice, "delta", None)
            if delta is not None:
                if getattr(delta, "content", None):
                    text.append(delta.content)
                if getattr(delta, "reasoning_content", None):
                    reasoning.append(delta.reasoning_content)
            finish = getattr(choice, "finish_reason", None) or finish
    message = SimpleNamespace(role="assistant", content="".join(text),
                              reasoning_content="".join(reasoning) or None)
    return SimpleNamespace(model=model, usage=None,
                           choices=[SimpleNamespace(index=0, message=message, finish_reason=finish)])


def _unusable(response: Any) -> bool:
    """True when a reply carries no usable text (e.g. all tokens spent thinking)."""
    try:
        message = response.choices[0].message
    except (AttributeError, IndexError, TypeError):
        return True
    if getattr(message, "tool_calls", None):
        return False                     # a tool-call reply carries no text by design
    content = getattr(message, "content", None)
    return not (isinstance(content, str) and content.strip())


def make_client(settings: Any, purpose: str = "general") -> FailoverChatClient:
    """The model client every LLM caller should use.

    ``purpose="scene"`` marks scene-generation clients (storyboard, code,
    repair); a MiniMax backup then writes with thinking off.
    """
    return FailoverChatClient(settings, purpose=purpose)
