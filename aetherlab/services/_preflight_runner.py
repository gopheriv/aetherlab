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


# ── overlap detection (self-contained: no aetherlab imports in this runner) ──
# Pairwise bounds checks between visible top-level mobjects, with an allowlist
# for relations that are overlapping *by design*. Kept in sync (by contract,
# not by import) with services/scene_preflight.py severity + repair wording.

_TEXT_TYPES = frozenset({
    "Text", "Tex", "MathTex", "SingleStringMathTex", "MarkupText", "Paragraph",
    "Code", "DecimalNumber", "Integer", "Variable",
})
_AXES_TYPES = frozenset({
    "Axes", "ThreeDAxes", "NumberPlane", "PolarPlane", "NumberLine",
})
_FRAMING_TYPES = frozenset({
    "SurroundingRectangle", "Rectangle", "RoundedRectangle", "BackgroundRectangle",
})
_TRAIL_TYPES = frozenset({"TracedPath"})
_MAX_OVERLAPS = 12


def _box_area(box) -> float:
    return max(0.0, box[1] - box[0]) * max(0.0, box[3] - box[2])


def _intersect(a, b):
    left, right = max(a[0], b[0]), min(a[1], b[1])
    bottom, top = max(a[2], b[2]), min(a[3], b[3])
    if right - left <= 1e-9 or top - bottom <= 1e-9:
        return None
    return (left, right, bottom, top)


def _union(a, b):
    return (min(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), max(a[3], b[3]))


def _contains(outer, inner, tol: float = 0.05) -> bool:
    return (outer[0] - tol <= inner[0] and inner[1] <= outer[1] + tol
            and outer[2] - tol <= inner[2] and inner[3] <= outer[3] + tol)


def _center_inside(box, other) -> bool:
    cx, cy = (other[0] + other[1]) / 2.0, (other[2] + other[3]) / 2.0
    return box[0] <= cx <= box[1] and box[2] <= cy <= box[3]


def _max_opacity(mob) -> float:
    """Highest opacity across the family (halos/glows read as translucent)."""
    try:
        family = mob.get_family()
    except Exception:  # noqa: BLE001
        return 1.0
    best = 0.0
    for member in family:
        for getter in ("get_stroke_opacity", "get_fill_opacity", "get_opacity"):
            fn = getattr(member, getter, None)
            if fn is None:
                continue
            try:
                best = max(best, float(fn()))
            except Exception:  # noqa: BLE001
                return 1.0
    return best


def _mob_label(mob) -> str:
    for attr in ("text", "tex_string"):
        try:
            value = getattr(mob, attr, "")
        except Exception:  # noqa: BLE001
            continue
        if isinstance(value, str) and value.strip():
            compact = " ".join(value.split())
            return compact[:48] + ("…" if len(compact) > 48 else "")
    return ""


def _severity_for(ratio: float, duration_s: float, *, transient: bool = False) -> str:
    if transient:
        return "low"
    if ratio >= 0.35 or (ratio >= 0.15 and duration_s >= 1.5):
        return "high"
    if ratio >= 0.12 or duration_s >= 1.0:
        return "medium"
    return "low"


def _suggest_repair(name_a: str, name_b: str, box_a, box_b, hit) -> str:
    push_x = (hit[1] - hit[0]) + 0.15
    push_y = (hit[3] - hit[2]) + 0.15
    cx_a, cx_b = (box_a[0] + box_a[1]) / 2.0, (box_b[0] + box_b[1]) / 2.0
    cy_a, cy_b = (box_a[2] + box_a[3]) / 2.0, (box_b[2] + box_b[3]) / 2.0
    if push_x <= push_y:
        dx = push_x if cx_b >= cx_a else -push_x
        move = f"move {name_b} by ({dx:+.2f}, 0.00)"
    else:
        dy = push_y if cy_b >= cy_a else -push_y
        move = f"move {name_b} by (0.00, {dy:+.2f})"
    both_text = name_a.split("#")[0] in _TEXT_TYPES and name_b.split("#")[0] in _TEXT_TYPES
    if both_text:
        return (f"{move}, or stack both in one VGroup(...).arrange(DOWN, buff=0.3) "
                f"so only one focal label shows per beat")
    return (f"{move}, or sequence them (FadeOut the finished one before the next "
            f"fades in) so only one focal object owns that region")


