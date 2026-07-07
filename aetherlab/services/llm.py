"""OpenAI-compatible analytical solver with deterministic fallback."""

from __future__ import annotations

import asyncio
import json
import re
from collections import Counter

from aetherlab.core.models import ProblemRequest, SolverResult
from aetherlab.core.settings import AppSettings


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
        if self.settings.openai_api_key:
            try:
                return await self._solve_remote(request)
            except Exception as exc:
                return self._fallback(
                    request,
                    note=f"Remote model failed; deterministic fallback used: {exc}",
                )
        return self._fallback(request, note="No API key configured; deterministic fallback used.")

    async def _solve_remote(self, request: ProblemRequest) -> SolverResult:
        from openai import AsyncOpenAI

        # Lazy-create client on first use
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url,
                timeout=max(self.settings.llm_timeout_seconds, 300),
            )

        response = await self._client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are the AetherLab analytical solver. "
                        "Return strict JSON with keys summary, derivation_steps, "
                        "keywords, variables, and key_equations. "
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
                        "Omit plot if no curve captures the result."
                    ),
                },
                {"role": "user", "content": request.prompt},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content or ""
        payload = self._parse_json(content)
        plot = payload.get("plot")
        equations = payload.get("key_equations")
        return SolverResult(
            summary=str(payload.get("summary", "")).strip() or "Remote solver completed.",
            derivation_steps=[str(step) for step in payload.get("derivation_steps", [])],
            keywords=[str(keyword) for keyword in payload.get("keywords", [])],
            variables={str(k): float(v) for k, v in dict(payload.get("variables", {})).items()},
            model_name=self.settings.llm_model,
            raw_response=content,
            # Kept as the raw dict; validation happens at canvas build so the
            # cached payload stays faithful to what the model returned.
            plot=plot if isinstance(plot, dict) else None,
            key_equations=[str(e) for e in equations][:4] if isinstance(equations, list) else [],
        )

    def _parse_json(self, content: str) -> dict[str, object]:
        # Reasoning models (e.g. MiniMax-M3) may wrap output in <think> blocks
        # whose prose can contain stray braces - drop them before extraction.
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            raise

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
        from aetherlab.services.plotting import fallback_plot_payload
        from aetherlab.services.scene_templates import detect_domain

        domain = detect_domain(keywords, variables)
        return SolverResult(
            summary=summary,
            derivation_steps=steps,
            keywords=keywords,
            variables=variables,
            model_name="deterministic-fallback",
            raw_response=note,
            # Exercises the full expression-compile pipeline even without a key.
            plot=fallback_plot_payload(),
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
