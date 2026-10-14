"""AetherLab lesson scenes: uniformly accelerated rectilinear motion (STAGE L).

GENERATED FILE — do not edit by hand. Source: .qwen/tmp/lesson_template.py,
data baked by .qwen/tmp/gen_scenes.py from canonical.json (Stage F v2).
Language of on-screen captions: EN. No LaTeX anywhere (unicode Text only).

Blocks (budgets 20/50/40/50/40/30/30/40 = 300 s):
  BlockB0 hook, BlockB1 concept, BlockB2 velocity, BlockB3 displacement,
  BlockB4 graph, BlockB5 area check, BlockB6 pause task, BlockB7 traps+recap.
"""

from manim import *

# == GEN:DATA BEGIN ==
DATA = {"v0": 2, "a": 3, "t": 4, "v": 14, "s": 32, "b6": {"v0": 0, "a": 2, "t": 5, "s": 25}}
UNITS = {"vel": "m/s", "acc": "m/s²", "dist": "m", "time": "s"}
FORMULAS = {
        "F-accel-def": "a = Δv / Δt",
        "F-vel": "v = v₀ + at",
        "F-disp": "s = v₀ t + at²/2",
        "F-avg": "s = (v₀ + v)t/2"
}
CAPTIONS = {
        "B0": [
                "How far did the car go?",
                "Two ways to the answer"
        ],
        "B1": [
                "v = s / t — uniform",
                "a = Δv / Δt",
                "[a] = m/s²",
                "x axis →"
        ],
        "B2": [
                "v = v₀ + at",
                "2 + 3·4 = 14 m/s"
        ],
        "B3": [
                "s = v₀t + at²/2",
                "8 + 24 = 32 m",
                "direction unchanged"
        ],
        "B4": [
                "v = 2 + 3t",
                "slope = a"
        ],
        "B5": [
                "S = (2+14)/2 · 4 = 32 m",
                "area = displacement ✓"
        ],
        "B6": [
                "v₀ = 0, a = 2, t = 5, s = ?",
                "Pause!",
                "s = 25 m"
        ],
        "B7": [
                "✗ 14·4 = 56",
                "slope = a; area = s",
                "v = v₀ + at; s = v₀t + at²/2"
        ]
}
# == GEN:DATA END ==

V0, A, T_END = DATA["v0"], DATA["a"], DATA["t"]
V_END, S_END = DATA["v"], DATA["s"]
B6 = DATA["b6"]


def x_of(t: float) -> float:
    return V0 * t + 0.5 * A * t * t


def v_of(t: float) -> float:
    return V0 + A * t


C_V, C_A, C_S, C_T = BLUE, RED, GREEN, GRAY_B
C_AXIS, C_CAR, C_ROAD = GRAY, YELLOW, GRAY_D

ROAD_Y = -2.6
ROAD_X0, ROAD_X1 = -5.6, 5.6


def road_point(x_phys: float):
    frac = min(max(x_phys / S_END, 0.0), 1.0)
    return [ROAD_X0 + frac * (ROAD_X1 - ROAD_X0), ROAD_Y, 0]


def make_car():
    body = Rectangle(width=1.6, height=0.5, fill_color=C_CAR, fill_opacity=0.9,
                     stroke_color=YELLOW_E, stroke_width=2)
    top = Rectangle(width=0.8, height=0.35, fill_color=C_CAR, fill_opacity=0.9,
                    stroke_color=YELLOW_E, stroke_width=2)
    top.next_to(body, UP, buff=0).shift(LEFT * 0.15)
    w1 = Circle(radius=0.18, fill_color=GRAY_D, fill_opacity=1,
                stroke_width=1).move_to(body.get_bottom() + LEFT * 0.5 + DOWN * 0.02)
    w2 = Circle(radius=0.18, fill_color=GRAY_D, fill_opacity=1,
                stroke_width=1).move_to(body.get_bottom() + RIGHT * 0.5 + DOWN * 0.02)
    return VGroup(body, top, w1, w2)


