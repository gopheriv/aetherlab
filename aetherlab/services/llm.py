"""OpenAI-compatible analytical solver with deterministic fallback."""

from __future__ import annotations

import asyncio
import logging
import re
from collections import Counter

from aetherlab.core.models import ProblemRequest, SolverResult
from aetherlab.core.settings import AppSettings
from aetherlab.services.model_policy import request_temperature

log = logging.getLogger(__name__)

# A transient provider hiccup must never quietly downgrade the physics to the
# canned scaffold: retry hard before conceding. Correctness beats latency here.
SOLVER_ATTEMPTS = 3
SOLVER_BACKOFF_SECONDS = (2.0, 5.0)

# The keyless fallback's ODE models a damped harmonic oscillator; it may only be
# attached when the question really is about one (see _fallback).
OSCILLATOR_STEMS = (
    "oscillat", "harmonic", "spring", "damp", "pendulum", "vibrat", "resonan",
    "shm", "mass-spring", "restoring force",
)


COMMON_WORDS = {
    "about",
    "after",
    "and",
    "boundary",
    "derive",
    "explain",
    "for",
    "from",
    "give",
    "into",
    "math",
    "model",
    "of",
    "physical",
    "problem",
    "show",
    "simulate",
    "solve",
    "step",
    "the",
    "then",
    "through",
    "to",
    "using",
    "with",
}

DEFAULT_VARIABLES = {
    "damping": 0.15,
    "stiffness": 1.0,
    "mass": 1.0,
}

# Governing equations for the keyless fallback, per scene_templates domain.
# Mathtext-subset LaTeX (no environments) so the hero banner always renders.
FALLBACK_EQUATIONS: dict[str, list[str]] = {
    "oscillator": [
        r"m\ddot{x} + c\dot{x} + kx = 0",
        r"x(t) = A e^{-\zeta \omega_0 t} \cos(\omega_d t + \varphi)",
    ],
    "pendulum": [
        r"\ddot{\theta} + \frac{g}{\ell}\sin\theta = 0",
        r"T \approx 2\pi\sqrt{\ell / g}",
    ],
    "orbit": [
        r"F = -\frac{G M m}{r^2}\hat{r}",
        r"r(\varphi) = \frac{p}{1 + e\cos\varphi}",
    ],
    "em_field": [
        r"E = k q / r^2",
        r"\Phi_E = q / \varepsilon_0",
    ],
    "wave": [
        r"\frac{\partial^2 y}{\partial t^2} = c^2 \frac{\partial^2 y}{\partial x^2}",
        r"y(x,t) = A\sin(kx - \omega t)",
    ],
}


