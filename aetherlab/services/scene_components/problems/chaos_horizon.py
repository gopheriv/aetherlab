"""Problem video: how far ahead can we predict a double pendulum?

"Two identical double pendulums are released from 120° and -10°; one starts a
millionth of a radian off. When do they visibly disagree? How much longer
would a start 1000 times more precise buy us?"

Device: twins. Two pendulums, drawn on the same pivot, look like one for ten
seconds and then fly apart. Beside them a log-scale graph of the gap climbs as
a straight line: the gap grows exponentially, and the slope is the Lyapunov
exponent. The slope predicts when the twins split; the what-if adds starts
1000× and 10⁶× more precise, whose lines run parallel and buy the same few
seconds each. That is the price of prediction.

Solving arc (subgoal labels): 1 the rules are exact, 2 watch the gap grow,
3 read the growth rate, 4 what if we measure 1000× better, 5 check.
"""

from __future__ import annotations

import math
from typing import Any

from aetherlab.services.scene_components.problems._kit import fill, pick, sci, text_of, variables_of

G = 9.81
T_END = 40.0
SPLIT = 0.5                       # "visibly different": the angles differ by half a radian (about 29°)
_CUES = ("chao", "predict", "butterfly", "sensitiv", "lyapunov", "diverg", "twin", "apart", "slightly different",
         "tiny difference", "initial condition")


def _angle(value: float | None, default: float) -> float:
    if value is None:
        return default
    return math.radians(value) if abs(value) > 3.2 else value   # degrees unless it looks like radians


def params(solver: Any) -> dict[str, float]:
    v = variables_of(solver)
    t1 = _angle(pick(v, ("theta1", "theta_1", "t1", "angle1", "theta10", "phi1", "theta")), math.radians(120.0))
    t2 = _angle(pick(v, ("theta2", "theta_2", "t2", "angle2", "theta20", "phi2")), math.radians(-10.0))
    delta = pick(v, ("delta", "epsilon", "perturbation", "d0", "delta0", "dtheta", "difference", "offset"))
    length = pick(v, ("l", "length", "arm", "l1", "arm_length"))
    return {"theta1": t1, "theta2": t2,
            "delta": delta if delta and 1e-12 <= delta <= 1e-2 else 1e-6,
            "length": length if length and 0.1 <= length <= 5.0 else 1.0}


def matches(solver: Any) -> bool:
    text = text_of(solver)
    return "double pendulum" in text and (any(c in text for c in _CUES) or "delta" in variables_of(solver))


def _rhs(length: float):
    def f(t, y):
        t1, t2, w1, w2 = y
        d = t1 - t2
        den = length * (3.0 - math.cos(2.0 * d))
        a1 = (-3.0 * G * math.sin(t1) - G * math.sin(t1 - 2.0 * t2)
              - 2.0 * math.sin(d) * (w2 * w2 * length + w1 * w1 * length * math.cos(d))) / den
        a2 = 2.0 * math.sin(d) * (2.0 * w1 * w1 * length + 2.0 * G * math.cos(t1) + w2 * w2 * length * math.cos(d)) / den
        return [w1, w2, a1, a2]
    return f


def _energy(y, length: float) -> float:
    t1, t2, w1, w2 = y
    kinetic = 0.5 * (length * w1) ** 2 + 0.5 * ((length * w1) ** 2 + (length * w2) ** 2
                                                + 2 * length * length * w1 * w2 * math.cos(t1 - t2))
    return kinetic - G * length * (2 * math.cos(t1) + math.cos(t2))


