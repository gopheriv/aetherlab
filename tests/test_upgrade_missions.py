from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from aetherlab.core.models import ProblemRequest, RagHit, RagResult, SceneBundle, SolverResult
from aetherlab.services.course_mode import CourseProgressStore
from aetherlab.services.derivation_verify import verify_derivation_records, verify_ode_units
from aetherlab.services.scene_specification import build_scene_spec


def _solver(**kwargs):
    values = dict(
        summary="A spring oscillator",
        derivation_steps=["Substitute the parameters into the equation."],
        keywords=["oscillator"],
        variables={"mass": 2.0, "stiffness": 8.0, "damping": 0.2},
        model_name="test",
    )
    values.update(kwargs)
    return SolverResult(**values)


def test_spaced_review_due_dates_and_review_rescheduling(tmp_path):
    plan = SimpleNamespace(
        title="Oscillations", topic="Oscillator", audience="undergrad",
        objectives=["Energy exchange"],
        questions=[SimpleNamespace(
            q="Where does the energy go?", answer="Between kinetic and potential.",
            why="The spring stores potential energy.", choices=["A", "B"],
        )],
    )
    store = CourseProgressStore(tmp_path / "progress.json")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    store.record_quiz_answer(plan, 0, False, "A", now=start)
    assert store.due_reviews(now=start) == []
    due = store.due_reviews(now=start + timedelta(days=1))
    assert len(due) == 1 and due[0]["answer"] == "Between kinetic and potential."
    interval = store.record_review_result(due[0], True, now=start + timedelta(days=1))
    assert interval == 1
    assert store.due_reviews(now=start + timedelta(days=1)) == []
    assert len(store.due_reviews(now=start + timedelta(days=2))) == 1


def test_spaced_review_uses_custom_schedule_confidence_and_records_events(tmp_path):
    plan = SimpleNamespace(
        title="Radiation", topic="Blackbody radiation", audience="undergrad",
        objectives=["Energy quantization"],
        questions=[SimpleNamespace(
            q="What does quantization mean?", answer="Discrete allowed energies.",
            why="The oscillator exchanges energy in packets.", choices=["A", "B"],
        )],
    )
    store = CourseProgressStore(tmp_path / "progress.json", review_intervals_days="2,5,10")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    store.record_quiz_answer(
        plan, 0, True, "A", confidence_level="low", now=start
    )
    assert store.due_reviews(now=start + timedelta(days=1)) == []
    first_due = store.due_reviews(now=start + timedelta(days=2))
    assert len(first_due) == 1
    assert first_due[0]["review_streak"] == 0

    assert store.record_review_result(
        first_due[0], True, now=start + timedelta(days=2)
    ) == 2
    later_due = store.due_reviews(now=start + timedelta(days=4))
    assert len(later_due) == 1
    store.record_quiz_answer(
        plan, 0, True, "A", confidence_level="high", now=start + timedelta(days=4)
    )
    assert store.due_reviews(now=start + timedelta(days=6)) == []
    assert len(store.due_reviews(now=start + timedelta(days=9))) == 1

    events = store.evaluation_events()
    assert [event["kind"] for event in events] == ["quiz", "spaced_review", "quiz"]
    assert events[0]["confidence_level"] == "low"
    assert events[0]["scheduled_interval_days"] == 2
    assert events[1]["days_since_first_attempt"] == 2.0
    assert events[2]["confidence_level"] == "high"
    assert events[2]["scheduled_interval_days"] == 5


def test_review_schedule_parser_is_bounded_and_falls_back_safely():
    from aetherlab.services.course_mode import parse_review_intervals

    assert parse_review_intervals("1,3,7,14") == (1, 3, 7, 14)
    assert parse_review_intervals("10,2,2,400,0") == (2, 10)
    assert parse_review_intervals("bad") == (1, 3, 7, 14)


