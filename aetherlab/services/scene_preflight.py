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
import re
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
    # Unintended pairwise overlaps (Agent2 contract): each item carries the
    # object names (a/b + label_a/label_b), first time_s, persistence
    # duration_s, bounds_a/bounds_b + overlap bounds, overlap_ratio, severity
    # (low/medium/high), transient (crossing during motion vs boundary pile),
    # and a suggested repair string. Others read this; the runner writes it.
    overlaps: list[dict] = field(default_factory=list)
    seconds: float = 0.0
    note: str = ""
    # [source line, start s, end s] for every top-level play/wait.
    events: list[list[float]] = field(default_factory=list)

    @property
    def crashed(self) -> bool:
        return self.ran and not self.ok

    def off_frame_lines(self, limit: int = 6) -> list[str]:
        from aetherlab.services.scene_components.layout import frame_half_extents

        half_w, half_h = frame_half_extents()
        frame = f"x -{half_w}..{half_w}, y -{half_h}..{half_h}"
        lines = []
        for item in self.off_frame[:limit]:
            left, right, bottom, top = item.get("bounds", [0, 0, 0, 0])
            lines.append(
                f"[PREFLIGHT:OFF_FRAME] {item.get('mobject')} after the {item.get('after')} at "
                f"~{item.get('time_s')}s spans x {left}..{right}, y {bottom}..{top} "
                f"(frame is about {frame}; overflow {item.get('overflow')})."
            )
        return lines

    def overlap_lines(self, limit: int = 6) -> list[str]:
        """Human/LLM-readable overlap findings with suggested repairs."""
        lines = []
        for item in self.overlaps[:limit]:
            lines.append(overlap_line(item))
        return lines

    @property
    def overlap_score(self) -> float:
        """Weighted severity total (high=3, medium=1, low=0.2); lower is better."""
        return overlap_score(self.overlaps)


def _overlap_label(item: dict, side: str) -> str:
    name = str(item.get(side, "?"))
    label = str(item.get(f"label_{side}", "") or "").strip()
    if label and label.lower() not in name.lower():
        return f"{name} ({label[:40]!r})"
    return name


def overlap_line(item: dict) -> str:
    """One [PREFLIGHT:OVERLAP] diagnostic line for an overlap finding."""
    bounds = item.get("overlap", item.get("bounds", [0, 0, 0, 0]))
    left, right, bottom, top = (list(bounds) + [0, 0, 0, 0])[:4]
    kind = "crossing during motion" if item.get("transient") else "shared region"
    return (
        f"[PREFLIGHT:OVERLAP] {_overlap_label(item, 'a')} vs {_overlap_label(item, 'b')} "
        f"at ~{item.get('time_s', 0)}s ({kind} x {left}..{right}, y {bottom}..{top}; "
        f"severity {item.get('severity', 'low')}, overlap {item.get('overlap_ratio', 0):.0%} "
        f"for {item.get('duration_s', 0)}s). Suggested repair: "
        f"{item.get('repair') or suggest_overlap_repair(item)}"
    )


def suggest_overlap_repair(item: dict) -> str:
    """Repair suggestion for an overlap finding (stored, or a generic fallback)."""
    stored = str(item.get("repair", "") or "").strip()
    if stored:
        return stored
    return (
        f"move {item.get('b', 'the second object')} out of "
        f"{item.get('a', 'the first object')}'s region, or sequence them so only "
        "one focal object owns that region per beat"
    )


def overlap_score(overlaps: list[dict]) -> float:
    """Weighted severity total for improvement comparison (lower is better)."""
    weights = {"high": 3.0, "medium": 1.0, "low": 0.2}
    return round(sum(weights.get(str(item.get("severity", "low")), 0.2)
                     for item in overlaps or []), 3)


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
    report.overlaps = [item for item in data.get("overlaps", []) if isinstance(item, dict)]
    report.events = [
        [int(e[0]), float(e[1]), float(e[2])] for e in data.get("events", [])
        if isinstance(e, list) and len(e) == 3
    ]
    return report


