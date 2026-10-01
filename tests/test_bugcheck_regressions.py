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


# ── live-run findings (2026-09-30 mission) ──────────────────────────────────

_ADVISORY_ONLY_SCENE = '''from manim import *
class AetherLabScene(Scene):
    def construct(self):
        glow = Circle(color=YELLOW).move_to(LEFT * 2)
        halo = Square(color=BLUE).move_to(LEFT * 2)
        self.play(Create(glow), run_time=2)
        self.play(Create(halo), glow.animate.shift(UP), run_time=2)
        self.play(halo.animate.rotate(PI / 3), run_time=2)
        self.wait(1)
'''


class _FakeGenerator:
    """Stands in for SceneGenerator: fixed code, repair returns a canned reply."""

    repaired_code: str | None = None

    def __init__(self, settings, **_kwargs):
        self._last_storyboard = None
        self._last_scene_spec = None
        self._last_fallback_reason = ""

    async def generate(self, request, solver, rag, class_name):
        return type(self).code

    async def repair(self, code, error, class_name, *, full_scene=False):
        return type(self).repaired_code or code


def _generate_with(monkeypatch, code, repaired=None):
    import asyncio

    from aetherlab.core.models import ProblemRequest, RagResult
    from aetherlab.services import manim_runtime

    fake = type("Fake", (_FakeGenerator,), {"code": code, "repaired_code": repaired})
    monkeypatch.setattr(manim_runtime, "SceneGenerator", fake)
    runtime = manim_runtime.ManimRuntime()
    monkeypatch.setattr(runtime, "_compose_curated", lambda *a, **k: None)
    settings = SimpleNamespace(openai_api_key="sk-test", render_mode="local", data_dir=None)
    return asyncio.run(runtime.generate_scene_async(
        ProblemRequest(prompt="Explain blackbody radiation", duration_target_s=7.0),
        _solver("Planck's law", ["blackbody"], {"T": 5800.0}),
        RagResult(keywords=[], hits=[], backend="none"),
        settings,
    ))


def test_advisory_only_ai_scene_ships_instead_of_the_template(monkeypatch):
    # Live run 2: an AI scene whose only remaining finding was a heuristic
    # [HYGIENE:OVERLAP] was discarded for the 5-second domain template.
    bundle = _generate_with(monkeypatch, _ADVISORY_ONLY_SCENE)
    assert bundle.used_fallback is False, bundle.fallback_reason
    assert bundle.code == _ADVISORY_ONLY_SCENE
    assert any("Shipping the best AI scene with advisory issues" in d
               for d in bundle.diagnostics), bundle.diagnostics


def test_crash_level_lint_goes_to_repair_not_straight_to_the_template(monkeypatch):
    broken = _ADVISORY_ONLY_SCENE.replace(
        "halo = Square(color=BLUE).move_to(LEFT * 2)",
        "halo = Diamond(color=BLUE).move_to(RIGHT * 2)",
    )
    fixed = broken.replace("Diamond(color=BLUE)", "Square(color=BLUE).rotate(PI / 4)")
    bundle = _generate_with(monkeypatch, broken, repaired=fixed)
    assert bundle.used_fallback is False, bundle.diagnostics
    assert "Diamond" not in bundle.code and "rotate(PI / 4)" in bundle.code


def test_crash_level_scene_never_ships(monkeypatch):
    broken = _ADVISORY_ONLY_SCENE.replace("Square(", "Diamond(")
    bundle = _generate_with(monkeypatch, broken)      # repair returns it unchanged
    assert bundle.used_fallback is True
    assert "Diamond" not in bundle.code


def test_minimax_scene_calls_default_to_thinking_off():
    from aetherlab.services.scene_generator import SceneGenerator

    minimax = SimpleNamespace(llm_model="MiniMax-M3")
    assert SceneGenerator(minimax)._minimax_thinking is False
    assert SceneGenerator(minimax, minimax_thinking=True)._minimax_thinking is True