def test_review_schedule_settings_round_trip_and_env_precedence(tmp_path, monkeypatch):
    from aetherlab.core.settings import load_settings, save_app_config

    monkeypatch.setenv("AETHERLAB_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("AETHERLAB_REVIEW_INTERVALS_DAYS", raising=False)
    save_app_config({"review_intervals_days": "2,5,10"})
    assert load_settings().review_intervals_days == "2,5,10"
    monkeypatch.setenv("AETHERLAB_REVIEW_INTERVALS_DAYS", "1,4,8")
    assert load_settings().review_intervals_days == "1,4,8"


def test_lesson_quiz_captures_self_rated_confidence(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from aetherlab.core.models import LessonBundle
    from aetherlab.services.lesson_planner import _template_lesson
    from aetherlab.ui.qt_compat import QtWidgets
    from aetherlab.ui.widgets import LessonView, _QuestionCard

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    plan = _template_lesson("Kepler orbit", "undergrad")
    view = LessonView()
    try:
        view.set_lesson(LessonBundle(plan=plan))
        card = view.findChildren(_QuestionCard)[0]
        card._confidence.setCurrentIndex(2)
        wrong = next(choice for choice in card._q.choices if choice != card._q.answer)
        card._answer_mcq(wrong)
        assert view.confidence_for_question(0) == "high"
    finally:
        view.close()
        # Keep the Qt application referenced through the test lifetime.
        assert app is QtWidgets.QApplication.instance()


def test_algebra_checks_are_safe_and_conservative():
    good = _solver(derivation_records=[{
        "claim": "Rearrange the kinematics equation",
        "from_expression": "v = u + a*t",
        "to_expression": "v-u = a*t",
    }])
    assert verify_derivation_records(good)["status"] == "passed"
    bad = _solver(derivation_records=[{
        "from_expression": "v = u + a*t",
        "to_expression": "v-u = -a*t",
    }])
    assert verify_derivation_records(bad)["status"] == "failed"
    prose = _solver()
    assert verify_derivation_records(prose)["status"] == "not_checked"
    hostile = _solver(derivation_records=[{
        "from_expression": "__import__('os').system('whoami')",
        "to_expression": "1",
    }])
    assert verify_derivation_records(hostile)["status"] == "not_checked"

    numeric_good = _solver(
        variables={"x": 2.0},
        derivation_records=[{"from_expression": "x + 1", "to_expression": "1 + x"}],
    )
    good_check = verify_derivation_records(numeric_good)["items"][0]
    assert good_check["status"] == "passed"
    assert good_check["substitution_status"] == "passed"
    numeric_spec = build_scene_spec(ProblemRequest("substitution check"), numeric_good)
    assert numeric_spec["physics"]["derivation_records"][0]["substitution_status"] == "passed"

    numeric_bad = _solver(
        variables={"x": 2.0},
        derivation_records=[{"from_expression": "x + 1", "to_expression": "4"}],
    )
    bad_check = verify_derivation_records(numeric_bad)["items"][0]
    assert bad_check["status"] == "failed"
    assert bad_check["substitution_status"] == "failed"

    coincidental_match = _solver(
        variables={"x": 1.0},
        derivation_records=[{"from_expression": "x + 1", "to_expression": "2*x"}],
    )
    coincidental_check = verify_derivation_records(coincidental_match)["items"][0]
    assert coincidental_check["status"] == "failed"
    assert coincidental_check["substitution_status"] == "passed"


def test_scene_hygiene_flags_explicitly_tiny_text_without_blocking():
    from aetherlab.services.scene_validation import scene_hygiene_warnings, validate_scene

    code = """from manim import *
class Demo(Scene):
    def construct(self):
        tiny = Text('tiny label', font_size=12)
        readable = MathTex('x = 1', font_size=24)
        self.add(tiny, readable)
"""
    warnings = scene_hygiene_warnings(code)
    text_warnings = [warning for warning in warnings if "HYGIENE:TEXT_SIZE" in warning]
    assert len(text_warnings) == 1
    assert "font_size=12" in text_warnings[0]
    assert "MathTex" not in text_warnings[0]
    assert validate_scene(code)[0] is True


def test_human_review_analysis_requires_paired_data_and_never_sets_a_gate(tmp_path):
    from tools.human_review_analysis import analyze_reviews

    cases = []
    machine_cases = {}
    for index in range(3):
        case_id = f"scene-{index}"
        (tmp_path / f"{case_id}.mp4").write_bytes(b"fixture")
        human_score = index + 2
        cases.append({
            "id": case_id,
            "video_path": f"{case_id}.mp4",
            "ratings": {
                "legibility": human_score,
                "physics": human_score,
                "pacing": human_score,
                "teaching_value": human_score,
            },
        })
        machine_cases[case_id] = {
            "score": human_score * 2,
            "breakdown": {
                "legibility": index / 2,
                "substance": index / 2,
                "structure": index / 2,
            },
        }
    report = analyze_reviews(
        {"human_ratings_required": 3, "cases": cases},
        {"cases": machine_cases},
        review_path=tmp_path / "review.json",
    )
    assert report["status"] == "ready_for_calibration_review"
    assert report["overall_spearman_rho"] == 1.0
    assert report["axis_correlations"]["physics"]["spearman_rho"] == 1.0
    assert report["axis_correlations"]["physics"]["mapping_kind"] == "proxy"
    assert report["release_gate_calibrated"] is False

    missing_scores = analyze_reviews(
        {"human_ratings_required": 3, "cases": cases},
        review_path=tmp_path / "review.json",
    )
    assert missing_scores["status"] == "incomplete"
    assert missing_scores["paired_human_critic_cases"] == 0


def test_ode_unit_checks_and_scene_spec_provenance():
    solver = _solver(
        numeric_spec={
            "state": ["x", "v"],
            "rhs": ["v", "-(stiffness/mass)*x - (2*damping)*v"],
            "initial": [1.0, 0.0],
            "t_range": [0.0, 2.0],
            "observe": "x",
        },
        variable_units={
            "x": "meter", "v": "meter/second", "mass": "kilogram",
            "stiffness": "newton/meter", "damping": "1/second",
        },
        derivation_records=[{
            "step_index": 1,
            "claim": "Newton's second law",
            "from_expression": "v = u + a*t",
            "to_expression": "v-u = a*t",
            "source_ref": "OpenStax Physics",
        }],
        assumptions=["Small displacement"],
    )
    units = verify_ode_units(solver)
    if units["status"] != "not_checked":
        assert units["status"] == "passed"
    rag = RagResult(
        keywords=["oscillator"],
        hits=[RagHit("physics.pdf", 12, 0.9, "Newton's second law", "OpenStax Physics")],
        backend="test",
    )
    storyboard = {
        "timeline_duration_s": 4.0,
        "timeline": [{
            "id": "A1.B1", "start_s": 0.0, "end_s": 4.0,
            "detail": "Show the oscillator", "narration_cue": "The mass moves.",
            "subtitle_cue": "The mass moves.", "target_object": "mass",
            "target_equation": "x(t)", "anchor_cell": "C3",
        }],
    }
    spec = build_scene_spec(
        ProblemRequest("Spring oscillator", duration_target_s=4.0),
        solver,
        rag,
        storyboard,
        narration="The mass moves.",
        scene=SimpleNamespace(code="class Scene: pass", status="compiled", engine="manim"),
    )
    assert spec["schema"] == "aetherlab.scene_spec.v1"
    assert spec["verification"]["derivations"]["status"] == "passed"
    assert spec["physics"]["derivation_records"][0]["provenance_ids"] == ["ref-1"]
    assert spec["timeline"]["beats"][0]["end_s"] == 4.0
    assert spec["narration"]["beat_cues"][0]["text"] == "The mass moves."
    assert spec["narration"]["beat_cues"][0]["target_object"] == "mass"
    assert spec["narration"]["beat_cues"][0]["target_equation"] == "x(t)"

    bad_units = _solver(
        numeric_spec=solver.numeric_spec,
        variable_units={**solver.variable_units, "damping": "meter"},
    )
    assert verify_ode_units(bad_units)["status"] == "failed"

    unsupported_units = _solver(
        numeric_spec={
            "state": ["x"], "rhs": ["special_function(x)"],
            "initial": [1.0], "t_range": [0.0, 1.0], "observe": "x",
        },
        variable_units={"x": "meter"},
    )
    unsupported_report = verify_ode_units(unsupported_units)
    assert unsupported_report["status"] == "not_checked"


def test_request_parameter_flows_from_remote_solver_to_scene_canvas_and_research(
    tmp_path, monkeypatch,
):
    import asyncio
    import json

    import openai

    from aetherlab.core.models import ProblemRequest, RagResult
    from aetherlab.services.llm import AsyncLLMCoordinator
    from aetherlab.services.numeric import solve_numeric
    from aetherlab.services.research import build_latex, render_numeric_figure
    from aetherlab.services.scene_specification import (
        build_scene_spec,
        canvas_inputs_from_scene_spec,
    )

    request = ProblemRequest(
        "Compare a damped spring at a selected mass.",
        parameters={"mass": 2.5},
        duration_target_s=4.0,
    )
    payload = {
        "summary": "A damped spring oscillator.",
        "derivation_steps": ["Apply Newton's second law."],
        "keywords": ["spring", "oscillator"],
        "variables": {"mass": 1.0, "stiffness": 8.0, "damping": 0.2},
        "ode": {
            "state": ["x", "v"],
            "rhs": ["v", "-(stiffness/mass)*x - 2*damping*v"],
            "initial": [1.0, 0.0],
            "t_range": [0.0, 2.0],
            "observe": "x",
        },
    }

    class FakeCompletions:
        async def create(self, **_kwargs):
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content=json.dumps(payload),
            ))])

    class FakeClient:
        def __init__(self, **_kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(openai, "AsyncOpenAI", FakeClient)
    monkeypatch.setattr(
        "aetherlab.services.model_policy.openai_client_kwargs", lambda _settings: {}
    )
    settings = SimpleNamespace(
        openai_api_key="test-key", llm_model="test-model", solver_attempts=1,
    )
    solver = asyncio.run(AsyncLLMCoordinator(settings).solve(request))
    assert solver.variables["mass"] == 2.5
    assert payload["variables"]["mass"] == 1.0

    rag = RagResult(keywords=list(solver.keywords), hits=[], backend="test")
    spec = build_scene_spec(request, solver, rag)
    projected = canvas_inputs_from_scene_spec(spec)
    assert projected is not None
    assert spec["request"]["parameters"]["mass"] == 2.5
    assert spec["physics"]["variables"]["mass"]["value"] == 2.5
    assert projected["params"]["mass"] == 2.5

    selected_mass = solve_numeric(projected["numeric_spec"], projected["params"])
    default_params = {**projected["params"], "mass": 1.0}
    default_mass = solve_numeric(projected["numeric_spec"], default_params)
    assert selected_mass.ok and default_mass.ok
    assert abs(selected_mass.series()[-1] - default_mass.series()[-1]) > 1e-3

    figure = render_numeric_figure(solver, tmp_path / "selected_mass.png")
    assert figure == tmp_path / "selected_mass.png" and figure.is_file()
    latex = build_latex(request, solver, rag, figure)
    assert "mass & = 2.5" in latex

    # Direct scene generation must apply the same request override before
    # building both its variable prompt and canonical scene specification.
    from aetherlab.services.scene_generator import SceneGenerator

    stale_solver = _solver(
        variables={"mass": 1.0, "stiffness": 8.0, "damping": 0.2},
        numeric_spec=payload["ode"],
    )
    captured = {}
    generator = SceneGenerator(SimpleNamespace(
        openai_api_key="test-key", llm_model="test-model", llm_timeout_seconds=60,
    ))

    async def fake_generate_remote(req, normalized, references, class_name):
        captured["mass"] = normalized.variables["mass"]
        captured["spec"] = build_scene_spec(req, normalized, references)
        return f"class {class_name}: pass"

    monkeypatch.setattr(generator, "_generate_remote", fake_generate_remote)
    code = asyncio.run(generator.generate(request, stale_solver, rag))
    assert code == "class AetherLabScene: pass"
    assert captured["mass"] == 2.5
    assert captured["spec"]["physics"]["variables"]["mass"]["value"] == 2.5


def test_invalid_request_parameters_are_skipped_not_raised():
    from aetherlab.core.models import ProblemRequest
    from aetherlab.services.parameters import apply_request_parameters

    solver = _solver(variables={"mass": 1.0, "stiffness": 8.0})
    request = ProblemRequest(
        "Spring",
        parameters={"mass": 2.5, "stiffness": float("nan"), " ": 3.0, "flag": True, "k": "x"},
    )
    updated = apply_request_parameters(request, solver)
    assert updated.variables == {"mass": 2.5, "stiffness": 8.0}
    assert solver.variables["mass"] == 1.0

    only_bad = ProblemRequest("Spring", parameters={"stiffness": float("inf")})
    assert apply_request_parameters(only_bad, solver) is solver


def test_numeric_trajectory_scene_preserves_solver_samples_and_time_order():
    import ast

    import numpy as np

    from aetherlab.services.numeric import solve_numeric
    from aetherlab.services.scene_components import trajectory

    solver = _solver(
        summary="Exponential decay",
        numeric_spec={
            "state": ["x"],
            "rhs": ["-x"],
            "initial": [1.0],
            "t_range": [0.0, 2.0],
            "observe": "x",
        },
    )
    code = trajectory.build("TrajectoryCheck", solver)
    assert code is not None

    tree = ast.parse(code)
    sample_literals = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in {"xs", "ys"}:
                sample_literals[target.id] = ast.literal_eval(node.value)

    expected = solve_numeric(solver.numeric_spec, solver.variables, max_points=120)
    assert expected.ok
    assert sample_literals["xs"] == [round(float(value), 5) for value in expected.t]
    assert sample_literals["ys"] == [round(float(value), 5) for value in expected.series()]
    assert "curve.set_points_as_corners(points)" in code
    assert "UpdateFromAlphaFunc(" in code
    assert "rate_func=linear" in code
    assert "MoveAlongPath" not in code

    # The displayed path's control vertices must remain within the documented
    # five-decimal serialization tolerance of the numerical samples.
    assert np.allclose(sample_literals["ys"], expected.series(), atol=5.1e-6)


def test_share_bundle_embeds_portable_validated_scene_spec(tmp_path):
    import json
    import zipfile

    from aetherlab.core.models import (
        LessonBundle,
        LessonChapter,
        LessonPlan,
        ProblemRequest,
        RagHit,
        RagResult,
        SceneBundle,
    )
    from aetherlab.services.scene_specification import build_scene_spec
    from aetherlab.services.share_export import export_lesson_bundle

    video = tmp_path / "lesson.mp4"
    video.write_bytes(b"mock mp4 payload")
    board = {
        "timeline_duration_s": 4.0,
        "timeline": [{
            "id": "A1.B1",
            "start_s": 0.0,
            "end_s": 4.0,
            "narration_cue": "A charge creates an electric field.",
            "target_object": "field lines",
        }],
    }
    solver = _solver(derivation_records=[{
        "claim": "Coulomb field",
        "source_ref": "OpenStax Physics",
        "from_expression": "E = k*q/r^2",
        "to_expression": "E = k*q/r^2",
    }])
    request = ProblemRequest("Electric dipole field", duration_target_s=4.0)
    rag = RagResult(
        keywords=["electric dipole"],
        hits=[RagHit(str(tmp_path / "textbook.pdf"), 12, 0.9, "Field law", "OpenStax Physics")],
        backend="test",
    )
    scene = SceneBundle(
        "AetherLabScene", "class AetherLabScene: pass", "manim", "rendered",
        video_path=str(video), storyboard=board,
    )
    scene.scene_spec = build_scene_spec(request, solver, rag, board, scene=scene)
    plan = LessonPlan(
        title="Electric dipole",
        topic="Electric dipole",
        chapters=[LessonChapter("dipole", "Field lines", key_equations=["E=kq/r^2"])],
    )
    bundle = LessonBundle(
        plan=plan,
        chapter_scenes=[scene],
        video_path=str(video),
        status="assembled",
    )
    output = tmp_path / "lesson.zip"
    export_lesson_bundle(bundle, output)
    with zipfile.ZipFile(output) as archive:
        name = next(path for path in archive.namelist() if path.endswith("/evidence/scene_01.json"))
        portable = json.loads(archive.read(name))
    serialized = json.dumps(portable)
    assert portable["schema"] == "aetherlab.scene_spec.v1"
    assert portable["evidence"][0]["source"] == ""
    assert "video_path" not in portable["scene"]
    assert str(tmp_path) not in serialized


def test_scene_spec_refresh_preserves_live_parameter_values(tmp_path):
    import os
    from dataclasses import replace

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from aetherlab.core.models import ProblemRequest, SceneBundle
    from aetherlab.core.settings import load_settings
    from aetherlab.services.scene_specification import build_scene_spec
    from aetherlab.ui.main_window import MainWindow
    from aetherlab.ui.qt_compat import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert app is not None
    settings = replace(load_settings(), data_dir=tmp_path, render_mode="local")
    window = MainWindow(settings)
    solver = _solver()
    window.on_solver_ready(solver)
    window.parameter_dock._sliders["mass"][1].setValue(1.25)
    request = ProblemRequest("Spring oscillator", duration_target_s=4.0)
    board = {"timeline_duration_s": 4.0, "timeline": [{
        "id": "A1.B1", "start_s": 0.0, "end_s": 4.0, "detail": "Spring motion",
    }]}
    scene = SceneBundle(
        "AetherLabScene", "class AetherLabScene: pass", "manim-community", "rendered",
        storyboard=board,
    )
    scene.scene_spec = build_scene_spec(request, solver, storyboard=board, scene=scene)
    window.on_scene_ready(scene)
    window.on_render_ready(scene)
    assert window.parameter_dock._sliders["mass"][1].value() == 1.25
    assert window.simulation_panel._live_canvas._state.params["mass"] == 1.25
    window.close()


def test_new_solver_and_scene_fields_round_trip():
    solver = _solver(variable_units={"x": "meter"}, assumptions=["small angle"])
    assert SolverResult.from_json(solver.to_json()).variable_units == {"x": "meter"}
    scene = SceneBundle(
        "Scene", "code", "manim", "compiled", scene_spec={"schema": "test.v1"},
        critique_model="MiniMax-M3",
        narration_text="The object moves.", subtitle_path="lesson.srt",
        narration_sync={"method": "storyboard_beat_windows"}, cache_hits=4,
    )
    restored = SceneBundle.from_json(scene.to_json())
    assert restored.scene_spec == {"schema": "test.v1"}
    assert restored.critique_model == "MiniMax-M3"
    assert restored.narration_text == "The object moves."
    assert restored.subtitle_path == "lesson.srt"
    assert restored.narration_sync["method"] == "storyboard_beat_windows"
    assert restored.cache_hits == 4


def test_storyboard_narration_maps_audio_and_caption_to_beat_windows(tmp_path, monkeypatch):
    import asyncio

    import aetherlab.services.voiceover as voiceover

    video = tmp_path / "silent.mp4"
    video.write_bytes(b"placeholder video")
    audio_durations = {}
    commands = []
    write_mux_output = True

    async def fake_synthesize(text, out_path, voice, rate):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(text.encode("utf-8"))
        audio_durations[out_path] = 0.8 if "first" in text else 1.2
        return out_path

    async def fake_duration(path):
        return 4.2 if Path(path).name.startswith("silent") else audio_durations[Path(path)]

    async def fake_ffmpeg(cmd):
        commands.append(cmd)
        if write_mux_output:
            Path(cmd[-1]).write_bytes(b"mock narrated mp4")
        return True

    monkeypatch.setattr(voiceover, "narration_available", lambda: True)
    monkeypatch.setattr(voiceover, "_ffmpeg_exe", lambda: "ffmpeg")
    monkeypatch.setattr(voiceover, "synthesize", fake_synthesize)
    monkeypatch.setattr(voiceover, "get_duration", fake_duration)
    monkeypatch.setattr(voiceover, "_run_ffmpeg", fake_ffmpeg)

    storyboard = {
        "timeline": [
            {
                "id": "A1.B1", "start_s": 0, "end_s": 2,
                "narration_cue": "The first detail.",
                "subtitle_cue": "First subtitle.", "target_object": "mass",
                "target_equation": "x(t)", "anchor_cell": "C3",
            },
            {
                "id": "A1.B2", "start_s": 2, "end_s": 4,
                "narration_cue": "The second detail.",
                "subtitle_cue": "Second subtitle.", "target_object": "curve",
                "target_equation": "v(t)", "anchor_cell": "D3",
            },
        ]
    }
    result = asyncio.run(voiceover.add_timed_beat_voiceover(
        video, storyboard, tmp_path / "out",
    ))
    assert result is not None
    assert result["sync"]["method"] == "storyboard_beat_windows"
    assert result["sync"]["timeline_scale"] == 1.05
    assert result["sync"]["max_boundary_overrun_s"] == 0.0
    assert Path(result["video_path"]).is_file()
    captions = Path(result["subtitle_path"]).read_text(encoding="utf-8")
    assert "00:00:02,100 -->" in captions
    assert "Second subtitle." in captions
    assert "adelay=2100:all=1" in commands[0][commands[0].index("-filter_complex") + 1]

    write_mux_output = False
    missing_output = tmp_path / "silent-without-mux.mp4"
    missing_output.write_bytes(b"placeholder video")
    declined = asyncio.run(voiceover.add_timed_beat_voiceover(
        missing_output, storyboard, tmp_path / "out",
    ))
    assert declined is None
    assert not (tmp_path / "out" / "silent-without-mux_narrated.mp4").exists()


def test_scene_generator_schedule_retains_visual_target_and_subtitle():
    from aetherlab.services.scene_generator import schedule_storyboard_timeline

    board = schedule_storyboard_timeline({
        "acts": [{
            "name": "HOOK", "duration_s": 4,
            "beats": [{
                "detail": "The mass moves", "duration_s": 4,
                "narration_cue": "Watch the mass move.",
                "target_object": "mass", "target_equation": "x(t)",
            }],
        }],
    }, 4)
    beat = board["timeline"][0]
    assert beat["subtitle_cue"] == beat["narration_cue"]
    assert beat["target_object"] == "mass"
    assert beat["target_equation"] == "x(t)"


def test_explicit_cloud_failure_is_visible_in_the_run_result_ui(tmp_path, monkeypatch):
    import os
    from dataclasses import replace

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from aetherlab.core.settings import load_settings
    from aetherlab.ui.main_window import MainWindow
    from aetherlab.ui.qt_compat import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    settings = replace(load_settings(), render_mode="cloud", data_dir=tmp_path)
    window = MainWindow(settings)
    scene = SceneBundle(
        "AetherLabScene", "class AetherLabScene: pass", "manim-community",
        "cloud-unavailable", diagnostics=[
            "Cloud render unavailable: status API timed out. Cloud-only mode is selected, so local fallback was skipped."
        ],
    )
    window.on_render_ready(scene)
    assert "local rendering was not started" in window.statusBar().currentMessage()
    assert not window.simulation_panel._error_banner.isHidden()
    assert "timed out" in window.simulation_panel._error_text.text()
    window.close()
    app.processEvents()


def test_prompt_gate_checks_golden_set_and_human_calibration(tmp_path):
    from tools.prompt_quality_lab import calibrate_human_review, evaluate_gate

    base_cases = [{"id": "a"}, {"id": "b"}]
    base = {"cases": base_cases, "summary": {"case_count": 2, "pass_count": 2, "mean_score": 5}}
    changed = {"cases": [{"id": "a"}, {"id": "c"}], "summary": base["summary"]}
    gate = evaluate_gate(base, changed)
    assert not gate["ok"] and "prompt IDs changed" in gate["reasons"][0]

    ids = [f"p{i}" for i in range(8)]
    report = {"cases": [{"id": key, "critic": {"score": min(i + 1, 5)}} for i, key in enumerate(ids)]}
    reviews = {
        "schema": "aetherlab.human_review.v1",
        "cases": [{
            "id": key,
            "ratings": {"legibility": min(i + 1, 5), "physics": min(i + 1, 5), "pacing": min(i + 1, 5), "teaching_value": min(i + 1, 5)},
        } for i, key in enumerate(ids)],
    }
    review_path = tmp_path / "reviews.json"
    review_path.write_text(json.dumps(reviews), encoding="utf-8")
    result = calibrate_human_review(report, review_path)
    assert result["reviewed_count"] == 8
    assert result["calibration_status"] == "ready_for_review"
    assert result["critic_human_spearman"] == 1.0


def test_render_telemetry_is_scrubbed_and_reported(tmp_path):
    from aetherlab.services.render_ledger import RenderJobLedger
    from tools.ledger_report import summarize_ledger

    ledger = RenderJobLedger(tmp_path / "render_ledger.json")
    ledger.start(job_id="render-1", backend="github-actions", provider="github_actions")
    ledger.metrics("render-1", {
        "backend": "github_actions", "queue_seconds": 3.0,
        "worker_seconds": 12.0, "download_seconds": 1.5,
        "quality_score": 8.2, "retry_count": 1,
        "manim_renderer": "cairo", "repair_cache": True, "cache_hits": 2,
        "private_key": "must-not-persist",
    })
    rows = ledger.list()
    assert "private_key" not in rows[0]["metrics"]
    report = summarize_ledger(rows)
    backend = report["telemetry"]["by_backend"]["github_actions"]
    assert backend["mean_queue_seconds"] == 3.0
    assert backend["mean_quality_score"] == 8.2
    assert report["telemetry"]["by_renderer"] == {"cairo": 1}
    assert report["telemetry"]["repair_cache"]["total_segment_hits"] == 2

    from aetherlab.services.render_backend import (
        _parse_runner_metrics,
        _workflow_elapsed_metrics,
    )

    times = _workflow_elapsed_metrics({
        "created_at": "2026-09-23T12:00:00Z",
        "run_started_at": "2026-09-23T12:00:05Z",
        "updated_at": "2026-09-23T12:00:17Z",
    })
    assert times == {"queue_seconds": 5.0, "worker_seconds": 12.0}
    runner = _parse_runner_metrics(
        "2026-09-25T02:51:00Z manim 0.21.0\n"
        "2026-09-25T02:51:00Z AETHERLAB_RENDER_WALL_SECONDS=8.5\n"
        "2026-09-25T02:51:00Z AETHERLAB_PEAK_RSS_KB=2048\n"
    )
    assert runner == {
        "render_wall_seconds": 8.5,
        "peak_rss_mb": 2.0,
        "manim_version": "0.21.0",
    }


def test_minimax_thinking_override_is_request_local():
    from aetherlab.services.model_policy import codegen_request_kwargs

    settings = SimpleNamespace(llm_model="MiniMax-M3")
    assert codegen_request_kwargs(settings) == {}
    assert codegen_request_kwargs(settings, minimax_thinking=False) == {
        "extra_body": {"thinking": {"type": "disabled"}}
    }
    assert codegen_request_kwargs(settings, minimax_thinking=True) == {
        "extra_body": {"thinking": {"type": "enabled"}}
    }


def test_visual_critic_retries_unknown_configured_model_with_in_memory_llm(tmp_path, monkeypatch):
    import asyncio
    import json as json_module
    from types import SimpleNamespace

    import openai

    import aetherlab.services.scene_critic as critic_module

    frame = tmp_path / "frame.png"
    frame.write_bytes(b"frame")
    monkeypatch.setattr(critic_module, "extract_frames", lambda _video, count: [frame])
    monkeypatch.setattr(critic_module, "_probe_duration", lambda _video: 3.0)
    calls = []

    class FakeCompletions:
        async def create(self, *, model, **kwargs):
            calls.append(model)
            if model == "qwen3.7-plus":
                raise RuntimeError("unknown model 'qwen3.7-plus' (2013)")
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content=json_module.dumps({
                    "verdict": "revise", "score": 6,
                    "breakdown": {
                        "legibility": 2, "composition": 1,
                        "palette": 1, "structure": 1, "substance": 1,
                    },
                    "problem_frames": [1], "issues": ["Improve pacing."],
                    "strengths": ["The spectrum is visible."],
                })
            ))])

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(openai, "AsyncOpenAI", FakeClient)
    settings = SimpleNamespace(
        openai_api_key="test-key", openai_base_url="https://example.invalid/v1",
        llm_timeout_seconds=30, llm_max_retries=0,
        vision_model="qwen3.7-plus", llm_model="MiniMax-M3",
    )
    result = asyncio.run(critic_module.critique_video(
        tmp_path / "video.mp4", "Explain a Planck spectrum.", settings,
    ))
    assert calls == ["qwen3.7-plus", "MiniMax-M3"]
    assert result.verdict == "revise" and result.score == 6
    assert result.model_used == "MiniMax-M3"
    assert settings.vision_model == "qwen3.7-plus"


