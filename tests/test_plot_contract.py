"""Reviewed expression/payload contracts; no GUI, network or user files."""
import ast
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from aetherlab.core.proc import subprocess_kwargs
from aetherlab.services.plotting import (
    ExprError,
    compile_expression,
    compile_plot,
    fallback_plot_payload,
)

FUNCTIONS = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan, "sinh": math.sinh, "cosh": math.cosh,
    "tanh": math.tanh, "arcsin": math.asin, "arccos": math.acos, "arctan": math.atan,
    "exp": math.exp, "log": math.log, "log10": math.log10, "sqrt": math.sqrt,
    "abs": abs, "sign": lambda value: 1 if value > 0 else (-1 if value < 0 else 0),
}


def test_f27_all_unary_functions_match_independent_scalar_math():
    from aetherlab.services.plotting import _FUNCTIONS
    assert set(FUNCTIONS) == set(_FUNCTIONS), "Every allowed function requires an independent oracle"
    grid = np.array([0.2, 0.5, 0.8])
    before = grid.copy()
    for name, oracle in FUNCTIONS.items():
        result = compile_expression(f"{name}(t)", set())(grid, {})
        np.testing.assert_allclose(result, [oracle(float(value)) for value in grid], err_msg=name)
        np.testing.assert_array_equal(grid, before)
        if name not in {"log", "log10", "sqrt"}:
            signed = np.array([-0.5, 0., 0.5])
            np.testing.assert_allclose(compile_expression(f"{name}(t)", set())(signed, {}),
                                       [oracle(float(value)) for value in signed], err_msg=name)


def test_f27_operators_constants_caret_and_named_parameters():
    from aetherlab.services.plotting import _CONSTANTS
    assert set(_CONSTANTS) == {"pi", "e", "tau"}
    grid = np.array([1.0, 2.0, 3.0])
    expressions = {"t+2": grid + 2, "t-2": grid - 2, "t*2": grid * 2, "t/2": grid / 2,
        "t//2": grid // 2, "t%2": grid % 2, "t**2": grid ** 2, "t^2": grid ** 2,
        "+t": grid, "-t": -grid, "cos(sin(t))": [math.cos(math.sin(x)) for x in grid],
        "pi": np.full(3, math.pi), "e": np.full(3, math.e), "tau": np.full(3, math.tau),
        "pi+e+tau": np.full(3, math.pi + math.e + math.tau),
        "α*t + mass": 2 * grid + 4}
    for expression, expected in expressions.items():
        np.testing.assert_allclose(compile_expression(expression, {"α", "mass"})(grid, {"α": 2, "mass": 4}), expected)
    # A declared physics coefficient e retains its existing precedence over the
    # mathematical constant; undeclared runtime keys cannot replace constants.
    np.testing.assert_allclose(compile_expression("e*t", {"e"})(grid, {"e": 2}), 2 * grid)
    np.testing.assert_allclose(compile_expression("e*t", set())(grid, {"e": 2}), math.e * grid)


def test_f27_function_arity_is_checked_before_numpy_can_use_an_out_array():
    for name in FUNCTIONS:
        for args in ("", "t,t", "t,t,t"):
            with pytest.raises(ExprError):
                compile_expression(f"{name}({args})", set())


def test_f27_unsafe_syntax_and_bare_function_values_are_rejected():
    for expression in ("__import__('os')", "open('owned')", "t.real", "t[0]", "[t]", "(t,)", "{'x':t}",
                       "{t}", "lambda:1", "(x:=1)", "t if t else 0", "t>0", "t and 1", "~t", "t<<2",
                       "t|2", "t&2", "t@t", "True", "'text'", "1j", "[x for x in t]", "unknown+t",
                       "sin(t,out=t)", "sin(*t)", "sin(**t)", *FUNCTIONS):
        with pytest.raises(ExprError):
            compile_expression(expression, set())


def test_f27_runtime_namespace_cannot_replace_functions_or_inject_unused_values():
    grid = np.array([0.2, 0.5, 0.8])
    for declared in (set(), {"sin"}):
        result = compile_expression("sin(t)", declared)(grid, {"sin": 17, "unused": object()})
        np.testing.assert_allclose(result, np.sin(grid))
    np.testing.assert_array_equal(compile_expression("t", {"t"})(grid, {"t": 99}), grid)
    for invalid in ({}, {"mass": "bad"}, {"mass": object()}, {"mass": 10**400}):
        with pytest.raises(ExprError):
            compile_expression("mass*t", {"mass"})(grid, invalid)


