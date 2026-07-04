"""LLM-driven dynamic Manim scene code generation."""

from __future__ import annotations

import json
import logging
import re

from aetherlab.core.models import ProblemRequest, RagResult, SolverResult
from aetherlab.core.settings import AppSettings
from aetherlab.services.error_learner import preventive_pitfalls_block
from aetherlab.services.scene_templates import build_scene, detect_domain, load_scene_palette

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


log = logging.getLogger(__name__)

SCENE_GENERATION_SYSTEM_PROMPT = """You are the AetherLab Cinematic Scene Architect — a physicist who directs like a
motion designer and stages like a filmmaker. You write ONE self-contained Manim
Community scene that turns an analytical result into 15–22 seconds of science
cinema: something a physics student would screenshot, replay, and send to a
friend. Correctness is the floor. Wonder is the target.

════════════════════════════════════════════════════════════════════════
§0 · HARD CONSTRAINTS  (break one and the render dies — obey all)
════════════════════════════════════════════════════════════════════════
0.1  Output ONLY valid Python. No markdown fences, no prose, no leading comments.
0.2  `from manim import *` (Manim Community). Never manimlib. `import numpy as np`
     if used. Use ONLY real Manim Community mobjects, animations, rate functions,
     and color constants — invent nothing.
0.3  Exactly one scene class, named `{class_name}`, inheriting `Scene`
     (or `MovingCameraScene`/`ThreeDScene` if the story truly needs it), with
     `def construct(self)`.
0.4  Must pass `compile(code, '<generated>', 'exec')`. Do not touch
     `config.frame_width`/`config.pixel_width`.
0.5  Keep everything inside the frame: after building a group, guard with
     `grp.scale_to_fit_width(config.frame_width - 1)` and `.move_to(ORIGIN)`,
     or lay out with `.arrange()`/`.next_to()`/`.to_edge()`. Never let text or
     curves bleed off-screen or overlap into mud.
0.6  Surface the solver's `variables` as on-screen, ValueTracker-driven numbers
     (`DecimalNumber` / `always_redraw`) so they read as live and become sliders.
0.7  15–22 s total. Never end frozen: the last 2–3 s is a living idle loop
     (slow rotation, gentle pulse, drifting tracer) via ValueTracker +
     always_redraw or an updater.

════════════════════════════════════════════════════════════════════════
§1 · WRITE THE SCENARIO FIRST  (the #1 lever on creativity)
════════════════════════════════════════════════════════════════════════
Before any code, decide the *world* this equation inhabits. A graph is evidence;
a scenario is a story. Pick a concrete physical protagonist and stage it:

  • Give the system a body: a bob on a string, a mass on a spring, a planet with
    a comet-tail, a bead on a wire, a charged sphere, a plucked string, a packet
    of wave crests, a spinning top, a droplet, a ray of light bending.
  • Give it a world: a horizon line, a pivot, a central star, a pair of plates,
    a medium boundary, a potential-well "landscape" the particle rolls in.
  • Give it stakes: what changes? What is conserved while everything else moves?
    What limit is approached? What breaks the symmetry?

Then structure THREE ACTS with clear act breaks (a beat of stillness or a wipe
between them so the viewer feels the turn):

  ACT I — ESTABLISH (≈25%): Fade up on the physical object at its initial
    condition, at rest or poised. Name it with a lower-third title. Let the
    governing law appear beside it as if the world summoned its own equation.
  ACT II — EVOLVE (≈50%): Release it. Let the dynamics play in real time — the
    pendulum swings and decays, the orbit sweeps, the wave propagates, the series
    accretes. Track the ONE quantity that matters (energy, amplitude, phase,
    partial sum) with a synchronized live readout or a second small panel.
  ACT III — REVEAL (≈25%): Deliver the insight. Snap to the invariant, overlay
    the envelope, coincide the curves, close the loop of the orbit, land the
    limit. This is the HERO FRAME (see §5). Hold it, then drift into the idle
    loop as the title fades to a quiet credit.

════════════════════════════════════════════════════════════════════════
§2 · DIRECTOR'S TOOLKIT  (reach for these — not just Axes.plot)
════════════════════════════════════════════════════════════════════════
Staging mobjects:  Dot, LabeledDot, Vector, Arrow, Line, DashedLine, Angle,
  Arc, Circle, Ellipse, Sector, AnnularSector, Polygon, RoundedRectangle,
  Axes, NumberPlane, PolarPlane, NumberLine, BarChart, Surface, ParametricFunction,
  ImplicitFunction, VectorField, ArrowVectorField, StreamLines, FunctionGraph,
  Brace, BraceLabel, SurroundingRectangle, Cross, Star, Triangle, DecimalNumber,
  ValueTracker, TracedPath.
Reveal / emphasis:  Create, Write, DrawBorderThenFill, GrowFromCenter,
  GrowFromEdge, GrowArrow, SpiralIn, FadeIn(shift=...), Transform,
  ReplacementTransform, TransformMatchingShapes, TransformMatchingTex,
  Indicate, Flash, Circumscribe, FocusOn, Wiggle, ApplyWave, ShowPassingFlash.
Living motion:  always_redraw, add_updater, ValueTracker.animate.set_value,
  Rotating, Rotate, MoveAlongPath, Homotopy, UpdateFromAlphaFunc.
Depth & light:  set_opacity, set_stroke(width=..., opacity=...) for a fat dim
  glow behind a thin bright line, set_color_by_gradient, set_fill(opacity=...),
  DashedVMobject for "ghost" references, TracedPath for comet trails,
  z_index for layering.
Camera (only if it earns it):  MovingCameraScene → self.camera.frame.animate
  .scale(0.6).move_to(focus); ThreeDScene → self.set_camera_orientation(...),
  self.begin_ambient_camera_rotation(rate=0.1) for a slow orbit around a surface.

════════════════════════════════════════════════════════════════════════
§3 · ANIMATION PRINCIPLES  (make motion feel intentional, not mechanical)
════════════════════════════════════════════════════════════════════════
  • STAGING: one clear idea per beat. Fade out finished elements so the frame
    never carries more than the eye can hold (~3 focal objects max).
  • ANTICIPATION: before a big move, a tiny counter-move or a held breath.
  • EASING & RHYTHM: never leave run_time at the default for everything. Mix
    fast reveals (0.6–1.0s) with a slow, savored climax (2.5–4s). Use `smooth`,
    `ease_in_out_sine`, `there_and_back`, `rate_functions.ease_out_back`,
    `rush_into`/`rush_from`. Silence (self.wait) is a tool — use it before the
    reveal.
  • FOLLOW-THROUGH & SECONDARY ACTION: when the main object moves, let its
    trail, shadow, or a coupled quantity react a beat later.
  • CONTINUITY: transform related objects into each other
    (ReplacementTransform / TransformMatchingTex) rather than fade-out/fade-in,
    so ideas *become* each other.

════════════════════════════════════════════════════════════════════════
§4 · LIGHT, COLOR & TYPE  (the difference between a plot and a poster)
════════════════════════════════════════════════════════════════════════
  • PALETTE: choose 2–3 hues + 1 accent and commit. Suggested cinematic sets on
    Manim's dark bg: {BLUE_D, TEAL, WHITE, +YELLOW accent} /
    {PURPLE, PINK, WHITE, +GOLD} / {GREEN_D, BLUE, GREY_B, +RED accent}.
  • SEMANTIC COLOR: one hue = the driver (input/cause), one = the response
    (output/effect), the accent = the "aha". Keep it consistent the whole scene.
  • GLOW: draw each hero curve twice — a wide low-opacity stroke under a thin
    bright one — to fake bloom. Gradients along a curve read as energy/flow.
  • TYPE: titles in Text (font_size 30–40) placed like a lower-third; math in
    MathTex; labels 18–24. Never a paragraph — 3–6 words max per beat. Let math
    write on with Write, and morph equations with TransformMatchingTex so the
    algebra feels alive.
  • SCAFFOLDING RECEDES: axes/grids fade in dim (stroke_opacity ~0.35) and stay
    background; the physics is always the brightest thing on screen.

════════════════════════════════════════════════════════════════════════
§5 · THE HERO FRAME  (design the one image people remember)
════════════════════════════════════════════════════════════════════════
Every scene earns exactly one climactic composition where the meaning locks in:
the orbit closes into a perfect ellipse with the swept-area sectors equal; the
damped envelope kisses the oscillation's peaks; the Fourier partial sum snaps
onto the square wave; the phase spiral collapses to the fixed point; the field
lines bloom symmetric around the charge. Build the whole scene toward it.
Techniques to sell it: Flash/Circumscribe on the key object, a brief
self.camera.frame zoom (MovingCameraScene), a held self.wait(1.2), the accent
color arriving ONLY here. Then exhale into the idle loop.

════════════════════════════════════════════════════════════════════════
§6 · DOMAIN PLAYBOOKS  (pick the one that fits; blend if needed)
════════════════════════════════════════════════════════════════════════
  • OSCILLATIONS / ODEs: real pendulum or spring on the left, its solution curve
    tracing on Axes on the right, a phase-portrait spiral converging to the
    attractor below. Envelope as a dashed ghost. Amplitude as a live DecimalNumber.
  • ORBITS / GRAVITATION: central star (glowing Dot), planet on a parametric
    ellipse with a TracedPath comet-tail, radius vector sweeping equal-area
    Sectors that visibly match — Kepler's 2nd law as the hero frame. Energy /
    angular-momentum bar holding flat.
  • WAVES / OPTICS: a wavefront of stacked crests marching across; refraction
    bending a ray at a boundary; superposition adding two ApplyWave strings into
    a beat pattern. Color the phase.
  • E&M / FIELDS: ArrowVectorField or StreamLines responding to a source you can
    move; Gauss surface as a glowing closed curve; field lines threading it.
  • QUANTUM: a potential-well "landscape", a wavepacket (Gaussian) propagating
    and spreading; |ψ|² shaded under the curve; energy levels as horizontal lines
    lighting up.
  • SERIES / TRANSFORMS / ANALYSIS: build term-by-term, each new term a colored
    curve, the partial sum (bright) visibly converging onto the dashed target;
    the error region shrinking to nothing at the reveal.
  • THERMO / STAT MECH: a cloud of Dots as particles, a piston, a distribution
    histogram (BarChart) relaxing toward equilibrium.

════════════════════════════════════════════════════════════════════════
§7 · ANTI-PATTERNS  (never ship these)
════════════════════════════════════════════════════════════════════════
  ✗ A bare Axes with a single static curve and a title. That is a screenshot,
    not a scene.
  ✗ Everything appearing at once, then nothing moving.
  ✗ Ten labels crowding the frame; walls of text; equations that never transform.
  ✗ Uniform run_time and default easing throughout — it reads as robotic.
  ✗ Ending on a frozen last frame.
  ✗ Colors with no meaning; scaffolding brighter than the physics.

Constraints are the canvas; creativity is the paint. Stage a world, direct three
acts, land one unforgettable hero frame, and breathe at the end. Output ONLY the
Python code for `{class_name}`.
"""

