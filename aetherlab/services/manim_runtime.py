"""ManimGL/Community scene generation, rendering, and validation."""

from __future__ import annotations

import hashlib
import logging
import re
import shutil
import subprocess
import tempfile
from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING

from aetherlab.core.models import ProblemRequest, RagResult, SceneBundle, SolverResult
from aetherlab.services.scene_generator import SceneGenerator

if TYPE_CHECKING:
    from aetherlab.core.settings import AppSettings

log = logging.getLogger(__name__)

# Where rendered videos are cached
_RENDER_DIR = Path(tempfile.gettempdir()) / "aetherlab" / "renders"
_RENDER_DIR.mkdir(parents=True, exist_ok=True)

# Manim Community render quality: 480p for speed
_RENDER_QUALITY = "l"  # low = 480p15


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
    try:
        import os as _os

        import psutil

        total_gb = psutil.virtual_memory().total / 1024**3
        cpu = _os.cpu_count() or 2
    except Exception:
        total_gb, cpu = 8.0, 2

    if total_gb >= 16 and cpu >= 6:
        return {"name": "cinematic", "fps": 60, "below_normal": False}
    if total_gb >= 10:
        return {"name": "standard", "fps": 30, "below_normal": False}
    return {"name": "constrained", "fps": 30, "below_normal": True}


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
    ) -> SceneBundle:
        """Generate a dynamic Manim scene using LLM, with retry on failure."""
        s = settings or self._settings
        engine, diagnostics = self.detect_engine()
        class_name = "AetherLabScene"

        if s and s.openai_api_key:
            from aetherlab.services.code_safety import validate_code_safety
            from aetherlab.services.scene_validation import estimate_duration, validate_scene

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
                lint_ok, lint_issues = validate_scene(code)
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
            code = self._build_scene_code(class_name, request, solver, rag)
        else:
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

    def generate_scene(
        self,
        request: ProblemRequest,
        solver: SolverResult,
        rag: RagResult,
    ) -> SceneBundle:
        """Synchronous fallback — uses the static template."""
        engine, diagnostics = self.detect_engine()
        class_name = "AetherLabScene"
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
    ) -> SceneBundle:
        """Render the generated scene to an MP4 video using Manim Community.

        Args:
            quality: Manim quality flag — 'l' (480p), 'm' (720p), 'h' (1080p), 'k' (4K).
        """
        if scene_bundle.status != "compiled":
            scene_bundle.diagnostics.append("Skipping render: scene did not compile.")
            return scene_bundle

        scene_name = _scene_name(scene_bundle.class_name, scene_bundle.code)
        scene_file = _RENDER_DIR / f"{scene_name}.py"
        scene_file.write_text(scene_bundle.code, encoding="utf-8")

        # Determine which manim binary to use
        manim_cmd = self._find_manim_command()
        if not manim_cmd:
            scene_bundle.diagnostics.append("No Manim binary found; returning code-only.")
            return scene_bundle

        # Clean old renders for this scene to avoid stale video bug
        _clean_old_renders(scene_name)

        # Timeouts ported from manim-bot: fps-explicit renders are heavier,
        # and its production ceiling is 600s.
        timeout_map = {"l": 240, "m": 420, "h": 600, "k": 900}
        render_timeout = timeout_map.get(quality, 240)

        tier = _RENDER_TIER
        log.info(
            "Rendering scene: %s with %s -q%s --fps %d (tier %s)",
            scene_name, " ".join(manim_cmd), quality, tier["fps"], tier["name"],
        )

        try:
            creation_flags = 0x08000000  # CREATE_NO_WINDOW on Windows
            if tier["below_normal"]:
                creation_flags |= 0x00004000  # BELOW_NORMAL_PRIORITY_CLASS
            # NOTE: No --disable_caching — let Manim cache rendered frames for speed
            result = subprocess.run(
                [
                    *manim_cmd, "render", f"-q{quality}",
                    "--fps", str(tier["fps"]),
                    "--media_dir", str(_RENDER_DIR / "media"),
                    str(scene_file), scene_bundle.class_name,
                ],
                capture_output=True,
                text=True,
                timeout=render_timeout,
                creationflags=creation_flags,
                cwd=str(_RENDER_DIR),
            )
            if result.returncode != 0:
                stderr = result.stderr.strip()
                # Keep a generous tail: the repair pass feeds this back to the
                # LLM and needs the actual traceback — chained exceptions and
                # LaTeX logs push the root cause well past a short tail.
                scene_bundle.diagnostics.append(f"Manim render failed: {stderr[-8000:]}")
                scene_bundle.status = "render-error"
                return scene_bundle
        except subprocess.TimeoutExpired:
            scene_bundle.diagnostics.append(f"Manim render timed out ({render_timeout}s).")
            scene_bundle.status = "render-timeout"
            return scene_bundle
        except Exception as exc:
            scene_bundle.diagnostics.append(f"Manim render error: {exc}")
            scene_bundle.status = "render-error"
            return scene_bundle

        # Find the output video
        video_path = _find_video(scene_name)
        if video_path:
            scene_bundle.video_path = str(video_path)
            scene_bundle.status = "rendered"
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
    ) -> SceneBundle:
        """Render; repair crashes/timeouts; then (optionally) critique and revise.

        Crash path: LLM scenes occasionally invent Manim kwargs that pass the
        compile check but explode at render time; feeding the traceback back for
        a bounded number of repair rounds converts most into successful renders.
        Quality path: with a vision model configured, the rendered video's
        frames are judged against the storyboard/brief and revised until the
        critic says ship (bounded by max_revisions). Without an API key this is
        exactly render_scene(); without a vision model, repairs-only.
        """
        s = settings or self._settings
        scene_bundle = self.render_scene(scene_bundle, s, quality)

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

            lint_ok, lint_issues = validate_scene(fixed)
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
            scene_bundle = self.render_scene(scene_bundle, s, quality)

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
            for round_no in range(1, max_revisions + 1):
                crit = await critique_video(scene_bundle.video_path, board_brief, s)
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
                    compile(revised, "<aetherlab-revised-scene>", "exec")
                except Exception as exc:  # noqa: BLE001
                    scene_bundle.diagnostics.append(
                        f"Visual revision {round_no} failed: {exc}"
                    )
                    break
                safe, _ = validate_code_safety(revised)
                lint_ok, _ = validate_scene(revised)
                if not safe or not lint_ok:
                    scene_bundle.diagnostics.append(
                        f"Visual revision {round_no} rejected by static gates."
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
                trial = self.render_scene(trial, s, quality)
                if trial.status == "rendered":
                    trial.diagnostics.append(f"Applied visual revision {round_no}.")
                    scene_bundle = trial
                else:
                    scene_bundle.diagnostics.append(
                        f"Visual revision {round_no} did not render; keeping previous cut."
                    )
                    break

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
    ) -> str:
        """Deterministic domain-aware fallback (services/scene_templates).

        Chooses a pendulum/orbit/wave/oscillator visualization matching the
        problem instead of one generic damped-wave plot, themed to the app
        palette when the UI has persisted one.
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
    """Remove old render artifacts to avoid stale video bug."""
    # Manim Community output structure: media/videos/<scene>/<quality>/
    media_dir = _RENDER_DIR / "media" / "videos" / scene_name
    if media_dir.exists():
        shutil.rmtree(media_dir, ignore_errors=True)


def _find_video(scene_name: str) -> Path | None:
    """Find the rendered MP4 file in Manim's output directory."""
    videos_dir = _RENDER_DIR / "media" / "videos" / scene_name
    if not videos_dir.exists():
        return None
    mp4s = list(videos_dir.rglob("*.mp4"))
    if mp4s:
        # Return the most recently modified file
        return max(mp4s, key=lambda p: p.stat().st_mtime)
    return None


def _shorten(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def sanitize_scene_name(text: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", text.title())
    return "".join(parts) or "AetherLabScene"
