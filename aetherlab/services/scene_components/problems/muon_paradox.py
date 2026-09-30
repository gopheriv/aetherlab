"""Problem video: do cosmic-ray muons reach the ground?

"Muons are made 15 km up and fly down at 0.995 c. Their half-life is 1.52 µs.
What fraction reaches the ground?"

Device: two stories, one ending. The everyday guess (50 µs of flight is 33
half-lives) kills every muon within the first kilometres. Then the same
descent is told twice, side by side: in Earth's story the muon's clock runs
ten times slow; in the muon's story the atmosphere is ten times thinner. Both
stories end with the same muons at the detector, and 400 simulated muons with
random decay times prove the count.

Solving arc (subgoal labels): 1 the everyday guess, 2 Earth's story, 3 the
muon's story, 4 check, 5 what if.
"""

from __future__ import annotations

import math
from typing import Any

from aetherlab.services.scene_components.problems._kit import fill, pick, sci, text_of, variables_of

C = 2.99792458e8
_DEFAULTS = {"height_m": 15e3, "beta": 0.995, "half_life_s": 1.52e-6}
_N_MUONS = 400
_SEED = 7


def params(solver: Any) -> dict[str, float]:
    v = variables_of(solver)
    h = pick(v, ("altitude", "height", "h", "altitude_km", "height_km", "distance", "d", "l0", "l", "h0"))
    if h is not None and 0 < h < 200:
        h *= 1e3                                   # a value this small is in km
    beta = pick(v, ("beta", "v_over_c", "fraction_c", "v", "speed", "velocity", "u"))
    if beta is not None and beta > 1.0:
        beta /= C                                  # given in m/s
    half = pick(v, ("half_life", "t_half", "t12", "t_1/2", "halflife", "half_life_us"))
    if half is None:
        tau = pick(v, ("tau", "lifetime", "mean_lifetime", "tau0", "mean_life"))
        half = tau * math.log(2) if tau else None
    if half is not None and half > 1e-3:
        half *= 1e-6                               # given in µs
    return {
        "height_m": h if h and 1e3 <= h <= 1e5 else _DEFAULTS["height_m"],
        "beta": beta if beta and 0.5 <= beta < 0.99999 else _DEFAULTS["beta"],
        "half_life_s": half if half and 1e-7 <= half <= 1e-4 else _DEFAULTS["half_life_s"],
    }


def matches(solver: Any) -> bool:
    return "muon" in text_of(solver)


def _survival(beta: float, h: float, half: float) -> tuple[float, float]:
    """(classical fraction, relativistic fraction) reaching the ground."""
    t_lab = h / (beta * C)
    gamma = 1.0 / math.sqrt(1.0 - beta * beta)
    return 2.0 ** (-t_lab / half), 2.0 ** (-(t_lab / gamma) / half)


def _solve(p: dict[str, float]) -> dict[str, Any]:
    import numpy as np
    from scipy.integrate import solve_ivp

    h, beta, half = p["height_m"], p["beta"], p["half_life_s"]
    gamma = 1.0 / math.sqrt(1.0 - beta * beta)
    t_lab = h / (beta * C)
    tau = t_lab / gamma
    classical, relativistic = _survival(beta, h, half)
    # Ground truth 1: integrate dN/dτ = -N ln2 / t½ along the muon's own clock.
    ode = solve_ivp(lambda t, n: -n * math.log(2) / half, (0.0, tau), [1.0], rtol=1e-10, atol=1e-12)
    # Ground truth 2: 400 muons with random (exponential) lifetimes.
    lives = np.random.default_rng(_SEED).exponential(half / math.log(2), _N_MUONS)
    survivors = int((lives > tau).sum())
    curve = []
    for i in range(61):
        b = 0.90 + 0.0999 * i / 60
        c_f, r_f = _survival(b, h, half)
        curve.append((round(b, 5), round(math.log10(r_f), 4), round(math.log10(c_f), 4)))
    return {
        "gamma": gamma, "t_lab": t_lab, "tau": tau, "classical": classical, "relativistic": relativistic,
        "ode_fraction": float(ode.y[0, -1]), "survivors": survivors, "n": _N_MUONS,
        "lives_us": [round(float(x) * 1e6, 4) for x in lives], "contracted_m": h / gamma, "curve": curve,
        "what_if": {b: _survival(b, h, half)[1] for b in (0.98, 0.999)},
    }