STORYBOARD_SYSTEM_PROMPT = """You are the AetherLab creative director. Design — do NOT code — a short
science-cinema treatment for the physics problem you are given. Think like a
filmmaker: concrete staging, three acts, one unforgettable hero frame.

Return STRICT JSON only (no markdown, no commentary) with exactly these keys:
{
  "concept": "one-sentence creative concept — the WORLD this equation lives in",
  "staging": "the concrete physical protagonist and its stage (objects, layout)",
  "palette": {"primary": "<manim color name>", "secondary": "<manim color name>",
               "accent": "<manim color name>"},
  "acts": [
    {"name": "ESTABLISH", "duration_s": <number>,
     "beats": ["what happens, beat by beat"]},
    {"name": "EVOLVE", "duration_s": <number>, "beats": [...]},
    {"name": "REVEAL", "duration_s": <number>, "beats": [...]}
  ],
  "hero_frame": "the single climactic composition the whole scene builds toward",
  "idle_loop": "the subtle living animation for the final ~2 seconds",
  "narration": ["one short spoken line per act, matching its beats"]
}

Rules: total duration 15-22 seconds across acts. Prefer a real-world referent
over a bare graph. Every act's beats must be implementable with stock Manim
Community mobjects. The variables you are given become on-screen live numbers —
work at least one into the staging."""


