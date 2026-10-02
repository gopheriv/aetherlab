"""ManimGL/Community scene generation, rendering, and validation."""

from __future__ import annotations

import ast
import asyncio
import hashlib
import logging
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from aetherlab.core.models import ProblemRequest, RagResult, SceneBundle, SolverResult
from aetherlab.core.proc import (
    ProcessCancelledError,
    run_process_tree,
    subprocess_kwargs,
)
from aetherlab.services.scene_generator import SceneGenerator

if TYPE_CHECKING:
    from aetherlab.core.settings import AppSettings

log = logging.getLogger(__name__)

# Where rendered videos are cached
_RENDER_DIR = Path(tempfile.gettempdir()) / "aetherlab" / "renders"
_RENDER_DIR.mkdir(parents=True, exist_ok=True)

# One isolated sub-directory per render lives here (Bug 1: no shared partial
# cache). Old run dirs are LRU-pruned so temp stays bounded.
_RUNS_DIR = _RENDER_DIR / "runs"
_MAX_KEPT_RUNS = 24

# Manim Community render quality: 480p for speed
_RENDER_QUALITY = "l"  # low = 480p15


@dataclass
class SceneCandidate:
    index: int
    scene: SceneBundle
    storyboard: dict | None = None
    draft_video_path: str = ""
    score: float = 0.0
    verdict: str = ""
    issues: list[str] = field(default_factory=list)
    breakdown: dict[str, float] = field(default_factory=dict)
    duration_delta: float = 9999.0


# ── Tournament budget control (Quality Flywheel Phase 4) ─────────────────────
# A first candidate scoring at/above this ships immediately; below it, the
# tournament escalates and fans out more candidates (cheap-first, expensive-only-
# when-needed). Keyless static-proxy scores are usually high, so keyless runs
# stay single-candidate cheap; only a genuinely weak (usually vision-judged)
# first render pays for a fan-out.
ESCALATE_BELOW_SCORE = 8.0


def storyboard_difficulty(storyboard: dict | None) -> float:
    """Estimate a storyboard's rendering difficulty in [0.0, 1.0].

    Harder scenes (more acts, more beats, longer runtime) are worth more
    candidates. An unknown/missing storyboard is treated as medium so we neither
    starve nor overspend on it.
    """
    if not isinstance(storyboard, dict):
        return 0.5
    acts = [a for a in (storyboard.get("acts") or []) if isinstance(a, dict)]
    beats = sum(len(a.get("beats") or []) for a in acts)
    duration = sum(float(a.get("duration_s") or 0.0) for a in acts)
    score = (
        min(len(acts) / 4.0, 1.0) * 0.4
        + min(beats / 12.0, 1.0) * 0.4
        + min(duration / 30.0, 1.0) * 0.2
    )
    return max(0.0, min(1.0, score))


def candidate_budget(storyboard: dict | None, cap: int) -> int:
    """Difficulty-scaled maximum number of candidates, clamped to [1, cap]."""
    if cap <= 1:
        return 1
    difficulty = storyboard_difficulty(storyboard)
    # Truncate (not round) so budgets stay conservative — cheap-first is the
    # whole point: an easy scene gets 1, only a clearly hard one reaches the cap.
    return max(1, min(cap, 1 + int(difficulty * (cap - 1))))


# Default candidate cap when the tournament runs auto-on for a configured user.
AUTO_TOURNAMENT_CAP = 3


def effective_candidate_cap(settings: "AppSettings | None") -> int:
    """The effective candidate cap in [1, 8] (Phase 6: default-on, safely).

    An explicit ``scene_candidates > 1`` is the power-user override. Otherwise,
    when a vision critic (API key + vision model) is configured and
    ``auto_tournament`` is on, default to ``AUTO_TOURNAMENT_CAP`` so configured
    users get the multi-candidate quality loop with no extra clicks — Phase-4
    escalation keeps the *typical* cost at one render. Keyless/offline (no
    critic) stays at 1: exactly one render, exactly as fast as before.
    """
    if settings is None:
        return 1
    explicit = int(getattr(settings, "scene_candidates", 1) or 1)
    if explicit > 1:
        return min(explicit, 8)
    has_critic = bool(
        getattr(settings, "openai_api_key", None) and getattr(settings, "vision_model", None)
    )
    if has_critic and bool(getattr(settings, "auto_tournament", True)):
        return AUTO_TOURNAMENT_CAP
    return 1


def detect_latex() -> bool:
    """True when a LaTeX toolchain is available for Manim's MathTex/Tex.

    Manim only needs LaTeX for Tex-family mobjects; when it's absent the scene
    prompts add a Text-only rule so generated scenes still render everywhere
    (the domain fallback templates are already Text-only by contract).
    """
    return shutil.which("latex") is not None or shutil.which("xelatex") is not None


def _detect_render_tier() -> dict:
    """Hardware-aware render tier, ported from the manim-bot project.

    Governs fps and process priority: capable boxes get 60fps, constrained
    ones render at 30fps below normal priority so the UI stays responsive.
    Always passing an explicit --fps prevents Manim from silently producing
    15fps output at low quality.
    """
    tiers = {
        "cinematic": {"name": "cinematic", "fps": 60, "below_normal": False},
        "standard": {"name": "standard", "fps": 30, "below_normal": False},
        "constrained": {"name": "constrained", "fps": 30, "below_normal": True},
        "cloud_cinematic": {"name": "cloud_cinematic", "fps": 60, "below_normal": False},
    }
    forced = (os.getenv("AETHERLAB_RENDER_TIER") or os.getenv("RENDER_TIER") or "auto").strip().lower()
    if forced in tiers:
        tier = dict(tiers[forced])
    else:
        try:
            import psutil

            total_gb = psutil.virtual_memory().total / 1024**3
            cpu = os.cpu_count() or 2
        except Exception:
            total_gb, cpu = 8.0, 2

        if total_gb >= 16 and cpu >= 6:
            tier = dict(tiers["cinematic"])
        elif total_gb >= 10:
            tier = dict(tiers["standard"])
        else:
            tier = dict(tiers["constrained"])

    fps_override = _env_int("AETHERLAB_MANIM_FPS", "MANIM_FPS", default=0)
    if fps_override > 0:
        tier["fps"] = fps_override
    return tier


def _env_int(*names: str, default: int = 0) -> int:
    for name in names:
        value = os.getenv(name)
        if value is None or not value.strip():
            continue
        try:
            return int(value)
        except ValueError:
            continue
    return default


_RENDER_TIER = _detect_render_tier()