def _solve(p: dict[str, float]) -> dict[str, Any] | None:
    import numpy as np
    from scipy.integrate import solve_ivp

    f = _rhs(p["length"])
    ts = np.linspace(0.0, T_END, 4001)
    y0 = [p["theta1"], p["theta2"], 0.0, 0.0]

    def run(start):
        s = solve_ivp(f, (0.0, T_END), start, t_eval=ts, method="DOP853", rtol=1e-12, atol=1e-13)
        return s.y if s.success else None

    ref = run(y0)
    if ref is None:
        return None
    runs = []
    for scale in (1.0, 1e-3, 1e-6):
        d0 = p["delta"] * scale
        if d0 < 1e-15:
            break
        other = run([y0[0] + d0] + y0[1:])
        if other is None:
            return None
        gap = np.hypot(other[0] - ref[0], other[1] - ref[1])
        crossed = np.nonzero(gap > SPLIT)[0]
        window = (gap > 10 * d0) & (gap < 0.05)
        coef = np.polyfit(ts[window], np.log(gap[window]), 1) if window.sum() > 50 else None
        rate = float(coef[0]) if coef is not None else None
        runs.append({"d0": d0, "gap": gap, "other": other, "rate": rate,
                     "intercept": float(coef[1]) if coef is not None else None,
                     "split": float(ts[crossed[0]]) if crossed.size else None})
    if len(runs) < 2 or any(r["split"] is None or r["rate"] is None or r["rate"] <= 0.1 for r in runs):
        return None                                      # not chaotic enough here: no honest horizon to show
    rate = runs[0]["rate"]
    drift = abs(_energy(ref[:, -1], p["length"]) - _energy(ref[:, 0], p["length"]))
    show = ts <= runs[0]["split"] + 4.0
    x_max = min(T_END, 5.0 * math.ceil((max(r["split"] for r in runs) + 2.0) / 5.0))
    step = 2                                             # 0.02 s between animation samples
    return {
        "rate": rate, "drift": drift, "runs": runs, "ts": ts,
        "anim_t": [round(float(t), 3) for t in ts[show][::step]],
        "anim_a": [[round(float(x), 5) for x in row[show][::step]] for row in ref[:2]],
        "anim_b": [[round(float(x), 5) for x in row[show][::step]] for row in runs[0]["other"][:2]],
        "graph": [[[round(float(t), 3), round(float(math.log10(max(g, 1e-15))), 4)]
                   for t, g in zip(ts[::10], r["gap"][::10]) if t <= x_max] for r in runs],
        "x_max": x_max,
        "predicted": [math.log(SPLIT / r["d0"]) / rate for r in runs],
    }


def _power(d0: float) -> tuple[str, str]:
    k = int(round(math.log10(d0)))
    return f"10^{{{k}}}", f"10^{k}"


def _words(d0: float) -> str:
    names = {-3: "a thousandth", -6: "a millionth", -9: "a billionth", -12: "a trillionth"}
    k = round(math.log10(d0))
    return names.get(k, f"10^{k}") if abs(math.log10(d0) - k) < 1e-9 else f"{d0:.1e}"


