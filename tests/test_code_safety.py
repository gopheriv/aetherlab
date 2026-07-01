"""WP1: the AST safety gate must reject escapes and accept real scenes."""

from __future__ import annotations

import pytest

from aetherlab.core.models import ProblemRequest, RagResult, SolverResult
from aetherlab.services.code_safety import validate_code_safety
from aetherlab.services.manim_runtime import ManimRuntime
from aetherlab.services.scene_generator import SceneGenerator

from .conftest import make_settings

UNSAFE_SNIPPETS = [
    ("import os", "import os\nos.getcwd()"),
    ("os.system", "import os\nos.system('echo hi')"),
    ("subprocess", "import subprocess\nsubprocess.run(['ls'])"),
    ("exec", "exec('x = 1')"),
    ("eval", "y = eval('1 + 1')"),
    ("__import__", "__import__('os').system('echo hi')"),
    ("subclasses escape", "cls = ().__class__.__bases__[0].__subclasses__()"),
    ("open", "open('/etc/passwd').read()"),
    ("globals leak", "fn.__globals__['x'] = 1"),
    ("pathlib", "import pathlib\npathlib.Path('.')"),
    ("relative import", "from . import helpers"),
]

SAFE_SCENES = [
    (
        "numpy + math + trackers",
        "from manim import *\n"
        "import numpy as np\n"
        "import math\n"
        "class AetherLabScene(Scene):\n"
        "    def construct(self):\n"
        "        t = ValueTracker(0.0)\n"
        "        axes = Axes(x_range=[-3, 3], y_range=[-2, 2])\n"
        "        curve = always_redraw(lambda: axes.plot(lambda x: np.sin(x)))\n"
        "        self.add(axes, curve)\n"
        "        angle = math.pi / 4\n",
    ),
    (
        "ThreeDScene + MathTex",
        "from manim import *\n"
        "class AetherLabScene(ThreeDScene):\n"
        "    def construct(self):\n"
        "        eq = MathTex(r'\\\\frac{d^2\\\\theta}{dt^2}')\n"
        "        self.add(eq)\n",
    ),
]


@pytest.mark.parametrize("label, code", UNSAFE_SNIPPETS, ids=[s[0] for s in UNSAFE_SNIPPETS])
def test_unsafe_is_rejected(label: str, code: str) -> None:
    ok, issues = validate_code_safety(code)
    assert ok is False, f"{label} should be rejected"
    assert issues, f"{label} should produce at least one issue string"


@pytest.mark.parametrize("label, code", SAFE_SCENES, ids=[s[0] for s in SAFE_SCENES])
def test_real_scene_is_accepted(label: str, code: str) -> None:
    ok, issues = validate_code_safety(code)
    assert ok is True, f"{label} should be accepted but got: {issues}"
    assert issues == []


def test_syntax_error_defers_to_compiler() -> None:
    # A syntax error is NOT a safety issue — the gate must defer (return safe).
    ok, issues = validate_code_safety("def broken(:\n    pass")
    assert ok is True
    assert issues == []


def test_deterministic_template_passes_gate(tmp_path) -> None:
    """A false positive here would block a legitimate render — critical."""
    request = ProblemRequest(prompt="pendulum")
    solver = SolverResult(
        summary="Damped oscillator",
        derivation_steps=["a", "b"],
        keywords=["x"],
        variables={"damping": 0.2, "stiffness": 1.0},
        model_name="m",
    )
    rag = RagResult(keywords=[], hits=[], backend="none")
    runtime = ManimRuntime(make_settings(tmp_path))
    template = runtime._build_scene_code("AetherLabScene", request, solver, rag)
    ok, issues = validate_code_safety(template)
    assert ok is True, f"deterministic template rejected: {issues}"


def test_generator_fallback_scene_passes_gate(tmp_path) -> None:
    solver = SolverResult(
        summary="Damped oscillator",
        derivation_steps=["a"],
        keywords=["x"],
        variables={"damping": 0.2, "stiffness": 1.0},
        model_name="m",
    )
    generator = SceneGenerator(make_settings(tmp_path))
    fallback = generator._fallback_scene("AetherLabScene", solver)
    ok, issues = validate_code_safety(fallback)
    assert ok is True, f"generator fallback rejected: {issues}"
