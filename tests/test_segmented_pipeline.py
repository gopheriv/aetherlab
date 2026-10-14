from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aetherlab.core.models import ProblemRequest, RagResult, SceneBundle, SolverResult
from aetherlab.services import segmented_pipeline as segmented
from aetherlab.services.scene_generator import SceneGenerator


def _board(count: int = 12, seconds_per_beat: float = 5.0) -> dict:
    timeline = []
    for index in range(count):
        start = index * seconds_per_beat
        timeline.append({
            "id": f"A{index // 3 + 1}.B{index % 3 + 1}",
            "act": f"Act {index // 3 + 1}",
            "detail": f"Explain step {index + 1}",
            "start_s": start,
            "end_s": start + seconds_per_beat,
            "duration_s": seconds_per_beat,
            "narration_cue": f"Step {index + 1}.",
            "subtitle_cue": f"Step {index + 1}.",
        })
    return {
        "title": "One oscillator story",
        "concept": "A measured displacement reveals stored energy.",
        "creative_direction": "A laboratory measurement becomes an equation.",
        "staging": "An instrumented spring and a dark laboratory bench.",
        "palette": {"primary": "BLUE", "secondary": "TEAL", "accent": "YELLOW"},
        "hero_frame": "The live trace meets the energy equation.",
        "idle_loop": "A small marker continues along the trace.",
        "timeline_duration_s": count * seconds_per_beat,
        "timeline": timeline,
    }


def test_partition_preserves_order_and_covers_full_duration():
    board = _board()
    segments = segmented.partition_storyboard(board, 60.0, max_segment_seconds=28.0)
    assert len(segments) == 3
    assert segments[0]["start_s"] == 0
    assert segments[-1]["end_s"] == 60
    assert [beat for segment in segments for beat in segment["beat_ids"]] == [
        beat["id"] for beat in board["timeline"]
    ]
    for previous, current in zip(segments, segments[1:]):
        assert previous["end_s"] == current["start_s"]
    for segment in segments:
        assert segment["storyboard"]["staging"] == board["staging"]
        assert segment["storyboard"]["palette"] == board["palette"]
        assert segment["storyboard"]["timeline"][0]["start_s"] == 0
        assert segment["storyboard"]["timeline"][-1]["end_s"] == segment["duration_s"]


@pytest.mark.parametrize("target", [120.0, 180.0])
def test_longer_targets_partition_exactly_without_losing_beats(target):
    board = _board(count=int(target // 5), seconds_per_beat=5.0)
    segments = segmented.partition_storyboard(board, target, max_segment_seconds=28.0)
    assert len(segments) == (5 if target == 120.0 else 8)
    assert sum(segment["duration_s"] for segment in segments) == target
    assert max(segment["duration_s"] for segment in segments) <= 28.0
    assert [beat for segment in segments for beat in segment["beat_ids"]] == [
        beat["id"] for beat in board["timeline"]
    ]


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda b: b["timeline"].__setitem__(0, {**b["timeline"][0], "start_s": 0.2}), "start"),
        (lambda b: b["timeline"].__setitem__(1, {**b["timeline"][1], "start_s": 6}), "gap"),
        (lambda b: b["timeline"].pop(), "ends"),
    ],
)
def test_partition_rejects_gaps_overlap_and_incomplete_end(edit, message):
    board = _board()
    edit(board)
    with pytest.raises(segmented.SegmentPlanError, match=message):
        segmented.partition_storyboard(board, 60.0)


def test_single_oversize_beat_is_not_silently_split():
    board = _board(count=1, seconds_per_beat=45.0)
    segments = segmented.partition_storyboard(board, 45.0, max_segment_seconds=28.0)
    assert len(segments) == 1
    assert segments[0]["duration_s"] == 45.0
    assert segments[0]["beat_ids"] == ["A1.B1"]


def test_shift_subtitles_offsets_each_segment(monkeypatch):
    monkeypatch.setattr(
        "aetherlab.services.voiceover._duration_sync",
        lambda path: 20.0 if Path(path).stem == "first" else 25.0,
    )
    merged = segmented._shift_subtitles(
        [
            "1\n00:00:01,000 --> 00:00:02,000\nfirst cue\n",
            "1\n00:00:02,000 --> 00:00:03,000\nsecond cue\n",
        ],
        [Path("first.mp4"), Path("second.mp4")],
    )
    assert "1\n00:00:01,000 --> 00:00:02,000\nfirst cue" in merged
    assert "2\n00:00:22,000 --> 00:00:23,000\nsecond cue" in merged


