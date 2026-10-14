"""Problem video: a grandfather clock on another world.

"A grandfather clock's L m pendulum makes one swing per second on Earth. On the
Moon (or wherever g is given), how long does one swing take?"

Device: two clocks, side by side. Each clock's second hand advances once per
real swing of its own pendulum, and each pendulum is integrated numerically,
so the Moon clock visibly falls behind the Earth clock. What-if: shorten the
Moon pendulum to L·g_moon/g_earth and the two clocks tick in step.

Solving arc (subgoal labels): 1 the idea, 2 solve, 3 check, 4 what if.
"""

from __future__ import annotations

import math
from typing import Any

_G_EARTH = 9.81
_WORLDS = {"moon": ("the Moon", 1.62), "mars": ("Mars", 3.71), "jupiter": ("Jupiter", 24.79),
           "venus": ("Venus", 8.87), "mercury": ("Mercury", 3.70), "titan": ("Titan", 1.35)}
_DEFAULT_LENGTH = 0.994          # a "seconds pendulum": one swing per second on Earth
_CHECK_S = 12.0
_SYNC_S = 6.0
_RELEASE = math.radians(8.0)


def _text(solver: Any) -> str:
    return " ".join([" ".join(getattr(solver, "keywords", []) or []),
                     getattr(solver, "summary", "") or ""]).lower()


def params(solver: Any) -> dict[str, Any]:
    variables = {str(k).lower(): v for k, v in dict(getattr(solver, "variables", {}) or {}).items()}

    def num(*names: str) -> float | None:
        for n in names:
            try:
                v = float(variables[n])
            except (KeyError, TypeError, ValueError):
                continue
            if math.isfinite(v) and v > 0:
                return v
        return None

    text = _text(solver)
    place, g_world = next(((name, g) for key, (name, g) in _WORLDS.items() if key in text), (None, None))
    g_given = num("g", "gravity", "g_moon", "g_planet", "local_gravity")
    if g_given is not None and abs(g_given - _G_EARTH) > 0.3:
        g_there = g_given
    else:
        g_there = g_world or 1.62
    place = place or ("the Moon" if abs(g_there - 1.62) < 0.05 else "the new world")
    length = num("length", "l", "pendulum_length")
    length = length if length and 0.05 <= length <= 20.0 else _DEFAULT_LENGTH
    return {"length": length, "g_there": g_there, "place": place}


def matches(solver: Any) -> bool:
    """A pendulum/clock problem set somewhere other than Earth."""
    text = _text(solver)
    if not any(w in text for w in ("pendulum", "clock")):
        return False
    if any(key in text for key in _WORLDS):
        return True
    variables = {str(k).lower(): v for k, v in dict(getattr(solver, "variables", {}) or {}).items()}
    for name in ("g", "gravity", "g_moon", "g_planet", "local_gravity"):
        try:
            if abs(float(variables[name]) - _G_EARTH) > 0.3:
                return True
        except (KeyError, TypeError, ValueError):
            continue
    return False


def _swing(length: float, g: float, t_end: float) -> tuple[list[float], list[float], list[float]] | None:
    from aetherlab.services.numeric import solve_numeric
    from aetherlab.services.scene_components import pendulum

    spec = dict(pendulum.numeric_spec(_RELEASE), t_range=[0.0, t_end])
    sol = solve_numeric(spec, {"gravity": g, "length": length, "damping": 0.0}, max_points=900)
    if not sol.ok:
        return None
    ts = [round(float(t), 4) for t in sol.t]
    ths = [round(float(v), 5) for v in sol.series("theta")]
    crossings = []
    for i in range(1, len(ths)):
        if (ths[i - 1] < 0) != (ths[i] < 0) and ths[i] != ths[i - 1]:
            f = -ths[i - 1] / (ths[i] - ths[i - 1])
            crossings.append(round(ts[i - 1] + f * (ts[i] - ts[i - 1]), 4))
    return ts, ths, crossings


def _solve(p: dict[str, Any]) -> dict[str, Any] | None:
    length, g = p["length"], p["g_there"]
    swing_earth = math.pi * math.sqrt(length / _G_EARTH)
    swing_there = math.pi * math.sqrt(length / g)
    sync_length = length * g / _G_EARTH
    earth = _swing(length, _G_EARTH, _CHECK_S)
    there = _swing(length, g, _CHECK_S)
    short = _swing(sync_length, g, _SYNC_S)
    earth_sync = _swing(length, _G_EARTH, _SYNC_S)
    if not all((earth, there, short, earth_sync)):
        return None
    # measured swing time: mean gap between zero crossings (one crossing per swing)
    measured = (there[2][-1] - there[2][0]) / (len(there[2]) - 1) if len(there[2]) > 2 else None
    return {"swing_earth": swing_earth, "swing_there": swing_there, "sync_length": sync_length,
            "earth": earth, "there": there, "short": short, "earth_sync": earth_sync,
            "measured": measured}