def make_road():
    y = ROAD_Y - 0.5
    line = Line([ROAD_X0 - 0.4, y, 0], [ROAD_X1 + 0.4, y, 0],
                color=C_ROAD, stroke_width=6)
    tick0 = Line([ROAD_X0, y, 0], [ROAD_X0, y + 0.25, 0], color=GRAY, stroke_width=3)
    tick1 = Line([ROAD_X1, y, 0], [ROAD_X1, y + 0.25, 0], color=GRAY, stroke_width=3)
    return VGroup(line, tick0, tick1)


CAP_Y0, CAP_DY = 3.45, 0.52


def cap_text(block: str, idx: int, font_size: int = 28):
    return Text(CAPTIONS[block][idx], font_size=font_size).move_to(
        [0, CAP_Y0 - idx * CAP_DY, 0])


def split_cap(full_text: str, font_size: int, pos, tail_color=WHITE):
    """Split a 'stem = tail' caption into two adjacent Texts centered at pos.

    Staged numeric reveals (L2 sync): the stem appears with the setup while
    the tail (the spoken number) pops exactly when it is named. The group
    as a whole is centered at pos, matching cap_text placement.
    Returns (stem, tail).
    """
    stem_text, tail_text = full_text.rsplit("=", 1)
    stem = Text(stem_text + "=", font_size=font_size)
    tail = Text(tail_text.strip(), font_size=font_size, color=tail_color)
    tail.next_to(stem, RIGHT, buff=0.18)
    VGroup(stem, tail).move_to(pos)
    return stem, tail


GAUGE_C = [0, -0.9, 0]
GAUGE_R = 1.5
V_MAX = 16


def make_gauge():
    arc = Arc(radius=GAUGE_R, start_angle=0, angle=PI, color=GRAY,
              stroke_width=6).move_to(GAUGE_C)
    ticks = []
    for v in (0, 4, 8, 12, 16):
        ang = PI * (1 - v / V_MAX)
        direction = np.array([np.cos(ang), np.sin(ang), 0])
        p1 = np.array(GAUGE_C) + direction * (GAUGE_R - 0.2)
        p2 = np.array(GAUGE_C) + direction * GAUGE_R
        ticks.append(Line(p1, p2, color=GRAY, stroke_width=4))
    return VGroup(arc, *ticks)


def make_needle(v: float):
    ang = PI * (1 - v / V_MAX)
    tip = np.array(GAUGE_C) + 1.15 * np.array([np.cos(ang), np.sin(ang), 0])
    return Line(GAUGE_C, tip, color=C_A, stroke_width=6)


def make_readout(value: float):
    num = DecimalNumber(value, num_decimal_places=0, font_size=40,
                        color=C_V).move_to(np.array(GAUGE_C) + DOWN * 1.0)
    unit = Text(UNITS["vel"], font_size=30, color=C_V).next_to(num, RIGHT, buff=0.15)
    return num, unit


def make_vt_axes(x_length=5.6, y_length=3.0, center=[-2.2, -0.9, 0]):
    return Axes(x_range=[0, 5, 1], y_range=[0, 16, 2],
                x_length=x_length, y_length=y_length,
                axis_config={"include_tip": True, "color": C_AXIS}).move_to(center)


def axis_labels(ax):
    xl = Text(f"t, {UNITS['time']}", font_size=24, color=C_T).next_to(
        ax.x_axis.get_end(), DOWN, buff=0.15)
    yl = Text(f"v, {UNITS['vel']}", font_size=24, color=C_V).next_to(
        ax.y_axis.get_end(), RIGHT, buff=0.15)
    return VGroup(xl, yl)