class ManimRuntime:
    def __init__(self, settings: "AppSettings | None" = None) -> None:
        self._settings = settings

    async def generate_scene_async(
        self,
        request: ProblemRequest,
        solver: SolverResult,
        rag: RagResult,
        settings: "AppSettings | None" = None,
        max_retries: int = 1,
        plan: object | None = None,
        aspect: str = "full",
        minimax_thinking: bool | None = None,
        locked_storyboard: dict | None = None,
        force_ai: bool = False,
    ) -> SceneBundle:
        """Generate a dynamic Manim scene, preferring curated components.

        A curated, numeric-driven component (services/scene_components) is used
        when one fits — it renders the real solution and is far more reliable
        than free-form LLM code. Only when no component fits do we fall back to
        LLM generation (with a key) or the static template. ``aspect``
        (setup/evolution/math/recap/full) steers that deterministic template
        fallback so a keyless lesson's chapters render as distinct clips.
        """
        s = settings or self._settings
        engine, diagnostics = self.detect_engine()
        class_name = "AetherLabScene"
        duration_target_s = float(request.duration_target_s)
        duration_failure_reason = ""
        try:
            from aetherlab.services.verify import physics_expectations

            expected_physics = physics_expectations(solver, request)
        except Exception:  # noqa: BLE001 — critique context must never block generation
            expected_physics = []

        composed = None if force_ai else self._compose_curated(
            class_name, solver, plan, diagnostics, float(request.duration_target_s),
            problem_prompt=request.prompt,
        )
        if composed is not None:
            composed.storyboard = {"physics_expectations": expected_physics}
            return composed

        # Why this scene is NOT AI-authored ("" while the LLM path is winning).
        fallback_reason = ""
        if s and s.openai_api_key:
            from aetherlab.services.code_safety import validate_code_safety
            from aetherlab.services.scene_validation import (
                count_construct_play_calls,
                estimate_duration,
                scene_hygiene_warnings,
                validate_scene,
            )

            generator = SceneGenerator(s, minimax_thinking=minimax_thinking)

            async def repair_rejected_scene(
                rejected_code: str, rejection: str, attempt_no: int
            ) -> str | None:
                """Ask once for a constrained fix, then re-run every static gate."""
                try:
                    repaired = await generator.repair(
                        rejected_code,
                        "This generated scene was rejected before rendering. Fix only "
                        "the reported syntax/safety/validation problems; do not use "
                        "getattr/setattr/hasattr, eval/exec, dunder attributes, "
                        "reflection, or unapproved imports.\n\n"
                        + rejection,
                        class_name,
                        full_scene=True,
                    )
                    compile(repaired, "<aetherlab-generated-scene-repair>", "exec")
                    repaired_safe, safety_issues = validate_code_safety(repaired)
                    repaired_board = dict(generator._last_storyboard or {})
                    repaired_lint_ok, lint_issues = validate_scene(
                        repaired,
                        require_motion=True,
                        timeline=repaired_board.get("timeline"),
                    )
                    repaired_overlaps = [
                        issue for issue in scene_hygiene_warnings(repaired)
                        if issue.startswith(_LAYOUT_BLOCKERS)
                    ]
                    repaired_estimate = estimate_duration(repaired)
                    target_miss = _estimate_misses_target(
                        repaired_estimate, duration_target_s
                    )
                    if not repaired_safe or not repaired_lint_ok or repaired_overlaps or target_miss:
                        problems = (
                            safety_issues + lint_issues + repaired_overlaps
                            + ([
                                f"[TIMING:DURATION] estimated {repaired_estimate.total_seconds:.1f}s; "
                                f"target {duration_target_s:.1f}s."
                            ] if target_miss else [])
                        )
                        diagnostics.append(
                            f"Attempt {attempt_no}: rejected-scene repair failed validation: "
                            + "; ".join(problems[:4])
                        )
                        return None
                    diagnostics.append(
                        f"Attempt {attempt_no}: repaired the generated scene after "
                        "pre-render validation."
                    )
                    return repaired
                except Exception as exc:  # noqa: BLE001 - repair is bounded and fail-soft
                    diagnostics.append(
                        f"Attempt {attempt_no}: generated-scene repair failed: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    return None

            async def repair_duration_miss(
                code_to_repair: str, estimate_seconds: float, attempt_no: int
            ) -> str | None:
                """Adjust readable holds when valid AI code misses its target."""
                low = duration_target_s * 0.8
                high = duration_target_s * 1.2
                if estimate_seconds < low:
                    instruction = (
                        f"The safe, valid scene is estimated at {estimate_seconds:.1f}s; "
                        f"the required window is {low:.1f}-{high:.1f}s for a "
                        f"{duration_target_s:.1f}s target. Add about "
                        f"{duration_target_s - estimate_seconds:.1f}s using readable "
                        "wait/hold durations on existing beats. Do not add details, "
                        "remove beats, or add self.play calls."
                    )
                else:
                    instruction = (
                        f"The safe, valid scene is estimated at {estimate_seconds:.1f}s; "
                        f"the required window is {low:.1f}-{high:.1f}s for a "
                        f"{duration_target_s:.1f}s target. Shorten only excess waits/holds "
                        "on existing beats. Do not remove details or change physics."
                    )
                instruction += (
                    " Preserve all exact BEAT markers, physics details, motion, and the "
                    "living ending. Stay within 16 top-level self.play calls and two "
                    "live updaters; never animate a mobject while an updater also changes it."
                    "\nRepair only construct() beginning at line "
                    f"{_construct_definition_line(code)}."
                )
                try:
                    repaired = await generator.repair(
                        code_to_repair, instruction, class_name, full_scene=False
                    )
                    compile(repaired, "<aetherlab-duration-repair>", "exec")
                    repaired_safe, safety_issues = validate_code_safety(repaired)
                    repaired_lint_ok, lint_issues = validate_scene(
                        repaired,
                        require_motion=True,
                        timeline=generator._last_storyboard.get("timeline")
                        if isinstance(generator._last_storyboard, dict) else None,
                    )
                    repaired_hygiene = scene_hygiene_warnings(repaired)
                    repaired_overlaps = [
                        issue for issue in repaired_hygiene
                        if issue.startswith(_LAYOUT_BLOCKERS)
                    ]
                    repaired_estimate = estimate_duration(repaired)
                    repaired_cost = _estimate_render_cost(repaired)
                    repaired_play_calls = count_construct_play_calls(repaired)
                    is_cloud = str(getattr(s, "render_mode", "local") or "local").lower() in {
                        "cloud", "auto",
                    }
                    too_expensive = is_cloud and repaired_cost > 3.5
                    too_many_plays = (
                        is_cloud and duration_target_s >= 24.0
                        and repaired_play_calls > 16
                    )
                    still_misses = _estimate_misses_target(
                        repaired_estimate, duration_target_s
                    )
                    if (
                        not repaired_safe or not repaired_lint_ok or repaired_overlaps
                        or too_expensive or too_many_plays or still_misses
                    ):
                        problems = (
                            safety_issues + lint_issues + repaired_overlaps
                            + ([f"[PERF:CLOUD_COST] estimate {repaired_cost:.1f} exceeds 3.5."]
                               if too_expensive else [])
                            + ([f"[PERF:PLAY_BUDGET] {repaired_play_calls} calls exceed 16."]
                               if too_many_plays else [])
                            + ([
                                f"[TIMING:DURATION] repaired estimate "
                                f"{repaired_estimate.total_seconds:.1f}s remains outside "
                                f"{low:.1f}-{high:.1f}s."
                            ] if still_misses else [])
                        )
                        diagnostics.append(
                            f"Attempt {attempt_no}: targeted duration repair failed validation: "
                            + "; ".join(problems[:4])
                        )
                        return None
                    diagnostics.append(
                        f"Attempt {attempt_no}: applied a targeted duration repair "
                        f"({repaired_estimate.total_seconds:.1f}s)."
                    )
                    return repaired
                except Exception as exc:  # noqa: BLE001 - bounded repair is fail-soft
                    diagnostics.append(
                        f"Attempt {attempt_no}: targeted duration repair failed: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    return None

            # Best compiled, safety-checked AI scene whose remaining findings are
            # all advisory: (issue count, code, storyboard, issues, scene spec).
            advisory_candidate: tuple[int, str, dict, list[str], object] | None = None

            def keep_advisory(candidate_code: str, board: dict, issues: list[str]) -> None:
                nonlocal advisory_candidate
                # A (repaired) built-in template must never be shipped as an
                # AI scene: the candidate path returns used_fallback=False.
                if fallback_reason:
                    return
                if advisory_candidate is None or len(issues) < advisory_candidate[0]:
                    advisory_candidate = (
                        len(issues), candidate_code, dict(board), list(issues),
                        getattr(generator, "_last_scene_spec", None),
                    )

            for attempt in range(max_retries + 1):
                if locked_storyboard is None:
                    code = await generator.generate(request, solver, rag, class_name)
                else:
                    code = await generator.generate(
                        request, solver, rag, class_name,
                        locked_storyboard=locked_storyboard,
                    )
                # A fallback scene compiles and renders perfectly, so without an
                # explicit signal it is indistinguishable from a real AI answer.
                # Surface it loudly — generate() already exhausted its own
                # attempts internally, so retrying here would only repeat them.
                fallback_reason = getattr(generator, "_last_fallback_reason", "")
                if fallback_reason:
                    diagnostics.append(f"FALLBACK: {fallback_reason}")
                try:
                    compile(code, "<aetherlab-generated-scene>", "exec")
                except SyntaxError as exc:
                    diagnostics.append(f"Attempt {attempt + 1}: scene failed to compile: {exc}")
                    if not fallback_reason:
                        repaired = await repair_rejected_scene(
                            code, f"Python SyntaxError: {exc}", attempt + 1
                        )
                        if repaired is not None:
                            code = repaired
                        else:
                            continue
                storyboard = dict(generator._last_storyboard or {})
                # Fail-closed safety gate: generated scenes run with full
                # interpreter privileges in the render subprocess.
                safe, issues = validate_code_safety(code)
                if not safe:
                    diagnostics.append(
                        f"Attempt {attempt + 1}: scene failed the safety gate: "
                        + "; ".join(issues[:4])
                    )
                    if not fallback_reason:
                        repaired = await repair_rejected_scene(
                            code,
                            "Safety gate findings:\n- " + "\n- ".join(issues[:12]),
                            attempt + 1,
                        )
                        if repaired is not None:
                            code = repaired
                            safe, issues = validate_code_safety(code)
                        if not safe:
                            continue
                # Static pre-render lint: hallucinated names, provably-bad
                # kwargs, structurally broken LaTeX. Catching these here turns
                # a render crash + repair round into a fresh generation.
                lint_ok, lint_issues = validate_scene(
                    code,
                    require_motion=True,
                    timeline=storyboard.get("timeline"),
                )
                cloud_mode = str(getattr(s, "render_mode", "local") or "local").lower() in {
                    "cloud", "auto",
                }
                render_cost = _estimate_render_cost(code)
                expensive_scene = cloud_mode and render_cost > 3.5
                play_calls = count_construct_play_calls(code)
                play_budget_exceeded = (
                    cloud_mode and duration_target_s >= 24.0 and play_calls > 16
                )
                hygiene = scene_hygiene_warnings(code)
                overlap_issues = [
                    issue for issue in hygiene
                    if issue.startswith(_LAYOUT_BLOCKERS)
                ]
                missing_markers = not lint_ok and any(
                    issue.startswith("[TIMING:BEAT_MARKERS]")
                    for issue in lint_issues
                )
                timing_runtime_issues = [
                    issue for issue in lint_issues
                    if issue.startswith("[TIMING:BEAT_RUNTIME]")
                ]
                updater_animate_issues = [
                    issue for issue in lint_issues
                    if issue.startswith("[MANIM:UPDATER_ANIMATE]")
                ]
                # Render-crash findings (unknown names, invalid kwargs, broken
                # LaTeX, ManimGL leftovers). Fed to the same bounded repair
                # instead of discarding an otherwise good scene outright.
                crash_issues = [
                    issue for issue in lint_issues
                    if not _is_advisory_issue(issue) and not issue.startswith("[MOTION:")
                ]
                if (
                    missing_markers or timing_runtime_issues or overlap_issues or expensive_scene
                    or play_budget_exceeded or updater_animate_issues or crash_issues
                ):
                    timeline = storyboard.get("timeline", [])
                    marker_lines = [
                        f"# BEAT {event['id']} | {float(event['start_s']):.2f}-"
                        f"{float(event['end_s']):.2f} s"
                        for event in timeline
                        if isinstance(event, dict)
                        and event.get("id")
                        and event.get("start_s") is not None
                        and event.get("end_s") is not None
                    ]
                    repair_instructions = []
                    if crash_issues:
                        repair_instructions.append(
                            "These findings would crash the render. Replace each invalid "
                            "name or argument with a real Manim Community equivalent "
                            "(for example a rotated Square or a Polygon for a diamond) "
                            "and keep the visual intent, physics, and timing:\n"
                            + "\n".join(crash_issues)
                        )
                    if missing_markers and marker_lines:
                        repair_instructions.append(
                            "The scene is otherwise usable, but its timing gate "
                            "requires these exact source comments. Add every line "
                            "verbatim and in order inside AetherLabScene.construct(), "
                            "immediately before the corresponding visual beat. Keep "
                            "the existing visuals, positions, and animation timings.\n"
                            + "\n".join(marker_lines)
                        )
                    if timing_runtime_issues:
                        repair_instructions.append(
                            "The beat comments match the schedule, but the accumulated "
                            "self.play/self.wait durations do not. Adjust only the affected "
                            "beat's literal run_time or wait durations so each beat lasts "
                            "its scheduled duration (within 15%) and the running clock stays "
                            "within 1.5 seconds of the schedule. Preserve all visual objects, "
                            "physics, narration "
                            "cues, and the living ending; do not move details into another "
                            "beat or compress their readable holds.\n"
                            + "\n".join(timing_runtime_issues)
                        )
                    if overlap_issues:
                        repair_instructions.append(
                            "Resolve these likely simultaneous layout collisions. "
                            "Keep the physics and scheduled duration; move the label "
                            "to a separate reserved zone or fade/transform the old "
                            "mobject before reusing its position. Remove unused helper "
                            "functions that create a duplicate label in the same slot:\n"
                            + "\n".join(overlap_issues)
                        )
                    if expensive_scene:
                        repair_instructions.append(
                            f"The cloud render cost estimate is {render_cost:.1f}, "
                            "above the 3.5 limit. Keep every requested visual and the "
                            "full storyboard duration; reduce implementation overhead "
                            "instead of shortening or deleting beats. Target at most 16 "
                            "top-level self.play calls by combining simultaneous items "
                            "with LaggedStart/AnimationGroup/Transform and using waits "
                            "for readable holds. Remove redundant updaters and dead helper "
                            "functions; keep at most two live updater/always_redraw "
                            "objects. Never rebuild a plot inside an updater: build each "
                            "curve once and Transform it between states. The resulting "
                            "cost estimate must be below 3.5."
                        )
                    if play_budget_exceeded:
                        repair_instructions.append(
                            f"This {duration_target_s:.0f}-second Cloud scene has "
                            f"{play_calls} top-level self.play calls; the maximum is 16. "
                            "Combine related animations into LaggedStart or AnimationGroup, "
                            "and use waits for readable holds. Preserve every scheduled "
                            "beat, marker, physics detail, motion, and the full duration. "
                            "Do not remove beats or make the ending static."
                        )
                    if updater_animate_issues:
                        repair_instructions.append(
                            "Fix these mobject/updater conflicts. Do not call .animate on "
                            "a displayed mobject while its active updater also changes its "
                            "value or geometry. Animate the associated ValueTracker and let "
                            "the updater update the display, or clear the updater before the "
                            "play. Preserve the visual beat and its scheduled duration:\n"
                            + "\n".join(updater_animate_issues)
                        )
                    if repair_instructions:
                        repair_error = "\n\n".join(repair_instructions)
                        repair_error += (
                            "\n\nRepair only the construct() method beginning at line "
                            f"{_construct_definition_line(code)}; preserve module helpers."
                        )
                        repair_candidate = code
                        for repair_round in range(2):
                            try:
                                repaired_code = await generator.repair(
                                    repair_candidate, repair_error, class_name,
                                    full_scene=False,
                                )
                                compile(
                                    repaired_code,
                                    "<aetherlab-scene-layout-repair>",
                                    "exec",
                                )
                                repaired_safe, repaired_safety_issues = validate_code_safety(
                                    repaired_code
                                )
                                repaired_lint_ok, repaired_lint_issues = validate_scene(
                                    repaired_code,
                                    require_motion=True,
                                    timeline=timeline,
                                )
                                repaired_hygiene = scene_hygiene_warnings(repaired_code)
                                repaired_overlaps = [
                                    issue for issue in repaired_hygiene
                                    if issue.startswith(_LAYOUT_BLOCKERS)
                                ]
                                repaired_cost = _estimate_render_cost(repaired_code)
                                repaired_too_expensive = cloud_mode and repaired_cost > 3.5
                                repaired_play_calls = count_construct_play_calls(repaired_code)
                                repaired_play_budget_exceeded = (
                                    cloud_mode and duration_target_s >= 24.0
                                    and repaired_play_calls > 16
                                )
                                repaired_timing_runtime_issues = [
                                    issue for issue in repaired_lint_issues
                                    if issue.startswith("[TIMING:BEAT_RUNTIME]")
                                ]
                                if (
                                    repaired_safe
                                    and repaired_lint_ok
                                    and not repaired_overlaps
                                    and not repaired_too_expensive
                                    and not repaired_play_budget_exceeded
                                ):
                                    code = repaired_code
                                    lint_ok = True
                                    lint_issues = []
                                    hygiene = repaired_hygiene
                                    overlap_issues = []
                                    render_cost = repaired_cost
                                    expensive_scene = False
                                    play_calls = repaired_play_calls
                                    play_budget_exceeded = False
                                    diagnostics.append(
                                        f"Attempt {attempt + 1}: applied a targeted timing "
                                        "and layout repair."
                                    )
                                    break

                                problems = (
                                    repaired_safety_issues + repaired_lint_issues
                                    + repaired_overlaps
                                    + ([
                                        f"[PERF:CLOUD_COST] repaired cost "
                                        f"{repaired_cost:.1f} remains above 3.5."
                                    ] if repaired_too_expensive else [])
                                    + ([
                                        f"[PERF:PLAY_BUDGET] repaired scene has "
                                        f"{repaired_play_calls} top-level self.play calls; "
                                        "maximum is 16."
                                    ] if repaired_play_budget_exceeded else [])
                                )
                                # The repair may have fixed every crash while
                                # leaving advisory drift; that version still
                                # beats both the crashing original and the
                                # template, so offer it as a candidate.
                                if repaired_safe and all(_is_advisory_issue(i) for i in problems):
                                    keep_advisory(repaired_code, storyboard, problems)
                                diagnostics.append(
                                    f"Attempt {attempt + 1}: layout repair round "
                                    f"{repair_round + 1} failed validation: "
                                    + "; ".join(problems[:4])
                                )
                                repairable_lint = all(
                                    issue.startswith((
                                        "[TIMING:BEAT_MARKERS]",
                                        "[TIMING:BEAT_RUNTIME]",
                                        "[MANIM:UPDATER_ANIMATE]",
                                    ))
                                    for issue in repaired_lint_issues
                                )
                                can_refine = (
                                    repair_round == 0
                                    and repaired_safe
                                    and not repaired_overlaps
                                    and repairable_lint
                                    and (
                                        repaired_too_expensive
                                        or repaired_play_budget_exceeded
                                        or repaired_timing_runtime_issues
                                    )
                                )
                                if not can_refine:
                                    break
                                repair_candidate = repaired_code
                                repair_error = (
                                    "Your previous whole-scene repair is close but still "
                                    "fails these exact checks. Make only the remaining safe "
                                    "changes while preserving physics, all beats, and their "
                                    "full duration:\n- " + "\n- ".join(problems[:8])
                                )
                                if marker_lines:
                                    repair_error += (
                                        "\nRestore every required timing marker verbatim and "
                                        "in order:\n" + "\n".join(marker_lines)
                                    )
                                repair_error += (
                                    "\nRepair only construct() beginning at line "
                                    f"{_construct_definition_line(repair_candidate)}."
                                )
                            except Exception as exc:  # noqa: BLE001 - bounded repair is fail-soft
                                diagnostics.append(
                                    f"Attempt {attempt + 1}: targeted layout repair "
                                    f"round {repair_round + 1} failed: "
                                    f"{type(exc).__name__}: {exc}"
                                )
                                break
                if (
                    not lint_ok or overlap_issues or expensive_scene
                    or play_budget_exceeded
                ):
                    if expensive_scene:
                        overlap_issues.append(
                            f"[PERF:CLOUD_COST] estimate {render_cost:.1f} remains "
                            "above the 3.5 cloud limit."
                        )
                    if play_budget_exceeded:
                        overlap_issues.append(
                            f"[PERF:PLAY_BUDGET] {play_calls} top-level self.play "
                            "calls exceed the 16-call Cloud limit."
                        )
                    diagnostics.append(
                        f"Attempt {attempt + 1}: pre-render lint failed: "
                        + "; ".join((lint_issues + overlap_issues)[:4])
                    )
                    remaining = lint_issues + overlap_issues
                    if not fallback_reason and all(_is_advisory_issue(i) for i in remaining):
                        keep_advisory(code, storyboard, remaining)
                    continue
                if attempt > 0:
                    diagnostics.append(f"Scene succeeded on retry {attempt}.")
                est = estimate_duration(code)
                if not fallback_reason and _estimate_misses_target(
                    est, duration_target_s
                ):
                    lower = duration_target_s * 0.8
                    upper = duration_target_s * 1.2
                    duration_failure_reason = (
                        f"AI scene estimate {est.total_seconds:.1f}s was outside the "
                        f"{lower:.1f}-{upper:.1f}s target window after {attempt + 1} "
                        "generation attempt(s)."
                    )
                    diagnostics.append(
                        f"Attempt {attempt + 1}: {duration_failure_reason} "
                        "Trying a bounded hold-time repair."
                    )
                    duration_repaired = await repair_duration_miss(
                        code, est.total_seconds, attempt + 1
                    )
                    if duration_repaired is None:
                        keep_advisory(code, storyboard, [
                            f"[TIMING:DURATION] estimated {est.total_seconds:.1f}s for a "
                            f"{duration_target_s:.0f}s target."
                        ])
                        continue
                    code = duration_repaired
                    est = estimate_duration(code)
                diagnostics.append(
                    f"Estimated duration ~{est.total_seconds:.0f}s "
                    f"({est.play_calls} beats, {est.wait_calls} waits)"
                    + ("." if est.exact else "; approximate: " + "; ".join(est.notes[:2]) + ".")
                )
                if hygiene:
                    diagnostics.append("Scene hygiene warnings: " + "; ".join(hygiene[:4]))
                storyboard["physics_expectations"] = expected_physics
                return SceneBundle(
                    class_name=class_name,
                    code=code,
                    engine=engine,
                    status="compiled",
                    used_fallback=bool(fallback_reason),
                    fallback_reason=fallback_reason,
                    diagnostics=diagnostics,
                    # Carried so the visual critic can judge the render
                    # against the director's locked treatment.
                    storyboard=storyboard,
                    scene_spec=getattr(generator, "_last_scene_spec", None),
                )
            # All retries exhausted. An AI scene whose only remaining findings
            # are advisory (timing drift, a possible overlap, render cost) still
            # answers the question; the generic template does not. Ship the best
            # such scene with its warnings — the critic/revision loop can polish.
            if advisory_candidate is not None:
                _count, code, storyboard, remaining, spec = advisory_candidate
                diagnostics.append(
                    "Shipping the best AI scene with advisory issues (no attempt was "
                    "fully clean): " + "; ".join(remaining[:4])
                )
                storyboard["physics_expectations"] = expected_physics
                return SceneBundle(
                    class_name=class_name,
                    code=code,
                    engine=engine,
                    status="compiled",
                    diagnostics=diagnostics,
                    storyboard=storyboard,
                    scene_spec=spec,
                )
            # Nothing usable — fall back to the static template
            fallback_reason = fallback_reason or duration_failure_reason or (
                "Every AI scene attempt failed validation; showing the built-in "
                "domain template."
            )
            diagnostics.append(f"FALLBACK: {fallback_reason}")
            code = self._build_scene_code(class_name, request, solver, rag, aspect)
        else:
            fallback_reason = (
                "No API key is configured, so the built-in domain template was used "
                "instead of an AI-generated scene."
            )
            code = self._build_scene_code(class_name, request, solver, rag, aspect)

        try:
            compile(code, "<aetherlab-generated-scene>", "exec")
            status = "compiled"
        except SyntaxError as exc:
            diagnostics.append(f"Generated scene failed to compile: {exc}")
            status = "compile-error"
        return SceneBundle(
            class_name=class_name,
            code=code,
            engine=engine,
            status=status,
            used_fallback=bool(fallback_reason),
            fallback_reason=fallback_reason,
            diagnostics=diagnostics,
            storyboard={"physics_expectations": expected_physics},
        )

    def _compose_curated(
        self, class_name: str, solver: SolverResult, plan: object | None, diagnostics: list[str],
        duration_target_s: float = 30.0, *, problem_prompt: str = "",
    ) -> SceneBundle | None:
        """Build a scene from the curated component library, if one fits."""
        try:
            from aetherlab.services.scene_components import compose_scene_code

            code = compose_scene_code(
                class_name, solver, plan, duration_target_s,
                problem_prompt=problem_prompt,
            )
        except Exception as exc:  # noqa: BLE001 — composition must never crash
            diagnostics.append(f"Curated composition unavailable: {exc}")
            return None
        if not code:
            return None
        try:
            compile(code, "<aetherlab-composed-scene>", "exec")
        except SyntaxError as exc:
            diagnostics.append(f"Composed scene failed to compile: {exc}")
            return None
        engine, _ = self.detect_engine()
        diagnostics.append("Scene composed from curated component library (numeric-driven).")
        return SceneBundle(
            class_name=class_name,
            code=code,
            engine=engine,
            status="compiled",
            diagnostics=diagnostics,
        )

    def scene_tournament_enabled(self, settings: "AppSettings | None" = None) -> bool:
        s = settings or self._settings
        # Requires a vision critic (to rank candidates) and an effective cap > 1
        # — which is true either by an explicit scene_candidates>1 or by the
        # auto_tournament default. Keyless/offline always resolves to 1 → off.
        return bool(
            s is not None
            and getattr(s, "openai_api_key", None)
            and getattr(s, "vision_model", None)
            and effective_candidate_cap(s) > 1
        )

    async def generate_render_tournament(
        self,
        request: ProblemRequest,
        solver: SolverResult,
        rag: RagResult,
        settings: "AppSettings | None" = None,
        quality: str = "l",
        brief: str = "",
        aspect: str = "full",
        progress: Callable[[str], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> SceneBundle:
        """Opt-in candidate tournament, failing soft to the normal single path."""
        s = settings or self._settings

        async def render_final(scene: SceneBundle, final_brief: str) -> SceneBundle:
            kwargs = {"cancel_check": cancel_check} if cancel_check is not None else {}
            return await self.render_scene_with_repair(
                scene,
                s,
                quality=quality,
                brief=final_brief,
                progress=progress,
                **kwargs,
            )

        async def score_candidates(items: list[SceneCandidate]) -> list[SceneCandidate]:
            kwargs = {"cancel_check": cancel_check} if cancel_check is not None else {}
            return await self._render_and_score_candidates(items, s, progress, **kwargs)

        if not self.scene_tournament_enabled(s):
            scene = await self.generate_scene_async(request, solver, rag, s, aspect=aspect)
            return await render_final(scene, brief)

        try:
            cap = effective_candidate_cap(s)
            # Cheap-first (Phase 4): render ONE candidate, then fan out the rest
            # of a difficulty-scaled budget ONLY if that first render is weak.
            first_built = await self._build_scene_candidates(
                request, solver, rag, s, aspect, progress, count=1, start_index=0
            )
            scored = await score_candidates(first_built)
            storyboard0 = scored[0].storyboard if scored else None
            budget = candidate_budget(storyboard0, cap) if scored else cap
            difficulty = storyboard_difficulty(storyboard0) if scored else 0.0
            best_so_far = max((c.score for c in scored), default=-1.0)
            # Escalate on the count BUILT (attempts), not scored (rendered): if
            # the first candidate built but failed to render, `scored` is empty
            # while `budget` falls back to the cap, and keying the second batch
            # off `scored` would build up to cap+1 candidates — over budget
            # (BUG-30). Keying off `first_built` caps total attempts at `budget`.
            if (not scored or best_so_far < ESCALATE_BELOW_SCORE) and budget > len(first_built):
                if progress:
                    progress(
                        f"First render scored {best_so_far:.1f}; escalating to "
                        f"{budget} candidate(s)"
                    )
                more = await self._build_scene_candidates(
                    request, solver, rag, s, aspect, progress,
                    count=budget - len(first_built), start_index=len(first_built),
                )
                if more:
                    scored += await score_candidates(more)
            if not scored:
                raise RuntimeError("no candidate rendered and scored")
            winner = sorted(
                scored,
                key=lambda c: (-c.score, len(c.issues), c.duration_delta, c.index),
            )[0]
            # Losers teach: record the aesthetic problems the critic named on the
            # candidates that did NOT win, so the next generation prompt steers
            # away from them (the flywheel's cross-run learning). Fail-soft.
            self._record_aesthetic_pitfalls(
                [issue for c in scored if c is not winner for issue in c.issues], s
            )
            # Observe: record the tournament (per-candidate scores + winner) in
            # the render-farm ledger so the dashboard can show why this scene won,
            # and so the ledger report (F181) can mine spend + the draft->HQ pair.
            job_id = self._record_tournament_ledger(
                scored, winner, s, quality, difficulty=difficulty, budget=budget
            )
            selected = SceneBundle(
                class_name=winner.scene.class_name,
                code=winner.scene.code,
                engine=winner.scene.engine,
                # Carry the winner's already-rendered draft through so the
                # repair path reuses it instead of rendering the same draft a
                # second time (BUG-29). render_scene_with_repair promotes it to
                # the requested quality from here.
                status=winner.scene.status,
                video_path=winner.scene.video_path,
                failure_kind=winner.scene.failure_kind,
                diagnostics=list(winner.scene.diagnostics) + [
                    (
                        f"Tournament winner: candidate #{winner.index + 1}, best of "
                        f"{len(scored)} rendered (score {winner.score:.1f})."
                    )
                ],
                storyboard=winner.storyboard,
                quality_score=winner.score,
                critique_verdict=winner.verdict,
                critique_issues=list(winner.issues),
                critique_breakdown=dict(winner.breakdown),
            )
            try:
                from aetherlab.services.scene_specification import refresh_scene_bundle_spec

                refresh_scene_bundle_spec(selected, request, solver, rag)
            except Exception as exc:  # noqa: BLE001 - a scene spec cannot break a tournament
                selected.diagnostics.append(
                    f"Scene specification unavailable: {type(exc).__name__}."
                )
            final = await render_final(selected, brief or request.prompt)
            # Winners teach — from the FINAL, HQ-critiqued result, not the 480p
            # draft score used only for tournament SELECTION. The critique loop in
            # render_scene_with_repair re-scores the promoted HQ render (and any
            # aesthetic revision), so exemplar promotion + retrieval (F173/F179)
            # learn from the quality the user actually sees. Never edits the
            # curated exemplar source automatically (supply-chain safety).
            self._record_exemplar_candidate(final, solver, s)
            # Close the draft->HQ loop in the ledger: record the winner's FINAL HQ
            # critic score against the same job the draft scores were logged under,
            # so the ledger report can correlate the cheap proxy with what shipped.
            self._record_tournament_hq(job_id, final, s)
            return final
        except ProcessCancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - tournament must never break solve
            log.info("Scene tournament failed (%s); falling back to single scene path.", exc)
            scene = await self.generate_scene_async(request, solver, rag, s, aspect=aspect)
            return await render_final(scene, brief)

    def _record_aesthetic_pitfalls(self, issues: list[str], settings: "AppSettings") -> None:
        """Persist losing candidates' critic issues so future prompts avoid them."""
        if not issues:
            return
        try:
            from aetherlab.services.error_learner import AestheticPitfallStore

            AestheticPitfallStore(settings.data_dir / "aesthetic_pitfalls.json").record(issues)
        except Exception as exc:  # noqa: BLE001 — learning is a bonus, never fatal
            log.info("Could not record aesthetic pitfalls (%s).", exc)

    def _record_exemplar_candidate(
        self, scene: SceneBundle, solver: SolverResult, settings: "AppSettings"
    ) -> None:
        """Stash a critic-approved, high-scoring scene as an exemplar candidate.

        Keyed off the FINAL scene's HQ critique (``quality_score``/
        ``critique_verdict``), so promotion reflects what the user sees — not the
        480p draft score the tournament used only to pick the winner.
        """
        try:
            from aetherlab.services.scene_exemplars import ExemplarCandidateStore
            from aetherlab.services.scene_templates import detect_domain

            domain = detect_domain(list(solver.keywords or []), dict(solver.variables or {}))
            ExemplarCandidateStore(settings.data_dir / "exemplar_candidates.json").record(
                domain=domain,
                code=scene.code,
                score=float(scene.quality_score),
                verdict=str(scene.critique_verdict),
                query_text=" ".join(str(k) for k in (solver.keywords or [])),
            )
        except Exception as exc:  # noqa: BLE001 — promotion is a bonus, never fatal
            log.info("Could not record exemplar candidate (%s).", exc)

    def _record_tournament_ledger(
        self, scored: list["SceneCandidate"], winner: "SceneCandidate",
        settings: "AppSettings", quality: str, *,
        difficulty: float = 0.0, budget: int = 0,
    ) -> str:
        """Record the tournament (candidates + winner + backend) in the ledger.

        Returns the ledger job id (or "" on failure) so the caller can record the
        winner's HQ score against the same job once the repair loop re-critiques it.
        """
        try:
            import hashlib

            from aetherlab.services.render_ledger import RenderJobLedger

            job_id = "tournament-" + hashlib.sha256(
                (winner.scene.code + quality).encode("utf-8")
            ).hexdigest()[:16]
            mode = str(getattr(settings, "render_mode", "local") or "local")
            backend = "github-actions" if mode in ("cloud", "auto") else "local"
            ledger = RenderJobLedger(settings.data_dir / "render_ledger.json")
            ledger.start(
                job_id=job_id, scene_class=winner.scene.class_name, quality=quality,
                backend=backend, provider=str(getattr(settings, "cloud_provider", "")),
            )
            ledger.tournament(job_id, difficulty=difficulty, budget=budget)
            ledger.candidates(job_id, [
                {"index": c.index, "score": c.score, "verdict": c.verdict, "breakdown": c.breakdown}
                for c in scored
            ])
            ledger.winner(job_id, winner.index)
            ledger.finish(job_id, "rendered")
            return job_id
        except Exception as exc:  # noqa: BLE001 — observability must never break a render
            log.info("Could not record tournament ledger (%s).", exc)
            return ""

    def _record_tournament_hq(
        self, job_id: str, final: SceneBundle, settings: "AppSettings"
    ) -> None:
        """Record the winner's FINAL HQ critic score against its tournament job.

        No-ops when ``job_id`` is empty (the ledger record failed) so a broken
        ledger never blocks a solve. Fail-soft like every flywheel leaf.
        """
        if not job_id:
            return
        try:
            from aetherlab.services.render_ledger import RenderJobLedger

            RenderJobLedger(settings.data_dir / "render_ledger.json").hq_result(
                job_id,
                score=float(final.quality_score or 0.0),
                verdict=str(final.critique_verdict or ""),
            )
        except Exception as exc:  # noqa: BLE001 — observability must never break a render
            log.info("Could not record tournament HQ result (%s).", exc)

    async def _build_scene_candidates(
        self,
        request: ProblemRequest,
        solver: SolverResult,
        rag: RagResult,
        settings: "AppSettings",
        aspect: str,
        progress: Callable[[str], None] | None,
        count: int | None = None,
        start_index: int = 0,
    ) -> list[SceneCandidate]:
        """Generate ``count`` candidates numbered from ``start_index``.

        ``count=None`` builds the full configured cap (legacy behaviour).
        Escalation builds one at a time, so absolute indices are preserved for
        temperature diversity and per-candidate cloud isolation (variant).
        """
        from aetherlab.services.code_safety import validate_code_safety
        from aetherlab.services.scene_validation import (
            estimate_duration,
            scene_hygiene_warnings,
            validate_scene,
        )

        cap = effective_candidate_cap(settings)
        n = cap if count is None else max(0, int(count))
        engine, base_diagnostics = self.detect_engine()
        generator = SceneGenerator(settings)
        candidates: list[SceneCandidate] = []
        class_name = "AetherLabScene"
        for i in range(start_index, start_index + n):
            try:
                if progress:
                    progress(f"Generating scene candidate {i + 1}")
                seed = f"candidate {i + 1}: distinct camera/composition/pacing, same physics"
                board = await generator.storyboard(
                    request,
                    solver,
                    rag,
                    temperature=min(1.1, 0.85 + 0.06 * i),
                    variation_seed=seed,
                )
                if board is None:
                    continue
                code = await generator.generate_from_storyboard(
                    request, solver, rag, class_name, board
                )
                compile(code, "<aetherlab-candidate-scene>", "exec")
                safe, safety_issues = validate_code_safety(code)
                if not safe:
                    log.info("Candidate %d rejected by safety gate: %s", i + 1, safety_issues[:3])
                    continue
                lint_ok, lint_issues = validate_scene(
                    code, require_motion=True, timeline=board.get("timeline")
                )
                if not lint_ok:
                    log.info("Candidate %d rejected by scene lint: %s", i + 1, lint_issues[:3])
                    continue
                est = estimate_duration(code)
                if _estimate_misses_target(est, request.duration_target_s):
                    log.info(
                        "Tournament candidate %d rejected: estimate %.1fs misses %.1fs target.",
                        i + 1, est.total_seconds, request.duration_target_s,
                    )
                    continue
                diagnostics = list(base_diagnostics)
                diagnostics.append(
                    f"Tournament candidate {i + 1}: estimated duration ~{est.total_seconds:.0f}s."
                )
                hygiene = scene_hygiene_warnings(code)
                if hygiene:
                    diagnostics.append("Scene hygiene warnings: " + "; ".join(hygiene[:4]))
                scene = SceneBundle(
                    class_name=class_name,
                    code=code,
                    engine=engine,
                    status="compiled",
                    diagnostics=diagnostics,
                    storyboard=board,
                )
                candidates.append(
                    SceneCandidate(
                        index=i,
                        scene=scene,
                        storyboard=board,
                        duration_delta=_duration_contract_delta(
                            est.total_seconds, request.duration_target_s
                        ),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                log.info("Candidate %d generation failed: %s", i + 1, exc)
                continue
        if not candidates and aspect:
            log.info("Tournament produced no candidates for aspect %s.", aspect)
        return candidates

    async def _render_and_score_candidates(
        self,
        candidates: list[SceneCandidate],
        settings: "AppSettings",
        progress: Callable[[str], None] | None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> list[SceneCandidate]:
        import json as _json

        from aetherlab.services.scene_critic import critique_video

        limit = max(1, min(
            int(getattr(settings, "scene_candidate_concurrency", 2) or 2),
            len(candidates),
        ))
        sem = asyncio.Semaphore(limit)
        frame_count = int(getattr(settings, "visual_critic_keyframes", 6) or 6)

        async def run_one(candidate: SceneCandidate) -> SceneCandidate | None:
            async with sem:
                if progress:
                    progress(f"Draft rendering candidate {candidate.index + 1}")
                # variant isolates this candidate's cloud job/artifact so
                # byte-identical candidates dispatched concurrently never collide.
                kwargs = {"cancel_check": cancel_check} if cancel_check is not None else {}
                draft = await self._render_once(
                    candidate.scene,
                    settings,
                    "l",
                    progress,
                    variant=f"cand{candidate.index}",
                    **kwargs,
                )
                if draft.status != "rendered" or not draft.video_path:
                    return None
                brief = _json.dumps(candidate.storyboard) if candidate.storyboard else "Scene candidate"
                expected_physics = (
                    draft.storyboard.get("physics_expectations", [])
                    if isinstance(draft.storyboard, dict) else []
                )
                crit = await critique_video(
                    draft.video_path,
                    brief,
                    settings,
                    frame_count=frame_count,
                    expected_physics=[str(item) for item in expected_physics],
                )
                if crit.verdict == "skipped":
                    # No vision judgement (keyless/offline). Instead of dropping
                    # the candidate — which would leave the tournament with no
                    # ranking signal and silently collapse to the single path —
                    # score it with the static per-axis proxy so ranking is
                    # deterministic and discriminating.
                    from aetherlab.services.scene_critic import static_quality_estimate

                    crit = static_quality_estimate(draft.code)
                draft.quality_score = float(crit.score or 0.0)
                draft.critique_verdict = str(crit.verdict or "")
                draft.critique_issues = list(crit.issues)
                draft.critique_model = str(crit.model_used or "")
                draft.critique_breakdown = dict(crit.breakdown)
                candidate.scene = draft
                candidate.draft_video_path = draft.video_path
                candidate.score = draft.quality_score
                candidate.verdict = draft.critique_verdict
                candidate.issues = list(draft.critique_issues)
                candidate.breakdown = dict(crit.breakdown)
                return candidate

        results = await asyncio.gather(*(run_one(c) for c in candidates))
        return [r for r in results if r is not None]

    def generate_scene(
        self,
        request: ProblemRequest,
        solver: SolverResult,
        rag: RagResult,
        plan: object | None = None,
    ) -> SceneBundle:
        """Synchronous path — curated component first, else the static template."""
        engine, diagnostics = self.detect_engine()
        class_name = "AetherLabScene"
        composed = self._compose_curated(
            class_name, solver, plan, diagnostics, float(request.duration_target_s),
            problem_prompt=request.prompt,
        )
        if composed is not None:
            return composed
        code = self._build_scene_code(class_name, request, solver, rag)
        try:
            compile(code, "<aetherlab-generated-scene>", "exec")
            status = "compiled"
        except SyntaxError as exc:
            diagnostics.append(f"Generated scene failed to compile: {exc}")
            status = "compile-error"
        return SceneBundle(
            class_name=class_name,
            code=code,
            engine=engine,
            status=status,
            diagnostics=diagnostics,
        )

    def render_scene(
        self,
        scene_bundle: SceneBundle,
        settings: "AppSettings | None" = None,
        quality: str = "l",
        *,
        cancel_check: Callable[[], bool] | None = None,
        cache_lineage: str | None = None,
        partial_animation_range: tuple[int, int] | None = None,
    ) -> SceneBundle:
        """Render the generated scene to an MP4 video using Manim Community.

        Each render runs in its OWN isolated media directory with caching
        disabled, so Manim can never splice a stale partial-movie file from a
        previous/adjacent render into this one — the root of the "sync bug"
        where a regenerated scene came out desynchronized from its code.

        Args:
            quality: Manim quality flag — 'l' (480p), 'm' (720p), 'h' (1080p), 'k' (4K).
        """
        if scene_bundle.status != "compiled":
            scene_bundle.diagnostics.append("Skipping render: scene did not compile.")
            if scene_bundle.video_path and not Path(scene_bundle.video_path).exists():
                scene_bundle.video_path = ""
            return scene_bundle

        manim_cmd = self._find_manim_command()
        if not manim_cmd:
            scene_bundle.diagnostics.append("No Manim binary found; returning code-only.")
            scene_bundle.video_path = ""
            return scene_bundle

        s = settings or self._settings
        data_dir = getattr(s, "data_dir", None)
        scene_bundle.video_path = ""
        scene_bundle.cache_hits = 0

        # ── Isolated per-render workspace (Bug 1) ──
        # A fresh uuid-suffixed dir per render means no two renders ever share
        # Manim's partial-movie cache — the frame-desync bug becomes impossible.
        scene_name = _scene_name(scene_bundle.class_name, scene_bundle.code)
        safe_lineage = (
            cache_lineage
            if cache_lineage and re.fullmatch(r"[a-f0-9]{32}", cache_lineage)
            else ""
        )
        run_dir = (
            _RUNS_DIR / f"repair_{safe_lineage}"
            if safe_lineage
            else _RUNS_DIR / f"{scene_name}_{quality}_{uuid.uuid4().hex[:8]}"
        )
        run_dir.mkdir(parents=True, exist_ok=True)
        media_dir = run_dir / "media"
        scene_file = run_dir / f"{scene_name}.py"
        scene_file.write_text(scene_bundle.code, encoding="utf-8")
        try:
            # Reuse the TeX the preflight compiled for this exact code (Manim
            # reads a manim.cfg next to the scene file).
            from aetherlab.services.scene_preflight import tex_cache_dir

            tex_dir = str(tex_cache_dir(scene_bundle.code)).replace("%", "%%")
            (run_dir / "manim.cfg").write_text(f"[CLI]\ntex_dir = {tex_dir}\n", encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 - a cache is an optimisation only
            log.debug("Shared TeX cache unavailable: %s", exc)
        _prune_old_runs()

        # ── Weight-aware timeout + resource guard (Bug 4) ──
        base_timeout = {"l": 240, "m": 420, "h": 600, "k": 900}.get(quality, 240)
        cost = _estimate_render_cost(scene_bundle.code)
        render_timeout = min(int(base_timeout * cost), 1800)  # hard ceiling 30 min
        tier = _RENDER_TIER
        fps = tier["fps"]
        # A runaway scene (bad run_time → tens of seconds at 4K/60) can wedge the
        # box; halve the frame rate on heavy hi-res renders.
        if cost >= 3.0 and quality in ("h", "k"):
            fps = 30

        log.info(
            "Rendering %s -q%s --fps %d --seed %d (tier %s, cost %.1f, timeout %ds)",
            scene_name, quality, fps, _scene_seed(scene_bundle.code),
            tier["name"], cost, render_timeout,
        )

        # Deterministic RNG per scene: a stable seed derived from the code means
        # a given scene renders identically every time (clean bug-repro), while
        # two tournament candidates — which have *different* code — still get
        # different seeds. So candidates differ by their prompt, never by the
        # dice, and the vision critic scores direction instead of RNG noise.
        seed = _scene_seed(scene_bundle.code)
        renderer_setting = os.getenv("AETHERLAB_MANIM_RENDERER", "cairo").strip().lower()
        renderer = renderer_setting if renderer_setting in {"cairo", "opengl"} else "cairo"
        if renderer_setting not in {"", "cairo", "opengl"}:
            scene_bundle.diagnostics.append(
                f"Unknown AETHERLAB_MANIM_RENDERER={renderer_setting!r}; using Cairo."
            )
        command = _manim_render_command(
            manim_cmd,
            quality=quality,
            fps=fps,
            seed=seed,
            media_dir=media_dir,
            scene_file=scene_file,
            class_name=scene_bundle.class_name,
            renderer=renderer,
            cache_enabled=bool(safe_lineage),
            partial_animation_range=(
                partial_animation_range if safe_lineage else None
            ),
        )

        started = time.time()
        try:
            result = run_process_tree(
                command,
                capture_output=True,
                text=True,
                # Decode Manim's output as UTF-8 regardless of the host locale.
                # A non-UTF-8 Windows console codec (e.g. cp1251) otherwise raises
                # UnicodeDecodeError in subprocess's reader thread on any byte it
                # can't map, failing an otherwise-successful render (BUG-33).
                encoding="utf-8",
                errors="replace",
                timeout=render_timeout,
                cancel_check=cancel_check,
                cwd=str(run_dir),
                **subprocess_kwargs(below_normal=tier["below_normal"]),
            )
            if result.returncode != 0:
                stderr = result.stderr.strip()
                kind = _classify_failure(stderr)
                dump = _dump_render_failure(data_dir, scene_bundle.code, stderr, kind)
                # Keep a generous tail: the repair pass feeds this back to the
                # LLM and needs the actual traceback — chained exceptions and
                # LaTeX logs push the root cause well past a short tail.
                note = f"Manim render failed [{kind}]: {stderr[-8000:]}"
                if dump:
                    note += f"\n(full log: {dump})"
                scene_bundle.diagnostics.append(note)
                scene_bundle.status = "render-error"
                scene_bundle.failure_kind = kind
                return scene_bundle
            if safe_lineage:
                scene_bundle.cache_hits = len(
                    re.findall(r"Using cached data \(hash :", result.stdout or "")
                )
                scene_bundle.diagnostics.append(
                    f"Manim repair cache reused {scene_bundle.cache_hits} play segment(s)."
                )
        except ProcessCancelledError:
            raise
        except subprocess.TimeoutExpired:
            _dump_render_failure(data_dir, scene_bundle.code, "render exceeded time budget", "timeout")
            scene_bundle.diagnostics.append(
                f"Manim render timed out ({render_timeout}s, cost {cost:.1f})."
            )
            scene_bundle.status = "render-timeout"
            scene_bundle.failure_kind = "timeout"
            return scene_bundle
        except Exception as exc:
            scene_bundle.diagnostics.append(f"Manim render error: {exc}")
            scene_bundle.status = "render-error"
            scene_bundle.failure_kind = "spawn"
            return scene_bundle

        # ── Video discovery: THIS render only (Bug 1) ──
        # The media dir is unique to this render, so any mp4 in it is ours;
        # the mtime floor is belt-and-suspenders.
        video_path = _find_video_in(media_dir, scene_bundle.class_name, started)
        if video_path:
            scene_bundle.video_path = str(video_path)
            scene_bundle.status = "rendered"
            scene_bundle.failure_kind = ""
            log.info("Video rendered: %s (%.1f MB)", video_path, video_path.stat().st_size / 1e6)
        else:
            scene_bundle.diagnostics.append("Render succeeded but video file not found.")
            scene_bundle.status = "compiled"

        return scene_bundle

    async def render_scene_with_repair(
        self,
        scene_bundle: SceneBundle,
        settings: "AppSettings | None" = None,
        quality: str = "l",
        max_repairs: int = 2,
        max_revisions: int = 2,
        brief: str = "",
        progress: Callable[[str], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> SceneBundle:
        """Render; repair crashes/timeouts; then (optionally) critique and revise.

        Crash path: LLM scenes occasionally invent Manim kwargs that pass the
        compile check but explode at render time; feeding the traceback back for
        a bounded number of repair rounds converts most into successful renders.
        Quality path: with a vision model configured, the rendered video's
        frames are judged against the storyboard/brief and revised until the
        critic says ship (bounded by max_revisions). Without an API key this is
        exactly render_scene(); without a vision model, repairs-only.

        Hard-scene strategy (Bug 4): the code is validated and repaired at DRAFT
        quality first (cheap, fast), and only promoted to the requested quality
        once it renders. If the final high-quality render fails or times out,
        the draft render is kept as partial success rather than returning
        nothing.
        """
        s = settings or self._settings
        timeline = (
            scene_bundle.storyboard.get("timeline")
            if isinstance(scene_bundle.storyboard, dict)
            else None
        )
        draft_quality = "l"  # validate/repair cheaply here; promote to `quality`

        async def render_once(
            bundle: SceneBundle,
            render_quality: str,
            *,
            partial_animation_range: tuple[int, int] | None = None,
        ) -> SceneBundle:
            kwargs = {"cancel_check": cancel_check} if cancel_check is not None else {}
            return await self._render_once(
                bundle, s, render_quality, progress,
                cache_lineage=cache_lineage,
                partial_animation_range=partial_animation_range,
                **kwargs
            )

        cache_lineage = None
        cache_mode = os.getenv("AETHERLAB_MANIM_REPAIR_CACHE", "").strip().lower()
        render_mode = str(getattr(s, "render_mode", "local") or "local").strip().lower()
        use_local_backend = render_mode == "local"
        if render_mode == "auto":
            threshold = float(getattr(s, "cloud_render_threshold", 3.0) or 3.0)
            use_local_backend = _estimate_render_cost(scene_bundle.code) < threshold
        if cache_mode in {"1", "true", "yes", "on"} and use_local_backend:
            cache_lineage = uuid.uuid4().hex

        # BUG-29: skip the draft render when the bundle already carries a valid
        # one (the tournament renders + critiques the winner as a draft before
        # handing it here). Re-rendering the same code at the same quality was a
        # wasted render on every tournament solve — and every lesson chapter —
        # once the tournament defaulted on (F177). A fresh compiled scene has no
        # video_path and renders normally.
        already_drafted = bool(
            scene_bundle.status == "rendered"
            and scene_bundle.video_path
            and Path(scene_bundle.video_path).exists()
        )
        if not already_drafted:
            # Preflight: run the scene's code in seconds (dry run, 2 fps) and fix
            # runtime crashes / off-screen geometry before paying for a render.
            scene_bundle = await self._preflight_and_repair(scene_bundle, s, timeline)
            scene_bundle = await render_once(scene_bundle, draft_quality)

        learner = None
        if s is not None:
            from aetherlab.services.error_learner import ErrorLearner

            learner = ErrorLearner(s.data_dir / "error_patterns.json")

        repairs = 0
        while (
            scene_bundle.status in {"render-error", "render-timeout"}
            and repairs < max_repairs
            and s is not None
            and s.openai_api_key
        ):
            from aetherlab.services.code_safety import validate_code_safety
            from aetherlab.services.scene_generator import SceneGenerator

            error = scene_bundle.diagnostics[-1] if scene_bundle.diagnostics else "unknown"
            if scene_bundle.status == "render-timeout":
                # Timeouts punish the most ambitious scenes — give the repair
                # model actionable direction instead of dropping the attempt.
                error += (
                    " The scene exceeded the render time limit. Reduce rendering "
                    "load while preserving the visual design: fewer/cheaper "
                    "always_redraw updaters (prefer static mobjects + .animate), "
                    "fewer self.play calls, lower curve sample counts, shorter "
                    "waits. Do NOT strip the scene down to a bare plot."
                )
            if learner is not None:
                # Cross-run learning: curated Manim-CE pitfall hints + a
                # recurrence warning when the same signature keeps appearing.
                hints = learner.hints_for(error)
                learner.record(error)
                if hints:
                    error += "\n\nKnown fixes for this class of error:\n- " + "\n- ".join(hints)
            repairs += 1
            log.info("Attempting render repair %d/%d", repairs, max_repairs)
            try:
                fixed = await SceneGenerator(s).repair(
                    scene_bundle.code,
                    error,
                    scene_bundle.class_name,
                    full_scene=repairs > 1,
                )
                compile(fixed, "<aetherlab-repaired-scene>", "exec")
            except Exception as exc:  # noqa: BLE001
                scene_bundle.diagnostics.append(f"Render repair {repairs} failed: {exc}")
                break
            safe, issues = validate_code_safety(fixed)
            if not safe:
                scene_bundle.diagnostics.append(
                    f"Render repair {repairs} rejected by safety gate: " + "; ".join(issues[:4])
                )
                break
            lint_ok, lint_issues = _blocking_scene_issues(fixed, timeline)
            if not lint_ok:
                # The repair itself introduced a provable render failure —
                # feed the lint report back as the next round's error instead
                # of wasting a render on it.
                scene_bundle.diagnostics.append(
                    f"Render repair {repairs} failed pre-render lint: "
                    + "; ".join(lint_issues[:4])
                )
                continue
            scene_bundle.code = fixed
            scene_bundle.status = "compiled"
            scene_bundle.diagnostics.append(f"Applied render repair {repairs}.")
            scene_bundle = await render_once(scene_bundle, draft_quality)

        # ── Promote the working code to the requested quality (Bug 4) ──
        # The draft rendered; render the final at the target quality. If that
        # fails/times out, keep the draft (partial success) rather than nothing.
        final_quality = draft_quality
        if scene_bundle.status == "rendered" and quality != draft_quality:
            hq = SceneBundle(
                class_name=scene_bundle.class_name,
                code=scene_bundle.code,
                engine=scene_bundle.engine,
                status="compiled",
                diagnostics=list(scene_bundle.diagnostics),
                storyboard=scene_bundle.storyboard,
            )
            hq = await render_once(hq, quality)
            if hq.status == "rendered":
                scene_bundle = hq
                final_quality = quality
            else:
                scene_bundle.diagnostics.append(
                    f"Final {quality} render {hq.status}; keeping draft render (partial success)."
                )

        # ── Perceptual quality loop ──────────────────────────────────────
        # The critic looks at the actual rendered frames and judges them
        # against the storyboard/brief; "revise" verdicts loop an aesthetic
        # rewrite. Entirely optional: no vision model → verdict "skipped".
        if (
            scene_bundle.status == "rendered"
            and s is not None
            and s.vision_model
            and s.openai_api_key
            # The built-in template is a fallback, not an AI scene: critiquing
            # and LLM-revising it spent minutes polishing a placeholder.
            and not scene_bundle.used_fallback
        ):
            import json as _json

            from aetherlab.services.code_safety import validate_code_safety
            from aetherlab.services.scene_critic import critique_video
            from aetherlab.services.scene_generator import SceneGenerator

            generator = SceneGenerator(s)
            board_brief = (
                _json.dumps(scene_bundle.storyboard)
                if scene_bundle.storyboard
                else (brief or "A short cinematic physics explainer scene.")
            )
            configured_revisions = getattr(s, "visual_critic_max_passes", None)
            revision_limit = max(0, int(max_revisions))
            if configured_revisions is not None:
                revision_limit = min(revision_limit, max(0, int(configured_revisions)))
            frame_count = int(getattr(s, "visual_critic_keyframes", 6) or 6)
            expected_physics = [
                str(item) for item in (
                    scene_bundle.storyboard.get("physics_expectations", [])
                    if isinstance(scene_bundle.storyboard, dict) else []
                )
            ]
            timeline = (
                scene_bundle.storyboard.get("timeline", [])
                if isinstance(scene_bundle.storyboard, dict) else []
            )
            beat_centers = [
                (float(event["start_s"]) + float(event["end_s"])) / 2.0
                for event in timeline if isinstance(event, dict)
                and "start_s" in event and "end_s" in event
            ]
            if len(beat_centers) > frame_count:
                beat_centers = [
                    beat_centers[round(i * (len(beat_centers) - 1) / (frame_count - 1))]
                    for i in range(frame_count)
                ] if frame_count > 1 else [beat_centers[len(beat_centers) // 2]]
            # Best critiqued cut so far. A revision is kept only if the critic
            # scores it higher; otherwise the loop stops and ships the better
            # cut. (Live 2026-09-30: two rounds cost ~6 min and scored 4.0 ->
            # 4.0, and the last revision shipped without ever being scored.)
            best: SceneBundle | None = None
            for round_no in range(1, revision_limit + 1):
                crit = await critique_video(
                    scene_bundle.video_path,
                    board_brief,
                    s,
                    frame_count=frame_count,
                    expected_physics=expected_physics,
                    event_times_s=beat_centers or None,
                )
                scene_bundle.quality_score = float(crit.score or 0.0)
                scene_bundle.critique_verdict = str(crit.verdict or "")
                scene_bundle.critique_issues = list(crit.issues)
                scene_bundle.critique_model = str(crit.model_used or "")
                scene_bundle.critique_breakdown = dict(crit.breakdown)
                if crit.verdict == "skipped":
                    break
                scene_bundle.diagnostics.append(
                    f"Visual critique round {round_no}: {crit.verdict} "
                    f"(score {crit.score:.1f})"
                    + (" — " + "; ".join(crit.issues[:3]) if crit.issues else "")
                )
                if best is not None and scene_bundle.quality_score <= best.quality_score:
                    best.diagnostics.append(
                        f"Visual revision {round_no - 1} scored "
                        f"{scene_bundle.quality_score:.1f}, not above "
                        f"{best.quality_score:.1f}; kept the earlier cut and stopped revising."
                    )
                    scene_bundle = best
                    break
                best = scene_bundle
                if not crit.should_revise:
                    break
                try:
                    revised = await generator.revise(
                        scene_bundle.code,
                        "\n".join(crit.issues) or "Improve composition and pacing.",
                        scene_bundle.class_name,
                    )
                except Exception as exc:  # noqa: BLE001
                    scene_bundle.diagnostics.append(
                        f"Visual revision {round_no} failed: {exc}"
                    )
                    break

                static_issues: list[str] = []
                try:
                    compile(revised, "<aetherlab-revised-scene>", "exec")
                except Exception as exc:  # noqa: BLE001
                    static_issues.append(f"compile: {exc}")
                if not static_issues:
                    safe, safety_issues = validate_code_safety(revised)
                    lint_ok, lint_issues = _blocking_scene_issues(revised, timeline)
                    if not safe:
                        static_issues.extend(safety_issues)
                    if not lint_ok:
                        static_issues.extend(lint_issues)
                if static_issues:
                    scene_bundle.diagnostics.append(
                        f"Visual revision {round_no} failed static gates: "
                        + "; ".join(static_issues[:4])
                    )
                    try:
                        revised = await generator.repair(
                            revised,
                            "The visual revision failed before rendering. Fix every "
                            "validation error while preserving the requested aesthetic "
                            "improvements:\n" + "\n".join(static_issues[:8]),
                            scene_bundle.class_name,
                        )
                        compile(revised, "<aetherlab-repaired-visual-revision>", "exec")
                        safe, safety_issues = validate_code_safety(revised)
                        lint_ok, lint_issues = _blocking_scene_issues(revised, timeline)
                        if not safe or not lint_ok:
                            raise ValueError("; ".join([*safety_issues, *lint_issues][:6]))
                        scene_bundle.diagnostics.append(
                            f"Repaired visual revision {round_no} before rendering."
                        )
                    except Exception as exc:  # noqa: BLE001
                        scene_bundle.diagnostics.append(
                            f"Visual revision {round_no} repair failed: {exc}"
                        )
                        break
                # Render the revision as a trial: only adopt it if it still
                # renders — never downgrade a shipped cut to a failed one.
                trial = SceneBundle(
                    class_name=scene_bundle.class_name,
                    code=revised,
                    engine=scene_bundle.engine,
                    status="compiled",
                    diagnostics=list(scene_bundle.diagnostics),
                    storyboard=scene_bundle.storyboard,
                )
                partial_range = None
                partial_mode = os.getenv(
                    "AETHERLAB_MANIM_PARTIAL_REVISIONS", ""
                ).strip().lower()
                if cache_lineage and partial_mode in {"1", "true", "yes", "on"}:
                    partial_range = _animation_range_for_times(
                        revised, crit.problem_times_s
                    )
                if partial_range is not None:
                    partial_preview = await render_once(
                        trial, final_quality, partial_animation_range=partial_range
                    )
                    preview_status = partial_preview.status
                    partial_preview.status = "compiled"
                    partial_preview.video_path = ""
                    partial_preview.failure_kind = ""
                    trial = await render_once(partial_preview, final_quality)
                    trial.diagnostics.append(
                        f"Partial revision pass {partial_range[0]}-{partial_range[1]} "
                        f"({preview_status}); assembled final clip from the repair-lineage cache."
                    )
                else:
                    trial = await render_once(trial, final_quality)
                if trial.status == "rendered":
                    trial.diagnostics.append(f"Applied visual revision {round_no}.")
                    scene_bundle = trial
                else:
                    render_error = (
                        trial.diagnostics[-1]
                        if trial.diagnostics
                        else f"revision render ended with status {trial.status}"
                    )
                    try:
                        repaired = await generator.repair(
                            revised, render_error, scene_bundle.class_name
                        )
                        compile(repaired, "<aetherlab-render-repaired-visual-revision>", "exec")
                        safe, safety_issues = validate_code_safety(repaired)
                        lint_ok, lint_issues = _blocking_scene_issues(repaired, timeline)
                        if not safe or not lint_ok:
                            raise ValueError("; ".join([*safety_issues, *lint_issues][:6]))
                        retry_trial = SceneBundle(
                            class_name=scene_bundle.class_name,
                            code=repaired,
                            engine=scene_bundle.engine,
                            status="compiled",
                            diagnostics=list(scene_bundle.diagnostics),
                            storyboard=scene_bundle.storyboard,
                        )
                        retry_trial = await render_once(retry_trial, final_quality)
                    except Exception as exc:  # noqa: BLE001
                        scene_bundle.diagnostics.append(
                            f"Visual revision {round_no} render repair failed: {exc}"
                        )
                        retry_trial = None
                    if retry_trial is not None and retry_trial.status == "rendered":
                        retry_trial.diagnostics.append(
                            f"Applied repaired visual revision {round_no}."
                        )
                        scene_bundle = retry_trial
                    else:
                        scene_bundle.diagnostics.append(
                            f"Visual revision {round_no} did not render after repair; "
                            "keeping previous cut."
                        )
                        break
            # The last round's revision has not been judged yet: score it once
            # so the shipped cut carries a real score, and never ship it if it
            # is not better than the cut it replaced.
            if best is not None and scene_bundle is not best and scene_bundle.status == "rendered":
                crit = await critique_video(
                    scene_bundle.video_path, board_brief, s,
                    frame_count=frame_count, expected_physics=expected_physics,
                )
                if crit.verdict != "skipped" and float(crit.score or 0.0) <= best.quality_score:
                    best.diagnostics.append(
                        f"Final visual revision scored {float(crit.score or 0.0):.1f}, not "
                        f"above {best.quality_score:.1f}; kept the earlier cut."
                    )
                    scene_bundle = best
                elif crit.verdict != "skipped":
                    scene_bundle.quality_score = float(crit.score or 0.0)
                    scene_bundle.critique_verdict = str(crit.verdict or "")
                    scene_bundle.critique_issues = list(crit.issues)
                    scene_bundle.critique_model = str(crit.model_used or "")
                    scene_bundle.critique_breakdown = dict(crit.breakdown)
                    scene_bundle.diagnostics.append(
                        f"Final visual critique: {crit.verdict} (score {crit.score:.1f})."
                    )

        # ── Narration↔visual sync (manim-bot decision) ───────────────────
        # Derive a voiceover from the FINAL code and fit it to the rendered
        # video (whole-clip sync). Fully optional and fail-soft: disabled, or
        # missing edge-tts/ffmpeg, or any error → the silent render is kept.
        if (
            scene_bundle.status == "rendered"
            and s is not None
            and getattr(s, "narration_enabled", False)
            and scene_bundle.video_path
        ):
            scene_bundle = await self._add_narration(scene_bundle, s, brief)

        if s is not None and scene_bundle.code:
            try:
                from aetherlab.services.render_backend import cloud_job_id, render_fps_for
                from aetherlab.services.render_ledger import RenderJobLedger

                job_id = cloud_job_id(
                    scene_bundle,
                    quality=quality,
                    fps=render_fps_for(scene_bundle.code, quality),
                )
                RenderJobLedger(s.data_dir / "render_ledger.json").metrics(job_id, {
                    "quality_score": scene_bundle.quality_score,
                    "retry_count": sum(
                        1 for message in scene_bundle.diagnostics
                        if "Applied render repair" in message or "Visual revision" in message
                    ),
                    "failure_kind": scene_bundle.failure_kind,
                })
            except Exception as exc:  # noqa: BLE001 - reporting never blocks a render
                log.debug("Could not attach final render metrics: %s", exc)

        return scene_bundle

    async def _preflight_and_repair(
        self, bundle: SceneBundle, s: "AppSettings | None", timeline: object
    ) -> SceneBundle:
        """Dry-run an AI scene before its first render; repair what it finds.

        Fail-soft: the original scene is rendered whenever the preflight cannot
        run or a repair does not verifiably help. Curated and fallback scenes
        are deterministic and tested, so they skip it.
        """
        from aetherlab.services.scene_preflight import (
            beat_drift_lines,
            beat_timings,
            preflight_enabled,
            preflight_scene,
        )

        curated = any("curated component library" in d.lower() for d in bundle.diagnostics)
        if (
            s is None or bundle.status != "compiled" or not bundle.code
            or f"class {bundle.class_name}" not in bundle.code
            or bundle.used_fallback or curated or not preflight_enabled()
        ):
            return bundle
        report = await asyncio.to_thread(preflight_scene, bundle.code, bundle.class_name)
        if not report.ran:
            bundle.diagnostics.append(f"Preflight skipped ({report.note[:200]}).")
            return bundle
        bundle.diagnostics.append(
            f"Preflight ({report.seconds:.0f}s): "
            + ("ran cleanly" if report.ok else "the scene crashed before rendering")
            + (f", measured duration {report.duration_s:.1f}s" if report.ok else "")
            + (f", {len(report.off_frame)} object(s) outside the frame" if report.off_frame else "")
            + "."
        )
        for line in report.off_frame_lines(3):
            bundle.diagnostics.append(line)

        def drift_summary(code: str, checked) -> tuple[float, list[str]]:
            timings = beat_timings(code, checked)
            worst = max((abs(t.drift_s) for t in timings), default=0.0)
            return worst, beat_drift_lines(timings, BEAT_DRIFT_TOLERANCE_S)

        if report.ok:
            timings = beat_timings(bundle.code, report)
            if timings:
                worst, _ = drift_summary(bundle.code, report)
                bundle.diagnostics.append(
                    f"Preflight beat timing: {len(timings)} beats measured, "
                    f"largest drift {worst:.2f}s."
                )
        if not getattr(s, "openai_api_key", None):
            return bundle

        from aetherlab.services.code_safety import validate_code_safety
        from aetherlab.services.scene_generator import SceneGenerator

        generator = SceneGenerator(s)

        async def try_repair(instruction: str, full_scene: bool):
            try:
                fixed = await generator.repair(bundle.code, instruction, bundle.class_name,
                                               full_scene=full_scene)
                compile(fixed, "<aetherlab-preflight-repair>", "exec")
            except Exception as exc:  # noqa: BLE001 - repair is bounded and fail-soft
                return None, f"repair failed: {type(exc).__name__}: {str(exc)[:160]}"
            safe, issues = validate_code_safety(fixed)
            lint_ok, lint_issues = _blocking_scene_issues(fixed, timeline)
            if not safe or not lint_ok:
                return None, "repair failed the static gates: " + "; ".join((issues + lint_issues)[:3])
            checked = await asyncio.to_thread(preflight_scene, fixed, bundle.class_name)
            return (fixed, checked), ""

        if report.crashed:
            error = report.error
            for round_no in range(1, 3):
                result, why = await try_repair(
                    "This scene crashed in a dry run before rendering (same Manim, no frames "
                    "drawn). Fix the cause and keep the visual design, physics and timing:\n"
                    + error[-5000:],
                    full_scene=round_no > 1,
                )
                if result is None:
                    bundle.diagnostics.append(f"Preflight repair {round_no}: {why}")
                    break
                fixed, checked = result
                if checked.ran and checked.ok:
                    bundle.code = fixed
                    bundle.diagnostics.append(
                        f"Preflight repair {round_no} fixed the crash before rendering "
                        f"(measured duration {checked.duration_s:.1f}s)."
                    )
                    return bundle
                error = checked.error or error
                bundle.diagnostics.append(f"Preflight repair {round_no} still crashes.")
            bundle.diagnostics.append(
                "Preflight crash not repaired; rendering the original (render repair follows)."
            )
            return bundle

        latest = report
        if report.off_frame:
            result, why = await try_repair(
                "A dry run of this scene found objects outside the camera frame (x about "
                "-7.1..7.1, y about -4.0..4.0). Keep everything visible: fit each axes' "
                "x_range/y_range to the values actually plotted (or normalise the data), "
                "move labels and readouts inside the frame, and keep the visual design, "
                "physics and timing:\n" + "\n".join(report.off_frame_lines(8)),
                full_scene=False,
            )
            if result is None:
                bundle.diagnostics.append(f"Preflight layout repair: {why}")
                return bundle
            fixed, checked = result
            if checked.ran and checked.ok and len(checked.off_frame) < len(report.off_frame):
                bundle.code = fixed
                latest = checked
                bundle.diagnostics.append(
                    f"Preflight layout repair kept: objects outside the frame "
                    f"{len(report.off_frame)} -> {len(checked.off_frame)}."
                )
            else:
                bundle.diagnostics.append(
                    "Preflight layout repair did not reduce off-frame objects; kept the original."
                )

        # Narration is placed at each beat's planned start, so a late or early
        # beat is a sync bug the viewer hears. Fix it before paying for a render.
        # The total length matters too: a long-video segment must fill its slot
        # (live 2026-10-02: 15.40 s for 13.76 s, then 13.17 s for 14.24 s,
        # each stopping the lesson), and the dry run measures it exactly.
        planned_end = 0.0
        if isinstance(timeline, list) and timeline and isinstance(timeline[-1], dict):
            try:
                planned_end = float(timeline[-1].get("end_s") or 0.0)
            except (TypeError, ValueError):
                planned_end = 0.0
        length_tolerance = max(1.0, planned_end * 0.05)
        narrated = bool(getattr(s, "narration_enabled", False))

        def timing_score(code: str, checked) -> tuple[float, list[str]]:
            worst, lines = drift_summary(code, checked)
            score = worst if narrated else 0.0
            if planned_end > 0:
                off = checked.duration_s - planned_end
                if abs(off) > length_tolerance:
                    lines = lines + [
                        f"[PREFLIGHT:DURATION] the scene runs {checked.duration_s:.2f}s but its "
                        f"schedule ends at {planned_end:.2f}s ({off:+.2f}s)."
                    ]
                score = max(score, abs(off) if abs(off) > length_tolerance else 0.0)
            return score, (lines if narrated else [line for line in lines if "DURATION" in line])

        score, timing_lines = timing_score(bundle.code, latest)
        if timing_lines:
            result, why = await try_repair(
                "A dry run measured this scene's timing. The narration for every beat starts "
                "exactly at the time in its # BEAT marker, and the scene must end when its "
                "schedule ends. Adjust run_time and wait() values (do not move or edit the "
                "# BEAT markers) so each beat starts at its marker time and the total length "
                "matches the schedule. Keep the visual design and physics:\n"
                + "\n".join(timing_lines),
                full_scene=False,
            )
            if result is None:
                bundle.diagnostics.append(f"Preflight timing repair: {why}")
                return bundle
            fixed, checked = result
            new_score = timing_score(fixed, checked)[0] if checked.ran and checked.ok else score
            if (
                checked.ran and checked.ok and new_score < score
                and len(checked.off_frame) <= len(latest.off_frame)
            ):
                bundle.code = fixed
                bundle.diagnostics.append(
                    f"Preflight timing repair kept: worst timing error {score:.2f}s -> {new_score:.2f}s."
                )
            else:
                bundle.diagnostics.append(
                    f"Preflight timing repair did not reduce the timing error ({score:.2f}s); kept the original."
                )
        return bundle

    async def _render_once(
        self,
        scene_bundle: SceneBundle,
        settings: "AppSettings | None",
        quality: str,
        progress: Callable[[str], None] | None = None,
        variant: str = "",
        cancel_check: Callable[[], bool] | None = None,
        cache_lineage: str | None = None,
        partial_animation_range: tuple[int, int] | None = None,
    ) -> SceneBundle:
        """One render attempt through the selected backend, with local fallback.

        ``variant`` isolates concurrent tournament candidates on the cloud
        backend so byte-identical candidate code cannot collide on the same
        job id / artifact (see render_backend.cloud_job_id). Empty for the
        normal single-scene path, which keeps its content-addressed cloud cache.
        """
        s = settings or self._settings
        if s is None:
            return self.render_scene(
                scene_bundle, settings, quality, cancel_check=cancel_check,
                cache_lineage=cache_lineage,
                partial_animation_range=partial_animation_range,
            )
        from aetherlab.services.render_backend import (
            CLOUD_UNAVAILABLE,
            LocalRenderBackend,
            render_timeout_for,
            select_backend,
        )

        backend = select_backend(s, scene_bundle.code, quality)
        timeout = render_timeout_for(scene_bundle.code, quality, s)
        total_started = time.monotonic()
        local_started = total_started
        cancel_kwargs = (
            {"cancel_check": cancel_check} if cancel_check is not None else {}
        )
        from aetherlab.services.render_backend import cloud_job_id, render_fps_for
        from aetherlab.services.render_ledger import RenderJobLedger

        if backend.name == "local":
            jid = cloud_job_id(
                scene_bundle, quality=quality,
                fps=render_fps_for(scene_bundle.code, quality), variant=variant,
            )
            ledger = RenderJobLedger(s.data_dir / "render_ledger.json")
            ledger.start(
                job_id=jid, scene_class=scene_bundle.class_name, quality=quality,
                fps=render_fps_for(scene_bundle.code, quality), backend="local",
            )
        else:
            jid = cloud_job_id(
                scene_bundle, quality=quality,
                fps=render_fps_for(scene_bundle.code, quality), variant=variant,
            )
            ledger = RenderJobLedger(s.data_dir / "render_ledger.json")

        def record_render_metrics(result: SceneBundle, backend_name: str, wall: float) -> None:
            metrics = {
                "backend": backend_name,
                "manim_renderer": os.getenv("AETHERLAB_MANIM_RENDERER", "cairo").strip().lower()
                if backend_name in {"local", "local_fallback"}
                else "cairo",
                "repair_cache": bool(cache_lineage)
                if backend_name in {"local", "local_fallback"}
                else False,
                "cache_hits": int(result.cache_hits or 0),
                "cache_hit": bool(result.cache_hits),
                "total_seconds": time.monotonic() - total_started,
                "retry_count": sum(
                    1 for message in result.diagnostics
                    if "Applied render repair" in message or "Visual revision" in message
                ),
                "quality_score": result.quality_score,
                "critic_model": result.critique_model,
                "failure_kind": result.failure_kind,
            }
            if result.narration_sync:
                metrics.update({
                    "narration_max_boundary_overrun_s": float(
                        result.narration_sync.get("max_boundary_overrun_s", 0.0) or 0.0
                    ),
                    "narration_max_rate_adjustment_pct": int(
                        result.narration_sync.get("max_rate_adjustment_pct", 0) or 0
                    ),
                    "narration_timeline_scale": float(
                        result.narration_sync.get("timeline_scale", 1.0) or 1.0
                    ),
                })
            if backend_name in {"local", "local_fallback"}:
                # For a cloud job the runner reports its own render time
                # (AETHERLAB_RENDER_WALL_SECONDS); the local clock here also
                # counts upload, queue and polling, so it must not overwrite it.
                metrics["render_wall_seconds"] = wall
                try:
                    from importlib.metadata import version

                    metrics["local_manim_version"] = version("manim")
                except Exception:  # noqa: BLE001 - telemetry is optional
                    pass
            ledger.metrics(jid, {
                **metrics,
            })

        rendered = await backend.render(
            scene_bundle,
            quality=quality,
            settings=s,
            timeout=timeout,
            progress=progress,
            variant=variant,
            cache_lineage=cache_lineage,
            partial_animation_range=partial_animation_range,
            **cancel_kwargs,
        )
        if rendered.status != CLOUD_UNAVAILABLE:
            if backend.name == "local":
                record_render_metrics(rendered, "local", time.monotonic() - local_started)
                if rendered.status == "rendered":
                    ledger.finish(jid, "rendered", rendered.video_path)
                elif rendered.status in {"render-error", "render-timeout"}:
                    ledger.failure(jid, rendered.diagnostics[-1] if rendered.diagnostics else "local render failed", kind=rendered.failure_kind)
            else:
                record_render_metrics(rendered, "github_actions", time.monotonic() - local_started)
            return rendered
        if str(getattr(s, "render_mode", "local") or "local").lower() == "cloud":
            # An explicit cloud choice commonly means the local machine cannot
            # handle this scene. Preserve that choice when the remote backend
            # is unavailable or times out; Auto mode retains its local fallback.
            if progress:
                try:
                    progress("Cloud render unavailable; cloud-only mode selected")
                except Exception:  # noqa: BLE001
                    pass
            record_render_metrics(rendered, "github_actions", time.monotonic() - local_started)
            return rendered
        # Cloud is optional. Restore the compiled status before handing the same
        # bundle to local rendering in Auto mode; the diagnostic stays so UI/tests
        # can report the fallback without poisoning the render guard.
        rendered.status = "compiled"
        rendered.failure_kind = ""
        if progress:
            try:
                progress("Cloud render unavailable; rendering locally")
            except Exception:  # noqa: BLE001
                pass
        local_started = time.monotonic()
        local = await LocalRenderBackend().render(
            rendered,
            quality=quality,
            settings=s,
            timeout=timeout,
            progress=progress,
            cache_lineage=cache_lineage,
            partial_animation_range=partial_animation_range,
            **cancel_kwargs,
        )
        if local.status == "rendered":
            local.diagnostics.append("Cloud render unavailable; rendered locally.")
        # Ledger: record the local fallback against the same cloud job id so the
        # dashboard shows the whole story (cloud attempt -> local fallback).
        try:
            reason = next(
                (d for d in reversed(rendered.diagnostics) if "unavailable" in d.lower()),
                "Cloud render unavailable; rendered locally.",
            )
            RenderJobLedger(s.data_dir / "render_ledger.json").fallback(
                jid, reason, local.video_path if local.status == "rendered" else ""
            )
            record_render_metrics(local, "local_fallback", time.monotonic() - local_started)
        except Exception as exc:  # noqa: BLE001 — observability must never break a render
            log.info("Could not record fallback ledger (%s).", exc)
        return local

    async def _add_narration(
        self, scene_bundle: SceneBundle, s: "AppSettings", brief: str
    ) -> SceneBundle:
        """Synthesize a fit-to-video voiceover and swap it onto the bundle.

        The silent render is preserved on silent_video_path; any failure leaves
        the bundle exactly as it was (silent)."""
        from aetherlab.services import voiceover

        narration_storyboard = None
        try:
            from aetherlab.services.scene_specification import storyboard_from_scene_spec

            narration_storyboard = storyboard_from_scene_spec(scene_bundle.scene_spec)
        except Exception:  # noqa: BLE001 - legacy bundles keep using their storyboard
            pass
        if narration_storyboard is None:
            narration_storyboard = scene_bundle.storyboard
        scene_bundle.narration_text = voiceover.storyboard_narration_script(narration_storyboard)
        if not voiceover.narration_available():
            scene_bundle.diagnostics.append(
                "Narration enabled but edge-tts/ffmpeg unavailable; kept silent video."
            )
            return scene_bundle
        try:
            timed_cues = voiceover.storyboard_timed_narration_segments(
                narration_storyboard
            )
            if timed_cues:
                beat_script = "\n".join(item["text"] for item in timed_cues)
                # Voice-first boards carry the voice, rate and clip cache their
                # windows were measured with; reuse them so every line fits.
                speech = {}
                for board in (narration_storyboard, scene_bundle.storyboard):
                    if isinstance(board, dict) and isinstance(board.get("speech"), dict):
                        speech = board["speech"]
                        break
                aligned = await voiceover.add_timed_beat_voiceover(
                    Path(scene_bundle.video_path),
                    narration_storyboard,
                    Path(s.data_dir) / "narration",
                    voice=str(speech.get("voice") or s.tts_voice),
                    rate=str(speech.get("rate") or s.tts_rate),
                    speech_cache_dir=Path(speech["cache_dir"]) if speech.get("cache_dir") else None,
                )
                if aligned:
                    scene_bundle.narration_text = beat_script
                    scene_bundle.silent_video_path = scene_bundle.video_path
                    scene_bundle.video_path = aligned["video_path"]
                    scene_bundle.subtitle_path = aligned["subtitle_path"]
                    scene_bundle.narration_sync = aligned["sync"]
                    if isinstance(scene_bundle.scene_spec, dict):
                        narration_spec = scene_bundle.scene_spec.setdefault("narration", {})
                        if isinstance(narration_spec, dict):
                            narration_spec["text"] = beat_script
                            narration_spec["sync"] = aligned["sync"]
                            narration_spec["subtitle_path"] = aligned["subtitle_path"]
                    scene_bundle.diagnostics.append(
                        "Added beat-timed narration and an aligned subtitle sidecar."
                    )
                    return scene_bundle
                scene_bundle.diagnostics.append(
                    "Beat narration did not fit its scheduled windows; using whole-clip fit."
                )

            script = voiceover.storyboard_narration_script(narration_storyboard)
            beat_timing = voiceover.storyboard_narration_timing(narration_storyboard)
            target = voiceover.storyboard_target_seconds(narration_storyboard)
            narration = script
            if s.openai_api_key:
                try:
                    narration = await SceneGenerator(s).narrate(
                        brief or "physics animation", scene_bundle.code, script, target,
                        beat_timing=beat_timing,
                    ) or script
                except Exception as exc:  # noqa: BLE001
                    scene_bundle.diagnostics.append(
                        f"Narration script gen failed ({exc}); using storyboard lines."
                    )
            if not narration or not narration.strip():
                scene_bundle.diagnostics.append("No narration text available; kept silent video.")
                return scene_bundle
            scene_bundle.narration_text = narration
            narrated = await voiceover.add_voiceover(
                Path(scene_bundle.video_path),
                narration,
                Path(s.data_dir) / "narration",
                voice=s.tts_voice,
                rate=s.tts_rate,
                fit_to_video=True,
            )
            if narrated:
                scene_bundle.silent_video_path = scene_bundle.video_path
                scene_bundle.video_path = str(narrated)
                scene_bundle.diagnostics.append("Added fit-to-video narration.")
            else:
                scene_bundle.diagnostics.append("Narration synthesis failed; kept silent video.")
        except Exception as exc:  # noqa: BLE001 — never break a good render
            scene_bundle.diagnostics.append(f"Narration error ({exc}); kept silent video.")
        return scene_bundle

    def detect_engine(self) -> tuple[str, list[str]]:
        diagnostics: list[str] = []
        # Generated scenes and rendering both target Manim Community (`python -m manim`),
        # so report it first when available — the label must match what actually runs.
        if find_spec("manim"):
            return "manim-community", diagnostics
        if find_spec("manimlib"):
            diagnostics.append("manim (Community) is not importable; only ManimGL is available.")
            return "manimgl", diagnostics
        diagnostics.append("Neither manim nor manimlib is importable.")
        return "generated-only", diagnostics

    def _find_manim_command(self) -> list[str] | None:
        """Find the manim command as a list suitable for subprocess.run.

        Dev installs prefer `python -m manim` (avoids cross-Python-version
        issues). In a PyInstaller bundle sys.executable is aetherlab.exe and
        `-m` means nothing — the exe instead relays `--manim ...` straight to
        Manim's CLI (see __main__.main), preserving subprocess isolation.
        """
        import sys

        if find_spec("manim"):
            if getattr(sys, "frozen", False):
                return [sys.executable, "--manim"]
            return [sys.executable, "-m", "manim"]
        manim_path = shutil.which("manim")
        if manim_path:
            return [manim_path]
        return None

    def _build_scene_code(
        self,
        class_name: str,
        request: ProblemRequest,
        solver: SolverResult,
        rag: RagResult,
        aspect: str = "full",
    ) -> str:
        """Deterministic domain-aware fallback (services/scene_templates).

        Chooses a pendulum/orbit/wave/oscillator visualization matching the
        problem instead of one generic damped-wave plot, themed to the app
        palette when the UI has persisted one. ``aspect`` varies the
        composition/pacing so lesson chapters sharing a domain look distinct.
        """
        from aetherlab.services.scene_templates import (
            build_scene,
            detect_domain,
            load_scene_palette,
        )

        domain = detect_domain(solver.keywords, solver.variables)
        palette = load_scene_palette(self._settings.data_dir if self._settings else None)
        return build_scene(
            class_name=class_name,
            domain=domain,
            title=_shorten(request.normalized_prompt(), 70),
            summary=_shorten(solver.summary, 120),
            steps=[_shorten(step, 82) for step in solver.derivation_steps[:4]],
            variables=solver.variables,
            palette=palette,
            aspect=aspect,
        )


def _scene_name(class_name: str, code: str = "") -> str:
    """Generate a stable, per-scene name.

    Including a short hash of the code keeps the name stable for identical
    scenes (so caches/frames are reused) while preventing different prompts
    from colliding in the same render directory.
    """
    if code:
        digest = hashlib.sha256(code.encode("utf-8")).hexdigest()[:10]
        return f"scene_{class_name}_{digest}"
    return f"scene_{class_name}"


def _construct_definition_line(code: str) -> int:
    """Find construct() so bounded repairs can edit only the scene method."""
    match = re.search(r"(?m)^\s*def\s+construct\s*\(", code)
    return code.count("\n", 0, match.start()) + 1 if match else 1


def _scene_seed(code: str) -> int:
    """A stable, non-negative 31-bit RNG seed derived from the scene code.

    Same code → same seed (deterministic renders); different code → different
    seed (distinct tournament candidates). Bounded to Manim/Click's INTEGER
    range so ``--seed`` never overflows.
    """
    digest = hashlib.sha256((code or "").encode("utf-8")).hexdigest()[:8]
    return int(digest, 16) % (2**31 - 1)


def _manim_render_command(
    manim_cmd: list[str],
    *,
    quality: str,
    fps: int,
    seed: int,
    media_dir: Path,
    scene_file: Path,
    class_name: str,
    renderer: str = "cairo",
    cache_enabled: bool = False,
    partial_animation_range: tuple[int, int] | None = None,
) -> list[str]:
    """Build a Manim CLI call; partial rendering requires lineage-local cache."""
    selected_renderer = renderer if renderer in {"cairo", "opengl"} else "cairo"
    command = [
        *manim_cmd,
        "render",
        f"-q{quality}",
        "--fps",
        str(fps),
        "--seed",
        str(seed),
        "--renderer",
        selected_renderer,
    ]
    if selected_renderer == "opengl":
        # The OpenGL renderer only encodes a file when this explicit flag is set.
        command.append("--write_to_movie")
    if not cache_enabled:
        # Isolated per-render directories plus disabled caching keep stale
        # partial movies out of ordinary renders. Only a UUID repair lineage
        # opts into Manim's content-hashed partial-movie reuse.
        command.append("--disable_caching")
    elif partial_animation_range is not None:
        start, end = partial_animation_range
        if isinstance(start, int) and isinstance(end, int) and 0 <= start <= end:
            command.extend(["-n", f"{start},{end}"])
    command.extend([
        "--media_dir", str(media_dir), str(scene_file), class_name,
    ])
    return command


def _animation_range_for_times(
    code: str, timestamps_s: list[float]
) -> tuple[int, int] | None:
    """Map critic timestamps to conservative top-level Scene.play indices.

    Dynamic branches, loops, nested calls, and non-literal timing are treated as
    ambiguous; in those cases the caller does a normal lineage-cached render.
    """
    if not timestamps_s:
        return None
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    construct = next((
        method
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        for method in node.body
        if isinstance(method, ast.FunctionDef) and method.name == "construct"
    ), None)
    if construct is None:
        return None

    def is_timed_call(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"play", "wait"}
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
        )

    events: list[tuple[ast.Call, float]] = []
    for statement in construct.body:
        direct = (
            statement.value
            if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call)
            else None
        )
        if direct is not None and is_timed_call(direct):
            call = direct
            duration: float | None = 1.0
            if call.func.attr == "play":
                run_time = next((kw.value for kw in call.keywords if kw.arg == "run_time"), None)
                if run_time is not None:
                    duration = (
                        float(run_time.value)
                        if isinstance(run_time, ast.Constant)
                        and isinstance(run_time.value, (int, float))
                        else None
                    )
            else:
                wait_value = (
                    call.args[0] if call.args else
                    next((kw.value for kw in call.keywords if kw.arg == "duration"), None)
                )
                if wait_value is not None:
                    duration = (
                        float(wait_value.value)
                        if isinstance(wait_value, ast.Constant)
                        and isinstance(wait_value.value, (int, float))
                        else None
                    )
            if duration is None or duration <= 0:
                return None
            events.append((call, duration))
        elif any(is_timed_call(node) for node in ast.walk(statement)):
            return None
    if not events:
        return None

    located: list[int] = []
    for timestamp in timestamps_s:
        try:
            time_s = max(0.0, float(timestamp))
        except (TypeError, ValueError):
            return None
        elapsed = 0.0
        index = len(events) - 1
        for candidate, (_call, duration) in enumerate(events):
            if time_s <= elapsed + duration or candidate == len(events) - 1:
                index = candidate
                break
            elapsed += duration
        located.append(index)
    start = max(0, min(located) - 1)
    end = min(len(events) - 1, max(located) + 1)
    return start, end


def _clean_old_renders(scene_name: str) -> None:
    """Legacy no-conflict cleanup (kept for API compatibility).

    Renders now use isolated per-run dirs (_RUNS_DIR), so there is no shared
    media tree to sweep; this only tidies the pre-isolation layout if present.
    """
    media_dir = _RENDER_DIR / "media" / "videos" / scene_name
    if media_dir.exists():
        shutil.rmtree(media_dir, ignore_errors=True)


def _find_video(scene_name: str) -> Path | None:
    """Legacy finder for the pre-isolation media layout (kept for API compat)."""
    videos_dir = _RENDER_DIR / "media" / "videos" / scene_name
    if not videos_dir.exists():
        return None
    mp4s = list(videos_dir.rglob("*.mp4"))
    if mp4s:
        return max(mp4s, key=lambda p: p.stat().st_mtime)
    return None


def _find_video_in(media_dir: Path, class_name: str, since: float) -> Path | None:
    """Return THIS render's MP4 from its isolated media dir.

    Because ``media_dir`` is unique to this render, any mp4 under it belongs to
    this render; the mtime floor guards against a fluke stale file. Prefer the
    file named after the scene class, else the largest (the assembled movie).
    """
    if not media_dir.exists():
        return None
    fresh = [p for p in media_dir.rglob("*.mp4") if p.stat().st_mtime >= since - 2.0]
    mp4s = fresh or list(media_dir.rglob("*.mp4"))
    if not mp4s:
        return None
    named = [p for p in mp4s if p.stem == class_name]
    if named:
        return max(named, key=lambda p: p.stat().st_mtime)
    return max(mp4s, key=lambda p: p.stat().st_size)


def _prune_old_runs(keep: int = _MAX_KEPT_RUNS) -> None:
    """LRU-prune isolated run dirs so temp doesn't grow without bound.

    A pruned video that a cached SceneBundle still points at is handled by the
    pipeline's existing 'video missing → re-render' path, so pruning is safe.
    """
    try:
        if not _RUNS_DIR.exists():
            return
        runs = sorted(
            (p for p in _RUNS_DIR.iterdir() if p.is_dir()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for stale in runs[keep:]:
            shutil.rmtree(stale, ignore_errors=True)
    except Exception:  # noqa: BLE001 — housekeeping must never break a render
        pass


def _estimate_render_cost(code: str) -> float:
    """Rough render-cost multiplier (1.0 = baseline 15s scene).

    Heavier scenes (longer, many updaters, 3D/field mobjects) get proportionally
    more render time before we call a timeout, so ambition isn't punished.
    Capped so a pathological estimate can't grant an unbounded budget.
    """
    try:
        from aetherlab.services.scene_validation import estimate_duration

        duration = estimate_duration(code).total_seconds
    except Exception:  # noqa: BLE001
        duration = 15.0
    updaters = code.count("always_redraw") + code.count("add_updater")
    plays = code.count("self.play")
    heavy = sum(
        code.count(m)
        for m in ("Surface", "ThreeDScene", "VectorField", "StreamLines",
                  "ParametricSurface", "ImplicitFunction", "MoveAlongPath")
    )
    cost = max(1.0, duration / 15.0) + 0.15 * updaters + 0.04 * plays + 0.5 * heavy
    return min(cost, 5.0)


# Layout findings that trigger a bounded layout repair before rendering.
# Voice and picture drift apart audibly past about half a second.
BEAT_DRIFT_TOLERANCE_S = 0.5

_LAYOUT_BLOCKERS = ("[HYGIENE:OVERLAP]", "[HYGIENE:REDRAW_POSITION]")
_ADVISORY_ISSUE_PREFIXES = ("[TIMING:", "[HYGIENE:", "[PERF:", "[MANIM:UPDATER_ANIMATE]")


# Cloud render budget findings stay blocking: an over-budget scene in Cloud
# mode can run past the remote timeout, and cloud-only mode then has no video.
_CLOUD_BUDGET_PREFIXES = ("[PERF:CLOUD_COST]", "[PERF:PLAY_BUDGET]")


def _is_advisory_issue(issue: str) -> bool:
    """A quality finding (timing, layout) rather than a render crash.

    These drive repair rounds, but a scene carrying only these still answers
    the question and is shipped over the generic template when repair fails.
    """
    text = str(issue)
    return text.startswith(_ADVISORY_ISSUE_PREFIXES) and not text.startswith(_CLOUD_BUDGET_PREFIXES)


def _blocking_scene_issues(code: str, timeline: object) -> tuple[bool, list[str]]:
    """validate_scene for a repair/revision of an already-accepted scene.

    Only render-crash findings block. Advisory timing/layout findings were
    already tolerated on the original, so rejecting a crash fix for them turned
    a repairable LaTeX error into a failed render (live, 2026-09-30).
    """
    from aetherlab.services.scene_validation import validate_scene

    _ok, issues = validate_scene(code, require_motion=True, timeline=timeline)
    blocking = [issue for issue in issues if not _is_advisory_issue(issue)]
    return not blocking, blocking


def _estimate_misses_target(estimate: object, target_seconds: float) -> bool:
    """True when a static duration estimate *provably* misses the target window.

    An estimate carrying notes (loops, non-literal timing, LaggedStart/
    AnimationGroup without run_time) is an approximation; rejecting a scene on
    it discarded correctly timed AI scenes, so those estimates stay advisory.
    """
    if not getattr(estimate, "exact", True):
        return False
    return _duration_contract_delta(
        getattr(estimate, "total_seconds", 0.0), target_seconds
    ) > 0


def _duration_contract_delta(
    seconds: float, target_seconds: float = 30.0, tolerance: float = 0.2
) -> float:
    """Distance outside the requested duration's tolerance window, in seconds."""
    try:
        value = float(seconds)
        target = float(target_seconds)
        tolerance = max(0.0, float(tolerance))
    except (TypeError, ValueError):
        return 9999.0
    if not math.isfinite(value) or not math.isfinite(target) or target <= 0:
        return 9999.0
    lower = target * (1.0 - tolerance)
    upper = target * (1.0 + tolerance)
    if lower <= value <= upper:
        return 0.0
    return min(abs(value - lower), abs(value - upper))


_FAILURE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    # Specific LaTeX failure text only: "dvisvgm" appears in every successful
    # MathTex log line, so a bare "dvi" marker labelled any crash in a scene
    # with math as "latex".
    ("latex", ("undefined control sequence", "latex error", "! latex",
               "latex compilation error", "missing $ inserted", "emergency stop",
               "tex error", "xelatex error")),
    ("ffmpeg", ("ffmpeg", "avconv", "libx264", "codec")),
    ("oom", ("memoryerror", "out of memory", "cannot allocate", "killed", "oom")),
    ("hallucinated-api", ("nameerror", "attributeerror", "has no attribute",
                          "unexpected keyword argument", "is not defined",
                          "typeerror", "importerror")),
    ("invalid-value", ("valueerror",)),
)


def _classify_failure(stderr: str) -> str:
    """Bucket a render stderr into a failure class for repair + metrics."""
    low = (stderr or "").lower()
    # The raised exception is at the end of the log; classify that first so
    # earlier INFO noise (dvisvgm, ffmpeg banners) cannot decide the class.
    for text in (low[-1200:], low):
        for kind, markers in _FAILURE_PATTERNS:
            if any(m in text for m in markers):
                return kind
    return "unknown"


def _dump_render_failure(data_dir, code: str, stderr: str, kind: str) -> Path | None:
    """Persist the failing scene + full stderr so any render failure is
    reproducible from disk. Best-effort; never raises into the render path."""
    try:
        base = Path(data_dir) if data_dir else _RENDER_DIR
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:4]
        dump = base / "logs" / "renders" / f"{stamp}_{kind}"
        dump.mkdir(parents=True, exist_ok=True)
        (dump / "scene.py").write_text(code, encoding="utf-8")
        (dump / "stderr.txt").write_text(stderr or "", encoding="utf-8")
        return dump
    except Exception:  # noqa: BLE001
        return None


def _shorten(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def sanitize_scene_name(text: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", text.title())
    return "".join(parts) or "AetherLabScene"
