"""Safe compilation of solver-provided plot expressions.

The LLM solver may attach a `plot` payload (see the system prompt in
services/llm.py) describing the curve that captures its result. This module
turns those expression strings into fast numpy-vectorized callables without
ever exposing `eval` to model output: expressions are parsed with `ast`,
walked against a strict whitelist, and compiled only if every node passes.

Consumed by services/llm.py (fallback payload) and ui/live_canvas.py
(canvas state construction).
"""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np


class ExprError(ValueError):
    """Raised when a solver expression is invalid or unsafe."""


MAX_EXPR_CHARS = 512
MAX_AST_NODES = 200
MAX_T_SPAN = 1e4

# numpy callables the expressions may use
_FUNCTIONS: dict[str, Any] = {
    "sin": np.sin,
    "cos": np.cos,
    "tan": np.tan,
    "sinh": np.sinh,
    "cosh": np.cosh,
    "tanh": np.tanh,
    "arcsin": np.arcsin,
    "arccos": np.arccos,
    "arctan": np.arctan,
    "exp": np.exp,
    "log": np.log,
    "log10": np.log10,
    "sqrt": np.sqrt,
    "abs": np.abs,
    "sign": np.sign,
}

_CONSTANTS: dict[str, float] = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}

_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv)
_ALLOWED_UNARYOPS = (ast.UAdd, ast.USub)


@dataclass(frozen=True)
class CompiledPlot:
    """A validated, compiled plot ready for the canvas."""

    kind: str
    x_fn: Callable[[np.ndarray, dict[str, float]], np.ndarray]
    y_fn: Callable[[np.ndarray, dict[str, float]], np.ndarray]
    t_range: tuple[float, float]
    x_range: tuple[float, float] | None
    y_range: tuple[float, float] | None
    x_label: str = "x"
    y_label: str = "y"
    param_names: tuple[str, ...] = field(default_factory=tuple)


class _IntToFloat(ast.NodeTransformer):
    """Convert int literals to floats so 9**9**9 overflows to inf instead of
    materializing a multi-gigabyte Python int."""

    def visit_Constant(self, node: ast.Constant) -> ast.Constant:  # noqa: N802
        if isinstance(node.value, int) and not isinstance(node.value, bool):
            return ast.copy_location(ast.Constant(float(node.value)), node)
        return node


def _validate(tree: ast.Expression, allowed_names: set[str]) -> None:
    count = 0
    for node in ast.walk(tree):
        count += 1
        if count > MAX_AST_NODES:
            raise ExprError(f"Expression too complex (> {MAX_AST_NODES} AST nodes).")

        if isinstance(node, ast.Expression):
            continue
        if isinstance(node, ast.BinOp):
            if not isinstance(node.op, _ALLOWED_BINOPS):
                raise ExprError(f"Operator {type(node.op).__name__} is not allowed.")
            continue
        if isinstance(node, _ALLOWED_BINOPS + _ALLOWED_UNARYOPS):
            continue
        if isinstance(node, ast.UnaryOp):
            if not isinstance(node.op, _ALLOWED_UNARYOPS):
                raise ExprError(f"Unary {type(node.op).__name__} is not allowed.")
            continue
        if isinstance(node, ast.Call):
            if node.keywords or any(isinstance(a, ast.Starred) for a in node.args):
                raise ExprError("Keyword/starred arguments are not allowed.")
            if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCTIONS:
                name = getattr(node.func, "id", type(node.func).__name__)
                raise ExprError(f"Function {name!r} is not allowed.")
            continue
        if isinstance(node, ast.Name):
            if not isinstance(node.ctx, ast.Load):
                raise ExprError("Assignment inside expressions is not allowed.")
            if (
                node.id not in allowed_names
                and node.id not in _FUNCTIONS
                and node.id not in _CONSTANTS
            ):
                raise ExprError(f"Unknown name {node.id!r}.")
            continue
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)) or isinstance(node.value, bool):
                raise ExprError("Only numeric literals are allowed.")
            continue
        if isinstance(node, ast.Load):
            continue
        raise ExprError(f"Syntax {type(node).__name__} is not allowed.")


