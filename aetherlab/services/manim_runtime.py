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
from aetherlab.services.code_safety import validate_code_safety
from aetherlab.services.error_learner import ErrorLearner
from aetherlab.services.scene_generator import SceneGenerator
from aetherlab.services.scene_templates import build_scene, detect_domain, load_scene_palette

if TYPE_CHECKING:
    from aetherlab.core.settings import AppSettings

log = logging.getLogger(__name__)

# Where rendered videos are cached
_RENDER_DIR = Path(tempfile.gettempdir()) / "aetherlab" / "renders"
_RENDER_DIR.mkdir(parents=True, exist_ok=True)

# Manim Community render quality: 480p for speed
_RENDER_QUALITY = "l"  # low = 480p15


class ManimRuntime:
    def __init__(self, settings: "AppSettings | None" = None) -> None:
        self._settings = settings

    async def generate_scene_async(
        self,
        request: ProblemRequest,
        solver: SolverResult,
        rag: RagResult,
        settings: "AppSettings | None" = None,
        max_retries: int = 2,
    ) -> SceneBundle:
        """Generate a dynamic Manim scene using the LLM.

        Each candidate must pass the AST safety gate (WP1) *and* compile before
        it is accepted. On a safety or syntax failure the real error is fed back
        to the model for an error-aware repair attempt (WP2a). ``max_retries``
        bounds the extra LLM calls; on exhaustion we fall back to the
        deterministic template, which is itself gated fail-closed.
        """
        s = settings or self._settings
        engine, diagnostics = self.detect_engine()
        class_name = "AetherLabScene"

        if s and s.openai_api_key:
            generator = SceneGenerator(s)
            feedback: str | None = None
            previous_code: str | None = None
            for attempt in range(max_retries + 1):
                code = await generator.generate(
                    request, solver, rag, class_name,
                    feedback=feedback, previous_code=previous_code,
                )
                previous_code = code

                # WP1: fail-closed safety gate BEFORE accepting the candidate.
                safe, issues = validate_code_safety(code)
                if not safe:
                    joined = "; ".join(issues)
                    diagnostics.append(f"Attempt {attempt + 1}: unsafe code rejected: {joined}")
                    feedback = (
                        "Your previous scene was rejected by the safety gate for "
                        f"using forbidden imports/calls: {joined}. Use only manim, "
                        "numpy, and math. Return a corrected full scene."
                    )
                    continue

                try:
                    compile(code, "<aetherlab-generated-scene>", "exec")
                except SyntaxError as exc:
                    diagnostics.append(f"Attempt {attempt + 1}: scene failed to compile: {exc}")
                    feedback = (
                        f"Your previous scene failed to compile with: {exc}. "
                        "Return a corrected full scene."
                    )
                    continue

                if attempt > 0:
                    diagnostics.append(f"Scene succeeded on retry {attempt}.")
                return SceneBundle(
                    class_name=class_name,
                    code=code,
                    engine=engine,
                    status="compiled",
                    diagnostics=diagnostics,
                )
            # All retries exhausted — fall back to the static template.
            diagnostics.append("All LLM attempts failed or were unsafe; using deterministic fallback.")
            code = self._build_scene_code(class_name, request, solver, rag)
        else:
            code = self._build_scene_code(class_name, request, solver, rag)

        return self._finalize_static(class_name, code, engine, diagnostics)

    def _finalize_static(
        self,
        class_name: str,
        code: str,
        engine: str,
        diagnostics: list[str],
    ) -> SceneBundle:
        """Gate + compile-check deterministic code before returning a bundle.

        The deterministic template is trusted, but we still run it through the
        safety gate so the fail-closed guarantee holds for *every* path.
        """
        safe, issues = validate_code_safety(code)
        if not safe:
            diagnostics.append("Deterministic template failed the safety gate: " + "; ".join(issues))
            return SceneBundle(
                class_name=class_name, code=code, engine=engine,
                status="unsafe", diagnostics=diagnostics,
            )
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
        return self._finalize_static(class_name, code, engine, diagnostics)

    def render_scene(
        self,
        scene_bundle: SceneBundle,
        settings: "AppSettings | None" = None,
        quality: str = "l",
    ) -> SceneBundle:
        """Render the generated scene to an MP4 video using Manim Community.

        Single-shot primitive (no self-heal). Backward-compatible signature used
        by callers that do not have the request/solver/rag needed to repair.

        Args:
            quality: Manim quality flag — 'l' (480p), 'm' (720p), 'h' (1080p), 'k' (4K).
        """
        bundle, _ = self._render_once(scene_bundle, quality)
        return bundle

    def _render_once(
        self,
        scene_bundle: SceneBundle,
        quality: str = "l",
    ) -> tuple[SceneBundle, str]:
        """Render exactly once. Returns ``(bundle, stderr_tail)``.

        The stderr tail is surfaced so the self-heal loop can classify the
        failure and, for CODE errors, feed the real message back to the LLM.
        """
        if scene_bundle.status != "compiled":
            scene_bundle.diagnostics.append("Skipping render: scene did not compile.")
            return scene_bundle, ""

        # WP1: fail-closed gate — never write/execute code that failed the gate,
        # even if it somehow reached the renderer already marked "compiled".
        safe, issues = validate_code_safety(scene_bundle.code)
        if not safe:
            scene_bundle.diagnostics.append("Refusing to render unsafe code: " + "; ".join(issues))
            scene_bundle.status = "unsafe"
            return scene_bundle, ""

        scene_name = _scene_name(scene_bundle.class_name, scene_bundle.code)
        scene_file = _RENDER_DIR / f"{scene_name}.py"
        scene_file.write_text(scene_bundle.code, encoding="utf-8")

        # Determine which manim binary to use
        manim_cmd = self._find_manim_command()
        if not manim_cmd:
            scene_bundle.diagnostics.append("No Manim binary found; returning code-only.")
            return scene_bundle, ""

        # Clean old renders for this scene to avoid stale video bug
        _clean_old_renders(scene_name)

        # Adjust timeout based on quality (higher quality = longer timeout)
        timeout_map = {"l": 180, "m": 300, "h": 480, "k": 900}
        render_timeout = timeout_map.get(quality, 180)

        log.info("Rendering scene: %s with %s -q%s", scene_name, " ".join(manim_cmd), quality)

        try:
            creation_flags = 0x08000000  # CREATE_NO_WINDOW on Windows
            # NOTE: No --disable_caching — let Manim cache rendered frames for speed
            result = subprocess.run(
                [*manim_cmd, "render", f"-q{quality}", str(scene_file), scene_bundle.class_name],
                capture_output=True,
                text=True,
                timeout=render_timeout,
                creationflags=creation_flags,
                cwd=str(_RENDER_DIR),
            )
            if result.returncode != 0:
                stderr = result.stderr.strip()
                scene_bundle.diagnostics.append(f"Manim render failed: {stderr[-300:]}")
                scene_bundle.status = "render-error"
                return scene_bundle, stderr
        except subprocess.TimeoutExpired:
            scene_bundle.diagnostics.append(f"Manim render timed out ({render_timeout}s).")
            scene_bundle.status = "render-timeout"
            return scene_bundle, "TimeoutExpired: render timed out"
        except Exception as exc:
            scene_bundle.diagnostics.append(f"Manim render error: {exc}")
            scene_bundle.status = "render-error"
            return scene_bundle, str(exc)

        # Find the output video
        video_path = _find_video(scene_name)
        if video_path:
            scene_bundle.video_path = str(video_path)
            scene_bundle.status = "rendered"
            log.info("Video rendered: %s (%.1f MB)", video_path, video_path.stat().st_size / 1e6)
            return scene_bundle, ""

        # Exit code 0 but no video is still a failure (e.g. manim CE's "There
        # are no scenes inside that module" when the file only defines a
        # ManimGL Scene). Surface it as a render error so the caller can
        # classify it instead of silently downgrading to "compiled".
        output_tail = (result.stdout or "")[-500:] + (result.stderr or "")[-300:]
        scene_bundle.diagnostics.append(
            "Manim exited 0 but produced no video: " + output_tail[-200:].strip()
        )
        scene_bundle.status = "render-error"
        return scene_bundle, output_tail

    async def render_scene_with_repair(
        self,
        scene_bundle: SceneBundle,
        request: ProblemRequest,
        solver: SolverResult,
        rag: RagResult,
        settings: "AppSettings | None" = None,
        quality: str = "l",
        max_repair_attempts: int = 2,
    ) -> SceneBundle:
        """Render with an error-aware self-heal loop (WP2b).

        Renders once; on a *code* failure feeds manim's real stderr back to the
        LLM for up to ``max_repair_attempts`` corrected re-renders (each
        re-validated by the WP1 gate). *Infra* failures (missing binary/LaTeX,
        ffmpeg, permission, timeout) never burn LLM calls — they are surfaced.
        If every repair fails, we fall back to the deterministic template, which
        avoids LaTeX and so renders even when the LLM scene cannot.
        """
        s = settings or self._settings
        bundle, stderr = self._render_once(scene_bundle, quality)
        if bundle.status == "rendered":
            return bundle

        llm_available = bool(s and s.openai_api_key)

        if bundle.status == "render-error" and llm_available:
            generator = SceneGenerator(s)
            learner = ErrorLearner(_error_store_path(s))
            attempts = 0
            while bundle.status == "render-error" and attempts < max_repair_attempts:
                kind = classify_render_error(stderr)
                if kind == "infra":
                    bundle.diagnostics.append(
                        "Render error classified as infrastructure; skipping LLM "
                        f"repair: {_stderr_head(stderr)}"
                    )
                    break
                attempts += 1
                # Cross-run learning: surface curated pitfall fixes + a recurrence
                # warning for this signature, then remember we hit it (WP5).
                hints = learner.hints_for(stderr)
                learner.record(stderr)
                if hints:
                    bundle.diagnostics.append(
                        f"Repair attempt {attempts}: applied {len(hints)} learned hint(s)."
                    )
                hint_block = ("\n\nKnown fixes for this error:\n- " + "\n- ".join(hints)) if hints else ""
                feedback = (
                    "Your previous scene compiled but crashed during rendering "
                    f"with:\n{stderr[-1500:]}{hint_block}"
                )
                code = await generator.generate(
                    request, solver, rag, bundle.class_name,
                    feedback=feedback, previous_code=bundle.code,
                )
                safe, issues = validate_code_safety(code)
                if not safe:
                    bundle.diagnostics.append(
                        f"Repair attempt {attempts}: candidate rejected by safety gate: "
                        + "; ".join(issues)
                    )
                    break
                try:
                    compile(code, "<aetherlab-generated-scene>", "exec")
                except SyntaxError as exc:
                    bundle.diagnostics.append(
                        f"Repair attempt {attempts}: candidate failed to compile: {exc}"
                    )
                    stderr = f"SyntaxError: {exc}"
                    continue  # keep repairing with the new error
                repaired = SceneBundle(
                    class_name=bundle.class_name, code=code, engine=bundle.engine,
                    status="compiled", diagnostics=bundle.diagnostics,
                )
                bundle, stderr = self._render_once(repaired, quality)
                if bundle.status == "rendered":
                    bundle.diagnostics.append(
                        f"Render succeeded after {attempts} LLM repair attempt(s)."
                    )
                    return bundle

        # Final safety net: the deterministic template avoids MathTex/LaTeX and
        # forbidden constructs, so it renders even when the LLM scene keeps
        # failing. Skip only if we are already rendering the template.
        if bundle.status == "render-error":
            template_code = self._build_scene_code(bundle.class_name, request, solver, rag)
            if template_code.strip() != bundle.code.strip():
                safe, _ = validate_code_safety(template_code)
                if safe:
                    tmpl_bundle = SceneBundle(
                        class_name=bundle.class_name, code=template_code, engine=bundle.engine,
                        status="compiled", diagnostics=bundle.diagnostics,
                    )
                    tmpl_bundle.diagnostics.append(
                        "Falling back to deterministic template for render."
                    )
                    final_bundle, _ = self._render_once(tmpl_bundle, quality)
                    return final_bundle

        return bundle

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

        Prefer `python -m manim` to avoid cross-Python-version issues.
        """
        if find_spec("manim"):
            import sys
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
        """Deterministic fallback scene, matched to the problem's domain (WP7).

        Domain detection uses the solver keywords plus the raw prompt words so
        e.g. a pendulum request gets a swinging pendulum even when the solver
        ran as the deterministic fallback.
        """
        detection_terms = [*solver.keywords, request.normalized_prompt()]
        domain = detect_domain(detection_terms, solver.variables)
        data_dir = getattr(self._settings, "data_dir", None)
        return build_scene(
            class_name=class_name,
            domain=domain,
            title=request.normalized_prompt(),
            summary=solver.summary,
            steps=solver.derivation_steps,
            variables=solver.variables,
            palette=load_scene_palette(data_dir),
        )


# Substrings that mean the *environment* is broken, not the generated code.
# Repairing these with the LLM is pointless, so they short-circuit the loop.
_INFRA_MARKERS: tuple[str, ...] = (
    "no module named",
    "modulenotfounderror",
    "command not found",
    "is not recognized as an internal or external command",
    "filenotfounderror",
    "the system cannot find the file",
    "winerror 2",
    "winerror 5",
    "permission denied",
    "permissionerror",
    "timed out",
    "timeoutexpired",
    "ffmpeg",
    "not installed",
    "latex not found",
    "no latex",
    "you do not have",  # manim: "You do not have <engine> installed"
    "please install",
    "no space left",
)

# Substrings that indicate a fault in the *generated scene* (repairable). LaTeX
# *content* errors (bad MathTex) live here — a missing LaTeX *engine* is infra.
_CODE_MARKERS: tuple[str, ...] = (
    "traceback (most recent call last)",
    "nameerror",
    "attributeerror",
    "typeerror",
    "valueerror",
    "keyerror",
    "indexerror",
    "syntaxerror",
    "cannot import name",
    "latex error",
    "undefined control sequence",
    "! ",  # TeX error lines start with "! "
    # manim CE: file defines no CE Scene subclass (e.g. ManimGL-only imports) —
    # repairable by regenerating with proper `from manim import *`.
    "no scenes inside",
)


def classify_render_error(stderr: str) -> str:
    """Classify a render failure as ``"code"`` (repairable) or ``"infra"``.

    Infra markers win first (they are specific). Then a recognisable code/TeX
    fault means ``"code"``. When nothing matches we default to ``"infra"`` — it
    is safer to surface an unknown failure than to burn LLM calls looping on it.
    """
    text = (stderr or "").lower()
    if any(marker in text for marker in _INFRA_MARKERS):
        return "infra"
    if any(marker in text for marker in _CODE_MARKERS):
        return "code"
    return "infra"


def _error_store_path(settings: "AppSettings | None") -> Path | None:
    """Where to persist the cross-run error-learning store, if we have a home."""
    data_dir = getattr(settings, "data_dir", None)
    if data_dir:
        return Path(data_dir) / "error_memory.json"
    return None


def _stderr_head(stderr: str, limit: int = 200) -> str:
    """First meaningful line of a stderr blob, trimmed for diagnostics."""
    for line in (stderr or "").splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:limit]
    return "(no stderr)"


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


def sanitize_scene_name(text: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", text.title())
    return "".join(parts) or "AetherLabScene"
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
            generator = SceneGenerator(s)
            for attempt in range(max_retries + 1):
                code = await generator.generate(request, solver, rag, class_name)
                try:
                    compile(code, "<aetherlab-generated-scene>", "exec")
                    if attempt > 0:
                        diagnostics.append(f"Scene succeeded on retry {attempt}.")
                    return SceneBundle(
                        class_name=class_name,
                        code=code,
                        engine=engine,
                        status="compiled",
                        diagnostics=diagnostics,
                    )
                except SyntaxError as exc:
                    diagnostics.append(f"Attempt {attempt + 1}: scene failed to compile: {exc}")
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
                # LLM and needs the actual traceback, not just the last line.
                scene_bundle.diagnostics.append(f"Manim render failed: {stderr[-1500:]}")
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
    ) -> SceneBundle:
        """Render; on a render-time API error, ask the LLM to fix its own code.

        LLM scenes occasionally invent Manim kwargs that pass the compile check
        but explode at render time. Feeding the traceback back for a bounded
        number of repair rounds converts most of those into successful renders.
        Without an API key this is exactly render_scene().
        """
        s = settings or self._settings
        scene_bundle = self.render_scene(scene_bundle, s, quality)

        repairs = 0
        while (
            scene_bundle.status == "render-error"
            and repairs < max_repairs
            and s is not None
            and s.openai_api_key
        ):
            from aetherlab.services.scene_generator import SceneGenerator

            error = scene_bundle.diagnostics[-1] if scene_bundle.diagnostics else "unknown"
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
            scene_bundle.code = fixed
            scene_bundle.status = "compiled"
            scene_bundle.diagnostics.append(f"Applied render repair {repairs}.")
            scene_bundle = self.render_scene(scene_bundle, s, quality)

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
        
        Prefer `python -m manim` to avoid cross-Python-version issues.
        """
        if find_spec("manim"):
            import sys
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
        title = _literal(_shorten(request.normalized_prompt(), 70))
        summary = _literal(_shorten(solver.summary, 120))
        first_steps = [_shorten(step, 82) for step in solver.derivation_steps[:4]]
        step_lines = ",\n            ".join(_literal(step) for step in first_steps) or _literal("No derivation steps available.")
        variable_lines = ",\n            ".join(
            f"{_literal(name)}: {float(value)!r}" for name, value in sorted(solver.variables.items())
        )
        if not variable_lines:
            variable_lines = f"{_literal('parameter')}: 1.0"
        rag_count = len(rag.hits)

        return _MANIM_SCENE_TEMPLATE.format(
            class_name=class_name,
            title=title,
            summary=summary,
            step_lines=step_lines,
            variable_lines=variable_lines,
            rag_count=rag_count,
        ).strip() + "\n"


