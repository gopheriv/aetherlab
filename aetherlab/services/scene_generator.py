"""LLM-driven dynamic Manim scene code generation."""

from __future__ import annotations

import ast
import logging
import re
import textwrap
from pathlib import Path

from aetherlab.core.models import ProblemRequest, RagResult, SolverResult
from aetherlab.core.settings import AppSettings
from aetherlab.services.model_policy import (
    codegen_request_kwargs,
    request_temperature,
    settings_pathway,
)

log = logging.getLogger(__name__)

SCENE_GENERATION_SYSTEM_PROMPT = """You are the AetherLab Cinematic Scene Architect — a physicist who directs like a
motion designer and stages like a filmmaker. You write ONE self-contained Manim
Community scene that turns an analytical result into the requested duration of
science cinema: something a physics student would screenshot, replay, and send
to a friend. Correctness is the floor. Wonder is the target.

════════════════════════════════════════════════════════════════════════
§0 · HARD CONSTRAINTS  (break one and the render dies — obey all)
════════════════════════════════════════════════════════════════════════
0.1  Output ONLY valid Python. No markdown fences, no prose, no leading comments.
0.2  `from manim import *` (Manim Community). Never manimlib. `import numpy as np`
     if used. Use ONLY real Manim Community mobjects, animations, rate functions,
     and color constants — invent nothing. Allowed global colors are: BLACK,
     WHITE, BLUE/GREEN/RED/YELLOW/TEAL/PURPLE/MAROON/GOLD (and their _A.._E
     variants), ORANGE, PINK, LIGHT_PINK, GRAY/GREY variants, DARK_BLUE,
     DARK_BROWN, LIGHT_BROWN, PURE_RED/GREEN/BLUE/CYAN/MAGENTA/YELLOW, and
     LOGO_* colors. `BROWN`, `CYAN`, `MAGENTA`, and `GREEN_SCREEN` are NOT
     global Manim constants; use DARK_BROWN, PURE_CYAN, PURE_MAGENTA, or GREEN.
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
     always_redraw rebuilds at the screen centre every frame: position the
     number inside the lambda (`.next_to(label, RIGHT)`).
0.7  Match the requested total duration (provided in the user brief) within
     ±20%. EVERY act must contain visible physical motion, not only
     FadeIn/Write/Create reveals. Use .animate, Transform/MoveAlongPath, or an
     updater. Never end frozen: the last 2–3 s is a living idle loop via
     ValueTracker + always_redraw or an updater; the final three sampled frames
     must be visibly different.
0.8  Honor EVERY requested on-screen object, label, comparison, and physical
     relationship from the user's prompt. Before output, audit the prompt noun
     by noun and confirm each requested element is created and shown in code.
0.9  NEVER construct MathTex, Tex, or SingleStringMathTex inside always_redraw
     or an updater; those callbacks run every frame and can compile LaTeX
     hundreds of times. Create formulas once. For changing numbers, create one
     DecimalNumber and update it with set_value().

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

Then structure FIVE ACTS with clear transitions so the viewer feels the turn:

  ACT I — HOOK: Open on a striking physical detail or question.
  ACT II — ESTABLISH: Name the system, show its initial state, and introduce
    the governing law.
  ACT III — EVOLVE: Let the dynamics play in real time. Track one important
    quantity with a synchronized live readout or a small supporting panel.
  ACT IV — REVEAL: Deliver the insight in one annotated hero frame.
  ACT V — RECAP: Restate the key relationship and let the living idle loop carry
    the final seconds. Clear unrelated objects between acts; keep at most three
    focal elements visible at once.

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
  Never use ManimGL-only ShowCreation, TextMobject, TexMobject, GraphScene,
  ThreeDVMobject, or class-level CONFIG.
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
  • LABELS: keep on-screen copy to short labels, symbols, and equation fragments.
    Spoken narration carries full sentences; do not burn sentence captions into
    the scene.

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

STORYBOARD_SYSTEM_PROMPT = """You are the AetherLab creative director. Design — do NOT code — a detailed
science-cinema treatment for the physics problem you are given. Think like a
filmmaker: concrete staging, five acts, one unforgettable hero frame.

Return STRICT JSON only (no markdown, no commentary) with exactly these keys:
{
  "concept": "one-sentence creative concept — the WORLD this equation lives in",
  "staging": "the concrete physical protagonist and its stage (objects, layout)",
  "palette": {"primary": "<manim color name>", "secondary": "<manim color name>",
               "accent": "<manim color name>"},
  "acts": [
    {"name": "HOOK", "duration_s": <number>, "beats": [
      {"detail": "one visible change", "duration_s": <number>,
       "kind": "demo | prediction | motion | comparison | equation | conclusion",
       "narration_cue": "short matching phrase", "anchor_cell": "C3",
       "target_object": "the focal Manim object", "target_equation": "LaTeX or empty"}
    ]},
    {"name": "ESTABLISH", "duration_s": <number>,
     "beats": [{"detail": "...", "duration_s": <number>,
                "narration_cue": "...", "anchor_cell": "D3",
                "target_object": "...", "target_equation": "..."}]},
    {"name": "EVOLVE", "duration_s": <number>, "beats": [...]},
    {"name": "REVEAL", "duration_s": <number>, "beats": [...]},
    {"name": "RECAP", "duration_s": <number>, "beats": [...]}
  ],
  "hero_frame": "the single climactic composition the whole scene builds toward",
  "idle_loop": "the subtle living animation for the final ~2 seconds",
  "narration": ["one short spoken line per act, matching its beats"]
}

Rules: the user brief gives the total duration target; allocate act durations
that sum to it within 5%. Give every act 1-2 implementable beats; each beat is
one visual detail, not a list of simultaneous objects. For a 30-second scene,
use 6-8 beats total (never more than 8) so each timed detail has room to read
and the Cloud render stays within budget. For every beat provide
its duration_s, one short narration_cue, one anchor_cell from a 6-by-6 grid,
the focal target_object, and target_equation when that beat shows an equation
(A1-F6, columns left-to-right, rows top-to-bottom). Beat durations must sum to
their act duration. Give text-heavy details more time than a simple motion beat.
Give every beat a pedagogical kind from demo | prediction | motion | comparison
| equation | conclusion so the scene arcs demo -> prediction -> motion/comparison
-> equation transform -> visual conclusion: at least one motion beat where the
physics visibly evolves, at least one equation or conclusion beat where the
governing law lands, and at least three distinct kinds overall. Structure every
beat as entrance -> readable hold -> exit/transform (never leave a completed
detail on screen when the next unrelated beat starts).
Keep each narration cue short enough to speak naturally inside its beat at about
2 words per second; if a cue is too long, shorten it instead of rushing the voice.
Combine only related animations within a beat so the implementation can batch
them with LaggedStart or AnimationGroup. Prefer a real-world referent over a bare graph. When using a
graph, label axes and units. Include a live numerical readout for a changing
quantity, a concise annotation on the hero frame, and a one-beat recap of the
key equation or physical meaning. Keep at most three focal elements visible at
once and specify a transition that clears unrelated content between acts. Give
each detail a clear entrance, enough time to read, and an exit or transform
before the next unrelated detail. Keep plots to at most two data series. Use
stock Manim Community mobjects. The variables you are given become on-screen
live numbers — work at least one into the staging."""


# UNT exam mode: fixed five-act weights (seconds at the 278 s reference lesson;
# schedule_storyboard_timeline scales them to any duration target).
UNT_ACT_WEIGHTS: dict[str, float] = {
    "HOOK": 8.0,
    "THEORY": 60.0,
    "WORKED": 90.0,
    "OFFICIAL_TASK": 90.0,
    "RECAP": 30.0,
}

UNT_STORYBOARD_SYSTEM_PROMPT = """You are the AetherLab UNT exam director. Design — do NOT code — a detailed
exam-paced treatment for the physics problem you are given. Think like a
KZ UNT coach: exam practice structure, units on everything, one clear answer.
Treat the supplied problem as unverified practice. Do not invent official
provenance, question numbers, pages, numeric conditions, results or answer keys.
OFFICIAL_TASK is a legacy internal act name; it does not establish official
status. Visible labels must say practice. Preserve the supplied solution and
show an answer letter only when supplied with the task's choices and key.

Return STRICT JSON only (no markdown, no commentary) with exactly these keys:
{
  "concept": "one-sentence exam concept — the task type and the law it tests",
  "staging": "the apparatus/graph stage (objects, layout, safe areas)",
  "palette": {"primary": "<manim color name>", "secondary": "<manim color name>",
               "accent": "<manim color name>"},
  "acts": [
    {"name": "HOOK", "duration_s": 8, "beats": [
      {"detail": "one visible change", "duration_s": <number>,
       "kind": "demo | prediction | motion | comparison | equation | conclusion",
       "narration_cue": "short matching phrase", "anchor_cell": "C3",
       "target_object": "the focal Manim object", "target_equation": "LaTeX or empty"}
    ]},
    {"name": "THEORY", "duration_s": 60, "beats": [...]},
    {"name": "WORKED", "duration_s": 90, "beats": [...]},
    {"name": "OFFICIAL_TASK", "duration_s": 90, "beats": [...]},
    {"name": "RECAP", "duration_s": 30, "beats": [...]}
  ],
  "hero_frame": "the single climactic composition: solved supplied task + numerical result",
  "idle_loop": "the subtle living animation for the final ~2 seconds",
  "narration": ["one short spoken line per act, matching its beats"]
}