def test_manim_command_keeps_cache_isolated_and_opengl_opt_in(tmp_path):
    from aetherlab.services.manim_runtime import (
        _animation_range_for_times,
        _manim_render_command,
    )

    args = dict(
        manim_cmd=["python", "-m", "manim"],
        quality="l",
        fps=15,
        seed=123,
        media_dir=tmp_path / "media",
        scene_file=tmp_path / "scene.py",
        class_name="AetherLabScene",
    )
    ordinary = _manim_render_command(**args)
    assert "--disable_caching" in ordinary
    assert ordinary[ordinary.index("--renderer") + 1] == "cairo"
    assert "--disable_caching" not in _manim_render_command(
        **args, cache_enabled=True, renderer="opengl"
    )
    cached = _manim_render_command(**args, cache_enabled=True, renderer="opengl")
    assert cached[cached.index("--renderer") + 1] == "opengl"
    assert "--write_to_movie" in cached
    assert "--write_to_movie" not in ordinary
    partial = _manim_render_command(
        **args, cache_enabled=True, partial_animation_range=(2, 4)
    )
    assert partial[partial.index("-n") + 1] == "2,4"
    assert "--disable_caching" not in partial

    code = """from manim import *
class AetherLabScene(Scene):
    def construct(self):
        self.wait(2)
        self.play(Write(Text('one')), run_time=3)
        self.wait(5)
"""
    assert _animation_range_for_times(code, [0.5, 4.0]) == (0, 2)
    ambiguous = code.replace("self.wait(2)", "for _ in range(2):\n            self.wait(2)")
    assert _animation_range_for_times(ambiguous, [1.0]) is None