def build(class_name: str, solver: Any) -> str | None:
    p = params(solver)
    s = _solve(p)
    if abs(s["ode_fraction"] - s["relativistic"]) > 1e-6 or abs(s["survivors"] / s["n"] - s["relativistic"]) > 0.05:
        return None
    h_km, beta, half_us = p["height_m"] / 1e3, p["beta"], p["half_life_s"] * 1e6
    t_us, tau_us, gamma = s["t_lab"] * 1e6, s["tau"] * 1e6, s["gamma"]
    n_cl, n_rel = t_us / half_us, tau_us / half_us
    cl_tex, cl_plain = sci(s["classical"], 2)
    pct = 100 * s["relativistic"]
    expected = s["n"] * s["relativistic"]
    b98, b999 = s["what_if"][0.98], s["what_if"][0.999]
    data = {
        "h_km": round(h_km, 4), "beta": beta, "gamma": round(gamma, 5), "t_us": round(t_us, 5),
        "tau_us": round(tau_us, 5), "lives": s["lives_us"], "n": s["n"], "survivors": s["survivors"],
        "curve": s["curve"], "log_rel": round(math.log10(s["relativistic"]), 4),
        "log_cl": round(math.log10(s["classical"]), 4),
        "problem": f"Cosmic rays make muons {h_km:g} km up. They fly down at {beta:g} c.",
        "problem2": f"Half of them decay every {half_us:g} micro-seconds.",
        "question": "What fraction of them reaches the ground?",
        "h_label": f"{h_km:g} km",
        "tex_t": rf"t=\frac{{h}}{{v}}=\frac{{{h_km:g}\,\text{{km}}}}{{{beta:g}\,c}}={t_us:.1f}\,\mu\text{{s}}",
        "plain_t": f"t = h / v = {h_km:g} km / {beta:g} c = {t_us:.1f} micro-s",
        "tex_ncl": rf"\frac{{{t_us:.1f}\,\mu\text{{s}}}}{{{half_us:g}\,\mu\text{{s}}}}={n_cl:.1f}\text{{ half-lives}}",
        "plain_ncl": f"{t_us:.1f} / {half_us:g} = {n_cl:.1f} half-lives",
        "tex_fcl": rf"\left(\tfrac{{1}}{{2}}\right)^{{{n_cl:.1f}}}\approx{cl_tex}",
        "plain_fcl": f"(½)^{n_cl:.1f} ≈ {cl_plain}",
        "guess_result": f"everyday guess: 0 of {s['n']} arrive",
        "paradox": "Yet detectors at sea level catch plenty of muons. Something is missing.",
        "tex_gamma": rf"\gamma=\frac{{1}}{{\sqrt{{1-v^2/c^2}}}}=\frac{{1}}{{\sqrt{{1-{beta:g}^2}}}}={gamma:.1f}",
        "plain_gamma": f"γ = 1/√(1 - v²/c²) = 1/√(1 - {beta:g}²) = {gamma:.1f}",
        "tex_tau": rf"\tau=\frac{{t}}{{\gamma}}=\frac{{{t_us:.1f}\,\mu\text{{s}}}}{{{gamma:.1f}}}={tau_us:.2f}\,\mu\text{{s}}",
        "plain_tau": f"tau = t / γ = {t_us:.1f} / {gamma:.1f} = {tau_us:.2f} micro-s",
        "tex_frel": rf"\frac{{{tau_us:.2f}}}{{{half_us:g}}}={n_rel:.2f}\text{{ half-lives}}\;\Rightarrow\;"
                    rf"\left(\tfrac{{1}}{{2}}\right)^{{{n_rel:.2f}}}={s['relativistic']:.3f}",
        "plain_frel": f"{tau_us:.2f} / {half_us:g} = {n_rel:.2f} half-lives → (½)^{n_rel:.2f} = {s['relativistic']:.3f}",
        "slow_note": f"The muon's clock ticks {gamma:.1f}× slower than ours",
        "tex_len": rf"L=\frac{{L_0}}{{\gamma}}=\frac{{{h_km:g}\,\text{{km}}}}{{{gamma:.1f}}}={s['contracted_m'] / 1e3:.2f}\,\text{{km}}",
        "plain_len": f"L = L0 / γ = {h_km:g} km / {gamma:.1f} = {s['contracted_m'] / 1e3:.2f} km",
        "tex_tmu": rf"t'=\frac{{L}}{{v}}=\frac{{{s['contracted_m'] / 1e3:.2f}\,\text{{km}}}}{{{beta:g}\,c}}"
                   rf"={tau_us:.2f}\,\mu\text{{s}}",
        "plain_tmu": f"t' = L / v = {s['contracted_m'] / 1e3:.2f} km / {beta:g} c = {tau_us:.2f} micro-s",
        "short_label": f"{s['contracted_m'] / 1e3:.2f} km",
        "earth_title": "Earth's story: the muon's clock runs slow",
        "muon_title": "The muon's story: the air is thin",
        "same": f"Same {n_rel:.2f} half-lives in both stories:",
        "same2": f"{pct:.1f}% arrive",
        "bar_guess": "everyday guess", "bar_rel": "relativity", "bar_sim": "simulation",
        "bar_guess_n": "0", "bar_rel_n": f"{expected:.1f}", "bar_sim_n": f"{s['survivors']}",
        "check": f"{s['n']} simulated muons with random decay times:",
        "check2": f"{s['survivors']} reach the ground ({100 * s['survivors'] / s['n']:.1f}%); relativity predicts {pct:.1f}%",
        "whatif_98": f"at 0.98 c: {100 * b98:.2f}% arrive",
        "whatif_999": f"at 0.999 c: {100 * b999:.0f}% arrive",
        "whatif_note": "Faster muons live longer in our eyes: survival climbs steeply near c",
        "answer": f"Answer: about {pct:.0f}% reach the ground.",
        "answer2": f"Time dilation (γ = {gamma:.1f}) turns {n_cl:.0f} half-lives into {n_rel:.1f}.",
    }
    return fill(_TEMPLATE, class_name, data)