Rules: the user brief gives the total duration target; allocate act durations
that sum to it within 5%, starting from the HOOK 8 / THEORY 60 / WORKED 90 /
OFFICIAL_TASK 90 / RECAP 30 weights scaled to the target. Give every act 1-3
implementable beats; each beat is one visual detail, not a list of simultaneous
objects. For every beat provide its duration_s, one short narration_cue, one
anchor_cell from a 6-by-6 grid, the focal target_object, and target_equation
when that beat shows an equation (A1-F6, columns left-to-right, rows
top-to-bottom). Beat durations must sum to their act duration. Give text-heavy
details more time than a simple motion beat.
WORKED and OFFICIAL_TASK acts must follow the exam blocks Given (Berildi/Dano/
Given) -> Find -> Solution -> Answer + units. Show an answer letter only when supplied
with the task's choices and key. Put units on
every quantity, label every graph axis with units (v, m/s; t, s), shade
area-under-graph segments only where they carry the actual supplied solution,
and show the supplied result at the hero frame and again in RECAP. Include a live
numerical readout for a changing quantity. Give every beat a pedagogical kind
from demo | prediction | motion | comparison | equation | conclusion: at least
one motion beat where the physics visibly evolves, at least one equation beat
where the governing law lands, and at least one conclusion beat with the boxed
answer. Structure every beat as entrance -> readable hold -> exit/transform
(never leave a completed detail on screen when the next unrelated beat starts).
Keep each narration cue short enough to speak naturally inside its beat at about
2 words per second. Keep at most three focal elements visible at once and
specify a transition that clears unrelated content between acts. Keep plots to
at most two data series. Use stock Manim Community mobjects. The variables you
are given become on-screen live numbers — work at least one into the staging.
Reserve the bottom subtitle zone (no hero text there) and keep all mobjects
inside the frame with portrait-safe .to_edge()/.arrange() composition."""

UNT_CODEGEN_APPENDIX = """
## UNT exam-mode appendix (overrides tolerances above)
UNT OVERRIDE: match the requested total duration within ±10% (not ±20%).
Every act must visibly MOVE via .animate, Transform/MoveAlongPath, or an
updater; end with a living idle loop via ValueTracker + always_redraw so the
final three sampled frames differ, never a frozen last frame.
Required elements per task chapter: Given → Find → Solution → Answer blocks,
units on every quantity, graph axis labels with units, shaded area segments
where they carry the supplied solution, and its numerical result in recap.
Treat generated material as unverified practice. Do not invent official status,
citations, numerical conditions, results or keys. Show an answer letter only when supplied
with the task's choices and key; otherwise show the numerical result with units.
Typography minimums at 1080p: titles 36-44, formulas 32+, axis labels
24+, answer letter 40+. Short labels only; narration carries sentences.
Safe areas: reserve the bottom ~180 px for subtitles/player in landscape
(no hero text there); in portrait reserve bottom ~300 px + top ~200 px for
platform chrome. Portrait layout via .to_edge(), .arrange(), and
scale_to_fit_width() only; never write config.frame_width/pixel_width.
Staging: max 3 focal objects; ReplacementTransform/TransformMatchingTex for
idea continuity; fast reveals 0.6-1.0 s, climax 2.5-4 s."""


SCENE_CODEGEN_SYSTEM_PROMPT = """You are the AetherLab Manim implementation engineer. You are given a locked
storyboard designed by the creative director. Implement it EXACTLY — every act,
every beat, the hero frame, and the idle loop — as ONE Manim Community scene.

HARD CONSTRAINTS (violating any ruins the render):
1. Output ONLY valid Python — no markdown fences, no prose.
2. `from manim import *` (Manim Community). Never manimlib. `import numpy as np`
   if used. Use ONLY real Manim Community mobjects, animations, rate functions,
   and real global color constants — invent nothing. Use WHITE, BLACK, BLUE,
   GREEN, RED, YELLOW, TEAL, PURPLE, MAROON, GOLD, ORANGE, PINK, GRAY/GREY
   (including _A.._E variants), DARK_BLUE/DARK_BROWN/LIGHT_BROWN, and
   PURE_CYAN/PURE_MAGENTA/PURE_YELLOW. Never use BROWN or GREEN_SCREEN.
   Import only the documented ManimCE and NumPy modules; do not import `colorsys`
   or use `getattr`, `setattr`, `hasattr`, `eval`, `exec`, dunder attributes,
   `__class__`, reflection, or dynamic attribute lookup.
   Never use ManimGL-only `ShowCreation`, `TextMobject`, `TexMobject`,
   `GraphScene`, `ThreeDVMobject`, or class-level `CONFIG`; use ManimCE names
   such as `Create`, `Text`, `MathTex`, and `ThreeDScene`.
3. Exactly one scene class named `{class_name}` inheriting `Scene` (or
   `MovingCameraScene` if the storyboard demands camera moves), with
   `def construct(self)`.
4. Must pass `compile(code, '<generated>', 'exec')`. Do not touch config.*.
5. Keep everything inside the frame: guard grouped layouts with
   `grp.scale_to_fit_width(config.frame_width - 1)` and `.move_to(ORIGIN)`,
   or lay out with `.arrange()`/`.next_to()`/`.to_edge()`.
6. Surface the given variables as ValueTracker-driven DecimalNumbers on screen.
   always_redraw rebuilds at the screen centre every frame, so position the
   number INSIDE the lambda (`.next_to(label, RIGHT)`), or give a placed
   DecimalNumber an updater `lambda m: m.set_value(tracker.get_value())`.
7. Match each act's duration_s with your run_time/wait budget (±20%).
8. Every act must visibly MOVE via .animate, Transform/MoveAlongPath, or an
   updater. End with the storyboard's idle loop via ValueTracker + always_redraw;
   the final three sampled frames must differ, never a frozen last frame.
9. Use the storyboard's palette consistently; the accent color appears ONLY at
   the hero frame.
10. Implement every object/label/comparison requested by the original problem;
    audit the request noun by noun before returning code.
11. Maintain scene hygiene: before a new act introduces unrelated content, fade
    out or transform the previous act's group; never stack unrelated mobjects at
    the same `.move_to(...)` coordinate; use `VGroup(...).arrange(...)` for
    multiple labels/equations; avoid `.copy()` unless the original is transformed
    or removed nearby; prefer `set_color_by_tex()`/`get_part_by_tex()` over deep
    MathTex indexing like `eq[0][3]`; keep NumberPlane/Axes as subtle background
    scaffolding with low stroke opacity.
12. Never create MathTex/Tex/SingleStringMathTex inside always_redraw or an
    updater. Create formulas once; animate changing numeric readouts with one
    DecimalNumber whose updater calls set_value().
13. Render performance (cheaper code renders faster and fails less): plot curves
    with `axes.plot(func)` rather than a hand-rolled ParametricFunction/FunctionGraph
    when an Axes/NumberPlane exists; batch related animations with
    `LaggedStart(...)`/`AnimationGroup(...)` instead of many sequential `self.play`
    beats; and in `always_redraw`/updaters, update the existing mobject in place
    (`.become(...)`, shift points) rather than rebuilding a VGroup from a
    comprehension every frame.
14. Do not burn full-sentence narration captions into the animation. Use short
    labels, symbols, and equation fragments; the spoken narration carries the
    sentences.
15. Check the installed ManimCE signature before using a constructor or method.
    Do not guess keyword arguments; prefer documented defaults when unsure.
16. Follow `storyboard.timeline` as a timed edit list. Each event has exact
    start_s/end_s and duration_s. Implement events in chronological order; do
    not show its detail before start_s, and remove or transform it by end_s.
    Add a `# BEAT A1.B1 | 0.00-2.50 s` comment at every event boundary, using
    that event's exact start_s/end_s so timing is auditable.
    If no timeline is supplied, write an equivalent compact beat schedule first.
17. One beat shows one focal detail, at most one supporting object, and one
    short attached label. Never show more than two graph traces at once. Fade
    or morph a finished label before introducing an unrelated one; crossfades
    between unrelated beats may overlap for at most 0.3 seconds.
18. Use the supplied 6-by-6 anchor_cell for the focal composition. Keep all
    mobjects at least 0.45 scene units inside the frame edges, attach labels to
    their referents, and reserve separate space for axes and titles. Use labels
    of 3-6 words, Text(font_size=30) or larger, and do not shrink an individual
    label below 0.22 scene units high. Prefer one clear plot over dense grids,
    tiny ticks, or overlapping live readouts.
19. Inside each event, budget an entrance, a readable hold, and a clean exit.
   Keep physical motion synchronized with its narration_cue. Do not leave a
   completed detail on screen as the next unrelated detail starts.
20. For a 30-second cloud scene, use no more than 16 top-level self.play calls
   in the entire scene and no more than two live updaters. Target one play call
   per beat and never exceed two; combine simultaneous details with
   LaggedStart/AnimationGroup and use waits for readable holds. Preserve the
   full requested duration and every storyboard beat.
21. Never animate a mobject directly while its active updater also changes that
   mobject. Animate the controlling ValueTracker and let its updater update the
   display, or remove the updater before animating. Do not animate the same
   mobject twice in one self.play call. Fade in a DecimalNumber/Integer with an
   updater in a separate self.play call BEFORE animating the ValueTracker that
   changes it; changing its digit count during FadeIn can crash Manim family
   interpolation.