def test_f27_scalar_and_multidimensional_outputs_are_independent_copies():
    for grid in (np.array(2.0), np.array([]), np.arange(6.0).reshape(2, 3)):
        before = grid.copy()
        result = compile_expression("2", set())(grid, {})
        assert result.shape == grid.shape
        result[...] = 99
        np.testing.assert_array_equal(grid, before)
        np.testing.assert_array_equal(compile_expression("2", set())(grid, {}), np.full(grid.shape, 2.0))
        identity = compile_expression("t", set())(grid, {})
        identity[...] = 77
        np.testing.assert_array_equal(grid, before)


def test_f27_damped_physics_curve_keeps_grid_and_parameters_unchanged():
    grid = np.linspace(0, 3, 17)
    before = grid.copy()
    parameters = {"damping": 0.2, "stiffness": 1.7}
    function = compile_expression("exp(-damping*t)*sin(stiffness*t)", set(parameters))
    np.testing.assert_allclose(function(grid, parameters), [math.exp(-0.2*x)*math.sin(1.7*x) for x in grid])
    np.testing.assert_array_equal(grid, before)
    assert parameters == {"damping": 0.2, "stiffness": 1.7}


def test_f28_character_and_ast_limits_include_exact_boundaries():
    compile_expression("t" + " " * 511, set())
    with pytest.raises(ExprError):
        compile_expression("t" + " " * 512, set())
    expression = "+" + "+".join(["t"] * 49 + ["1"])
    assert len(list(ast.walk(ast.parse(expression, mode="eval")))) == 200
    np.testing.assert_allclose(compile_expression(expression, set())(np.array([2.]), {}), [99.])
    with pytest.raises(ExprError):
        compile_expression("+".join(["t"] * 51), set())
    for invalid in (None, 0, "", " ", "("):
        with pytest.raises(ExprError):
            compile_expression(invalid, set())


def test_f28_overflow_zero_division_and_domains_are_controlled():
    grid = np.array([1., 2.])
    assert np.isposinf(compile_expression("9**9**9", set())(grid, {})).all()
    assert np.isnan(compile_expression("1/0", set())(grid, {})).all()
    assert np.isnan(compile_expression("sqrt(-t)", set())(grid, {})).all()
    assert np.isneginf(compile_expression("log(0)", set())(grid, {})).all()
    with pytest.raises(ExprError):
        compile_expression("(-1)**0.5", set())(grid, {})
    with pytest.raises(ExprError):
        compile_expression("9" * 400, set())


def test_f28_range_span_clamps_and_unrepresentable_ranges_fail():
    for start in (0, -20001, 20001):
        compiled = compile_plot({"y": "t", "t_range": [start, start + 20000]}, {})
        assert compiled.t_range == (float(start), float(start + 10000))
    assert compile_plot({"y": "t", "t_range": (-2, 2)}, {}).t_range == (-2., 2.)
    for limits in ([1e308, 1.000000000000001e308], [-1e308, 1e308], [0, 10**400]):
        with pytest.raises(ExprError):
            compile_plot({"y": "t", "t_range": limits}, {})
    with pytest.raises(ExprError):
        compile_plot({"y": "t", "t_range": [0, 1], "points": [{"t": 10**400}]}, {})


def test_f28_pathological_power_finishes_in_an_actual_bounded_process():
    root = Path(__file__).resolve().parents[1]
    environment = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    command = "import numpy as n; from aetherlab.services.plotting import compile_expression; assert n.isposinf(compile_expression('9**9**9',set())(n.array([0.]),{})).all(); print('OK')"
    result = subprocess.run([sys.executable, "-c", command], cwd=root, env=environment,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10, **subprocess_kwargs())
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_f29_legacy_explicit_and_parametric_payloads_preserve_their_curves():
    grid = np.array([0., 1., 2.])
    explicit = compile_plot({"y": "t^2", "t_range": [0, 2], "x_label": "t (s)", "y_label": "s (m)"}, {})
    np.testing.assert_array_equal(explicit.x_fn(grid, {}), grid)
    np.testing.assert_array_equal(explicit.y_fn(grid, {}), grid ** 2)
    assert (explicit.x_label, explicit.y_label, explicit.param_names) == ("t (s)", "s (m)", ())
    for x in (None, "", "0"):
        plot = compile_plot({"kind": "parametric", "x": x, "y": "t", "t_range": [0, 2]}, {})
        np.testing.assert_array_equal(plot.x_fn(grid, {}), np.zeros(3) if x == "0" else grid)