@pytest.mark.parametrize("target, beats_per_act", [(60.0, 3), (120.0, 6), (180.0, 9)])
def test_long_storyboard_prompt_raises_global_beat_budget_without_thinking_change(
    monkeypatch, target, beats_per_act,
):
    acts = []
    for act_index in range(5):
        beat_duration = target / 5 / beats_per_act
        acts.append({
            "name": f"ACT {act_index + 1}",
            "duration_s": target / 5,
            "beats": [{
                "detail": f"beat {act_index * 3 + beat_index + 1}",
                "duration_s": beat_duration,
                "narration_cue": "Show the next physical state.",
                "anchor_cell": "C3",
            } for beat_index in range(beats_per_act)],
        })
    payload = json.dumps({"acts": acts})
    captured = {}

    class FakeCompletions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content=payload), finish_reason="stop",
            )])

    settings = SimpleNamespace(
        llm_model="test-model", openai_base_url="", openai_api_key="offline-test-key",
        llm_timeout_seconds=60, llm_context_window=250_000,
    )
    generator = SceneGenerator(settings)
    generator._client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    request = ProblemRequest("Explain oscillator energy", duration_target_s=target)
    solver = SolverResult("summary", [], ["oscillator"], {}, "test")
    rag = RagResult(["oscillator"], [], "test")
    board = asyncio.run(generator.storyboard(request, solver, rag))
    expected_min = max(6, int(target / 5 + 0.999))
    expected_max = max(expected_min, int(target / 3.75 + 0.999))
    assert board is not None and len(board["timeline"]) == 5 * beats_per_act
    storyboard_prompt = captured["messages"][0]["content"]
    assert "duration-scaled global beat count" in storyboard_prompt
    user_prompt = captured["messages"][1]["content"]
    assert f"{expected_min}–{expected_max} meaningful visual beats" in user_prompt
    assert captured["max_tokens"] == min(32768, max(4096, 2048 + expected_max * 256))
    assert "do not compress the explanation to the 30-second beat count" in captured["messages"][0]["content"]
    assert generator._minimax_thinking is False


