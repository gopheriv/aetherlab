"""Conservative checks for structured algebra steps and ODE dimensions.

These checks never infer correctness from prose or LaTeX. Unsupported input is
reported as ``not_checked`` so the UI cannot accidentally label a derivation as
verified merely because a numeric model integrated successfully.
"""

from __future__ import annotations

import ast
import math
from typing import Any


class _UnsupportedUnitExpressionError(ValueError):
    """The expression is outside the dimensional checker's supported subset."""


class _UnitDimensionalityError(ValueError):
    """An expression explicitly applies a dimensional quantity incorrectly."""


def verify_derivation_records(solver: Any) -> dict[str, Any]:
    records = getattr(solver, "derivation_records", None) or []
    steps = list(getattr(solver, "derivation_steps", []) or [])
    if not records:
        return {
            "status": "not_checked",
            "checked": 0,
            "failed": 0,
            "not_checked": len(steps),
            "total": len(steps),
            "items": [],
            "message": "No structured algebra records were supplied; written steps remain unverified.",
        }
    try:
        import sympy as sp
    except Exception:  # noqa: BLE001 - verification is optional
        return {
            "status": "not_checked", "checked": 0, "failed": 0,
            "not_checked": len(records), "total": len(records), "items": [],
            "message": "SymPy is unavailable; algebra records were not checked.",
        }

    variable_values = getattr(solver, "variables", {}) or {}
    variables = set(variable_values)
    checked = failed = unchecked = 0
    substitution_checked = substitution_failed = 0
    items: list[dict[str, str]] = []
    for index, record in enumerate(records, 1):
        if not isinstance(record, dict):
            unchecked += 1
            items.append({
                "index": str(index),
                "claim": "",
                "source_ref": "",
                "status": "not_checked",
                "detail": "The structured derivation record is not an object.",
                "substitution_status": "not_checked",
                "substitution_detail": "Numeric substitution was not checked.",
            })
            continue
        before = str(record.get("from_expression", "")).strip()
        after = str(record.get("to_expression", "")).strip()
        provenance = str(record.get("source_ref", "")).strip()
        item = {
            "index": str(index),
            "claim": str(record.get("claim", "")).strip(),
            "source_ref": provenance,
        }
        try:
            step_index = int(record.get("step_index"))
            if 1 <= step_index <= len(steps):
                item["step_index"] = str(step_index)
        except (TypeError, ValueError, OverflowError):
            pass
        if not before or not after:
            unchecked += 1
            item.update(
                status="not_checked",
                detail="The step has no before/after expressions.",
                substitution_status="not_checked",
                substitution_detail="Numeric substitution was not checked.",
            )
            items.append(item)
            continue
        try:
            left = _parse_sympy(before, sp, variables)
            right = _parse_sympy(after, sp, variables)
            passed = _equivalent(left, right, sp, variable_values)
            substitution = _check_substitution(left, right, variable_values, sp)
            substitution_checked += int(substitution["status"] in {"passed", "failed"})
            substitution_failed += int(substitution["status"] == "failed")
            if passed is None:
                unchecked += 1
                item.update(
                    status="not_checked",
                    detail=(
                        "Equation forms differ by a symbolic factor that may be zero; "
                        "the solver supplied no nonzero value or assumption for it."
                    ),
                    substitution_status=substitution["status"],
                    substitution_detail=substitution["detail"],
                )
            else:
                checked += 1
                failed += int(not passed)
                item.update(
                    status="passed" if passed else "failed",
                    detail="Expressions are algebraically equivalent." if passed
                    else "Expressions are not algebraically equivalent.",
                    substitution_status=substitution["status"],
                    substitution_detail=substitution["detail"],
                )
        except (ValueError, SyntaxError, TypeError, ZeroDivisionError) as exc:
            unchecked += 1
            item.update(
                status="not_checked", detail=f"Unsupported expression: {exc}",
                substitution_status="not_checked",
                substitution_detail="Numeric substitution was not checked.",
            )
        items.append(item)

    status = "failed" if failed else ("not_checked" if unchecked or not checked else "passed")
    if failed:
        message = f"{failed} of {checked} checked structured algebra step(s) failed."
        if unchecked:
            message += f" {unchecked} additional step(s) were not checked."
    elif unchecked:
        message = f"{checked} structured algebra step(s) passed; {unchecked} were not checked."
    elif checked:
        message = f"{checked} structured algebra step(s) passed."
    else:
        message = "No supported structured algebra step was available to check."
    return {
        "status": status,
        "checked": checked,
        "failed": failed,
        "not_checked": unchecked,
        "total": len(records),
        "substitution_checked": substitution_checked,
        "substitution_failed": substitution_failed,
        "items": items,
        "message": message,
    }


