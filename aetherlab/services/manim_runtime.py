"""ManimGL/Community scene generation, rendering, and validation."""

from __future__ import annotations

import asyncio
import hashlib
import logging
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
        + min(duration / 25.0, 1.0) * 0.2
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

        composed = self._compose_curated(class_name, solver, plan, diagnostics)
        if composed is not None:
            return composed

        if s and s.openai_api_key:
            from aetherlab.services.code_safety import validate_code_safety
            from aetherlab.services.scene_validation import (
                estimate_duration,
                scene_hygiene_warnings,
                validate_scene,
            )

            generator = SceneGenerator(s)
            for attempt in range(max_retries + 1):
                code = await generator.generate(request, solver, rag, class_name)
                try:
                    compile(code, "<aetherlab-generated-scene>", "exec")
                except SyntaxError as exc:
                    diagnostics.append(f"Attempt {attempt + 1}: scene failed to compile: {exc}")
                    continue
                # Fail-closed safety gate: generated scenes run with full
                # interpreter privileges in the render subprocess.
                safe, issues = validate_code_safety(code)
                if not safe:
                    diagnostics.append(
                        f"Attempt {attempt + 1}: scene failed the safety gate: "
                        + "; ".join(issues[:4])
                    )
                    continue
                # Static pre-render lint: hallucinated names, provably-bad
                # kwargs, structurally broken LaTeX. Catching these here turns
                # a render crash + repair round into a fresh generation.
                lint_ok, lint_issues = validate_scene(code, require_motion=True)
                if not lint_ok:
                    diagnostics.append(
                        f"Attempt {attempt + 1}: pre-render lint failed: "
                        + "; ".join(lint_issues[:4])
                    )
                    continue
                if attempt > 0:
                    diagnostics.append(f"Scene succeeded on retry {attempt}.")
                est = estimate_duration(code)
                diagnostics.append(
                    f"Estimated duration ~{est.total_seconds:.0f}s "
                    f"({est.play_calls} beats, {est.wait_calls} waits)."
                )
                hygiene = scene_hygiene_warnings(code)
                if hygiene:
                    diagnostics.append("Scene hygiene warnings: " + "; ".join(hygiene[:4]))
                return SceneBundle(
                    class_name=class_name,
                    code=code,
                    engine=engine,
                    status="compiled",
                    diagnostics=diagnostics,
                    # Carried so the visual critic can judge the render
                    # against the director's locked treatment.
                    storyboard=generator._last_storyboard,
                )
            # All retries exhausted — fall back to static template
            diagnostics.append("All LLM attempts failed; using deterministic fallback.")
            code = self._build_scene_code(class_name, request, solver, rag, aspect)
        else:
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
            diagnostics=diagnostics,
        )

    def _compose_curated(
        self, class_name: str, solver: SolverResult, plan: object | None, diagnostics: list[str]
    ) -> SceneBundle | None:
        """Build a scene from the curated component library, if one fits."""
        try:
            from aetherlab.services.scene_components import compose_scene_code

            code = compose_scene_code(class_name, solver, plan)
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
                lint_ok, lint_issues = validate_scene(code, require_motion=True)
                if not lint_ok:
                    log.info("Candidate %d rejected by scene lint: %s", i + 1, lint_issues[:3])
                    continue
                est = estimate_duration(code)
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
                        duration_delta=_duration_contract_delta(est.total_seconds),
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
                crit = await critique_video(draft.video_path, brief, settings, frame_count=frame_count)
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
        composed = self._compose_curated(class_name, solver, plan, diagnostics)
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

        # ── Isolated per-render workspace (Bug 1) ──
        # A fresh uuid-suffixed dir per render means no two renders ever share
        # Manim's partial-movie cache — the frame-desync bug becomes impossible.
        scene_name = _scene_name(scene_bundle.class_name, scene_bundle.code)
        run_dir = _RUNS_DIR / f"{scene_name}_{quality}_{uuid.uuid4().hex[:8]}"
        run_dir.mkdir(parents=True, exist_ok=True)
        media_dir = run_dir / "media"
        scene_file = run_dir / f"{scene_name}.py"
        scene_file.write_text(scene_bundle.code, encoding="utf-8")
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
            "Rendering %s -q%s --fps %d (tier %s, cost %.1f, timeout %ds)",
            scene_name, quality, fps, tier["name"], cost, render_timeout,
        )

        started = time.time()
        try:
            result = run_process_tree(
                [
                    *manim_cmd, "render", f"-q{quality}",
                    "--fps", str(fps),
                    # Correctness over speed: never reuse a cached partial movie.
                    "--disable_caching",
                    "--media_dir", str(media_dir),
                    str(scene_file), scene_bundle.class_name,
                ],
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
        draft_quality = "l"  # validate/repair cheaply here; promote to `quality`

        async def render_once(bundle: SceneBundle, render_quality: str) -> SceneBundle:
            kwargs = {"cancel_check": cancel_check} if cancel_check is not None else {}
            return await self._render_once(
                bundle, s, render_quality, progress, **kwargs
            )

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
                    scene_bundle.code, error, scene_bundle.class_name
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
            from aetherlab.services.scene_validation import validate_scene

            lint_ok, lint_issues = validate_scene(fixed, require_motion=True)
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
        ):
            import json as _json

            from aetherlab.services.code_safety import validate_code_safety
            from aetherlab.services.scene_critic import critique_video
            from aetherlab.services.scene_generator import SceneGenerator
            from aetherlab.services.scene_validation import validate_scene

            generator = SceneGenerator(s)
            board_brief = (
                _json.dumps(scene_bundle.storyboard)
                if scene_bundle.storyboard
                else (brief or "A short cinematic physics explainer scene.")
            )
            revision_limit = int(getattr(s, "visual_critic_max_passes", max_revisions) or max_revisions)
            frame_count = int(getattr(s, "visual_critic_keyframes", 6) or 6)
            for round_no in range(1, revision_limit + 1):
                crit = await critique_video(scene_bundle.video_path, board_brief, s, frame_count=frame_count)
                scene_bundle.quality_score = float(crit.score or 0.0)
                scene_bundle.critique_verdict = str(crit.verdict or "")
                scene_bundle.critique_issues = list(crit.issues)
                scene_bundle.critique_breakdown = dict(crit.breakdown)
                if crit.verdict == "skipped":
                    break
                scene_bundle.diagnostics.append(
                    f"Visual critique round {round_no}: {crit.verdict} "
                    f"(score {crit.score:.1f})"
                    + (" — " + "; ".join(crit.issues[:3]) if crit.issues else "")
                )
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
                    lint_ok, lint_issues = validate_scene(revised, require_motion=True)
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
                        lint_ok, lint_issues = validate_scene(revised, require_motion=True)
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
                        lint_ok, lint_issues = validate_scene(repaired, require_motion=True)
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

        return scene_bundle

    async def _render_once(
        self,
        scene_bundle: SceneBundle,
        settings: "AppSettings | None",
        quality: str,
        progress: Callable[[str], None] | None = None,
        variant: str = "",
        cancel_check: Callable[[], bool] | None = None,
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
                scene_bundle, settings, quality, cancel_check=cancel_check
            )
        from aetherlab.services.render_backend import (
            CLOUD_UNAVAILABLE,
            LocalRenderBackend,
            render_timeout_for,
            select_backend,
        )

        backend = select_backend(s, scene_bundle.code, quality)
        timeout = render_timeout_for(scene_bundle.code, quality, s)
        cancel_kwargs = (
            {"cancel_check": cancel_check} if cancel_check is not None else {}
        )
        rendered = await backend.render(
            scene_bundle,
            quality=quality,
            settings=s,
            timeout=timeout,
            progress=progress,
            variant=variant,
            **cancel_kwargs,
        )
        if rendered.status != CLOUD_UNAVAILABLE:
            return rendered
        # Cloud is optional. Restore the compiled status before handing the same
        # bundle to local rendering; the diagnostic stays so UI/tests can report
        # the fallback without poisoning the render guard.
        rendered.status = "compiled"
        rendered.failure_kind = ""
        if progress:
            try:
                progress("Cloud render unavailable; rendering locally")
            except Exception:  # noqa: BLE001
                pass
        local = await LocalRenderBackend().render(
            rendered,
            quality=quality,
            settings=s,
            timeout=timeout,
            progress=progress,
            **cancel_kwargs,
        )
        if local.status == "rendered":
            local.diagnostics.append("Cloud render unavailable; rendered locally.")
        # Ledger: record the local fallback against the same cloud job id so the
        # dashboard shows the whole story (cloud attempt -> local fallback).
        try:
            from aetherlab.services.render_backend import cloud_job_id, render_fps_for
            from aetherlab.services.render_ledger import RenderJobLedger

            jid = cloud_job_id(
                rendered, quality=quality, fps=render_fps_for(rendered.code, quality), variant=variant
            )
            reason = next(
                (d for d in reversed(rendered.diagnostics) if "unavailable" in d.lower()),
                "Cloud render unavailable; rendered locally.",
            )
            RenderJobLedger(s.data_dir / "render_ledger.json").fallback(
                jid, reason, local.video_path if local.status == "rendered" else ""
            )
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

        if not voiceover.narration_available():
            scene_bundle.diagnostics.append(
                "Narration enabled but edge-tts/ffmpeg unavailable; kept silent video."
            )
            return scene_bundle
        try:
            script = voiceover.storyboard_narration_script(scene_bundle.storyboard)
            target = voiceover.storyboard_target_seconds(scene_bundle.storyboard)
            narration = script
            if s.openai_api_key:
                try:
                    narration = await SceneGenerator(s).narrate(
                        brief or "physics animation", scene_bundle.code, script, target
                    ) or script
                except Exception as exc:  # noqa: BLE001
                    scene_bundle.diagnostics.append(
                        f"Narration script gen failed ({exc}); using storyboard lines."
                    )
            if not narration or not narration.strip():
                scene_bundle.diagnostics.append("No narration text available; kept silent video.")
                return scene_bundle
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


def _duration_contract_delta(seconds: float) -> float:
    """0 inside the 15-22s target, else distance to the nearest boundary."""
    try:
        value = float(seconds)
    except (TypeError, ValueError):
        return 9999.0
    if 15.0 <= value <= 22.0:
        return 0.0
    return min(abs(value - 15.0), abs(value - 22.0))


_FAILURE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("latex", ("undefined control sequence", "latex error", "! latex",
               "no such file", "dvi", "tex error", "xelatex")),
    ("ffmpeg", ("ffmpeg", "avconv", "libx264", "codec")),
    ("oom", ("memoryerror", "out of memory", "cannot allocate", "killed", "oom")),
    ("hallucinated-api", ("nameerror", "attributeerror", "has no attribute",
                          "unexpected keyword argument", "is not defined",
                          "typeerror", "importerror")),
)


def _classify_failure(stderr: str) -> str:
    """Bucket a render stderr into a failure class for repair + metrics."""
    low = (stderr or "").lower()
    for kind, markers in _FAILURE_PATTERNS:
        if any(m in low for m in markers):
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
