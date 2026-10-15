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
MAX_CURVES = 6
MAX_POINTS = 8
MAX_LABEL_CHARS = 40

_ALLOWED_STYLES = ("solid", "dashed")
_ALLOWED_ROLES = ("primary", "secondary", "reference")

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
class CompiledCurve:
    """One compiled curve of a (possibly multi-curve) plot payload."""

    name: str
    x_fn: Callable[[np.ndarray, dict[str, float]], np.ndarray]
    y_fn: Callable[[np.ndarray, dict[str, float]], np.ndarray]
    style: str = "solid"      # solid | dashed
    role: str = "primary"     # primary | secondary | reference


@dataclass(frozen=True)
class CompiledPlot:
    """A validated, compiled plot ready for the canvas.

    `x_fn`/`y_fn` remain the PRIMARY curve's callables for backward
    compatibility; `curves` carries the full (ordered) set. `fill` is an
    optional (upper_fn, lower_fn) pair for translucent region shading, and
    `points` is an optional tuple of (t, label) markers.
    """

    kind: str
    x_fn: Callable[[np.ndarray, dict[str, float]], np.ndarray]
    y_fn: Callable[[np.ndarray, dict[str, float]], np.ndarray]
    t_range: tuple[float, float]
    x_range: tuple[float, float] | None
    y_range: tuple[float, float] | None
    x_label: str = "x"
    y_label: str = "y"
    param_names: tuple[str, ...] = field(default_factory=tuple)
    curves: tuple[CompiledCurve, ...] = field(default_factory=tuple)
    fill: tuple[Callable, Callable] | None = None
    points: tuple[tuple[float, str], ...] = field(default_factory=tuple)


class _IntToFloat(ast.NodeTransformer):
    """Convert int literals to floats so 9**9**9 overflows to inf instead of
    materializing a multi-gigabyte Python int."""

    def visit_Constant(self, node: ast.Constant) -> ast.Constant:  # noqa: N802
        if isinstance(node.value, int) and not isinstance(node.value, bool):
            try:
                value = float(node.value)
            except OverflowError as exc:
                raise ExprError("Numeric literal exceeds the supported float range.") from exc
            return ast.copy_location(ast.Constant(value), node)
        return node


