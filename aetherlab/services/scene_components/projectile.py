"""Curated component: projectile motion (UNT kinematics staple).

Integrates the real point-mass equations — x'' = 0, y'' = -g — through the
same scipy / AST-allow-listed path as every other numeric result, with the UNT
convention g = 10 m/s². It bakes the trajectory into a self-contained Manim
scene: launch pad with the angle arc, the projectile with a trail and a live
velocity vector split into constant-vx / changing-vy components, a ticking
t·vx·vy readout, and a finale revealing the apex height H and range R markers
with the range formula.

Depends only on ``manim`` + ``numpy``. Selected when the solver's domain is a
projectile / throw / ballistics problem.
"""

from __future__ import annotations

import math
from typing import Any

_MAX_POINTS = 200
_G = 10.0  # UNT convention
_V0 = 20.0
_ANGLE_DEG = 60.0


def params(solver: Any) -> dict[str, float]:
    """Resolved launch parameters; shared by build() and explain()."""
    variables = {str(k): v for k, v in dict(getattr(solver, "variables", {}) or {}).items()}
    v0 = _clamp(variables.get("v0", variables.get("v", _V0)), 1.0, 100.0)
    angle = _clamp(
        variables.get("angle", variables.get("alpha", _ANGLE_DEG)), 5.0, 85.0
    )
    return {"v0": v0, "angle_deg": angle, "g": _G}


def theory(v0: float, angle_deg: float, g: float = _G) -> dict[str, float]:
    """Closed-form flight time / range / apex (cross-checks the integration)."""
    a = math.radians(angle_deg)
    t = 2.0 * v0 * math.sin(a) / g
    return {
        "flight_time": t,
        "range": v0 * math.cos(a) * t,
        "apex": (v0 * math.sin(a)) ** 2 / (2.0 * g),
    }


def build(class_name: str, solver: Any) -> str | None:
    """Return a projectile-motion scene, or None if it cannot integrate."""
    try:
        import numpy as np
    except Exception:  # noqa: BLE001
        return None

    p = params(solver)
    v0, angle_deg = p["v0"], p["angle_deg"]
    a = math.radians(angle_deg)
    th = theory(v0, angle_deg)

    spec = {
        "state": ["x", "y", "vx", "vy"],
        "rhs": ["vx", "vy", "0", "-g"],
        "initial": [0.0, 0.0, v0 * math.cos(a), v0 * math.sin(a)],
        "t_range": [0.0, th["flight_time"]],
        "observe": "x",
    }
    try:
        from aetherlab.services.numeric import solve_numeric

        sol = solve_numeric(spec, {"g": _G}, max_points=_MAX_POINTS)
    except Exception:  # noqa: BLE001 — composition must never crash the pipeline
        return None
    if not sol.ok or len(sol.t) < 12:
        return None

    xs = np.array(sol.states["x"], dtype=float)
    ys = np.array(sol.states["y"], dtype=float)
    vxs = np.array(sol.states["vx"], dtype=float)
    vys = np.array(sol.states["vy"], dtype=float)
    ts = np.array(sol.t, dtype=float)
    if not (xs.size == ys.size == vxs.size == vys.size == ts.size):
        return None
    if not all(bool(np.all(np.isfinite(arr))) for arr in (xs, ys, vxs, vys)):
        return None
    ys = np.maximum(ys, 0.0)  # integration overshoot never digs under the ground

    flight_range = float(xs.max())
    apex_h = float(ys.max())
    flight_t = float(ts.max())

    # Fit to frame: world x in [0, R], y in [0, H]; ground sits low, title up.
    scale = min(10.5 / max(flight_range, 1e-6), 4.55 / max(apex_h, 1e-6))
    ground_y = -2.6
    x0 = -0.5 * flight_range * scale

    def screen(x: float, y: float) -> list[float]:
        return [round(float(x0 + x * scale), 4), round(float(ground_y + y * scale), 4)]

    path = [screen(x, y) for x, y in zip(xs, ys)]
    apex_pt = screen(float(xs[int(np.argmax(ys))]), apex_h)
    land_pt = screen(flight_range, 0.0)
    v_scale = 0.11 * scale / 0.303  # velocity arrow gain, resolution-independent-ish

    title = _shorten(
        getattr(solver, "summary", "") or "Projectile motion (UNT kinematics)", 60
    )
    from aetherlab.services.scene_components.motion import mathtex_or_text

    formula_block = mathtex_or_text(
        "formula",
        r"R = \frac{v_0^2 \sin 2\alpha}{g}",
        "R = v₀²·sin2α / g",
        scale=0.6,
        color="BLUE_B",
    )
    # The template slot sits inside construct(): indent to the method level.
    formula_block = "\n".join(
        f"        {line}" if line.strip() else line
        for line in formula_block.splitlines()
    )
    return _TEMPLATE.format(
        class_name=class_name,
        path=repr(path),
        vxs=repr([round(float(v), 4) for v in vxs]),
        vys=repr([round(float(v), 4) for v in vys]),
        ts=repr([round(float(t), 4) for t in ts]),
        apex_pt=repr(apex_pt),
        land_pt=repr(land_pt),
        apex_txt=repr(f"H = {apex_h:.1f} м"),
        range_txt=repr(f"R = {flight_range:.1f} м"),
        formula_block=formula_block,
        angle_txt=repr(f"α = {angle_deg:g}°"),
        v_scale=repr(round(v_scale, 4)),
        angle_rad=repr(round(a, 6)),
        ground_y=repr(ground_y),
        x0=repr(round(x0, 4)),
        title=repr(title),
    )


def _clamp(value: Any, lo: float, hi: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = lo
    return max(lo, min(hi, v))


def _shorten(text: str, limit: int) -> str:
    compact = " ".join(str(text).split())
    return compact if len(compact) <= limit else compact[: limit - 1] + "…"


_TEMPLATE = '''\
"""Generated by AetherLab - projectile motion (curated component)."""

import numpy as np
from manim import *


class {class_name}(Scene):
    def construct(self):
        raw = {path}
        vxs = {vxs}
        vys = {vys}
        ts = {ts}
        path = [np.array([x, y, 0.0]) for x, y in raw]
        apex_pt = np.array({apex_pt} + [0.0])
        land_pt = np.array({land_pt} + [0.0])
        v_scale = {v_scale}
        ground_y = {ground_y}
        x0 = {x0}
        n = len(path)

        title = Text({title}).scale(0.46).to_edge(UP)
        title.set_z_index(5)

        ground = Line([-7.0, ground_y, 0.0], [7.0, ground_y, 0.0],
                      color=GREY_B, stroke_width=3)
        ground.set_z_index(0)
        pad = Rectangle(width=0.5, height=0.18, color=GREY_A,
                        fill_color=GREY_A, fill_opacity=1.0, stroke_width=0)
        pad.move_to([x0, ground_y + 0.09, 0.0])
        pad.set_z_index(0)
        arc = Arc(radius=0.55, start_angle=0.0, angle={angle_rad},
                  arc_center=[x0, ground_y, 0.0], color=GOLD, stroke_width=3)
        arc.set_z_index(1)
        angle_lab = Text({angle_txt}, color=GOLD).scale(0.3)
        angle_lab.next_to(arc, UP + RIGHT, buff=0.08)
        angle_lab.set_z_index(5)

        idx = ValueTracker(0.0)

        def sample(arr):
            # Continuous path: lerp between bracketing samples so the flight
            # glides instead of jumping once per baked sample (motion.py).
            v = float(np.clip(idx.get_value(), 0, n - 1))
            lo = min(int(v), n - 1)
            hi = min(lo + 1, n - 1)
            f = v - lo
            return arr[lo] * (1.0 - f) + arr[hi] * f

        def body_pt():
            return sample(path)

        def vel_vec():
            return np.array([sample(vxs) * v_scale, sample(vys) * v_scale, 0.0])

        body = always_redraw(lambda: Dot(body_pt(), color=TEAL, radius=0.13))
        trail = TracedPath(body_pt, stroke_color=TEAL, stroke_width=3.0,
                           dissipating_time=6.0)
        trail.set_z_index(1)
        vel = always_redraw(lambda: Arrow(
            body_pt(), body_pt() + vel_vec(), color=YELLOW, buff=0.1,
            stroke_width=4, max_tip_length_to_length_ratio=0.18))
        vel.set_z_index(2)
        comp_x = always_redraw(lambda: DashedLine(
            body_pt(), body_pt() + np.array([vel_vec()[0], 0.0, 0.0]),
            color=GREEN, stroke_width=2, dashed_ratio=0.7))
        comp_y = always_redraw(lambda: DashedLine(
            body_pt(), body_pt() + np.array([0.0, vel_vec()[1], 0.0]),
            color=RED, stroke_width=2, dashed_ratio=0.7))
        # Deliberate curated composition: the velocity vector and its
        # components emanate from the body, so their contact with it is the
        # exhibit, not clutter (preflight honors this flag).
        vel._aetherlab_allow_overlap = True
        comp_x._aetherlab_allow_overlap = True
        comp_y._aetherlab_allow_overlap = True

        def readout_text():
            return (f"t = {{sample(ts):.2f}} с   "
                    f"vx = {{sample(vxs):.1f}} м/с   "
                    f"vy = {{sample(vys):.1f}} м/с")

        readout = always_redraw(lambda: Text(readout_text()).scale(0.32).to_edge(DOWN))
        readout.set_z_index(5)

        apex_line = DashedLine([apex_pt[0], ground_y, 0.0], apex_pt,
                               color=GREY_A, stroke_width=2, dashed_ratio=0.6)
        apex_line.set_z_index(1)
        apex_lab = Text({apex_txt}, color=GOLD).scale(0.32)
        apex_lab.move_to([apex_pt[0] - 1.35, (apex_pt[1] + ground_y) / 2.0, 0.0])
        apex_lab.set_z_index(5)
        range_line = DashedLine([land_pt[0], ground_y + 0.02, 0.0],
                                [land_pt[0], ground_y + 0.9, 0.0],
                                color=GREY_A, stroke_width=2, dashed_ratio=0.6)
        range_line.set_z_index(1)
        range_lab = Text({range_txt}, color=GOLD).scale(0.32)
        range_lab.next_to(range_line, UP, buff=0.12)
        range_lab.set_z_index(5)
{formula_block}
        formula.move_to([3.6, 2.5, 0.0])

        self.play(FadeIn(title), Create(ground), FadeIn(pad), Create(arc),
                  FadeIn(angle_lab), run_time=1.0)
        self.add(trail, comp_x, comp_y, vel, body, readout)
        self.play(idx.animate.set_value(float(n - 1)), run_time=6.0, rate_func=linear)
        self.play(FadeIn(apex_line), FadeIn(apex_lab), FadeIn(range_line),
                  FadeIn(range_lab), FadeIn(formula), run_time=1.2)
        self.wait(0.5)
'''
