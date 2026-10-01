"""Problem video: what colour does a trapped electron glow?

"An electron is trapped in a box 1.0 nm wide. It drops from n = 3 to n = 2.
What colour is the light? How wide must the box be to glow green?"

Device: size decides colour. It opens on three glowing vials (same stuff,
different sizes) and asks why. Inside the box only whole half-waves fit, like a
guitar string; that one fact builds the energy ladder, E ∝ n²/L². The electron
drops a rung, a photon of that energy flies into a spectrum and lands on its
colour. The check solves Schrödinger's equation numerically on a grid and gets
the same ladder. The what-if squeezes the box and the colour slides to blue:
the vials explained.

Solving arc (subgoal labels): 1 only whole half-waves fit, 2 the energy
ladder, 3 the jump, 4 check, 5 what if.
"""

from __future__ import annotations

import math
from typing import Any

from aetherlab.services.scene_components.problems._kit import fill, pick, text_of, variables_of

H = 6.62607015e-34
ME = 9.1093837015e-31
EV = 1.602176634e-19
HC_EV_NM = 1239.84198
_STEMS = ("particle in a box", "quantum dot", "infinite well", "infinite square well", "infinite potential well",
          "electron in a box", "box of width", "electron trapped in a box", "particle in a 1d box")


def params(solver: Any) -> dict[str, float]:
    v = variables_of(solver)
    length = pick(v, ("l", "length", "width", "box_width", "box_length", "l_nm", "width_nm", "a", "d"))
    if length is not None and length < 1e-6:
        length *= 1e9                              # metres to nm
    n_i = pick(v, ("n_i", "ni", "n_initial", "n_upper", "upper", "n2", "n_start"))
    n_f = pick(v, ("n_f", "nf", "n_final", "n_lower", "lower", "n1", "n_end"))
    n_i = int(round(n_i)) if n_i else 3
    n_f = int(round(n_f)) if n_f else 2
    if not (1 <= n_f < n_i <= 6):
        n_i, n_f = 3, 2
    return {"L_nm": length if length and 0.2 <= length <= 20.0 else 1.0, "n_i": n_i, "n_f": n_f}


def matches(solver: Any) -> bool:
    text = text_of(solver)
    return any(s in text for s in _STEMS)


def e1_ev(l_nm: float) -> float:
    return H * H / (8.0 * ME * (l_nm * 1e-9) ** 2) / EV


def wavelength_nm(l_nm: float, n_i: int, n_f: int) -> float:
    return HC_EV_NM / ((n_i * n_i - n_f * n_f) * e1_ev(l_nm))


def colour_name(nm: float) -> str:
    for edge, name in ((380, "ultraviolet (invisible)"), (450, "violet"), (495, "blue"), (570, "green"),
                       (590, "yellow"), (620, "orange"), (750, "red")):
        if nm < edge:
            return name
    return "infrared (invisible)"