def _validate(tree: ast.Expression, allowed_names: set[str]) -> None:
    called_names = {id(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
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
            # NumPy accepts a second positional `out` array. A mathematical
            # expression must never acquire that write capability.
            if len(node.args) != 1:
                raise ExprError(f"Function {node.func.id!r} requires exactly one argument.")
            continue
        if isinstance(node, ast.Name):
            if not isinstance(node.ctx, ast.Load):
                raise ExprError("Assignment inside expressions is not allowed.")
            if node.id in _FUNCTIONS and id(node) not in called_names:
                raise ExprError(f"Function {node.id!r} must be called with one argument.")
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
    used_parameters = frozenset(node.id for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id in param_names
        and node.id not in _FUNCTIONS and node.id != "t")

    tree = ast.fix_missing_locations(_IntToFloat().visit(tree))
    code = compile(tree, "<aetherlab-plot-expr>", "eval")

    def fn(t: np.ndarray, params: dict[str, float]) -> np.ndarray:
        namespace: dict[str, Any] = dict(_FUNCTIONS)
        namespace.update(_CONSTANTS)
        # Bind only declared parameters actually used by this expression.
        # Extraneous fields cannot replace math functions or constants.
        for name in used_parameters:
            try:
                namespace[name] = float(params[name])
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise ExprError(f"Missing or invalid numeric parameter {name!r}.") from exc
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
        except (TypeError, ValueError, NameError) as exc:
            raise ExprError("Expression cannot be evaluated as real numeric math.") from exc
        if np.iscomplexobj(result):
            raise ExprError("Plot expressions must produce real values, not complex numbers.")
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
    try:
        lo, hi = float(value[0]), float(value[1])
    except OverflowError as exc:
        raise ExprError(f"{what} must be a finite [lo, hi] number pair.") from exc
    if not (math.isfinite(lo) and math.isfinite(hi)) or lo >= hi:
        raise ExprError(f"{what} must be finite with lo < hi.")
    return lo, hi


def _compile_curve_entry(
    entry: Any, index: int, kind: str, params: set[str]
) -> CompiledCurve:
    """Validate + compile one entry of a `curves` list."""
    if not isinstance(entry, dict):
        raise ExprError(f"curves[{index}] must be an object.")

    y_fn = compile_expression(entry.get("y"), params)
    if kind == "explicit":
        x_fn = compile_expression("t", params)
    else:
        x_fn = compile_expression(_parametric_x(entry), params)

    style = entry.get("style", "solid")
    if style not in _ALLOWED_STYLES:
        raise ExprError(f"curves[{index}].style must be one of {_ALLOWED_STYLES}.")
    role = entry.get("role", "primary" if index == 0 else "secondary")
    if role not in _ALLOWED_ROLES:
        raise ExprError(f"curves[{index}].role must be one of {_ALLOWED_ROLES}.")

    name = entry.get("name")
    if name is not None and not isinstance(name, str):
        raise ExprError(f"curves[{index}].name must be a string.")
    name = (name or f"curve {index + 1}")[:MAX_LABEL_CHARS]

    return CompiledCurve(name=name, x_fn=x_fn, y_fn=y_fn, style=style, role=role)


def _compile_points(
    payload: Any, t0: float, t1: float
) -> tuple[tuple[float, str], ...]:
    """Validate the optional `points` marker list: [{t, label}]."""
    if payload is None:
        return ()
    if not isinstance(payload, list):
        raise ExprError("points must be a list of {t, label} objects.")
    out: list[tuple[float, str]] = []
    for i, entry in enumerate(payload[:MAX_POINTS]):
        if not isinstance(entry, dict):
            raise ExprError(f"points[{i}] must be an object.")
        t = entry.get("t")
        if not isinstance(t, (int, float)) or isinstance(t, bool):
            raise ExprError(f"points[{i}].t must be a finite number.")
        try:
            t = float(t)
        except OverflowError as exc:
            raise ExprError(f"points[{i}].t must be a finite number.") from exc
        if not math.isfinite(t):
            raise ExprError(f"points[{i}].t must be a finite number.")
        if not (t0 <= t <= t1):
            continue  # silently drop out-of-range markers
        label = entry.get("label", "")
        if not isinstance(label, str):
            raise ExprError(f"points[{i}].label must be a string.")
        out.append((float(t), label[:MAX_LABEL_CHARS]))
    return tuple(out)


def _parametric_x(payload: dict) -> Any:
    value = payload.get("x")
    # Preserve legacy missing/empty-string defaults, but never silently turn a
    # malformed numeric zero, False, list or object into the diagonal x=t.
    return "t" if value is None or (isinstance(value, str) and value == "") else value


def compile_plot(payload: Any, variables: dict[str, float]) -> CompiledPlot:
    """Validate a solver `plot` payload and compile its expressions.

    Two payload shapes are accepted:
    - Legacy single curve: {kind, x, y, t_range, ...} — unchanged behavior.
    - Multi-curve: {kind, curves: [{name, x?, y, style?, role?}], t_range, ...}
      plus optional fill_between {upper, lower} and points [{t, label}].
    """
    if not isinstance(payload, dict):
        raise ExprError("plot payload must be an object.")

    kind = payload.get("kind", "explicit")
    if kind not in ("explicit", "parametric"):
        raise ExprError(f"Unknown plot kind {kind!r}.")

    t0, t1 = _pair(payload.get("t_range"), "t_range")
    if t1 - t0 > MAX_T_SPAN:
        t1 = t0 + MAX_T_SPAN
        if not math.isfinite(t1) or t1 <= t0:
            raise ExprError("t_range cannot represent an increasing interval within the supported span.")

    params = set(variables.keys())

    curves_payload = payload.get("curves")
    if curves_payload is not None:
        if not isinstance(curves_payload, list) or not curves_payload:
            raise ExprError("curves must be a non-empty list.")
        if len(curves_payload) > MAX_CURVES:
            raise ExprError(f"At most {MAX_CURVES} curves are allowed.")
        curves = tuple(
            _compile_curve_entry(entry, i, kind, params)
            for i, entry in enumerate(curves_payload)
        )
    else:
        # Legacy single-curve payload (and all cached SolverResults).
        y_fn = compile_expression(payload.get("y"), params)
        if kind == "explicit":
            x_fn = compile_expression("t", params)
        else:
            x_fn = compile_expression(_parametric_x(payload), params)
        curves = (
            CompiledCurve(
                name=str(payload.get("y_label") or "y")[:MAX_LABEL_CHARS],
                x_fn=x_fn,
                y_fn=y_fn,
                style="solid",
                role="primary",
            ),
        )

    # Primary = first primary-role curve, else the first curve.
    primary = next((c for c in curves if c.role == "primary"), curves[0])

    fill_payload = payload.get("fill_between")
    fill = None
    if fill_payload is not None:
        if not isinstance(fill_payload, dict):
            raise ExprError("fill_between must be an object with upper/lower.")
        fill = (
            compile_expression(fill_payload.get("upper"), params),
            compile_expression(fill_payload.get("lower"), params),
        )

    points = _compile_points(payload.get("points"), t0, t1)

    x_range = _pair(payload["x_range"], "x_range") if payload.get("x_range") else None
    y_range = _pair(payload["y_range"], "y_range") if payload.get("y_range") else None

    return CompiledPlot(
        kind=kind,
        x_fn=primary.x_fn,
        y_fn=primary.y_fn,
        t_range=(t0, t1),
        x_range=x_range,
        y_range=y_range,
        x_label=str(payload.get("x_label") or ("t" if kind == "explicit" else "x")),
        y_label=str(payload.get("y_label") or "y"),
        param_names=tuple(sorted(params)),
        curves=curves,
        fill=fill,
        points=points,
    )


def fallback_plot_payload() -> dict[str, Any]:
    """Deterministic damped-oscillator showcase matching llm.DEFAULT_VARIABLES.

    Emits the oscillation plus its two dashed decay envelopes so the no-key
    path exercises the full multi-curve pipeline (roles, dashed references).
    """
    return {
        "kind": "explicit",
        "t_range": [0.0, 10.0],
        "y_range": [-1.2, 1.2],
        "x_label": "t (s)",
        "y_label": "x(t)",
        "curves": [
            {
                "name": "x(t)",
                "y": "exp(-damping*t) * sin(stiffness*t*2) / sqrt(mass)",
                "style": "solid",
                "role": "primary",
            },
            {
                "name": "envelope",
                "y": "exp(-damping*t) / sqrt(mass)",
                "style": "dashed",
                "role": "reference",
            },
            {
                "name": "-envelope",
                "y": "-exp(-damping*t) / sqrt(mass)",
                "style": "dashed",
                "role": "reference",
            },
        ],
    }
