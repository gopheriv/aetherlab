"""Bounded policy and per-model pathways for OpenAI-compatible clients.

Provider SDK retries multiply long read timeouts, so every asynchronous model
client shares this policy instead of inheriting the SDK defaults implicitly.

**Model pathways.** Models differ enormously in how long one call takes. A
standard chat model answers a codegen prompt in seconds; a *reasoning* model
(MiniMax-M*, QwQ, DeepSeek-R1, GLM thinking builds) spends thousands of tokens
inside ``<think>`` blocks first and can need many minutes. One global timeout
therefore either starves the slow models or leaves the fast ones hanging.

``resolve_pathway()`` maps a model id to a :class:`ModelPathway` describing how
to drive that family: the minimum wall-clock budget one call needs, whether a
timeout is worth retrying, and whether thinking should be switched off.
``effective_llm_timeout()`` then *raises* a too-small configured timeout to the
pathway's floor, so pointing AetherLab at a reasoning model works out of the
box instead of silently timing out into the fallback template.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aetherlab.core.settings import AppSettings


MIN_LLM_TIMEOUT_SECONDS = 5.0
# Headroom for reasoning models: a cinematic codegen call on a thinking model
# legitimately runs for many minutes, and clamping it lower guarantees the
# silent-fallback bug rather than preventing it.
MAX_LLM_TIMEOUT_SECONDS = 1800.0
MAX_LLM_RETRIES = 1

# Per-pathway wall-clock floors for ONE model call.
STANDARD_TIMEOUT_FLOOR = 60.0
REASONING_TIMEOUT_FLOOR = 900.0

_HYBRID_QWEN_RE = re.compile(r"^qwen3\.[567]-(?:plus|max|flash)(?:$|-)" )
_THINKING_ONLY_MODELS = {
    "qwen3.7-max-preview",
    "qwen3.7-max-2026-05-17",
}

# Families that always emit a long chain of thought before the answer, matched
# against the bare model id (vendor prefix stripped, lowercased).
_SLOW_REASONING_RE = re.compile(
    r"^(?:"
    r"minimax-m\d"        # MiniMax-M1/M2/M3…
    r"|qwq"               # Qwen QwQ
    r"|deepseek-r\d"      # DeepSeek-R1…
    r"|o[1-9](?:$|-)"     # OpenAI o1/o3/o4 reasoning line
    r"|glm-[\d.]+-think"  # GLM thinking builds
    r")"
)

# Kimi reasoning models (K3 "k3-agent", K2.8 "k2d8-preview", "kimi-*" aliases).
# Their API rejects any sampling temperature except 1 with HTTP 400, which
# would otherwise make every call fail into the deterministic fallback.
_KIMI_RE = re.compile(r"^(?:k\d+(?:d\d+)?(?:-|$)|kimi-)")


@dataclass(frozen=True)
class ModelPathway:
    """How one family of models must be driven.

    ``name`` is a stable id for diagnostics. ``min_timeout_seconds`` is the
    floor a single call needs. ``retry_on_timeout`` is False where retrying
    would simply burn a second full budget for the same reason.
    """

    name: str
    min_timeout_seconds: float
    retry_on_timeout: bool
    disable_thinking: bool
    # Some families accept exactly one temperature; None means any is fine.
    fixed_temperature: float | None = None
    # Stream replies so a gateway never sees a long silent request; the Kimi
    # gateway dropped long non-streamed requests while streamed ones completed.
    stream_requests: bool = False


PATHWAY_STANDARD = ModelPathway(
    name="standard", min_timeout_seconds=STANDARD_TIMEOUT_FLOOR,
    retry_on_timeout=True, disable_thinking=False,
)
PATHWAY_HYBRID_QWEN = ModelPathway(
    name="hybrid-qwen", min_timeout_seconds=STANDARD_TIMEOUT_FLOOR,
    retry_on_timeout=True, disable_thinking=True,
)
PATHWAY_REASONING = ModelPathway(
    name="reasoning", min_timeout_seconds=REASONING_TIMEOUT_FLOOR,
    retry_on_timeout=False, disable_thinking=False,
)
PATHWAY_KIMI = ModelPathway(
    name="kimi-reasoning", min_timeout_seconds=REASONING_TIMEOUT_FLOOR,
    retry_on_timeout=False, disable_thinking=False, fixed_temperature=1.0,
    stream_requests=True,
)


def resolve_pathway(model: str | None) -> ModelPathway:
    """Classify a model id into the pathway that says how to drive it."""
    name = _model_id(model)
    if _KIMI_RE.match(name):
        return PATHWAY_KIMI
    if _SLOW_REASONING_RE.match(name) or is_thinking_only_model(name):
        return PATHWAY_REASONING
    if is_hybrid_qwen_model(name):
        return PATHWAY_HYBRID_QWEN
    return PATHWAY_STANDARD


def settings_pathway(settings: "AppSettings") -> ModelPathway:
    """The pathway for the model this settings object selects."""
    return resolve_pathway(getattr(settings, "llm_model", ""))


def effective_llm_timeout(settings: "AppSettings") -> float:
    """Return the configured timeout inside the supported safety bounds.

    The configured value is authoritative — no hidden per-model floor is
    applied here (BUG-34: one bounded policy, no surprise overrides). The
    pathway instead supplies the *default* at settings-load time, and
    ``timeout_shortfall`` reports a configuration that is too low to succeed.
    """
    try:
        value = float(getattr(settings, "llm_timeout_seconds", 60.0) or 60.0)
    except (TypeError, ValueError):
        value = 60.0
    return max(MIN_LLM_TIMEOUT_SECONDS, min(MAX_LLM_TIMEOUT_SECONDS, value))


def structured_request_timeout(settings: "AppSettings", *, cap: float = 180.0) -> float:
    """Bound JSON-only planning and solving calls independently of scene codegen."""
    return min(effective_llm_timeout(settings), max(MIN_LLM_TIMEOUT_SECONDS, float(cap)))


class PolicyTemperature(float):
    """A temperature pinned by model policy that remembers what was asked for.

    It behaves as the float that is sent. ``wanted`` keeps the caller's
    original value so a failover to a different model family (see
    services/llm_client.py) can apply that family's own rule instead of
    inheriting the first model's pin.
    """

    wanted: float

    def __new__(cls, value: float, wanted: float) -> "PolicyTemperature":
        obj = super().__new__(cls, value)
        obj.wanted = float(wanted)
        return obj


def request_temperature(settings: "AppSettings", wanted: float) -> float:
    """The sampling temperature to send for this model.

    Callers ask for the temperature their task wants (hot for storyboards,
    cold for code). A pathway with a fixed temperature overrides it, because
    that API rejects any other value outright.
    """
    wanted = float(getattr(wanted, "wanted", wanted))
    fixed = settings_pathway(settings).fixed_temperature
    return PolicyTemperature(wanted if fixed is None else fixed, wanted)


def fallback_settings(settings: "AppSettings") -> "AppSettings | None":
    """Settings for the backup provider, or None when none is fully configured.

    The backup reuses every other setting (timeouts, retries); only the
    endpoint, key and model change. The vision model becomes the backup
    model too, because the primary's vision model is unknown to the backup.
    """
    key = getattr(settings, "fallback_api_key", None)
    url = getattr(settings, "fallback_base_url", None)
    model = getattr(settings, "fallback_llm_model", None)
    if not (key and url and model):
        return None
    from dataclasses import is_dataclass, replace
    from types import SimpleNamespace

    changes = {"openai_api_key": key, "openai_base_url": url, "llm_model": model,
               "vision_model": model if getattr(settings, "vision_model", None) else None}
    if is_dataclass(settings):
        return replace(settings, **changes)
    return SimpleNamespace(**{**vars(settings), **changes})


def default_timeout_for(model: str | None) -> float:
    """The timeout a model should get when the user has configured none."""
    return resolve_pathway(model).min_timeout_seconds


def timeout_shortfall(settings: "AppSettings") -> str:
    """Warn when the configured timeout is below what this model needs.

    Returns "" when the budget is adequate. Surfacing this beats silently
    overriding the user's setting: a reasoning model on a 180s budget times
    out every call and degrades to the built-in template.
    """
    pathway = settings_pathway(settings)
    configured = effective_llm_timeout(settings)
    if configured >= pathway.min_timeout_seconds:
        return ""
    return (
        f"{getattr(settings, 'llm_model', 'This model')} is a '{pathway.name}' model that "
        f"typically needs ~{pathway.min_timeout_seconds:.0f}s per call, but the configured "
        f"timeout is {configured:.0f}s. Raise 'llm_timeout_seconds' in Settings, or scenes "
        "will fall back to the built-in template."
    )


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


_DASHSCOPE_EXPLICIT_CACHE_MODELS = frozenset({
    "qwen3.7-plus", "qwen3.7-max", "qwen3.7-flash",
    "qwen3.8-max", "qwen3.8-flash", "qwen3-max", "kimi-k2.7-code",
})


def system_prompt_message(
    settings: "AppSettings", content: str, *, minimum_cache_chars: int = 3600
) -> dict[str, Any]:
    """Return a stable system message, enabling supported DashScope prompt caching.

    Explicit cache markers are sent only to Alibaba Model Studio endpoints and
    model ids documented as supporting them. Short prompts stay ordinary text
    because the provider's minimum cacheable prefix is 1,024 tokens.
    """
    base_url = str(getattr(settings, "openai_base_url", "") or "").lower()
    model = _model_id(getattr(settings, "llm_model", ""))
    dashscope_endpoint = "dashscope" in base_url or ".maas.aliyuncs.com" in base_url
    model_supported = any(
        model == supported or model.startswith(supported + "-")
        for supported in _DASHSCOPE_EXPLICIT_CACHE_MODELS
    )
    if dashscope_endpoint and model_supported and len(content) >= minimum_cache_chars:
        return {
            "role": "system",
            "content": [{
                "type": "text",
                "text": content,
                "cache_control": {"type": "ephemeral"},
            }],
        }
    return {"role": "system", "content": content}


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


def codegen_request_kwargs(
    settings: "AppSettings", *, minimax_thinking: bool | None = None
) -> dict[str, Any]:
    """Per-pathway flags for non-streaming scene code and structured JSON tasks.

    MiniMax supports its own nested ``thinking`` toggle; hybrid Qwen models
    use DashScope's ``enable_thinking`` flag. An omitted MiniMax override
    preserves the provider's existing default; compact structured tasks can
    disable thinking when reasoning tokens were consuming their output budget.
    """
    model = _model_id(settings.llm_model)
    if re.match(r"^minimax-m\d", model):
        if minimax_thinking is None:
            return {}
        thinking_type = "enabled" if minimax_thinking else "disabled"
        return {"extra_body": {"thinking": {"type": thinking_type}}}
    if settings_pathway(settings).disable_thinking:
        return {"extra_body": {"enable_thinking": False}}
    return {}


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
