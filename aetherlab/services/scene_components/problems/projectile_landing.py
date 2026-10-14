"""Problem video: where does the kicked ball land?

"A ball is kicked at v m/s, θ° above level ground. How far away does it land,
and how long is it in the air?"

Device: two shadows. The ball's shadow on the ground glides at a steady speed,
while its shadow on a wall rises and falls like a ball thrown straight up. Each
shadow is a simple motion, and together they solve the problem: the wall
shadow gives the flight time, and the ground shadow turns that time into a
distance. Then the real flight (integrated numerically) lands on the flag at
the computed distance. What-if: at the same speed, 30° and 60° land on the same
spot, and 45° goes farthest.

Solving arc (subgoal labels): 1 picture it, 2 split the motion, 3 solve,
4 check, 5 what if.
"""

from __future__ import annotations

import math
from typing import Any

_G = 9.81
_DEFAULT_SPEED = 18.0
_DEFAULT_ANGLE = 40.0


def _num(variables: dict[str, Any], names: tuple[str, ...]) -> float | None:
    for name in names:
        if name in variables:
            try:
                v = float(variables[name])
            except (TypeError, ValueError):
                continue
            if math.isfinite(v):
                return v
    return None


def params(solver: Any) -> dict[str, float]:
    variables = {str(k).lower(): v for k, v in dict(getattr(solver, "variables", {}) or {}).items()}
    speed = _num(variables, ("speed", "v0", "v", "initial_speed", "launch_speed", "velocity", "u"))
    angle = _num(variables, ("angle", "theta", "launch_angle", "theta0", "elevation"))
    g = _num(variables, ("g", "gravity"))
    speed = speed if speed and 1.0 <= abs(speed) <= 200.0 else _DEFAULT_SPEED
    if angle is not None and 0.0 < angle < 1.6:
        angle = math.degrees(angle)          # a value this small is in radians
    angle = angle if angle and 5.0 <= angle <= 85.0 else _DEFAULT_ANGLE
    g = g if g and 0.5 <= g <= 30.0 else _G
    return {"speed": abs(speed), "angle": angle, "g": g}


# This video stages an oblique launch from level ground. Vertical throws and
# launches from a height (cliff, table, building) are different problems, and
# showing them as a 40-degree kick would draw the wrong trajectory.
_OTHER_GEOMETRY = ("straight up", "straight upward", "vertically up", "thrown vertically",
                   "launched vertically", "fired vertically", "straight down", "is dropped",
                   "thrown horizontally", "launched horizontally", "fired horizontally",
                   "kicked horizontally", "rolls off", "cliff", "building", "rooftop",
                   "tabletop", "off a table", "from a table", "tower", "bridge", "balcony")
_ANGLE_NAMES = ("angle", "theta", "launch_angle", "theta0", "elevation")


def matches(solver: Any) -> bool:
    """A kicked/thrown/launched-projectile problem with a launch speed given."""
    text = " ".join([" ".join(getattr(solver, "keywords", []) or []),
                     getattr(solver, "summary", "") or ""]).lower()
    variables = {str(k).lower(): v for k, v in dict(getattr(solver, "variables", {}) or {}).items()}
    angle = _num(variables, _ANGLE_NAMES)
    # "how far" / "lands" also describe braking cars and landing planes, so
    # they count only alongside a launch angle.
    topical = any(w in text for w in ("projectile", "kicked", "thrown", "launched", "cannon",
                                      "range of a")) or (
        angle is not None and any(w in text for w in ("how far", "lands"))
    )
    if any(w in text for w in _OTHER_GEOMETRY):
        return False
    if angle is not None:
        degrees = math.degrees(angle) if 0.0 < angle < 1.6 else angle
        if not 5.0 <= degrees <= 85.0:
            return False                 # 0 or 90 degrees: not an oblique launch
    has_speed = bool(set(variables) & {"speed", "v0", "v", "initial_speed", "launch_speed", "velocity", "u"})
    return topical and has_speed


