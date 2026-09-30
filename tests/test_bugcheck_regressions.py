"""Regressions for the 2026-09-30 bug check (BUG-65..BUG-73 in ERRORS_FOUND.md).

Each test reproduces a defect that the green 221/221 feature suite missed.
"""

from __future__ import annotations

from types import SimpleNamespace

from aetherlab.core.models import SceneBundle, SolverResult
from aetherlab.services.derivation_verify import verify_derivation_records
from aetherlab.services.manim_runtime import _estimate_misses_target
from aetherlab.services.scene_components import _compose_component
from aetherlab.services.scene_components.problems import PROBLEMS, _module
from aetherlab.services.scene_generator import schedule_storyboard_timeline
from aetherlab.services.scene_validation import (
    check_timeline_runtime,
    estimate_duration,
    validate_scene,
)
from aetherlab.services.voiceover import storyboard_timed_narration_segments


def _solver(summary: str, keywords: list[str], variables: dict[str, float]) -> SolverResult:
    return SolverResult(
        summary=summary, derivation_steps=[], keywords=keywords,
        variables=variables, model_name="test",
    )


_LAGGED_SCENE = '''from manim import *
class AetherLabScene(Scene):
    def construct(self):
        dots = VGroup(*[Dot() for _ in range(6)]).arrange(RIGHT)
        # BEAT A1.B1 | 0.00-3.00 s
        self.play(LaggedStart(*[FadeIn(d) for d in dots], lag_ratio=0.3))
        self.wait(0.5)
        # BEAT A1.B2 | 3.00-5.00 s
        self.play(dots.animate.shift(UP), run_time=1.5)
        self.wait(0.5)
'''
_LAGGED_TIMELINE = [
    {"id": "A1.B1", "start_s": 0.0, "end_s": 3.0},
    {"id": "A1.B2", "start_s": 3.0, "end_s": 5.0},
]


def test_bug65_lagged_start_beat_is_not_rejected_as_mistimed():
    # Six lagged 1 s FadeIns at lag 0.3 really run 2.5 s, so this scene is on
    # schedule; the gate used to count the LaggedStart as 1 s and reject it.
    assert check_timeline_runtime(_LAGGED_SCENE, _LAGGED_TIMELINE) == []
    ok, issues = validate_scene(_LAGGED_SCENE, require_motion=True, timeline=_LAGGED_TIMELINE)
    assert ok, issues


def test_bug65_timeline_gate_still_catches_literal_mistiming():
    code = _LAGGED_SCENE.replace(
        "self.play(LaggedStart(*[FadeIn(d) for d in dots], lag_ratio=0.3))",
        "self.play(FadeIn(dots), run_time=0.5)",
    )
    issues = check_timeline_runtime(code, _LAGGED_TIMELINE)
    assert issues and issues[0].startswith("[TIMING:BEAT_RUNTIME] A1.B1")


def test_bug66_approximate_duration_estimate_never_rejects_a_scene():
    est = estimate_duration(_LAGGED_SCENE)
    assert not est.exact and any("group animation" in note for note in est.notes)
    # 3.5 s estimated against a 30 s target is a miss only if the sum is exact.
    assert _estimate_misses_target(est, 30.0) is False
    exact = estimate_duration(
        "class S(Scene):\n    def construct(self):\n"
        "        self.play(Create(c), run_time=2)\n        self.wait(duration=3)\n"
    )
    assert exact.exact and exact.total_seconds == 5.0
    assert _estimate_misses_target(exact, 30.0) is True
    nested = estimate_duration(
        "class S(Scene):\n    def construct(self):\n"
        "        self.play(Create(c, run_time=4))\n"
    )
    assert nested.exact and nested.total_seconds == 4.0


def test_bug67_act_narration_is_spoken_once_not_per_beat():
    board = {
        "acts": [
            {"name": "Setup", "duration_s": 10, "beats": ["ball", "arrow", "axes"]},
            {"name": "Fall", "duration_s": 20, "beats": [
                {"detail": "drop", "narration_cue": "It drops."},
                {"detail": "speed readout"},
            ]},
        ],
        "narration": ["A ball waits at the cliff edge.", "Gravity takes over."],
    }
    timeline = schedule_storyboard_timeline(board, 30.0)["timeline"]
    cues = [beat["narration_cue"] for beat in timeline]
    assert cues == ["A ball waits at the cliff edge.", "", "", "It drops.", ""]
    spoken = [seg["text"] for seg in storyboard_timed_narration_segments({"timeline": timeline})]
    assert spoken == ["A ball waits at the cliff edge.", "It drops."]


def test_bug68_cached_fallback_scene_is_stale_when_a_key_exists():
    from aetherlab.services.lesson_pipeline import _scene_cache_usable as lesson_usable
    from aetherlab.services.pipeline import _stale_fallback_scene
    from aetherlab.ui.workers import _scene_cache_usable as worker_usable

    template = SceneBundle(class_name="S", code="x", engine="manim", status="compiled",
                           used_fallback=True, fallback_reason="timed out")
    ai_scene = SceneBundle(class_name="S", code="x", engine="manim", status="compiled")
    keyed = SimpleNamespace(openai_api_key="sk-test", min_quality_score=0.0)
    keyless = SimpleNamespace(openai_api_key=None, min_quality_score=0.0)
    assert _stale_fallback_scene(template, keyed)
    assert not _stale_fallback_scene(template, keyless)
    assert not worker_usable(template, keyed) and not lesson_usable(template, keyed)
    assert worker_usable(template, keyless) and lesson_usable(template, keyless)
    assert worker_usable(ai_scene, keyed) and lesson_usable(ai_scene, keyed)


