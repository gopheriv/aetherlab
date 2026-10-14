"""Invariant-checked Newtonian three-body scene for explicit 2D initial data."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from aetherlab.services.multibody import integrate_newtonian
from aetherlab.services.scene_components.problems._kit import text_of, variables_of


def _extract(values: dict[str, float]):
    def first(*names: str) -> float | None:
        for name in names:
            if name in values:
                return values[name]
        return None

    masses = [first(f"m{i}", f"m_{i}", f"mass{i}", f"mass_{i}") for i in range(1, 4)]
    positions = [[first(f"x{i}", f"x_{i}"), first(f"y{i}", f"y_{i}")] for i in range(1, 4)]
    velocities = [
        [first(f"vx{i}", f"v_x{i}", f"vx_{i}", f"v_x_{i}"),
         first(f"vy{i}", f"v_y{i}", f"vy_{i}", f"v_y_{i}")]
        for i in range(1, 4)
    ]
    g = first("g", "gravitational_constant", "gravitationalconstant")
    end = first("t_end", "tend", "end_time", "endtime")
    if (
        any(value is None for value in masses)
        or any(value is None for pair in positions + velocities for value in pair)
        or g is None or end is None
    ):
        return None
    masses = [float(value) for value in masses]
    positions = [[float(value) for value in pair] for pair in positions]
    velocities = [[float(value) for value in pair] for pair in velocities]
    g, end = float(g), float(end)
    if not (
        all(math.isfinite(value) and value > 0 for value in masses)
        and math.isfinite(g) and g > 0 and math.isfinite(end) and end > 0
    ):
        return None
    distances = [
        math.dist(positions[i], positions[j])
        for i in range(3) for j in range(i + 1, 3)
    ]
    collision_radius = first("collision_radius", "collisionradius")
    if collision_radius is None:
        collision_radius = max(min(distances) * 1e-5, 1e-10)
    collision_radius = float(collision_radius)
    if not math.isfinite(collision_radius) or collision_radius < 0:
        return None
    return masses, positions, velocities, g, end, collision_radius


def matches(solver: Any, prompt_context: str = "") -> bool:
    text = f"{text_of(solver)} {prompt_context}".replace("-", " ").lower()
    explicit_three_body = "three body" in text or "3 body" in text
    return explicit_three_body and _extract(variables_of(solver)) is not None


def _verified_trajectory(values: dict[str, float]):
    data = _extract(values)
    if data is None:
        return None, "all masses, 2D positions/velocities, G, and t_end are required"
    masses, positions, velocities, g, end, collision_radius = data
    # Refine by a factor of two and compare both conservation laws and endpoint.
    base_steps = 10_000
    base = integrate_newtonian(
        masses, positions, velocities, gravitational_constant=g, t_end=end,
        dt=end / base_steps, sample_every=max(1, math.ceil(base_steps / 160)),
        collision_radius=collision_radius,
    )
    refined = integrate_newtonian(
        masses, positions, velocities, gravitational_constant=g, t_end=end,
        dt=end / (2 * base_steps), sample_every=2 * base_steps,
        collision_radius=collision_radius,
    )
    if not base.ok:
        return None, base.note
    if not refined.ok:
        return None, f"refined integration failed: {refined.note}"
    extent = max(
        float(np.ptp(np.asarray(positions)[:, 0])),
        float(np.ptp(np.asarray(positions)[:, 1])),
        1e-9,
    )
    endpoint_difference = float(np.max(np.abs(base.positions[-1] - refined.positions[-1]))) / extent
    if base.energy_error > 1e-3 or base.angular_momentum_error > 1e-3:
        return None, "relative energy or angular-momentum drift exceeds 0.1%"
    if endpoint_difference > 1e-2:
        return None, "halved-step endpoint differs by more than 1% of initial extent"
    return (base, masses, end, endpoint_difference), ""


def check_lines(solver: Any) -> list[str]:
    if not matches(solver):
        return []
    verified, reason = _verified_trajectory(variables_of(solver))
    if verified is None:
        return [f"Three-body scene declined: {reason}."]
    result, _masses, _end, endpoint_error = verified
    return [
        "Three-body Newtonian integration passed step-refinement checks: "
        f"energy drift={result.energy_error:.3g}, "
        f"angular-momentum drift={result.angular_momentum_error:.3g}, "
        f"endpoint difference={endpoint_error:.3g}, "
        f"minimum separation={result.minimum_separation:.5g}."
    ]


def build(class_name: str, solver: Any) -> str | None:
    verified, _reason = _verified_trajectory(variables_of(solver))
    if verified is None:
        return None
    result, masses, end, _endpoint_error = verified
    sampled = result.positions
    payload = {
        "masses": [float(value) for value in masses],
        "positions": [
            [[float(round(coord, 9)) for coord in point] for point in sample]
            for sample in sampled
        ],
        "energy_error": result.energy_error,
        "angular_error": result.angular_momentum_error,
        "minimum_separation": result.minimum_separation,
        "t_end": end,
        "units": "consistent input units",
    }
    return _TEMPLATE.replace("__CLASS__", class_name).replace("__DATA__", repr(payload))


_TEMPLATE = '''\
"""AetherLab: invariant-checked 2D Newtonian three-body encounter."""
import numpy as np
from manim import *

class __CLASS__(Scene):
    def construct(self):
        data = __DATA__
        samples = np.asarray(data["positions"], dtype=float)
        masses = data["masses"]
        colors = [BLUE, ORANGE, GREEN]
        all_xy = samples.reshape((-1, 2))
        x0, x1 = float(np.min(all_xy[:, 0])), float(np.max(all_xy[:, 0]))
        y0, y1 = float(np.min(all_xy[:, 1])), float(np.max(all_xy[:, 1]))
        xpad = max((x1 - x0) * 0.12, 0.25)
        ypad = max((y1 - y0) * 0.12, 0.25)
        if x1 - x0 < 1e-8:
            x0, x1 = x0 - 1.0, x1 + 1.0
        if y1 - y0 < 1e-8:
            y0, y1 = y0 - 1.0, y1 + 1.0
        axes = Axes(
            x_range=[x0 - xpad, x1 + xpad, max((x1 - x0) / 4.0, 0.1)],
            y_range=[y0 - ypad, y1 + ypad, max((y1 - y0) / 4.0, 0.1)],
            x_length=10.0, y_length=5.0,
            axis_config={"include_tip": False, "stroke_opacity": 0.45},
        ).move_to(DOWN * 0.72)
        title = Text("Three bodies, one gravitational field", font_size=30).to_edge(UP)
        subtitle = Text("Point-mass model | consistent input units", font_size=18, color=GRAY_B)
        subtitle.next_to(title, DOWN, buff=0.1)
        legend = VGroup(*[
            Text(f"m{index + 1}={masses[index]:g}", font_size=16, color=colors[index])
            for index in range(3)
        ]).arrange(RIGHT, buff=0.35).next_to(subtitle, DOWN, buff=0.12)
        paths = VGroup()
        moving = VGroup()
        trackers = []
        for body in range(3):
            points = [axes.c2p(float(point[body, 0]), float(point[body, 1])) for point in samples]
            path = VMobject(color=colors[body], stroke_width=2.2, stroke_opacity=0.65)
            path.set_points_as_corners(points)
            paths.add(path)
            dot = Dot(points[0], color=colors[body], radius=0.1)
            tracker = ValueTracker(0.0)
            def move_body(mob, alpha, trajectory=points):
                q = float(np.clip(alpha * (len(trajectory) - 1), 0.0, len(trajectory) - 1))
                k = min(int(q), len(trajectory) - 2)
                fraction = q - k
                mob.move_to(trajectory[k] * (1.0 - fraction) + trajectory[k + 1] * fraction)
            dot.add_updater(lambda mob, tr=tracker, fn=move_body: fn(mob, tr.get_value()))
            moving.add(dot)
            trackers.append(tracker)
        stats = Text(
            f"dE/scale={data['energy_error']:.2g}  "
            f"dL/scale={data['angular_error']:.2g}  "
            f"closest={data['minimum_separation']:.3g}",
            font_size=16, color=GRAY_A,
        ).to_edge(DOWN, buff=0.06)
        self.play(FadeIn(title), FadeIn(subtitle), FadeIn(legend), Create(axes), run_time=2.0)
        self.play(LaggedStart(*[Create(path) for path in paths], lag_ratio=0.2), run_time=4.0)
        self.add(moving)
        self.play(*[tracker.animate.set_value(1.0) for tracker in trackers], run_time=18.0, rate_func=linear)
        self.play(FadeIn(stats), run_time=2.0)
        self.wait(4.0)
'''