class BlockB0(Scene):
    """Hook and goal, 20 s: j0a 6 + j0b 8 + j0c 6."""

    def construct(self):
        road, car = make_road(), make_car().move_to(road_point(0))
        cap0 = cap_text("B0", 0)
        num, unit = make_readout(V0)
        readout = VGroup(num, unit).move_to([4.6, 2.1, 0]).scale(0.8)
        # j0a (6): road + car + question. Speech f1 at 0.3 ("...two...").
        self.play(FadeIn(road), FadeIn(car), FadeIn(cap0), FadeIn(readout),
                  run_time=1.5)
        self.wait(4.5)
        # j0b (8): compressed journey T 0->4; speedo climbs 2->14.
        # Speech f1 placed late (E1 10.5-10.7): "fourteen" lands ~12.5-13.4
        # as the car arrives at 12.7.
        T = ValueTracker(0.0)
        car.add_updater(lambda m: m.move_to(road_point(x_of(T.get_value()))))
        num.add_updater(lambda m: m.set_value(v_of(T.get_value())))
        self.play(T.animate.set_value(T_END), run_time=6.7, rate_func=linear)
        car.clear_updaters()
        num.clear_updaters()
        num.set_value(V_END)
        car.move_to(road_point(S_END))
        self.wait(1.3)
        # j0c (6): freeze + goal card. cap1 at E2=16.3 (f2 "answer two ways"),
        # not at the shot head (f1 asks the question).
        cap1 = cap_text("B0", 1)
        self.wait(2.3)
        self.play(FadeIn(cap1), run_time=2)
        self.wait(1.7)


class BlockB1(Scene):
    """What 'uniformly accelerated' means, 50 s: 10+14+12+14."""

    def construct(self):
        # j1a (10): uniform-motion contrast, steady speedo + equal ticks.
        cap0 = cap_text("B1", 0)
        gauge = make_gauge()
        needle = make_needle(4)
        num, unit = make_readout(4)
        ticks = VGroup(*[
            Line([-3.0 + i * 1.2, ROAD_Y - 0.5, 0], [-3.0 + i * 1.2, ROAD_Y - 0.1, 0],
                 color=C_V, stroke_width=5)
            for i in range(4)])
        # Ticks illustrate "uniform" (~2.5-3.6); cap0 with its recitation.
        self.play(FadeIn(gauge), FadeIn(needle), FadeIn(num),
                  FadeIn(unit), run_time=2)
        for tick in ticks[:3]:
            self.play(FadeIn(tick), run_time=0.8)
        self.play(FadeIn(ticks[3]), FadeIn(cap0), run_time=1.5)
        self.wait(4.1)
        # j1b (14): close-up, four equal +3 needle jumps at fragment heads
        # E=(10.3, 14.3, 20.5): jump1 with f1, jumps 2-3 with f2 ("plus 3"),
        # jump4 with f3.
        T = ValueTracker(0.0)
        dyn_needle = always_redraw(lambda: make_needle(v_of(T.get_value())))
        num.add_updater(lambda m: m.set_value(v_of(T.get_value())))
        self.add(dyn_needle)
        self.remove(needle)
        num.set_value(V0)
        self.wait(0.3)
        plus_labels = []
        lab_pos = [[-2.7 + i * 1.8, -2.9, 0] for i in range(4)]
        self.play(T.animate.set_value(1), run_time=2, rate_func=linear)
        plus_labels.append(
            Text("+3", font_size=30, color=C_A).move_to(lab_pos[0]))
        self.play(FadeIn(plus_labels[0]), run_time=0.5)
        self.wait(1.5)
        self.play(T.animate.set_value(2), run_time=2, rate_func=linear)
        plus_labels.append(
            Text("+3", font_size=30, color=C_A).move_to(lab_pos[1]))
        self.play(FadeIn(plus_labels[1]), run_time=0.5)
        self.wait(0.5)
        self.play(T.animate.set_value(3), run_time=2, rate_func=linear)
        plus_labels.append(
            Text("+3", font_size=30, color=C_A).move_to(lab_pos[2]))
        self.play(FadeIn(plus_labels[2]), run_time=0.5)
        self.wait(0.7)
        self.play(T.animate.set_value(4), run_time=2, rate_func=linear)
        plus_labels.append(
            Text("+3", font_size=30, color=C_A).move_to(lab_pos[3]))
        self.play(FadeIn(plus_labels[3]), run_time=0.5)
        self.wait(1.0)
        num.clear_updaters()
        num.set_value(V_END)
        self.remove(dyn_needle)
        needle = make_needle(V_END)
        self.add(needle)
        # j1c (12): a-vector + definition + unit.
        cap1 = cap_text("B1", 1)
        cap2 = cap_text("B1", 2)
        self.play(FadeOut(VGroup(gauge, needle, num, unit, ticks, *plus_labels)),
                  run_time=1.5)
        avec = Arrow([-2.5, -0.9, 0], [0.5, -0.9, 0], color=C_A,
                     stroke_width=8, buff=0)
        alabel = Text("a", font_size=44, color=C_A).next_to(avec, UP, buff=0.2)
        self.play(Create(avec), FadeIn(alabel), run_time=2)
        self.play(FadeIn(cap1), run_time=2)
        self.wait(1.9)
        self.play(FadeIn(cap2), run_time=2)
        self.wait(2.6)
        # j1d (14): Ox axis + sign rule + recap.
        cap3 = cap_text("B1", 3)
        axis = Arrow([-5.5, -2.2, 0], [5.5, -2.2, 0], color=C_AXIS,
                     stroke_width=5, buff=0)
        ox = Text("Ox", font_size=36, color=C_AXIS).next_to(axis.get_end(),
                                                            DOWN, buff=0.2)
        plus = Text("+", font_size=44, color=C_S).move_to([4.6, -1.5, 0])
        self.play(Create(axis), FadeIn(ox), run_time=3)
        self.play(FadeIn(cap3), FadeIn(plus), run_time=2.5)
        self.play(Indicate(avec, scale_factor=1.15), run_time=2.5)
        self.wait(6)


