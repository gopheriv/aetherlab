"""Bounded Newtonian N-body integration for verified scene data.

This deliberately small solver supports point masses with explicit initial
conditions. It has no collision softening, hidden unit conversion, or inferred
state. Close approaches inside the caller's exclusion radius fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

MAX_BODIES = 8
MAX_STEPS = 200_000


@dataclass(frozen=True)
class NBodyResult:
    ok: bool
    times: np.ndarray
    positions: np.ndarray
    velocities: np.ndarray
    energy_error: float
    angular_momentum_error: float
    minimum_separation: float
    step_seconds: float
    note: str = ""


def integrate_newtonian(
    masses,
    positions,
    velocities,
    *,
    gravitational_constant: float,
    t_end: float,
    dt: float,
    sample_every: int = 1,
    collision_radius: float = 0.0,
) -> NBodyResult:
    """Integrate 2–8 mutually gravitating bodies with kick-drift-kick Verlet.

    Positions and velocities are N×2 or N×3 arrays. All inputs use one
    consistent unit system. The integration step is adjusted down (never up)
    only to land exactly on ``t_end``; a model over ``MAX_STEPS`` is rejected.
    """
    empty = np.empty((0,), dtype=float)

    def failed(note: str) -> NBodyResult:
        return NBodyResult(False, empty, empty, empty, float("inf"), float("inf"), 0.0, 0.0, note)

    try:
        mass = np.asarray(masses, dtype=float)
        x = np.asarray(positions, dtype=float)
        v = np.asarray(velocities, dtype=float)
        g, end, step = float(gravitational_constant), float(t_end), float(dt)
        radius = float(collision_radius)
        sample = int(sample_every)
    except (TypeError, ValueError, OverflowError):
        return failed("inputs must be finite numeric arrays/scalars")
    if mass.ndim != 1 or not 2 <= len(mass) <= MAX_BODIES:
        return failed(f"body count must be between 2 and {MAX_BODIES}")
    if x.ndim != 2 or v.shape != x.shape or x.shape[0] != len(mass) or x.shape[1] not in (2, 3):
        return failed("positions/velocities must be matching N×2 or N×3 arrays")
    if not (np.isfinite(mass).all() and np.isfinite(x).all() and np.isfinite(v).all()):
        return failed("all initial conditions must be finite")
    if np.any(mass <= 0):
        return failed("all masses must be positive")
    if not (np.isfinite(g) and g > 0 and np.isfinite(end) and end > 0 and np.isfinite(step) and step > 0):
        return failed("G, t_end, and dt must be finite and positive")
    if not np.isfinite(radius) or radius < 0:
        return failed("collision_radius must be finite and non-negative")
    if sample <= 0:
        return failed("sample_every must be a positive integer")

    steps = int(np.ceil(end / step))
    if steps <= 0 or steps > MAX_STEPS:
        return failed(f"integration requires {steps} steps; limit is {MAX_STEPS}")
    h = end / steps
    n, dim = x.shape

    def distances_and_acceleration(state: np.ndarray):
        acceleration = np.zeros_like(state)
        minimum = float("inf")
        for i in range(n - 1):
            for j in range(i + 1, n):
                delta = state[j] - state[i]
                distance_sq = float(np.dot(delta, delta))
                distance = float(np.sqrt(distance_sq))
                if not np.isfinite(distance_sq) or not np.isfinite(distance):
                    raise ArithmeticError("pair separation overflowed the numeric range")
                minimum = min(minimum, distance)
                if distance <= max(radius, np.finfo(float).tiny):
                    raise ArithmeticError("point-mass collision/exclusion radius reached")
                inv_r3 = 1.0 / (distance_sq * distance)
                acceleration[i] += g * mass[j] * delta * inv_r3
                acceleration[j] -= g * mass[i] * delta * inv_r3
        if not np.isfinite(acceleration).all():
            raise ArithmeticError("force evaluation produced a non-finite acceleration")
        return acceleration, minimum

    def invariants(state: np.ndarray, speed: np.ndarray) -> tuple[float, np.ndarray]:
        kinetic = 0.5 * float(np.sum(mass[:, None] * speed * speed))
        potential = 0.0
        for i in range(n - 1):
            for j in range(i + 1, n):
                distance = float(np.linalg.norm(state[j] - state[i]))
                potential -= g * mass[i] * mass[j] / distance
        angular = np.zeros(3, dtype=float)
        for m, point, velocity in zip(mass, state, speed, strict=True):
            if dim == 2:
                angular[2] += m * (point[0] * velocity[1] - point[1] * velocity[0])
            else:
                angular += m * np.cross(point, velocity)
        if not np.isfinite(kinetic) or not np.isfinite(potential) or not np.isfinite(angular).all():
            raise ArithmeticError("invariant evaluation produced a non-finite result")
        return kinetic + potential, angular

    try:
        acceleration, minimum = distances_and_acceleration(x)
        initial_energy, initial_angular = invariants(x, v)
        length_scale = max(float(np.max(np.linalg.norm(x[:, None, :] - x[None, :, :], axis=2))), 1e-12)
        velocity_scale = max(float(np.sqrt(np.mean(v * v))), np.sqrt(g * float(np.sum(mass)) / length_scale), 1e-12)
        energy_scale = max(abs(initial_energy), 0.5 * float(np.sum(mass)) * velocity_scale**2, 1e-30)
        angular_scale = max(
            float(np.linalg.norm(initial_angular)),
            float(np.sum(mass)) * length_scale * velocity_scale,
            1e-30,
        )
        angular_error = 0.0
        energy_error = 0.0
        sample_x = [x.copy()]
        sample_v = [v.copy()]
        sample_t = [0.0]
        for index in range(1, steps + 1):
            half_v = v + 0.5 * h * acceleration
            x = x + h * half_v
            next_acceleration, current_min = distances_and_acceleration(x)
            v = half_v + 0.5 * h * next_acceleration
            if not np.isfinite(x).all() or not np.isfinite(v).all():
                raise ArithmeticError("integration produced a non-finite state")
            acceleration = next_acceleration
            minimum = min(minimum, current_min)
            energy, angular = invariants(x, v)
            energy_error = max(energy_error, abs(energy - initial_energy) / energy_scale)
            angular_error = max(
                angular_error, float(np.linalg.norm(angular - initial_angular)) / angular_scale,
            )
            if index % sample == 0 or index == steps:
                sample_x.append(x.copy())
                sample_v.append(v.copy())
                sample_t.append(index * h)
    except (ArithmeticError, FloatingPointError, OverflowError, ZeroDivisionError) as exc:
        return failed(str(exc))
    if not (np.isfinite(x).all() and np.isfinite(v).all()):
        return failed("integration produced a non-finite state")
    return NBodyResult(
        True,
        np.asarray(sample_t, dtype=float),
        np.asarray(sample_x, dtype=float),
        np.asarray(sample_v, dtype=float),
        float(energy_error),
        float(angular_error),
        float(minimum),
        float(h),
    )