def test_construct_play_call_counter_enforces_cloud_budget():
    from aetherlab.services.scene_validation import count_construct_play_calls

    code = "from manim import *\nclass AetherLabScene(Scene):\n    def construct(self):\n"
    code += "".join(
        "        self.play(Wait(0.1))\n" for _ in range(17)
    )
    assert count_construct_play_calls(code) == 17
    assert count_construct_play_calls("class AetherLabScene: pass") == 0


def test_linter_rejects_animation_of_updater_controlled_mobject():
    from aetherlab.services.scene_validation import check_updater_animation_conflicts

    conflict = """from manim import *
class AetherLabScene(Scene):
    def construct(self):
        readout = DecimalNumber(0)
        readout.add_updater(lambda mob: mob.set_value(2))
        self.play(readout.animate.set_value(2))
"""
    assert check_updater_animation_conflicts(conflict)[0].startswith(
        "[MANIM:UPDATER_ANIMATE] readout"
    )
    tracker_pattern = conflict.replace(
        "self.play(readout.animate.set_value(2))",
        "tracker = ValueTracker(0)\n        self.play(tracker.animate.set_value(2))",
    )
    assert check_updater_animation_conflicts(tracker_pattern) == []
    cleared_first = conflict.replace(
        "self.play(readout.animate.set_value(2))",
        "readout.clear_updaters()\n        self.play(readout.animate.set_value(2))",
    )
    assert check_updater_animation_conflicts(cleared_first) == []