def _numeric(l_nm: float, levels: int) -> tuple[list[float], list[list[float]], list[float]]:
    """Finite-difference Schrödinger solve: energies (eV) and sampled ψ for the lowest levels."""
    import numpy as np
    from scipy.linalg import eigh_tridiagonal

    n = 1200
    dx = l_nm * 1e-9 / (n + 1)
    hbar = H / (2 * math.pi)
    diag = np.full(n, hbar * hbar / (ME * dx * dx))
    off = np.full(n - 1, -hbar * hbar / (2 * ME * dx * dx))
    w, vecs = eigh_tridiagonal(diag, off, select="i", select_range=(0, levels - 1))
    samples = []
    idx = np.linspace(0, n - 1, 41).astype(int)
    for k in range(levels):
        psi = vecs[:, k] / np.max(np.abs(vecs[:, k]))
        if psi[n // (2 * (k + 1))] < 0:            # same sign convention as sin(kπx/L)
            psi = -psi
        samples.append([round(float(psi[i]), 4) for i in idx])
    xs = [round((int(i) + 1) / (n + 1), 5) for i in idx]   # grid point i sits at x = (i + 1) dx
    return [float(x) / EV for x in w], samples, xs


def _solve(p: dict[str, Any]) -> dict[str, Any]:
    l_nm, n_i, n_f = p["L_nm"], p["n_i"], p["n_f"]
    e1 = e1_ev(l_nm)
    lam = wavelength_nm(l_nm, n_i, n_f)
    numeric, samples, xs = _numeric(l_nm, n_i)
    lam_num = HC_EV_NM / (numeric[n_i - 1] - numeric[n_f - 1])
    what_if = []
    for target in (530.0, 455.0):
        l_new = round(l_nm * math.sqrt(target / lam), 3)
        lam_new = wavelength_nm(l_new, n_i, n_f)
        what_if.append((l_new, lam_new))
    return {"e1": e1, "lam": lam, "numeric": numeric, "samples": samples, "sample_x": xs, "lam_num": lam_num,
            "what_if": what_if}


def build(class_name: str, solver: Any) -> str | None:
    p = params(solver)
    s = _solve(p)
    l_nm, n_i, n_f = p["L_nm"], p["n_i"], p["n_f"]
    if abs(s["numeric"][0] - s["e1"]) > 0.002 * s["e1"] or abs(s["lam_num"] - s["lam"]) > 0.005 * s["lam"]:
        return None
    e1, lam = s["e1"], s["lam"]
    e1_j = e1 * EV
    k = n_i * n_i - n_f * n_f
    de = k * e1
    (lg, lam_g), (lb, lam_b) = s["what_if"]
    levels = [n * n * e1 for n in range(1, n_i + 1)]
    data = {
        "L": l_nm, "n_i": n_i, "n_f": n_f, "e1": e1, "lam": round(lam, 2), "levels": [round(x, 4) for x in levels],
        "samples": s["samples"], "sample_x": s["sample_x"], "what_if": [[lg, round(lam_g, 2)], [lb, round(lam_b, 2)]],
        "problem": f"An electron is trapped in a box {l_nm:g} nm wide.",
        "problem2": f"It drops from level n = {n_i} to level n = {n_f}.",
        "question": "What colour is the light it gives off?",
        "hook": "Same material, different sizes. Why different colours?",
        "tex_lam_n": r"\lambda_n=\frac{2L}{n}", "plain_lam_n": "λ = 2L / n",
        "tex_p": r"p=\frac{h}{\lambda_n}=\frac{nh}{2L}", "plain_p": "p = h / λ = n h / 2L",
        "tex_e": r"E_n=\frac{p^2}{2m}=\frac{n^2h^2}{8mL^2}", "plain_e": "E = p² / 2m = n² h² / 8 m L²",
        "tex_e1": rf"E_1=\frac{{(6.63\times10^{{-34}})^2}}{{8\,(9.11\times10^{{-31}})\,({l_nm:g}\times10^{{-9}})^2}}"
                  rf"={e1_j * 1e20:.2f}\times10^{{-20}}\,\text{{J}}={e1:.3f}\,\text{{eV}}",
        "plain_e1": f"E1 = h² / 8 m L² = {e1_j * 1e20:.2f} × 10^-20 J = {e1:.3f} eV",
        "fit_note": "Only whole half-waves fit between the walls, like a guitar string",
        "tex_ladder": r"E_n=n^2E_1", "plain_ladder": "E = n² × E1",
        "tex_de": rf"\Delta E=E_{n_i}-E_{n_f}=({n_i}^2-{n_f}^2)\,E_1={k}\times{e1:.3f}\,\text{{eV}}={de:.2f}\,\text{{eV}}",
        "plain_de": f"ΔE = ({n_i}² - {n_f}²) × E1 = {k} × {e1:.3f} = {de:.2f} eV",
        "tex_lam": rf"\lambda=\frac{{hc}}{{\Delta E}}=\frac{{1240\,\text{{eV nm}}}}{{{de:.2f}\,\text{{eV}}}}={lam:.0f}\,\text{{nm}}",
        "plain_lam": f"λ = hc / ΔE = 1240 eV·nm / {de:.2f} eV = {lam:.0f} nm",
        "colour": f"{lam:.0f} nm: {colour_name(lam)} light",
        "tex_schr": r"-\frac{\hbar^2}{2m}\,\frac{d^2\psi}{dx^2}=E\,\psi,\qquad \psi(0)=\psi(L)=0",
        "plain_schr": "-ħ²/2m · ψ'' = E ψ,  ψ(0) = ψ(L) = 0",
        "check_head": "Schrödinger's equation solved numerically on a 1200-point grid:",
        "tex_num": r"\text{grid:}\;\;E_1,E_2,E_3=" + ",\\;".join(f"{x:.4f}" for x in s["numeric"][:3]) + r"\;\text{eV}",
        "plain_num": "grid:  E1, E2, E3 = " + ", ".join(f"{x:.4f}" for x in s["numeric"][:3]) + " eV",
        "tex_formula": r"\text{formula:}\;\;n^2E_1=" + ",\\;".join(f"{x:.4f}" for x in levels[:3]) + r"\;\text{eV}",
        "plain_formula": "formula:  n² E1 = " + ", ".join(f"{x:.4f}" for x in levels[:3]) + " eV",
        "check_lam": f"grid wavelength: {s['lam_num']:.1f} nm  (formula: {lam:.1f} nm)",
        "dots_note": "dots: the numerical wave; lines: the sine formula",
        "tex_scale": r"\lambda=\frac{hc}{\Delta E}=\frac{8mc\,L^2}{(n_i^2-n_f^2)\,h}\;\propto\;L^2",
        "plain_scale": "λ = 8 m c L² / ((ni² - nf²) h)  ∝  L²",
        "shrink": "A smaller box pushes the rungs apart: bigger jumps, bluer light",
        "vial_labels": [f"{l_nm:g} nm", f"{lg:g} nm", f"{lb:g} nm"],
        "vial_colours": [f"{lam:.0f} nm", f"{lam_g:.0f} nm", f"{lam_b:.0f} nm"],
        "answer": f"Answer: {lam:.0f} nm, {colour_name(lam)} light.",
        "answer2": f"A {lg:g} nm box glows green ({lam_g:.0f} nm).",
    }
    return fill(_TEMPLATE, class_name, data)


def check_lines(solver: Any) -> list[str]:
    p = params(solver)
    s = _solve(p)
    return [f"Schrödinger's equation solved numerically for an electron in a {p['L_nm']:g} nm box (1200-point grid): "
            f"E1 = {s['numeric'][0]:.4f} eV (formula {s['e1']:.4f} eV); the n = {p['n_i']} → {p['n_f']} photon is "
            f"{s['lam_num']:.1f} nm ({colour_name(s['lam_num'])})."]


_TEMPLATE = r'''"""Generated by AetherLab - problem: what colour does the trapped electron glow?"""

import math

import numpy as np
from manim import *

__HELPERS__


def wl_hex(nm):
    # visible-light colour of a wavelength (approximate), grey outside 380-750 nm
    if nm < 380 or nm > 750:
        return "#9a9a9a"
    if nm < 440:
        r, g, b = (440 - nm) / 60, 0.0, 1.0
    elif nm < 490:
        r, g, b = 0.0, (nm - 440) / 50, 1.0
    elif nm < 510:
        r, g, b = 0.0, 1.0, (510 - nm) / 20
    elif nm < 580:
        r, g, b = (nm - 510) / 70, 1.0, 0.0
    elif nm < 645:
        r, g, b = 1.0, (645 - nm) / 65, 0.0
    else:
        r, g, b = 1.0, 0.0, 0.0
    return "#%02x%02x%02x" % tuple(int(255 * max(0.0, min(1.0, c))) for c in (r, g, b))


class __CLASS__(Scene):
    def construct(self):
        D = __DATA__
        n_i, n_f, lam, L0 = D["n_i"], D["n_f"], D["lam"], D["L"]
        levels = D["levels"]
        wall_l, wall_r, floor_y, top_y = -5.2, -2.3, -3.3, 2.75
        room = top_y - 0.45 - floor_y
        amp = 0.3

        def diagram(width_nm, e_scale):
            # the box, its standing waves on their rungs, and the rung energies, for one box width
            right = wall_l + (wall_r - wall_l) * width_nm / L0
            lv = [e * (L0 / width_nm) ** 2 for e in levels]
            walls = VGroup(Line([wall_l, floor_y, 0], [wall_l, top_y, 0], color=GREY_A, stroke_width=6),
                           Line([right, floor_y, 0], [right, top_y, 0], color=GREY_A, stroke_width=6),
                           Line([wall_l, floor_y, 0], [right, floor_y, 0], color=GREY_D, stroke_width=2))
            waves, tags, rungs, e_tags = VGroup(), VGroup(), VGroup(), VGroup()
            for n in range(1, n_i + 1):
                y = floor_y + e_scale * lv[n - 1]
                waves.add(FunctionGraph(
                    lambda x, n=n, y=y: y + amp * math.sin(n * PI * (x - wall_l) / (right - wall_l)),
                    x_range=[wall_l, right, (right - wall_l) / 150], color=BLUE_B, stroke_width=3))
                tags.add(label(f"n = {n}", 22, BLUE_B).next_to([right, y, 0], RIGHT, buff=0.15))
                rungs.add(DashedLine([wall_l, y, 0], [right, y, 0], color=GREY_B, stroke_width=2, dash_length=0.12))
                e_tags.add(label(f"{lv[n - 1]:.2f} eV", 22, GREY_A).next_to([wall_l, y, 0], LEFT, buff=0.12))
            width_t = label(f"L = {width_nm:g} nm", 24, GREY_A).next_to(walls[2], DOWN, buff=0.12)
            return {"walls": walls, "waves": waves, "tags": tags, "rungs": rungs, "e_tags": e_tags,
                    "width": width_t, "lv": lv, "right": right}

        base = diagram(L0, room / levels[-1])

        def ey(n):
            return floor_y + room / levels[-1] * levels[n - 1]

        # 1. Picture it: three glowing vials, and one electron in a box.
        title = label("What colour does the trapped electron glow?", 38, YELLOW).to_edge(UP, buff=0.3)
        vials = VGroup()
        for i, nm in enumerate([lam, D["what_if"][0][1], D["what_if"][1][1]]):
            glass = RoundedRectangle(width=0.9, height=1.8, corner_radius=0.25, color=GREY_B, stroke_width=3)
            glow = RoundedRectangle(width=0.8, height=1.3, corner_radius=0.2, stroke_width=0,
                                    fill_color=wl_hex(nm), fill_opacity=0.85).align_to(glass, DOWN).shift(UP * 0.05)
            vials.add(VGroup(glow, glass).move_to([-1.6 + 1.6 * i, 0.4, 0]))
        hook = label(D["hook"], 28, WHITE).next_to(vials, DOWN, buff=0.4)
        self.play(Write(title), run_time=1.2)
        self.play(LaggedStart(*[FadeIn(v, shift=0.3 * UP) for v in vials], lag_ratio=0.3), run_time=1.6)
        self.play(FadeIn(hook), run_time=0.8)
        self.wait(3.0)
        walls, width_t = base["walls"], base["width"]
        problem = VGroup(label(D["problem"], 28, WHITE, 7.4), label(D["problem2"], 28, WHITE, 7.4),
                         label(D["question"], 30, TEAL_A, 7.4))
        problem.arrange(DOWN, buff=0.22, aligned_edge=LEFT).move_to([2.9, 0.8, 0])
        self.play(FadeOut(vials), FadeOut(hook), FadeOut(title), Create(walls), FadeIn(width_t), run_time=1.2)
        self.play(FadeIn(problem[0]), run_time=0.8)
        self.play(FadeIn(problem[1]), run_time=0.8)
        self.play(FadeIn(problem[2]), run_time=0.8)
        self.wait(4.0)

        # 2. Only whole half-waves fit between the walls.
        step1 = chip("1 · only whole half-waves fit")
        self.play(FadeOut(problem), FadeIn(step1), run_time=0.7)
        note = label(D["fit_note"], 24, BLUE_B, 7.6).move_to([2.9, 2.75, 0])
        self.play(FadeIn(note), run_time=0.8)
        waves, tags = base["waves"], base["tags"]
        derivation = [eq(D["tex_lam_n"], D["plain_lam_n"], 38, WHITE, 7.6), eq(D["tex_p"], D["plain_p"], 38, WHITE, 7.6),
                      eq(D["tex_e"], D["plain_e"], 38, WHITE, 7.6)]
        for i, m in enumerate(derivation):
            m.move_to([2.9, 1.6 - 1.15 * i, 0])
        for i in range(min(3, n_i)):
            self.play(Create(waves[i]), FadeIn(tags[i]), run_time=1.3)
            self.play(Write(derivation[i]), run_time=1.4)
            self.wait(1.8)
        for i in range(3, n_i):
            self.play(Create(waves[i]), FadeIn(tags[i]), run_time=0.9)
        e1_line = eq(D["tex_e1"], D["plain_e1"], 30, YELLOW, 7.8).move_to([2.9, -2.2, 0])
        self.play(Write(e1_line), run_time=2.0)
        self.wait(4.0)

        # 3. The energy ladder: each wave sits on its own rung, E = n² E1.
        step2 = chip("2 · the energy ladder")
        self.play(FadeOut(VGroup(*derivation, note)), FadeOut(step1), FadeIn(step2),
                  e1_line.animate.scale(0.85).move_to([2.9, 2.7, 0]), run_time=0.9)
        rungs, e_tags = base["rungs"], base["e_tags"]
        ladder_eq = eq(D["tex_ladder"], D["plain_ladder"], 40, WHITE).move_to([2.9, 1.5, 0])
        self.play(LaggedStart(*[Create(r) for r in rungs], lag_ratio=0.2), FadeIn(e_tags), Write(ladder_eq), run_time=1.8)
        gaps = label("the rungs spread apart: 1, 4, 9, ...", 24, GREY_A).next_to(ladder_eq, DOWN, buff=0.3)
        self.play(FadeIn(gaps), run_time=0.8)
        self.wait(3.5)

        # 4. The jump: the electron drops a rung and the energy leaves as one photon.
        step3 = chip("3 · the jump")
        electron = Dot([wall_r - 0.35, ey(n_i), 0], radius=0.12, color=YELLOW).set_z_index(5)
        self.play(FadeOut(gaps), FadeOut(ladder_eq), FadeOut(step2), FadeIn(step3), FadeIn(electron, scale=2), run_time=0.9)
        de = eq(D["tex_de"], D["plain_de"], 32, WHITE, 7.8).move_to([2.9, 1.6, 0])
        lam_eq = eq(D["tex_lam"], D["plain_lam"], 34, WHITE, 7.8).move_to([2.9, 0.45, 0])
        self.play(Write(de), run_time=1.8)
        self.wait(2.0)
        self.play(Write(lam_eq), run_time=1.6)
        self.wait(1.5)
        # the spectrum the photon lands in
        s_left, s_right, s_y = -0.4, 6.6, -2.7

        def sx(nm):
            return s_left + (s_right - s_left) * (min(max(nm, 380), 780) - 380) / 400

        strip = VGroup(*[Rectangle(width=(s_right - s_left) / 80 + 0.01, height=0.45, stroke_width=0,
                                   fill_color=wl_hex(380 + 5 * i + 2.5), fill_opacity=1).move_to([sx(380 + 5 * i + 2.5), s_y, 0])
                         for i in range(80)])
        s_marks = VGroup(*[label(f"{nm} nm", 18, GREY_A).next_to([sx(nm), s_y - 0.23, 0], DOWN, buff=0.08)
                           for nm in (400, 500, 600, 700)])
        self.play(FadeIn(strip), FadeIn(s_marks), run_time=0.9)
        packet = FunctionGraph(lambda x: 0.16 * math.sin(9 * x) * math.exp(-x * x * 3), x_range=[-1.2, 1.2, 0.02],
                               color=wl_hex(lam), stroke_width=4).move_to(electron.get_center() + RIGHT * 1.0)
        self.play(electron.animate.move_to([wall_r - 0.35, ey(n_f), 0]), FadeIn(packet), run_time=1.0)
        self.play(packet.animate.move_to([sx(lam), s_y + 0.8, 0]), run_time=2.2, rate_func=smooth)
        pin = Triangle(color=WHITE, fill_opacity=1).scale(0.12).rotate(PI).move_to([sx(lam), s_y + 0.35, 0])
        colour = label(D["colour"], 28, wl_hex(lam)).next_to(pin, UP, buff=0.3)
        self.play(FadeOut(packet), FadeIn(pin, shift=0.2 * DOWN), FadeIn(colour), run_time=0.9)
        self.wait(4.0)

        # 5. Check: solve Schrödinger's equation on a grid; the same ladder comes out.
        step4 = chip("4 · check: solve Schrödinger's equation numerically")
        self.play(FadeOut(VGroup(de, lam_eq, e1_line)), FadeOut(step3), FadeIn(step4), run_time=0.8)
        schr = eq(D["tex_schr"], D["plain_schr"], 32, WHITE, 7.8).move_to([2.9, 2.6, 0])
        head = label(D["check_head"], 22, GREY_A, 7.8).move_to([2.9, 1.8, 0])
        self.play(Write(schr), run_time=1.6)
        self.play(FadeIn(head), run_time=0.7)
        pts = VGroup()
        for n in range(1, n_i + 1):
            for fx, v in zip(D["sample_x"], D["samples"][n - 1]):
                pts.add(Dot([wall_l + (wall_r - wall_l) * fx, ey(n) + amp * v, 0], radius=0.045, color=ORANGE))
        self.play(LaggedStart(*[FadeIn(d, scale=2) for d in pts], lag_ratio=0.01), run_time=2.0)
        nums = VGroup(eq(D["tex_num"], D["plain_num"], 32, GREEN_B, 7.8),
                      eq(D["tex_formula"], D["plain_formula"], 32, WHITE, 7.8)).arrange(DOWN, buff=0.18)
        nums.move_to([2.9, 0.95, 0])
        lam_chk = label(D["check_lam"], 24, GREEN_B, 7.8).move_to([2.9, 0.0, 0])
        dots_note = label(D["dots_note"], 20, ORANGE, 7.8).move_to([2.9, -0.55, 0])
        self.play(FadeIn(nums), run_time=1.0)
        self.play(FadeIn(lam_chk), FadeIn(dots_note), run_time=0.9)
        self.wait(4.5)

        # 6. What if the box is smaller? The rungs spread and the light turns blue.
        step5 = chip("5 · what if the box is smaller?")
        self.play(FadeOut(VGroup(schr, head, nums, lam_chk, dots_note, pts, colour, electron)), FadeOut(step4),
                  FadeIn(step5), run_time=0.8)
        scale_eq = eq(D["tex_scale"], D["plain_scale"], 32, WHITE, 7.8).move_to([2.9, 2.6, 0])
        shrink = label(D["shrink"], 24, GREY_A, 7.8).move_to([2.9, 1.85, 0])
        self.play(Write(scale_eq), run_time=1.8)
        self.play(FadeIn(shrink), run_time=0.8)
        # one energy scale that fits the smallest box, so the rungs can visibly spread
        smallest = D["what_if"][-1][0]
        fit_scale = room / (levels[-1] * (L0 / smallest) ** 2)
        parts = ("walls", "waves", "tags", "rungs", "e_tags", "width")
        shown = VGroup(*[base[k] for k in parts])
        rescaled = diagram(L0, fit_scale)
        self.play(Transform(shown, VGroup(*[rescaled[k] for k in parts])), run_time=1.5)
        pin_t = label(f"{lam:.0f} nm", 22, wl_hex(lam)).next_to(pin, UP, buff=0.12)
        self.play(FadeIn(pin_t), run_time=0.5)
        for (l_new, lam_new) in D["what_if"]:
            smaller = diagram(l_new, fit_scale)
            self.play(Transform(shown, VGroup(*[smaller[k] for k in parts])),
                      pin.animate.move_to([sx(lam_new), s_y + 0.35, 0]),
                      Transform(pin_t, label(f"{lam_new:.0f} nm", 22, wl_hex(lam_new)).next_to(
                          [sx(lam_new), s_y + 0.35, 0], UP, buff=0.2)), run_time=2.2)
            self.wait(1.6)
        vials = VGroup()
        for i, (name, nm_text, nm) in enumerate(zip(D["vial_labels"], D["vial_colours"],
                                                   [lam, D["what_if"][0][1], D["what_if"][1][1]])):
            glass = RoundedRectangle(width=0.8, height=1.5, corner_radius=0.22, color=GREY_B, stroke_width=3)
            glow = RoundedRectangle(width=0.7, height=1.1, corner_radius=0.18, stroke_width=0,
                                    fill_color=wl_hex(nm), fill_opacity=0.85).align_to(glass, DOWN).shift(UP * 0.05)
            cap = VGroup(label(name, 20, GREY_A), label(nm_text, 20, wl_hex(nm))).arrange(DOWN, buff=0.05)
            vials.add(VGroup(glow, glass, cap.next_to(glass, DOWN, buff=0.1)).move_to([1.2 + 1.8 * i, -0.2, 0]))
        self.play(LaggedStart(*[FadeIn(v, shift=0.2 * UP) for v in vials], lag_ratio=0.3), run_time=1.6)
        self.wait(2.0)
        answer = VGroup(label(D["answer"], 30, YELLOW, 7.4), label(D["answer2"], 28, YELLOW, 7.4)).arrange(DOWN, buff=0.12)
        box = SurroundingRectangle(answer, color=YELLOW, buff=0.2, corner_radius=0.12)
        card = VGroup(answer, box).move_to([2.9, 2.3, 0])
        self.play(FadeOut(scale_eq), FadeOut(shrink), FadeIn(card, scale=0.9), run_time=1.0)
        self.wait(5.0)
'''