class AsyncLLMCoordinator:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        # Lazy-create client on first use — import is inside _solve_remote
        self._client = None

    async def solve(self, request: ProblemRequest) -> SolverResult:
        from aetherlab.services.parameters import apply_request_parameters

        if not self.settings.openai_api_key:
            solver = self._fallback(
                request, note="No API key configured; deterministic fallback used."
            )
            return apply_request_parameters(request, solver)

        attempts = max(1, int(getattr(self.settings, "solver_attempts", SOLVER_ATTEMPTS)))
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                solver = await self._solve_remote(request)
                return apply_request_parameters(request, solver)
            except Exception as exc:  # noqa: BLE001 — retried, then reported loudly
                last_exc = exc
                log.warning(
                    "Solver attempt %d/%d failed (%s: %s)",
                    attempt + 1, attempts, type(exc).__name__, exc,
                )
                if attempt < attempts - 1:
                    delay = SOLVER_BACKOFF_SECONDS[min(attempt, len(SOLVER_BACKOFF_SECONDS) - 1)]
                    await asyncio.sleep(delay)

        # Every attempt failed: this is a real quality downgrade, so say so
        # loudly rather than letting the canned scaffold pass as a real answer.
        log.error(
            "Solver fell back to the deterministic scaffold after %d failed attempts: %s",
            attempts, last_exc,
        )
        solver = self._fallback(
            request,
            note=(
                f"Remote model failed after {attempts} attempts; deterministic "
                f"fallback used (results are a generic scaffold, not solved physics): {last_exc}"
            ),
        )
        return apply_request_parameters(request, solver)

    async def _solve_remote(self, request: ProblemRequest) -> SolverResult:
        from aetherlab.services.llm_client import make_client


        # Lazy-create client on first use
        if self._client is None:
            self._client = make_client(self.settings)

        response = await self._client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are the AetherLab analytical solver. "
                        "Return strict JSON with keys summary, derivation_steps, "
                        "keywords, variables, and key_equations. Optionally add "
                        "variable_units (only when known), assumptions, and "
                        "derivation_records. Each derivation_record should identify "
                        "the 1-based step_index in derivation_steps and may contain "
                        "claim, from_expression, to_expression, and source_ref; "
                        "expressions must use plain arithmetic and named variables. "
                        "Do not invent a checkable record when a step is prose or "
                        "depends on an unstated identity. "
                        "Variables must map names to numbers. "
                        "key_equations: 1-4 LaTeX strings, the governing equation "
                        "FIRST (e.g. \"m\\\\ddot{x} + c\\\\dot{x} + kx = 0\"). Use "
                        "inline LaTeX only — fractions/roots/greek/sub-superscripts "
                        "are fine, but no \\\\begin environments, no \\\\text, no "
                        "displaystyle. "
                        "Optionally add a plot key describing the picture that best "
                        "captures the result: {\"kind\": \"explicit\"|\"parametric\", "
                        "\"t_range\": [t0, t1], \"x_range\"?: [lo, hi], "
                        "\"y_range\"?: [lo, hi], \"x_label\"?: str, \"y_label\"?: str, "
                        "\"curves\": [{\"name\": str, \"x\"?: expr, \"y\": expr, "
                        "\"style\"?: \"solid\"|\"dashed\", "
                        "\"role\"?: \"primary\"|\"secondary\"|\"reference\"}], "
                        "\"fill_between\"?: {\"upper\": expr, \"lower\": expr}, "
                        "\"points\"?: [{\"t\": num, \"label\": str}]}. "
                        "Exactly one curve should have role primary (the physics hero); "
                        "use role reference + style dashed for envelopes/asymptotes/targets; "
                        "fill_between for energy bands or |psi|^2; points for equilibria or "
                        "resonances (max 6 curves, 8 points). A bare single-curve form "
                        "{kind, x, y, t_range, ...} is also accepted. "
                        "Example: {\"kind\": \"explicit\", \"t_range\": [0, 10], "
                        "\"y_label\": \"x(t)\", \"curves\": ["
                        "{\"name\": \"x(t)\", \"y\": \"exp(-damping*t)*cos(2*t)\", \"role\": \"primary\"}, "
                        "{\"name\": \"envelope\", \"y\": \"exp(-damping*t)\", \"style\": \"dashed\", \"role\": \"reference\"}], "
                        "\"points\": [{\"t\": 0, \"label\": \"release\"}]}. "
                        "Expressions may use only: the free variable t, names from "
                        "variables, numeric literals, + - * / ** ( ), the functions "
                        "sin cos tan sinh cosh tanh arcsin arccos arctan exp log log10 "
                        "sqrt abs sign, and constants pi, e. For explicit kind, x is t. "
                        "Omit plot if no curve captures the result. "
                        "When the problem is governed by an ODE, also add an ode key "
                        "for the numerical ground truth: {\"state\": [names...], "
                        "\"rhs\": [expr per state], \"initial\": [numbers], "
                        "\"t_range\": [t0, t1], \"observe\": name}. Each rhs expr may use "
                        "the state names, the variables, t, the same functions/constants, "
                        "and defines that state's time derivative. Omit ode if not an ODE."
                    ),
                },
                {"role": "user", "content": request.prompt},
            ],
            temperature=request_temperature(self.settings, 0.2),
        )
        content = response.choices[0].message.content or ""
        payload = self._parse_json(content)
        plot = payload.get("plot")
        numeric_spec = payload.get("ode") or payload.get("numeric_spec")
        equations = payload.get("key_equations")
        units = payload.get("variable_units")
        records = payload.get("derivation_records")
        assumptions = payload.get("assumptions")
        return SolverResult(
            summary=str(payload.get("summary", "")).strip() or "Remote solver completed.",
            derivation_steps=[str(step) for step in payload.get("derivation_steps", [])],
            keywords=[str(keyword) for keyword in payload.get("keywords", [])],
            variables={str(k): float(v) for k, v in dict(payload.get("variables", {})).items()},
            # the model that actually answered (the backup, if the primary failed)
            model_name=getattr(self._client, "last_served_by", None) or self.settings.llm_model,
            raw_response=content,
            # Kept as the raw dict; validation happens at canvas build so the
            # cached payload stays faithful to what the model returned.
            plot=plot if isinstance(plot, dict) else None,
            numeric_spec=numeric_spec if isinstance(numeric_spec, dict) else None,
            key_equations=[str(e) for e in equations][:4] if isinstance(equations, list) else [],
            variable_units={str(k): str(v) for k, v in units.items() if str(v).strip()}
            if isinstance(units, dict) else {},
            derivation_records=[dict(record) for record in records[:12] if isinstance(record, dict)]
            if isinstance(records, list) else [],
            assumptions=[str(item) for item in assumptions[:12] if str(item).strip()]
            if isinstance(assumptions, list) else [],
        )

    def _parse_json(self, content: str) -> dict[str, object]:
        from aetherlab.services.model_json import load_model_json

        return load_model_json(content)

    def _fallback(self, request: ProblemRequest, *, note: str) -> SolverResult:
        keywords = extract_keywords(request.prompt)
        variables = dict(DEFAULT_VARIABLES)
        variables.update(request.parameters)
        if not keywords:
            keywords = ["differential equation", "phase space", "stability"]

        focus = ", ".join(keywords[:3])
        steps = [
            f"Normalize the request into governing quantities for {focus}.",
            "State assumptions, domains, and conserved or dissipated quantities.",
            "Derive the symbolic relationship and isolate controllable parameters.",
            "Map each scalar parameter onto a simulation ValueTracker-compatible state.",
            "Cross-check the result against local references when available.",
        ]
        summary = (
            f"{note} Prepared an analytical scaffold with {len(steps)} derivation "
            f"steps and {len(variables)} simulation variables."
        )
        awaitable_pause()
        from aetherlab.services.numeric import fallback_numeric_spec
        from aetherlab.services.plotting import fallback_plot_payload
        from aetherlab.services.scene_templates import detect_domain

        domain = detect_domain(keywords, variables)
        # The fallback ODE *is* a damped harmonic oscillator, so attach it only
        # when the topic actually is one. Otherwise the verifier would report
        # "3/3 physics checks passed" about a system the user never asked about
        # (e.g. an entropy question), which is worse than reporting nothing.
        topic = f"{request.prompt} {' '.join(keywords)}".lower()
        oscillator_like = any(stem in topic for stem in OSCILLATOR_STEMS)
        return SolverResult(
            summary=summary,
            derivation_steps=steps,
            keywords=keywords,
            variables=variables,
            model_name="deterministic-fallback",
            raw_response=note,
            # Exercises the full expression-compile pipeline even without a key.
            plot=fallback_plot_payload(),
            # Ground-truth ODE so the offline canvas/PDF integrate a real system
            # — but only when it genuinely models the asked-about system.
            numeric_spec=fallback_numeric_spec() if oscillator_like else None,
            key_equations=FALLBACK_EQUATIONS.get(domain, FALLBACK_EQUATIONS["oscillator"]),
        )


def extract_keywords(prompt: str, limit: int = 8) -> list[str]:
    tokens = [
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", prompt)
        if token.lower() not in COMMON_WORDS
    ]
    counts = Counter(tokens)
    ranked = [word for word, _ in counts.most_common(limit)]

    phrase_patterns = [
        "fourier transform",
        "navier stokes",
        "lorentz attractor",
        "general relativity",
        "damped harmonic oscillator",
        "eigenvalue",
        "eigenvalues",
        "lagrangian",
        "hamiltonian",
    ]
    lower = prompt.lower()
    phrases = []
    for phrase in phrase_patterns:
        # Match both space-separated and hyphenated forms
        if phrase in lower or phrase.replace(" ", "-") in lower:
            phrases.append(phrase)
    merged = phrases + [word for word in ranked if word not in phrases]
    return merged[:limit]


def awaitable_pause() -> None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