def test_cloud_poll_retries_a_transient_read_timeout(tmp_path, monkeypatch):
    import asyncio
    import io
    import zipfile

    import aetherlab.services.manim_runtime as runtime
    from aetherlab.services.render_backend import CloudRenderBackend

    class CloudClient:
        def __init__(self):
            self.polls = 0
            self.artifact_name = ""

        def default_branch(self):
            return "main"

        def ensure_workflow(self, *, workflow, branch):
            return False

        def ensure_branch(self, branch):
            return None

        def put_file(self, path, content, *, branch, message):
            return None

        def dispatch(self, **kwargs):
            return 42

        def get_run(self, run_id, *, job_id, branch):
            self.polls += 1
            if self.polls == 1:
                raise TimeoutError("read operation timed out")
            return {"id": 42, "status": "completed", "conclusion": "success"}

        def download_run_logs(self, run_id):
            return (
                "2026-09-25T02:51:00Z manim 0.21.0\n"
                "2026-09-25T02:51:00Z AETHERLAB_RENDER_WALL_SECONDS=8.5\n"
                "2026-09-25T02:51:00Z AETHERLAB_PEAK_RSS_KB=2048\n"
            )

        def find_run_artifact(self, run_id, name):
            self.artifact_name = name
            return {"id": 77, "name": name}

        def find_repo_artifact(self, name):
            return None

        def download_artifact_zip(self, artifact_id):
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w") as zipped:
                zipped.writestr(
                    self.artifact_name,
                    b"\x00\x00\x00\x18ftypmp42" + b"0" * 256,
                )
            return archive.getvalue()

    settings = SimpleNamespace(
        render_mode="cloud", cloud_provider="github_actions",
        github_repo="owner/render", github_token="token",
        github_workflow="render.yml", github_branch="renders",
        cloud_render_timeout=10, cloud_poll_seconds=2, data_dir=tmp_path,
    )
    monkeypatch.setattr(runtime, "_RUNS_DIR", tmp_path / "runs")
    client = CloudClient()
    backend = CloudRenderBackend(settings, client=client)
    scene = SceneBundle(
        "AetherLabScene",
        "from manim import *\nclass AetherLabScene(Scene):\n    def construct(self):\n        self.wait(1)\n",
        "manim-community", "compiled",
    )

    rendered = asyncio.run(backend.render(
        scene, quality="l", settings=settings, timeout=10,
    ))
    assert client.polls == 2
    assert rendered.status == "rendered"
    assert rendered.video_path and Path(rendered.video_path).is_file()
    from aetherlab.services.render_ledger import RenderJobLedger

    row = RenderJobLedger(tmp_path / "render_ledger.json").list()[0]
    assert row["metrics"]["manim_version"] == "0.21.0"
    assert row["metrics"]["render_wall_seconds"] == 8.5
    assert row["metrics"]["peak_rss_mb"] == 2.0