def _solve(p: dict[str, float]) -> dict[str, Any] | None:
    from aetherlab.services.numeric import solve_numeric

    v, th, g = p["speed"], math.radians(p["angle"]), p["g"]
    vx, vy = v * math.cos(th), v * math.sin(th)
    t_flight = 2.0 * vy / g
    rng = vx * t_flight
    apex = vy * vy / (2.0 * g)
    sol = solve_numeric({
        "state": ["x", "y", "vx", "vy"],
        "rhs": ["vx", "vy", "0", "-g"],
        "initial": [0.0, 0.0, vx, vy],
        "t_range": [0.0, t_flight],
        "observe": "x",
    }, {"g": g}, max_points=241)
    if not sol.ok:
        return None
    xs, ys = list(sol.series("x")), list(sol.series("y"))
    what_if = {a: v * v * math.sin(math.radians(2 * a)) / g for a in (30, 45, 60)}
    return {
        "vx": vx, "vy": vy, "t": t_flight, "range": rng, "apex": apex,
        "ts": [round(float(t), 4) for t in sol.t], "xs": [round(x, 4) for x in xs],
        "ys": [round(y, 4) for y in ys], "landing_num": xs[-1], "what_if": what_if,
    }


def build(class_name: str, solver: Any) -> str | None:
    p = params(solver)
    s = _solve(p)
    if s is None or abs(s["landing_num"] - s["range"]) > 0.01 * s["range"]:
        return None
    v, g = p["speed"], p["g"]
    high = v * v * math.sin(math.radians(60)) ** 2 / (2 * g)
    far = max(s["range"], s["what_if"][45])
    scale = min(11.4 / (1.1 * far), 3.9 / max(high, s["apex"]))
    fmt = {
        "v": f"{v:g}", "a": f"{p['angle']:g}", "g": f"{g:g}",
        "vx": f"{s['vx']:.1f}", "vy": f"{s['vy']:.1f}", "t": f"{s['t']:.2f}",
        "r": f"{s['range']:.1f}", "r30": f"{s['what_if'][30]:.1f}", "r45": f"{s['what_if'][45]:.1f}",
    }
    return _TEMPLATE.format(
        class_name=class_name, scale=round(scale, 5),
        ts=repr(s["ts"]), xs=repr(s["xs"]), ys=repr(s["ys"]),
        speed=round(v, 4), angle=round(p["angle"], 4), g=round(g, 4),
        t_flight=round(s["t"], 4), rng=round(s["range"], 4),
        problem=repr(f"A ball is kicked at {fmt['v']} m/s, {fmt['a']}° above level ground."),
        question=repr("How far away does it land, and how long is it in the air?"),
        brief=repr(f"v = {fmt['v']} m/s at {fmt['a']}°:  where does it land?"),
        vx_label=repr(f"sideways: {fmt['v']}·cos {fmt['a']}° = {fmt['vx']} m/s"),
        vy_label=repr(f"upward: {fmt['v']}·sin {fmt['a']}° = {fmt['vy']} m/s"),
        eq_time=repr(f"up and back down:  t = 2·vy / g = 2 × {fmt['vy']} / {fmt['g']} = {fmt['t']} s"),
        eq_range=repr(f"sideways for {fmt['t']} s:  x = vx·t = {fmt['vx']} × {fmt['t']} = {fmt['r']} m"),
        flag_label=repr(f"{fmt['r']} m"),
        check_label=repr(f"simulated flight lands at {s['landing_num']:.1f} m after {fmt['t']} s"),
        w30=repr(f"30° and 60°: both {fmt['r30']} m, the same spot"),
        w45=repr(f"45°: {fmt['r45']} m, the farthest"),
        answer=repr(f"Answer: it lands {fmt['r']} m away, after {fmt['t']} s in the air"),
    )


def check_lines(solver: Any) -> list[str]:
    """What AetherLab's own simulation says, for the study document's checks."""
    p = params(solver)
    s = _solve(p)
    if s is None:
        return []
    # A radian given (0.6981) comes back as 39.9982°: show it as the student wrote it.
    return [f"Numerical simulation of the flight (v = {p['speed']:g} m/s, θ = {round(p['angle'], 1):g}°, "
            f"g = {p['g']:g} m/s², no air resistance): it lands {s['landing_num']:.2f} m away "
            f"after {s['t']:.2f} s, reaching {s['apex']:.2f} m at the top."]


