"""LLM-driven dynamic Manim scene code generation."""

from __future__ import annotations

import json
import logging
import re

from aetherlab.core.models import ProblemRequest, RagResult, SolverResult
from aetherlab.core.settings import AppSettings

log = logging.getLogger(__name__)

SCENE_GENERATION_SYSTEM_PROMPT = """You are the AetherLab Manim scene architect.
Your job is to generate a complete, self-contained Manim Community scene that
visualizes the physics/math problem described by the analytical solver.

## Rules
1. Output ONLY valid Python code — no markdown fences, no commentary.
2. Use `from manim import *` (Manim Community). Never use manimlib.
3. The scene class MUST be named exactly `{class_name}` and inherit from `Scene`.
4. Use the solver's variables dict to parameterize the animation — these become
   interactive ValueTrackers in the desktop UI.
5. Animate the core physics: show the equation, then visualize the key behavior
   (wave, trajectory, vector field, phase portrait, etc.).
6. Keep the scene short: 8–15 seconds of animation.
7. Use `self.wait()` sparingly. Prefer `self.play()` with Transform, Create, Write.
8. All text must use `font_size` kwarg (24–36 for titles, 18–24 for labels).
9. Use `VGroup` with `.arrange()` for grouped elements.
10. Fade out elements before replacing them to avoid visual clutter.
11. The last 2 seconds should have a subtle ambient animation (pulsing, slow
    rotation) using ValueTracker + always_redraw — never a static freeze.
12. Use Axes, NumberPlane, PolarPlane as appropriate for the domain.
13. For ODEs: plot the solution curve on Axes with a traced moving point.
14. For mechanics: show forces as arrows, trajectories as parametric curves.
15. For algebra/analysis: animate the key identity or transform step-by-step.
16. Import numpy as np at the top if you need it.
17. Do NOT use `config.frame_width` or `config.pixel_width` — use defaults.
18. The code must compile with `compile(code, '<generated>', 'exec')`.
"""

SCENE_GENERATION_USER_TEMPLATE = """## Problem
{prompt}

## Analytical Solution Summary
{summary}

## Derivation Steps
{steps}

## Simulation Variables (name → value)
{variables}

## RAG Context ({rag_count} references found)
{rag_context}

Generate the Manim scene class now. Output ONLY the Python code."""


class SceneGenerator:
    """Generate dynamic Manim scene code via LLM."""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        # Lazy-create client on first use — import is inside _generate_remote
        self._client = None

    async def generate(
        self,
        request: ProblemRequest,
        solver: SolverResult,
        rag: RagResult,
        class_name: str = "AetherLabScene",
    ) -> str:
        """Generate Manim scene code using the LLM."""
        if not self.settings.openai_api_key:
            return self._fallback_scene(class_name, solver)

        try:
            return await self._generate_remote(request, solver, rag, class_name)
        except Exception as exc:
            log.warning("LLM scene generation failed, using fallback: %s", exc)
            return self._fallback_scene(class_name, solver)

    async def _generate_remote(
        self,
        request: ProblemRequest,
        solver: SolverResult,
        rag: RagResult,
        class_name: str,
    ) -> str:
        from openai import AsyncOpenAI

        # Lazy-create client on first use
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url,
                timeout=max(self.settings.llm_timeout_seconds, 300),
            )

        steps_text = "\n".join(
            f"{i}. {step}" for i, step in enumerate(solver.derivation_steps[:6], 1)
        ) or "No derivation steps available."

        vars_text = "\n".join(
            f"  {name} = {value}" for name, value in sorted(solver.variables.items())
        ) or "  (no variables)"

        rag_lines = []
        for hit in rag.hits[:3]:
            rag_lines.append(f"- {hit.source_name}: {hit.excerpt[:200]}")
        rag_context = "\n".join(rag_lines) if rag_lines else "No local references."

        system = SCENE_GENERATION_SYSTEM_PROMPT.format(class_name=class_name)
        user = SCENE_GENERATION_USER_TEMPLATE.format(
            prompt=request.prompt,
            summary=solver.summary,
            steps=steps_text,
            variables=vars_text,
            rag_count=len(rag.hits),
            rag_context=rag_context,
        )

        response = await self._client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.4,
            max_tokens=8192,
        )
        content = response.choices[0].message.content or ""
        return self._extract_code(content, class_name)

    def _extract_code(self, content: str, class_name: str) -> str:
        """Strip markdown fences and validate the extracted code."""
        code = content.strip()

        # Strip markdown fences if present
        fence_match = re.search(r"```(?:python)?\s*\n(.*?)```", code, re.DOTALL)
        if fence_match:
            code = fence_match.group(1).strip()

        # Ensure the class name matches
        if f"class {class_name}" not in code:
            # Try to rename
            code = re.sub(
                r"class \w+\(Scene\)",
                f"class {class_name}(Scene)",
                code,
                count=1,
            )

        # Ensure import
        if "from manim import" not in code and "import manim" not in code:
            code = "from manim import *\nimport numpy as np\n\n" + code

        return code

    def _fallback_scene(self, class_name: str, solver: SolverResult) -> str:
        """Deterministic fallback that uses solver variables."""
        import math

        damping = solver.variables.get("damping", 0.15)
        stiffness = solver.variables.get("stiffness", 1.0)
        mass = solver.variables.get("mass", 1.0)
        title = solver.summary[:70] if solver.summary else "Physics Simulation"

        return f'''from manim import *
import numpy as np


class {class_name}(Scene):
    def construct(self):
        title = Text("{_escape(title)}", font_size=32)
        title.to_edge(UP)

        axes = Axes(
            x_range=[-3, 3, 1],
            y_range=[-2, 2, 1],
            axis_config={{"include_numbers": True}},
        ).scale(0.65).shift(DOWN * 0.5)

        damping = ValueTracker({damping})
        stiffness = ValueTracker({stiffness})

        def get_curve():
            d = damping.get_value()
            k = stiffness.get_value()
            return axes.plot(
                lambda x: np.exp(-d * (x + 3)) * np.sin(k * x * 2),
                color=BLUE,
            )

        curve = always_redraw(get_curve)

        dot = always_redraw(lambda: Dot(
            axes.c2p(3, np.exp(-damping.get_value() * 6) * np.sin(stiffness.get_value() * 6)),
            color=YELLOW, radius=0.06,
        ))

        self.play(Write(title), run_time=1)
        self.play(Create(axes), run_time=1)
        self.play(Create(curve), FadeIn(dot), run_time=2)
        self.wait(2)
        self.play(
            damping.animate.set_value({damping * 3}),
            run_time=3,
            rate_func=there_and_back,
        )
        self.wait(2)
'''.strip() + "\n"


def _escape(text: str) -> str:
    """Escape string for embedding in Python source."""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