def test_kimi_models_get_the_only_temperature_their_api_accepts():
    # Kimi K3/K2.8 reject any temperature except 1 (HTTP 400), which would make
    # every call fail into the deterministic fallback. The pathway pins it, and
    # every chat.completions call must route its temperature through the policy.
    import ast
    from pathlib import Path

    from aetherlab.services.model_policy import request_temperature, resolve_pathway

    for model in ("k3-agent", "k2d8-preview", "kimi-for-coding", "moonshot/K3-agent"):
        pathway = resolve_pathway(model)
        assert pathway.name == "kimi-reasoning" and pathway.fixed_temperature == 1.0
        assert pathway.retry_on_timeout is False
    assert resolve_pathway("MiniMax-M3").fixed_temperature is None
    assert request_temperature(SimpleNamespace(llm_model="k3-agent"), 0.15) == 1.0
    assert request_temperature(SimpleNamespace(llm_model="qwen3.7-plus"), 0.15) == 0.15

    services = Path(__file__).resolve().parents[1] / "aetherlab" / "services"
    raw = []
    for path in services.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "create"):
                continue
            for kw in node.keywords:
                if kw.arg == "temperature" and not (
                    isinstance(kw.value, ast.Call) and getattr(kw.value.func, "id", "") == "request_temperature"
                ):
                    raw.append(f"{path.name}:{node.lineno}")
    assert not raw, f"model calls sending a raw temperature: {raw}"


def test_backup_provider_takes_over_when_the_primary_fails(monkeypatch):
    # K3 primary, MiniMax backup: a cut connection, an error status or an empty
    # reply is retried once on the backup with the backup's own temperature
    # rule; a healthy primary is used alone; no backup means errors surface.
    import asyncio

    import httpx
    import openai
    import pytest

    from aetherlab.services.llm_client import make_client
    from aetherlab.services.model_policy import request_temperature

    calls = []
    behaviour = {"primary": "cut"}

    def reply(text):
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=text), finish_reason="stop")])

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            self.base_url = kwargs.get("base_url")
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

        async def _create(self, **kwargs):
            calls.append((self.base_url, kwargs))
            if "kimi" in self.base_url:
                if behaviour["primary"] == "cut":
                    raise openai.APIConnectionError(request=httpx.Request("POST", self.base_url))
                text = "" if behaviour["primary"] == "empty" else "from K3"
            else:
                text = "from MiniMax"
            if not kwargs.get("stream"):
                return reply(text)

            async def chunks():   # a streamed reply, split mid-word
                for piece in (text[:3], text[3:]) if text else ("",):
                    yield SimpleNamespace(model=kwargs["model"], choices=[SimpleNamespace(
                        delta=SimpleNamespace(content=piece, reasoning_content="hmm"),
                        finish_reason=None)])
                yield SimpleNamespace(model=kwargs["model"], choices=[SimpleNamespace(
                    delta=SimpleNamespace(content=None, reasoning_content=None), finish_reason="stop")])
            return chunks()

    monkeypatch.setattr(openai, "AsyncOpenAI", FakeAsyncOpenAI)
    settings = SimpleNamespace(
        openai_api_key="kimi-key", openai_base_url="https://agent-gw.kimi.com/coding/v1",
        llm_model="k3-agent", vision_model="k3-agent", llm_timeout_seconds=900, llm_max_retries=0,
        fallback_api_key="mm-key", fallback_base_url="https://api.minimax.io/v1",
        fallback_llm_model="MiniMax-M3",
    )

    def ask(client):
        return asyncio.run(client.chat.completions.create(
            model=settings.llm_model, temperature=request_temperature(settings, 0.15),
            messages=[{"role": "user", "content": "x"}]))

    client = make_client(settings)
    assert ask(client).choices[0].message.content == "from MiniMax"
    (_, first), (backup_url, backup) = calls[-2], calls[-1]
    assert first["model"] == "k3-agent" and first["temperature"] == 1.0
    assert first.get("stream") is True, "Kimi requests are streamed"
    assert backup_url.endswith("minimax.io/v1") and backup["model"] == "MiniMax-M3"
    assert backup["temperature"] == 0.15, "the backup gets the temperature the task wanted"
    assert not backup.get("stream"), "MiniMax is called the ordinary way"
    assert "extra_body" not in backup, "only scene clients switch the backup's thinking off"
    assert client.last_served_by == "MiniMax-M3" and "APIConnectionError" in client.last_failover_reason

    behaviour["primary"] = "empty"
    assert ask(client).choices[0].message.content == "from MiniMax"

    behaviour["primary"] = "ok"
    before = len(calls)
    answer = ask(client)
    assert answer.choices[0].message.content == "from K3"          # reassembled from chunks
    assert answer.choices[0].finish_reason == "stop"
    assert len(calls) == before + 1 and client.last_served_by == "k3-agent"

    # A scene-generation client asks a MiniMax backup to write with thinking off.
    behaviour["primary"] = "cut"
    scene = make_client(settings, purpose="scene")
    assert ask(scene).choices[0].message.content == "from MiniMax"
    assert calls[-1][1].get("extra_body") == {"thinking": {"type": "disabled"}}

    behaviour["primary"] = "cut"
    lone = make_client(SimpleNamespace(**{**vars(settings), "fallback_api_key": None}))
    with pytest.raises(openai.APIConnectionError):
        ask(lone)


def test_backup_provider_settings_load_from_env(tmp_path, monkeypatch):
    from aetherlab.core import settings as app_settings

    monkeypatch.setenv("AETHERLAB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AETHERLAB_FALLBACK_OPENAI_API_KEY", "mm-key")
    monkeypatch.setenv("AETHERLAB_FALLBACK_OPENAI_BASE_URL", "https://api.minimax.io/v1")
    monkeypatch.setenv("AETHERLAB_FALLBACK_LLM_MODEL", "MiniMax-M3")
    s = app_settings.load_settings()
    assert (s.fallback_api_key, s.fallback_base_url, s.fallback_llm_model) == (
        "mm-key", "https://api.minimax.io/v1", "MiniMax-M3")
    for name in ("AETHERLAB_FALLBACK_OPENAI_API_KEY", "AETHERLAB_FALLBACK_OPENAI_BASE_URL",
                 "AETHERLAB_FALLBACK_LLM_MODEL"):
        monkeypatch.delenv(name)
    assert app_settings.load_settings().fallback_api_key is None


def test_study_document_parses_latex_json_and_heals_a_broken_equation(tmp_path):
    # Models write LaTeX in JSON with single backslashes: "\frac" must not become
    # a form feed. A malformed equation must cost one block, not the PDF.
    import shutil

    import pytest

    from aetherlab.core.models import ProblemRequest
    from aetherlab.services import study_document as sd

    raw = r'''{"title": "Pendulum", "restatement": "Find T.", "given": [{"symbol": "L", "value": "1\,\mathrm{m}",
    "meaning": "length, θ < 5°"}], "find": ["$T$"], "theory": [{"heading": "Small angles",
    "paragraphs": ["Use $\sin\theta \approx \theta$ — 100% & tidy_ish."], "equations": [{"latex":
    "\ddot{\theta} + \frac{g}{L}\theta = 0", "note": "SHM"}]}], "plan": ["ODE", "ω"],
    "steps": [{"title": "ω", "explanation": "Compare.", "latex": "\omega = \sqrt{g/L}"},
              {"title": "broken", "explanation": "malformed", "latex": "\frac{a}{ \left( b"}],
    "final_answer": {"statement": "T ≈ 2.01 s", "latex": "T = 2.01\,\mathrm{s}"}, "checks": [],
    "common_mistakes": [], "summary": []}'''
    doc = sd._parse_json(raw)
    eq = doc["theory"][0]["equations"][0]["latex"]
    assert "\\frac" in eq and "\\theta" in eq and not any(ord(c) < 32 for c in eq)
    assert sd._valid(doc, "problem")
    assert sd.classify("A pendulum is 1 m long. Find its period.") == "problem"
    assert sd.classify("Explain Planck's law of blackbody radiation") == "topic"
    assert sd._rich("100% of $\\theta$ & θ") == "100\\% of $\\theta$ \\& $\\theta$"

    request = ProblemRequest(prompt="A pendulum is 1 m long. Find its period.")
    built = sd.build_document(doc, "problem", request, ["Ref"], ["Simulated check"], None, "test")
    if shutil.which("pdflatex") is None:
        pytest.skip("pdflatex not installed")
    pdf, repaired, error = sd.compile_healing(built, tmp_path / "document.tex")
    assert pdf is not None and pdf.exists() and error == ""
    assert repaired == 1, "only the malformed equation is replaced"