class BlockB2(Scene):
    """Velocity v = v0 + at, 40 s: j2a 12 + j2b 16 + j2c 12."""

    def construct(self):
        cap0 = cap_text("B2", 0)
        # j2a (12): formula assembles in coloured parts.
        p1 = Text("v =", font_size=52, color=C_V).move_to([-3.6, -0.5, 0])
        p2 = Text("v₀", font_size=52, color=C_V).move_to([-1.9, -0.5, 0])
        p3 = Text("+", font_size=52).move_to([-0.9, -0.5, 0])
        p4 = Text("at", font_size=52, color=C_A).move_to([0.4, -0.5, 0])
        # Parts assemble as named: "v =", "v0" (f1), "+" (f1 tail),
        # "at" (f2 head, E2=4.9), full formula cap0 with its recitation.
        self.wait(0.3)
        self.play(Write(p1), run_time=1.7)
        self.play(Write(p2), run_time=1.7)
        self.play(Write(p3), run_time=1.2)
        self.play(Write(p4), run_time=2.1)
        self.play(FadeIn(cap0), run_time=2)
        self.wait(3)
        # j2b (16): stem with the setup, "= 14" pops at W14=16.0 as the
        # number is spoken in all languages, then the box.
        stem, tail = split_cap(CAPTIONS["B2"][1], 28, [0, CAP_Y0 - CAP_DY, 0],
                               tail_color=C_S)
        self.wait(0.3)
        self.play(FadeIn(stem), run_time=2)
        self.wait(1.7)
        self.play(FadeIn(tail), run_time=0.5)
        box = SurroundingRectangle(VGroup(stem, tail), color=C_S, buff=0.15)
        self.play(Create(box), run_time=2)
        self.wait(9.5)
        # j2c (12): unit check + stamp.
        units = Text(f"({UNITS['acc']})·{UNITS['time']} → {UNITS['vel']}",
                     font_size=40).move_to([0, -2.2, 0])
        stamp = Text("✓", font_size=64, color=C_S).move_to([4.9, -2.2, 0])
        self.wait(0.3)
        self.play(FadeIn(units), run_time=2)
        self.wait(3.4)
        self.play(FadeIn(stamp), run_time=1.5)
        self.wait(4.8)