def test_zero_length_waits_are_removed_and_nonpositive_durations_linted():
    from aetherlab.services.scene_validation import (
        lint_nonpositive_durations,
        repair_zero_waits,
    )

    code = (
        "class S(Scene):\n    def construct(self):\n"
        "        self.play(Create(c), run_time=1)\n        self.wait(0.0)\n"
        "        if flag:\n            self.wait(0)\n        self.wait(1)\n"
    )
    assert len(lint_nonpositive_durations(code)) == 2
    fixed, dropped = repair_zero_waits(code)
    assert dropped == 2 and lint_nonpositive_durations(fixed) == []
    assert "            pass\n" in fixed and "self.wait(1)" in fixed
    assert lint_nonpositive_durations("self.play(A(), run_time=0)\n")


def test_failure_classifier_ignores_dvisvgm_info_lines():
    from aetherlab.services.manim_runtime import _classify_failure

    log = (
        "INFO Writing '\\lambda_{max}' to media/Tex/abc.tex\n"
        "INFO dvisvgm media/Tex/abc.dvi\n" * 3
        + "ValueError: AetherLabScene.wait() has a duration of 0 <= 0 seconds"
    )
    assert _classify_failure(log) == "invalid-value"
    assert _classify_failure("! Undefined control sequence \foo") == "latex"


def test_repair_of_an_accepted_scene_is_not_blocked_by_advisory_findings():
    from aetherlab.services.manim_runtime import _blocking_scene_issues

    timeline = [{"id": "A1.B1", "start_s": 0.0, "end_s": 10.0}]
    drifted = (
        "from manim import *\nclass AetherLabScene(Scene):\n    def construct(self):\n"
        "        c = Circle()\n        # BEAT A1.B1 | 0.00-10.00 s\n"
        "        self.play(c.animate.shift(UP), run_time=2)\n        self.wait(1)\n"
    )
    ok, issues = _blocking_scene_issues(drifted, timeline)
    assert ok and issues == []
    ok, issues = _blocking_scene_issues(drifted.replace("Circle()", "Diamond()"), timeline)
    assert not ok and any("Diamond" in issue for issue in issues)


def test_redrawn_readout_without_position_is_flagged_for_layout_repair():
    from aetherlab.services.manim_runtime import _LAYOUT_BLOCKERS
    from aetherlab.services.scene_validation import scene_hygiene_warnings

    unplaced = (
        "from manim import *\nclass S(Scene):\n    def construct(self):\n"
        "        t = ValueTracker(3000)\n"
        "        value = always_redraw(lambda: DecimalNumber(t.get_value()).scale(0.3))\n"
        "        group = VGroup(Text('T ='), value).arrange(RIGHT)\n"
    )
    placed = unplaced.replace(".scale(0.3))", ".scale(0.3).next_to(label, RIGHT))")
    flagged = [w for w in scene_hygiene_warnings(unplaced) if w.startswith(_LAYOUT_BLOCKERS)]
    assert flagged and "REDRAW_POSITION" in flagged[0]
    assert not [w for w in scene_hygiene_warnings(placed) if "REDRAW_POSITION" in w]


def test_critic_requests_disable_minimax_thinking(monkeypatch, tmp_path):
    import asyncio

    from aetherlab.services import scene_critic

    calls = []

    class _Resp:
        choices = [SimpleNamespace(message=SimpleNamespace(
            content='{"verdict": "ship", "score": 8}'))]

    class _Client:
        chat = SimpleNamespace(completions=SimpleNamespace(create=None))

    async def create(**kwargs):
        calls.append(kwargs)
        return _Resp()

    _Client.chat.completions.create = create
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"png")
    monkeypatch.setattr(scene_critic, "extract_frames", lambda *_a, **_k: [frame])
    monkeypatch.setattr("aetherlab.services.llm_client.make_client", lambda *_a, **_k: _Client())
    settings = SimpleNamespace(vision_model="MiniMax-M3", llm_model="MiniMax-M3",
                               openai_api_key="sk-test")
    result = asyncio.run(scene_critic.critique_video(str(tmp_path / "v.mp4"), "brief", settings))
    assert result.verdict == "ship"
    assert calls[0]["extra_body"] == {"thinking": {"type": "disabled"}}


