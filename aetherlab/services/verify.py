"""Physics verifier — sanity-check a result against its own numerics.

Most tools emit plausible-looking physics; AetherLab checks itself. Given a
solver result with an ODE ground truth, this runs concrete, numeric checks:
the trajectory stays finite and bounded, a dissipative system loses energy while
a conservative one conserves it, and (when applicable) a small-angle pendulum's
measured period matches 2*pi*sqrt(L/g). Results are a structured report the UI
and the research PDF surface; nothing here raises.

numpy only — no symbolic-units dependency.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from aetherlab.core.models import NumericSolution

_DAMPING_NAMES = ("damping", "friction", "gamma", "c", "resistance", "drag")


@dataclass
class Check:
    name: str
    passed: bool
    detail: str
    severity: str = "info"  # "info" | "warning" | "error"


@dataclass
class VerificationReport:
    checks: list[Check] = field(default_factory=list)
    ok: bool = True
    summary: str = ""

    def add(self, name: str, passed: bool, detail: str, severity: str = "warning") -> None:
        self.checks.append(Check(name, passed, detail, severity if not passed else "info"))
        if not passed and severity == "error":
            self.ok = False

    def as_lines(self) -> list[str]:
        mark = {True: "PASS", False: "FAIL"}
        return [f"[{mark[c.passed]}] {c.name}: {c.detail}" for c in self.checks]


def verify_solution(solver: Any, request: Any = None) -> VerificationReport:
    """Verify a solver result against its integrated ODE. Never raises."""
    report = VerificationReport()
    spec = getattr(solver, "numeric_spec", None)
    variables = {str(k): float(v) for k, v in getattr(solver, "variables", {}).items()}
    if not isinstance(spec, dict):
        report.add("model", True, "No ODE ground truth to verify (analytic/conceptual result).", "info")
        report.summary = "No numeric model to verify."
        return report

    try:
        from aetherlab.services.numeric import solve_numeric

        sol = solve_numeric(spec, variables, max_points=600)
    except Exception as exc:  # noqa: BLE001
        report.add("integrate", False, f"Could not integrate the model: {exc}", "error")
        report.summary = "Verification could not run."
        return report

    if not sol.ok or len(sol.t) < 3:
        report.add("integrate", False, sol.note or "Integration failed.", "error")
        report.summary = "Verification could not run."
        return report

    _check_finite(sol, report)
    _check_bounded(sol, variables, report)
    _check_energy(sol, spec, variables, report)
    _check_pendulum_period(sol, solver, request, variables, report)

    passed = sum(1 for c in report.checks if c.passed)
    report.summary = f"{passed}/{len(report.checks)} physics checks passed."
    return report


def physics_expectations(solver: Any, request: Any = None) -> list[str]:
    """Facts from the solver/verifier that a visual critic may check if visible.

    These describe the numerical model and its observed checks; they do not
    certify the solver's written derivation or facts absent from sampled frames.
    """
    facts: list[str] = []
    variables = getattr(solver, "variables", {}) or {}
    if variables:
        rendered_items = []
        for name, value in sorted(variables.items())[:8]:
            try:
                rendered_items.append(f"{name}={float(value):.5g}")
            except (TypeError, ValueError, OverflowError):
                continue
        rendered = ", ".join(rendered_items)
    else:
        rendered = ""
    if rendered:
        facts.append(f"Solver-provided parameters: {rendered}.")
    equations = getattr(solver, "key_equations", []) or []
    if equations:
        facts.append("Governing equation(s): " + "; ".join(str(eq) for eq in equations[:3]))
    if isinstance(getattr(solver, "numeric_spec", None), dict):
        try:
            report = verify_solution(solver, request)
            facts.append(f"Numerical model cross-check: {report.summary}")
            facts.extend(report.as_lines()[:6])
        except Exception as exc:  # noqa: BLE001 - critic context is best-effort
            facts.append(f"Numerical model cross-check unavailable: {type(exc).__name__}.")
    else:
        facts.append("No deterministic ODE ground truth is available for this result.")
    return facts[:10]


def _state_array(sol: NumericSolution, name: str) -> np.ndarray:
    return np.asarray(sol.states.get(name, []), dtype=float)


def _check_finite(sol: NumericSolution, report: VerificationReport) -> None:
    all_vals = np.concatenate([_state_array(sol, k) for k in sol.states]) if sol.states else np.array([])
    finite = bool(all_vals.size) and bool(np.all(np.isfinite(all_vals)))
    report.add(
        "finite", finite,
        "Trajectory is finite over the whole interval." if finite
        else "Trajectory contains non-finite values (blow-up).",
        severity="error",
    )


def _check_bounded(sol: NumericSolution, variables: dict[str, float], report: VerificationReport) -> None:
    x = _state_array(sol, sol.observe or next(iter(sol.states), ""))
    if x.size < 4:
        return
    head = float(np.max(np.abs(x[: max(2, x.size // 5)])))
    tail = float(np.max(np.abs(x[-max(2, x.size // 5):])))
    damping = _damping_value(variables)
    if damping > 1e-9:
        ok = tail <= head * 1.05 + 1e-9
        report.add(
            "boundedness", ok,
            f"Dissipative system: late amplitude {tail:.3g} <= early {head:.3g}." if ok
            else f"Damped system but amplitude grew ({head:.3g} -> {tail:.3g}) — unphysical.",
            severity="warning",
        )
    else:
        ok = tail <= head * 2.0 + 1e-9
        report.add(
            "boundedness", ok,
            f"Conservative system stays bounded (|x|<= {max(head, tail):.3g})." if ok
            else f"Undamped system amplitude grew markedly ({head:.3g} -> {tail:.3g}).",
            severity="warning",
        )


def _check_energy(
    sol: NumericSolution, spec: dict, variables: dict[str, float], report: VerificationReport
) -> None:
    state = [str(s) for s in spec.get("state", [])]
    if len(state) != 2 or "stiffness" not in variables or "mass" not in variables:
        return  # energy check only defined for the canonical 2nd-order oscillator form
    x = _state_array(sol, state[0])
    v = _state_array(sol, state[1])
    if x.size != v.size or x.size < 3 or variables["mass"] == 0:
        return
    omega2 = variables["stiffness"] / variables["mass"]
    energy = 0.5 * v * v + 0.5 * omega2 * x * x
    e0, e_end = float(energy[0]), float(energy[-1])
    if e0 <= 1e-12:
        return
    damping = _damping_value(variables)
    if damping > 1e-9:
        ok = e_end <= e0 * 1.02
        report.add(
            "energy", ok,
            f"Damped: energy decays {e0:.3g} -> {e_end:.3g}." if ok
            else f"Damped but energy grew {e0:.3g} -> {e_end:.3g} — sign error?",
            severity="warning",
        )
    else:
        drift = float(np.max(np.abs(energy - e0)) / e0)
        ok = drift < 0.05
        report.add(
            "energy", ok,
            f"Conservative: energy drift {drift * 100:.2f}% (< 5%)." if ok
            else f"Undamped but energy drifts {drift * 100:.1f}% — not conserved.",
            severity="warning",
        )


def _check_pendulum_period(
    sol: NumericSolution, solver: Any, request: Any, variables: dict[str, float], report: VerificationReport
) -> None:
    text = " ".join([
        " ".join(getattr(solver, "keywords", []) or []),
        getattr(request, "prompt", "") if request is not None else "",
        getattr(solver, "summary", "") or "",
    ]).lower()
    if "pendulum" not in text:
        return
    g = variables.get("gravity", variables.get("g"))
    length = variables.get("length", variables.get("l"))
    if not g or not length or g <= 0 or length <= 0:
        return
    x = _state_array(sol, sol.observe or next(iter(sol.states), ""))
    t = np.asarray(sol.t, dtype=float)
    measured = _period_from_zero_crossings(t, x)
    if measured is None:
        return
    expected = 2.0 * math.pi * math.sqrt(length / g)
    rel = abs(measured - expected) / expected
    ok = rel < 0.15
    report.add(
        "pendulum-period", ok,
        f"Measured period {measured:.3g}s vs small-angle 2*pi*sqrt(L/g)={expected:.3g}s ({rel*100:.1f}% off)."
        if ok else
        f"Period {measured:.3g}s deviates {rel*100:.0f}% from 2*pi*sqrt(L/g)={expected:.3g}s.",
        severity="warning",
    )


def _damping_value(variables: dict[str, float]) -> float:
    for name in _DAMPING_NAMES:
        if name in variables:
            return abs(float(variables[name]))
    return 0.0


def _period_from_zero_crossings(t: np.ndarray, x: np.ndarray) -> float | None:
    if x.size < 4:
        return None
    signs = np.sign(x - np.mean(x))
    crossings = np.where(np.diff(signs) != 0)[0]
    if crossings.size < 3:
        return None
    times = t[crossings]
    # Two zero-crossings per period.
    half_periods = np.diff(times)
    if half_periods.size == 0:
        return None
    return float(2.0 * np.mean(half_periods))
