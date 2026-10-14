"""Problem video: how long until the swing walks across?

"Two identical 1.0 m pendulums (1.0 kg) are joined by a weak spring
(k = 1.0 N/m). One is pulled 10° aside and let go. How long until all the
swinging has moved to the other one?"

Device: one motion, two simple dances. First we watch the swing drain from A
into B, with an energy bar under each bob. Then two small insets show the only
two motions that never change: swinging in step (the spring never stretches)
and swinging opposite (the spring pulls both back). Each has one pure
frequency. The real motion is the two dances added; they drift out of step,
and when they are exactly out of step A stands still. That gives
T = π / (ω₂ − ω₁), and the full nonlinear simulation checks it.

Solving arc (subgoal labels): 1 watch the swing walk across, 2 two dances that
never change, 3 add the two dances, 4 check, 5 what if.
"""

from __future__ import annotations

import math
from typing import Any

from aetherlab.services.scene_components.problems._kit import fill, pick, text_of, variables_of

_STEMS = ("coupled pendul", "sympathetic pendul", "pendulums connected", "pendulums joined", "spring-coupled pendul",
          "pendulums coupled", "coupled swing")


def params(solver: Any) -> dict[str, float]:
    v = variables_of(solver)
    length = pick(v, ("l", "length", "l1", "pendulum_length"))
    mass = pick(v, ("m", "mass", "m1", "bob_mass"))
    k = pick(v, ("k", "spring_constant", "stiffness", "k_spring", "kappa"))
    g = pick(v, ("g", "gravity"))
    amp = pick(v, ("theta0", "theta", "angle", "amplitude", "a0", "theta_0"))
    if amp is not None and abs(amp) > 0.8:
        amp = math.radians(amp)                    # degrees unless it looks like radians
    p = {"L": length if length and 0.1 <= length <= 10 else 1.0,
         "m": mass if mass and 0.01 <= mass <= 100 else 1.0,
         "k": k if k and 0.001 <= k <= 1000 else 1.0,
         "g": g if g and 0.5 <= g <= 30 else 9.81,
         "amp": abs(amp) if amp and 0.02 <= abs(amp) <= 0.5 else math.radians(10.0)}
    return p


def matches(solver: Any) -> bool:
    text = text_of(solver)
    if any(s in text for s in _STEMS):
        return True
    return "pendul" in text and "spring" in text and ("two" in text or "coupled" in text) and "double pendulum" not in text


def transfer_time(p: dict[str, float], k: float | None = None) -> tuple[float, float, float]:
    k = p["k"] if k is None else k
    w1 = math.sqrt(p["g"] / p["L"])
    w2 = math.sqrt(p["g"] / p["L"] + 2.0 * k / p["m"])
    return w1, w2, math.pi / (w2 - w1)


def _solve(p: dict[str, float]) -> dict[str, Any] | None:
    import numpy as np
    from scipy.integrate import solve_ivp

    g, length, m, k, a0 = p["g"], p["L"], p["m"], p["k"], p["amp"]
    w1, w2, transfer_period = transfer_time(p)
    if not 2.0 <= transfer_period <= 60.0:
        return None

    def f(t, y):
        a, b, va, vb = y
        return [va, vb, -g / length * math.sin(a) - k / m * (math.sin(a) - math.sin(b)) * math.cos(a),
                -g / length * math.sin(b) - k / m * (math.sin(b) - math.sin(a)) * math.cos(b)]

    t_end = 2.4 * transfer_period
    ts = np.linspace(0.0, t_end, int(t_end / 0.01) + 1)
    s = solve_ivp(f, (0.0, t_end), [a0, 0.0, 0.0, 0.0], t_eval=ts, method="DOP853", rtol=1e-10, atol=1e-12)
    if not s.success:
        return None
    a, b, va, vb = s.y
    ea = 0.5 * m * (length * va) ** 2 + m * g * length * (1 - np.cos(a))
    eb = 0.5 * m * (length * vb) ** 2 + m * g * length * (1 - np.cos(b))
    spring = 0.5 * k * length * length * (np.sin(a) - np.sin(b)) ** 2
    total = ea + eb + spring
    first = ts < 1.5 * transfer_period
    i = int(np.argmin(np.where(first, ea, np.inf)))
    step = 2
    return {
        "w1": w1, "w2": w2, "T": transfer_period, "T_sim": float(ts[i]), "left": float(ea[i] / total[0]),
        "drift": float(np.max(np.abs(total - total[0])) / total[0]),
        "t": [round(float(x), 3) for x in ts[::step]],
        "a": [round(float(x), 5) for x in a[::step]], "b": [round(float(x), 5) for x in b[::step]],
        "ea": [round(float(x), 4) for x in (ea / total[0])[::step]], "eb": [round(float(x), 4) for x in (eb / total[0])[::step]],
        "graph_t": [round(float(x), 3) for x in ts[::10]],
        "graph_a": [round(float(x), 5) for x in a[::10]], "graph_b": [round(float(x), 5) for x in b[::10]],
        "t_end": t_end,
    }


def build(class_name: str, solver: Any) -> str | None:
    p = params(solver)
    s = _solve(p)
    if s is None or abs(s["T_sim"] - s["T"]) > 0.05 * s["T"] or s["left"] > 0.02 or s["drift"] > 1e-6:
        return None
    g, length, m, k, a0 = p["g"], p["L"], p["m"], p["k"], p["amp"]
    w1, w2, transfer_period = s["w1"], s["w2"], s["T"]
    deg = math.degrees(a0)
    ks = [k / 4.0, k, 4.0 * k]
    curve = [(round(kk, 5), round(transfer_time(p, kk)[2], 4))
             for kk in [k / 4.0 * (16.0 ** (i / 60.0)) for i in range(61)]]
    data = {
        "L": length, "amp": a0, "T": round(transfer_period, 4), "T_sim": round(s["T_sim"], 3), "w1": w1, "w2": w2,
        "t": s["t"], "a": s["a"], "b": s["b"], "ea": s["ea"], "eb": s["eb"],
        "gt": s["graph_t"], "ga": s["graph_a"], "gb": s["graph_b"], "t_end": round(s["t_end"], 3),
        "curve": curve, "ks": [round(x, 5) for x in ks], "Ts": [round(transfer_time(p, x)[2], 3) for x in ks],
        "problem": f"Two identical {length:g} m pendulums ({m:g} kg)",
        "problem1b": f"are joined by a weak spring (k = {k:g} N/m).",
        "problem2": f"Pendulum A is pulled {deg:.0f}° aside and let go. B starts at rest.",
        "question": "How long until all the swinging has moved to B?",
        "watch_note": "The swing drains out of A and into B, then back again",
        "tex_w1": rf"\omega_1=\sqrt{{\frac{{g}}{{L}}}}=\sqrt{{\frac{{{g:g}}}{{{length:g}}}}}={w1:.3f}\ \text{{rad/s}}",
        "plain_w1": f"ω1 = √(g/L) = √({g:g}/{length:g}) = {w1:.3f} rad/s",
        "tex_w2": rf"\omega_2=\sqrt{{\frac{{g}}{{L}}+\frac{{2k}}{{m}}}}=\sqrt{{{g / length:.2f}+{2 * k / m:.2f}}}={w2:.3f}\ \text{{rad/s}}",
        "plain_w2": f"ω2 = √(g/L + 2k/m) = √({g / length:.2f} + {2 * k / m:.2f}) = {w2:.3f} rad/s",
        "in_step": "in step: the spring never stretches",
        "opposite": "opposite: the spring pulls both back",
        "tex_sum_a": r"\theta_A=\tfrac{\theta_0}{2}\left(\cos\omega_1t+\cos\omega_2t\right)"
                     r"=\theta_0\cos\!\left(\tfrac{\omega_2-\omega_1}{2}t\right)\cos\!\left(\tfrac{\omega_1+\omega_2}{2}t\right)",
        "plain_sum_a": "θA = (θ0/2)(cos ω1t + cos ω2t) = θ0 cos((ω2-ω1)t/2) cos((ω1+ω2)t/2)",
        "tex_sum_b": r"\theta_B=\tfrac{\theta_0}{2}\left(\cos\omega_1t-\cos\omega_2t\right)"
                     r"=\theta_0\sin\!\left(\tfrac{\omega_2-\omega_1}{2}t\right)\sin\!\left(\tfrac{\omega_1+\omega_2}{2}t\right)",
        "plain_sum_b": "θB = (θ0/2)(cos ω1t - cos ω2t) = θ0 sin((ω2-ω1)t/2) sin((ω1+ω2)t/2)",
        "envelope_note": "the slow envelope: A is still when the two dances are exactly out of step",
        "tex_ws": rf"\omega_1={w1:.3f}\ \text{{rad/s}},\qquad\omega_2={w2:.3f}\ \text{{rad/s}}",
        "plain_ws": f"ω1 = {w1:.3f} rad/s,   ω2 = {w2:.3f} rad/s",
        "tex_T": rf"T=\frac{{\pi}}{{\omega_2-\omega_1}}=\frac{{\pi}}{{{w2:.3f}-{w1:.3f}}}={transfer_period:.1f}\ \text{{s}}",
        "plain_T": f"T = π / (ω2 - ω1) = π / ({w2:.3f} - {w1:.3f}) = {transfer_period:.1f} s",
        "check": f"Full simulation (no small-swing shortcut): A is still at {s['T_sim']:.1f} s",
        "check2": f"A keeps {100 * s['left']:.2f}% of the energy; the formula said {transfer_period:.1f} s",
        "dots_note": "dots: simulation;  lines: the two-dance formula",
        "whatif_note": "A weak spring passes the swing slowly; a stiff one quickly",
        "k_labels": [f"k = {x:g} N/m: {transfer_time(p, x)[2]:.1f} s" for x in ks],
        "answer": f"Answer: after about {transfer_period:.0f} s ({transfer_period:.1f} s by formula, {s['T_sim']:.1f} s simulated)",
        "answer2": "all the swinging has moved from A to B.",
    }
    return fill(_TEMPLATE, class_name, data)


def check_lines(solver: Any) -> list[str]:
    p = params(solver)
    s = _solve(p)
    if s is None:
        return []
    return [f"Coupled pendulums simulated with the full nonlinear equations (L = {p['L']:g} m, k = {p['k']:g} N/m, "
            f"{math.degrees(p['amp']):.0f}° start): pendulum A is still at {s['T_sim']:.2f} s, keeping "
            f"{100 * s['left']:.2f}% of the energy; the normal-mode formula π/(ω₂ − ω₁) gives {s['T']:.2f} s."]


_TEMPLATE = r'''"""Generated by AetherLab - problem: how long until the swing walks across?"""

import math

import numpy as np
from manim import *

__HELPERS__


class __CLASS__(Scene):
    def construct(self):
        D = __DATA__
        ts, A, B, EA, EB = D["t"], D["a"], D["b"], D["ea"], D["eb"]
        T, w1, w2, a0 = D["T"], D["w1"], D["w2"], D["amp"]
        beam_y, arm = 2.3, 2.7
        pa, pb = np.array([-5.4, beam_y, 0.0]), np.array([-3.2, beam_y, 0.0])
        t = ValueTracker(0.0)

        def at(series):
            return float(np.interp(t.get_value(), ts, series))

        def bob(pivot, angle, length=arm):
            return pivot + length * np.array([math.sin(angle), -math.cos(angle), 0.0])

        def spring(p, q, coils=9, amp=0.12):
            d = q - p
            n = np.array([-d[1], d[0], 0.0]) / (np.linalg.norm(d) + 1e-9)
            pts = [p + d * 0.12]
            for i in range(coils * 2):
                pts.append(p + d * (0.12 + 0.76 * (i + 0.5) / (coils * 2)) + n * amp * (1 if i % 2 == 0 else -1))
            pts += [p + d * 0.88, q]
            return VMobject(color=GREY_B, stroke_width=2.5).set_points_as_corners([p] + pts)

        def rig():
            ba, bb = bob(pa, at(A)), bob(pb, at(B))
            return VGroup(Line(pa, ba, color=GREY_A, stroke_width=3), Line(pb, bb, color=GREY_A, stroke_width=3),
                          spring(ba, bb), Dot(ba, radius=0.16, color=BLUE), Dot(bb, radius=0.16, color=ORANGE))

        bar_y, bar_h = -3.35, 1.5

        def bars():
            ea, eb = at(EA), at(EB)
            ra = Rectangle(width=0.6, height=max(ea * bar_h, 0.01), stroke_width=0, fill_color=BLUE, fill_opacity=0.85)
            rb = Rectangle(width=0.6, height=max(eb * bar_h, 0.01), stroke_width=0, fill_color=ORANGE, fill_opacity=0.85)
            return VGroup(ra.move_to([pa[0], bar_y + ra.height / 2, 0]), rb.move_to([pb[0], bar_y + rb.height / 2, 0]))

        # 1. Picture it: two pendulums, one spring, one push.
        title = label("How long until the swing walks across?", 40, YELLOW).to_edge(UP, buff=0.3)
        beam = Line([-6.4, beam_y, 0], [-2.2, beam_y, 0], color=GREY_B, stroke_width=6)
        pendulums = always_redraw(rig)
        energy = always_redraw(bars)
        bar_base = Line([-6.2, bar_y, 0], [-2.4, bar_y, 0], color=GREY_B, stroke_width=2)
        bar_tags = VGroup(label("A", 24, BLUE).next_to([pa[0], bar_y, 0], DOWN, buff=0.1),
                          label("B", 24, ORANGE).next_to([pb[0], bar_y, 0], DOWN, buff=0.1))
        bar_title = label("swing energy", 20, GREY_A).move_to([-4.3, bar_y + bar_h + 0.25, 0])
        problem = VGroup(label(D["problem"], 28, WHITE, 8.0), label(D["problem1b"], 28, WHITE, 8.0),
                         label(D["problem2"], 28, WHITE, 8.0),
                         label(D["question"], 28, TEAL_A, 8.0)).arrange(DOWN, buff=0.22, aligned_edge=LEFT)
        problem.move_to([2.7, 0.9, 0])
        self.play(Write(title), Create(beam), run_time=1.1)
        self.play(FadeIn(pendulums), FadeIn(energy), Create(bar_base), FadeIn(bar_tags), FadeIn(bar_title), run_time=1.0)
        self.play(FadeIn(problem[0]), FadeIn(problem[1]), run_time=1.0)
        self.play(FadeIn(problem[2]), run_time=0.9)
        self.play(FadeIn(problem[3]), run_time=0.9)
        self.wait(4.0)

        # 2. Watch: the swing drains out of A and into B.
        step1 = chip("1 · watch the swing walk across")
        clock = always_redraw(lambda: label(f"t = {t.get_value():4.1f} s", 26).move_to([-4.3, 3.05, 0]))
        self.play(FadeOut(title), FadeOut(problem), FadeIn(step1), FadeIn(clock), run_time=0.8)
        watch = min(T * 1.02, D["t_end"])
        self.play(t.animate.set_value(watch), run_time=min(14.0, watch), rate_func=linear)
        note = label(D["watch_note"], 26, WHITE, 8.2).move_to([2.7, 1.2, 0])
        self.play(FadeIn(note), Indicate(energy, color=ORANGE), run_time=1.0)
        self.wait(3.0)

        # 3. Two dances that never change.
        step2 = chip("2 · two dances that never change")
        self.play(FadeOut(note), FadeOut(step1), FadeIn(step2), run_time=0.7)
        s = ValueTracker(0.0)
        mini = 1.25

        def dance(cx, sign, w, color):
            piv_a, piv_b = np.array([cx - 0.7, 2.5, 0.0]), np.array([cx + 0.7, 2.5, 0.0])

            def draw():
                ang = 0.35 * math.cos(w * s.get_value())
                ba, bb = bob(piv_a, ang, mini), bob(piv_b, sign * ang, mini)
                return VGroup(Line(piv_a + LEFT * 0.3, piv_b + RIGHT * 0.3, color=GREY_B, stroke_width=3),
                              Line(piv_a, ba, color=GREY_A, stroke_width=2), Line(piv_b, bb, color=GREY_A, stroke_width=2),
                              spring(ba, bb, 6, 0.07), Dot(ba, radius=0.1, color=color), Dot(bb, radius=0.1, color=color))
            return always_redraw(draw)

        d1, d2 = dance(0.6, 1, w1, TEAL), dance(4.6, -1, w2, PINK)
        c1 = label(D["in_step"], 22, TEAL, 3.6).move_to([0.6, 0.85, 0])
        c2 = label(D["opposite"], 22, PINK, 3.6).move_to([4.6, 0.85, 0])
        e1 = eq(D["tex_w1"], D["plain_w1"], 36, TEAL, 8.2).move_to([2.6, -0.3, 0])
        e2 = eq(D["tex_w2"], D["plain_w2"], 36, PINK, 8.2).move_to([2.6, -1.45, 0])
        self.play(FadeIn(d1), FadeIn(d2), FadeIn(c1), FadeIn(c2), run_time=1.0)
        self.play(s.animate.set_value(6.0), Write(e1), run_time=6.0, rate_func=linear)
        self.play(s.animate.set_value(12.0), Write(e2), run_time=6.0, rate_func=linear)
        pure = label("each dance has one pure frequency; the opposite dance is a little faster", 22, GREY_A, 8.2)
        pure.move_to([2.6, -2.5, 0])
        self.play(FadeIn(pure), s.animate.set_value(16.0), run_time=3.0, rate_func=linear)
        self.wait(1.5)

        # 4. Add the two dances: they drift out of step, and A stands still.
        step3 = chip("3 · add the two dances")
        d1.clear_updaters()
        d2.clear_updaters()
        ws = eq(D["tex_ws"], D["plain_ws"], 32, WHITE, 8.2).move_to([2.6, 2.75, 0])
        self.play(FadeOut(VGroup(d1, d2, c1, c2, pure, e1, e2)), FadeOut(step2), FadeIn(step3), FadeIn(ws), run_time=0.9)
        sa = eq(D["tex_sum_a"], D["plain_sum_a"], 30, BLUE_B, 8.4).move_to([2.6, 1.85, 0])
        sb = eq(D["tex_sum_b"], D["plain_sum_b"], 30, ORANGE, 8.4).move_to([2.6, 1.0, 0])
        self.play(Write(sa), run_time=2.0)
        self.play(Write(sb), run_time=2.0)
        self.wait(2.0)
        t_max = D["gt"][-1]
        ax = Axes(x_range=[0, t_max, 5], y_range=[-1.15, 1.15, 0.5], x_length=8.0, y_length=2.6,
                  axis_config={"color": GREY_B, "include_ticks": False}, tips=False).move_to([2.7, -1.75, 0])
        x_lab = label("time (s)", 20, GREY_A).next_to(ax, DOWN, buff=0.1).shift(RIGHT * 3.4)
        self.play(Create(ax), FadeIn(x_lab), run_time=0.8)
        dw, sw = (w2 - w1) / 2, (w1 + w2) / 2
        fa = ax.plot(lambda u: math.cos(dw * u) * math.cos(sw * u), x_range=[0, t_max, 0.02], color=BLUE_B, stroke_width=2)
        fb = ax.plot(lambda u: math.sin(dw * u) * math.sin(sw * u), x_range=[0, t_max, 0.02], color=ORANGE, stroke_width=2)
        env_a = ax.plot(lambda u: abs(math.cos(dw * u)), x_range=[0, t_max, 0.05], color=BLUE_E, stroke_width=3)
        env_b = ax.plot(lambda u: abs(math.sin(dw * u)), x_range=[0, t_max, 0.05], color=ORANGE, stroke_width=3,
                        stroke_opacity=0.6)
        self.play(Create(fa), Create(fb), run_time=3.0, rate_func=linear)
        envs = VGroup(DashedVMobject(env_a, num_dashes=40), DashedVMobject(env_b, num_dashes=40))
        self.play(Create(envs), run_time=1.5)
        env_note = label(D["envelope_note"], 22, GREY_A, 8.2).move_to([2.7, 0.3, 0])
        eT = eq(D["tex_T"], D["plain_T"], 36, YELLOW, 8.0)
        self.play(FadeIn(env_note), run_time=0.8)
        mark = DashedLine(ax.c2p(T, -1.15), ax.c2p(T, 1.15), color=YELLOW, stroke_width=3)
        mark_t = label(f"{T:.1f} s", 22, YELLOW).next_to(ax.c2p(T, 1.15), UP, buff=0.05)
        self.play(Create(mark), FadeIn(mark_t), run_time=0.9)
        self.play(FadeOut(env_note), FadeOut(sa), FadeOut(sb), run_time=0.5)
        eT.move_to([2.7, 1.75, 0])
        self.play(Write(eT), run_time=1.6)
        self.wait(3.0)

        # 5. Check: the full simulation, dots on the formula curves; the pendulums confirm it.
        step4 = chip("4 · check it")
        self.play(FadeOut(step3), FadeIn(step4), run_time=0.6)
        dots = VGroup()
        for u, va, vb in list(zip(D["gt"], D["ga"], D["gb"]))[::3]:
            dots.add(Dot(ax.c2p(u, va / a0), radius=0.03, color=BLUE_A), Dot(ax.c2p(u, vb / a0), radius=0.03, color=ORANGE))
        self.play(LaggedStart(*[FadeIn(d) for d in dots], lag_ratio=0.002), run_time=2.0)
        chk = VGroup(label(D["check"], 24, GREEN_B, 8.2), label(D["check2"], 24, GREEN_B, 8.2),
                     label(D["dots_note"], 20, GREY_A, 8.2)).arrange(DOWN, buff=0.1).move_to([2.7, 0.55, 0])
        self.play(FadeIn(chk), run_time=1.0)
        t.set_value(0.0)
        self.play(t.animate.set_value(D["T_sim"]), run_time=6.0, rate_func=linear)
        self.play(Flash(bob(pb, at(B)), color=GREEN), Indicate(energy, color=GREEN), run_time=1.0)
        self.wait(3.0)

        # 6. What if the spring is stiffer or weaker?
        step5 = chip("5 · what if the spring changes?")
        self.play(FadeOut(VGroup(chk, dots, fa, fb, envs, ax, x_lab, mark, mark_t, ws, eT)), FadeOut(step4), FadeIn(step5),
                  run_time=0.8)
        k_lo, k_hi = D["curve"][0][0], D["curve"][-1][0]
        t_hi = max(T for _, T in D["curve"])
        kax = Axes(x_range=[0, k_hi * 1.05, k_hi / 4], y_range=[0, t_hi * 1.1, t_hi / 4], x_length=6.8, y_length=3.8,
                   axis_config={"color": GREY_B, "include_ticks": False}, tips=False).move_to([2.9, -0.9, 0])
        kx = label("spring stiffness k (N/m)", 20, GREY_A).next_to(kax, DOWN, buff=0.15)
        ky = label("time to walk across (s)", 20, GREY_A).rotate(PI / 2).next_to(kax, LEFT, buff=0.15)
        kc = VMobject(color=YELLOW, stroke_width=4).set_points_smoothly([kax.c2p(x, y) for x, y in D["curve"]])
        self.play(Create(kax), FadeIn(kx), FadeIn(ky), run_time=0.9)
        self.play(Create(kc), run_time=1.8)
        rows = VGroup()
        for kk, TT, txt, col in zip(D["ks"], D["Ts"], D["k_labels"], (BLUE_B, YELLOW, PINK)):
            dot = Dot(kax.c2p(kk, TT), color=col, radius=0.09)
            self.play(FadeIn(dot, scale=2), run_time=0.4)
            rows.add(label(txt, 24, col, 5.0))
        rows.arrange(DOWN, aligned_edge=LEFT, buff=0.14).move_to([4.2, 1.9, 0])
        note = label(D["whatif_note"], 22, GREY_A, 6.6).move_to([2.9, 2.85, 0])
        self.play(FadeIn(rows), FadeIn(note), run_time=1.0)
        self.wait(3.5)
        answer = VGroup(label(D["answer"], 28, YELLOW, 8.4), label(D["answer2"], 28, YELLOW, 8.4)).arrange(DOWN, buff=0.1)
        box = SurroundingRectangle(answer, color=YELLOW, buff=0.2, corner_radius=0.12)
        card = VGroup(BackgroundRectangle(box, color=BLACK, fill_opacity=0.9), answer, box).move_to([2.7, 2.2, 0])
        self.play(FadeOut(rows), FadeOut(note), FadeIn(card, scale=0.9), run_time=1.0)
        self.wait(5.0)
'''