def build(class_name: str, solver: Any) -> str | None:
    p = params(solver)
    s = _solve(p)
    if s is None or s["measured"] is None or abs(s["measured"] - s["swing_there"]) > 0.02 * s["swing_there"]:
        return None
    place, length, g = p["place"], p["length"], p["g_there"]
    place_cap = place[0].upper() + place[1:]
    one_minute = 60.0 / s["swing_there"] * s["swing_earth"]
    # seconds-pendulum phrasing only when it really ticks once a second on Earth
    earth_phrase = ("makes one swing per second on Earth" if abs(s["swing_earth"] - 1.0) < 0.02
                    else f"makes one swing every {s['swing_earth']:.2f} s on Earth")
    return _TEMPLATE.format(
        class_name=class_name,
        t_e=repr(s["earth"][0]), th_e=repr(s["earth"][1]), c_e=repr(s["earth"][2]),
        t_m=repr(s["there"][0]), th_m=repr(s["there"][1]), c_m=repr(s["there"][2]),
        t_s=repr(s["short"][0]), th_s=repr(s["short"][1]), c_s=repr(s["short"][2]),
        t_es=repr(s["earth_sync"][0]), th_es=repr(s["earth_sync"][1]), c_es=repr(s["earth_sync"][2]),
        ratio=round(s["sync_length"] / length, 5), check_s=_CHECK_S, sync_s=_SYNC_S,
        title=repr(f"A grandfather clock on {place}"),
        problem1=repr(f"This clock's {length:.2f} m pendulum {earth_phrase}."),
        problem2=repr(f"On {place}, gravity is only {g:.2f} m/s².  How long is one swing there?"),
        brief=repr(f"L = {length:.2f} m,  g = {g:.2f} m/s²:  one swing?"),
        place_label=repr(f"{place_cap}  g = {g:.2f}"),
        pull_earth=repr("Earth pulls the bob back hard\n9.81 m/s²"),
        pull_there=repr(f"{place_cap} pulls it back gently\n{g:.2f} m/s²"),
        eq_rule=repr("one swing (half a period):  t = π·√(L / g)"),
        eq_earth=repr(f"Earth:  π·√({length:.3f} / 9.81) = {s['swing_earth']:.2f} s"),
        eq_there=repr(f"{place_cap}:  π·√({length:.3f} / {g:.2f}) = {s['swing_there']:.2f} s"),
        eq_ratio=repr(f"{s['swing_there'] / s['swing_earth']:.2f}× slower, because √(9.81 / {g:.2f}) = "
                      f"{math.sqrt(_G_EARTH / g):.2f}"),
        drift=repr(f"after one Earth minute, the clock on {place} would show only {one_minute:.0f} s"),
        whatif_q=repr(f"How short must the pendulum be to keep Earth time on {place}?"),
        whatif_a=repr(f"L × {g:.2f} / 9.81 = {s['sync_length'] * 100:.1f} cm"),
        in_step=repr("now both clocks tick in step"),
        answer=repr(f"Answer: one swing takes {s['swing_there']:.2f} s on {place}"),
        answer2=repr(f"(a {s['sync_length'] * 100:.1f} cm pendulum there would keep Earth time)"),
    )


def check_lines(solver: Any) -> list[str]:
    """What AetherLab's own simulation says, for the study document's checks."""
    p = params(solver)
    s = _solve(p)
    if s is None or s["measured"] is None:
        return []
    return [f"Simulated pendulum (L = {p['length']:.3f} m, g = {p['g_there']:.2f} m/s²): one swing takes "
            f"{s['measured']:.2f} s, against {s['swing_there']:.2f} s from the small-angle formula."]