SCENE_CODEGEN_SYSTEM_PROMPT = """You are the AetherLab Manim implementation engineer. You are given a locked
storyboard designed by the creative director. Implement it EXACTLY — every act,
every beat, the hero frame, and the idle loop — as ONE Manim Community scene.

HARD CONSTRAINTS (violating any ruins the render):
1. Output ONLY valid Python — no markdown fences, no prose.
2. `from manim import *` (Manim Community). Never manimlib. `import numpy as np`
   if used. Use ONLY real Manim Community mobjects, animations, rate functions,
   and color constants — invent nothing.
3. Exactly one scene class named `{class_name}` inheriting `Scene` (or
   `MovingCameraScene` if the storyboard demands camera moves), with
   `def construct(self)`.
4. Must pass `compile(code, '<generated>', 'exec')`. Do not touch config.*.
5. Keep everything inside the frame: guard grouped layouts with
   `grp.scale_to_fit_width(config.frame_width - 1)` and `.move_to(ORIGIN)`,
   or lay out with `.arrange()`/`.next_to()`/`.to_edge()`.
6. Surface the given variables as ValueTracker-driven DecimalNumbers on screen.
7. Match each act's duration_s with your run_time/wait budget (±20%).
8. End with the storyboard's idle loop via ValueTracker + always_redraw —
   never a frozen last frame.
9. Use the storyboard's palette consistently; the accent color appears ONLY at
   the hero frame."""