def verify_ode_units(solver: Any) -> dict[str, Any]:
    spec = getattr(solver, "numeric_spec", None)
    units = getattr(solver, "variable_units", None) or {}
    if not isinstance(spec, dict):
        return _not_checked_units("No deterministic ODE is available.")
    state = spec.get("state")
    rhs = spec.get("rhs")
    names = set(getattr(solver, "variables", {}) or {})
    if not isinstance(state, list) or not isinstance(rhs, list) or len(state) != len(rhs):
        return _not_checked_units("The ODE state and right-hand sides are incomplete.")
    if not isinstance(units, dict):
        return _not_checked_units("Variable units were not supplied.")
    required = names | {str(name) for name in state}
    missing = sorted(name for name in required if not str(units.get(name, "")).strip())
    if missing:
        return _not_checked_units("Units are missing for: " + ", ".join(missing[:8]) + ".")
    try:
        import pint
    except Exception:  # noqa: BLE001 - dimensional checking is optional
        return _not_checked_units("Pint is unavailable; ODE dimensions were not checked.")

    try:
        registry = pint.UnitRegistry()
        values = getattr(solver, "variables", {}) or {}
        state_initial = spec.get("initial") or []
        env = {
            str(name): registry.Quantity(float(values.get(name, 1.0)), str(unit))
            for name, unit in units.items()
            if str(unit).strip()
        }
        for index, name in enumerate(state):
            initial = state_initial[index] if index < len(state_initial) else 1.0
            env[str(name)] = registry.Quantity(float(initial), str(units[str(name)]))
        env["t"] = registry.Quantity(1.0, "second")
        outcomes = []
        for index, (name, expression) in enumerate(zip(state, rhs, strict=True)):
            actual = _eval_quantity(str(expression), env, registry)
            expected = registry.Quantity(1.0, str(units[str(name)])) / registry.Quantity(1.0, "second")
            passed = actual.dimensionality == expected.dimensionality
            outcomes.append({
                "state": str(name),
                "rhs": str(expression),
                "status": "passed" if passed else "failed",
                "actual": str(actual.dimensionality),
                "expected": str(expected.dimensionality),
            })
        failures = sum(item["status"] == "failed" for item in outcomes)
        status = "failed" if failures else "passed"
        message = (
            f"{failures} of {len(outcomes)} ODE right-hand side(s) have inconsistent units."
            if failures else f"Units are dimensionally consistent for {len(outcomes)} ODE state(s)."
        )
        return {"status": status, "checked": len(outcomes), "items": outcomes, "message": message}
    except (_UnsupportedUnitExpressionError, SyntaxError) as exc:
        return {
            "status": "not_checked", "checked": 0, "items": [],
            "message": f"Unsupported ODE expression; units were not checked: {exc}",
        }
    except Exception as exc:  # noqa: BLE001 - malformed unit metadata must fail soft
        return {
            "status": "failed", "checked": 0, "items": [],
            "message": f"Could not validate declared units: {type(exc).__name__}: {exc}",
        }


def _not_checked_units(message: str) -> dict[str, Any]:
    return {"status": "not_checked", "checked": 0, "items": [], "message": message}