def build(class_name: str, solver: Any) -> str | None:
    p = params(solver)
    s = _solve(p)
    if s is None or s["drift"] > 1e-6:
        return None
    runs, rate = s["runs"], s["rate"]
    first = runs[0]
    d_tex = _power(first["d0"])[0]
    extra = math.log(1000.0) / rate
    gains = [runs[i + 1]["split"] - runs[i]["split"] for i in range(len(runs) - 1)]
    deg1, deg2 = math.degrees(p["theta1"]), math.degrees(p["theta2"])
    data = {
        "L": p["length"], "t": s["anim_t"], "a": s["anim_a"], "b": s["anim_b"], "graph": s["graph"],
        "splits": [round(r["split"], 3) for r in runs], "d0_log": [round(math.log10(r["d0"]), 3) for r in runs],
        "rate": round(rate, 4), "split_log": round(math.log10(SPLIT), 4), "x_max": s["x_max"],
        "fit_b": round(first["intercept"] / math.log(10), 4),
        "y_min": min(-8, math.floor(math.log10(runs[-1]["d0"])) - 1),
        "problem": f"Two identical double pendulums start at {deg1:.0f}° and {deg2:.0f}°.",
        "problem2": f"One starts {_words(first['d0'])} of a radian off: far too small to see.",
        "question": "When do they visibly disagree? What would a better start buy?",
        "twin_note": "two pendulums, drawn on top of each other",
        "tex_eom1": r"\ddot\theta_1=\frac{-3g\sin\theta_1-g\sin(\theta_1-2\theta_2)"
                    r"-2\sin(\theta_1-\theta_2)\,\big(\dot\theta_2^{\,2}L+\dot\theta_1^{\,2}L\cos(\theta_1-\theta_2)\big)}"
                    r"{L\,\big(3-\cos(2\theta_1-2\theta_2)\big)}",
        "plain_eom1": "θ1'' = [-3g sin θ1 - g sin(θ1 - 2θ2) - 2 sin(θ1 - θ2)(θ2'² L + θ1'² L cos(θ1 - θ2))] "
                      "/ [L (3 - cos(2θ1 - 2θ2))]",
        "tex_eom2": r"\ddot\theta_2=\frac{2\sin(\theta_1-\theta_2)\,\big(2\dot\theta_1^{\,2}L+2g\cos\theta_1"
                    r"+\dot\theta_2^{\,2}L\cos(\theta_1-\theta_2)\big)}{L\,\big(3-\cos(2\theta_1-2\theta_2)\big)}",
        "plain_eom2": "θ2'' = 2 sin(θ1 - θ2)(2θ1'² L + 2g cos θ1 + θ2'² L cos(θ1 - θ2)) / [L (3 - cos(2θ1 - 2θ2))]",
        "rules": "Exact rules: the same start always gives the same future.",
        "no_formula": "No formula solves them, so AetherLab steps them forward in tiny time steps.",
        "tex_growth": r"\text{gap}\approx\delta_0\,e^{\lambda t}",
        "plain_growth": "gap ≈ d0 × e^(λt)",
        "tex_rate": rf"\lambda=\text{{slope}}\times\ln 10={rate:.2f}\ \text{{s}}^{{-1}}",
        "plain_rate": f"λ = slope × ln 10 = {rate:.2f} per second",
        "tex_double": rf"\text{{the gap doubles every }}\frac{{\ln 2}}{{\lambda}}={math.log(2) / rate:.2f}\ \text{{s}}",
        "plain_double": f"the gap doubles every ln2 / λ = {math.log(2) / rate:.2f} s",
        "tex_horizon": rf"T=\frac{{1}}{{\lambda}}\ln\frac{{0.5}}{{\delta_0}}=\frac{{1}}{{{rate:.2f}}}\ln\frac{{0.5}}{{{d_tex}}}"
                       rf"={s['predicted'][0]:.1f}\ \text{{s}}",
        "plain_horizon": f"T = (1/λ) ln(0.5 / d0) = {s['predicted'][0]:.1f} s",
        "measured": f"measured: they split at {first['split']:.1f} s",
        "split_label": f"split at {first['split']:.1f} s",
        "tex_extra": rf"\Delta T=\frac{{\ln 1000}}{{\lambda}}=\frac{{6.91}}{{{rate:.2f}}}={extra:.1f}\ \text{{s}}",
        "plain_extra": f"ΔT = ln 1000 / λ = 6.91 / {rate:.2f} = {extra:.1f} s",
        "extra_note": "that is all a 1000× better start buys",
        "run_tex": [rf"{_power(r['d0'])[0]}\text{{ rad off: split at {r['split']:.1f} s}}" for r in runs],
        "run_plain": [f"{_power(r['d0'])[1]} rad off: split at {r['split']:.1f} s" for r in runs],
        "gains": "measured gains: " + ", ".join(f"+{g:.1f} s" for g in gains),
        "weather": "Each 1000× buys the same few seconds.",
        "weather2": "The same limit caps weather forecasts.",
        "tex_check": rf"\text{{energy drift over {T_END:.0f} s: }}{sci(s['drift'], 2)[0]}\ \text{{J}}",
        "plain_check": f"energy drift over {T_END:.0f} s: {sci(s['drift'], 2)[1]} J",
        "check1b": "(tiny: the time-stepping is trustworthy)",
        "check2": "predicted splits: " + ", ".join(f"{x:.1f} s" for x in s["predicted"]),
        "check3": "measured splits:  " + ", ".join(f"{r['split']:.1f} s" for r in runs),
        "answer": f"Answer: they split after about {first['split']:.0f} s.",
        "answer2": f"1000× better start: only ~{extra:.0f} s more.",
    }
    return fill(_TEMPLATE, class_name, data)


def check_lines(solver: Any) -> list[str]:
    p = params(solver)
    s = _solve(p)
    if s is None:
        return []
    runs = s["runs"]
    return [f"Double pendulum integrated numerically (DOP853, tolerance 1e-12, energy drift {s['drift']:.1e} J): "
            f"starts {runs[0]['d0']:.0e} rad apart split by {SPLIT} rad at {runs[0]['split']:.1f} s; "
            f"Lyapunov exponent ≈ {s['rate']:.2f} per second; a 1000× more precise start splits at "
            f"{runs[1]['split']:.1f} s."]


