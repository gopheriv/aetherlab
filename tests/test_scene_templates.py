"""WP7: domain-aware deterministic fallback scenes."""

from __future__ import annotations

import pytest

from aetherlab.core.models import ProblemRequest, RagResult, SolverResult
from aetherlab.services.code_safety import validate_code_safety
from aetherlab.services.manim_runtime import ManimRuntime
from aetherlab.services.scene_generator import SceneGenerator
from aetherlab.services.scene_templates import build_scene, detect_domain

from .conftest import make_settings

DOMAINS = ["oscillator", "pendulum", "orbit", "wave"]


# ── detection ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("keywords, variables, expected", [
    (["simple", "pendulum", "angles"], {}, "pendulum"),
    ([], {"gravity": 9.8, "length": 1.0}, "pendulum"),
    (["kepler", "orbit"], {}, "orbit"),
    (["two-body", "problem"], {}, "orbit"),
    (["fourier", "series"], {}, "wave"),
    (["heat equation", "rod"], {}, "wave"),
    (["damped", "harmonic", "oscillator"], {"damping": 0.1}, "oscillator"),
    ([], {}, "oscillator"),
])
def test_detect_domain(keywords, variables, expected):
    assert detect_domain(keywords, variables) == expected


# ── every template is safe, compiles, and is LaTeX-free ─────────────────────


@pytest.mark.parametrize("domain", DOMAINS)
def test_template_is_safe_and_compiles(domain):
    code = build_scene(
        class_name="AetherLabScene",
        domain=domain,
        title="A title with 'quotes' & specials_",
        summary="Summary text",
        steps=["step one", "step two", "step three", "step four (dropped)"],
        variables={"damping": 0.2, "stiffness": 1.5, "gravity": 9.8,
                   "length": 0.5, "eccentricity": 0.6},
    )
    safe, issues = validate_code_safety(code)
    assert safe, f"{domain} template failed the gate: {issues}"
    compile(code, f"<{domain}-template>", "exec")
    assert "class AetherLabScene(Scene)" in code
    assert "MathTex" not in code and "Tex(" not in code, "templates must not need LaTeX"
    # Templates MUST import Manim Community directly. A manimlib-first
    # try/except makes the class subclass ManimGL's Scene on machines with
    # ManimGL installed, and `python -m manim` then reports "There are no
    # scenes inside that module" (exit 0, no video) — the original latent bug.
    assert "from manim import *" in code
    assert "manimlib" not in code, "templates must not import manimlib"


def test_unknown_domain_falls_back_to_oscillator():
    code = build_scene("AetherLabScene", "nonsense-domain", "t", "s", [], {})
    compile(code, "<t>", "exec")
    assert "damping" in code  # oscillator body


# ── integration: both fallback paths pick the right domain ──────────────────


def _solver(keywords, variables):
    return SolverResult(
        summary="sum", derivation_steps=["a", "b"], keywords=keywords,
        variables=variables, model_name="m",
    )


def test_runtime_fallback_is_domain_aware(tmp_path):
    rt = ManimRuntime(make_settings(tmp_path))
    code = rt._build_scene_code(
        "AetherLabScene",
        ProblemRequest(prompt="Solve the simple pendulum for large angles."),
        _solver(["simple", "pendulum"], {}),
        RagResult(keywords=[], hits=[], backend="none"),
    )
    assert "pendulum template" in code
    assert "omega = math.sqrt(g / length)" in code


def test_runtime_fallback_detects_domain_from_prompt_alone(tmp_path):
    # Deterministic solver keywords may miss the domain — the prompt fills in.
    rt = ManimRuntime(make_settings(tmp_path))
    code = rt._build_scene_code(
        "AetherLabScene",
        ProblemRequest(prompt="Show the Kepler orbit for an inverse-square force."),
        _solver(["inverse-square", "force"], {}),
        RagResult(keywords=[], hits=[], backend="none"),
    )
    assert "orbit template" in code


def test_generator_fallback_is_domain_aware(tmp_path):
    gen = SceneGenerator(make_settings(tmp_path))
    code = gen._fallback_scene("AetherLabScene", _solver(["fourier", "wave"], {}))
    assert "wave template" in code
    safe, issues = validate_code_safety(code)
    assert safe, issues
    compile(code, "<t>", "exec")


def test_generator_fallback_default_still_oscillator(tmp_path):
    gen = SceneGenerator(make_settings(tmp_path))
    code = gen._fallback_scene("AetherLabScene", _solver([], {"damping": 0.3}))
    assert "oscillator template" in code
    assert "0.3" in code  # solver variable parameterizes the scene
