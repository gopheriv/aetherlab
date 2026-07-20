"""Prompt router: decide which output modalities a problem actually warrants.

A single OpenAI-compatible classification call (strict JSON) with a
deterministic keyword-heuristic fallback, mirroring services/llm.py. Never
raises — always returns a usable OutputPlan so the pipeline can gate its stages
(a purely conceptual question may need only the PDF; a 3-D field problem skips
the 2-D canvas; a static definition skips the render entirely).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

from aetherlab.core.models import OutputPlan, ProblemRequest
from aetherlab.core.settings import AppSettings

log = logging.getLogger(__name__)

# Planning is cheap relative to a render; retry rather than silently under-plan.
PLANNER_ATTEMPTS = 3
PLANNER_BACKOFF_SECONDS = (1.0, 3.0)

_SYSTEM_PROMPT = (
    "You are the AetherLab lesson planner. Given a physics or math request, "
    "decide which output modalities genuinely help — pick the MINIMAL useful "
    "set, not everything. Return strict JSON with exactly these keys: "
    '{"needs_numeric": bool, "needs_2d": bool, "needs_3d": bool, '
    '"needs_animation": bool, "needs_pdf": bool, "rationale": short string}. '
    "Guidance: needs_numeric — the answer benefits from numerically integrating "
    "an ODE / time-evolution (oscillators, circuits, orbits, decay, projectiles). "
    "needs_2d — a 2-D plot (y vs x or vs t) clarifies the result. "
    "needs_3d — the phenomenon is inherently three-dimensional (fields, surfaces, "
    "potentials, orbitals, flux). needs_animation — motion or time-evolution is "
    "worth animating. needs_pdf — a written, cited derivation adds value (usually "
    "true). A purely conceptual 'what is / explain' question typically needs only "
    "the PDF. Respond with JSON only."
)

# Substring stems (lower-cased) — chosen so one entry catches inflections
# ("oscillat" → oscillator/oscillation/oscillating).
_DYNAMICS = (
    "oscillat", "pendulum", "motion", "orbit", "decay", "circuit", "trajector",
    "velocit", "dynamic", "differential equation", " ode", "harmonic", "damp",
    "spring", "projectile", "kinematic", "accelerat", "resonan", "diffus",
    "relaxation", "rlc", "lc circuit", "friction",
)
_THREE_D = (
    "3d", "3-d", "three dimensional", "three-dimensional", "surface", "vector field",
    "electric field", "magnetic field", "electromagnetic", "potential", "sphere",
    "orbital", "gradient", "flux", "manifold", "volume", "solid angle",
)
_MOTION = (
    "animate", "animation", "simulate", "simulation", "evolve", "over time",
    "time evolution", "moving", "propagat", "trajector",
)
_PLOT = (
    "plot", "graph", "curve", "versus", " vs ", "diagram", "chart", "visuali",
    "draw", "sketch",
)
_CONCEPTUAL = (
    "explain", "what is", "what are", "concept", "conceptual", "intuition",
    "define", "definition", "why ", "describe", "meaning", "difference between",
)


class Planner:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self._client = None

    async def plan(self, request: ProblemRequest) -> OutputPlan:
        """Plan the outputs, never below the deterministic heuristic floor.

        The model is asked for the minimal useful set, but a flaky or stingy
        reply must not silently drop a modality the prompt clearly warrants —
        that would mean the same question yields a video one run and not the
        next. So the remote plan is UNIONed with the heuristic floor, and the
        call is retried before conceding to the floor alone.
        """
        floor = self.heuristic_plan(request)
        if not self.settings.openai_api_key:
            return floor

        attempts = max(1, int(getattr(self.settings, "planner_attempts", PLANNER_ATTEMPTS)))
        for attempt in range(attempts):
            try:
                remote = await self._plan_remote(request)
                return _union(remote, floor)
            except Exception as exc:  # noqa: BLE001 — retried, then floor
                log.warning(
                    "Planner attempt %d/%d failed (%s: %s)",
                    attempt + 1, attempts, type(exc).__name__, exc,
                )
                if attempt < attempts - 1:
                    await asyncio.sleep(PLANNER_BACKOFF_SECONDS[
                        min(attempt, len(PLANNER_BACKOFF_SECONDS) - 1)
                    ])
        log.error("Planner fell back to the heuristic floor after %d attempts.", attempts)
        return floor

    async def _plan_remote(self, request: ProblemRequest) -> OutputPlan:
        from openai import AsyncOpenAI

        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url,
                timeout=max(self.settings.llm_timeout_seconds, 30),
            )

        response = await self._client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": request.prompt},
            ],
            temperature=0.0,
            max_tokens=400,
        )
        content = response.choices[0].message.content or ""
        payload = _parse_json(content)
        return OutputPlan.from_json(payload, model_name=self.settings.llm_model)

    def heuristic_plan(self, request: ProblemRequest) -> OutputPlan:
        """Deterministic keyword classifier — the offline / fallback path."""
        text = request.normalized_prompt().lower()

        def has(stems: tuple[str, ...]) -> bool:
            return any(stem in text for stem in stems)

        dynamics = has(_DYNAMICS)
        three_d = has(_THREE_D)
        plot_ask = has(_PLOT)
        conceptual = has(_CONCEPTUAL) and not (dynamics or plot_ask)

        needs_numeric = dynamics
        needs_3d = three_d
        # Animate by default: skip only when the ask is clearly conceptual or a
        # purely static plot request. Defaulting to "skip" would silently drop
        # the video for any prompt without an explicit motion cue.
        needs_animation = (
            dynamics or three_d or has(_MOTION) or not (conceptual or plot_ask)
        )
        # 2-D unless it's a 3-D-only phenomenon or a purely conceptual question.
        needs_2d = dynamics or plot_ask or not (conceptual or three_d)
        needs_pdf = True

        bits = []
        if dynamics:
            bits.append("dynamics/ODE terms")
        if three_d:
            bits.append("3-D geometry/field terms")
        if conceptual:
            bits.append("conceptual phrasing")
        if plot_ask:
            bits.append("explicit plot request")
        rationale = (
            "Heuristic plan from " + (", ".join(bits) if bits else "no strong signals")
            + f"; enabled: {', '.join(_enabled(needs_numeric, needs_2d, needs_3d, needs_animation, needs_pdf))}."
        )
        return OutputPlan(
            needs_numeric=needs_numeric,
            needs_2d=needs_2d,
            needs_3d=needs_3d,
            needs_animation=needs_animation,
            needs_pdf=needs_pdf,
            rationale=rationale,
            model_name="heuristic-fallback",
        )


def _union(remote: OutputPlan, floor: OutputPlan) -> OutputPlan:
    """Remote plan OR the heuristic floor — never fewer outputs than warranted.

    Keeps the model's reasoning, but records when the floor added something the
    model omitted so the decision stays auditable.
    """
    added = [
        name
        for name, r, f in (
            ("numeric", remote.needs_numeric, floor.needs_numeric),
            ("2d", remote.needs_2d, floor.needs_2d),
            ("3d", remote.needs_3d, floor.needs_3d),
            ("animation", remote.needs_animation, floor.needs_animation),
            ("pdf", remote.needs_pdf, floor.needs_pdf),
        )
        if f and not r
    ]
    rationale = remote.rationale
    if added:
        rationale = (rationale + " " if rationale else "") + (
            f"Heuristic floor also required: {', '.join(added)}."
        )
    return OutputPlan(
        needs_numeric=remote.needs_numeric or floor.needs_numeric,
        needs_2d=remote.needs_2d or floor.needs_2d,
        needs_3d=remote.needs_3d or floor.needs_3d,
        needs_animation=remote.needs_animation or floor.needs_animation,
        needs_pdf=remote.needs_pdf or floor.needs_pdf,
        rationale=rationale,
        model_name=remote.model_name,
    )


def _enabled(*flags: bool) -> list[str]:
    names = ("numeric", "2d", "3d", "animation", "pdf")
    return [name for name, on in zip(names, flags, strict=True) if on]


def _parse_json(content: str) -> dict[str, object]:
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise
