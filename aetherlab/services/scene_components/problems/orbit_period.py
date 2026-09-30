"""Problem video: how long is one lap of the ISS?

"The International Space Station orbits h km above Earth. How long does one lap
take?"

Device: Newton's cannon. A cannon on a (hugely exaggerated) mountain fires
faster and faster. Slow shots fall back to the ground; a fast enough shot falls
around the Earth forever. That is what an orbit is. The solve sets gravity equal
to the pull needed to curve the path. The check is a time-lapse of the
numerically integrated orbit, with the lap closing just as the clock reaches the
computed period. What-if: how high must a satellite be to take exactly one day?
Zoom out to the geostationary ring.

Solving arc (subgoal labels): 1 the idea, 2 solve, 3 check, 4 what if.
Every orbit shown is integrated with ``solve_numeric``.
"""

from __future__ import annotations

import math
import re
from typing import Any

_GM = 3.986004418e14        # Earth, m^3/s^2
_R = 6.371e6                # Earth mean radius, m
_SIDEREAL_DAY = 86164.1     # s: one turn of the Earth relative to the stars
_DEFAULT_ALT_KM = 420.0
_EARTH_PX = 2.0             # Earth radius on screen (scene units)


_SUPERSCRIPT = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")


def _sci(value: float) -> str:
    """3 significant figures with a real superscript exponent, e.g. 6.79 × 10⁶."""
    exponent = int(math.floor(math.log10(abs(value))))
    return f"{value / 10 ** exponent:.3g} × 10{str(exponent).translate(_SUPERSCRIPT)}"


def _text(solver: Any) -> str:
    return " ".join([" ".join(getattr(solver, "keywords", []) or []),
                     getattr(solver, "summary", "") or ""]).lower()


def params(solver: Any) -> dict[str, float]:
    variables = {str(k).lower(): v for k, v in dict(getattr(solver, "variables", {}) or {}).items()}
    alt = None
    for name in ("altitude_km", "altitude", "height_km", "height", "h"):
        try:
            v = float(variables[name])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(v) and v > 0:
            alt = v / 1000.0 if v > 1e5 else v      # a value that large is in metres
            break
    alt = alt if alt and 150.0 <= alt <= 30000.0 else _DEFAULT_ALT_KM
    return {"altitude_km": alt}


# Atomic "orbits" (Bohr model) and quantum problems are not Earth orbits; "h"
# there is Planck's constant, not an altitude.
_ATOMIC_CUES = ("electron", "atom", "bohr", "nucleus", "hydrogen", "quantum", "planck", "photon")


def matches(solver: Any) -> bool:
    """An Earth-orbit period problem (satellite / ISS / low orbit)."""
    text = _text(solver)
    if any(cue in text for cue in _ATOMIC_CUES):
        return False
    # Whole-word "ISS": the bare substring also occurs in "emission",
    # "transmission" and "mission".
    iss = re.search(r"\biss\b", text) is not None or "space station" in text
    topical = iss or any(w in text for w in ("satellite", "orbit period", "orbital period",
                                             "low earth orbit", "one lap", "orbits"))
    variables = {str(k).lower() for k in (getattr(solver, "variables", {}) or {})}
    has_alt = bool(variables & {"altitude_km", "altitude", "height_km", "height", "h"})
    return topical and (has_alt or iss)


def _cannon() -> list[list[list[float]]] | None:
    """Three shots from the mountain in screen units (GM = 1), cut at impact."""
    from aetherlab.services.numeric import solve_numeric

    r0 = _EARTH_PX + 0.45
    v_circ = math.sqrt(1.0 / r0)
    shots = []
    for frac, t_end in ((0.55, 6.0), (0.78, 12.0), (1.0, 2 * math.pi * r0 ** 1.5)):
        sol = solve_numeric({
            "state": ["x", "y", "vx", "vy"],
            "rhs": ["vx", "vy", "-x/(x*x+y*y)**1.5", "-y/(x*x+y*y)**1.5"],
            "initial": [0.0, r0, frac * v_circ, 0.0],
            "t_range": [0.0, t_end],
            "observe": "x",
        }, {}, max_points=300)
        if not sol.ok:
            return None
        pts = []
        for x, y in zip(sol.series("x"), sol.series("y")):
            pts.append([round(float(x), 4), round(float(y), 4)])
            if math.hypot(x, y) < _EARTH_PX and len(pts) > 3:
                break
        shots.append(pts)
    return shots


def _solve(p: dict[str, float]) -> dict[str, Any] | None:
    from aetherlab.services.numeric import solve_numeric

    r = _R + p["altitude_km"] * 1000.0
    v = math.sqrt(_GM / r)
    period = 2 * math.pi * r / v
    # the numerically integrated orbit, in screen units, sampled uniformly in time
    k = _EARTH_PX / _R
    sol = solve_numeric({
        "state": ["x", "y", "vx", "vy"],
        "rhs": ["vx", "vy", "-mu*x/(x*x+y*y)**1.5", "-mu*y/(x*x+y*y)**1.5"],
        "initial": [0.0, r, -v, 0.0],
        "t_range": [0.0, period],
        "observe": "x",
    }, {"mu": _GM}, max_points=361)
    if not sol.ok:
        return None
    xs, ys = sol.series("x"), sol.series("y")
    closure = math.hypot(xs[-1] - xs[0], ys[-1] - ys[0]) / r   # lap closes on the start point
    geo_r = (_GM * _SIDEREAL_DAY ** 2 / (4 * math.pi ** 2)) ** (1 / 3)
    return {
        "r": r, "v": v, "period": period, "closure": closure, "geo_r": geo_r,
        "orbit": [[round(float(x * k), 4), round(float(y * k), 4)] for x, y in zip(xs, ys)],
        "cannon": _cannon(),
    }


def build(class_name: str, solver: Any) -> str | None:
    p = params(solver)
    s = _solve(p)
    if s is None or s["cannon"] is None or s["closure"] > 0.01:
        return None
    alt = p["altitude_km"]
    minutes = s["period"] / 60.0
    laps = 86400.0 / s["period"]
    geo_alt = (s["geo_r"] - _R) / 1000.0
    return _TEMPLATE.format(
        class_name=class_name, orbit=repr(s["orbit"]), cannon=repr(s["cannon"]),
        orbit_px=round(_EARTH_PX * s["r"] / _R, 4), geo_px=round(_EARTH_PX * s["geo_r"] / _R, 4),
        earth_px=_EARTH_PX, period_min=round(minutes, 3),
        problem1=repr(f"The International Space Station orbits {alt:.0f} km above the ground."),
        problem2=repr("How long does one lap around the Earth take?"),
        brief=repr(f"orbit {alt:.0f} km up:  one lap takes?"),
        to_scale=repr(f"drawn to scale:  {alt:.0f} km\nis this thin"),
        shot1=repr("too slow: it falls back to the ground"),
        shot2=repr("faster: it lands much farther away"),
        shot3=repr("fast enough: the ground curves away as fast as it falls"),
        idea=repr("an orbit is falling around the Earth, forever"),
        eq1=repr("gravity pulls just enough to bend the path into a circle:"),
        eq2=repr("GMm / r² = m·v² / r     so     v = √(GM / r)"),
        eq3=repr(f"r = 6371 + {alt:.0f} = {s['r'] / 1000:,.0f} km"),
        eq4=repr(f"v = √(3.986 × 10¹⁴ / {_sci(s['r'])}) = {s['v'] / 1000:.2f} km/s"),
        eq5=repr(f"one lap:  T = 2πr / v = {s['period']:,.0f} s = {minutes:.1f} min"),
        clock_note=repr(f"lap complete: {minutes:.1f} min, as computed"),
        sunrise=repr(f"{laps:.1f} laps a day: the crew sees {laps:.0f} sunrises every 24 hours"),
        whatif_q=repr("How high for a lap that takes exactly one day?"),
        whatif_eq=repr(f"r³ = GM·T² / (4π²),  T = 23 h 56 min   →   r = {s['geo_r'] / 1000:,.0f} km"),
        whatif_a=repr(f"{geo_alt:,.0f} km up: it keeps pace with the turning Earth"),
        answer=repr(f"Answer: one lap takes {minutes:.1f} minutes"),
        answer2=repr(f"moving at {s['v'] / 1000:.2f} km/s, {laps:.1f} laps a day"),
    )


def check_lines(solver: Any) -> list[str]:
    """What AetherLab's own simulation says, for the study document's checks."""
    p = params(solver)
    s = _solve(p)
    if s is None:
        return []
    return [f"Numerically integrated orbit {p['altitude_km']:.0f} km up: one lap takes "
            f"{s['period'] / 60:.1f} min at {s['v'] / 1000:.2f} km/s, and the path closes on itself "
            f"to within {100 * s['closure']:.2f}% of the radius."]


_TEMPLATE = '''\
"""Generated by AetherLab - problem: how long is one lap of the ISS?"""

import numpy as np
from manim import *


class {class_name}(Scene):
    def construct(self):
        orbit = {orbit}
        cannon = {cannon}
        orbit_px, geo_px, earth_px = {orbit_px}, {geo_px}, {earth_px}
        period_min = {period_min}
        center = np.array([0.0, -0.35, 0.0])

        def chip(text):
            return Text(text, font_size=24, color=YELLOW_A).to_corner(UL, buff=0.3)

        def pt(xy):
            return center + np.array([xy[0], xy[1], 0.0])

        earth = Circle(radius=earth_px, color=BLUE_D, fill_color=BLUE_E, fill_opacity=1,
                       stroke_width=2).move_to(center)
        land = VGroup(*[Ellipse(width=w, height=h, color=GREEN_E, fill_color=GREEN_E,
                                fill_opacity=0.9, stroke_width=0).move_to(center + np.array(off))
                        for w, h, off in ((1.1, 0.7, [-0.6, 0.6, 0]), (0.8, 1.1, [0.8, -0.3, 0]),
                                          (0.6, 0.4, [-0.9, -0.9, 0]))])
        air = Circle(radius=earth_px + 0.06, color=BLUE_B, stroke_width=4, stroke_opacity=0.5).move_to(center)
        planet = VGroup(air, earth, land)

        def fit(m, width=13.0):
            # Cloud and local fonts differ in width: never let a line leave the frame.
            if m.width > width:
                m.scale_to_fit_width(width)
            return m

        # The problem, drawn to scale.
        title = Text("How long is one lap of the ISS?", font_size=40, color=YELLOW).to_edge(UP, buff=0.3)
        p1 = fit(Text({problem1}, font_size=26)).next_to(title, DOWN, buff=0.2)
        p2 = fit(Text({problem2}, font_size=26, color=TEAL_A)).next_to(p1, DOWN, buff=0.1)
        ring = Circle(radius=orbit_px, color=GREY_B, stroke_width=1.5).move_to(center)
        iss = Dot(pt(orbit[0]), color=WHITE, radius=0.08).set_z_index(5)
        scale_note = Text({to_scale}, font_size=24, color=GREY_A).move_to([4.6, 1.1, 0])
        pointer = Arrow(scale_note.get_left(), pt(orbit[0]) + np.array([0.12, 0.0, 0]), buff=0.15,
                        color=GREY_A, stroke_width=2, max_tip_length_to_length_ratio=0.1)
        self.play(Write(title), run_time=1.0)
        self.play(FadeIn(planet), FadeIn(p1), FadeIn(p2), run_time=1.2)
        self.play(Create(ring), GrowFromCenter(iss), run_time=1.0)
        self.play(FadeIn(scale_note), GrowArrow(pointer), run_time=0.8)
        self.wait(3.2)

        # 1. The idea: Newton's cannon.
        brief = fit(Text({brief}, font_size=26, color=GREY_A), 7.4).to_corner(UR, buff=0.3)
        step1 = chip("1 · the idea: Newton's cannon")
        self.play(FadeOut(title), FadeOut(p1), FadeOut(p2), FadeOut(scale_note), FadeOut(pointer),
                  FadeOut(ring), FadeOut(iss), FadeIn(brief), FadeIn(step1), run_time=0.8)
        top = pt([0.0, earth_px])
        mountain = Polygon(top + LEFT * 0.35, top + UP * 0.42, top + RIGHT * 0.35, color=GREY_B,
                           fill_color=GREY_D, fill_opacity=1, stroke_width=2)
        barrel = Rectangle(width=0.32, height=0.1, color=GREY_A, fill_color=GREY_A,
                           fill_opacity=1).move_to(top + UP * 0.45 + RIGHT * 0.12)
        self.play(FadeIn(mountain), FadeIn(barrel), run_time=0.7)
        notes = [{shot1}, {shot2}, {shot3}]
        colors = [RED, ORANGE, GREEN]
        run_times = [1.6, 2.4, 4.2]
        shown = VGroup()
        for i in range(3):
            path = VMobject(color=colors[i], stroke_width=3)
            path.set_points_as_corners([pt(q) for q in cannon[i]])
            ball = Dot(pt(cannon[i][0]), color=colors[i], radius=0.07)
            note = Text(notes[i], font_size=24, color=colors[i]).move_to([0, -3.35, 0])
            self.play(FadeIn(note), run_time=0.4)
            self.play(Create(path), MoveAlongPath(ball, path), run_time=run_times[i], rate_func=linear)
            shown.add(path, ball)
            self.play(FadeOut(note), run_time=0.3)
        idea = Text({idea}, font_size=28, color=YELLOW_A).move_to([0, -3.35, 0])
        self.play(FadeIn(idea), run_time=0.7)
        self.wait(2.2)

        # 2. Solve: gravity supplies exactly the pull the curve needs.
        step2 = chip("2 · solve")
        self.play(FadeOut(VGroup(shown, mountain, barrel, idea)), FadeOut(step1), FadeIn(step2),
                  planet.animate.scale(0.45).move_to([-4.7, -0.9, 0]), run_time=1.0)
        lines = VGroup(
            Text({eq1}, font_size=26, color=GREY_A),
            Text({eq2}, font_size=30),
            Text({eq3}, font_size=28, color=BLUE_B),
            Text({eq4}, font_size=28, color=BLUE_B),
            Text({eq5}, font_size=30, color=YELLOW),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.34).move_to([1.3, -0.2, 0])
        for i, line in enumerate(lines):
            self.play(FadeIn(line, shift=0.15 * RIGHT), run_time=0.8)
            self.wait(1.3 if i else 0.6)
        self.wait(1.4)

        # 3. Check: time-lapse of the integrated orbit against a clock.
        step3 = chip("3 · check it: one lap, timed")
        self.play(FadeOut(lines), FadeOut(step2), FadeIn(step3),
                  planet.animate.scale(1 / 0.45).move_to(center), run_time=1.0)
        idx = ValueTracker(0.0)

        def sat_pt():
            return pt(orbit[min(int(idx.get_value()), len(orbit) - 1)])

        ring2 = Circle(radius=orbit_px, color=GREY_B, stroke_width=1.2, stroke_opacity=0.5).move_to(center)
        sat = always_redraw(lambda: Dot(sat_pt(), color=WHITE, radius=0.08).set_z_index(5))
        trail = TracedPath(sat_pt, stroke_color=YELLOW, stroke_width=3)
        timer = always_redraw(lambda: Text(
            f"{{period_min * idx.get_value() / (len(orbit) - 1):5.1f}} min", font_size=34,
            color=YELLOW).move_to([4.8, 2.6, 0]))
        timelapse = Text("time-lapse", font_size=22, color=GREY_B).move_to([4.8, 2.05, 0])
        self.play(Create(ring2), FadeIn(timelapse), run_time=0.6)
        self.add(trail, sat, timer)
        self.play(idx.animate.set_value(float(len(orbit) - 1)), run_time=8.0, rate_func=linear)
        done = Text({clock_note}, font_size=26, color=GREEN_B).move_to([0, -3.4, 0])
        self.play(Flash(sat, color=GREEN), FadeIn(done), run_time=0.9)
        self.wait(1.2)
        sun = Text({sunrise}, font_size=24, color=GREY_A).move_to([0, -2.85, 0])
        self.play(FadeIn(sun), run_time=0.7)
        self.wait(2.2)

        # 4. What if: a one-day orbit. Zoom out to find it.
        step4 = chip("4 · what if?")
        for m in (sat, timer):
            m.clear_updaters()
        q = Text({whatif_q}, font_size=26, color=TEAL_A).move_to([0, -3.35, 0])
        self.play(FadeOut(VGroup(done, sun, timer, timelapse, trail)), FadeOut(step3), FadeIn(step4),
                  FadeIn(q), run_time=0.8)
        eq = fit(Text({whatif_eq}, font_size=26, color=WHITE)).move_to([0, 2.6, 0])
        self.play(FadeIn(eq), run_time=0.9)
        self.wait(1.4)
        zoom = 2.55 / geo_px      # the one-day ring lands at a fixed on-screen radius
        world = VGroup(planet, ring2, sat)
        self.play(world.animate.scale(zoom, about_point=center), run_time=2.0)
        geo_ring = Circle(radius=geo_px * zoom, color=TEAL, stroke_width=3).move_to(center)
        geo_sat = Dot(center + UP * geo_px * zoom, color=TEAL, radius=0.09)
        self.play(Create(geo_ring), GrowFromCenter(geo_sat), run_time=1.4)
        spin = VGroup(planet, geo_sat)
        a = Text({whatif_a}, font_size=26, color=TEAL).move_to([0, -3.35, 0])
        self.play(FadeOut(q), FadeIn(a), run_time=0.6)
        self.play(Rotate(spin, angle=TAU / 3, about_point=center), run_time=3.0, rate_func=linear)
        self.wait(1.0)

        answer = Text({answer}, font_size=32, color=YELLOW)
        answer2 = Text({answer2}, font_size=24, color=GREY_A)
        card_text = VGroup(answer, answer2).arrange(DOWN, buff=0.15)
        box = SurroundingRectangle(card_text, color=YELLOW, buff=0.22, corner_radius=0.12)
        card = VGroup(card_text, box).move_to([0, -0.35, 0])
        self.play(FadeOut(VGroup(world, geo_ring, geo_sat, eq, a)), run_time=0.8)
        self.play(FadeIn(card, scale=0.9), run_time=1.0)
        self.wait(4.0)
'''