def compile_expression(
    expr: str, param_names: set[str]
) -> Callable[[np.ndarray, dict[str, float]], np.ndarray]:
    """Compile a whitelisted math expression into `fn(t_array, params) -> array`.

    Free names: `t`, the given parameter names, and pi/e/tau. Raises ExprError
    for anything outside the whitelist.
    """
    if not isinstance(expr, str) or not expr.strip():
        raise ExprError("Expression is empty.")
    if len(expr) > MAX_EXPR_CHARS:
        raise ExprError(f"Expression longer than {MAX_EXPR_CHARS} chars.")

    # Common LLM slip: caret for exponentiation. `^` (BitXor) is rejected by
    # the whitelist, so normalizing first is strictly permissive.
    expr = expr.replace("^", "**")

    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ExprError(f"Cannot parse expression: {exc}") from exc

    allowed = {"t"} | set(param_names)
    _validate(tree, allowed)

    tree = ast.fix_missing_locations(_IntToFloat().visit(tree))
    code = compile(tree, "<aetherlab-plot-expr>", "eval")

    def fn(t: np.ndarray, params: dict[str, float]) -> np.ndarray:
        namespace: dict[str, Any] = dict(_FUNCTIONS)
        namespace.update(_CONSTANTS)
        namespace.update({k: float(v) for k, v in params.items()})
        namespace["t"] = t
        try:
            with np.errstate(all="ignore"):
                result = eval(code, {"__builtins__": {}}, namespace)  # noqa: S307
        except OverflowError:
            # Pure-float pow raises instead of returning inf (e.g. 9**9**9);
            # treat it like numpy would — the canvas filters non-finite values.
            result = math.inf
        except ZeroDivisionError:
            result = math.nan
        # Broadcast constants (e.g. "2*pi") to the sample grid's shape.
        return np.broadcast_to(np.asarray(result, dtype=float), np.shape(t)).copy()

    return fn


def _pair(value: Any, what: str) -> tuple[float, float]:
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 2
        or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value)
    ):
        raise ExprError(f"{what} must be a [lo, hi] number pair.")
    lo, hi = float(value[0]), float(value[1])
    if not (math.isfinite(lo) and math.isfinite(hi)) or lo >= hi:
        raise ExprError(f"{what} must be finite with lo < hi.")
    return lo, hi


def compile_plot(payload: Any, variables: dict[str, float]) -> CompiledPlot:
    """Validate a solver `plot` payload and compile its expressions."""
    if not isinstance(payload, dict):
        raise ExprError("plot payload must be an object.")

    kind = payload.get("kind", "explicit")
    if kind not in ("explicit", "parametric"):
        raise ExprError(f"Unknown plot kind {kind!r}.")

    t0, t1 = _pair(payload.get("t_range"), "t_range")
    if t1 - t0 > MAX_T_SPAN:
        t1 = t0 + MAX_T_SPAN

    params = set(variables.keys())

    y_expr = payload.get("y")
    y_fn = compile_expression(y_expr, params)

    if kind == "explicit":
        x_fn = compile_expression("t", params)
    else:
        x_fn = compile_expression(payload.get("x") or "t", params)

    x_range = _pair(payload["x_range"], "x_range") if payload.get("x_range") else None
    y_range = _pair(payload["y_range"], "y_range") if payload.get("y_range") else None

    return CompiledPlot(
        kind=kind,
        x_fn=x_fn,
        y_fn=y_fn,
        t_range=(t0, t1),
        x_range=x_range,
        y_range=y_range,
        x_label=str(payload.get("x_label") or ("t" if kind == "explicit" else "x")),
        y_label=str(payload.get("y_label") or "y"),
        param_names=tuple(sorted(params)),
    )


def fallback_plot_payload() -> dict[str, Any]:
    """Deterministic damped-oscillator plot matching llm.DEFAULT_VARIABLES."""
    return {
        "kind": "explicit",
        "x": "t",
        "y": "exp(-damping*t) * sin(stiffness*t*2) / sqrt(mass)",
        "t_range": [0.0, 10.0],
        "y_range": [-1.2, 1.2],
        "x_label": "t (s)",
        "y_label": "x(t)",
    }