_TEMPLATE = '''\
"""Generated by AetherLab - problem: where does the kicked ball land?"""

import math

import numpy as np
from manim import *


class {class_name}(Scene):
    def construct(self):
        ts = {ts}
        xs = {xs}
        ys = {ys}
        s = {scale}
        speed, angle, g = {speed}, {angle}, {g}
        t_flight, rng = {t_flight}, {rng}
        th = math.radians(angle)
        ground_y, x0, wall_x = -2.55, -5.5, -6.35
        origin = np.array([x0, ground_y, 0.0])

        def world(x, y):
            return np.array([x0 + s * x, ground_y + s * y, 0.0])

        def chip(text):
            return Text(text, font_size=24, color=YELLOW_A).to_corner(UL, buff=0.3)

        def fit(m, width=13.0):
            # Cloud and local fonts differ in width: never let a line leave the frame.
            if m.width > width:
                m.scale_to_fit_width(width)
            return m

        # 1. Picture it: the problem as a scene.
        title = Text("Where does the ball land?", font_size=40, color=YELLOW).to_edge(UP, buff=0.35)
        problem = fit(Text({problem}, font_size=28)).next_to(title, DOWN, buff=0.3)
        question = fit(Text({question}, font_size=28, color=TEAL_A)).next_to(problem, DOWN, buff=0.15)
        ground = Line([-7.1, ground_y, 0], [7.1, ground_y, 0], color=GREY_B, stroke_width=3)
        ball = Dot(origin, color=WHITE, radius=0.12).set_z_index(5)
        v_len = 2.2
        v_tip = origin + v_len * np.array([math.cos(th), math.sin(th), 0.0])
        v_arrow = Arrow(origin, v_tip, buff=0, color=YELLOW, stroke_width=6,
                        max_tip_length_to_length_ratio=0.15)
        v_text = Text(f"{{speed:g}} m/s", font_size=26, color=YELLOW).next_to(v_tip, UP, buff=0.1)
        arc = Arc(radius=0.75, start_angle=0, angle=th, arc_center=origin, color=GREY_A)
        a_text = Text(f"{{angle:g}}°", font_size=24, color=GREY_A).move_to(
            origin + 1.1 * np.array([math.cos(th / 2), math.sin(th / 2), 0.0]))
        guess = Text("?", font_size=48, color=TEAL).move_to(world(rng, 0) + UP * 0.6)
        self.play(Write(title), run_time=1.0)
        self.play(FadeIn(problem), FadeIn(question), Create(ground), FadeIn(ball), run_time=1.4)
        self.play(GrowArrow(v_arrow), FadeIn(v_text), Create(arc), FadeIn(a_text), FadeIn(guess), run_time=1.2)
        self.wait(4.0)

        # 2. Split the motion into two simple ones.
        brief = fit(Text({brief}, font_size=26, color=GREY_A), 7.4).to_corner(UR, buff=0.3)
        step = chip("1 · split the motion")
        self.play(FadeOut(title), FadeOut(problem), FadeOut(question), FadeIn(brief), FadeIn(step), run_time=0.8)
        vx_tip = origin + v_len * math.cos(th) * RIGHT
        vy_tip = origin + v_len * math.sin(th) * UP
        vx_arrow = Arrow(origin, vx_tip, buff=0, color=BLUE, stroke_width=6, max_tip_length_to_length_ratio=0.18)
        vy_arrow = Arrow(origin, vy_tip, buff=0, color=RED, stroke_width=6, max_tip_length_to_length_ratio=0.18)
        dash_x = DashedLine(v_tip, vx_tip, color=GREY_B, stroke_width=1.5)
        dash_y = DashedLine(v_tip, vy_tip, color=GREY_B, stroke_width=1.5)
        vx_text = Text({vx_label}, font_size=24, color=BLUE).move_to([2.2, 1.9, 0])
        vy_text = Text({vy_label}, font_size=24, color=RED).move_to([2.2, 1.35, 0])
        self.play(Create(dash_x), Create(dash_y), GrowArrow(vx_arrow), GrowArrow(vy_arrow), run_time=1.2)
        self.play(FadeIn(vx_text, shift=0.2 * LEFT), FadeIn(vy_text, shift=0.2 * LEFT), run_time=0.9)
        rule_x = Text("sideways: nothing pushes, so the speed stays the same", font_size=24,
                      color=BLUE_B).move_to([2.2, 0.7, 0])
        rule_y = Text("up and down: gravity slows it, stops it, brings it back", font_size=24,
                      color=RED_B).move_to([2.2, 0.2, 0])
        self.play(FadeIn(rule_x), run_time=0.7)
        self.play(FadeIn(rule_y), run_time=0.7)
        self.wait(3.0)

        # The two shadows, in slow motion: each is one simple motion.
        step2 = chip("2 · watch the two shadows")
        wall = Line([wall_x, ground_y, 0], [wall_x, 1.7, 0], color=GREY_B, stroke_width=3)
        self.play(FadeOut(VGroup(v_arrow, v_text, arc, a_text, vx_arrow, vy_arrow, dash_x, dash_y,
                                 rule_x, rule_y, vx_text, vy_text, guess)),
                  FadeOut(step), FadeIn(step2), Create(wall), run_time=0.9)
        t = ValueTracker(0.0)

        def pos():
            return world(float(np.interp(t.get_value(), ts, xs)), float(np.interp(t.get_value(), ts, ys)))

        ball.add_updater(lambda m: m.move_to(pos()))
        ground_shadow = always_redraw(lambda: Dot([pos()[0], ground_y, 0], color=BLUE, radius=0.1))
        wall_shadow = always_redraw(lambda: Dot([wall_x, pos()[1], 0], color=RED, radius=0.1))
        link_g = always_redraw(lambda: DashedLine(pos(), [pos()[0], ground_y, 0], color=BLUE_E, stroke_width=1.5))
        link_w = always_redraw(lambda: DashedLine(pos(), [wall_x, pos()[1], 0], color=RED_E, stroke_width=1.5))
        ticks = VGroup()

        def drop_ticks(group):
            # a mark on each shadow every quarter second of flight
            n = int(t.get_value() / 0.25 + 1e-9)
            while len(group) // 2 < n:
                k = len(group) // 2 + 1
                p = world(float(np.interp(0.25 * k, ts, xs)), float(np.interp(0.25 * k, ts, ys)))
                group.add(Dot([p[0], ground_y, 0], color=BLUE_B, radius=0.05))
                group.add(Dot([wall_x, p[1], 0], color=RED_B, radius=0.05))

        ticks.add_updater(drop_ticks)
        trail = TracedPath(pos, stroke_color=WHITE, stroke_width=2, stroke_opacity=0.5)
        slow = Text("slow motion, a mark every 0.25 s", font_size=22, color=GREY_B).to_corner(DR, buff=0.2)
        self.add(trail, link_g, link_w, ground_shadow, wall_shadow, ticks)
        self.play(FadeIn(slow), run_time=0.4)
        self.play(t.animate.set_value(t_flight), run_time=9.0, rate_func=linear)
        ticks.clear_updaters()
        note_g = Text("ground shadow: evenly spaced marks, a steady speed", font_size=24,
                      color=BLUE_B).move_to([1.8, 1.4, 0])
        note_w = Text("wall shadow: bunched at the top, a ball thrown straight up",
                      font_size=24, color=RED_B).move_to([1.8, 0.85, 0])
        self.play(FadeIn(note_g), run_time=0.7)
        self.play(FadeIn(note_w), run_time=0.7)
        self.wait(3.0)

        # 3. Solve: the wall shadow gives the time, the ground shadow the distance.
        step3 = chip("3 · solve")
        eq_t = Text({eq_time}, font_size=26, color=RED_A).move_to([1.2, 1.75, 0])
        eq_x = Text({eq_range}, font_size=26, color=BLUE_A).move_to([1.2, 1.1, 0])
        self.play(FadeOut(note_g), FadeOut(note_w), FadeOut(slow), FadeOut(step2), FadeIn(step3), run_time=0.6)
        self.play(Indicate(wall_shadow, color=RED), FadeIn(eq_t, shift=0.2 * DOWN), run_time=1.4)
        self.wait(2.0)
        self.play(Indicate(ground_shadow, color=BLUE), FadeIn(eq_x, shift=0.2 * DOWN), run_time=1.4)
        flag_base = world(rng, 0)
        pole = Line(flag_base, flag_base + UP * 1.0, color=GREY_A, stroke_width=3)
        cloth = Polygon(flag_base + UP * 1.0, flag_base + UP * 0.72 + RIGHT * 0.45, flag_base + UP * 0.44,
                        color=TEAL, fill_color=TEAL, fill_opacity=0.9)
        flag_text = Text({flag_label}, font_size=24, color=TEAL).next_to(pole, DOWN, buff=0.15)
        self.play(Create(pole), FadeIn(cloth), FadeIn(flag_text), run_time=0.9)
        self.wait(3.0)

        # 4. Check: fly the real (simulated) ball at real speed onto the flag.
        step4 = chip("4 · check it")
        for mob in (link_g, link_w, ground_shadow, wall_shadow):
            mob.clear_updaters()
        self.play(FadeOut(VGroup(link_g, link_w, ground_shadow, wall_shadow, ticks, trail, eq_t, eq_x)),
                  FadeOut(step3), FadeIn(step4), run_time=0.7)
        t.set_value(0.0)
        trail2 = TracedPath(pos, stroke_color=YELLOW, stroke_width=3)
        clock = always_redraw(lambda: Text(f"t = {{t.get_value():.2f}} s", font_size=26).move_to([5.3, 2.8, 0]))
        self.add(trail2, clock)
        self.play(t.animate.set_value(t_flight), run_time=t_flight, rate_func=linear)
        hit = Text({check_label}, font_size=26, color=GREEN_B).move_to([0.9, 1.5, 0])
        self.play(Flash(ball, color=GREEN), Indicate(cloth, color=GREEN), FadeIn(hit), run_time=1.1)
        self.wait(3.0)

        # 5. What if: which angle goes farthest?
        step5 = chip("5 · what if the angle changes?")
        ball.clear_updaters()
        clock.clear_updaters()
        self.play(FadeOut(VGroup(hit, clock, trail2)), FadeOut(step4), FadeIn(step5), run_time=0.6)

        def arc_for(deg, color):
            a = math.radians(deg)
            tf = 2 * speed * math.sin(a) / g
            pts = [world(speed * math.cos(a) * u, speed * math.sin(a) * u - 0.5 * g * u * u)
                   for u in np.linspace(0, tf, 90)]
            path = VMobject(color=color, stroke_width=3.5)
            path.set_points_as_corners(pts)
            return path

        a30, a45, a60 = arc_for(30, BLUE), arc_for(45, GREEN), arc_for(60, ORANGE)
        self.play(Create(a30), Create(a60), run_time=2.2)
        same = Text({w30}, font_size=26, color=ORANGE).move_to([0.6, 2.35, 0])
        self.play(FadeIn(same), run_time=0.8)
        self.wait(1.6)
        self.play(Create(a45), run_time=1.6)
        best = Text({w45}, font_size=26, color=GREEN).next_to(same, DOWN, buff=0.2)
        self.play(FadeIn(best), run_time=0.8)
        self.wait(1.6)
        answer = Text({answer}, font_size=30, color=YELLOW)
        box = SurroundingRectangle(answer, color=YELLOW, buff=0.2, corner_radius=0.12)
        card = VGroup(answer, box).move_to([0.4, 2.35, 0])
        self.play(FadeOut(same), FadeOut(best), FadeIn(card, scale=0.9), run_time=1.0)
        self.wait(4.0)
'''