class BlockB3(Scene):
    """Displacement s = v0t + at^2/2, 50 s: j3a 12 + j3b 14 + j3c 24."""

    def construct(self):
        road = make_road()
        # j3a (12): displacement arrow + direction guard.
        cap2 = cap_text("B3", 2)
        arrow = Arrow(road_point(0) + UP * 0.7, road_point(S_END) + UP * 0.7,
                      color=C_S, stroke_width=8, buff=0)
        self.play(FadeIn(road), Create(arrow), run_time=4)
        self.play(FadeIn(cap2), run_time=4)
        self.wait(4)
        # j3b (14): two coloured terms.
        cap0 = cap_text("B3", 0)
        term1 = Text("v₀t", font_size=52, color=C_V).move_to([-3.4, 0.0, 0])
        term2 = Text("at²/2", font_size=52, color=C_A).move_to([-1.2, 0.0, 0])
        # Terms appear as named (word timings): v0t at ~13.5, at2/2 at 14.8;
        # full formula cap0 at E2=17.3 with the explanation.
        self.wait(1.5)
        self.play(Write(term1), run_time=1.3)
        self.play(Write(term2), run_time=2)
        self.wait(0.5)
        self.play(FadeIn(cap0), run_time=2)
        self.wait(6.7)
        # j3c (24): STAGED growth per clause — bar1 to 8 with f1 ("eight" at
        # ~28.4-28.9, bar completes 28.6), bar2 to 24 with f2 (ends 32.1),
        # totals + cap1 at 33.4 ("thirty-two"), then the car replays x(T).
        GROUND = -2.0
        BAR_H = 2.4
        car = make_car().move_to(road_point(0))
        T1 = ValueTracker(0.0)
        T2 = ValueTracker(0.0)
        T3 = ValueTracker(0.0)

        def bar_h1():
            return max(0.03, (V0 * T1.get_value()) / S_END * BAR_H)

        def bar_h2():
            return max(0.03, (0.5 * A * T2.get_value() ** 2) / S_END * BAR_H)

        def bar1():
            h = bar_h1()
            return Rectangle(width=1.4, height=h, fill_color=C_V,
                             fill_opacity=0.8, stroke_width=1).move_to(
                                 [-3.4, GROUND + h / 2, 0])

        def bar2():
            h = bar_h2()
            return Rectangle(width=1.4, height=h, fill_color=C_A,
                             fill_opacity=0.8, stroke_width=1).move_to(
                                 [-1.2, GROUND + h / 2, 0])

        def upd1(m):
            m.set_value(V0 * T1.get_value())
            m.move_to([-3.4, GROUND + bar_h1() + 0.3, 0])

        def upd2(m):
            m.set_value(0.5 * A * T2.get_value() ** 2)
            m.move_to([-1.2, GROUND + bar_h2() + 0.3, 0])

        d1, d2 = always_redraw(bar1), always_redraw(bar2)
        n1 = DecimalNumber(0, num_decimal_places=0, font_size=32, color=C_V)
        n2 = DecimalNumber(0, num_decimal_places=0, font_size=32, color=C_A)
        n1.add_updater(upd1)
        n2.add_updater(upd2)
        self.add(d1, d2, n1, n2)
        self.wait(0.3)
        self.play(FadeOut(arrow), T1.animate.set_value(T_END),
                  run_time=2.3, rate_func=linear)
        n1.clear_updaters()
        n1.set_value(V0 * T_END)
        self.wait(1.0)
        self.play(T2.animate.set_value(T_END), run_time=2.5, rate_func=linear)
        n2.clear_updaters()
        n2.set_value(0.5 * A * T_END ** 2)
        self.wait(1.3)
        cap1 = cap_text("B3", 1)
        fh1 = (V0 * T_END) / S_END * BAR_H
        fh2 = (0.5 * A * T_END ** 2) / S_END * BAR_H
        fb1 = Rectangle(width=1.4, height=fh1, fill_color=C_V,
                        fill_opacity=0.8, stroke_width=1).move_to(
                            [-3.4, GROUND + fh1 / 2, 0])
        fb2 = Rectangle(width=1.4, height=fh2, fill_color=C_A,
                        fill_opacity=0.8, stroke_width=1).move_to(
                            [-1.2, GROUND + fh2 / 2, 0])
        fl1 = Text(f"{V0 * T_END}", font_size=32, color=C_V).move_to(
            [-3.4, GROUND + fh1 + 0.3, 0])
        fl2 = Text(f"{int(0.5 * A * T_END ** 2)}", font_size=32,
                   color=C_A).move_to([-1.2, GROUND + fh2 + 0.3, 0])
        # Finals fade in over identical frozen dynamics (invisible swap).
        self.play(FadeIn(cap1), FadeIn(fb1), FadeIn(fb2), FadeIn(fl1),
                  FadeIn(fl2), FadeIn(car), run_time=2)
        self.remove(d1, d2, n1, n2)
        car.add_updater(lambda m: m.move_to(road_point(x_of(T3.get_value()))))
        self.play(T3.animate.set_value(T_END), run_time=12, rate_func=linear)
        car.clear_updaters()
        car.move_to(road_point(S_END))
        self.wait(2.6)