def test_study_document_typesetting_fixes_from_live_review():
    # Each assertion is a defect seen in a real MiniMax-M3 PDF.
    from aetherlab.services import study_document as sd

    # "\\" in a display body without an environment ran the lines together.
    assert "\\begin{gathered}" in sd._display("a = 1 \\\\ b = 2")
    assert "\\begin{aligned}" in sd._display("a &= 1 \\\\ b &= 2 \\\\")
    assert sd._display("\\begin{aligned}a&=1\\\\b&=2\\end{aligned}").count("\\begin") == 1
    # "Step 1: 1. Resolve..." double numbering.
    assert sd._heading("1. Resolve the velocity") == "Resolve the velocity"
    assert sd._heading("Step 3: Apply energy") == "Apply energy"
    assert sd._heading("2D motion") == "2D motion"
    # Bare identifiers in prose become math; ✓ is a glyph, not "?"; URLs are left alone.
    assert sd._rich("a_y and R_max ✓") == "$a_{y}$ and $R_{\\mathrm{max}}$ $\\checkmark$"
    assert "$" not in sd._rich("https://en.wikipedia.org/wiki/Planck's_law")
    assert sd._rich("consistent. \\checkmark") == "consistent. $\\checkmark$"
    assert sd._rich("R = v_0^2 sin^2 x") == "R = $v_{0}^{2}$ $\\sin^{2}$ x"
    # "one.\nTwo" in JSON is a newline between list items, not a LaTeX command;
    # "\nabla" and "\nu" still are.
    parsed = sd._parse_json(r'{"title": "t", "summary": ["one.\nTwo.\nThree $\nabla \nu$"]}')
    assert sd._items(parsed["summary"]) == ["one.", "Two.", "Three $\\nabla \\nu$"]
    assert sd._rich("use \\textbf{x}") == "use \\textbackslash{}textbf\\{x\\}"
    # Loose web matches ("Taekwondo" for a kicked football) are dropped; textbooks stay.
    from aetherlab.core.models import ProblemRequest

    cites = ["OpenStax - University Physics Vol 1.pdf, p.200",
             "Projectile motion, Wikipedia: https://en.wikipedia.org/wiki/Projectile_motion",
             "Taekwondo, Wikipedia: https://en.wikipedia.org/wiki/Taekwondo",
             "Height in sports, Wikipedia: https://en.wikipedia.org/wiki/Height_in_sports",
             "Black-body radiation, Wikipedia: https://en.wikipedia.org/wiki/Black-body_radiation"]
    content = {"title": "Projectile motion of a kicked ball", "abstract": "maximum height; blackbody radiation aside"}
    kept = sd.relevant_citations(cites, content, ProblemRequest(prompt="A football is kicked at 18 m/s."))
    assert kept == [cites[0], cites[1], cites[4]]
    # A text-mode "\-" inside math overprinted "6-7".
    assert sd._math("6\\!\\-\\!7") == "6\\!-\\!7"


def test_client_retries_a_dropped_connection_only_without_a_backup(monkeypatch):
    # MiniMax drops connections for minutes at a time; one drop used to turn an AI
    # scene into the built-in template. Drops are retried (no backup configured),
    # timeouts are not, and a tool-call reply counts as a usable answer.
    import asyncio

    import httpx
    import openai
    import pytest

    from aetherlab.services import llm_client

    req = httpx.Request("POST", "https://api.minimax.io/v1")
    settings = SimpleNamespace(openai_api_key="k", openai_base_url="https://api.minimax.io/v1", llm_model="MiniMax-M3",
                               vision_model=None, llm_timeout_seconds=900, llm_max_retries=0,
                               fallback_api_key=None, fallback_base_url=None, fallback_llm_model=None)
    client = llm_client.make_client(settings)
    ok = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="hi", tool_calls=None))])
    monkeypatch.setattr(llm_client, "DROP_BACKOFF_S", 0.0)

    def primary(errors):
        calls = []

        async def create(**kwargs):
            calls.append(kwargs)
            if errors:
                raise errors.pop(0)
            return ok

        client._primary = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        return calls

    calls = primary([openai.APIConnectionError(request=req), openai.APIConnectionError(request=req)])
    assert asyncio.run(client.chat.completions.create(model="MiniMax-M3", messages=[])) is ok and len(calls) == 3
    calls = primary([openai.APITimeoutError(request=req)])
    with pytest.raises(openai.APITimeoutError):
        asyncio.run(client.chat.completions.create(model="MiniMax-M3", messages=[]))
    assert len(calls) == 1, "a timeout is never retried"
    tool_reply = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[object()]))])
    assert not llm_client._unusable(tool_reply)


def test_study_document_retries_a_dropped_connection_but_not_a_timeout(monkeypatch):
    # Live MiniMax runs dropped the connection mid-request; one drop must not
    # cost the whole document, but a timeout (already a full budget) is final.
    import asyncio

    import httpx
    import openai

    from aetherlab.core.models import ProblemRequest, RagResult
    from aetherlab.services import llm_client
    from aetherlab.services import study_document as sd

    good = ('{"title": "T", "restatement": "r", "steps": [{"title": "s", "explanation": "e", "latex": "x=1"}],'
            ' "final_answer": {"statement": "x = 1", "latex": "x=1"}}')
    req = httpx.Request("POST", "https://example.invalid")

    def fake_client(errors):
        calls = []

        async def create(**kwargs):
            calls.append(kwargs)
            if errors:
                raise errors.pop(0)
            msg = SimpleNamespace(content=good)
            return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="stop")])

        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))), calls

    async def no_sleep(_):
        return None

    monkeypatch.setattr(sd.asyncio, "sleep", no_sleep)
    settings = SimpleNamespace(openai_api_key="k", llm_model="MiniMax-M3", openai_base_url="https://api.minimax.io/v1")
    request = ProblemRequest(prompt="Find x if x = 1.")
    rag = RagResult(keywords=[], hits=[], backend="t")

    client, calls = fake_client([openai.APIConnectionError(request=req)])
    monkeypatch.setattr(llm_client, "make_client", lambda *a, **k: client)
    doc, _ = asyncio.run(sd.author_document(request, _solver(), rag, settings, "problem"))
    assert doc is not None and len(calls) == 2, "one drop, then success on the same attempt"

    client, calls = fake_client([openai.APITimeoutError(request=req), openai.APITimeoutError(request=req)])
    monkeypatch.setattr(llm_client, "make_client", lambda *a, **k: client)
    doc, reason = asyncio.run(sd.author_document(request, _solver(), rag, settings, "problem"))
    assert doc is None and len(calls) == 2 and "Timeout" in reason, "timeouts move on, never retried"


def test_study_document_without_a_model_is_built_from_the_solver(tmp_path):
    import asyncio

    from aetherlab.core.models import ProblemRequest, RagResult
    from aetherlab.services.study_document import write_study_document

    solver = _solver(summary="Damped oscillator.", derivation_steps=["m x'' + c x' + k x = 0"],
                     key_equations=["m\\ddot{x} + c\\dot{x} + kx = 0"], variables={"m": 1.0})
    request = ProblemRequest(prompt="Explain damped oscillations")
    result = asyncio.run(write_study_document(
        request, solver, RagResult(keywords=[], hits=[], backend="t"),
        SimpleNamespace(openai_api_key=None), tmp_path))
    assert result.mode == "topic" and result.authored_by.startswith("AetherLab")
    assert result.tex_path.exists() and "no model configured" in result.note
    assert result.pdf_path is not None and result.pdf_path.exists()
