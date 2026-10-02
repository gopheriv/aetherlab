"""Voice-first sync: measured speech sets the beat windows; the dry run checks them."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from aetherlab.core.models import SceneBundle
from aetherlab.services import scene_preflight, voiceover
from aetherlab.services.scene_generator import (
    SPEECH_TAIL_S,
    SceneGenerator,
    fit_timeline_to_speech,
    is_speech_timed,
    schedule_storyboard_timeline,
)
from aetherlab.services.scene_preflight import beat_drift_lines, beat_timings, preflight_scene


def _board(cues: list[str], target: float = 12.0) -> dict:
    return schedule_storyboard_timeline({
        "acts": [
            {"name": "Setup", "duration_s": 1,
             "beats": [{"detail": "a", "narration_cue": cues[0], "duration_s": 3},
                       {"detail": "b", "narration_cue": cues[1], "duration_s": 1}]},
            {"name": "Payoff", "duration_s": 1,
             "beats": [{"detail": "c", "narration_cue": cues[2], "duration_s": 2}]},
        ],
    }, target)


# ── timing maths ──────────────────────────────────────────────────────────

def test_every_beat_gets_its_spoken_length_and_the_total_is_kept():
    board = _board(["Hot iron glows red.", "Now hotter.", "The peak moves to blue as T rises."])
    speech = [1.4, 4.1, 2.6]           # the short second line is spoken slowly
    fitted = fit_timeline_to_speech(board, speech, 12.0)
    assert fitted is not None and is_speech_timed(fitted)
    timeline = fitted["timeline"]
    assert [b["id"] for b in timeline] == ["A1.B1", "A1.B2", "A2.B1"]
    for beat, seconds in zip(timeline, speech):
        assert beat["duration_s"] >= seconds + SPEECH_TAIL_S - 1e-6
    assert timeline[0]["start_s"] == 0.0 and timeline[-1]["end_s"] == 12.0
    for before, after in zip(timeline, timeline[1:]):
        assert before["end_s"] == after["start_s"]
    # Estimated windows would have given the 2-word line about 1 s.
    assert board["timeline"][1]["duration_s"] < 4.1
    # Acts follow their beats.
    assert fitted["acts"][0]["end_s"] == timeline[1]["end_s"]
    assert fitted["acts"][1]["start_s"] == timeline[2]["start_s"]


def test_spare_time_goes_to_beats_the_director_made_longer():
    board = _board(["One.", "Two.", "Three."])
    base = [b["duration_s"] for b in board["timeline"]]
    assert base == pytest.approx([4.5, 1.5, 6.0])    # director's weights within each act
    fitted = fit_timeline_to_speech(board, [0.5, 0.5, 0.5], 12.0)
    durations = [b["duration_s"] for b in fitted["timeline"]]
    assert durations[2] > durations[0] > durations[1]
    assert sum(durations) == pytest.approx(12.0)


def test_lines_longer_than_the_target_are_declined_not_squeezed():
    board = _board(["a", "b", "c"])
    assert fit_timeline_to_speech(board, [5.0, 5.0, 5.0], 12.0) is None


def test_generator_speeds_the_whole_voice_up_evenly_only_when_needed(tmp_path, monkeypatch):
    board = _board(["a b c", "d e f", "g h i"])
    rates_tried: list[str] = []

    async def fake_measure(lines, cache_dir, voice, rate, **_kwargs):
        rates_tried.append(rate)
        return [4.5, 4.5, 4.5] if rate == "+8%" else [3.6, 3.6, 3.6]

    monkeypatch.setattr(voiceover, "measure_speech", fake_measure)
    monkeypatch.setattr(voiceover, "narration_available", lambda: True)
    settings = SimpleNamespace(narration_enabled=True, tts_voice="v", tts_rate="+8%",
                               data_dir=tmp_path, openai_api_key="k", llm_model="m")
    fitted = asyncio.run(SceneGenerator(settings).fit_board_to_speech(board, 12.0))
    assert rates_tried == ["+8%", "+18%"]
    assert fitted["speech"]["rate"] == "+18%" and is_speech_timed(fitted)


def test_narration_off_or_tts_failure_keeps_the_estimated_windows(tmp_path, monkeypatch):
    board = _board(["a", "b", "c"])
    off = SimpleNamespace(narration_enabled=False, data_dir=tmp_path)
    assert asyncio.run(SceneGenerator(off).fit_board_to_speech(board, 12.0)) is board

    async def failing(*_args, **_kwargs):
        return None

    monkeypatch.setattr(voiceover, "measure_speech", failing)
    monkeypatch.setattr(voiceover, "narration_available", lambda: True)
    on = SimpleNamespace(narration_enabled=True, tts_voice="v", tts_rate="+0%", data_dir=tmp_path)
    assert asyncio.run(SceneGenerator(on).fit_board_to_speech(board, 12.0)) is board


def test_segments_keep_the_measured_windows():
    from aetherlab.services.segmented_pipeline import partition_storyboard

    cues = [f"line {i}" for i in range(3)]
    fitted = fit_timeline_to_speech(_board(cues, 60.0), [6.0, 9.0, 12.0], 60.0)
    fitted["speech"] = {"voice": "v", "rate": "+8%", "cache_dir": "c"}
    for segment in partition_storyboard(fitted, 60.0, max_segment_seconds=28.0):
        local = segment["storyboard"]
        assert is_speech_timed(local) and local["speech"]["rate"] == "+8%"


# ── the measured clips are the clips that play ────────────────────────────

def _ffmpeg() -> str:
    exe = voiceover._ffmpeg_exe()
    if not exe:
        pytest.skip("no bundled ffmpeg")
    return exe


def _tone(path: Path, seconds: float) -> None:
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"sine=frequency=440:duration={seconds}", "-c:a", "libmp3lame", str(path)],
                   check=True)


def test_final_mix_reuses_the_measured_clip_without_rate_changes(tmp_path, monkeypatch):
    ffmpeg = _ffmpeg()
    video = tmp_path / "scene.mp4"
    subprocess.run([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=black:s=320x180:d=12:r=15", "-pix_fmt", "yuv420p", str(video)],
                   check=True)
    cache = tmp_path / "speech_cache"
    cues = ["Hot iron glows red.", "Now hotter.", "The peak moves to blue."]
    lengths = {cues[0]: 1.4, cues[1]: 4.1, cues[2]: 2.6}
    synth_calls: list[str] = []

    async def fake_synthesize(text, out_path, voice, rate):
        synth_calls.append(text)
        _tone(Path(out_path), lengths[" ".join(text.split())])
        return Path(out_path)

    monkeypatch.setattr(voiceover, "synthesize", fake_synthesize)
    monkeypatch.setattr(voiceover, "narration_available", lambda: True)
    speech = asyncio.run(voiceover.measure_speech(cues, cache, "v", "+8%"))
    assert speech == pytest.approx([1.4, 4.1, 2.6], abs=0.08)
    board = fit_timeline_to_speech(_board(cues), speech, 12.0)

    result = asyncio.run(voiceover.add_timed_beat_voiceover(
        video, board, tmp_path / "out", voice="v", rate="+8%", speech_cache_dir=cache,
    ))
    assert result is not None, "voice-first windows must always fit their own clips"
    assert len(synth_calls) == 3                     # measured once, never re-synthesized
    assert result["sync"]["max_rate_adjustment_pct"] == 0
    assert result["sync"]["max_boundary_overrun_s"] == 0.0


# ── the dry run measures when each beat really starts ─────────────────────

_MARKED = '''from manim import *
class S(Scene):
    def helper(self, mob):
        self.play(mob.animate.shift(UP), run_time=1.0)

    def construct(self):
        dot = Dot()
        # BEAT A1.B1 | 0.00-2.00 s
        self.play(FadeIn(dot), run_time=1.5)
        self.wait(0.5)
        # BEAT A1.B2 | 2.00-4.00 s
        self.helper(dot)
        self.wait(1.0)
        # BEAT A2.B1 | 4.00-6.00 s
        self.play(dot.animate.shift(DOWN), run_time=2.0)
'''


def test_dry_run_reports_each_beat_start_on_time():
    report = preflight_scene(_MARKED, "S")
    assert report.ran and report.ok, report.error or report.note
    timings = {t.beat_id: t for t in beat_timings(_MARKED, report)}
    assert set(timings) == {"A1.B1", "A1.B2", "A2.B1"}
    for timing in timings.values():                 # the helper's play counts for A1.B2
        assert timing.drift_s == pytest.approx(0.0, abs=0.01)
    assert beat_drift_lines(list(timings.values()), 0.5) == []


def test_dry_run_catches_a_late_beat():
    late = _MARKED.replace("self.wait(0.5)", "self.wait(1.7)")
    report = preflight_scene(late, "S")
    assert report.ran and report.ok, report.error or report.note
    lines = beat_drift_lines(beat_timings(late, report), 0.5)
    assert lines and all("+1.20s" in line for line in lines)
    assert {line.split()[1] for line in lines} == {"A1.B2", "A2.B1"}


def test_pipeline_repairs_drift_only_when_it_helps(tmp_path, monkeypatch):
    from aetherlab.services import manim_runtime
    from aetherlab.services.manim_runtime import ManimRuntime

    late = _MARKED.replace("self.wait(0.5)", "self.wait(1.7)")
    repairs: list[str] = []

    async def fake_repair(self, code, instruction, class_name, full_scene=False):
        repairs.append(instruction)
        return _MARKED                               # the on-time version

    monkeypatch.setattr(SceneGenerator, "repair", fake_repair)
    monkeypatch.setattr(manim_runtime, "_blocking_scene_issues", lambda code, timeline: (True, []))
    settings = SimpleNamespace(openai_api_key="k", narration_enabled=True, llm_model="m",
                               data_dir=tmp_path)
    bundle = SceneBundle("S", late, "manim-community", "compiled")
    out = asyncio.run(ManimRuntime(settings)._preflight_and_repair(bundle, settings, None))
    assert len(repairs) == 1 and "[PREFLIGHT:BEAT_DRIFT] A1.B2" in repairs[0]
    assert out.code == _MARKED
    assert any("timing repair kept: largest beat drift 1.20s -> 0.00s" in d for d in out.diagnostics)

    # Narration off: drift is reported but no repair call is spent on it.
    repairs.clear()
    quiet = SimpleNamespace(openai_api_key="k", narration_enabled=False, llm_model="m",
                            data_dir=tmp_path)
    bundle = SceneBundle("S", late, "manim-community", "compiled")
    out = asyncio.run(ManimRuntime(quiet)._preflight_and_repair(bundle, quiet, None))
    assert repairs == [] and out.code == late
    assert any("largest drift 1.20s" in d for d in out.diagnostics)


def test_report_without_events_measures_nothing():
    assert beat_timings(_MARKED, scene_preflight.PreflightReport(ran=True, ok=True)) == []


def test_long_lesson_retries_one_unusable_plan(tmp_path, monkeypatch):
    # Live run 2026-10-02: one bad 60 s plan reply stopped the whole lesson.
    from aetherlab.core.models import ProblemRequest, RagResult, SolverResult
    from aetherlab.services import segmented_pipeline as segmented

    calls = {"n": 0}

    async def flaky_storyboard(*_args, **_kwargs):
        calls["n"] += 1
        return None

    monkeypatch.setattr(SceneGenerator, "storyboard", flaky_storyboard)
    settings = SimpleNamespace(data_dir=tmp_path, openai_api_key="k", llm_model="m",
                               render_mode="local", narration_enabled=False,
                               tts_voice="v", tts_rate="+0%")
    messages: list[str] = []
    result = asyncio.run(segmented.render_segmented_scene(
        ProblemRequest("Explain", duration_target_s=60.0),
        SolverResult("summary", [], [], {}, "test"), RagResult([], [], "test"), settings,
        progress=messages.append,
    ))
    assert calls["n"] == 2 and result.status == "incomplete"
    assert any("asking for the full plan again" in m for m in messages)


def test_segment_beat_markers_are_accepted():
    # Live run 2026-10-02: every long-video segment failed with
    # "[TIMING:BEAT_MARKERS] missing S1.B1 ..." because the checker only knew
    # A<act>.B<n> names, so no 60 s+ lesson could ever pass validation.
    from aetherlab.services.scene_validation import check_timeline_markers
    from aetherlab.services.segmented_pipeline import partition_storyboard

    board = _board(["one", "two", "three"], 60.0)
    segment = partition_storyboard(board, 60.0, max_segment_seconds=28.0)[0]
    timeline = segment["storyboard"]["timeline"]
    assert timeline[0]["id"] == "S1.B1"
    code = "\n".join(
        f"        # BEAT {b['id']} | {b['start_s']:.2f}-{b['end_s']:.2f} s\n        self.wait(1)"
        for b in timeline
    )
    assert check_timeline_markers(code, timeline) == []
    report = scene_preflight.PreflightReport(ran=True, ok=True, events=[[3, 0.0, 1.0]])
    assert [t.beat_id for t in beat_timings(code, report)] == ["S1.B1"]


def test_over_long_narration_is_tightened_then_fitted(tmp_path, monkeypatch):
    # Live run 2026-10-02: MiniMax wrote more narration than 60 s allows even
    # at +20%; the lines are now rewritten to a measured word budget.
    import json as _json

    board = _board(["one two three four five six seven eight",
                    "nine ten eleven twelve thirteen fourteen fifteen sixteen",
                    "a b c d e f g h"])

    async def fake_measure(lines, cache_dir, voice, rate, **_kwargs):
        return [0.6 * len(line.split()) for line in lines]   # 4.8 s per long line

    seen: dict = {}

    class _Completions:
        async def create(self, **kwargs):
            seen["request"] = kwargs["messages"][1]["content"]
            reply = {"A1.B1": "one two three", "A1.B2": "nine ten eleven", "A2.B1": "a b c"}
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content=_json.dumps(reply)), finish_reason="stop")])

    monkeypatch.setattr(voiceover, "measure_speech", fake_measure)
    monkeypatch.setattr(voiceover, "narration_available", lambda: True)
    settings = SimpleNamespace(narration_enabled=True, tts_voice="v", tts_rate="+0%",
                               data_dir=tmp_path, openai_api_key="k", llm_model="MiniMax-M3",
                               openai_base_url="https://api.minimax.io/v1")
    generator = SceneGenerator(settings)
    generator._client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
    fitted = asyncio.run(generator.fit_board_to_speech(board, 12.0))   # 14.4 s of speech > 12 s
    assert is_speech_timed(fitted)
    assert [b["narration_cue"] for b in fitted["timeline"]] == ["one two three", "nine ten eleven", "a b c"]
    assert "(max " in seen["request"] and "A1.B2" in seen["request"]