SCENE_REVISE_SYSTEM_PROMPT = """You are the AetherLab scene reviser. A rendered Manim scene was reviewed by
a visual critic. Revise the COMPLETE scene to address every critique point
while preserving the storyboard's concept, acts, and hero frame.

Rules:
1. Output ONLY valid Python — no markdown fences, no commentary.
2. Keep the class named exactly `{class_name}` (inherits Scene, defines
   `def construct(self)`).
3. Address the critique concretely (spacing, legibility, pacing, palette,
   overlap, dead time) — do not simplify the scene into a bare plot.
4. Use only real Manim Community APIs."""


SCENE_REPAIR_SYSTEM_PROMPT = """You are the AetherLab Manim repair engineer. A Manim Community scene you
wrote failed at render time. Fix the exact error and return the COMPLETE
corrected scene.

Rules:
1. Output ONLY valid Python — no markdown fences, no commentary.
2. Keep the class named exactly `{class_name}` (inherits Scene, defines
   `def construct(self)`).
3. Change as little as possible: fix the failing API usage (wrong kwarg,
   nonexistent method, bad constant) while preserving the visual design.
4. Use only real Manim Community APIs. If unsure a kwarg exists, drop it or
   use the closest documented equivalent.
"""

SCENE_REPAIR_USER_TEMPLATE = """## Render error
{error}

## The scene code that failed
{code}

Return the complete corrected Python file now."""


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
        # Lazy-create client on first use — import is inside _ensure_client
        self._client = None
        # Most recent storyboard (dict) — the critic evaluates renders against it.
        self._last_storyboard: dict | None = None

    async def generate(
        self,
        request: ProblemRequest,
        solver: SolverResult,
        rag: RagResult,
        class_name: str = "AetherLabScene",
        *,
        feedback: str | None = None,
        previous_code: str | None = None,
    ) -> str:
        """Generate Manim scene code using the LLM.

        When ``feedback`` (and optionally ``previous_code``) is supplied, the
        prompt asks the model to *repair* the previous attempt using the real
        error text — this powers the error-aware self-heal loop.
        """
        if not self.settings.openai_api_key:
            return self._fallback_scene(class_name, solver)

        try:
            return await self._generate_remote(
                request, solver, rag, class_name, feedback=feedback, previous_code=previous_code
            )
        except Exception as exc:
            log.warning("LLM scene generation failed, using fallback: %s", exc)
            return self._fallback_scene(class_name, solver)
    ) -> str:
        """Generate Manim scene code using the LLM."""
        if not self.settings.openai_api_key:
            return self._fallback_scene(class_name, solver)

        # One retry before falling back: reasoning models occasionally blow
        # their output budget or hiccup transiently, and a cinematic scene is
        # worth a second attempt.
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                return await self._generate_remote(request, solver, rag, class_name)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                log.warning(
                    "LLM scene generation attempt %d failed: %s", attempt + 1, exc
                )
        log.warning("LLM scene generation failed twice, using fallback: %s", last_exc)
        return self._fallback_scene(class_name, solver)

    async def _generate_remote(
        self,
        request: ProblemRequest,
        solver: SolverResult,
        rag: RagResult,
        class_name: str,
        *,
        feedback: str | None = None,
        previous_code: str | None = None,
    ) -> str:
    def _ensure_client(self):
        from openai import AsyncOpenAI

        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url,
                timeout=max(self.settings.llm_timeout_seconds, 300),
            )
        return self._client

    async def storyboard(
        self,
        request: ProblemRequest,
        solver: SolverResult,
        rag: RagResult,
    ) -> dict | None:
        """Directing pass: a high-temperature creative treatment as strict JSON.

        Returns None on any failure — the caller falls back to the proven
        single-call cinematic generation, so storyboarding can only ever add
        quality, never subtract reliability.
        """
        import json as _json

        vars_text = "\n".join(
            f"  {name} = {value}" for name, value in sorted(solver.variables.items())
        ) or "  (no variables)"
        user = (
            f"## Problem\n{request.prompt}\n\n"
            f"## Analytical summary\n{solver.summary}\n\n"
            f"## Variables (become live on-screen numbers)\n{vars_text}\n\n"
            "Design the storyboard JSON now."
        )
        try:
            client = self._ensure_client()
            response = await client.chat.completions.create(
                model=self.settings.llm_model,
                messages=[
                    {"role": "system", "content": STORYBOARD_SYSTEM_PROMPT},
                    {"role": "user", "content": user},
                ],
                # Ideation runs hot; the codegen pass runs cold. This split is
                # the whole point of storyboarding separately.
                temperature=0.9,
                max_tokens=4096,
            )
            content = response.choices[0].message.content or ""
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            match = re.search(r"\{.*\}", content, re.DOTALL)
            board = _json.loads(match.group(0) if match else content)
            if not isinstance(board, dict) or "acts" not in board:
                return None
            self._last_storyboard = board
            return board
        except Exception as exc:  # noqa: BLE001 — storyboard is best-effort
            log.info("Storyboard pass failed (%s); using single-call generation.", exc)
            return None

    async def _generate_remote(
        self,
        request: ProblemRequest,
        solver: SolverResult,
        rag: RagResult,
        class_name: str,
    ) -> str:
        self._ensure_client()

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

        system = (
            SCENE_GENERATION_SYSTEM_PROMPT.format(class_name=class_name)
            + "\n\n"
            + preventive_pitfalls_block()
            + _palette_prompt_hint(load_scene_palette(getattr(self.settings, "data_dir", None)))
        )
        # .replace (not .format): the prompt body contains literal braces
        # .replace (not .format): the prompt bodies contain literal braces
        # (color-palette sets like {BLUE_D, TEAL, ...}) that would break .format.
        from aetherlab.services.error_learner import preventive_pitfalls_block

        # Two-call generation: hot directing pass → cold implementation pass.
        # Storyboard failure degrades to the proven single-call cinematic path.
        import json as _json

        board = await self.storyboard(request, solver, rag)
        if board is not None:
            system = (
                SCENE_CODEGEN_SYSTEM_PROMPT.replace("{class_name}", class_name)
                + "\n\n"
                + preventive_pitfalls_block()
            )
            user = (
                f"## Locked storyboard (implement exactly)\n"
                f"{_json.dumps(board, indent=2)}\n\n"
                f"## Problem\n{request.prompt}\n\n"
                f"## Analytical summary\n{solver.summary}\n\n"
                f"## Derivation steps\n{steps_text}\n\n"
                f"## Variables (name = value)\n{vars_text}\n\n"
                f"## Reference context\n{rag_context}\n\n"
                "Output ONLY the Python code implementing the storyboard."
            )
            temperature = 0.15  # implementation runs cold — precision over flair
        else:
            system = (
                SCENE_GENERATION_SYSTEM_PROMPT.replace("{class_name}", class_name)
                + "\n\n"
                + preventive_pitfalls_block()
            )
            user = SCENE_GENERATION_USER_TEMPLATE.format(
                prompt=request.prompt,
                summary=solver.summary,
                steps=steps_text,
                variables=vars_text,
                rag_count=len(rag.hits),
                rag_context=rag_context,
            )
            temperature = 0.4

        # Machines without a LaTeX toolchain can't render MathTex — force the
        # scene to unicode Text so it still renders everywhere. (Lazy import:
        # manim_runtime imports this module at top level.)
        from aetherlab.services.manim_runtime import detect_latex

        if not detect_latex():
            system += (
                "\n\nIMPORTANT — NO LaTeX ON THIS MACHINE: never use MathTex, "
                "Tex, or SingleStringMathTex. Write every formula with "
                "Text(...) using unicode math (×, ·, ², ³, √, θ, ω, π, ½, ∂)."
            )

        if feedback:
            user += _repair_addendum(feedback, previous_code)
        # Keep the assembled context within the configured model window so an
        # oversized RAG excerpt can't overflow it (~3 chars/token, reserving the
        # output budget). At the default 250k window this never trips.
        char_budget = max(2000, (self.settings.llm_context_window - 32768) * 3)
        if len(system) + len(user) > char_budget:
            user = user[: max(500, char_budget - len(system))]

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
        """Strip markdown fences and normalize the extracted code."""
        code = content.strip()

            temperature=temperature,
            # Reasoning models (MiniMax-M3, QwQ) spend thousands of tokens on
            # <think> blocks, and the cinematic prompt yields 100+ line scenes —
            # leave generous room or the code gets cut off mid-statement.
            max_tokens=32768,
        )
        choice = response.choices[0]
        if choice.finish_reason == "length":
            # Truncated replies produce code that dies at compile with a
            # confusing SyntaxError — fail loudly so retry/fallback handles it.
            raise ValueError("LLM reply was truncated at the max_tokens limit.")
        content = choice.message.content or ""
        return self._extract_code(content, class_name)

    async def repair(self, code: str, error: str, class_name: str) -> str:
        """Ask the LLM to fix a scene that failed at render time."""
        from openai import AsyncOpenAI

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
                    "content": SCENE_REPAIR_SYSTEM_PROMPT.format(class_name=class_name),
                },
                {
                    "role": "user",
                    "content": SCENE_REPAIR_USER_TEMPLATE.format(
                        # Generous window: the root cause of a Manim failure is
                        # often buried under chained tracebacks/LaTeX logs.
                        error=error[-12000:], code=code
                    ),
                },
            ],
            temperature=0.2,
            max_tokens=32768,
        )
        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise ValueError("Repair reply was truncated at the max_tokens limit.")
        return self._extract_code(choice.message.content or "", class_name)

    async def revise(self, code: str, critique: str, class_name: str) -> str:
        """Aesthetic revision: rework a *rendering* scene per visual critique.

        Distinct from repair(): repair fixes crashes minimally; revise improves
        composition/pacing/legibility while preserving the storyboard intent.
        """
        client = self._ensure_client()
        response = await client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": SCENE_REVISE_SYSTEM_PROMPT.format(class_name=class_name),
                },
                {
                    "role": "user",
                    "content": (
                        f"## Visual critique of the rendered result\n{critique}\n\n"
                        f"## The scene code that produced it\n{code}\n\n"
                        "Return the complete revised Python file now."
                    ),
                },
            ],
            temperature=0.3,
            max_tokens=32768,
        )
        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise ValueError("Revise reply was truncated at the max_tokens limit.")
        return self._extract_code(choice.message.content or "", class_name)

    def _extract_code(self, content: str, class_name: str) -> str:
        """Strip reasoning blocks and markdown fences, validate the code."""
        code = content.strip()

        # Reasoning models (e.g. MiniMax-M3, QwQ) prefix output with
        # <think>...</think> blocks — drop them before code extraction.
        code = re.sub(r"<think>.*?</think>", "", code, flags=re.DOTALL).strip()

        # Strip markdown fences if present
        fence_match = re.search(r"```(?:python)?\s*\n(.*?)```", code, re.DOTALL)
        if fence_match:
            code = fence_match.group(1).strip()

        # Ensure the scene class is named exactly `class_name`, preserving its
        # base class. This must match ANY base (Scene, ThreeDScene,
        # MovingCameraScene, PolarPlane-based, etc.), not only `(Scene)`.
        if f"class {class_name}" not in code:
            code = _rename_scene_class(code, class_name)

        # Ensure imports so the scene is self-contained even if the model
        # omitted them (or we prepended a rename onto a bare body).
        if "from manim import" not in code and "import manim" not in code:
            code = "from manim import *\nimport numpy as np\n\n" + code

        return code

    def _fallback_scene(self, class_name: str, solver: SolverResult) -> str:
        """Deterministic, domain-aware fallback built from solver output (WP7)."""
        domain = detect_domain(solver.keywords, solver.variables)
        title = solver.summary[:70] if solver.summary else "Physics Simulation"
        data_dir = getattr(self.settings, "data_dir", None)
        return build_scene(
            class_name=class_name,
            domain=domain,
            title=title,
            summary=solver.summary or "",
            steps=solver.derivation_steps,
            variables=solver.variables,
            palette=load_scene_palette(data_dir),
        )