def _statuses(records):
    solver = SimpleNamespace(
        derivation_records=records,
        derivation_steps=["step"] * len(records),
        variables={"F": 10.0, "m": 2.0, "a": 5.0, "g": 9.8, "h": 1.0},
    )
    return [item["status"] for item in verify_derivation_records(solver)["items"]]


def test_bug69_rearranging_by_a_symbol_is_equivalent():
    assert _statuses([
        {"from_expression": "F = m*a", "to_expression": "a = F/m"},
        {"from_expression": "m*g*h = m*v**2/2", "to_expression": "v**2 = 2*g*h"},
        {"from_expression": "F = m*a", "to_expression": "m*a - F = 0"},
    ]) == ["passed", "passed", "passed"]
    # Changing the physics or multiplying by a sum stays not equivalent.
    assert _statuses([
        {"from_expression": "F = m*a", "to_expression": "F = m*a + 1"},
        {"from_expression": "x = y", "to_expression": "x*(x-y) = y*(x-y)"},
    ]) == ["failed", "failed"]


def test_bug70_generic_phrases_do_not_route_to_unrelated_components():
    wrong = {
        "atwood machine": _solver(
            "Two masses m1 and m2 hang over a frictionless pulley; find the acceleration.",
            ["pulley", "tension"], {"m1": 2.0, "m2": 3.0, "g": 9.8}),
        "wind tunnel": _solver(
            "Drag force on a car model in a wind tunnel at 30 m/s.",
            ["drag", "wind tunnel"], {"v": 30.0}),
        "mirror image": _solver(
            "The projectile's path is a mirror image about the apex.",
            ["kinematics"], {"v0": 20.0}),
    }
    for label, solver in wrong.items():
        routed = _compose_component("S", solver)
        assert routed is None or routed[0] not in {
            "coupled_oscillators", "quantum", "mirror"}, (label, routed[0])
    right = {
        "coupled_oscillators": _solver("Two coupled oscillators exchange energy.",
                                       ["coupled oscillators"], {}),
        "quantum": _solver("Quantum tunneling through a barrier.", ["tunneling"], {}),
        "mirror": _solver("An object 30 cm from a mirror of focal length 10 cm.",
                          ["optics", "mirror"], {}),
    }
    for expected, solver in right.items():
        routed = _compose_component("S", solver)
        assert routed is not None and routed[0] == expected


def test_bug70_coupled_pendulums_are_not_a_chaotic_double_pendulum():
    routed = _compose_component(
        "S", _solver("Two coupled pendulums trade energy back and forth.",
                     ["coupled pendulums"], {}))
    assert routed is not None and routed[0] == "coupled_oscillators"


def _problem_matches(solver):
    return [name for name in PROBLEMS if _module(name).matches(solver)]


def test_bug71_problem_videos_need_their_own_physics():
    unrelated = [
        _solver("Photoelectric emission of electrons from a metal.",
                ["photoelectric effect"], {"f": 1e15, "h": 6.626e-34}),
        _solver("Sound transmission through a wall.", ["sound"], {"h": 3.0}),
        _solver("In the Bohr model the electron orbits the nucleus.",
                ["Bohr model"], {"h": 6.626e-34}),
        _solver("A car at 20 m/s brakes. How far does it travel before stopping?",
                ["kinematics", "braking"], {"v": 20.0, "a": -5.0}),
        _solver("A plane lands at 70 m/s and decelerates on the runway.",
                ["kinematics"], {"v": 70.0, "a": -3.0}),
        _solver("A ball is thrown straight up at 15 m/s.", ["projectile"], {"v0": 15.0}),
        _solver("A stone is thrown horizontally from a 20 m cliff.", ["projectile"],
                {"v0": 10.0, "h": 20.0}),
    ]
    for solver in unrelated:
        assert _problem_matches(solver) == [], solver.summary
    assert _problem_matches(_solver(
        "A ball is kicked at 18 m/s, 40 degrees above level ground; split the "
        "velocity into horizontal and vertical components. How far away does it land?",
        ["projectile motion"], {"v0": 18.0, "theta": 40.0})) == ["projectile_landing"]
    assert _problem_matches(_solver(
        "How long is one lap of the ISS?", ["ISS"], {})) == ["orbit_period"]


def test_bug72_wikibooks_citations_are_labelled_and_filtered():
    from aetherlab.core.models import ProblemRequest, RagHit, RagResult
    from aetherlab.services import study_document as sd
    from aetherlab.services.research import build_citations

    rag = RagResult(keywords=["projectile"], hits=[RagHit(
        source_path="https://en.wikibooks.org/wiki/Physics_Study_Guide/Projectile_motion",
        page_number=None, score=0.9, excerpt="...", source_label="Projectile motion",
        origin="web")], backend="web")
    [citation] = build_citations(rag)
    assert ", Wikibooks: https://en.wikibooks.org/" in citation
    kept = sd.relevant_citations(
        [citation, "Taekwondo, Wikibooks: https://en.wikibooks.org/wiki/Taekwondo"],
        {"theory": "projectile motion"}, ProblemRequest(prompt="A ball is kicked."))
    assert kept == [citation]