22. Honor each beat's pedagogical kind: demo stages the apparatus, prediction
   poses the question on screen, motion evolves the physics live, comparison
   juxtaposes two states side by side, equation morphs the governing law with
   TransformMatchingTex (never a static screenshot), conclusion lands one
   visual takeaway. Vary the choreography per kind with these concrete
   devices: coordinated highlight `self.play(Flash(focus), Circumscribe(focus))`
   for the hero moment, equation morph chains
   `self.play(TransformMatchingTex(eq_before, eq_after))` so algebra becomes
   itself, and — only on MovingCameraScene — one purposeful push
   `self.play(self.camera.frame.animate.scale(0.6).move_to(focus))` toward the
   climax. Dim scaffolding (stroke_opacity ~0.35), layer with set_z_index
   (axes behind, physics mid, labels on top), and always give a beat an
   entrance, a readable hold, and an exit/transform — completed content fades
   or morphs away before the next unrelated beat."""


TEMPORAL_LAYOUT_CONTRACT = """TIMED DETAIL + CLEAN FRAME CONTRACT
Treat storyboard.timeline as the edit schedule. Every event has start_s,
end_s, duration_s, kind (demo/prediction/motion/comparison/equation/conclusion),
narration_cue, subtitle_cue, target_object,
target_equation, and anchor_cell. Stage each kind distinctly (demo shows the
apparatus, motion evolves it live, equation morphs the law, conclusion lands
the takeaway) and vary the choreography: coordinated Flash+Circumscribe
highlights, TransformMatchingTex equation chains, one purposeful camera push.
Add one
`# BEAT A1.B1 | 0.00-2.50 s` marker per event using the exact window. Begin its
single focal detail inside its assigned window;
finish its entrance, readable hold, and exit/transform before the next
unrelated window starts. Crossfade overlap is limited to 0.3 seconds.

Composition: one focal detail, one supporting object, and one short attached
label per beat; at most two data traces and three focal elements visible.
Clear finished equations and callouts. Keep titles, axes, legends, and live
readouts in distinct reserved zones. Use anchor cells A1-F6 (columns
left-to-right, rows top-to-bottom), a 0.45-unit safe margin, and readable type
(Text font_size >=30; no individual label below 0.22 scene units). Replace a
previous state instead of accumulating curves or labels. The hero frame is
the only planned multi-element composition; arrange it as one balanced group,
then clear it for the recap.

Render budget: for a 30-second Cloud scene, use 6-8 timed beats total, at most
16 top-level self.play calls for the entire scene, and at most two live
updaters. Target one play call per beat; combine simultaneous details with
LaggedStart/AnimationGroup and use waits for holds. NEVER put axes.plot(...), ParametricFunction, or another full
curve construction inside always_redraw; that rebuilds hundreds of points on
every frame and can stall cloud rendering. Create static spectra once and use
Transform between temperature states. Keep no more than three live updater or
always_redraw objects total; animate a small marker directly instead of
replotting its curve. Never animate a mobject directly in self.play while its
active updater mutates that mobject; animate the controlling ValueTracker or
clear the updater first. Fade in a live DecimalNumber/Integer in its own play
before animating the ValueTracker that changes its digits. Keep each marker immediately before its corresponding
visual action, and use the scheduled duration for entrances, holds, and exits."""


SCENE_REVISE_SYSTEM_PROMPT = """You are the AetherLab scene reviser. A rendered Manim scene was reviewed by
a visual critic. Revise the COMPLETE scene to address every critique point
while preserving the storyboard's concept, acts, and hero frame.

Rules:
1. Output ONLY valid Python — no markdown fences, no commentary.
2. Keep the class named exactly `{class_name}` (inherits Scene, defines
   `def construct(self)`).
3. Address the critique concretely (spacing, legibility, pacing, palette,
   overlap, dead time) — do not simplify the scene into a bare plot.
4. Use only real Manim Community APIs and global colors. Never invent BROWN,
   GREEN_SCREEN, or other color names; use DARK_BROWN/GREEN or a hex string.
5. Preserve scene hygiene: no stale copied originals, no repeated unrelated
   move_to anchors without cleanup, no abrupt self.clear(), and no dominant bare
   grids.
6. Preserve visible physical motion in every act and a living ending whose last
   sampled frames differ; do not "fix" a critique by freezing or deleting a
   requested object.
7. Never rebuild MathTex/Tex/SingleStringMathTex in always_redraw or an updater;
   keep formulas static and use DecimalNumber.set_value() for live numbers.
8. Preserve each scheduled beat's start_s/end_s and leave a readable hold.
   Remove overlapping labels, stale curves, and completed details; keep at most
   three focal elements visible and retain the storyboard's anchor cells."""


SCENE_REPAIR_SYSTEM_PROMPT = """You are the AetherLab Manim repair engineer. A Manim Community scene you
wrote failed static validation or rendering. Fix the exact issue with the smallest safe edit.

Rules:
1. Output ONLY valid Python — no markdown fences, no commentary.
2. If given a function repair scope, return only that complete function with
   its original signature. Return the complete scene only when the scope says
   `whole scene` or a function-only repair cannot address the error.
3. Change as little as possible: fix the failing API usage (wrong kwarg,
   nonexistent method, bad constant) while preserving the visual design.
4. Use only real Manim Community APIs. If unsure a kwarg exists, drop it or
   use the closest documented equivalent.
5. If the failure involved clutter/overlap, fix with FadeOut/Transform,
   VGroup.arrange(), or different zones rather than piling new objects onto the
   same anchor.
6. Keep every requested object and visible-motion beat; never repair a crash by
   reducing the scene to static text/axes.
7. Never rebuild MathTex/Tex/SingleStringMathTex in always_redraw or an updater;
   keep formulas static and use DecimalNumber.set_value() for live numbers.
8. Preserve the storyboard beat markers and their time windows. When the repair
   request supplies the canonical marker list, replace all marker comments with
   exactly that list, once each and in the listed order. For an OOM,
   simplify each beat's mobject count and sampling density while keeping its
   duration and core physics; do not compress several details into one crowded
   frame.
9. If a ValueError reports unequal zip lengths inside Animation.interpolate_mobject,
   check for a DecimalNumber/Integer whose updater changes its digit count while
   that readout is fading/writing/creating and its controlling ValueTracker is
   animated in the same self.play. Fade in the readout in an earlier play, then
   animate the tracker. Also check for directly animating an updater-controlled
   mobject. Do not drop the visual beat or duration.
"""

SCENE_REPAIR_USER_TEMPLATE = """## Validation or render issue
{error}

## Repair scope: {scope_label}
Change only the scoped function when a function is named. Keep its signature.

## Installed Manim Community API references
{api_docs}

## Code in the failing scope
{scope_code}

## Complete original scene (context and exact identifiers)
{code}

Return the scoped Python repair now."""


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


