"""Fast unit tests for the projectile curated component (no Manim run)."""
from types import SimpleNamespace

from aetherlab.services.scene_components import projectile


def _solver(**variables):
    return SimpleNamespace(
        variables=variables,
        summary="UNT test throw",
    )


def test_build_returns_complete_scene():
    code = projectile.build("UNTTestThrow", _solver(v0=20.0, angle=60.0))
    assert code is not None
    assert "class UNTTestThrow(Scene)" in code
    assert "rate_func=linear" in code  # physics sweep must not be eased
    assert "{angle_rad}" not in code and "{path}" not in code  # fully substituted


def test_integration_matches_theory():
    # UNT convention g=10, v0=20, 60°: R=34.64м, H=15.0м baked into the labels.
    code = projectile.build("UNTTestThrow", _solver(v0=20.0, angle=60.0))
    assert code is not None
    assert "R = 34.6 м" in code
    assert "H = 15.0 м" in code
    th = projectile.theory(20.0, 60.0)
    assert th["range"] == abs(th["range"])
    assert abs(th["range"] - 34.641) < 0.01
    assert abs(th["apex"] - 15.0) < 0.01
    assert abs(th["flight_time"] - 3.4641) < 0.001


def test_params_clamp_garbage():
    p = projectile.params(SimpleNamespace(variables={"v0": -5, "angle": "nope"}))
    assert p["v0"] == 1.0
    assert p["angle_deg"] == 5.0
