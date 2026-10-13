from manim import *


class StageCProbe(Scene):
    def construct(self):
        formula = MathTex(r"v = v_0 + at").scale(1.2)
        formula.to_edge(UP)
        ax = Axes(
            x_range=[0, 4, 1],
            y_range=[0, 14, 2],
            x_length=5,
            y_length=3,
            x_axis_config={"include_tip": True},
            y_axis_config={"include_tip": True},
        )
        line = ax.plot(lambda t: 2 + 3 * t, color=BLUE)
        label = ax.get_graph_label(line, MathTex(r"v(t)=2+3t"))
        lines = VGroup(
            Text("Скорость растёт линейно", font_size=26),
            Text("Жылдамдық сызықты өседі: ә ғ қ ң ө ұ ү һ і", font_size=26),
            Text("Velocity grows linearly", font_size=26),
        ).arrange(DOWN, aligned_edge=LEFT).to_edge(DOWN)
        self.play(Write(formula), run_time=1)
        self.play(Create(ax), run_time=1)
        self.play(Create(line), FadeIn(label), run_time=1.5)
        self.play(FadeIn(lines), run_time=1)
        self.wait(0.5)