def _parse_sympy(text: str, sp: Any, variables: set[str]):
    """Parse arithmetic with a tiny AST allowlist; never call eval/parse_expr."""
    names = {name: sp.Symbol(name) for name in variables}
    if text.count("=") == 1:
        lhs, rhs = text.split("=", 1)
        return (
            _sympy_node(ast.parse(lhs.strip().replace("^", "**"), mode="eval").body, sp, names),
            _sympy_node(ast.parse(rhs.strip().replace("^", "**"), mode="eval").body, sp, names),
        )
    return _sympy_node(ast.parse(text.strip().replace("^", "**"), mode="eval").body, sp, names)


def _sympy_node(node: ast.AST, sp: Any, names: dict[str, Any]):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return sp.Rational(str(node.value))
    if isinstance(node, ast.Name):
        if node.id not in names:
            names[node.id] = sp.Symbol(node.id)
        return names[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _sympy_node(node.operand, sp, names)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left, right = _sympy_node(node.left, sp, names), _sympy_node(node.right, sp, names)
        operations = {
            ast.Add: lambda: left + right,
            ast.Sub: lambda: left - right,
            ast.Mult: lambda: left * right,
            ast.Div: lambda: left / right,
            ast.Pow: lambda: left ** right,
        }
        operation = operations.get(type(node.op))
        if operation:
            return operation()
    raise ValueError("only numeric constants, symbols, and + - * / ** are supported")


def _equivalent(left: Any, right: Any, sp: Any, known_values: Any = None) -> bool | None:
    if not isinstance(left, tuple) and not isinstance(right, tuple):
        return sp.simplify(left - right) == 0
    if not isinstance(left, tuple) or not isinstance(right, tuple):
        return False
    left_eq = sp.simplify(left[0] - left[1])
    right_eq = sp.simplify(right[0] - right[1])
    delta = sp.simplify(left_eq - right_eq)
    if delta == 0:
        return True
    ratio = sp.simplify(left_eq / right_eq) if right_eq != 0 else None
    return ratio is not None and _is_nonzero_scaling(ratio, sp, known_values)


def _is_nonzero_scaling(ratio: Any, sp: Any, known_values: Any = None) -> bool | None:
    """True when two equation forms differ by a constant or a monomial factor.

    Rearranging ``F = m*a`` into ``a = F/m`` divides both sides by ``m``; the
    residuals then differ by the factor ``-m``. A monomial factor is safe only
    when the solver supplied a finite, nonzero value for each free symbol (or
    SymPy can prove it nonzero from symbol assumptions). Otherwise the step is
    unverified: the factor might be zero and introduce solutions. Multiplying
    by a sum such as ``(x - y)`` can introduce solutions even when its terms
    are individually nonzero, so that remains not equivalent.
    """
    if ratio == 0 or ratio.has(sp.zoo, sp.nan, sp.oo, -sp.oo):
        return False
    if ratio.is_number:
        return ratio.is_zero is False
    numerator, denominator = sp.fraction(sp.together(ratio))
    symbols = sorted(ratio.free_symbols, key=lambda symbol: symbol.name)
    try:
        if not all(sp.Poly(part, *symbols).is_monomial for part in (numerator, denominator)):
            return False
    except sp.PolynomialError:
        return False
    supplied = known_values if isinstance(known_values, dict) else {}
    unknown = False
    for symbol in symbols:
        if symbol.is_nonzero is True:
            continue
        value = supplied.get(symbol.name)
        try:
            numeric = float(value)
        except (TypeError, ValueError, OverflowError):
            unknown = True
            continue
        if not math.isfinite(numeric):
            unknown = True
        elif numeric == 0:
            return False
    return None if unknown else True


def _check_substitution(
    left: Any, right: Any, values: Any, sp: Any,
) -> dict[str, str]:
    """Check this step at supplied solver values without overriding the proof.

    For equation forms, both sides must be satisfied at the supplied point to
    count as a successful sample. If neither is satisfied, the point cannot
    validate the transformation and remains ``not_checked``.
    """
    if not isinstance(values, dict):
        return {"status": "not_checked", "detail": "No numeric solver values were supplied."}
    if isinstance(left, tuple) != isinstance(right, tuple):
        return {
            "status": "failed",
            "detail": "Equation and expression forms differ at substitution.",
        }
    expressions = [*left, *right] if isinstance(left, tuple) else [left, right]
    symbols = set().union(*(expression.free_symbols for expression in expressions))
    numeric_values: dict[str, Any] = {}
    for name, value in values.items():
        if isinstance(value, bool):
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError, OverflowError):
            continue
        if math.isfinite(numeric):
            try:
                numeric_values[str(name)] = sp.Rational(str(value))
            except (TypeError, ValueError, ZeroDivisionError):
                continue
    missing = sorted(symbol.name for symbol in symbols if symbol.name not in numeric_values)
    if missing:
        return {
            "status": "not_checked",
            "detail": "Numeric substitution lacks values for: " + ", ".join(missing[:8]) + ".",
        }
    substitutions = {symbol: numeric_values[symbol.name] for symbol in symbols}
    try:
        if isinstance(left, tuple) or isinstance(right, tuple):
            if not isinstance(left, tuple) or not isinstance(right, tuple):
                return {
                    "status": "failed",
                    "detail": "Equation and expression forms differ at substitution.",
                }
            before_residual = sp.simplify((left[0] - left[1]).subs(substitutions))
            after_residual = sp.simplify((right[0] - right[1]).subs(substitutions))
            before_holds = _numeric_zero(before_residual, sp)
            after_holds = _numeric_zero(after_residual, sp)
            if before_holds and after_holds:
                detail = "Both equation forms hold at the supplied solver values."
                status = "passed"
            elif before_holds != after_holds:
                detail = "Only one equation form holds at the supplied solver values."
                status = "failed"
            else:
                detail = "The supplied solver values satisfy neither equation form."
                status = "not_checked"
            return {"status": status, "detail": detail}
        difference = sp.simplify((left - right).subs(substitutions))
        if _numeric_zero(difference, sp):
            return {"status": "passed", "detail": "Expressions agree at the supplied solver values."}
        return {"status": "failed", "detail": "Expressions differ at the supplied solver values."}
    except (ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
        return {
            "status": "not_checked",
            "detail": f"Numeric substitution could not be evaluated: {exc}",
        }


def _numeric_zero(value: Any, sp: Any) -> bool:
    evaluated = sp.N(value)
    if not getattr(evaluated, "is_number", False) or evaluated.is_finite is False:
        raise ValueError("substitution did not produce a finite numeric value")
    return math.isclose(float(evaluated), 0.0, rel_tol=1e-9, abs_tol=1e-9)


def _eval_quantity(text: str, env: dict[str, Any], registry: Any):
    tree = ast.parse(text, mode="eval").body
    functions = {
        "sin": __import__("numpy").sin,
        "cos": __import__("numpy").cos,
        "tan": __import__("numpy").tan,
        "exp": __import__("numpy").exp,
        "log": __import__("numpy").log,
        "sqrt": __import__("numpy").sqrt,
        "abs": abs,
    }

    def visit(node: ast.AST):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return registry.Quantity(float(node.value), "dimensionless")
        if isinstance(node, ast.Name):
            if node.id in {"pi", "e"}:
                return registry.Quantity(math.pi if node.id == "pi" else math.e, "dimensionless")
            if node.id in env:
                return env[node.id]
            raise _UnsupportedUnitExpressionError(f"unknown symbol {node.id}")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Pow):
                if right.dimensionality != registry.dimensionless.dimensionality:
                    raise _UnitDimensionalityError("exponent must be dimensionless")
                return left ** float(right.magnitude)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in functions and len(node.args) == 1:
            return functions[node.func.id](visit(node.args[0]))
        raise _UnsupportedUnitExpressionError(
            "only arithmetic and supported math functions are checked"
        )

    return visit(tree)
