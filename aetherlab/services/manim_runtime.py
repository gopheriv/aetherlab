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
"""Generated by AetherLab.

The import block supports ManimGL first and Manim Community second so
the scene can be inspected even on systems without ManimGL.
"""

import math

try:
    from manimlib import *
except Exception:
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
        self.add(bounded_group)
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
