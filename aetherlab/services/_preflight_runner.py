"""Child-process runner for scene preflight (see services/scene_preflight.py).

Usage: python -m aetherlab.services._preflight_runner <scene.py> <ClassName> <report.json> <fps>

Executes the scene with Manim's dry run (no frames are drawn) at a low frame
rate, so construct() runs end to end in seconds. After every play/wait it
records objects that sit outside the camera frame, and at the end the exact
scene duration. The report is written as JSON; a crash is reported with its
traceback. Generated code runs here exactly as it would in the render
subprocess, never in the app's own process.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
import traceback


def _visible(mob) -> bool:
    try:
        family = mob.get_family()
    except Exception:  # noqa: BLE001
        return True
    for member in family:
        for getter in ("get_stroke_opacity", "get_fill_opacity", "get_opacity"):
            fn = getattr(member, getter, None)
            if fn is None:
                continue
            try:
                if float(fn()) > 0.05:
                    return True
            except Exception:  # noqa: BLE001
                return True
    return False


def _bounds(mob) -> tuple[float, float, float, float] | None:
    try:
        if not mob.has_points() and not mob.submobjects:
            return None
        left, right = float(mob.get_left()[0]), float(mob.get_right()[0])
        bottom, top = float(mob.get_bottom()[1]), float(mob.get_top()[1])
    except Exception:  # noqa: BLE001
        return None
    values = (left, right, bottom, top)
    if not all(math.isfinite(v) for v in values):
        return (-1e9, 1e9, -1e9, 1e9)
    if right - left <= 1e-6 and top - bottom <= 1e-6:
        return None
    return values


def main() -> int:
    scene_path, class_name, report_path, fps = sys.argv[1:5]
    tex_dir = sys.argv[5] if len(sys.argv) > 5 else ""
    report: dict = {"ok": False, "error": "", "duration_s": 0.0, "plays": 0, "off_frame": [],
                    "events": []}

    from manim import Scene, config

    config.dry_run = True
    config.disable_caching = True
    config.write_to_movie = False
    config.save_last_frame = False
    config.frame_rate = max(1, int(fps))
    config.verbosity = "ERROR"
    if tex_dir:
        # Shared, content-addressed TeX cache: formulas compiled once are reused.
        config.tex_dir = tex_dir
    config.progress_bar = "none"

    half_w, half_h = config.frame_width / 2.0, config.frame_height / 2.0
    margin = 0.6
    seen: set[tuple[str, str]] = set()

    def inspect(scene, call: str) -> None:
        report["plays"] += 1
        time_s = round(exact["seconds"], 2)
        for mob in list(getattr(scene, "mobjects", [])):
            bounds = _bounds(mob)
            if bounds is None or not _visible(mob):
                continue
            left, right, bottom, top = bounds
            # A full-screen backdrop is meant to overflow the frame slightly.
            if right - left >= 2 * half_w * 0.97 and top - bottom >= 2 * half_h * 0.97 \
                    and abs((left + right) / 2) < 1.0 and abs((top + bottom) / 2) < 1.0 \
                    and right - left <= 2 * half_w * 1.6 and top - bottom <= 2 * half_h * 1.6:
                continue
            over = max(-half_w - left, right - half_w, -half_h - bottom, top - half_h)
            if over <= margin:
                continue
            name = type(mob).__name__
            key = (name, "x" if max(-half_w - left, right - half_w) >= max(-half_h - bottom, top - half_h) else "y")
            if key in seen:
                continue
            seen.add(key)
            report["off_frame"].append({
                "mobject": name, "time_s": time_s, "after": call,
                "bounds": [round(v, 2) if abs(v) < 1e6 else (1e6 if v > 0 else -1e6) for v in bounds],
                "overflow": round(min(over, 1e6), 2),
            })
            if len(report["off_frame"]) >= 12:
                return

    original_play, original_wait = Scene.play, Scene.wait
    # At 2 fps Manim rounds every animation up to whole frames, so the dry-run
    # clock overstates the length (40.5 s for a 34.3 s scene). Manim keeps each
    # play's unrounded run time in scene.duration; sum it for top-level calls
    # only (wait() calls play() internally).
    depth = {"n": 0}
    exact = {"seconds": 0.0}

    import os

    scene_file = os.path.normcase(os.path.abspath(scene_path))

    def _scene_line() -> int:
        # The outermost frame in the scene file is the construct() line that
        # led here, even when the play happens inside a helper method. Beat
        # markers are construct() comments, so this line places the event.
        line, frame = 0, sys._getframe(2)
        while frame is not None:
            if os.path.normcase(os.path.abspath(frame.f_code.co_filename)) == scene_file:
                line = frame.f_lineno
            frame = frame.f_back
        return line

    def _timed(original, call):
        def wrapper(self, *args, **kwargs):
            top_level = depth["n"] == 0
            start_s, line = exact["seconds"], (_scene_line() if top_level else 0)
            depth["n"] += 1
            try:
                result = original(self, *args, **kwargs)
            finally:
                depth["n"] -= 1
            if depth["n"] == 0:
                try:
                    exact["seconds"] += max(0.0, float(getattr(self, "duration", 0.0) or 0.0))
                except (TypeError, ValueError):
                    pass
                if top_level and len(report["events"]) < 4000:
                    report["events"].append(
                        [line, round(start_s, 3), round(exact["seconds"], 3)]
                    )
                inspect(self, call)
            return result
        return wrapper

    play = _timed(original_play, "play")
    wait = _timed(original_wait, "wait")

    Scene.play, Scene.wait = play, wait
    try:
        spec = importlib.util.spec_from_file_location("aetherlab_preflight_scene", scene_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        scene = getattr(module, class_name)()
        scene.render()
        report["duration_s"] = round(exact["seconds"], 2)
        report["ok"] = True
    except BaseException as exc:  # noqa: BLE001 - every failure is the report
        report["error"] = "".join(traceback.format_exception(exc))[-6000:]
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