class BlockB4(Scene):
    """Graph v(t), 40 s: j4a 14 + j4b 14 + j4c 12."""

    def construct(self):
        ax = make_vt_axes()
        labels = axis_labels(ax)
        cap0 = cap_text("B4", 0)
        # j4a (14): axes + self-drawing line. Sweep 2.5-9.7 split at 6.9
        # where the "2" start-marker pops (word "two" ~6.7-7.1); arrival
        # at (4, 14) + "14" label at 9.7 ("fourteen" ~9.5-9.9).
        # T split proportional (2.444/4 over 4.4/2.8 s) — rate stays linear.
        self.play(Create(ax), FadeIn(labels), FadeIn(cap0), run_time=2.5)
        T = ValueTracker(0.0)
        dyn_line = always_redraw(lambda: ax.plot(
            v_of, x_range=[0, max(T.get_value(), 0.02)], color=C_V))
        tracer = always_redraw(lambda: Dot(
            ax.c2p(T.get_value(), v_of(T.get_value())), color=YELLOW, radius=0.09))
        self.add(dyn_line, tracer)
        self.play(T.animate.set_value(2.444), run_time=4.4, rate_func=linear)
        mark_pos = ax.c2p(0, V0)
        mark = VGroup(
            Dot(mark_pos, color=YELLOW, radius=0.11),
            Text("2", font_size=30, color=YELLOW).move_to(
                mark_pos + UP * 0.42 + LEFT * 0.1))
        self.add(mark)
        self.play(T.animate.set_value(T_END), run_time=2.8, rate_func=linear)
        self.remove(dyn_line, tracer)
        line = ax.plot(v_of, x_range=[0, T_END], color=C_V)
        end_pos = ax.c2p(T_END, V_END)
        dot = Dot(end_pos, color=YELLOW, radius=0.09)
        lab14 = Text(f"{V_END}", font_size=30, color=YELLOW).move_to(
            end_pos + UP * 0.35 + RIGHT * 0.35)
        self.add(line)
        self.play(FadeIn(dot), FadeIn(lab14), run_time=1)
        self.wait(3.3)
        # j4b (14): slope triangle dv/dt -> a = 3.
        cap1 = cap_text("B4", 1)
        p0, p1, p2 = ax.c2p(0, V0), ax.c2p(T_END, V0), ax.c2p(T_END, V_END)
        base = Line(p0, p1, color=C_T, stroke_width=5)
        rise = Line(p1, p2, color=C_V, stroke_width=5)
        dt_lab = Text(f"Δt = {T_END}", font_size=26, color=C_T).next_to(
            base.get_center(), DOWN, buff=0.15)
        dv_lab = Text(f"Δv = {V_END - V0}", font_size=26, color=C_V).next_to(
            rise.get_center(), RIGHT, buff=0.15)
        aval = Text(f"a = {A}", font_size=40, color=C_A).move_to([4.3, 0.6, 0])
        self.wait(0.3)
        self.play(Create(base), Create(rise), FadeIn(dt_lab), FadeIn(dv_lab),
                  run_time=2.7)
        self.play(FadeIn(aval), FadeIn(cap1), run_time=2.5)
        self.wait(8.5)
        # j4c (12): rule frozen.
        box = SurroundingRectangle(cap1, color=C_A, buff=0.15)
        self.wait(0.3)
        self.play(Create(box), run_time=4)
        self.wait(7.7)