def _merge_repaired_function(original: str, response: str, function_name: str) -> str | None:
    """Merge a function-only repair into the original source by AST line span."""
    content = re.sub(r"<think>.*?</think>", "", response or "", flags=re.DOTALL).strip()
    fenced = re.search(r"```(?:python)?\s*\n(.*?)```", content, re.DOTALL)
    if fenced:
        content = fenced.group(1).strip()
    if re.search(r"^\s*class\s+\w+", content, flags=re.MULTILINE):
        return None  # Full-scene response: let the normal extractor handle it.
    try:
        replacement_tree = ast.parse(content)
        original_tree = ast.parse(original)
    except SyntaxError:
        return None
    replacements = [
        node for node in ast.walk(replacement_tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == function_name
    ]
    targets = [
        node for node in ast.walk(original_tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == function_name
    ]
    if not replacements or not targets:
        return None
    replacement = min(replacements, key=lambda node: node.lineno)
    target = min(targets, key=lambda node: node.lineno)
    new_source = ast.get_source_segment(content, replacement)
    if not new_source:
        return None
    indent = " " * int(getattr(target, "col_offset", 0) or 0)
    new_lines = textwrap.dedent(new_source).splitlines(keepends=True)
    if not new_lines:
        return None
    if not new_lines[-1].endswith(("\n", "\r")):
        new_lines[-1] += "\n"
    replacement_lines = [
        (indent + line if line.strip() else line)
        for line in new_lines
    ]
    original_lines = original.splitlines(keepends=True)
    original_lines[target.lineno - 1 : (target.end_lineno or target.lineno)] = replacement_lines
    merged = "".join(original_lines)
    try:
        ast.parse(merged)
    except SyntaxError:
        return None
    return merged


_TIMELINE_ANCHORS = (
    "C3", "D3", "C4", "D4", "B3", "E3", "B4", "E4", "C2", "D2", "C5", "D5",
)


def schedule_storyboard_timeline(storyboard: dict, duration_target_s: float) -> dict:
    """Attach deterministic absolute timing to each visual beat.

    LLM-provided beat durations act as weights within their act. Older
    storyboards with string beats remain supported and divide each act evenly.
    Act and beat intervals are scaled to the requested total, so the codegen
    pass receives a complete, non-overlapping edit schedule.
    """
    timed = dict(storyboard)
    raw_acts = storyboard.get("acts")
    if not isinstance(raw_acts, list) or not raw_acts:
        return timed
    try:
        target = max(0.1, float(duration_target_s))
    except (TypeError, ValueError):
        target = 30.0

    valid = [(index, act) for index, act in enumerate(raw_acts) if isinstance(act, dict)]
    if not valid:
        return timed

    def positive_weight(value: object) -> float:
        try:
            weight = float(value)
        except (TypeError, ValueError):
            return 1.0
        return weight if 0.05 <= weight <= target * 10 else 1.0

    act_weights = [positive_weight(act.get("duration_s")) for _, act in valid]
    act_weight_total = sum(act_weights)
    narration = storyboard.get("narration")
    revised_acts = list(raw_acts)
    timeline: list[dict] = []
    elapsed = 0.0

    for valid_index, ((act_index, raw_act), act_weight) in enumerate(zip(valid, act_weights)):
        act = dict(raw_act)
        act_duration = target * act_weight / act_weight_total
        act_end = target if valid_index == len(valid) - 1 else elapsed + act_duration
        act["duration_s"] = round(act_end - elapsed, 3)
        act["start_s"] = round(elapsed, 3)
        act["end_s"] = round(act_end, 3)
        revised_acts[act_index] = act

        raw_beats = act.get("beats")
        if isinstance(raw_beats, (str, dict)):
            raw_beats = [raw_beats]
        if not isinstance(raw_beats, list) or not raw_beats:
            raw_beats = [{"detail": f"{act.get('name', 'Act')} transition"}]

        act_narration = (
            str(narration[act_index])
            if isinstance(narration, list) and act_index < len(narration)
            else ""
        )
        own_cues = [
            str(beat.get("narration_cue") or beat.get("cue") or "").strip()
            if isinstance(beat, dict) else ""
            for beat in raw_beats
        ]
        # The act's narration line is spoken ONCE, on the act's first beat, and
        # only when no beat carries its own cue. Copying it onto every beat made
        # the timed voiceover and subtitles repeat the same sentence per beat.
        if not any(own_cues) and act_narration.strip():
            own_cues[0] = act_narration.strip()
        beat_cues = own_cues
        beat_weights = []
        for beat, cue in zip(raw_beats, beat_cues, strict=True):
            base = positive_weight(beat.get("duration_s")) if isinstance(beat, dict) else 1.0
            # Longer cues receive proportionally more room. Explicit storyboard
            # weights still control text-heavy beats when they ask for even more.
            speaking_room = len(cue.split()) / 2.0
            beat_weights.append(max(base, speaking_room, 0.05))
        beat_weight_total = sum(beat_weights)
        beat_elapsed = elapsed

        for beat_index, (beat, cue, beat_weight) in enumerate(zip(raw_beats, beat_cues, beat_weights, strict=True)):
            if isinstance(beat, dict):
                detail = str(
                    beat.get("detail") or beat.get("visual") or beat.get("text") or "One visual detail"
                ).strip()
                anchor = str(beat.get("anchor_cell") or "").strip().upper()
            else:
                detail = str(beat).strip() or "One visual detail"
                anchor = ""
            if len(anchor) != 2 or anchor[0] not in "ABCDEF" or anchor[1] not in "123456":
                anchor = _TIMELINE_ANCHORS[(act_index * 3 + beat_index) % len(_TIMELINE_ANCHORS)]

            beat_duration = (act_end - elapsed) * beat_weight / beat_weight_total
            beat_end = act_end if beat_index == len(raw_beats) - 1 else beat_elapsed + beat_duration
            duration = max(0.0, beat_end - beat_elapsed)
            enter_s = min(0.35, duration * 0.2)
            exit_s = min(0.30, duration * 0.2)
            narration_target_s = len(cue.split()) / 2.0
            narration_overflow_s = max(0.0, narration_target_s - duration)
            timeline.append({
                "id": f"A{act_index + 1}.B{beat_index + 1}",
                "act": str(act.get("name") or f"ACT {act_index + 1}"),
                "detail": detail,
                "start_s": round(beat_elapsed, 3),
                "end_s": round(beat_end, 3),
                "duration_s": round(duration, 3),
                "enter_s": round(enter_s, 3),
                "hold_s": round(max(0.0, duration - enter_s - exit_s), 3),
                "exit_s": round(exit_s, 3),
                "narration_cue": cue,
                "subtitle_cue": cue,
                "narration_words": len(cue.split()),
                "narration_target_s": round(narration_target_s, 3),
                "narration_fits": narration_overflow_s <= 0.25,
                "narration_overflow_s": round(narration_overflow_s, 3),
                "anchor_cell": anchor,
                "target_object": str(
                    beat.get("target_object") or beat.get("object") or detail
                ).strip() if isinstance(beat, dict) else detail,
                "target_equation": str(
                    beat.get("target_equation") or beat.get("equation") or ""
                ).strip() if isinstance(beat, dict) else "",
            })
            beat_elapsed = beat_end
        elapsed = act_end

    timed["acts"] = revised_acts
    timed["timeline"] = timeline
    timed["timeline_duration_s"] = round(target, 3)
    try:
        from aetherlab.services.scene_specification import ensure_beat_arc

        ensure_beat_arc(timed)
    except Exception:  # noqa: BLE001 - kind tagging is advisory, never fatal
        pass
    return timed


def build_unt_storyboard(duration_target_s: float, concept: str = "UNT exam task") -> dict:
    """Deterministic UNT storyboard: five exam acts scaled to the target.

    Uses :data:`UNT_ACT_WEIGHTS` as act weights; :func:`schedule_storyboard_timeline`
    scales them to any duration, so the same builder serves a 30 s task chapter
    and the 278 s reference lesson. Eight beats keep a short task readable;
    the LLM directing pass adds more beats for long-form targets.
    """
    board = {
        "concept": str(concept or "UNT exam task"),
        "source_status": "practice_scaffold_unverified",
        "staging": "Practice stage: Given/Find panel left, relevant physical diagram centre, supplied answer right; subtitle zone clear.",
        "palette": {"primary": "BLUE", "secondary": "TEAL", "accent": "YELLOW"},
        "acts": [
            {"name": "HOOK", "duration_s": UNT_ACT_WEIGHTS["HOOK"], "beats": [
                {"detail": "Hook: task question with a live number", "duration_s": 8.0,
                 "kind": "demo", "narration_cue": "What must we find?",
                 "anchor_cell": "C3", "target_object": "question label",
                 "target_equation": ""},
            ]},
            {"name": "THEORY", "duration_s": UNT_ACT_WEIGHTS["THEORY"], "beats": [
                {"detail": "Governing law with units", "duration_s": 30.0,
                 "kind": "equation", "narration_cue": "Law with units.",
                 "anchor_cell": "D3", "target_object": "equation",
                 "target_equation": ""},
                {"detail": "Live readout evolves", "duration_s": 30.0,
                 "kind": "motion", "narration_cue": "Watch the quantity change.",
                 "anchor_cell": "C4", "target_object": "live readout",
                 "target_equation": ""},
            ]},
            {"name": "WORKED", "duration_s": UNT_ACT_WEIGHTS["WORKED"], "beats": [
                {"detail": "Given and Find blocks with units", "duration_s": 45.0,
                 "kind": "demo", "narration_cue": "Given and find.",
                 "anchor_cell": "D4", "target_object": "Given panel",
                 "target_equation": ""},
                {"detail": "Solution steps to boxed answer", "duration_s": 45.0,
                 "kind": "conclusion", "narration_cue": "Solution to answer.",
                 "anchor_cell": "B3", "target_object": "answer box",
                 "target_equation": ""},
            ]},
            {"name": "OFFICIAL_TASK", "duration_s": UNT_ACT_WEIGHTS["OFFICIAL_TASK"], "beats": [
                {"detail": "Practice task Given Find with source-derived visuals", "duration_s": 45.0,
                 "kind": "prediction", "narration_cue": "Supplied practice task setup.",
                 "anchor_cell": "E3", "target_object": "task graph",
                 "target_equation": ""},
                {"detail": "Show the supplied solution using an appropriate physical diagram", "duration_s": 45.0,
                 "kind": "motion", "narration_cue": "Use the supplied quantities and law.",
                 "anchor_cell": "B4", "target_object": "solution diagram",
                 "target_equation": ""},
            ]},
            {"name": "RECAP", "duration_s": UNT_ACT_WEIGHTS["RECAP"], "beats": [
                {"detail": "Supplied numerical result with units and a solving tactic", "duration_s": 30.0,
                 "kind": "conclusion", "narration_cue": "Review the supplied result and tactic.",
                 "anchor_cell": "E4", "target_object": "supplied answer",
                 "target_equation": ""},
            ]},
        ],
        "hero_frame": "Supplied solution diagram and boxed numerical result with units",
        "idle_loop": "Live supplied quantity changes subtly without changing the solution",
        "narration": [
            "Hook question.",
            "Theory with units.",
            "Worked example.",
            "Practice task.",
            "Recap and tactic.",
        ],
    }
    return schedule_storyboard_timeline(board, duration_target_s)


SPEECH_TAIL_S = 0.35     # breath after each line, inside its own beat
SILENT_BEAT_MIN_S = 0.8  # a beat without a line still needs time to read


def fit_timeline_to_speech(
    board: dict, speech_s: list[float], duration_target_s: float
) -> dict | None:
    """Voice-first timing: rebuild beat windows from measured speech.

    ``speech_s`` holds the synthesized length of each timeline beat's line, in
    timeline order (0.0 for a beat without one). Every beat gets at least its
    spoken length plus a breath; the remaining time goes to the beats the
    director made longer, so the total stays exactly the requested duration.
    Returns None when the lines need more time than the target allows; the
    caller can then try a uniformly faster voice.
    """
    timeline = board.get("timeline")
    if not isinstance(timeline, list) or not timeline or len(speech_s) != len(timeline):
        return None
    target = float(duration_target_s)
    base = [max(0.0, float(beat.get("duration_s", 0.0) or 0.0)) for beat in timeline]
    need = [
        (seconds + SPEECH_TAIL_S) if seconds > 0 else SILENT_BEAT_MIN_S
        for seconds in speech_s
    ]
    spare = target - sum(need)
    if spare < 0:
        return None
    weights = [max(0.0, b - n) for b, n in zip(base, need)]
    if sum(weights) <= 1e-9:
        weights = base if sum(base) > 1e-9 else [1.0] * len(need)
    weight_total = sum(weights)
    windows = [n + spare * w / weight_total for n, w in zip(need, weights)]

    fitted = dict(board)
    new_timeline: list[dict] = []
    cursor = 0.0
    for index, (beat, window, seconds) in enumerate(zip(timeline, windows, speech_s)):
        end = target if index == len(timeline) - 1 else cursor + window
        duration = max(0.0, end - cursor)
        enter_s = min(0.35, duration * 0.2)
        exit_s = min(0.30, duration * 0.2)
        item = dict(beat)
        item.update({
            "start_s": round(cursor, 3),
            "end_s": round(end, 3),
            "duration_s": round(duration, 3),
            "enter_s": round(enter_s, 3),
            "hold_s": round(max(0.0, duration - enter_s - exit_s), 3),
            "exit_s": round(exit_s, 3),
            "speech_s": round(seconds, 3),
            "narration_target_s": round(seconds, 3),
            "narration_fits": True,
            "narration_overflow_s": 0.0,
        })
        new_timeline.append(item)
        cursor = end
    # Act windows follow their beats (beat ids are A<act>.B<n>).
    acts = list(fitted.get("acts") or [])
    for act_index, act in enumerate(acts):
        if not isinstance(act, dict):
            continue
        members = [b for b in new_timeline if str(b.get("id", "")).startswith(f"A{act_index + 1}.")]
        if members:
            act = dict(act)
            act["start_s"] = members[0]["start_s"]
            act["end_s"] = members[-1]["end_s"]
            act["duration_s"] = round(members[-1]["end_s"] - members[0]["start_s"], 3)
            acts[act_index] = act
    fitted["acts"] = acts
    fitted["timeline"] = new_timeline
    fitted["timeline_duration_s"] = round(target, 3)
    fitted["timing_basis"] = "speech"
    return fitted


def is_speech_timed(board: dict | None) -> bool:
    """True when the beat windows came from measured narration (keep them as is)."""
    return isinstance(board, dict) and board.get("timing_basis") == "speech"


class SceneGenerator:
    """Generate dynamic Manim scene code via LLM."""

    def __init__(
        self, settings: AppSettings, *, minimax_thinking: bool | None = None
    ) -> None:
        self.settings = settings
        # MiniMax "thinking" defaults OFF for every scene-writing call. With it
        # on, M3 spent its whole max_tokens budget reasoning and returned no
        # code in every recorded run (A/B 2026-09-24, first live failover, the
        # 2026-09-30 blackbody run: storyboard JSON cut off, codegen empty,
        # ~20 min to reach the template); thinking-off produced a rendered AI
        # scene. Pass minimax_thinking=True to opt back in (e.g. for an A/B).
        self._minimax_thinking = False if minimax_thinking is None else minimax_thinking
        # Lazy-create client on first use — import is inside _ensure_client
        self._client = None
        # Most recent storyboard (dict) — the critic evaluates renders against it.
        self._last_storyboard: dict | None = None
        self._last_scene_spec: dict | None = None
        # Why the last generate() returned the built-in template instead of an
        # AI scene ("" when the LLM succeeded). The caller surfaces this so a
        # fallback is never mistaken for a real answer.
        self._last_fallback_reason: str = ""

    async def generate(
        self,
        request: ProblemRequest,
        solver: SolverResult,
        rag: RagResult,
        class_name: str = "AetherLabScene",
        *,
        locked_storyboard: dict | None = None,
        unt_mode: bool | None = None,
    ) -> str:
        """Generate Manim scene code using the LLM.

        On any failure this returns the built-in domain template and records why
        in ``_last_fallback_reason`` — the caller must surface that, otherwise a
        template silently masquerades as an AI-authored answer.
        """
        from openai import APITimeoutError

        from aetherlab.services.model_policy import (
            effective_llm_timeout,
            settings_pathway,
            timeout_shortfall,
        )
        from aetherlab.services.parameters import apply_request_parameters

        solver = apply_request_parameters(request, solver)
        self._last_fallback_reason = ""
        self._last_storyboard = None
        self._last_scene_spec = None
        if not self.settings.openai_api_key:
            self._last_fallback_reason = (
                "No API key is configured, so the built-in domain template was used "
                "instead of an AI-generated scene."
            )
            return self._fallback_scene(class_name, solver)

        pathway = settings_pathway(self.settings)
        budget = effective_llm_timeout(self.settings)

        # One retry before falling back: models occasionally blow their output
        # budget or hiccup transiently, and a cinematic scene is worth a second
        # attempt. A *timeout* is the exception — the next attempt would spend
        # the same full budget to fail the same way, so that path stops early.
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                if locked_storyboard is None:
                    code = await self._generate_remote(
                        request, solver, rag, class_name, unt_mode=unt_mode
                    )
                else:
                    code = await self._generate_remote(
                        request, solver, rag, class_name,
                        locked_storyboard=locked_storyboard,
                        unt_mode=unt_mode,
                    )
                self._last_fallback_reason = ""
                return code
            except APITimeoutError as exc:
                last_exc = exc
                log.warning(
                    "LLM scene generation timed out after %.0fs on attempt %d "
                    "(model=%s, pathway=%s).",
                    budget, attempt + 1, self.settings.llm_model, pathway.name,
                )
                if not pathway.retry_on_timeout:
                    break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                log.warning(
                    "LLM scene generation attempt %d failed: %s", attempt + 1, exc
                )

        if isinstance(last_exc, APITimeoutError):
            advice = timeout_shortfall(self.settings) or (
                "Raise 'llm_timeout_seconds' in Settings or pick a faster model."
            )
            self._last_fallback_reason = (
                f"AI scene generation timed out after {budget:.0f}s on "
                f"{self.settings.llm_model}; showing the built-in domain template. "
                + advice
            )
        else:
            self._last_fallback_reason = (
                f"AI scene generation failed ({type(last_exc).__name__}: {last_exc}); "
                "showing the built-in domain template."
            )
        log.warning("Using fallback scene: %s", self._last_fallback_reason)
        self._last_storyboard = None
        self._last_scene_spec = None
        return self._fallback_scene(class_name, solver)

    def _ensure_client(self):
        from aetherlab.services.llm_client import make_client


        if self._client is None:
            self._client = make_client(self.settings, purpose="scene")
        return self._client

    async def fit_board_to_speech(self, board: dict, duration_target_s: float) -> dict:
        """With narration on, time every beat from its measured spoken line.

        Tries the configured voice rate first, then a uniformly faster voice
        (+10, +20 points) when the lines need more room than the target allows.
        One rate for the whole video sounds natural; per-line squeezing did not.
        Any failure (no TTS, offline) keeps the estimated windows unchanged.
        """
        settings = self.settings
        if not getattr(settings, "narration_enabled", False) or is_speech_timed(board):
            return board
        timeline = board.get("timeline")
        if not isinstance(timeline, list) or not timeline:
            return board
        from aetherlab.services import voiceover

        if not voiceover.narration_available():
            return board
        lines = [
            " ".join(str(beat.get("narration_cue") or "").split())
            if isinstance(beat, dict) else ""
            for beat in timeline
        ]
        if not any(lines):
            return board
        voice = str(getattr(settings, "tts_voice", "") or voiceover.DEFAULT_VOICE)
        base_rate = voiceover._parse_rate(getattr(settings, "tts_rate", "") or voiceover.DEFAULT_RATE)
        cache_dir = Path(settings.data_dir) / "narration" / "speech_cache"

        async def fit(
            candidate: dict, spoken: list[str], extras: tuple[int, ...]
        ) -> tuple[dict | None, list[float] | None]:
            first: list[float] | None = None
            for extra in extras:
                rate = voiceover._format_rate(base_rate + extra)
                speech = await voiceover.measure_speech(spoken, cache_dir, voice, rate)
                if speech is None:
                    return None, None
                first = first or speech
                fitted = fit_timeline_to_speech(candidate, speech, duration_target_s)
                if fitted is not None:
                    fitted["speech"] = {
                        "voice": voice, "rate": rate, "cache_dir": str(cache_dir),
                        "spoken_s": round(sum(speech), 2),
                    }
                    log.info(
                        "Voice-first timing: %d lines, %.1fs of speech in %.1fs at %s.",
                        sum(1 for line in spoken if line), sum(speech), duration_target_s, rate,
                    )
                    return fitted, speech
            return None, first

        # Natural speed first, then a slightly faster voice. Tighter wording
        # comes before the biggest speed-up: a live run fitted 50.5 s of
        # speech into 60 s only by speaking 28% fast, which sounds rushed.
        fitted, speech = await fit(board, lines, (0, 10))
        if fitted is not None:
            return fitted
        if speech is None:
            log.info("Voice-first timing unavailable (speech synthesis failed).")
            return board
        log.info(
            "Narration runs %.1fs at the base rate; too long for %.1fs at +10%%. "
            "Asking for tighter lines.", sum(speech), duration_target_s,
        )
        shorter = await self._condense_lines(board, lines, speech, duration_target_s)
        if shorter is not None:
            short_lines = [
                " ".join(str(beat.get("narration_cue") or "").split())
                for beat in shorter["timeline"]
            ]
            fitted, _ = await fit(shorter, short_lines, (0, 10, 20))
            if fitted is not None:
                return fitted
        fitted, _ = await fit(board, lines, (20,))
        if fitted is not None:
            return fitted
        log.info(
            "Voice-first timing declined: narration still needs more than %.1fs.",
            duration_target_s,
        )
        return board

    async def _condense_lines(
        self, board: dict, lines: list[str], speech: list[float], duration_target_s: float
    ) -> dict | None:
        """One rewrite that fits each beat's line into a measured word budget."""
        if not getattr(self.settings, "openai_api_key", None):
            return None
        spoken = [i for i, line in enumerate(lines) if line]
        silent = len(lines) - len(spoken)
        room = duration_target_s - SPEECH_TAIL_S * len(spoken) - SILENT_BEAT_MIN_S * silent
        total = sum(speech)
        if room <= 0 or total <= 0:
            return None
        scale = 0.9 * room / total            # 10% margin for a slightly slower read
        timeline = board["timeline"]
        budgets = {
            str(timeline[i].get("id")): max(3, int(len(lines[i].split()) * scale))
            for i in spoken
        }
        request = "\n".join(
            f'{timeline[i].get("id")} (max {budgets[str(timeline[i].get("id"))]} words): {lines[i]}'
            for i in spoken
        )
        system = (
            "You tighten physics narration so it fits its animation. Rewrite each line "
            "within its word limit, keeping its meaning, numbers and units, and the same "
            "order and tone. Reply with one JSON object mapping each beat id to its new "
            "line, nothing else."
        )
        try:
            from aetherlab.services.model_json import load_model_json

            response = await self._ensure_client().chat.completions.create(
                model=self.settings.llm_model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": request}],
                temperature=request_temperature(self.settings, 0.3),
                max_tokens=2048,
                **codegen_request_kwargs(self.settings, minimax_thinking=False),
            )
            rewritten = load_model_json(response.choices[0].message.content or "")
        except Exception as exc:  # noqa: BLE001 - tightening is best-effort
            log.info("Narration tightening failed (%s).", exc)
            return None
        if not isinstance(rewritten, dict):
            return None
        shorter = dict(board)
        new_timeline = []
        for beat in timeline:
            item = dict(beat)
            line = " ".join(str(rewritten.get(str(beat.get("id")), "")).split())
            budget = budgets.get(str(beat.get("id")))
            if line and budget and len(line.split()) <= budget + 2:
                item["narration_cue"] = item["subtitle_cue"] = line
            new_timeline.append(item)
        shorter["timeline"] = new_timeline
        return shorter

    async def storyboard(
        self,
        request: ProblemRequest,
        solver: SolverResult,
        rag: RagResult,
        *,
        temperature: float = 0.9,
        variation_seed: str = "",
        unt_mode: bool | None = None,
    ) -> dict | None:
        """Directing pass: a high-temperature creative treatment as strict JSON.

        Returns None on any failure — the caller falls back to the proven
        single-call cinematic generation, so storyboarding can only ever add
        quality, never subtract reliability.
        """
        from aetherlab.core.render_profile import resolve_unt_mode
        from aetherlab.services.model_json import load_model_json

        unt, _ = resolve_unt_mode(self.settings, unt_mode)
        vars_text = "\n".join(
            f"  {name} = {value}" for name, value in sorted(solver.variables.items())
        ) or "  (no variables)"
        duration_target_s = float(request.duration_target_s)
        beat_min = max(6, int(duration_target_s / 5.0 + 0.999))
        beat_max = max(beat_min, int(duration_target_s / 3.75 + 0.999))
        if unt:
            storyboard_system = UNT_STORYBOARD_SYSTEM_PROMPT
            if beat_max > 8:
                storyboard_system = storyboard_system.replace(
                    "Give every act 1-3\nimplementable beats; each beat is",
                    "Give every act enough implementable beats to meet the requested "
                    "global beat count; each beat is",
                )
        else:
            storyboard_system = STORYBOARD_SYSTEM_PROMPT
            if beat_max > 8:
                storyboard_system = storyboard_system.replace(
                    "Give every act 1-2 implementable beats; each beat is",
                    "Give every act enough implementable beats to meet the requested "
                    "global beat count; each beat is",
                ).replace(
                    "For a 30-second scene,\nuse 6-8 beats total (never more than 8) so each timed detail has room to read\n"
                    "and the Cloud render stays within budget.",
                    "For a long-form scene, follow the duration-scaled global beat count "
                    "in the user brief. Those beats will be rendered in separate bounded "
                    "scenes; do not compress the explanation to the 30-second beat count.",
                )
        user = (
            f"## Problem\n{request.prompt}\n\n"
            f"## Analytical summary\n{solver.summary}\n\n"
            f"## Variables (become live on-screen numbers)\n{vars_text}\n\n"
            f"## Total scene duration target\n{duration_target_s:g} seconds; "
            "make all act durations sum to this target and give every visual beat "
            f"its own duration, narration cue, and 6x6 anchor cell. Include {beat_min}–"
            f"{beat_max} meaningful visual beats (not cosmetic holds) so the full "
            "explanation has enough detail for this duration. Preserve all derivation "
            "steps, assumptions, and units from the analytical summary.\n\n"
            "Design the storyboard JSON now."
        )
        if unt:
            user += (
                "\n\nFollow the UNT exam acts HOOK/THEORY/WORKED/OFFICIAL_TASK/RECAP "
                "with Given → Find → Solution → Answer blocks, units on every "
                "quantity and labelled graph axes where relevant. Preserve the "
                "supplied result; show a letter only when supplied with task choices "
                "and key. Do not label generated practice as an official task."
            )
        if variation_seed:
            user += (
                "\n\n## Variation seed\n"
                f"{variation_seed}\n"
                "Use this seed only to choose a distinct composition/pacing approach; "
                "do not change the physics."
            )
        from aetherlab.services.model_policy import system_prompt_message

        last_error = ""
        for attempt in range(2):
            try:
                client = self._ensure_client()
                messages = [
                    system_prompt_message(self.settings, storyboard_system),
                    {"role": "user", "content": user},
                ]
                if last_error:
                    messages.append({
                        "role": "user",
                        "content": (
                            "The previous storyboard could not be used: "
                            f"{last_error}. Return one complete, syntactically valid "
                            "JSON object with an `acts` array. Do not omit beats or "
                            "return Markdown, commentary, or an empty response."
                        ),
                    })
                response = await client.chat.completions.create(
                    model=self.settings.llm_model,
                    messages=messages,
                    # Ideation runs hot; the codegen pass runs cold. This split is
                    # the whole point of storyboarding separately.
                    temperature=request_temperature(self.settings, temperature),
                    # A reasoning model whose thinking cannot be switched off spends
                    # part of this budget thinking; 4096 cut the JSON mid-string.
                    max_tokens=min(
                        32768,
                        max(
                            16384 if settings_pathway(self.settings).name in {
                                "reasoning", "kimi-reasoning",
                            } else 4096,
                            2048 + beat_max * 256,
                        ),
                    ),
                    **codegen_request_kwargs(
                        self.settings, minimax_thinking=self._minimax_thinking
                    ),
                )
                choices = getattr(response, "choices", None) or []
                if not choices:
                    raise ValueError("storyboard response contained no choices")
                choice = choices[0]
                message = getattr(choice, "message", None)
                content = str(getattr(message, "content", "") or "").strip()
                if not content:
                    raise ValueError(
                        "storyboard response was empty "
                        f"(finish_reason={getattr(choice, 'finish_reason', 'unknown')})"
                    )
                board = load_model_json(content)
                if not isinstance(board, dict) or not isinstance(board.get("acts"), list):
                    raise ValueError("storyboard JSON must contain an acts array")
                if unt:
                    # The directing response cannot certify its own provenance.
                    # This API receives no verified official-question record.
                    board["source_status"] = "practice_scaffold_unverified"
                if not board["acts"] or any(
                    not isinstance(act, dict)
                    or not isinstance(act.get("beats"), list)
                    or not act["beats"]
                    for act in board["acts"]
                ):
                    raise ValueError("storyboard acts must each contain a non-empty beats array")
                beat_count = sum(
                    len(act["beats"]) for act in board["acts"]
                )
                if duration_target_s > 45.0 and beat_count < beat_min:
                    raise ValueError(
                        f"storyboard returned {beat_count} beats; need at least {beat_min}"
                    )
                board = schedule_storyboard_timeline(board, duration_target_s)
                board = await self.fit_board_to_speech(board, duration_target_s)
                self._last_storyboard = board
                return board
            except ValueError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt == 0:
                    log.info("Storyboard JSON is unusable; retrying once (%s).", exc)
                    continue
                log.info("Storyboard pass failed (%s); using single-call generation.", exc)
                return None
            except Exception as exc:  # noqa: BLE001 — provider failures stay fail-soft
                log.info("Storyboard pass failed (%s); using single-call generation.", exc)
                return None
        return None

    async def _generate_remote(
        self,
        request: ProblemRequest,
        solver: SolverResult,
        rag: RagResult,
        class_name: str,
        locked_storyboard: dict | None = None,
        unt_mode: bool | None = None,
    ) -> str:
        from aetherlab.core.render_profile import resolve_unt_mode

        unt, _ = resolve_unt_mode(self.settings, unt_mode)
        duration_pct = "10%" if unt else "20%"
        self._ensure_client()

        steps_text = "\n".join(
            f"{i}. {step}" for i, step in enumerate(solver.derivation_steps, 1)
        ) or "No derivation steps available."

        vars_text = "\n".join(
            f"  {name} = {value}" for name, value in sorted(solver.variables.items())
        ) or "  (no variables)"
        duration_target_s = float(request.duration_target_s)

        rag_lines = []
        for hit in rag.hits[:3]:
            rag_lines.append(f"- {hit.source_name}: {hit.excerpt[:200]}")
        rag_context = "\n".join(rag_lines) if rag_lines else "No local references."

        # .replace (not .format): the prompt bodies contain literal braces
        # (color-palette sets like {BLUE_D, TEAL, ...}) that would break .format.
        from aetherlab.services.error_learner import (
            AestheticPitfallStore,
            preventive_pitfalls_block,
        )

        # The flywheel's "losers teach" channel: past low-scoring renders'
        # aesthetic problems are appended to the pitfalls block so this
        # generation actively avoids them. Fail-soft - no store, no effect.
        try:
            _aesthetic = AestheticPitfallStore(
                self.settings.data_dir / "aesthetic_pitfalls.json"
            )
        except Exception:  # noqa: BLE001 - learning is a bonus, never fatal
            _aesthetic = None

        # Two-call generation: hot directing pass → cold implementation pass.
        # Storyboard failure degrades to the proven single-call cinematic path.
        import json as _json

        board = (
            locked_storyboard
            if locked_storyboard is not None
            else await self.storyboard(request, solver, rag, unt_mode=unt)
        )
        if board is not None:
            if not is_speech_timed(board):
                # Speech-timed windows are final: re-weighting them by word
                # count would undo the measured fit.
                board = schedule_storyboard_timeline(board, duration_target_s)
            self._last_storyboard = board
            self._last_scene_spec = None
            try:
                from aetherlab.services.scene_specification import (
                    build_scene_spec,
                    validate_scene_spec,
                )

                candidate_spec = build_scene_spec(request, solver, rag, board)
                if validate_scene_spec(candidate_spec)["status"] == "passed":
                    self._last_scene_spec = candidate_spec
            except Exception as exc:  # noqa: BLE001 - generation can use the locked board
                log.info("Canonical scene spec unavailable for codegen (%s).", exc)
            system = SCENE_CODEGEN_SYSTEM_PROMPT.replace("{class_name}", class_name)
            system += (
                "\n\nWhen a canonical aetherlab.scene_spec.v1 is supplied, it is the "
                "single source of truth for equations, values, units, assumptions, "
                "citations, timed beats, narration, and visual bindings. Implement its "
                "timeline without changing those facts or their order."
            )
            if unt:
                system += UNT_CODEGEN_APPENDIX
            try:
                is_segmented = int(board.get("segment_count", 1) or 1) > 1
            except (TypeError, ValueError):
                is_segmented = False
            if is_segmented:
                system += (
                    "\n\n## Bounded segment contract\n"
                    "This scene is one independently rendered part of a longer "
                    "explanation. Implement only the supplied local beat schedule; "
                    "do not replay earlier beats, add a new opening scenario, or "
                    "replace the segment with a generic recap. Keep physical values, "
                    "equation notation, palette, and apparatus identity consistent "
                    "with the shared creative direction. Reconstruct persistent-looking "
                    "objects from the supplied entry state because Python mobjects do "
                    "not persist between segment processes. End at the supplied exit "
                    "state and preserve the full assigned segment duration."
                )
            system_additions = preventive_pitfalls_block(_aesthetic)
            spec_timeline = board.get("timeline", [])
            spec_context = ""
            if isinstance(self._last_scene_spec, dict):
                prompt_spec = dict(self._last_scene_spec)
                prompt_spec["evidence"] = [
                    {**ref, "source": ""}
                    for ref in prompt_spec.get("evidence", [])
                    if isinstance(ref, dict)
                ]
                try:
                    spec_context = _json.dumps(prompt_spec, indent=2, ensure_ascii=False)
                    spec_timeline = self._last_scene_spec.get("timeline", {}).get("beats", [])
                except (TypeError, ValueError):
                    self._last_scene_spec = None
            marker_lines = [
                f"# BEAT {event['id']} | {float(event['start_s']):.2f}-"
                f"{float(event['end_s']):.2f} s"
                for event in spec_timeline
                if isinstance(event, dict)
                and event.get("id")
                and event.get("start_s") is not None
                and event.get("end_s") is not None
            ]
            marker_contract = ""
            if marker_lines:
                marker_contract = (
                    "## Mandatory beat-boundary comments\n"
                    "Copy every line below verbatim into construct(), in this exact "
                    "order, immediately before that beat's visual action. These "
                    "comments are checked by the timing gate; do not omit or edit them.\n"
                    + "\n".join(marker_lines)
                    + "\n\n"
                )
            if spec_context:
                user = (
                    "## Canonical scene specification (aetherlab.scene_spec.v1)\n"
                    f"{spec_context}\n\n"
                    "Implement the physics, assumptions, timed visual beats, narration, "
                    "and visual bindings exactly as specified. The timetable is absolute; "
                    "use readable holds to make each action land inside its window.\n\n"
                    f"{marker_contract}"
                    f"## Reference excerpts\n{rag_context}\n\n"
                    f"## Total scene duration target\n{duration_target_s:g} seconds.\n\n"
                    "Output ONLY the Python code implementing the specification."
                )
            else:
                user = (
                    f"## Locked storyboard (implement exactly)\n"
                    f"{_json.dumps(board, indent=2)}\n\n"
                    f"## Problem\n{request.prompt}\n\n"
                    f"## Total scene duration target\n{duration_target_s:g} seconds. "
                    f"The complete animation should stay within {duration_pct} of this duration.\n\n"
                    f"{marker_contract}"
                    f"## Analytical summary\n{solver.summary}\n\n"
                    f"## Derivation steps\n{steps_text}\n\n"
                    f"## Variables (name = value)\n{vars_text}\n\n"
                    f"## Reference context\n{rag_context}\n\n"
                    "Output ONLY the Python code implementing the storyboard."
                )
            temperature = 0.15  # implementation runs cold — precision over flair
        else:
            system = SCENE_GENERATION_SYSTEM_PROMPT.replace("{class_name}", class_name)
            if unt:
                system += UNT_CODEGEN_APPENDIX
            system_additions = preventive_pitfalls_block(_aesthetic)
            try:
                from aetherlab.services.scene_specification import (
                    build_scene_spec,
                    validate_scene_spec,
                )

                candidate_spec = build_scene_spec(request, solver, rag)
                if validate_scene_spec(candidate_spec)["status"] == "passed":
                    self._last_scene_spec = candidate_spec
                    system += (
                        "\n\nThe canonical aetherlab.scene_spec.v1 supplied by the user "
                        "is the source of truth for equations, values, units, assumptions, "
                        "and reference provenance. Do not change those facts."
                    )
            except Exception as exc:  # noqa: BLE001 - retain the legacy generation path
                log.info("Canonical physics spec unavailable for codegen (%s).", exc)
            user = SCENE_GENERATION_USER_TEMPLATE.format(
                prompt=request.prompt,
                summary=solver.summary,
                steps=steps_text,
                variables=vars_text,
                rag_count=len(rag.hits),
                rag_context=rag_context,
            )
            if isinstance(self._last_scene_spec, dict):
                prompt_spec = dict(self._last_scene_spec)
                prompt_spec["evidence"] = [
                    {**ref, "source": ""}
                    for ref in prompt_spec.get("evidence", [])
                    if isinstance(ref, dict)
                ]
                try:
                    user += (
                        "\n\n## Canonical physics specification "
                        "(aetherlab.scene_spec.v1)\n"
                        + _json.dumps(prompt_spec, indent=2, ensure_ascii=False)
                    )
                except (TypeError, ValueError):
                    self._last_scene_spec = None
            user += (
                f"\n\n## Total scene duration target\n{duration_target_s:g} seconds. "
                f"The complete animation should stay within {duration_pct} of this duration."
            )
            temperature = 0.4

        # Few-shot: show the model ONE domain-matched, render-proven exemplar so
        # it imitates correct Manim-CE API usage and a real 3-beat arc instead of
        # improvising from prose alone. Appended to `system` (never truncated by
        # the budget trim below); fail-soft — no match yields no exemplar.
        from aetherlab.services.scene_exemplars import exemplar_block

        exemplar = exemplar_block(solver.keywords, solver.variables, data_dir=self.settings.data_dir)
        if exemplar:
            system_additions += "\n\n" + exemplar

        system += "\n\n" + TEMPORAL_LAYOUT_CONTRACT

        # Machines without a LaTeX toolchain can't render MathTex — force the
        # scene to unicode Text so it still renders everywhere. (Lazy import:
        # manim_runtime imports this module at top level.)
        from aetherlab.services.manim_runtime import detect_latex

        if not detect_latex():
            system_additions += (
                "\n\nIMPORTANT — NO LaTeX ON THIS MACHINE: never use MathTex, "
                "Tex, or SingleStringMathTex. Write every formula with "
                "Text(...) using unicode math (×, ·, ², ³, √, θ, ω, π, ½, ∂)."
            )

        # Keep the assembled context within the configured model window so an
        # oversized RAG excerpt can't overflow it (~3 chars/token, reserving the
        # output budget). At the default 250k window this never trips.
        char_budget = max(2000, (self.settings.llm_context_window - 32768) * 3)
        system_size = len(system) + len(system_additions)
        if system_size + len(user) > char_budget:
            user = user[: max(500, char_budget - system_size)]

        from aetherlab.services.model_policy import system_prompt_message

        messages = [system_prompt_message(self.settings, system)]
        if system_additions.strip():
            messages.append({"role": "system", "content": system_additions})
        messages.append({"role": "user", "content": user})

        response = await self._client.chat.completions.create(
            model=self.settings.llm_model,
            messages=messages,
            temperature=request_temperature(self.settings, temperature),
            # Reasoning models (MiniMax-M3, QwQ) spend thousands of tokens on
            # <think> blocks, and the cinematic prompt yields 100+ line scenes —
            # leave generous room or the code gets cut off mid-statement.
            max_tokens=32768,
            **codegen_request_kwargs(
                self.settings, minimax_thinking=self._minimax_thinking
            ),
        )
        choice = response.choices[0]
        content = choice.message.content or ""
        truncated = choice.finish_reason == "length"

        # A reasoning model can spend its whole completion budget inside
        # <think> and still emit a complete scene afterwards, so hitting the
        # token cap is not by itself a failure. Try to extract first and only
        # give up when nothing usable came back; the caller's compile gate
        # still rejects code that really was cut mid-statement.
        try:
            code = self._extract_code(content, class_name)
        except ValueError as exc:
            if truncated:
                raise ValueError(
                    "LLM reply was truncated at the max_tokens limit before a "
                    "usable scene class was produced."
                ) from exc
            raise
        if truncated:
            log.warning(
                "Reply hit the max_tokens limit but a complete scene class was "
                "recovered (model=%s spent its budget reasoning).",
                self.settings.llm_model,
            )
        return code

    async def generate_from_storyboard(
        self,
        request: ProblemRequest,
        solver: SolverResult,
        rag: RagResult,
        class_name: str,
        storyboard: dict,
        unt_mode: bool | None = None,
    ) -> str:
        """Implement a pre-selected storyboard with the normal cold codegen pass."""
        return await self._generate_remote(
            request, solver, rag, class_name,
            locked_storyboard=storyboard, unt_mode=unt_mode,
        )

    async def repair(
        self, code: str, error: str, class_name: str, *, full_scene: bool = False
    ) -> str:
        """Repair only the failing function when the traceback identifies it.

        Installed signatures and the failing function are sent as targeted
        context. If the model returns a complete scene anyway, it is accepted
        through the normal code extractor.
        """
        client = self._ensure_client()
        from aetherlab.services.scene_validation import (
            manim_api_reference_context,
            repair_scope_for_error,
        )

        scope_label, scope_code, function_name = repair_scope_for_error(code, error)
        if full_scene:
            scope_label, scope_code, function_name = "whole scene", code, None
        api_docs = manim_api_reference_context(code, error)
        user = SCENE_REPAIR_USER_TEMPLATE.format(
            error=error[-12000:],
            scope_label=scope_label,
            api_docs=api_docs or "No conclusive installed signature was found.",
            scope_code=scope_code,
            code=code,
        )

        response = await client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": SCENE_REPAIR_SYSTEM_PROMPT.format(class_name=class_name),
                },
                {
                    "role": "user",
                    "content": user,
                },
            ],
            temperature=request_temperature(self.settings, 0.2),
            max_tokens=32768,
            **codegen_request_kwargs(self.settings, minimax_thinking=self._minimax_thinking),
        )
        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise ValueError("Repair reply was truncated at the max_tokens limit.")
        content = choice.message.content or ""
        from aetherlab.services.scene_validation import restore_beat_markers

        if function_name:
            merged = _merge_repaired_function(code, content, function_name)
            if merged:
                return restore_beat_markers(code, self._extract_code(merged, class_name))
        return restore_beat_markers(code, self._extract_code(content, class_name))

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
            temperature=request_temperature(self.settings, 0.3),
            max_tokens=32768,
            **codegen_request_kwargs(self.settings, minimax_thinking=self._minimax_thinking),
        )
        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise ValueError("Revise reply was truncated at the max_tokens limit.")
        from aetherlab.services.scene_validation import restore_beat_markers

        return restore_beat_markers(code, self._extract_code(choice.message.content or "", class_name))

    async def narrate(
        self,
        prompt: str,
        code: str,
        storyboard_script: str = "",
        target_seconds: float | None = None,
        beat_timing: str = "",
    ) -> str:
        """Derive a flowing voiceover script FROM the final scene code.

        Following the manim-bot decision, narration is derived from the code
        that actually renders (so it tracks the on-screen beats in order), seeded
        by the storyboard's per-beat lines when available. The audio is later fit
        to the video length, so we target a word budget proportional to duration.
        """
        code_ctx = code if len(code) <= 6000 else code[:4000] + "\n# … middle omitted …\n" + code[-2000:]
        length_rule = ""
        try:
            secs = float(target_seconds) if target_seconds else None
        except (TypeError, ValueError):
            secs = None
        if secs and secs > 0:
            lo, hi = int(secs * 1.4), int(secs * 2.0)
            length_rule = (
                f" The video is about {int(secs)}s, so write roughly {lo}-{hi} words "
                "(~1.5-2 words/sec) — narrate every beat with no long silences."
            )
        seed = (
            f"\n\nTimed visual beats in order:\n{beat_timing}\n\n"
            f"Beat cue lines (one short spoken sentence per line, same order):\n{storyboard_script}"
            if storyboard_script else ""
        )
        system = (
            "You are a physics narrator. Given the Manim scene code that produces "
            "an animation, write a single natural, flowing voiceover that narrates "
            "the visual events IN THE ORDER they appear on screen. Plain spoken "
            "prose only — no stage directions, no markdown, no lists, no LaTeX. "
            "When timed beat cues are supplied, keep one short sentence per beat "
            "in the same order, leave readable pauses between ideas, and keep each "
            "line brief enough for its window. Do not speak timestamps or beat IDs."
            + length_rule
        )
        user = f"## Problem\n{prompt}\n\n## Scene code\n```python\n{code_ctx}\n```{seed}\n\nWrite the voiceover now."
        client = self._ensure_client()
        response = await client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=request_temperature(self.settings, 0.5),
            max_tokens=1200,
            **codegen_request_kwargs(self.settings, minimax_thinking=self._minimax_thinking),
        )
        text = (response.choices[0].message.content or "").strip()
        # Strip any accidental markdown fences/headers a model may add.
        text = re.sub(r"```[a-z]*", "", text).replace("`", "").strip()
        return text

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

        from aetherlab.services.scene_validation import (
            repair_text_mode_math,
            repair_unknown_color_constants,
            repair_zero_waits,
        )

        code, replacements = repair_unknown_color_constants(code)
        if replacements:
            log.info(
                "Repaired invented Manim color constants: %s",
                ", ".join(f"{old}->{new}" for old, new in sorted(replacements.items())),
            )
        # Tex("m_1") is text-mode math: LaTeX aborts with "Missing $ inserted."
        # and the render dies after minutes (a whole cloud job). Promote to
        # MathTex here so the candidate is salvaged instead of wasted.
        code, promoted = repair_text_mode_math(code)
        if promoted:
            log.info("Promoted text-mode math to MathTex: %s", "; ".join(promoted))
        # self.wait(0.0) is a no-op that Manim 0.21 rejects at render time.
        code, dropped = repair_zero_waits(code)
        if dropped:
            log.info("Removed %d zero-length self.wait() call(s).", dropped)
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
        code = build_scene(
            class_name=class_name,
            domain=domain,
            title=title,
            summary=solver.summary[:120],
            steps=solver.derivation_steps[:4],
            variables=solver.variables,
            palette=palette,
        )
        try:
            from aetherlab.services.scene_components.layout import (
                apply_fallback_layout_fixes,
            )

            fixed, fixes = apply_fallback_layout_fixes(code)
            if fixes:
                compile(fixed, "<aetherlab-fallback-layout>", "exec")
                log.info("Fallback layout fixes: %s", "; ".join(fixes))
                return fixed
        except Exception:  # noqa: BLE001 - layout polish never breaks fallback
            pass
        return code