_MANIM_SCENE_TEMPLATE = '''
"""Generated by AetherLab (Manim Community).

Do NOT import manimlib here: manimgl parses sys.argv at import time, which
hijacks the Manim Community CLI arguments mid-render (ported finding from
the manim-bot project).
"""

import math

from manim import *


class {class_name}(Scene):
    def construct(self):
        title_text = {title}
        summary_text = {summary}
        derivation_steps = [
            {step_lines}
        ]
        variables = {{
            {variable_lines}
        }}

        title = Text(title_text).scale(0.55)
        title.to_edge(UP)

        summary = Text(summary_text).scale(0.32)
        summary.next_to(title, DOWN)

        rows = VGroup()
        for index, step in enumerate(derivation_steps, start=1):
            rows.add(Text(f"{{index}}. {{step}}").scale(0.28))
        rows.arrange(DOWN, aligned_edge=LEFT, buff=0.18)
        rows.next_to(summary, DOWN, buff=0.35)

        axes = Axes(x_range=[-3, 3, 1], y_range=[-2, 2, 1])
        axes.scale(0.55)
        axes.to_edge(DOWN)

        damping = variables.get("damping", 0.15)
        stiffness = variables.get("stiffness", 1.0)
        waveform = lambda x: math.exp(-damping * (x + 3)) * math.sin(stiffness * x * 2)
        if hasattr(axes, "plot"):
            curve = axes.plot(waveform, color=BLUE)
        else:
            curve = axes.get_graph(waveform, color=BLUE)
        caption = Text("RAG references: {rag_count}").scale(0.25)
        caption.next_to(axes, UP, buff=0.1)

        bounded_group = VGroup(title, summary, rows, axes, curve, caption)
        frame_width = getattr(config, "frame_width", 14.0)
        if isinstance(config, dict):
            frame_width = config.get("frame_width", frame_width)
        bounded_group.scale_to_fit_width(frame_width - 1.0)
        bounded_group.move_to(ORIGIN)

        # A scene with no animations produces no video file, so always
        # animate in (and hold) rather than static-add.
        self.play(FadeIn(bounded_group), run_time=1.0)
        self.play(Create(curve.copy().set_color(YELLOW)), run_time=1.5)
        self.wait(1.0)
'''


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


def _literal(text: str) -> str:
    return repr(text)


def sanitize_scene_name(text: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", text.title())
    return "".join(parts) or "AetherLabScene"