def check_lines(solver: Any) -> list[str]:
    p = params(solver)
    s = _solve(p)
    return [f"Muon decay simulated along the muon's own clock (h = {p['height_m'] / 1e3:g} km, v = {p['beta']:g} c, "
            f"half-life {p['half_life_s'] * 1e6:g} µs): γ = {s['gamma']:.2f}, flight {s['t_lab'] * 1e6:.1f} µs in "
            f"Earth's frame but {s['tau'] * 1e6:.2f} µs for the muon; {100 * s['ode_fraction']:.1f}% survive "
            f"({s['survivors']} of {s['n']} random muons), versus {sci(s['classical'], 2)[1]} without relativity."]


_TEMPLATE = r'''"""Generated by AetherLab - problem: do the muons reach the ground?"""

import math

import numpy as np
from manim import *

__HELPERS__


class __CLASS__(Scene):
    def construct(self):
        D = __DATA__
        n, lives = D["n"], D["lives"]
        t_lab, gamma = D["t_us"], D["gamma"]
        top_y, ground_y, col_x, col_w = 2.45, -3.35, -4.75, 1.6
        span = top_y - ground_y
        rng = np.random.default_rng(3)
        xs0 = col_x + rng.uniform(-0.62, 0.62, n)
        ys0 = top_y - rng.uniform(0.0, 0.18, n)

        def column(x, height, top):
            body = Rectangle(width=col_w, height=height, stroke_width=0, fill_opacity=1)
            body.set_fill(color="#15325e")
            body.move_to([x, top - height / 2, 0])
            return body

        # 1. Picture it: a cosmic ray makes a shower of muons at the top of the air.
        title = label("Do the muons reach the ground?", 40, YELLOW).to_edge(UP, buff=0.3)
        air = column(col_x, span, top_y)
        ground = Line([-7.1, ground_y, 0], [-3.1, ground_y, 0], color=GREY_B, stroke_width=4)
        detector = Rectangle(width=1.0, height=0.28, color=TEAL, fill_color=TEAL, fill_opacity=0.5)
        detector.move_to([col_x, ground_y - 0.2, 0])
        det_text = label("detector", 20, TEAL_A).next_to(detector, DOWN, buff=0.08)
        h_brace = BraceBetweenPoints([col_x - 0.95, ground_y, 0], [col_x - 0.95, top_y, 0], LEFT)
        h_text = label(D["h_label"], 24, GREY_A).rotate(PI / 2).next_to(h_brace, LEFT, buff=0.1)
        ray = Line([-2.2, 3.9, 0], [col_x + 0.2, top_y + 0.05, 0], color=YELLOW, stroke_width=5)
        problem = VGroup(label(D["problem"], 26, WHITE, 9.6), label(D["problem2"], 26, WHITE, 9.6),
                         label(D["question"], 28, TEAL_A, 9.6)).arrange(DOWN, buff=0.22, aligned_edge=LEFT)
        problem.move_to([1.6, 1.2, 0])
        self.play(Write(title), FadeIn(air), Create(ground), FadeIn(detector), FadeIn(det_text), run_time=1.4)
        self.play(GrowFromCenter(h_brace), FadeIn(h_text), run_time=0.8)
        self.play(Create(ray), run_time=0.7)
        dots = VGroup(*[Dot([x, y, 0], radius=0.03, color=ORANGE) for x, y in zip(xs0, ys0)])
        self.play(Flash(ray.get_end(), color=YELLOW, flash_radius=0.6), FadeOut(ray),
                  LaggedStart(*[FadeIn(d, scale=3) for d in dots], lag_ratio=0.002, run_time=1.4))
        self.remove(*dots)
        self.add(dots)   # the group itself must be in the scene for its updater to run
        top_spot = [col_x + 0.35, top_y + 0.4, 0]
        muon_word = label(f"{n} muons", 22, ORANGE).move_to(top_spot)
        self.play(FadeIn(muon_word), FadeIn(problem[0]), run_time=0.9)
        self.play(FadeIn(problem[1]), run_time=0.8)
        self.play(FadeIn(problem[2]), run_time=0.8)
        self.wait(4.5)

        T = ValueTracker(0.0)          # lab (Earth) time in microseconds
        clock_rate = ValueTracker(1.0)  # 1 = everyday guess, gamma = relativity

        def alive_count():
            proper = T.get_value() / clock_rate.get_value()
            return sum(1 for life in lives if life > proper)

        def fall(group):
            frac = min(T.get_value() / t_lab, 1.0)
            proper = T.get_value() / clock_rate.get_value()
            for d, x0, y0, life in zip(group, xs0, ys0, lives):
                d.move_to([x0, y0 - (y0 - ground_y - 0.08) * frac, 0])
                d.set_opacity(1.0 if life > proper else 0.0)

        counter = always_redraw(lambda: label(f"muons left: {alive_count()} of {n}", 22, ORANGE, 4.2).move_to(top_spot))

        # 2. The everyday guess: 50 microseconds is 33 half-lives.
        step1 = chip("1 · the everyday guess")
        self.play(FadeOut(title), FadeOut(problem), FadeIn(step1), run_time=0.7)
        e1 = eq(D["tex_t"], D["plain_t"], 36, WHITE, 9.4).move_to([1.8, 2.0, 0])
        e2 = eq(D["tex_ncl"], D["plain_ncl"], 36, WHITE, 9.4).move_to([1.8, 1.0, 0])
        e3 = eq(D["tex_fcl"], D["plain_fcl"], 36, RED_B, 9.4).move_to([1.8, -0.2, 0])
        self.play(Write(e1), run_time=1.6)
        self.wait(2.0)
        self.play(Write(e2), run_time=1.3)
        self.wait(1.5)
        self.play(Write(e3), run_time=1.3)
        self.wait(1.5)
        dots.add_updater(fall)
        self.remove(muon_word)
        self.add(counter)
        # slow motion at the start, where the decays happen
        self.play(T.animate.set_value(t_lab), run_time=7.0, rate_func=lambda a: a ** 2.5)
        guess = label(D["guess_result"], 28, RED, 9.4).move_to([1.8, -1.35, 0])
        paradox = label(D["paradox"], 26, YELLOW, 9.4).move_to([1.8, -2.1, 0])
        self.play(FadeIn(guess), run_time=0.8)
        self.play(FadeIn(paradox, shift=0.2 * UP), run_time=1.0)
        self.wait(3.5)

        # 3. Earth's story: the moving muon's clock runs slow.
        step2 = chip("2 · " + D["earth_title"])
        self.play(FadeOut(VGroup(e1, e2, e3, guess, paradox)), FadeOut(step1), FadeIn(step2), run_time=0.8)
        g1 = eq(D["tex_gamma"], D["plain_gamma"], 36, WHITE, 9.4).move_to([1.8, 2.05, 0])
        g2 = eq(D["tex_tau"], D["plain_tau"], 36, WHITE, 9.4).move_to([1.8, 1.15, 0])
        g3 = eq(D["tex_frel"], D["plain_frel"], 34, GREEN_B, 9.4).move_to([1.8, 0.0, 0])
        self.play(Write(g1), run_time=1.8)
        self.wait(2.5)
        self.play(Write(g2), run_time=1.5)
        self.wait(2.0)
        self.play(Write(g3), run_time=1.5)
        self.wait(2.0)

        def dial(center, color, name):
            face = Circle(radius=0.62, color=color, stroke_width=3).move_to(center)
            ticks = VGroup(*[Line(center + 0.52 * np.array([math.cos(a), math.sin(a), 0]),
                                  center + 0.62 * np.array([math.cos(a), math.sin(a), 0]),
                                  color=color, stroke_width=2) for a in np.linspace(0, TAU, 12, endpoint=False)])
            caption = label(name, 20, color).next_to(face, DOWN, buff=0.12)
            return VGroup(face, ticks, caption)

        lab_c, mu_c = np.array([-0.8, -1.9, 0]), np.array([2.2, -1.9, 0])
        lab_dial, mu_dial = dial(lab_c, BLUE_B, "Earth's clock"), dial(mu_c, ORANGE, "the muon's clock")
        # one turn of a hand = 10 microseconds on that clock
        lab_hand = always_redraw(lambda: Line(lab_c, lab_c + 0.5 * np.array(
            [math.sin(TAU * T.get_value() / 10), math.cos(TAU * T.get_value() / 10), 0]), color=BLUE_B, stroke_width=4))
        mu_hand = always_redraw(lambda: Line(mu_c, mu_c + 0.5 * np.array(
            [math.sin(TAU * T.get_value() / gamma / 10), math.cos(TAU * T.get_value() / gamma / 10), 0]),
            color=ORANGE, stroke_width=4))
        lab_read = always_redraw(lambda: label(f"{T.get_value():.1f}", 24, BLUE_B).next_to(lab_dial, RIGHT, buff=0.2))
        mu_read = always_redraw(lambda: label(f"{T.get_value() / gamma:.2f}", 24, ORANGE).next_to(mu_dial, RIGHT, buff=0.2))
        unit = eq(r"\text{(microseconds)}", "(microseconds)", 26, GREY_B, 5.0).move_to([0.7, -3.3, 0])
        slow = label(D["slow_note"], 24, ORANGE, 9.4).move_to([1.8, -0.95, 0])
        self.play(FadeOut(counter), run_time=0.3)
        T.set_value(0.0)
        clock_rate.set_value(gamma)
        self.add(counter)
        self.play(FadeIn(lab_dial), FadeIn(mu_dial), FadeIn(lab_hand), FadeIn(mu_hand), FadeIn(lab_read),
                  FadeIn(mu_read), FadeIn(unit), FadeIn(slow), run_time=1.0)
        self.play(T.animate.set_value(t_lab), run_time=9.0, rate_func=linear)
        dots.clear_updaters()
        arrived = label(f"{D['survivors']} of {n} reached the detector", 22, GREEN, 4.2).move_to(top_spot)
        self.play(FadeOut(counter), FadeIn(arrived), Indicate(detector, color=GREEN), run_time=1.0)
        self.wait(3.0)

        # 4. The muon's story: at rest, it sees a thin atmosphere rush past.
        step3 = chip("3 · " + D["muon_title"])
        for m in (lab_hand, mu_hand, lab_read, mu_read):
            m.clear_updaters()
        self.play(FadeOut(VGroup(g1, g2, g3, lab_dial, mu_dial, lab_hand, mu_hand, lab_read, mu_read, unit, slow)),
                  FadeOut(step2), FadeIn(step3), run_time=0.9)
        # true scale: the air Earth measures, and the air the muon measures
        rx, short_h = 2.9, span / gamma
        ghost = DashedVMobject(Rectangle(width=1.0, height=span), num_dashes=60).set_color(GREY_B)
        ghost.move_to([rx, top_y - span / 2, 0])
        slab = Rectangle(width=1.0, height=span, stroke_width=0, fill_color="#15325e", fill_opacity=1)
        slab.move_to(ghost)
        ghost_t = label("Earth: " + D["h_label"], 20, GREY_A).next_to(ghost, DOWN, buff=0.12)
        self.play(FadeIn(slab), Create(ghost), FadeIn(ghost_t), run_time=1.0)
        squashed = Rectangle(width=1.0, height=short_h, stroke_width=0, fill_color="#15325e", fill_opacity=1)
        squashed.move_to([rx, top_y - short_h / 2, 0])
        self.play(Transform(slab, squashed), run_time=2.2)
        short_text = label("muon: " + D["short_label"], 20, TEAL_A, 1.9).next_to(squashed, RIGHT, buff=0.12)
        self.play(FadeIn(short_text), run_time=0.6)
        l1 = eq(D["tex_len"], D["plain_len"], 34, WHITE, 5.6).move_to([-0.8, 1.3, 0])
        l2 = eq(D["tex_tmu"], D["plain_tmu"], 34, WHITE, 5.6).move_to([-0.8, 0.1, 0])
        self.play(Write(l1), run_time=1.5)
        self.wait(2.0)
        self.play(Write(l2), run_time=1.5)
        self.wait(1.5)
        # zoomed muon's view: the muon sits still while the thin air and the ground rise to meet it
        zx, z_top, z_bot = 5.75, 0.55, -2.55
        z_frame = Rectangle(width=2.3, height=z_top - z_bot + 0.5, color=GREY_B, stroke_width=2)
        z_frame.move_to([zx, (z_top + z_bot) / 2 + 0.1, 0])
        z_title = VGroup(label("the muon's view", 22, TEAL_A, 2.3), label("(zoomed in)", 20, TEAL_A, 2.3)).arrange(DOWN, buff=0.06).next_to(z_frame, UP, buff=0.12)
        U = ValueTracker(0.0)

        def gy():
            return z_bot + (z_top - z_bot) * U.get_value()

        z_air = always_redraw(lambda: Rectangle(width=2.0, height=max(z_top - gy(), 0.001), stroke_width=0,
                                                fill_color="#15325e", fill_opacity=1).move_to([zx, (z_top + gy()) / 2, 0]))
        z_ground = always_redraw(lambda: Line([zx - 1.05, gy(), 0], [zx + 1.05, gy(), 0], color=GREY_B, stroke_width=4))
        z_det = always_redraw(lambda: Rectangle(width=0.7, height=0.16, color=TEAL, fill_color=TEAL,
                                                fill_opacity=0.6).move_to([zx, gy() - 0.1, 0]))
        muon = Dot([zx, z_top, 0], radius=0.1, color=ORANGE).set_z_index(5)
        z_clock = always_redraw(lambda: VGroup(label("muon's clock", 20, ORANGE, 2.3),
                                               label(f"{D['tau_us'] * U.get_value():.2f} micro-s", 22, ORANGE, 2.3))
                                .arrange(DOWN, buff=0.05).next_to(z_frame, DOWN, buff=0.1))
        self.play(Create(z_frame), FadeIn(z_title), FadeIn(z_air), FadeIn(z_ground), FadeIn(z_det),
                  FadeIn(muon, scale=2), FadeIn(z_clock), run_time=1.0)
        self.play(U.animate.set_value(1.0), run_time=5.0, rate_func=linear)
        self.play(Flash(muon, color=GREEN), run_time=0.8)
        same = VGroup(label(D["same"], 26, GREEN, 5.6), label(D["same2"], 30, GREEN, 5.6)).arrange(DOWN, buff=0.15)
        same.move_to([-0.8, -1.4, 0])
        self.play(FadeIn(same, shift=0.2 * UP), run_time=1.0)
        self.wait(4.5)
        for m in (z_air, z_ground, z_det, z_clock):
            m.clear_updaters()
        muon_view = VGroup(z_frame, z_title, z_air, z_ground, z_det, z_clock, muon, ghost, slab, ghost_t, short_text)

        # 5. Check: count the simulated muons against the prediction.
        step4 = chip("4 · check it")
        self.play(FadeOut(VGroup(l1, l2, same, muon_view)), FadeOut(step3), FadeIn(step4), run_time=0.8)
        base_y, bar_w, per = -2.3, 1.2, 0.07
        bars = VGroup()
        for i, (name, value, color) in enumerate([(D["bar_guess"], 0.0, RED), (D["bar_rel"], float(D["bar_rel_n"]), GREEN),
                                                  (D["bar_sim"], float(D["survivors"]), TEAL)]):
            x = -1.2 + 2.6 * i
            bar = Rectangle(width=bar_w, height=max(value * per, 0.02), color=color, fill_color=color, fill_opacity=0.8)
            bar.move_to([x, base_y + bar.height / 2, 0])
            name_t = label(name, 22, color).next_to([x, base_y, 0], DOWN, buff=0.2)
            num_t = label([D["bar_guess_n"], D["bar_rel_n"], D["bar_sim_n"]][i], 26, color).next_to(bar, UP, buff=0.12)
            bars.add(VGroup(bar, name_t, num_t))
        axis = Line([-2.2, base_y, 0], [5.4, base_y, 0], color=GREY_B)
        self.play(Create(axis), run_time=0.5)
        self.play(LaggedStart(*[GrowFromEdge(b[0], DOWN) for b in bars], lag_ratio=0.4),
                  LaggedStart(*[FadeIn(b[1]) for b in bars], lag_ratio=0.4),
                  LaggedStart(*[FadeIn(b[2]) for b in bars], lag_ratio=0.4), run_time=2.5)
        check = VGroup(label(D["check"], 26, GREEN_B, 9.2), label(D["check2"], 26, GREEN_B, 9.2)).arrange(DOWN, buff=0.15)
        check.move_to([1.8, 2.1, 0])
        self.play(FadeIn(check), Indicate(dots, color=GREEN), run_time=1.2)
        self.wait(4.5)

        # 6. What if the muons were slower or faster?
        step5 = chip("5 · what if they were slower?")
        left_panel = VGroup(air, ground, detector, det_text, h_brace, h_text, dots, muon_word, arrived)
        self.play(FadeOut(VGroup(bars, axis, check)), FadeOut(left_panel), FadeOut(step4), FadeIn(step5), run_time=0.8)
        ax = Axes(x_range=[0.90, 1.0, 0.02], y_range=[-11, 0, 1], x_length=8.6, y_length=4.4,
                  axis_config={"color": GREY_B, "include_ticks": True}, tips=False).move_to([1.4, -0.75, 0])
        x_lab = label("speed as a fraction of c", 22, GREY_A).next_to(ax, DOWN, buff=0.5)
        marks = VGroup(*[label(t, 20, GREY_A).next_to(ax.c2p(0.9, v), LEFT, buff=0.12)
                         for t, v in (("1", 0), ("1/100 000", -5), ("1/10 billion", -10))])
        y_lab = label("fraction reaching the ground", 22, GREY_A).rotate(PI / 2).next_to(marks, LEFT, buff=0.2)
        bmarks = VGroup(*[label(f"{b:g}", 20, GREY_A).next_to(ax.c2p(b, -11), DOWN, buff=0.1) for b in (0.9, 0.95, 1.0)])
        rel = VMobject(color=GREEN, stroke_width=4).set_points_smoothly([ax.c2p(b, r) for b, r, _ in D["curve"]])
        cl = VMobject(color=RED, stroke_width=3).set_points_smoothly([ax.c2p(b, c) for b, _, c in D["curve"]])
        rel_t = label("relativity", 22, GREEN).next_to(ax.c2p(0.93, D["curve"][30][1]), UP, buff=0.35)
        cl_t = label("everyday guess", 22, RED).next_to(ax.c2p(0.93, D["curve"][30][2]), UP, buff=0.15)
        self.play(Create(ax), FadeIn(x_lab), FadeIn(y_lab), FadeIn(marks), FadeIn(bmarks), run_time=1.2)
        self.play(Create(cl), FadeIn(cl_t), run_time=1.5)
        self.play(Create(rel), FadeIn(rel_t), run_time=2.0)
        here = Dot(ax.c2p(D["beta"], D["log_rel"]), color=YELLOW, radius=0.09)
        here_t = label(f"our muons: {D['beta']:g} c", 22, YELLOW).next_to(here, LEFT, buff=0.2)
        self.play(FadeIn(here, scale=2), FadeIn(here_t), run_time=0.9)
        notes = VGroup(label(D["whatif_98"], 24, WHITE), label(D["whatif_999"], 24, WHITE),
                       label(D["whatif_note"], 22, GREY_A, 7.8)).arrange(DOWN, aligned_edge=LEFT, buff=0.15)
        notes.move_to([1.4, 2.4, 0])
        self.play(FadeIn(notes), run_time=1.0)
        self.wait(4.0)
        answer = VGroup(label(D["answer"], 32, YELLOW, 9.0), label(D["answer2"], 28, YELLOW, 9.0)).arrange(DOWN, buff=0.12)
        box = SurroundingRectangle(answer, color=YELLOW, buff=0.2, corner_radius=0.12)
        card = VGroup(answer, box).move_to([0.9, 2.35, 0])
        self.play(FadeOut(notes), FadeIn(card, scale=0.9), run_time=1.0)
        self.wait(5.0)
'''