_TEMPLATE = r'''"""Generated by AetherLab - problem: how far ahead can we predict a double pendulum?"""

import math

import numpy as np
from manim import *

__HELPERS__


class __CLASS__(Scene):
    def construct(self):
        D = __DATA__
        ts = D["t"]
        a1, a2 = D["a"]
        b1, b2 = D["b"]
        pivot = np.array([-4.2, 0.55, 0.0])
        arm = 1.3
        t = ValueTracker(0.0)

        def joints(th1, th2):
            p1 = pivot + arm * np.array([math.sin(th1), -math.cos(th1), 0.0])
            return p1, p1 + arm * np.array([math.sin(th2), -math.cos(th2), 0.0])

        def at(series):
            return float(np.interp(t.get_value(), ts, series))

        def pendulum(s1, s2, color, width):
            def draw():
                p1, p2 = joints(at(s1), at(s2))
                return VGroup(Line(pivot, p1, color=color, stroke_width=width), Line(p1, p2, color=color, stroke_width=width),
                              Dot(p1, radius=0.09, color=color), Dot(p2, radius=0.11, color=color))
            return always_redraw(draw)

        # 1. Picture it: twins that look like one pendulum.
        title = label("How far ahead can we predict it?", 40, YELLOW).to_edge(UP, buff=0.3)
        mount = VGroup(Line(pivot + LEFT * 0.5, pivot + RIGHT * 0.5, color=GREY_B, stroke_width=4), Dot(pivot, color=GREY_B))
        twin_a = pendulum(a1, a2, WHITE, 5)
        twin_b = pendulum(b1, b2, PINK, 3)
        problem = VGroup(label(D["problem"], 27, WHITE, 7.8), label(D["problem2"], 27, WHITE, 7.8),
                         label(D["question"], 28, TEAL_A, 7.8)).arrange(DOWN, buff=0.22, aligned_edge=LEFT)
        problem.move_to([2.8, 0.9, 0])
        twin_note = label(D["twin_note"], 22, PINK, 5.4).move_to([-4.2, -3.0, 0])
        self.play(Write(title), FadeIn(mount), run_time=1.2)
        self.play(FadeIn(twin_a), FadeIn(twin_b), FadeIn(twin_note), run_time=1.0)
        self.play(FadeIn(problem[0]), run_time=0.9)
        self.play(FadeIn(problem[1]), run_time=0.9)
        self.play(FadeIn(problem[2]), run_time=0.9)
        self.wait(4.0)

        # 2. The rules are exact.
        step1 = chip("1 · the rules are exact")
        self.play(FadeOut(title), FadeOut(problem), FadeIn(step1), run_time=0.7)
        rules = label(D["rules"], 26, WHITE, 8.2).move_to([2.8, 2.6, 0])
        eom1 = eq(D["tex_eom1"], D["plain_eom1"], 30, WHITE, 8.4).move_to([2.8, 1.35, 0])
        eom2 = eq(D["tex_eom2"], D["plain_eom2"], 30, WHITE, 8.4).move_to([2.8, -0.05, 0])
        no_formula = label(D["no_formula"], 24, GREY_A, 8.2).move_to([2.8, -1.25, 0])
        self.play(FadeIn(rules), run_time=0.8)
        self.play(Write(eom1), run_time=2.2)
        self.play(Write(eom2), run_time=2.0)
        self.wait(3.0)
        self.play(FadeIn(no_formula), run_time=0.8)
        self.wait(3.0)

        # 3. Watch the gap grow, on a log scale.
        step2 = chip("2 · watch the gap grow")
        self.play(FadeOut(VGroup(rules, eom1, eom2, no_formula)), FadeOut(step1), FadeIn(step2), run_time=0.8)
        x_max, y_min = D["x_max"], D["y_min"]
        ax = Axes(x_range=[0, x_max, 5], y_range=[y_min, 1, 1], x_length=6.6, y_length=4.9,
                  axis_config={"color": GREY_B, "include_ticks": True}, tips=False).move_to([3.5, -0.2, 0])
        x_lab = label("time (s)", 20, GREY_A).next_to(ax, DOWN, buff=0.45)
        x_marks = VGroup(*[label(f"{v}", 18, GREY_A).next_to(ax.c2p(v, y_min), DOWN, buff=0.1)
                           for v in range(0, int(x_max) + 1, 10)])
        y_marks = VGroup(*[eq(tx, pl, 24, GREY_A).next_to(ax.c2p(0, v), LEFT, buff=0.1)
                           for tx, pl, v in [("1", "1", 0)] + [(f"10^{{{k}}}", f"1e{k}", k)
                                                                for k in range(-6, y_min - 1, -6)]])
        y_lab = label("gap between the twins (rad)", 20, GREY_A).rotate(PI / 2).next_to(y_marks, LEFT, buff=0.15)
        split_line = DashedLine(ax.c2p(0, D["split_log"]), ax.c2p(x_max, D["split_log"]), color=RED_B, stroke_width=2)
        # anchored by its right edge to the axis end: the Cloud font runs wider than the local one
        split_t = label("visibly different (0.5 rad)", 20, RED_B, 3.4).next_to(
            ax.c2p(x_max, D["split_log"]), UP, buff=0.08).align_to(ax.c2p(x_max, D["split_log"]), RIGHT)
        self.play(Create(ax), FadeIn(x_lab), FadeIn(x_marks), FadeIn(y_marks), FadeIn(y_lab), run_time=1.2)
        self.play(Create(split_line), FadeIn(split_t), run_time=0.8)
        g0 = D["graph"][0]

        def gap_curve():
            now = t.get_value()
            pts = [ax.c2p(x, y) for x, y in g0 if x <= now]
            if len(pts) < 2:
                pts = [ax.c2p(0, g0[0][1]), ax.c2p(0.01, g0[0][1])]
            return VMobject(color=PINK, stroke_width=4).set_points_as_corners(pts)

        live = always_redraw(gap_curve)
        clock = always_redraw(lambda: label(f"t = {t.get_value():4.1f} s", 26, WHITE).move_to([-6.0, -3.3, 0]))
        tail_a = TracedPath(lambda: joints(at(a1), at(a2))[1], stroke_color=WHITE, stroke_width=2, dissipating_time=1.2)
        tail_b = TracedPath(lambda: joints(at(b1), at(b2))[1], stroke_color=PINK, stroke_width=2, dissipating_time=1.2)
        self.add(tail_a, tail_b, live, clock)
        self.play(FadeOut(twin_note), run_time=0.3)
        split = D["splits"][0]
        self.play(t.animate.set_value(split), run_time=split * 0.85, rate_func=linear)
        flash_pt = ax.c2p(split, D["split_log"])
        split_lab = label(D["split_label"], 24, YELLOW).next_to(flash_pt, UP, buff=0.35).shift(LEFT * 0.6)
        self.play(Flash(flash_pt, color=YELLOW), FadeIn(split_lab), t.animate.set_value(split + 0.6), run_time=0.9,
                  rate_func=linear)
        self.play(t.animate.set_value(ts[-1]), run_time=(ts[-1] - split - 0.6) * 0.85, rate_func=linear)
        self.wait(2.0)

        # 4. Read the growth rate off the straight line.
        step3 = chip("3 · read the growth rate")
        for m in (twin_a, twin_b, tail_a, tail_b, clock):
            m.clear_updaters()
        self.play(FadeOut(VGroup(twin_a, twin_b, tail_a, tail_b, mount, clock)), FadeOut(step2), FadeIn(step3),
                  run_time=0.8)
        slope = D["rate"] / math.log(10)
        fit = DashedLine(ax.c2p(0.5, D["fit_b"] + slope * 0.5), ax.c2p(split, D["fit_b"] + slope * split),
                         color=YELLOW, stroke_width=3)
        self.play(Create(fit), run_time=1.2)
        panel_x = -3.9
        e_g = VGroup(eq(D["tex_growth"], D["plain_growth"], 34, YELLOW, 5.3),
                     eq(D["tex_rate"], D["plain_rate"], 32, YELLOW, 5.3)).arrange(DOWN, aligned_edge=LEFT, buff=0.15)
        e_d = eq(D["tex_double"], D["plain_double"], 32, WHITE, 5.3)
        e_h = eq(D["tex_horizon"], D["plain_horizon"], 32, WHITE, 5.3)
        meas = label(D["measured"], 24, GREEN_B, 5.3)
        box = VGroup(e_g, e_d, e_h, meas).arrange(DOWN, buff=0.3, aligned_edge=LEFT)
        bg = BackgroundRectangle(box, color=BLACK, fill_opacity=0.85, buff=0.2)
        VGroup(bg, box).move_to([panel_x, 1.0, 0])
        self.play(FadeIn(bg), Write(e_g), run_time=1.6)
        self.wait(2.0)
        self.play(Write(e_d), run_time=1.2)
        self.wait(1.5)
        self.play(Write(e_h), run_time=1.4)
        self.play(FadeIn(meas), run_time=0.8)
        self.wait(3.5)

        # 5. What if we measured 1000 times better?
        step4 = chip("4 · what if we measure 1000× better?")
        self.play(FadeOut(VGroup(bg, e_g, e_d, e_h, meas)), FadeOut(step3), FadeIn(step4), run_time=0.8)
        e_x = eq(D["tex_extra"], D["plain_extra"], 32, WHITE, 5.3).move_to([panel_x, 2.5, 0])
        x_note = label(D["extra_note"], 26, GREY_A, 5.3).next_to(e_x, DOWN, buff=0.2)
        self.play(Write(e_x), run_time=1.5)
        self.play(FadeIn(x_note), run_time=0.8)
        self.wait(2.0)
        colors = [PINK, ORANGE, TEAL]
        run_texts = VGroup()
        for k in range(len(D["graph"])):
            if k == 0:
                run_texts.add(eq(D["run_tex"][0], D["run_plain"][0], 32, colors[0], 5.3))
                continue
            curve = VMobject(color=colors[k], stroke_width=4).set_points_as_corners(
                [ax.c2p(x, y) for x, y in D["graph"][k]])
            mark = Dot(ax.c2p(D["splits"][k], D["split_log"]), color=colors[k], radius=0.08)
            self.play(Create(curve), run_time=2.2, rate_func=linear)
            self.play(Flash(mark, color=colors[k]), FadeIn(mark), run_time=0.7)
            run_texts.add(eq(D["run_tex"][k], D["run_plain"][k], 32, colors[k], 5.3))
        run_texts.arrange(DOWN, aligned_edge=LEFT, buff=0.14).move_to([panel_x, 0.95, 0])
        self.play(FadeIn(run_texts), run_time=0.9)
        gains = label(D["gains"], 24, YELLOW, 5.3).move_to([panel_x, -0.05, 0])
        weather = VGroup(label(D["weather"], 26, WHITE, 5.3), label(D["weather2"], 26, WHITE, 5.3)).arrange(
            DOWN, buff=0.1).move_to([panel_x, -0.8, 0])
        self.play(FadeIn(gains), run_time=0.9)
        self.play(FadeIn(weather), run_time=0.9)
        self.wait(4.0)

        # 6. Check the simulation itself, then the answer.
        step5 = chip("5 · check")
        check = VGroup(eq(D["tex_check"], D["plain_check"], 28, GREEN_B, 5.3), label(D["check1b"], 24, GREEN_B, 5.3),
                       label(D["check2"], 26, GREEN_B, 5.3), label(D["check3"], 26, GREEN_B, 5.3)).arrange(
            DOWN, aligned_edge=LEFT, buff=0.12).move_to([panel_x, 1.9, 0])
        self.play(FadeOut(VGroup(e_x, x_note, run_texts, gains, weather)), FadeOut(step4), FadeIn(step5), run_time=0.8)
        self.play(FadeIn(check), run_time=0.9)
        self.wait(4.0)
        answer = VGroup(label(D["answer"], 30, YELLOW, 5.1), label(D["answer2"], 30, YELLOW, 5.1)).arrange(DOWN, buff=0.12)
        abox = SurroundingRectangle(answer, color=YELLOW, buff=0.18, corner_radius=0.12)
        card = VGroup(BackgroundRectangle(abox, color=BLACK, fill_opacity=0.9), answer, abox).move_to([panel_x, -0.6, 0])
        self.play(FadeIn(card, scale=0.9), run_time=1.0)
        self.wait(5.0)
'''