def test_beat_timing_judges_beat_length_not_a_constant_intro_offset():
    code = (
        "from manim import *\nclass S(Scene):\n    def construct(self):\n"
        "        self.play(FadeIn(t), run_time=0.6)\n"
        "        # BEAT A1.B1 | 0.00-2.73 s\n        self.play(Create(a), run_time=2.73)\n"
        "        # BEAT A1.B2 | 2.73-5.00 s\n        self.play(Create(b), run_time=2.27)\n"
    )
    timeline = [{"id": "A1.B1", "start_s": 0.0, "end_s": 2.73},
                {"id": "A1.B2", "start_s": 2.73, "end_s": 5.0}]
    assert check_timeline_runtime(code, timeline) == []
    short = check_timeline_runtime(code.replace("run_time=2.27", "run_time=0.5"), timeline)
    assert short and short[0].startswith("[TIMING:BEAT_RUNTIME] A1.B2")


def _revision_loop(monkeypatch, scores, passes, tmp_path):
    """Drive render_scene_with_repair with scripted critic scores."""
    import asyncio
    from dataclasses import replace

    from aetherlab.services import scene_critic
    from aetherlab.services.manim_runtime import ManimRuntime
    from aetherlab.services.scene_critic import Critique
    from aetherlab.services.scene_generator import SceneGenerator

    video = tmp_path / "v.mp4"
    video.write_bytes(b"v")
    queue = list(scores)
    calls = {"critique": 0, "render": 0}

    async def fake_critique(*_a, **_k):
        calls["critique"] += 1
        score = queue.pop(0)
        return Critique(verdict="revise" if score < 7 else "ship", score=score, issues=["x"])

    async def fake_revise(self, code, critique, class_name):
        return ("from manim import *\nclass AetherLabScene(Scene):\n"
                "    def construct(self):\n        dot = Dot(color=RED)\n"
                "        self.play(Create(dot))\n        self.play(dot.animate.shift(RIGHT))\n")

    async def fake_render(scene, *_a, **_k):
        calls["render"] += 1
        return replace(scene, status="rendered", video_path=str(video))

    monkeypatch.setattr(scene_critic, "critique_video", fake_critique)
    monkeypatch.setattr(SceneGenerator, "revise", fake_revise)
    settings = SimpleNamespace(
        openai_api_key="sk-test", vision_model="v", llm_model="m", render_mode="local",
        visual_critic_max_passes=passes, visual_critic_keyframes=6, data_dir=tmp_path,
        narration_enabled=False, tts_voice="", tts_rate="",
    )
    runtime = ManimRuntime(settings)
    monkeypatch.setattr(runtime, "_render_once", fake_render)
    original = ("from manim import *\nclass AetherLabScene(Scene):\n"
                "    def construct(self):\n        self.play(Create(Dot()))\n")
    start = SceneBundle("AetherLabScene", original, "manim-community", "rendered",
                        video_path=str(video))
    result = asyncio.run(runtime.render_scene_with_repair(start, settings, quality="l"))
    return result, calls, original


def test_worse_revision_is_reverted_and_revising_stops(monkeypatch, tmp_path):
    result, calls, original = _revision_loop(monkeypatch, [4.0, 3.0], 3, tmp_path)
    assert result.code == original and result.quality_score == 4.0
    assert calls == {"critique": 2, "render": 1}, calls      # no third round
    assert any("kept the earlier cut" in d for d in result.diagnostics)


def test_last_revision_is_scored_before_it_ships(monkeypatch, tmp_path):
    kept, _calls, original = _revision_loop(monkeypatch, [4.0, 6.5], 1, tmp_path)
    assert kept.code != original and kept.quality_score == 6.5
    assert any("Final visual critique" in d for d in kept.diagnostics)
    reverted, _calls, original = _revision_loop(monkeypatch, [4.0, 3.5], 1, tmp_path)
    assert reverted.code == original and reverted.quality_score == 4.0