def test_segmented_run_resumes_valid_segments_without_regenerating(tmp_path, monkeypatch):
    settings = SimpleNamespace(
        data_dir=tmp_path, openai_api_key="configured-but-not-used-by-fakes",
        llm_model="test-model", render_mode="local", narration_enabled=False,
        tts_voice="voice", tts_rate="0%",
    )
    request = ProblemRequest("Explain spring oscillator", duration_target_s=60.0)
    solver = SolverResult(
        summary="A spring oscillator", derivation_steps=["F=-kx"],
        keywords=["oscillator"], variables={"m": 1.0, "k": 4.0}, model_name="test",
    )
    rag = RagResult(keywords=["oscillator"], hits=[], backend="test")
    board = _board()
    calls = {"generated": 0, "rendered": 0, "assembled": 0}

    async def fake_storyboard(*_args, **_kwargs):
        return board

    monkeypatch.setattr(SceneGenerator, "storyboard", fake_storyboard)

    class Runtime:
        async def generate_scene_async(self, req, _solver, _rag, _settings, **kwargs):
            calls["generated"] += 1
            scene_board = kwargs["locked_storyboard"]
            return SceneBundle(
                class_name="AetherLabScene", code="class AetherLabScene: pass",
                engine="manim-community", status="compiled", storyboard=scene_board,
            )

        async def render_scene_with_repair(self, bundle, *_args, **_kwargs):
            calls["rendered"] += 1
            source = tmp_path / f"source_{calls['rendered']}.mp4"
            source.write_bytes(b"x" * 2048)
            bundle.video_path = str(source)
            bundle.status = "rendered"
            bundle.subtitle_path = ""
            return bundle

    async def fake_duration(path):
        if Path(path).name == "lesson.mp4":
            return 60.0
        # Partition lengths are 25, 25, and 10 seconds.
        return 25.0 if "segment_001" in str(path) or "segment_002" in str(path) else 10.0

    async def fake_assemble(clips, out_path, **_kwargs):
        calls["assembled"] += 1
        out_path = Path(out_path)
        out_path.write_bytes(b"y" * 4096)
        return out_path

    monkeypatch.setattr(segmented, "_valid_video", lambda path, expected_hash="": Path(path).is_file())
    monkeypatch.setattr("aetherlab.services.voiceover.get_duration", fake_duration)
    monkeypatch.setattr("aetherlab.services.assembly.assemble_lesson", fake_assemble)
    monkeypatch.setattr("aetherlab.services.voiceover._duration_sync", lambda _path: 20.0)

    first = asyncio.run(segmented.render_segmented_scene(
        request, solver, rag, settings, runtime=Runtime(), max_segment_seconds=28.0,
    ))
    assert first.status == "rendered"
    assert calls == {"generated": 3, "rendered": 3, "assembled": 1}
    manifest_path = next(tmp_path.glob("segmented_scenes/*/manifest.json"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["state"] == "complete"
    assert all(segment["state"] == "rendered" for segment in manifest["segments"])

    second = asyncio.run(segmented.render_segmented_scene(
        request, solver, rag, settings, runtime=Runtime(), max_segment_seconds=28.0,
    ))
    assert second.status == "rendered"
    assert calls == {"generated": 3, "rendered": 3, "assembled": 1}


def test_long_ai_pipeline_does_not_claim_template_as_success(tmp_path):
    settings = SimpleNamespace(
        data_dir=tmp_path, openai_api_key=None, llm_model="test-model",
    )
    result = asyncio.run(segmented.render_segmented_scene(
        ProblemRequest("Explain", duration_target_s=60.0),
        SolverResult("summary", [], [], {}, "test"),
        RagResult([], [], "test"), settings,
    ))
    assert result.status == "incomplete"
    assert result.used_fallback is False
    assert "no segmented fallback" in result.diagnostics[0]


@pytest.mark.parametrize("target, expected_segments", [(120.0, 5), (180.0, 8)])
def test_long_form_assembly_requires_every_requested_segment(
    tmp_path, monkeypatch, target, expected_segments,
):
    settings = SimpleNamespace(
        data_dir=tmp_path, openai_api_key="offline-fake", llm_model="test-model",
        render_mode="local", narration_enabled=False, tts_voice="voice", tts_rate="0%",
    )
    request = ProblemRequest("Explain spring oscillator", duration_target_s=target)
    solver = SolverResult("A spring oscillator", ["F=-kx"], ["oscillator"], {}, "test")
    rag = RagResult(["oscillator"], [], "test")
    board = _board(count=int(target // 5), seconds_per_beat=5.0)
    counters = {"generated": 0, "rendered": 0, "assembled": 0}

    async def fake_storyboard(*_args, **_kwargs):
        return board

    monkeypatch.setattr(SceneGenerator, "storyboard", fake_storyboard)

    class Runtime:
        async def generate_scene_async(self, _req, *_args, **kwargs):
            counters["generated"] += 1
            return SceneBundle(
                class_name="AetherLabScene", code="class AetherLabScene: pass",
                engine="manim-community", status="compiled",
                storyboard=kwargs["locked_storyboard"],
            )

        async def render_scene_with_repair(self, bundle, *_args, **_kwargs):
            counters["rendered"] += 1
            source = tmp_path / f"segment_source_{counters['rendered']}.mp4"
            source.write_bytes(b"x" * 2048)
            bundle.video_path = str(source)
            bundle.status = "rendered"
            return bundle

    async def fake_duration(path):
        if Path(path).name == "lesson.mp4":
            return target
        index = int(Path(path).parent.name[-3:]) - 1
        return float(board["timeline"][0]["duration_s"] * 5) if index < expected_segments - 1 else (
            target - 25.0 * (expected_segments - 1)
        )

    async def fake_assemble(clips, out_path, **_kwargs):
        counters["assembled"] += 1
        assert len(clips) == expected_segments
        Path(out_path).write_bytes(b"y" * 4096)
        return Path(out_path)

    monkeypatch.setattr(segmented, "_valid_video", lambda path, expected_hash="": Path(path).is_file())
    monkeypatch.setattr("aetherlab.services.voiceover.get_duration", fake_duration)
    monkeypatch.setattr("aetherlab.services.assembly.assemble_lesson", fake_assemble)
    monkeypatch.setattr("aetherlab.services.voiceover._duration_sync", lambda _path: 20.0)

    result = asyncio.run(segmented.render_segmented_scene(
        request, solver, rag, settings, runtime=Runtime(), max_segment_seconds=28.0,
    ))
    assert result.status == "rendered"
    assert counters == {
        "generated": expected_segments,
        "rendered": expected_segments,
        "assembled": 1,
    }


def test_command_bar_exposes_only_bounded_duration_choices(monkeypatch):
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6 import QtWidgets

    from aetherlab.ui.widgets import CommandBar

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    bar = CommandBar()
    assert bar.get_duration_target() == 30.0
    assert [bar._duration.itemData(i) for i in range(bar._duration.count())] == [
        30.0, 60.0, 120.0, 180.0,
    ]
    assert [bar._duration.itemText(i) for i in range(bar._duration.count())] == [
        "30 сек", "1 мин", "2 мин", "3 мин",
    ]
    bar.set_language("en")
    assert [bar._duration.itemText(i) for i in range(bar._duration.count())] == [
        "30 sec", "60 sec", "2 min", "3 min",
    ]
    bar._duration.setCurrentIndex(bar._duration.findData(120.0))
    assert bar.get_duration_target() == 120.0
    bar.deleteLater()
    app.processEvents()


def test_resumed_narrated_lesson_keeps_every_segment_subtitle(tmp_path, monkeypatch):
    # Review fix: reused segments did not add their cues to the merged track, so
    # a fully resumed narrated lesson came back "incomplete" with empty subtitles.
    settings = SimpleNamespace(
        data_dir=tmp_path, openai_api_key="configured-but-not-used-by-fakes",
        llm_model="test-model", render_mode="local", narration_enabled=True,
        tts_voice="voice", tts_rate="0%",
    )
    request = ProblemRequest("Explain spring oscillator", duration_target_s=60.0)
    solver = SolverResult(summary="A spring oscillator", derivation_steps=["F=-kx"],
                          keywords=["oscillator"], variables={"m": 1.0}, model_name="test")
    rag = RagResult(keywords=["oscillator"], hits=[], backend="test")
    board = _board()

    async def fake_storyboard(*_args, **_kwargs):
        return board

    monkeypatch.setattr(SceneGenerator, "storyboard", fake_storyboard)
    rendered = {"n": 0}

    class Runtime:
        async def generate_scene_async(self, req, _solver, _rag, _settings, **kwargs):
            return SceneBundle(class_name="AetherLabScene", code="class AetherLabScene: pass",
                               engine="manim-community", status="compiled",
                               storyboard=kwargs["locked_storyboard"])

        async def render_scene_with_repair(self, bundle, *_args, **_kwargs):
            rendered["n"] += 1
            source = tmp_path / f"narrated_{rendered['n']}.mp4"
            source.write_bytes(b"x" * 2048)
            srt = tmp_path / f"narrated_{rendered['n']}.srt"
            srt.write_text(f"1\n00:00:01,000 --> 00:00:02,000\ncue {rendered['n']}\n", encoding="utf-8")
            bundle.video_path, bundle.status = str(source), "rendered"
            bundle.silent_video_path, bundle.narration_text = str(source), f"line {rendered['n']}"
            bundle.subtitle_path = str(srt)
            bundle.narration_sync = {"method": "storyboard_beat_windows",
                                     "max_boundary_overrun_s": 0.0, "max_rate_adjustment_pct": 0}
            return bundle

    async def fake_duration(path):
        if Path(path).name == "lesson.mp4":
            return 60.0
        return 25.0 if "segment_001" in str(path) or "segment_002" in str(path) else 10.0

    async def fake_assemble(clips, out_path, **_kwargs):
        Path(out_path).write_bytes(b"y" * 4096)
        return Path(out_path)

    monkeypatch.setattr(segmented, "_valid_video", lambda path, expected_hash="": Path(path).is_file())
    monkeypatch.setattr("aetherlab.services.voiceover.get_duration", fake_duration)
    monkeypatch.setattr("aetherlab.services.assembly.assemble_lesson", fake_assemble)
    monkeypatch.setattr("aetherlab.services.voiceover._duration_sync", lambda _path: 20.0)

    first = asyncio.run(segmented.render_segmented_scene(request, solver, rag, settings, runtime=Runtime(),
        max_segment_seconds=28.0))
    assert first.status == "rendered", first.diagnostics[-1:]
    second = asyncio.run(segmented.render_segmented_scene(request, solver, rag, settings, runtime=Runtime(),
        max_segment_seconds=28.0))
    assert rendered["n"] == 3                                  # all three reused
    assert second.status == "rendered", second.diagnostics[-1:]
    merged = Path(second.subtitle_path).read_text(encoding="utf-8")
    assert all(f"cue {n}" in merged for n in (1, 2, 3))


def test_beat_floor_applies_only_to_long_form_storyboards(monkeypatch):
    # Review fix: the floor discarded usable 30 s storyboards with five beats,
    # dropping them to the timeline-less single-call path.
    from aetherlab.services import scene_generator

    five_beats = {"acts": [{"name": "A", "duration_s": 30,
                            "beats": [{"detail": f"b{i}", "duration_s": 6} for i in range(5)]}]}

    class _Resp:
        def __init__(self, text):
            self.choices = [SimpleNamespace(message=SimpleNamespace(content=text))]

    async def create(**_kwargs):
        return _Resp(json.dumps(five_beats))

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    settings = SimpleNamespace(openai_api_key="k", llm_model="MiniMax-M3", openai_base_url="",
                               data_dir=None)
    generator = scene_generator.SceneGenerator(settings)
    generator._client = client
    solver = SolverResult(summary="s", derivation_steps=[], keywords=[], variables={}, model_name="t")
    rag = RagResult(keywords=[], hits=[], backend="none")
    short = asyncio.run(generator.storyboard(ProblemRequest("p", duration_target_s=30.0), solver, rag))
    assert short is not None and len(short["timeline"]) == 5
    long_ = asyncio.run(generator.storyboard(ProblemRequest("p", duration_target_s=60.0), solver, rag))
    assert long_ is None                                        # 60 s needs >= 12 beats


def test_pipeline_resumes_segmented_lesson_instead_of_rerendering_joined_code(tmp_path, monkeypatch):
    # Review fix: a cached segmented lesson whose video was missing was re-rendered
    # from its joined code (every segment's AetherLabScene), silently producing
    # only the last segment.
    from dataclasses import replace as dc_replace

    from aetherlab.core.cache import SessionCache
    from aetherlab.core.settings import load_settings
    from aetherlab.services.pipeline import AetherLabPipeline

    settings = dc_replace(load_settings(), data_dir=tmp_path, cache_path=tmp_path / "cache.sqlite3",
                          openai_api_key="k")
    request = ProblemRequest("Explain spring oscillator", duration_target_s=60.0)
    solver = SolverResult(summary="s", derivation_steps=[], keywords=["k"], variables={}, model_name="t")
    rag = RagResult(keywords=["k"], hits=[], backend="test")
    pipeline = AetherLabPipeline(settings)
    pipeline.cache = SessionCache(settings.cache_path)
    key = pipeline.cache.ensure_request(request)
    pipeline.cache.store_solver(key, solver)
    pipeline.cache.store_rag(key, rag)
    pipeline.cache.store_scene(key, SceneBundle(
        "AetherLabSegmentedScene", "class AetherLabScene: ...\n\nclass AetherLabScene: ...",
        "manim-community", "rendered", video_path=str(tmp_path / "gone.mp4")))

    async def no_ingest():
        return None

    pipeline._ensure_ingested = no_ingest
    resumed = tmp_path / "lesson.mp4"
    calls = {"segmented": 0, "rerender": 0}

    async def fake_segmented(*_args, **_kwargs):
        calls["segmented"] += 1
        resumed.write_bytes(b"x")
        return SceneBundle("AetherLabSegmentedScene", "joined", "manim-community", "rendered",
                           video_path=str(resumed))

    async def forbidden_rerender(*_args, **_kwargs):
        calls["rerender"] += 1
        raise AssertionError("joined segment code must not be re-rendered")

    monkeypatch.setattr(segmented, "render_segmented_scene", fake_segmented)
    monkeypatch.setattr("aetherlab.services.pipeline._video_exists", lambda path: Path(path).is_file())
    pipeline.manim.render_scene_with_repair = forbidden_rerender
    monkeypatch.setattr(pipeline.manim, "detect_engine", lambda: ("manim-community", []))
    result = asyncio.run(pipeline.run(request))
    assert calls == {"segmented": 1, "rerender": 0}
    assert result.scene.video_path == str(resumed)
