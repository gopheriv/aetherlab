from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from aetherlab.services.multibody import integrate_newtonian
from aetherlab.services.scene_components import _compose_component, compose_scene_code
from aetherlab.services.scene_components.problems import compose_problem
from aetherlab.services.scene_components.problems.three_body import check_lines, matches


def _circular_pair():
    # Two unit masses orbit their common centre at radius one when v = 1/2.
    return [1.0, 1.0], [[-1.0, 0.0], [1.0, 0.0]], [[0.0, -0.5], [0.0, 0.5]]


def test_velocity_verlet_two_body_circular_orbit_conserves_invariants():
    masses, positions, velocities = _circular_pair()
    result = integrate_newtonian(
        masses, positions, velocities, gravitational_constant=1.0,
        t_end=2.0, dt=0.002, sample_every=100,
    )
    assert result.ok, result.note
    assert result.times[0] == 0.0 and result.times[-1] == pytest.approx(2.0)
    assert result.energy_error < 1e-6
    assert result.angular_momentum_error < 1e-12
    radius = np.linalg.norm(result.positions[-1, 0])
    assert radius == pytest.approx(1.0, abs=2e-6)


def test_step_halving_converges_on_the_analytic_two_body_fixture():
    masses, positions, velocities = _circular_pair()
    base = integrate_newtonian(
        masses, positions, velocities, gravitational_constant=1.0,
        t_end=1.0, dt=0.01,
    )
    refined = integrate_newtonian(
        masses, positions, velocities, gravitational_constant=1.0,
        t_end=1.0, dt=0.005,
    )
    assert base.ok and refined.ok
    scale = 2.0
    error = np.max(np.abs(base.positions[-1] - refined.positions[-1])) / scale
    assert error < 1e-4


def test_three_body_translation_and_mass_identity_are_preserved():
    result = integrate_newtonian(
        [1.0, 2.0, 3.0], [[-1.0, 0.0], [1.0, 0.0], [0.0, 1.5]],
        [[0.0, -0.1], [0.0, 0.05], [0.1, 0.0]],
        gravitational_constant=0.1, t_end=0.2, dt=0.001, sample_every=7,
    )
    assert result.ok, result.note
    assert result.positions.shape[1:] == (3, 2)
    assert result.positions[-1, 2, 0] > result.positions[0, 2, 0]
    assert np.isfinite(result.velocities).all()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"masses": [1.0], "positions": [[0, 0]], "velocities": [[0, 0]]},
        {"masses": [1.0, -1.0], "positions": [[0, 0], [1, 0]], "velocities": [[0, 0], [0, 0]]},
        {"masses": [1.0, 1.0], "positions": [[0, 0], [1, 0]], "velocities": [[0, 0], [0]]},
        {"masses": [1.0, 1.0], "positions": [[0, 0], [0, 0]], "velocities": [[0, 0], [0, 0]]},
    ],
)
def test_invalid_or_colliding_models_fail_closed(kwargs):
    values = {
        "gravitational_constant": 1.0, "t_end": 1.0, "dt": 0.01,
    }
    values.update(kwargs)
    result = integrate_newtonian(**values)
    assert not result.ok
    assert result.note


def test_close_approach_respects_explicit_exclusion_radius():
    result = integrate_newtonian(
        [1.0, 1.0], [[-0.5, 0.0], [0.5, 0.0]], [[0.0, 0.0], [0.0, 0.0]],
        gravitational_constant=1.0, t_end=0.1, dt=0.001, collision_radius=0.995,
    )
    assert not result.ok
    assert "exclusion radius" in result.note


def test_step_limit_is_bounded_and_reported():
    result = integrate_newtonian(
        [1.0, 1.0], [[0.0, 0.0], [1.0, 0.0]], [[0.0, 0.0], [0.0, 0.0]],
        gravitational_constant=1.0, t_end=10.0, dt=1e-8,
    )
    assert not result.ok
    assert "limit is" in result.note


def _three_body_solver():
    variables = {
        "m1": 1.0, "m2": 1.0, "m3": 1.0,
        "x1": -1.0, "y1": 0.0, "x2": 1.0, "y2": 0.0, "x3": 0.0, "y3": 2.0,
        "vx1": 0.0, "vy1": -0.3, "vx2": 0.0, "vy2": 0.3, "vx3": 0.1, "vy3": 0.0,
        "g": 0.1, "t_end": 0.5,
    }
    return SimpleNamespace(
        summary="Explicit three-body Newtonian encounter.",
        keywords=["three body", "gravity"], variables=variables,
    )


def test_curated_three_body_scene_requires_explicit_data_and_refinement():
    solver = _three_body_solver()
    assert matches(solver)
    lines = check_lines(solver)
    assert len(lines) == 1 and "passed step-refinement checks" in lines[0]
    name, code = compose_problem("AetherLabScene", solver)
    assert name == "three_body"
    assert "class AetherLabScene(Scene)" in code
    assert "set_points_as_corners" in code
    assert "closest=" in code


def test_three_body_route_rejects_missing_initial_state_and_other_topics():
    incomplete = _three_body_solver()
    del incomplete.variables["vx3"]
    assert not matches(incomplete)
    unrelated = _three_body_solver()
    unrelated.keywords = ["blackbody"]
    unrelated.summary = "Planck radiation spectrum"
    assert not matches(unrelated)


def test_three_body_prompt_never_falls_through_to_kepler_orbit():
    solver = _three_body_solver()
    del solver.variables["vx3"]
    assert compose_problem("AetherLabScene", solver, prompt_context="three-body encounter") is None
    assert _compose_component(
        "AetherLabScene", solver, problem_prompt="three-body encounter",
    ) is None
    assert compose_scene_code(
        "AetherLabScene", solver, problem_prompt="three-body encounter",
    ) is None
