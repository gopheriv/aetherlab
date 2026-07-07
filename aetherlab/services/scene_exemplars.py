"""Curated, gate-passing Manim exemplars injected into the codegen prompt.

The cinematic system prompt DESCRIBES a well-directed scene; these SHOW one. One
domain-matched exemplar is added to the scene-generation context so the model
imitates concrete, correct Manim-CE API usage and a clear ESTABLISH → EVOLVE →
REVEAL arc — which reduces hallucinated-API render crashes and flat "axes + one
curve" compositions (the failure modes the pipeline otherwise only catches after
an expensive render).

Every exemplar is Text-only (no LaTeX so it renders without a TeX toolchain),
uses only the render-proven vocabulary of ``scene_templates``, and is verified to
compile, pass ``code_safety``, pass ``scene_validation``, and render (see
test_features.py F163). Keyed by the domains of ``scene_templates.detect_domain``
(pendulum / orbit / wave / oscillator).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

# ── the exemplars ───────────────────────────────────────────────────────────

_OSCILLATOR = '''from manim import *
import numpy as np
import math


class AetherLabScene(Scene):
    def construct(self):
        # ESTABLISH — name the system, then reveal the stage.
        title = Text("Damped Harmonic Oscillator", color="#F8FAFC").scale(0.5).to_edge(UP)
        subtitle = Text("amplitude decays each cycle", color="#22D3EE").scale(0.32)
        subtitle.next_to(title, DOWN, buff=0.2)
        self.play(Write(title), run_time=1.0)
        self.play(FadeIn(subtitle, shift=UP * 0.2), run_time=0.6)

        axes = Axes(x_range=[0, 10, 2], y_range=[-1.2, 1.2, 0.5]).scale(0.55).to_edge(DOWN)
        self.play(Create(axes), run_time=1.0)

        # EVOLVE — draw the decaying cosine inside its amplitude envelope.
        zeta, omega = 0.18, 2.2
        curve = axes.plot(lambda x: math.exp(-zeta * x) * math.cos(omega * x), color="#22D3EE")
        env_hi = axes.plot(lambda x: math.exp(-zeta * x), color="#F59E0B")
        env_lo = axes.plot(lambda x: -math.exp(-zeta * x), color="#F59E0B")
        self.play(Create(curve), run_time=2.0)
        self.play(Create(env_hi), Create(env_lo), run_time=0.9)

        # REVEAL — a hero label rides the envelope while a tracer keeps moving.
        t = ValueTracker(0.0)
        dot = always_redraw(lambda: Dot(
            axes.c2p(t.get_value(),
                     math.exp(-zeta * t.get_value()) * math.cos(omega * t.get_value())),
            color="#F8FAFC", radius=0.09))
        tag = Text("A·e^(-zeta·omega·t)", color="#F59E0B").scale(0.32)
        tag.next_to(axes.c2p(2.2, math.exp(-zeta * 2.2)), UP, buff=0.15)
        self.add(dot)
        self.play(t.animate.set_value(9.5), FadeIn(tag), run_time=4.0, rate_func=linear)
        self.wait(0.6)
'''

_PENDULUM = '''from manim import *
import numpy as np
import math


class AetherLabScene(Scene):
    def construct(self):
        # ESTABLISH — the object first, its graph second.
        title = Text("Simple Pendulum", color="#F8FAFC").scale(0.5).to_edge(UP)
        self.play(Write(title), run_time=0.9)

        g, length, damping = 9.81, 1.0, 0.12
        omega = math.sqrt(g / length)
        theta0 = 0.9
        pivot = np.array([-3.2, 0.6, 0.0])
        rod_len = 1.9
        t = ValueTracker(0.0)

        def theta_at(time):
            return theta0 * math.exp(-damping * time) * math.cos(omega * time)

        def bob_pos():
            th = theta_at(t.get_value())
            return pivot + rod_len * np.array([math.sin(th), -math.cos(th), 0.0])

        anchor = Dot(pivot, color="#F8FAFC", radius=0.05)
        rod = always_redraw(lambda: Line(pivot, bob_pos(), color="#94A3B8", stroke_width=3))
        bob = always_redraw(lambda: Dot(bob_pos(), color="#F59E0B", radius=0.14))
        self.play(Create(rod), FadeIn(bob), FadeIn(anchor), run_time=0.8)

        # EVOLVE — trace theta(t) on axes as the bob swings.
        axes = Axes(x_range=[0, 8, 2], y_range=[-1, 1, 0.5]).scale(0.42)
        axes.to_edge(DOWN).shift(RIGHT * 1.8)
        trace = always_redraw(lambda: axes.plot(
            theta_at, x_range=[0, max(t.get_value(), 0.01)], color="#22D3EE"))
        label = Text("theta(t)", color="#F8FAFC").scale(0.3).next_to(axes, UP, buff=0.1)
        self.play(Create(axes), FadeIn(label), run_time=0.8)
        self.add(trace)

        # REVEAL — the period law, while the swing keeps decaying.
        tag = Text("T = 2·pi·sqrt(L/g)", color="#F59E0B").scale(0.34).next_to(title, DOWN, buff=0.25)
        self.play(t.animate.set_value(8.0), FadeIn(tag), run_time=5.0, rate_func=linear)
        self.wait(0.5)
'''

_ORBIT = '''from manim import *
import numpy as np
import math


class AetherLabScene(Scene):
    def construct(self):
        # ESTABLISH — the elliptical orbit and its focus.
        title = Text("Kepler Orbit", color="#F8FAFC").scale(0.5).to_edge(UP)
        self.play(Write(title), run_time=0.9)

        a, e = 2.6, 0.55
        b = a * math.sqrt(1 - e * e)
        center = np.array([0.0, -1.1, 0.0])
        focus = center + np.array([a * e, 0.0, 0.0])
        orbit = Ellipse(width=2 * a, height=2 * b, color="#22D3EE").move_to(center)
        star = Dot(focus, color="#F59E0B", radius=0.16)
        self.play(Create(orbit), run_time=1.4)
        self.play(FadeIn(star, scale=0.5), run_time=0.5)

        # EVOLVE — the planet sweeps, the radius vector tracks it.
        t = ValueTracker(0.0)

        def planet_pos():
            ang = t.get_value()
            return center + np.array([a * math.cos(ang), b * math.sin(ang), 0.0])

        planet = always_redraw(lambda: Dot(planet_pos(), color="#F8FAFC", radius=0.1))
        radius = always_redraw(lambda: Line(focus, planet_pos(), color="#94A3B8", stroke_width=2))
        self.add(radius, planet)

        # REVEAL — the law that makes the motion non-uniform.
        tag = Text("equal areas in equal times", color="#F59E0B").scale(0.32)
        tag.next_to(title, DOWN, buff=0.25)
        self.play(t.animate.set_value(2 * math.pi), FadeIn(tag), run_time=5.0, rate_func=linear)
        self.wait(0.5)
'''

_WAVE = '''from manim import *
import numpy as np
import math


class AetherLabScene(Scene):
    def construct(self):
        # ESTABLISH — the string and its axes.
        title = Text("Standing Wave", color="#F8FAFC").scale(0.5).to_edge(UP)
        self.play(Write(title), run_time=0.9)

        axes = Axes(x_range=[0, 6.283, 1.571], y_range=[-1.5, 1.5, 0.5]).scale(0.6).to_edge(DOWN)
        self.play(Create(axes), run_time=1.0)

        # EVOLVE — a standing wave oscillates between its envelopes.
        k, omega = 2.0, 2.5
        t = ValueTracker(0.0)
        wave = always_redraw(lambda: axes.plot(
            lambda x: math.sin(k * x) * math.cos(omega * t.get_value()), color="#22D3EE"))
        env_hi = axes.plot(lambda x: math.sin(k * x), color="#F59E0B")
        env_lo = axes.plot(lambda x: -math.sin(k * x), color="#F59E0B")
        self.play(Create(env_hi), Create(env_lo), run_time=0.9)
        self.add(wave)

        # REVEAL — mark the nodes (fixed points) as the hero idea.
        nodes = VGroup(*[Dot(axes.c2p(n * math.pi / k, 0.0), color="#F8FAFC", radius=0.07)
                         for n in range(4)])
        tag = Text("nodes stay fixed", color="#F59E0B").scale(0.32).next_to(title, DOWN, buff=0.25)
        self.play(FadeIn(nodes, lag_ratio=0.2), FadeIn(tag), run_time=1.0)
        self.play(t.animate.set_value(4.0), run_time=4.0, rate_func=linear)
        self.wait(0.5)
'''

EXEMPLARS: dict[str, str] = {
    "oscillator": _OSCILLATOR,
    "pendulum": _PENDULUM,
    "orbit": _ORBIT,
    "wave": _WAVE,
}


# ── selection + prompt assembly ─────────────────────────────────────────────


def exemplar_for(
    keywords: Iterable[str] | None,
    variables: Mapping[str, float] | None,
) -> tuple[str, str] | None:
    """Return ``(domain, exemplar_code)`` matched to the problem, or None.

    Selection reuses ``scene_templates.detect_domain`` so the exemplar's physics
    matches the scene the pipeline would otherwise build. Fail-soft: any error
    (or an unknown domain) yields None and the prompt simply carries no exemplar.
    """
    try:
        from aetherlab.services.scene_templates import detect_domain

        domain = detect_domain(list(keywords or []), dict(variables or {}))
    except Exception:  # noqa: BLE001 — an exemplar is a bonus, never fatal
        return None
    code = EXEMPLARS.get(domain)
    return (domain, code) if code else None


def exemplar_block(
    keywords: Iterable[str] | None,
    variables: Mapping[str, float] | None,
) -> str:
    """Formatted few-shot block for the codegen prompt (\"\" when no match)."""
    match = exemplar_for(keywords, variables)
    if not match:
        return ""
    domain, code = match
    return (
        f"## Reference exemplar — a well-directed {domain} scene\n"
        "Study its STRUCTURE and its correct Manim-CE API usage: three beats "
        "(establish the object → evolve the motion → reveal the hero idea), a "
        "labelled hero moment, and motion that keeps going into the final frame. "
        "Do NOT copy it verbatim — adapt the technique to THIS problem's physics "
        "and variables.\n"
        f"```python\n{code}```\n"
    )
