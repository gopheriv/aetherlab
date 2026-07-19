"""Numerical ground truth for physics problems.

A solver may attach an ODE `numeric_spec` (see the system prompt in
services/llm.py). This module integrates it with scipy `solve_ivp` to produce
the *exact* trajectory that drives the canvas and the research PDF, instead of
trusting a curve the model guessed.

Right-hand sides are compiled through services/plotting.compile_expression —
the same AST allow-list used everywhere else — so model-authored math is never
`eval`'d directly. scipy is optional: if it is missing (or the spec is invalid)
solve_numeric returns an `ok=False` NumericSolution and callers fall back to the
analytic plot payload.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from aetherlab.core.models import NumericSolution
from aetherlab.services.plotting import ExprError, compile_expression

MAX_STATE_VARS = 6
MAX_POINTS = 2000
MAX_T_SPAN = 1.0e4


def solve_numeric(
    spec: Any, variables: dict[str, float], *, max_points: int = 400
) -> NumericSolution:
    """Integrate an ODE spec into a NumericSolution. Never raises.

    Spec schema:
        {"state": ["x", "v"],
         "rhs":   ["v", "-(stiffness/mass)*x - (2*damping)*v"],
         "initial": [1.0, 0.0],
         "t_range": [0.0, 20.0],
         "observe": "x"}          # optional; defaults to state[0]
    """
    try:
        from scipy.integrate import solve_ivp
    except Exception:
        return NumericSolution(ok=False, note="scipy not installed; analytic fallback used.")

    try:
        state, rhs, initial, (t0, t1), observe = _validate(spec)
    except ExprError as exc:
        return NumericSolution(ok=False, note=str(exc))

    variables = {str(k): float(v) for k, v in dict(variables or {}).items()}
    allowed = set(state) | set(variables)
    try:
        rhs_fns = [compile_expression(expr, allowed) for expr in rhs]
    except ExprError as exc:
        return NumericSolution(ok=False, note=f"Bad RHS expression: {exc}")

    def f(t: float, y: np.ndarray) -> list[float]:
        params = dict(variables)
        for name, value in zip(state, y, strict=True):
            params[name] = float(value)
        derivs: list[float] = []
        for fn in rhs_fns:
            with np.errstate(all="ignore"):
                derivs.append(float(np.asarray(fn(float(t), params)).reshape(-1)[0]))
        return derivs

    n = max(2, min(int(max_points), MAX_POINTS))
    t_eval = np.linspace(t0, t1, n)
    try:
        sol = solve_ivp(
            f, (t0, t1), initial, t_eval=t_eval, method="RK45",
            rtol=1e-6, atol=1e-9, max_step=(t1 - t0) / 50.0,
        )
    except Exception as exc:  # noqa: BLE001 — integration must never crash the app
        return NumericSolution(ok=False, note=f"Integration failed: {exc}")

    if not sol.success or not np.all(np.isfinite(sol.y)):
        return NumericSolution(
            state=_states(sol, state), t=sol.t.tolist(), observe=observe, ok=False,
            note=sol.message or "Integration diverged (non-finite state).",
        ) if sol.t.size else NumericSolution(ok=False, note=sol.message or "Integration failed.")

    return NumericSolution(
        t=sol.t.tolist(),
        states=_states(sol, state),
        observe=observe,
        method="RK45",
        ok=True,
        note=f"Integrated {len(state)} state var(s) over [{t0:g}, {t1:g}] at {sol.t.size} points.",
    )


def _states(sol: Any, state: list[str]) -> dict[str, list[float]]:
    return {name: sol.y[i].tolist() for i, name in enumerate(state)}


def _validate(spec: Any) -> tuple[list[str], list[str], list[float], tuple[float, float], str]:
    if not isinstance(spec, dict):
        raise ExprError("numeric_spec must be an object.")
    state = spec.get("state")
    rhs = spec.get("rhs")
    initial = spec.get("initial")
    t_range = spec.get("t_range")

    if not (isinstance(state, list) and 1 <= len(state) <= MAX_STATE_VARS):
        raise ExprError(f"state must be a list of 1..{MAX_STATE_VARS} names.")
    state = [str(s) for s in state]
    if len({s for s in state}) != len(state):
        raise ExprError("state names must be unique.")

    if not (isinstance(rhs, list) and len(rhs) == len(state) and all(isinstance(e, str) for e in rhs)):
        raise ExprError("rhs must be a list of expressions, one per state variable.")

    if not (isinstance(initial, list) and len(initial) == len(state)):
        raise ExprError("initial must give one value per state variable.")
    try:
        initial = [float(v) for v in initial]
    except (TypeError, ValueError) as exc:
        raise ExprError("initial values must be numbers.") from exc
    if not all(math.isfinite(v) for v in initial):
        raise ExprError("initial values must be finite.")

    if not (isinstance(t_range, (list, tuple)) and len(t_range) == 2):
        raise ExprError("t_range must be a [t0, t1] pair.")
    t0, t1 = float(t_range[0]), float(t_range[1])
    if not (math.isfinite(t0) and math.isfinite(t1)) or t1 <= t0:
        raise ExprError("t_range must be finite with t0 < t1.")
    if t1 - t0 > MAX_T_SPAN:
        t1 = t0 + MAX_T_SPAN

    observe = str(spec.get("observe") or state[0])
    if observe not in state:
        observe = state[0]
    return state, rhs, initial, (t0, t1), observe


def fallback_numeric_spec() -> dict[str, Any]:
    """Damped harmonic oscillator matching llm.DEFAULT_VARIABLES.

    x'' + 2*damping*x' + (stiffness/mass)*x = 0, released from rest at x=1.
    Underdamped for the defaults (damping=0.15, stiffness=1, mass=1).
    """
    return {
        "state": ["x", "v"],
        "rhs": ["v", "-(stiffness/mass)*x - (2*damping)*v"],
        "initial": [1.0, 0.0],
        "t_range": [0.0, 20.0],
        "observe": "x",
    }