def repair_overlap_code(code: str, overlaps: list[dict], *, attempt: int = 0) -> tuple[str, bool]:
    """Deterministically nudge stacked duplicates apart (bounded, fail-soft).

    The dominant machine-generated crowding pattern is several mobjects placed
    at the identical ``.move_to(...)`` target with no cleanup between them.
    For each such pile, later occurrences are shifted downward by a staggered
    amount that grows with ``attempt`` (1.0/1.6/2.2 ... units). Only single-line
    calls are edited, the result is compile-checked, and any doubt returns the
    original code unchanged. Returns (code, changed).
    """
    import ast

    if not overlaps or not code:
        return code, False
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code, False
    groups: dict[str, list[ast.Call]] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "move_to" or not node.args:
            continue
        try:
            segment = ast.get_source_segment(code, node.args[0]) or ""
        except Exception:  # noqa: BLE001 - conservative: skip unresolvable targets
            continue
        norm = re.sub(r"\s+", "", segment)
        if norm:
            groups.setdefault(norm, []).append(node)
    piles = {target: calls for target, calls in groups.items() if len(calls) >= 2}
    if not piles:
        return code, False
    step = 1.0 + 0.6 * max(0, attempt)
    # (line index, column, text): applied right-to-left per line.
    insertions: dict[int, list[tuple[int, str]]] = {}
    for calls in piles.values():
        ordered = sorted(calls, key=lambda n: (n.lineno, n.col_offset))
        for pile_index, node in enumerate(ordered[1:], start=1):
            end_line = getattr(node, "end_lineno", None) or node.lineno
            end_col = getattr(node, "end_col_offset", None)
            if end_line != node.lineno or not end_col:
                continue  # multi-line call: skip rather than risk breaking it
            distance = round(step * pile_index, 2)
            insertions.setdefault(node.lineno - 1, []).append(
                (end_col, f".shift(DOWN * {distance})")
            )
    if not insertions:
        return code, False
    lines = code.splitlines(keepends=True)
    for line_index, edits in insertions.items():
        if not 0 <= line_index < len(lines):
            return code, False
        for col, text in sorted(edits, reverse=True):
            line = lines[line_index]
            if not 0 <= col <= len(line):
                return code, False
            lines[line_index] = line[:col] + text + line[col:]
    repaired = "".join(lines)
    try:
        compile(repaired, "<aetherlab-overlap-repair>", "exec")
    except SyntaxError:
        return code, False
    return repaired, repaired != code


def repair_overlaps_with_recheck(
    code: str, class_name: str, *, max_attempts: int = 3,
    timeout: int = PREFLIGHT_TIMEOUT_S,
) -> tuple[str, "PreflightReport", bool]:
    """Bounded overlap repair: nudge, re-preflight, keep only improvements.

    Runs the preflight, applies :func:`repair_overlap_code` with growing
    separation, and re-checks after every attempt (at most ``max_attempts``).
    Returns (best_code, best_report, improved); when nothing reduces the
    overlap score the ORIGINAL code and its report are returned unchanged.
    """
    baseline = preflight_scene(code, class_name, timeout=timeout)
    if not baseline.ran or not baseline.ok:
        return code, baseline, False
    actionable = [item for item in baseline.overlaps
                  if str(item.get("severity", "low")) in {"high", "medium"}]
    if not actionable:
        return code, baseline, False
    best_code, best_report, best_score = code, baseline, baseline.overlap_score
    for attempt in range(max_attempts):
        candidate, changed = repair_overlap_code(best_code, best_report.overlaps,
                                                 attempt=attempt)
        if not changed:
            break
        checked = preflight_scene(candidate, class_name, timeout=timeout)
        if not checked.ran or not checked.ok:
            continue
        if checked.overlap_score < best_score:
            best_code, best_report, best_score = candidate, checked, checked.overlap_score
            remaining = [item for item in checked.overlaps
                         if str(item.get("severity", "low")) in {"high", "medium"}]
            if not remaining:
                break
    improved = best_score < baseline.overlap_score
    if not improved:
        return code, baseline, False
    return best_code, best_report, True


_BEAT_MARKER_LINE = re.compile(
    r"^\s*#\s*BEAT\s+([AS]\d+\.B\d+)\s*\|\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*s\s*$"
)


@dataclass
class BeatTiming:
    beat_id: str
    planned_s: float
    measured_s: float

    @property
    def drift_s(self) -> float:
        return self.measured_s - self.planned_s


def beat_timings(code: str, report: PreflightReport) -> list[BeatTiming]:
    """When each marked beat really starts, measured by the dry run.

    A beat starts with the first top-level animation written after its
    ``# BEAT`` marker (and before the next one). Beats with no animation of
    their own are skipped. Narration is placed at the planned start, so the
    drift is exactly how far picture and voice come apart.
    """
    markers = []
    for number, text in enumerate(code.splitlines(), start=1):
        match = _BEAT_MARKER_LINE.match(text)
        if match:
            markers.append((number, match.group(1), float(match.group(2))))
    timings: list[BeatTiming] = []
    for index, (line, beat_id, planned) in enumerate(markers):
        next_line = markers[index + 1][0] if index + 1 < len(markers) else 10**9
        starts = [start for event_line, start, _end in report.events
                  if line < event_line < next_line]
        if starts:
            timings.append(BeatTiming(beat_id, planned, min(starts)))
    return timings


def beat_drift_lines(timings: list[BeatTiming], tolerance_s: float, limit: int = 10) -> list[str]:
    late = [t for t in timings if abs(t.drift_s) > tolerance_s]
    return [
        f"[PREFLIGHT:BEAT_DRIFT] {t.beat_id} is planned at {t.planned_s:.2f}s but its first "
        f"animation starts at {t.measured_s:.2f}s ({t.drift_s:+.2f}s)."
        for t in late[:limit]
    ]