class BlockB5(Scene):
    """Area check, 30 s: j5a 16 + j5b 14."""

    def construct(self):
        ax = make_vt_axes(x_length=5.2, y_length=2.6, center=[-2.6, -0.6, 0])
        labels = axis_labels(ax)
        line = ax.plot(v_of, x_range=[0, T_END], color=C_V)
        road, car = make_road(), make_car().move_to(road_point(0))
        # j5a (16): STAGED — fill grows with f2 ("area..."), counter+car run
        # with f3 (the computation), "= 32" pops at 14.0 with the counter
        # ("thirty-two" ~13.85-14.04 in all languages).
        self.play(Create(ax), FadeIn(labels), FadeIn(line), FadeIn(road),
                  FadeIn(car), run_time=2)
        TF = ValueTracker(0.0)
        fill = always_redraw(lambda: ax.get_area(
            line, x_range=[0, max(TF.get_value(), 0.02)], color=C_S,
            opacity=0.35))
        self.add(fill)
        self.play(TF.animate.set_value(T_END), run_time=3.9, rate_func=linear)
        self.remove(fill)
        full = ax.get_area(line, x_range=[0, T_END], color=C_S, opacity=0.35)
        self.add(full)
        TM = ValueTracker(0.0)
        counter = DecimalNumber(0, num_decimal_places=0, font_size=56, color=C_S)
        counter.move_to([4.3, 0.2, 0])
        cunit = Text(UNITS["dist"], font_size=36, color=C_S).next_to(
            counter, RIGHT, buff=0.15)
        counter.add_updater(lambda m: m.set_value(
            V0 * TM.get_value() + 0.5 * A * TM.get_value() ** 2))
        car.add_updater(lambda m: m.move_to(road_point(x_of(TM.get_value()))))
        stem, tail = split_cap(CAPTIONS["B5"][0], 28, [0, CAP_Y0, 0],
                               tail_color=C_S)
        self.add(counter, cunit)
        # Main sweep 5.9-14.0 split proportionally (rate const 4/8.1).
        self.play(TM.animate.set_value(0.444), run_time=0.9, rate_func=linear)
        self.play(TM.animate.set_value(1.432), FadeIn(stem),
                  run_time=2, rate_func=linear)
        self.play(TM.animate.set_value(T_END), run_time=5.2, rate_func=linear)
        counter.clear_updaters()
        car.clear_updaters()
        counter.set_value(S_END)
        car.move_to(road_point(S_END))
        self.play(FadeIn(tail), run_time=0.5)
        self.wait(1.5)
        # j5b (14): stamp — 32 matches 32.
        cap1 = cap_text("B5", 1)
        stamp = Text("✓", font_size=72, color=C_S).move_to([4.3, -1.6, 0])
        self.wait(0.3)
        self.play(FadeIn(cap1), run_time=1.7)
        self.play(FadeIn(stamp), run_time=1.5)
        self.wait(10.5)


class BlockB6(Scene):
    """Pause task, 30 s: j6a 10 + j6b 12 + j6c 8."""

    def construct(self):
        # j6a (10): condition card, no solution visible. The card itself shows
        # caption B6[0], so no separate top-band copy (avoids duplication).
        card = Rectangle(width=10.0, height=1.6, color=GRAY, stroke_width=3)
        card.move_to([0, 0.4, 0])
        cond = Text(CAPTIONS["B6"][0], font_size=30).move_to(card.get_center())
        self.play(Create(card), FadeIn(cond), run_time=4)
        self.wait(6)
        # j6b (12): pause card with pulsing icon (no numbers tick).
        cap1 = cap_text("B6", 1)
        icon = VGroup(
            Rectangle(width=0.45, height=1.4, fill_color=WHITE, fill_opacity=0.95,
                      stroke_width=0).move_to([-0.35, -1.8, 0]),
            Rectangle(width=0.45, height=1.4, fill_color=WHITE, fill_opacity=0.95,
                      stroke_width=0).move_to([0.35, -1.8, 0]))
        self.play(FadeIn(icon), FadeIn(cap1), run_time=3)
        for _ in range(3):
            self.play(icon.animate.scale(1.1), run_time=1)
            self.play(icon.animate.scale(1 / 1.1), run_time=1)
        self.wait(3)
        # j6c (8): short solution revealed after the pause.
        cap2 = cap_text("B6", 2)
        steps = Text(f"0·{B6['t']} + {B6['a']}·{B6['t'] ** 2}/2",
                     font_size=40).move_to([0, -1.8, 0])
        self.play(FadeOut(icon), FadeIn(steps), FadeIn(cap2), run_time=3)
        box = SurroundingRectangle(cap2, color=C_S, buff=0.15)
        self.play(Create(box), run_time=1)
        self.wait(4)