def _palette_prompt_hint(palette: dict[str, str] | None) -> str:
    """Ask the LLM to match the user's theme colors, so generated scenes look
    consistent with the deterministic templates and the app."""
    if not palette:
        return ""
    return (
        "\n\n## Theme"
        f"\nUse `config.background_color = \"{palette['background']}\"` and prefer "
        f"these colors: primary curves `{palette['curve']}`, highlights "
        f"`{palette['accent']}`, secondary `{palette['secondary']}`, text "
        f"`{palette['text']}`. Pass them as hex strings to `color=`."
    )


def _rename_scene_class(code: str, class_name: str) -> str:
    """Rename the scene's class to ``class_name`` while preserving its base.

    Matches ``class <Name>(<AnyBase>)`` for any base class. When several classes
    are present the one whose base mentions ``Scene`` is preferred (that is the
    actual Manim scene); otherwise the first class definition is renamed.
    """
    pattern = re.compile(r"class\s+(\w+)\s*\(([^)]*)\)")
    matches = list(pattern.finditer(code))
    if not matches:
        return code

    target = next((m for m in matches if "Scene" in m.group(2)), matches[0])
    base = target.group(2)
    start, end = target.span()
    return code[:start] + f"class {class_name}({base})" + code[end:]


def _repair_addendum(feedback: str, previous_code: str | None) -> str:
    """Build the repair instruction appended to the user prompt on a retry."""
    parts = [
        "\n\n## Repair Request",
        "Your previous scene failed. Fix it and return the COMPLETE corrected "
        "scene (full file, not a diff). The exact failure was:",
        f"```\n{feedback.strip()}\n```",
    ]
    if previous_code:
        parts.append("Your previous (broken) scene was:")
        parts.append(f"```python\n{previous_code.strip()}\n```")
    return "\n".join(parts)

        # Ensure the class name matches — cover Scene and the camera/3D
        # subclasses the prompt now allows (MovingCameraScene, ThreeDScene).
        if f"class {class_name}" not in code:
            code = re.sub(
                r"class \w+\((\w*Scene)\)",
                rf"class {class_name}(\1)",
                code,
                count=1,
            )

        # Ensure import
        if "from manim import" not in code and "import manim" not in code:
            code = "from manim import *\nimport numpy as np\n\n" + code

        # Validate: without a scene class + construct(), the file would compile
        # but render nothing (e.g. reasoning ate the whole token budget and the
        # reply was think-block only). Raising here routes to the fallback scene.
        if f"class {class_name}" not in code or "def construct" not in code:
            raise ValueError(
                "LLM reply contained no usable scene class "
                f"(got {len(code)} chars after stripping)."
            )

        return code

    def _fallback_scene(self, class_name: str, solver: SolverResult) -> str:
        """Deterministic domain-aware fallback (see services/scene_templates).

        Picks a visualization matching the problem's domain — pendulum, orbit,
        wave, or the classic damped oscillator — instead of one generic plot,
        so even the keyless/failed-LLM experience stays about the user's physics.
        """
        from aetherlab.services.scene_templates import (
            build_scene,
            detect_domain,
            load_scene_palette,
        )

        domain = detect_domain(solver.keywords, solver.variables)
        palette = load_scene_palette(self.settings.data_dir)
        title = solver.summary[:70] if solver.summary else "Physics Simulation"
        return build_scene(
            class_name=class_name,
            domain=domain,
            title=title,
            summary=solver.summary[:120],
            steps=solver.derivation_steps[:4],
            variables=solver.variables,
            palette=palette,
        )
