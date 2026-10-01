"""Preflight: run a scene's code in seconds before the slow render.

Static gates cannot see runtime crashes (a hex string where Manim 0.21 wants
a colour object, a zero-length wait) or geometry that leaves the screen (a
Planck curve shooting off the top of its axes). Each such miss used to cost a
full render: 1-5 minutes locally, about 3.5 minutes round trip on GitHub
Actions, before repair could even start.

``preflight_scene`` executes the scene with Manim's dry run at 2 fps in a
child process (``_preflight_runner``). Nothing is drawn, so a 30 s scene
finishes in about 5-10 s. The report gives the crash traceback, objects found
outside the frame after each animation, and the exact scene duration
(including loops and lagged groups that static estimates miss).

Fail-soft: any problem running the preflight itself returns ``ran=False`` and
the caller renders exactly as before. Disable with ``AETHERLAB_PREFLIGHT=0``.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

PREFLIGHT_FPS = 2
PREFLIGHT_TIMEOUT_S = 120


@dataclass
class PreflightReport:
    ran: bool = False
    ok: bool = False
    error: str = ""
    duration_s: float = 0.0
    off_frame: list[dict] = field(default_factory=list)
    seconds: float = 0.0
    note: str = ""

    @property
    def crashed(self) -> bool:
        return self.ran and not self.ok

    def off_frame_lines(self, limit: int = 6) -> list[str]:
        lines = []
        for item in self.off_frame[:limit]:
            left, right, bottom, top = item.get("bounds", [0, 0, 0, 0])
            lines.append(
                f"[PREFLIGHT:OFF_FRAME] {item.get('mobject')} after the {item.get('after')} at "
                f"~{item.get('time_s')}s spans x {left}..{right}, y {bottom}..{top} "
                f"(frame is about x -7.1..7.1, y -4.0..4.0; overflow {item.get('overflow')})."
            )
        return lines


def tex_cache_dir(code: str) -> Path:
    """A TeX cache shared by the preflight and the local render of the same code.

    Keyed by the code, so the render reuses every formula the preflight already
    compiled (LaTeX was ~35 s of a cold 50 s preflight), while concurrent
    tournament candidates, whose code differs, never write the same folder.
    """
    import hashlib

    from aetherlab.services.manim_runtime import _RENDER_DIR

    digest = hashlib.sha256((code or "").encode("utf-8")).hexdigest()[:16]
    root = _RENDER_DIR / "tex"
    path = root / digest
    path.mkdir(parents=True, exist_ok=True)
    _prune_tex_cache(root, keep=40)
    return path


def _prune_tex_cache(root: Path, keep: int) -> None:
    try:
        folders = sorted((d for d in root.iterdir() if d.is_dir()),
                         key=lambda d: d.stat().st_mtime, reverse=True)
    except OSError:
        return
    import shutil

    for stale in folders[keep:]:
        shutil.rmtree(stale, ignore_errors=True)


def preflight_enabled() -> bool:
    return os.getenv("AETHERLAB_PREFLIGHT", "1").strip().lower() not in {"0", "false", "no", "off"}


def preflight_scene(code: str, class_name: str, timeout: int = PREFLIGHT_TIMEOUT_S,
                    *, tex_dir: Path | None = None) -> PreflightReport:
    """Dry-run ``code`` in a child process and report crashes, off-frame objects and duration."""
    started = time.monotonic()
    report = PreflightReport()
    if not preflight_enabled():
        report.note = "preflight disabled"
        return report
    try:
        with tempfile.TemporaryDirectory(prefix="aetherlab_preflight_") as tmp:
            scene_path = Path(tmp) / "scene.py"
            report_path = Path(tmp) / "report.json"
            scene_path.write_text(code, encoding="utf-8")
            from aetherlab.core.proc import subprocess_kwargs

            env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
            result = subprocess.run(
                [sys.executable, "-m", "aetherlab.services._preflight_runner",
                 str(scene_path), class_name, str(report_path), str(PREFLIGHT_FPS),
                 str(tex_dir or tex_cache_dir(code))],
                cwd=tmp, capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=timeout, env=env, **subprocess_kwargs(),
            )
            if not report_path.exists():
                report.note = (f"preflight runner produced no report (exit {result.returncode}): "
                               f"{(result.stderr or result.stdout)[-400:]}")
                return report
            data = json.loads(report_path.read_text(encoding="utf-8"))
    except subprocess.TimeoutExpired:
        report.note = f"preflight timed out after {timeout}s"
        return report
    except Exception as exc:  # noqa: BLE001 - preflight is advisory
        report.note = f"preflight unavailable: {type(exc).__name__}: {exc}"
        return report
    finally:
        report.seconds = round(time.monotonic() - started, 1)
    report.ran = True
    report.ok = bool(data.get("ok"))
    report.error = str(data.get("error", ""))
    report.duration_s = float(data.get("duration_s", 0.0) or 0.0)
    report.off_frame = [item for item in data.get("off_frame", []) if isinstance(item, dict)]
    return report