class BlockB7(Scene):
    """Traps and recap, 40 s: j7a 14 + j7b 9 + j7c 17."""

    def construct(self):
        # j7a (14): trap E1 crossed out. The big trap text IS caption B7[0]
        # (split: "56" pops at 7.3 as spoken), so no separate top-band copy.
        stem, tail56 = split_cap(CAPTIONS["B7"][0], 56, [0, 0.6, 0])
        self.play(FadeIn(stem), run_time=2.5)
        self.wait(4.8)
        self.play(FadeIn(tail56), run_time=0.5)
        self.wait(0.7)
        cross = Cross(VGroup(stem, tail56), color=RED, stroke_width=8)
        self.play(Create(cross), run_time=2)
        hint = Text(FORMULAS["F-avg"], font_size=44, color=C_S).move_to([0, -1.4, 0])
        self.play(FadeIn(hint), run_time=2)
        self.wait(1.5)
        # j7b (9): slope (red arrow) vs area (green fill) side by side.
        cap1 = cap_text("B7", 1)
        self.play(FadeOut(VGroup(stem, tail56, cross, hint)), run_time=1)
        ax_l = make_vt_axes(x_length=2.6, y_length=1.8, center=[-3.6, -1.2, 0])
        ax_r = make_vt_axes(x_length=2.6, y_length=1.8, center=[3.6, -1.2, 0])
        line_l = ax_l.plot(v_of, x_range=[0, T_END], color=C_V)
        line_r = ax_r.plot(v_of, x_range=[0, T_END], color=C_V)
        sparr = Arrow(ax_l.c2p(1, v_of(1)), ax_l.c2p(3, v_of(3)), color=C_A,
                      stroke_width=7, buff=0)
        sfill = ax_r.get_area(line_r, x_range=[0, T_END], color=C_S, opacity=0.4)
        self.play(Create(ax_l), Create(line_l), Create(sparr), run_time=2.3)
        self.play(Create(ax_r), Create(line_r), FadeIn(sfill), FadeIn(cap1),
                  run_time=2.5)
        self.wait(3.2)
        # j7c (17): formula triptych + ENT bridge.
        cap2 = cap_text("B7", 2)
        parts = [p.strip() for p in CAPTIONS["B7"][2].split(";")]
        f1 = Text(parts[0], font_size=40, color=C_V).move_to([-3.4, 0.4, 0])
        f2 = Text(parts[1], font_size=40, color=C_S).move_to([2.6, 0.4, 0])
        f3 = Text(FORMULAS["F-avg"], font_size=40, color=C_T).move_to([0, -0.7, 0])
        # F1 with the recap head; F2/F3 staggered over their naming windows.
        self.play(FadeOut(VGroup(ax_l, line_l, sparr, ax_r, line_r, sfill)),
                  FadeIn(f1), FadeIn(cap2), run_time=2.5)
        self.wait(0.3)
        self.play(FadeIn(f2), run_time=1.2)
        self.wait(2.0)
        self.play(FadeIn(f3), run_time=2.0)
        self.wait(3.1)
        bridge = Text("✓", font_size=64, color=C_S).move_to([0, -2.2, 0])
        self.play(FadeIn(bridge), run_time=2.5)
        self.wait(3.4)