def test_repair_that_fixes_the_crash_but_keeps_advisory_drift_still_ships(monkeypatch):
    # Live Compton run: the repair removed an undefined name but kept an
    # overlap warning; it was discarded and the template shipped.
    broken = _ADVISORY_ONLY_SCENE.replace("Square(", "Diamond(")
    bundle = _generate_with(monkeypatch, broken, repaired=_ADVISORY_ONLY_SCENE)
    assert bundle.used_fallback is False, bundle.diagnostics
    assert bundle.code == _ADVISORY_ONLY_SCENE


def test_spelled_out_diagonal_directions_are_mapped_to_manim_constants():
    from aetherlab.services.scene_validation import repair_unknown_color_constants

    code = ("from manim import *\nclass S(Scene):\n    def construct(self):\n"
            "        d = Dot().move_to(UP_RIGHT * 2 + DOWN_LEFT)\n        t = Text('UP_RIGHT')\n")
    fixed, mapping = repair_unknown_color_constants(code)
    assert mapping == {"UP_RIGHT": "UR", "DOWN_LEFT": "DL"}
    assert "move_to(UR * 2 + DL)" in fixed and "Text('UP_RIGHT')" in fixed


def test_repaired_template_is_never_shipped_as_an_ai_scene(monkeypatch):
    import asyncio

    from aetherlab.core.models import ProblemRequest, RagResult
    from aetherlab.services import manim_runtime

    class _TemplateGen(_FakeGenerator):
        code = _ADVISORY_ONLY_SCENE.replace("Square(", "Diamond(")
        repaired_code = _ADVISORY_ONLY_SCENE

        async def generate(self, request, solver, rag, class_name):
            self._last_fallback_reason = "AI scene generation failed (timeout)."
            return type(self).code

    monkeypatch.setattr(manim_runtime, "SceneGenerator", _TemplateGen)
    runtime = manim_runtime.ManimRuntime()
    monkeypatch.setattr(runtime, "_compose_curated", lambda *a, **k: None)
    bundle = asyncio.run(runtime.generate_scene_async(
        ProblemRequest(prompt="x", duration_target_s=7.0), _solver("s", ["k"], {}),
        RagResult(keywords=[], hits=[], backend="none"),
        SimpleNamespace(openai_api_key="sk-test", render_mode="local", data_dir=None),
    ))
    assert bundle.used_fallback is True and bundle.fallback_reason


def test_cloud_budget_findings_stay_blocking():
    from aetherlab.services.manim_runtime import _is_advisory_issue

    assert _is_advisory_issue("[HYGIENE:OVERLAP] a and b")
    assert _is_advisory_issue("[TIMING:BEAT_RUNTIME] A1.B1 ...")
    assert not _is_advisory_issue("[PERF:CLOUD_COST] estimate 4.2 remains above 3.5.")
    assert not _is_advisory_issue("[PERF:PLAY_BUDGET] 20 calls exceed 16.")


def test_failover_keeps_a_requested_thinking_off():
    from aetherlab.services.llm_client import FailoverChatClient

    client = FailoverChatClient.__new__(FailoverChatClient)
    client.purpose = "general"
    client._fallback_settings = SimpleNamespace(llm_model="MiniMax-M3")
    backup = client._fallback_kwargs({
        "model": "k3-agent", "extra_body": {"thinking": {"type": "disabled"}},
    })
    assert backup["extra_body"] == {"thinking": {"type": "disabled"}}
    plain = client._fallback_kwargs({"model": "k3-agent"})
    assert "extra_body" not in plain


def test_ledger_start_clears_metrics_from_a_previous_backend(tmp_path):
    from aetherlab.services.render_ledger import RenderJobLedger

    ledger = RenderJobLedger(tmp_path / "ledger.json")
    ledger.start(job_id="j1", backend="local")
    ledger.metrics("j1", {"backend": "local", "local_manim_version": "0.21.0",
                          "render_wall_seconds": 60.0})
    ledger.start(job_id="j1", backend="github-actions")
    ledger.metrics("j1", {"backend": "github_actions", "render_wall_seconds": 140.0})
    metrics = ledger.get("j1")["metrics"]
    assert metrics == {"backend": "github_actions", "render_wall_seconds": 140.0}