def test_f29_multicurve_primary_roles_styles_and_payload_isolation():
    payload = {"kind": "parametric", "t_range": [0, 2], "curves": [
        {"name": "secondary", "x": "t", "y": "t", "role": "secondary", "style": "dashed"},
        {"name": "primary", "x": "2*t", "y": "gain*t", "role": "primary"}]}
    plot = compile_plot(payload, {"gain": 3})
    payload["curves"][1]["y"] = "99*t"
    assert plot.param_names == ("gain",)
    assert plot.curves[0].style == "dashed" and plot.curves[0].role == "secondary"
    np.testing.assert_array_equal(plot.x_fn(np.array([1.]), {}), [2.])
    np.testing.assert_array_equal(plot.y_fn(np.array([1.]), {"gain": 3}), [3.])
    np.testing.assert_array_equal(plot.y_fn(np.array([1.]), {"gain": 4}), [4.])
    for curve in payload["curves"]:
        curve["role"] = "secondary"
        curve.pop("name", None)
    first = compile_plot(payload, {"gain": 3})
    assert first.curves[0].name == "curve 1"
    np.testing.assert_array_equal(first.x_fn(np.array([1.]), {}), [1.])
    default = compile_plot(fallback_plot_payload(), {"damping": .2, "stiffness": 1., "mass": 1.})
    assert len(default.curves) == 3


def test_f29_malformed_payloads_and_curve_entries_raise_domain_errors():
    for payload in (None, [], "bad", {"kind": "bad"}, {"y": "t", "t_range": [1, 0]},
                    {"y": False, "t_range": [0, 1]}, {"curves": [], "t_range": [0, 1]},
                    {"curves": [{"y": "t"}] * 7, "t_range": [0, 1]}):
        with pytest.raises(ExprError):
            compile_plot(payload, {})
    for entry in (None, "bad", {}, {"y": "t", "style": "dots"}, {"y": "t", "role": "bad"}, {"y": "t", "name": 2}):
        with pytest.raises(ExprError):
            compile_plot({"t_range": [0, 1], "curves": [entry]}, {})
    for x in (0, False, [], {}):
        for curve in (False, True):
            payload = {"kind": "parametric", "t_range": [0, 1]}
            payload.update({"curves": [{"x": x, "y": "t"}]} if curve else {"x": x, "y": "t"})
            with pytest.raises(ExprError):
                compile_plot(payload, {})


def test_f29_optional_ranges_and_invalid_finite_pairs():
    for value in (None, [], {}, "", False, 0):
        assert compile_plot({"y": "t", "t_range": [0, 1], "x_range": value, "y_range": value}, {}).x_range is None
    for key in ("t_range", "x_range", "y_range"):
        for value in ([0], [0, 0], [1, 0], [True, 1], [0, "1"], [0, math.inf], [math.nan, 1], [0, 10**400]):
            payload = {"y": "t", "t_range": [0, 1], key: value}
            with pytest.raises(ExprError):
                compile_plot(payload, {})


def test_f29_fill_markers_label_limits_and_six_curve_boundary():
    payload = {"t_range": [0, 2], "curves": [{"name": "x" * 80, "y": "t"}] * 6,
        "fill_between": {"upper": "t+1", "lower": "t-1"},
        "points": [{"t": 0, "label": "a" * 80}, {"t": 2, "label": "end"}, {"t": 3, "label": "drop"}]}
    compiled = compile_plot(payload, {})
    assert len(compiled.curves) == 6 and len(compiled.curves[0].name) == 40
    assert compiled.points == ((0., "a" * 40), (2., "end"))
    np.testing.assert_array_equal(compiled.fill[0](np.array([1.]), {}), [2.])
    np.testing.assert_array_equal(compiled.fill[1](np.array([1.]), {}), [0.])
    payload["points"] = [{"t": 1, "label": str(i)} for i in range(10)]
    assert len(compile_plot(payload, {}).points) == 8
    for fields in ({"fill_between": []}, {"fill_between": {}}, {"points": {}}, {"points": [None]},
                   {"points": [{"t": True}]}, {"points": [{"t": math.nan}]}, {"points": [{"t": 1, "label": 2}]}):
        with pytest.raises(ExprError):
            compile_plot({"y": "t", "t_range": [0, 2], **fields}, {})
