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
                        "keywords, and variables. Variables must map names to numbers."
                    ),
                },
                {"role": "user", "content": request.prompt},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content or ""
        payload = self._parse_json(content)
        return SolverResult(
            summary=str(payload.get("summary", "")).strip() or "Remote solver completed.",
            derivation_steps=[str(step) for step in payload.get("derivation_steps", [])],
            keywords=[str(keyword) for keyword in payload.get("keywords", [])],
            variables={str(k): float(v) for k, v in dict(payload.get("variables", {})).items()},
            model_name=self.settings.llm_model,
            raw_response=content,
        )

    def _parse_json(self, content: str) -> dict[str, object]:
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
        return SolverResult(
            summary=summary,
            derivation_steps=steps,
            keywords=keywords,
            variables=variables,
            model_name="deterministic-fallback",
            raw_response=note,
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
    phrases = [phrase for phrase in phrase_patterns if phrase in lower]
    merged = phrases + [word for word in ranked if word not in phrases]
    return merged[:limit]


def awaitable_pause() -> None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