def main() -> int:
    scene_path, class_name, report_path, fps = sys.argv[1:5]
    tex_dir = sys.argv[5] if len(sys.argv) > 5 else ""
    report: dict = {"ok": False, "error": "", "duration_s": 0.0, "plays": 0, "off_frame": [],
                    "overlaps": [], "events": []}

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
    # Persistent overlap pairs across beat boundaries: key -> worst observation.
    # Keyed by (cls, id) so adding/removing mobjects cannot shift identities.
    tracked: dict[tuple[tuple[str, int], tuple[str, int]], dict] = {}
    prev_snapshot: dict[tuple[str, int], dict] = {}

    def _is_backdrop(bounds) -> bool:
        left, right, bottom, top = bounds
        return (
            right - left >= 2 * half_w * 0.97 and top - bottom >= 2 * half_h * 0.97
            and abs((left + right) / 2) < 1.0 and abs((top + bottom) / 2) < 1.0
            and right - left <= 2 * half_w * 1.6 and top - bottom <= 2 * half_h * 1.6
        )

    def _fixed_ids(scene) -> set[int]:
        """Mobjects fixed to the camera frame (screen space, not world space)."""
        ids: set[int] = set()
        holders = [getattr(scene, "camera", None), getattr(scene, "renderer", None)]
        holders += [getattr(h, "camera", None) for h in list(holders)]
        for holder in holders + [scene]:
            if holder is None:
                continue
            for attr in ("fixed_in_frame_mobjects", "fixed_mobjects"):
                try:
                    mobjs = getattr(holder, attr, None)
                except Exception:  # noqa: BLE001
                    continue
                if not mobjs:
                    continue
                try:
                    for member in list(mobjs):
                        ids.add(id(member))
                except Exception:  # noqa: BLE001
                    continue
        return ids

    def _allowlisted(entry_a, entry_b, hit, panels) -> bool:
        """True when an overlap is a deliberate relation, not a layout bug."""
        cls_a, cls_b = entry_a["cls"], entry_b["cls"]
        box_a, box_b = entry_a["bounds"], entry_b["bounds"]
        area_a, area_b = entry_a["area"], entry_b["area"]
        smaller, larger = min(area_a, area_b), max(area_a, area_b)
        ratio = _box_area(hit) / smaller if smaller > 1e-12 else 0.0
        # Edges merely touching.
        if ratio < 0.03:
            return True
        # Deliberate compositing flag set by curated/explanation layers.
        if entry_a.get("composite") or entry_b.get("composite"):
            return True
        # Comet trails follow their source by design.
        if cls_a in _TRAIL_TYPES or cls_b in _TRAIL_TYPES:
            return True
        # Framing boxes/panels/caption bands around their content.
        if cls_a in _FRAMING_TYPES and _center_inside(box_a, box_b):
            return True
        if cls_b in _FRAMING_TYPES and _center_inside(box_b, box_a):
            return True
        # Two objects sharing one panel (caption + title under the caption
        # band) are one deliberate composition, not a collision.
        for panel in panels:
            if _center_inside(panel, box_a) and _center_inside(panel, box_b):
                return True
        # A much larger object fully containing a small one (sectors inside
        # their orbit's span, badges on a panel) is deliberate framing.
        if larger > 1e-12 and smaller / larger < 1.0 / 3.0 and (
                _contains(box_a, box_b) or _contains(box_b, box_a)):
            return True
        # Translucent halos/glows over their source (star glow, bloom).
        if _center_inside(box_a, box_b) and entry_a.get("opacity", 1.0) < 0.5:
            return True
        if _center_inside(box_b, box_a) and entry_b.get("opacity", 1.0) < 0.5:
            return True
        # Curves live inside their axes: crossings are the plot, not clutter.
        if cls_a in _AXES_TYPES and _center_inside(box_a, box_b):
            return True
        if cls_b in _AXES_TYPES and _center_inside(box_b, box_a):
            return True
        # Axis labels hug their axes; only a deep bite is a real collision.
        if (cls_a in _AXES_TYPES and cls_b in _TEXT_TYPES and ratio < 0.25) or (
                cls_b in _AXES_TYPES and cls_a in _TEXT_TYPES and ratio < 0.25):
            return True
        # Attached labels may kiss their referent.
        if (cls_a in _TEXT_TYPES or cls_b in _TEXT_TYPES) and ratio < 0.12:
            return True
        # Small markers sitting on curves (dots, arrow tips).
        if smaller < 0.06 and larger > 1e-12 and _box_area(hit) / larger < 0.06:
            return True
        return False

    def inspect(scene, call: str) -> None:
        report["plays"] += 1
        time_s = round(exact["seconds"], 2)
        fixed = _fixed_ids(scene)
        snapshot: dict[tuple[str, int], dict] = {}
        for index, mob in enumerate(list(getattr(scene, "mobjects", []))):
            bounds = _bounds(mob)
            if bounds is None or not _visible(mob):
                continue
            left, right, bottom, top = bounds
            # A full-screen backdrop is meant to overflow the frame slightly.
            if _is_backdrop(bounds):
                continue
            over = max(-half_w - left, right - half_w, -half_h - bottom, top - half_h)
            if over > margin:
                name = type(mob).__name__
                key = (name, "x" if max(-half_w - left, right - half_w) >= max(-half_h - bottom, top - half_h) else "y")
                if key not in seen:
                    seen.add(key)
                    report["off_frame"].append({
                        "mobject": name, "time_s": time_s, "after": call,
                        "bounds": [round(v, 2) if abs(v) < 1e6 else (1e6 if v > 0 else -1e6) for v in bounds],
                        "overflow": round(min(over, 1e6), 2),
                    })
                    if len(report["off_frame"]) >= 12:
                        pass
            cls = type(mob).__name__
            try:
                composite = bool(getattr(mob, "_aetherlab_allow_overlap", False))
            except Exception:  # noqa: BLE001
                composite = False
            snapshot[(cls, id(mob))] = {
                "name": f"{cls}#{index}", "cls": cls, "bounds": bounds,
                "area": _box_area(bounds), "label": _mob_label(mob),
                "space": "fixed" if id(mob) in fixed else "world",
                "opacity": _max_opacity(mob), "composite": composite,
            }
        _track_overlaps(snapshot, prev_snapshot, time_s)
        prev_snapshot.clear()
        prev_snapshot.update(snapshot)

    def _track_overlaps(snapshot, previous, time_s: float) -> None:
        entries = sorted(snapshot.items(), key=lambda item: item[1]["name"])
        panels = [entry["bounds"] for _, entry in entries
                  if entry["cls"] in _FRAMING_TYPES]
        for pos_a in range(len(entries)):
            for pos_b in range(pos_a + 1, len(entries)):
                (key_a, entry_a), (key_b, entry_b) = entries[pos_a], entries[pos_b]
                # World-space and fixed-in-frame mobjects live in different
                # coordinate systems (camera moves one, not the other); a
                # camera zoom/pan is affine, so within one space the overlap
                # relation is camera-invariant and needs no transform.
                if entry_a["space"] != entry_b["space"]:
                    continue
                pair = tuple(sorted((key_a, key_b)))
                box_a, box_b = entry_a["bounds"], entry_b["bounds"]
                hit = _intersect(box_a, box_b)
                if hit is not None and not _allowlisted(entry_a, entry_b, hit, panels):
                    smaller = min(entry_a["area"], entry_b["area"])
                    ratio = _box_area(hit) / smaller if smaller > 1e-12 else 0.0
                    prior = tracked.get(pair)
                    first_t = prior["first_t"] if prior else time_s
                    duration = round(time_s - first_t, 2)
                    if prior is None or ratio >= prior["ratio"]:
                        tracked[pair] = {
                            "name_a": entry_a["name"], "name_b": entry_b["name"],
                            "label_a": entry_a["label"], "label_b": entry_b["label"],
                            "first_t": first_t, "last_t": time_s, "duration_s": duration,
                            "ratio": round(ratio, 4), "box_a": box_a, "box_b": box_b,
                            "hit": hit, "transient": False,
                        }
                    else:
                        prior["last_t"] = time_s
                        prior["duration_s"] = duration
                    continue
                # No boundary overlap: check the swept boxes for a crossing
                # DURING the motion between the two boundary snapshots.
                prev_a, prev_b = previous.get(key_a), previous.get(key_b)
                if prev_a is None or prev_b is None:
                    continue
                swept_a = _union(prev_a["bounds"], box_a)
                swept_b = _union(prev_b["bounds"], box_b)
                swept_hit = _intersect(swept_a, swept_b)
                if swept_hit is None or _intersect(prev_a["bounds"], prev_b["bounds"]) is not None:
                    continue
                if _allowlisted(entry_a, entry_b, swept_hit, panels):
                    continue
                if pair not in tracked:
                    tracked[pair] = {
                        "name_a": entry_a["name"], "name_b": entry_b["name"],
                        "label_a": entry_a["label"], "label_b": entry_b["label"],
                        "first_t": time_s, "last_t": time_s, "duration_s": 0.0,
                        "ratio": 0.0, "box_a": box_a, "box_b": box_b,
                        "hit": swept_hit, "transient": True,
                    }

    def _finalize_overlaps() -> None:
        rank = {"high": 0, "medium": 1, "low": 2}
        findings = []
        for item in tracked.values():
            severity = _severity_for(item["ratio"], item["duration_s"],
                                     transient=item["transient"])

            def _clean(box):
                return [round(v, 2) if abs(v) < 1e6 else (1e6 if v > 0 else -1e6)
                        for v in box]

            findings.append({
                "a": item["name_a"], "b": item["name_b"],
                "label_a": item["label_a"], "label_b": item["label_b"],
                "time_s": item["first_t"], "duration_s": item["duration_s"],
                "bounds_a": _clean(item["box_a"]), "bounds_b": _clean(item["box_b"]),
                "overlap": _clean(item["hit"]),
                "bounds": _clean(item["hit"]),
                "overlap_ratio": item["ratio"], "transient": item["transient"],
                "severity": severity,
                "repair": _suggest_repair(item["name_a"], item["name_b"],
                                          item["box_a"], item["box_b"], item["hit"]),
            })
        findings.sort(key=lambda f: (rank.get(f["severity"], 3), -f["overlap_ratio"]))
        report["overlaps"] = findings[:_MAX_OVERLAPS]

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
    try:
        _finalize_overlaps()
    except Exception:  # noqa: BLE001 - overlap detection is advisory
        report["overlaps"] = []
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
