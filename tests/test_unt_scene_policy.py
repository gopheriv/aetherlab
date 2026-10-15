"""UNT scaffolds must not invent a task, numeric answer or answer letter."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from aetherlab.core.models import ProblemRequest, RagResult, SolverResult
from aetherlab.services.scene_generator import (
    UNT_ACT_WEIGHTS,
    UNT_CODEGEN_APPENDIX,
    SceneGenerator,
    build_unt_storyboard,
)
from aetherlab.services.scene_validation import check_unt_gates


@pytest.mark.parametrize("target", [30.0, 60.0, 278.0, 300.0])
def test_unt_scaffold_keeps_act_weights_and_complete_timeline(target):
    board = build_unt_storyboard(target, "Circuit current")
    assert [act["name"] for act in board["acts"]] == list(UNT_ACT_WEIGHTS)
    assert len(board["timeline"]) == 8
    assert board["timeline_duration_s"] == target
    assert sum(act["duration_s"] for act in board["acts"]) == pytest.approx(target, abs=0.005)
    assert board["timeline"][0]["start_s"] == 0
    assert board["timeline"][-1]["end_s"] == target


def test_topic_agnostic_scaffold_never_fabricates_physics_or_answer():
    board = build_unt_storyboard(278, "Find current through a resistor")
    assert all(not beat["target_equation"] for act in board["acts"] for beat in act["beats"])
    text = json.dumps(board)
    for invented in ("12 m", "2 plus 8 plus 2", "Answer B", "answer letter B", "Official task"):
        assert invented not in text
    assert board["source_status"] == "practice_scaffold_unverified"


def test_codegen_policy_preserves_conditions_and_does_not_require_invented_letters():
    assert "Do not invent" in UNT_CODEGEN_APPENDIX
    assert "only when supplied" in UNT_CODEGEN_APPENDIX
    assert "unverified practice" in UNT_CODEGEN_APPENDIX


def test_actual_unt_storyboard_request_labels_unverified_practice(monkeypatch):
    captured = {}
    class Completions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            response = build_unt_storyboard(30, "Circuit current")
            response["source_status"] = "official_verified"
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(
                content=json.dumps(response)))])
    settings = SimpleNamespace(llm_model="owned-model", llm_timeout_seconds=60,
        llm_context_window=250000, openai_base_url="", openai_api_key="owned-unused-key", unt_mode=True)
    generator = SceneGenerator(settings)
    generator._client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    request = ProblemRequest("Voltage is 9 V and resistance is 3 Ohm. Find current.", duration_target_s=30)
    solver = SolverResult("I = 3 A", ["I=U/R=9/3=3 A"], ["current"], {"U": 9, "R": 3}, "owned")
    board = asyncio.run(generator.storyboard(request, solver, RagResult(["current"], [], "owned")))
    assert board is not None
    assert board["source_status"] == "practice_scaffold_unverified"
    system = captured["messages"][0]["content"]
    user = captured["messages"][1]["content"]
    assert "unverified practice" in system
    assert "only when supplied" in system
    assert "2 + 8 + 2 = 12 m" not in system
    assert request.prompt in user and solver.summary in user


NUMERIC_TASK = '''from manim import *
class Owned(Scene):
    def construct(self):
        labels = Text("Given 9 V; Find current; Solution I=U/R; Answer 3 A")
        self.add(labels)
'''


@pytest.mark.parametrize("task", [NUMERIC_TASK, NUMERIC_TASK.replace(
    "Given 9 V; Find current; Solution I=U/R; Answer 3 A",
    "Given resistance 3 Ohm and power 12 W; Find voltage; Solution U=sqrt(P R); Answer 6 V")])
def test_open_numeric_task_does_not_require_an_unsupplied_answer_letter(task):
    assert check_unt_gates(task) == []


def test_structured_choice_caller_can_require_a_supplied_letter():
    issues = check_unt_gates(NUMERIC_TASK, require_answer_letter=True)
    assert len(issues) == 1 and issues[0].startswith("[UNT:EXAM:ANSWER_LETTER]")
    assert check_unt_gates(NUMERIC_TASK.replace("Answer 3 A", "Answer B: 3 A"), require_answer_letter=True) == []


def test_chapter_skips_exam_blocks_but_still_rejects_canvas_writes():
    assert check_unt_gates("", is_task_segment=False) == []
    issues = check_unt_gates("config.pixel_width=100", is_task_segment=False)
    assert len(issues) == 1 and issues[0].startswith("[UNT:CONFIG:WRITE]")


def test_portrait_layout_remains_an_advisory():
    from aetherlab.services.manim_runtime import _is_advisory_issue

    issues = check_unt_gates(NUMERIC_TASK, is_vertical=True)
    assert len(issues) == 1 and issues[0].startswith("[UNT:LAYOUT:PORTRAIT]")
    assert _is_advisory_issue(issues[0])
    assert check_unt_gates(NUMERIC_TASK.replace("self.add(labels)", "self.add(labels.to_edge(UP))"), is_vertical=True) == []


@pytest.mark.parametrize("duration,unt_ok,cinematic_ok", [
    (159, False, False), (160, False, True), (179, False, True),
    (180, True, True), (200, True, True), (220, True, True),
    (221, False, True), (240, False, True), (241, False, False),
])
def test_unt_and_cinematic_duration_boundaries(duration, unt_ok, cinematic_ok):
    from aetherlab.services.manim_runtime import _duration_contract_delta

    assert (_duration_contract_delta(duration, 200, 0.10) == 0) is unt_ok
    assert (_duration_contract_delta(duration, 200, 0.20) == 0) is cinematic_ok