_TEMPLATE = '''\
"""Generated by AetherLab - problem: a grandfather clock on another world."""

import numpy as np
from manim import *


class {class_name}(Scene):
    def construct(self):
        t_e, th_e, c_e = {t_e}, {th_e}, {c_e}
        t_m, th_m, c_m = {t_m}, {th_m}, {c_m}
        t_s, th_s, c_s = {t_s}, {th_s}, {c_s}
        t_es, th_es, c_es = {t_es}, {th_es}, {c_es}
        clock = ValueTracker(0.0)
        rod_full = 2.1

        def chip(text):
            return Text(text, font_size=24, color=YELLOW_A).to_corner(UL, buff=0.3)

        def pendulum(x, pivot_y, rod, times, angles, color, radius=0.16):
            pivot = np.array([x, pivot_y, 0.0])

            def bob():
                th = float(np.interp(clock.get_value(), times, angles))
                return pivot + rod.get_value() * np.array([np.sin(th), -np.cos(th), 0.0])

            rod_line = always_redraw(lambda: Line(pivot, bob(), color=GREY_A, stroke_width=3))
            ball = always_redraw(lambda: Dot(bob(), radius=radius, color=color))
            hook = Dot(pivot, color=GREY_B, radius=0.05)
            return VGroup(hook, rod_line, ball)

        def clock_face(x, y, crossings, color, read_y=-2.85):
            center = np.array([x, y, 0.0])
            ring = Circle(radius=0.78, color=color, stroke_width=4).move_to(center)
            marks = VGroup(*[
                Line(center + 0.78 * np.array([np.sin(a), np.cos(a), 0]),
                     center + (0.66 if k % 5 == 0 else 0.72) * np.array([np.sin(a), np.cos(a), 0]),
                     color=GREY_B, stroke_width=2 if k % 5 == 0 else 1)
                for k, a in enumerate(np.linspace(0, TAU, 60, endpoint=False))
            ])

            def hand():
                ticks = int(np.searchsorted(crossings, clock.get_value()))
                a = ticks * TAU / 60
                return Line(center, center + 0.64 * np.array([np.sin(a), np.cos(a), 0]),
                            color=color, stroke_width=4)

            readout = always_redraw(lambda: Text(
                f"clock shows {{int(np.searchsorted(crossings, clock.get_value()))}} s",
                font_size=24, color=color).move_to([x, read_y, 0]))
            return VGroup(ring, marks, always_redraw(hand), Dot(center, radius=0.05)), readout

        def fit(m, width=13.0):
            # Cloud and local fonts differ in width: never let a line leave the frame.
            if m.width > width:
                m.scale_to_fit_width(width)
            return m

        # The problem.
        title = Text({title}, font_size=40, color=YELLOW).to_edge(UP, buff=0.4)
        p1 = fit(Text({problem1}, font_size=28)).next_to(title, DOWN, buff=0.35)
        p2 = fit(Text({problem2}, font_size=28, color=TEAL_A)).next_to(p1, DOWN, buff=0.15)
        rod_e = ValueTracker(rod_full)
        demo = pendulum(0.0, 0.3, rod_e, t_e, th_e, BLUE)
        self.play(Write(title), run_time=1.0)
        self.play(FadeIn(p1), FadeIn(p2), FadeIn(demo), run_time=1.4)
        self.play(clock.animate.set_value(4.0), run_time=4.0, rate_func=linear)
        self.wait(1.5)

        # 1. The idea: weaker pull, slower swing.
        brief = fit(Text({brief}, font_size=26, color=GREY_A), 7.4).to_corner(UR, buff=0.3)
        step1 = chip("1 · the idea")
        for m in demo.get_family():
            m.clear_updaters()
        self.play(FadeOut(title), FadeOut(p1), FadeOut(p2), FadeOut(demo), FadeIn(brief), FadeIn(step1), run_time=0.8)
        bob_e = Dot([-3.2, 0.4, 0], radius=0.22, color=BLUE)
        bob_m = Dot([3.2, 0.4, 0], radius=0.22, color=GREY_A)
        g_len = 2.2
        arrow_e = Arrow(bob_e.get_center(), bob_e.get_center() + DOWN * g_len, buff=0, color=BLUE,
                        stroke_width=7, max_tip_length_to_length_ratio=0.15)
        arrow_m = Arrow(bob_m.get_center(), bob_m.get_center() + DOWN * max(0.5, g_len * {ratio}), buff=0,
                        color=GREY_A, stroke_width=7, max_tip_length_to_length_ratio=0.4)
        lab_e = Text({pull_earth}, font_size=24, color=BLUE_B).move_to([-3.2, 1.4, 0])
        lab_m = Text({pull_there}, font_size=24, color=GREY_A).move_to([3.2, 1.4, 0])
        self.play(GrowFromCenter(bob_e), GrowFromCenter(bob_m), run_time=0.6)
        self.play(GrowArrow(arrow_e), FadeIn(lab_e), run_time=1.0)
        self.play(GrowArrow(arrow_m), FadeIn(lab_m), run_time=1.0)
        idea = fit(Text("gravity is what swings the bob back: a weaker pull means a slower swing",
                        font_size=26, color=YELLOW_A)).move_to([0, -2.6, 0])
        self.play(FadeIn(idea), run_time=0.8)
        self.wait(3.0)

        # 2. Solve.
        step2 = chip("2 · solve")
        self.play(FadeOut(VGroup(bob_e, bob_m, arrow_e, arrow_m, lab_e, lab_m, idea)),
                  FadeOut(step1), FadeIn(step2), run_time=0.7)
        rule = Text({eq_rule}, font_size=32, color=WHITE).move_to([0, 1.6, 0])
        e_line = Text({eq_earth}, font_size=30, color=BLUE_B).move_to([0, 0.5, 0])
        m_line = Text({eq_there}, font_size=30, color=GREY_A).move_to([0, -0.3, 0])
        r_line = Text({eq_ratio}, font_size=28, color=YELLOW_A).move_to([0, -1.4, 0])
        self.play(Write(rule), run_time=1.2)
        self.wait(1.2)
        self.play(FadeIn(e_line, shift=0.2 * RIGHT), run_time=0.9)
        self.wait(1.2)
        self.play(FadeIn(m_line, shift=0.2 * RIGHT), run_time=0.9)
        self.wait(1.2)
        self.play(FadeIn(r_line), run_time=0.9)
        self.wait(2.5)

        # 3. Check: two real clocks, each counting its own simulated swings.
        step3 = chip("3 · check: two clocks")
        self.play(FadeOut(VGroup(rule, e_line, m_line, r_line)), FadeOut(step2), FadeIn(step3), run_time=0.7)
        clock.set_value(0.0)
        rod_m = ValueTracker(rod_full)
        pend_e = pendulum(-3.4, 0.35, rod_e, t_e, th_e, BLUE)
        pend_m = pendulum(3.4, 0.35, rod_m, t_m, th_m, GREY_A)
        face_e, read_e = clock_face(-3.4, 1.75, c_e, BLUE)
        face_m, read_m = clock_face(3.4, 1.75, c_m, GREY_A)
        name_e = Text("Earth  g = 9.81", font_size=26, color=BLUE_B).move_to([-3.4, -2.3, 0])
        name_m = Text({place_label}, font_size=26, color=GREY_A).move_to([3.4, -2.3, 0])
        real = always_redraw(lambda: Text(f"real time: {{clock.get_value():.1f}} s", font_size=26,
                                          color=WHITE).move_to([0, -3.2, 0]))
        self.play(FadeIn(pend_e), FadeIn(pend_m), FadeIn(face_e), FadeIn(face_m), FadeIn(name_e),
                  FadeIn(name_m), run_time=1.0)
        self.add(read_e, read_m, real)
        self.play(clock.animate.set_value({check_s}), run_time={check_s}, rate_func=linear)
        drift = fit(Text({drift}, font_size=26, color=YELLOW_A)).move_to([0, 2.9, 0])
        self.play(FadeIn(drift), Indicate(face_m, color=YELLOW), run_time=1.0)
        self.wait(2.5)

        # 4. What if: shorten the pendulum on the other world until the clocks agree.
        step4 = chip("4 · what if?")
        question = fit(Text({whatif_q}, font_size=26, color=TEAL_A)).move_to([0, 2.9, 0])
        self.play(FadeOut(drift), FadeOut(step3), FadeIn(step4), FadeIn(question), run_time=0.8)
        fix = Text({whatif_a}, font_size=28, color=TEAL).move_to([3.4, -0.6, 0])
        self.play(rod_m.animate.set_value(rod_full * {ratio}), FadeIn(fix), run_time=1.6)
        self.wait(1.0)
        # restart both clocks at zero with the shortened pendulum
        for m in VGroup(pend_e, pend_m, face_e, face_m, read_e, read_m).get_family():
            m.clear_updaters()
        self.remove(pend_e, pend_m, face_e, face_m, read_e, read_m)
        clock.set_value(0.0)
        pend_e2 = pendulum(-3.4, 0.35, rod_e, t_es, th_es, BLUE)
        pend_m2 = pendulum(3.4, 0.35, rod_m, t_s, th_s, TEAL)
        face_e2, read_e2 = clock_face(-3.4, 1.75, c_es, BLUE)
        face_m2, read_m2 = clock_face(3.4, 1.75, c_s, TEAL)
        self.add(pend_e2, pend_m2, face_e2, face_m2, read_e2, read_m2)
        self.play(clock.animate.set_value({sync_s}), run_time={sync_s}, rate_func=linear)
        in_step = Text({in_step}, font_size=26, color=GREEN_B).move_to([0, -0.6, 0])
        self.play(FadeIn(in_step), run_time=0.7)
        self.wait(1.5)

        answer = Text({answer}, font_size=30, color=YELLOW)
        answer2 = Text({answer2}, font_size=24, color=GREY_A)
        card_text = VGroup(answer, answer2).arrange(DOWN, buff=0.15)
        box = SurroundingRectangle(card_text, color=YELLOW, buff=0.22, corner_radius=0.12)
        card = VGroup(card_text, box).move_to([0, 0.3, 0])
        for m in VGroup(pend_e2, pend_m2, face_e2, face_m2, read_e2, read_m2, real).get_family():
            m.clear_updaters()
        self.play(FadeOut(VGroup(pend_e2, pend_m2, face_e2, face_m2, read_e2, read_m2, real, fix,
                                 name_e, name_m, question, in_step)), run_time=0.8)
        self.play(FadeIn(card, scale=0.9), run_time=1.0)
        self.wait(4.0)
'''
