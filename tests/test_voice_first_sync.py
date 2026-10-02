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
    assert any("timing repair kept: worst timing error 1.20s -> 0.00s" in d for d in out.diagnostics)

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


def test_default_segments_are_short_enough_for_the_cloud_budget():
    # Live 2026-10-02: 27 s segments carried ~9 beats / 24 plays (cloud limit 16).
    from aetherlab.services import segmented_pipeline as segmented

    board = schedule_storyboard_timeline({"acts": [{"name": "A", "duration_s": 60, "beats": [
        {"detail": str(i), "narration_cue": f"line {i}", "duration_s": 1} for i in range(22)
    ]}]}, 60.0)
    segments = segmented.partition_storyboard(board, 60.0)
    assert all(item["duration_s"] <= segmented.DEFAULT_SEGMENT_MAX_S + 1e-6 for item in segments)
    assert all(len(item["beat_ids"]) <= 6 for item in segments)
    assert segmented._segment_play_budget(segments[0]) <= 14


# ── cloud LaTeX detection (live 2026-10-02) ───────────────────────────────

@pytest.mark.parametrize("code, needs", [
    ("value = DecimalNumber(5800, num_decimal_places=0)", True),
    ("ax = Axes(x_range=[0, 3], axis_config={'include_numbers': True})", True),
    ("labels = ax.get_axis_labels(x_label='x', y_label='y')", True),
    ("eq = MathTex(r'E = h\\nu')", True),
    ("n = Integer(3)", True),
    ("t = Text('Planck')", False),
    ("dot = Dot(); ring = Circle()", False),
    ("myTitle(3)", False),
])
def test_cloud_render_installs_latex_for_every_latex_object(code, needs, monkeypatch):
    # A DecimalNumber readout failed three cloud renders with
    # FileNotFoundError: 'latex', because only MathTex/Tex were detected.
    from aetherlab.services import render_backend

    monkeypatch.setattr(render_backend, "_latex_missing_seen", False)
    assert render_backend._needs_latex(code) is needs


def test_one_missing_latex_failure_makes_later_renders_install_it(monkeypatch):
    from aetherlab.services import render_backend

    monkeypatch.setattr(render_backend, "_latex_missing_seen", False)
    assert render_backend._needs_latex("dot = Dot()") is False
    log = "FileNotFoundError: [Errno 2] No such file or directory: 'latex'"
    assert render_backend._note_missing_latex(log) is True
    assert render_backend._needs_latex("dot = Dot()") is True
    assert render_backend._note_missing_latex("ValueError: something else") is False


def test_api_key_byte_order_mark_is_stripped(monkeypatch):
    # Live 2026-10-02: a key piped through PowerShell carried a UTF-8 BOM and
    # every MiniMax request failed with "'ascii' codec can't encode '﻿'".
    from aetherlab.core import settings as settings_module

    monkeypatch.setenv("AETHERLAB_OPENAI_API_KEY", "﻿sk-cp-example-key \n")
    assert settings_module.load_settings().openai_api_key == "sk-cp-example-key"


# ── repairs keep the beat markers (live cloud run 2026-10-02) ─────────────

_ORIGINAL_WITH_MARKERS = """from manim import *
class AetherLabScene(Scene):
    def construct(self):
        glow = Circle(color=ORANGE)
        # BEAT S2.B1 | 0.00-3.00 s
        self.play(FadeIn(glow), run_time=1.5)
        self.wait(1.5)
        # BEAT S2.B2 | 3.00-6.00 s
        self.play(glow.animate.scale(1.5), run_time=1.5)
        self.wait(1.5)
        # BEAT S2.B3 | 6.00-8.00 s
        # BEAT S2.B4 | 8.00-10.00 s
        self.play(glow.animate.set_color(YELLOW), run_time=2.0)
        self.wait(1.5)
"""


def test_markers_a_repair_dropped_are_restored_in_place():
    from aetherlab.services.scene_validation import check_timeline_markers, restore_beat_markers

    repaired = "\n".join(
        line for line in _ORIGINAL_WITH_MARKERS.splitlines() if "# BEAT" not in line
    ).replace("Circle(color=ORANGE)", "Circle(color=ORANGE, radius=1.2)") + "\n"
    restored = restore_beat_markers(_ORIGINAL_WITH_MARKERS, repaired)
    timeline = [
        {"id": "S2.B1", "start_s": 0.0, "end_s": 3.0},
        {"id": "S2.B2", "start_s": 3.0, "end_s": 6.0},
        {"id": "S2.B3", "start_s": 6.0, "end_s": 8.0},
        {"id": "S2.B4", "start_s": 8.0, "end_s": 10.0},
    ]
    assert check_timeline_markers(restored, timeline) == []
    lines = restored.splitlines()
    # Each marker sits right before the line it preceded; the two adjacent
    # markers stay together in order, and the second self.wait(1.5) keeps its own.
    assert lines[lines.index("        # BEAT S2.B2 | 3.00-6.00 s") + 1].strip().startswith(
        "self.play(glow.animate.scale")
    b3 = lines.index("        # BEAT S2.B3 | 6.00-8.00 s")
    assert lines[b3 + 1] == "        # BEAT S2.B4 | 8.00-10.00 s"
    assert "radius=1.2" in restored


def test_restore_leaves_code_alone_when_markers_survive_or_anchors_vanish():
    from aetherlab.services.scene_validation import restore_beat_markers

    assert restore_beat_markers(_ORIGINAL_WITH_MARKERS, _ORIGINAL_WITH_MARKERS) == _ORIGINAL_WITH_MARKERS
    rewritten = "from manim import *\nclass AetherLabScene(Scene):\n    def construct(self):\n        self.wait(10)\n"
    assert restore_beat_markers(_ORIGINAL_WITH_MARKERS, rewritten) == rewritten


def test_colorsys_is_an_allowed_import():
    from aetherlab.services.code_safety import validate_code_safety

    safe, issues = validate_code_safety("import colorsys\nfrom manim import *\nr, g, b = colorsys.hsv_to_rgb(0.1, 1, 1)\n")
    assert safe, issues


def test_a_failed_segment_gets_a_second_generation(tmp_path, monkeypatch):
    # Live cloud run 2026-10-02: segment 2 of 5 failed its checks once and the
    # whole lesson stopped.
    from aetherlab.core.models import ProblemRequest, RagResult, SolverResult
    from aetherlab.services import segmented_pipeline as segmented

    board = schedule_storyboard_timeline({"acts": [{"name": "A", "duration_s": 30, "beats": [
        {"detail": str(i), "narration_cue": f"line {i}", "duration_s": 1} for i in range(4)
    ]}]}, 50.0)

    async def fake_storyboard(*_args, **_kwargs):
        return board

    monkeypatch.setattr(SceneGenerator, "storyboard", fake_storyboard)
    tries = {"n": 0}

    class Runtime:
        async def generate_scene_async(self, *_args, **kwargs):
            tries["n"] += 1
            if tries["n"] == 1:
                return SceneBundle("AetherLabScene", "", "manim-community", "compiled",
                                   used_fallback=True, diagnostics=["validation failed"])
            return SceneBundle("AetherLabScene", "class AetherLabScene: pass", "manim-community",
                               "compiled", storyboard=kwargs["locked_storyboard"])

        async def render_scene_with_repair(self, bundle, *_args, **_kwargs):
            bundle.status = "render-error"            # stop after generation
            return bundle

    settings = SimpleNamespace(data_dir=tmp_path, openai_api_key="k", llm_model="m",
                               render_mode="local", narration_enabled=False,
                               tts_voice="v", tts_rate="+0%")
    messages: list[str] = []
    asyncio.run(segmented.render_segmented_scene(
        ProblemRequest("Explain", duration_target_s=50.0),
        SolverResult("summary", [], [], {}, "test"), RagResult([], [], "test"), settings,
        runtime=Runtime(), progress=messages.append, max_segment_seconds=60.0,
    ))
    assert tries["n"] == 2
    assert any("generating it once more" in m for m in messages)


def test_short_segment_holds_its_last_frame_to_fill_the_slot(tmp_path):
    # Live cloud run 2026-10-02: a 13.17 s render in a 14.24 s slot stopped the lesson.
    from aetherlab.services import segmented_pipeline as segmented

    ffmpeg = _ffmpeg()
    clip = tmp_path / "segment.mp4"
    subprocess.run([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=navy:s=320x180:d=13.17:r=15", "-f", "lavfi", "-i",
                    "sine=frequency=330:duration=13.17", "-shortest",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", str(clip)], check=True)
    assert asyncio.run(segmented._hold_last_frame(clip, 14.24 - 13.17)) is True
    measured = voiceover._duration_sync(clip)
    assert measured == pytest.approx(14.24, abs=0.15)


def test_wording_is_tightened_before_the_biggest_speed_up(tmp_path, monkeypatch):
    import json as _json

    board = _board(["a b c d e f", "g h i j k l", "m n o p q r"])
    rates: list[str] = []

    async def fake_measure(lines, cache_dir, voice, rate, **_kwargs):
        rates.append(rate)
        words = sum(len(line.split()) for line in lines)
        per_word = {"+0%": 0.75, "+10%": 0.7, "+20%": 0.6}[rate]
        return [per_word * len(line.split()) for line in lines] if words else [0.0] * len(lines)

    class _Completions:
        async def create(self, **_kwargs):
            reply = {"A1.B1": "a b c", "A1.B2": "g h i", "A2.B1": "m n o"}
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content=_json.dumps(reply)), finish_reason="stop")])

    monkeypatch.setattr(voiceover, "measure_speech", fake_measure)
    monkeypatch.setattr(voiceover, "narration_available", lambda: True)
    settings = SimpleNamespace(narration_enabled=True, tts_voice="v", tts_rate="+0%",
                               data_dir=tmp_path, openai_api_key="k", llm_model="MiniMax-M3",
                               openai_base_url="https://api.minimax.io/v1")
    generator = SceneGenerator(settings)
    generator._client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
    # 18 words: 13.5 s at +0%, 12.6 s at +10%: too long for 12 s, so tighten
    # (would have fitted at +20%, 10.8 s, but that voice is too fast).
    fitted = asyncio.run(generator.fit_board_to_speech(board, 12.0))
    assert rates[:2] == ["+0%", "+10%"] and "+20%" not in rates[:3]
    assert fitted["speech"]["rate"] == "+0%"
    assert fitted["timeline"][0]["narration_cue"] == "a b c"


def test_a_scene_that_misses_its_scheduled_length_is_repaired(tmp_path, monkeypatch):
    # Live cloud runs 2026-10-02: segments ran 15.40 s for a 13.76 s slot.
    from aetherlab.services import manim_runtime
    from aetherlab.services.manim_runtime import ManimRuntime

    long_version = _MARKED.replace("run_time=2.0)", "run_time=4.5)")   # 6.0 s -> 8.5 s
    repairs: list[str] = []

    async def fake_repair(self, code, instruction, class_name, full_scene=False):
        repairs.append(instruction)
        return _MARKED

    monkeypatch.setattr(SceneGenerator, "repair", fake_repair)
    monkeypatch.setattr(manim_runtime, "_blocking_scene_issues", lambda code, timeline: (True, []))
    settings = SimpleNamespace(openai_api_key="k", narration_enabled=False, llm_model="m",
                               data_dir=tmp_path)
    timeline = [{"id": "A1.B1", "start_s": 0.0, "end_s": 2.0},
                {"id": "A1.B2", "start_s": 2.0, "end_s": 4.0},
                {"id": "A2.B1", "start_s": 4.0, "end_s": 6.0}]
    bundle = SceneBundle("S", long_version, "manim-community", "compiled")
    out = asyncio.run(ManimRuntime(settings)._preflight_and_repair(bundle, settings, timeline))
    assert len(repairs) == 1 and "[PREFLIGHT:DURATION] the scene runs 8.50s" in repairs[0]
    assert "BEAT_DRIFT" not in repairs[0]          # narration off: length only
    assert out.code == _MARKED


def test_lines_stay_at_planned_starts_when_the_video_runs_long(tmp_path, monkeypatch):
    # Live cloud run 4: a 15.13 s render of a 13.59 s plan. Stretching every
    # cue by the overall ratio would have moved early lines up to 1.3 s late.
    ffmpeg = _ffmpeg()
    video = tmp_path / "long.mp4"
    subprocess.run([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=black:s=320x180:d=13.3:r=15", "-pix_fmt", "yuv420p", str(video)],
                   check=True)
    cache = tmp_path / "speech_cache"
    cues = ["Hot iron glows red.", "Now hotter.", "The peak moves to blue."]
    lengths = {cues[0]: 1.4, cues[1]: 4.1, cues[2]: 2.6}

    async def fake_synthesize(text, out_path, voice, rate):
        _tone(Path(out_path), lengths[" ".join(text.split())])
        return Path(out_path)

    monkeypatch.setattr(voiceover, "synthesize", fake_synthesize)
    monkeypatch.setattr(voiceover, "narration_available", lambda: True)
    speech = asyncio.run(voiceover.measure_speech(cues, cache, "v", "+8%"))
    board = fit_timeline_to_speech(_board(cues), speech, 12.0)
    planned = [b["start_s"] for b in board["timeline"]]
    result = asyncio.run(voiceover.add_timed_beat_voiceover(
        video, board, tmp_path / "out", voice="v", rate="+8%", speech_cache_dir=cache,
    ))
    assert result is not None
    assert result["sync"]["timeline_scale"] == 1.0
    assert [b["start_s"] for b in result["sync"]["beats"]] == planned
    assert result["sync"]["beats"][-1]["end_s"] == pytest.approx(13.3, abs=0.1)


def test_a_somewhat_long_segment_is_accepted_with_a_note(tmp_path, monkeypatch):
    from aetherlab.core.models import ProblemRequest, RagResult, SolverResult
    from aetherlab.services import segmented_pipeline as segmented

    board = schedule_storyboard_timeline({"acts": [{"name": "A", "duration_s": 13.59, "beats": [
        {"detail": str(i), "narration_cue": "", "duration_s": 1} for i in range(4)
    ]}]}, 50.0)

    async def fake_storyboard(*_args, **_kwargs):
        return board

    monkeypatch.setattr(SceneGenerator, "storyboard", fake_storyboard)

    class Runtime:
        async def generate_scene_async(self, *_args, **kwargs):
            return SceneBundle("AetherLabScene", "class AetherLabScene: pass", "manim-community",
                               "compiled", storyboard=kwargs["locked_storyboard"])

        async def render_scene_with_repair(self, bundle, *_args, **_kwargs):
            source = tmp_path / "rendered.mp4"
            source.write_bytes(b"x" * 2048)
            bundle.video_path, bundle.status = str(source), "rendered"
            return bundle

    async def fake_duration(path):
        return 57.0 if Path(path).name == "lesson.mp4" else 57.0   # 50 s plan, +14%

    async def fake_assemble(clips, out_path, **_kwargs):
        Path(out_path).write_bytes(b"y" * 4096)
        return Path(out_path)

    monkeypatch.setattr(segmented, "_valid_video", lambda path, expected_hash="": Path(path).is_file())
    monkeypatch.setattr("aetherlab.services.voiceover.get_duration", fake_duration)
    monkeypatch.setattr("aetherlab.services.assembly.assemble_lesson", fake_assemble)
    monkeypatch.setattr("aetherlab.services.voiceover._duration_sync", lambda _path: 57.0)
    settings = SimpleNamespace(data_dir=tmp_path, openai_api_key="k", llm_model="m",
                               render_mode="local", narration_enabled=False,
                               tts_voice="v", tts_rate="+0%")
    result = asyncio.run(segmented.render_segmented_scene(
        ProblemRequest("Explain", duration_target_s=50.0),
        SolverResult("summary", [], [], {}, "test"), RagResult([], [], "test"), settings,
        runtime=Runtime(), max_segment_seconds=60.0,
    ))
    assert result.status == "rendered", result.diagnostics[-1:]
    assert any("past its 50.00s slot" in d for d in result.diagnostics)


def test_cached_clips_lose_their_edge_silence(tmp_path, monkeypatch):
    # Live cloud run 5: edge-tts pads each clip ~0.45 s (22% of a short line),
    # so a 128-word script measured 62.5 s and could not fit 60 s.
    ffmpeg = _ffmpeg()

    async def padded_synthesize(text, out_path, voice, rate):
        subprocess.run([ffmpeg, "-v", "error", "-y",
                        "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono:d=0.15",
                        "-f", "lavfi", "-i", "sine=frequency=300:duration=1.4:sample_rate=24000",
                        "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono:d=0.35",
                        "-filter_complex", "[0:a][1:a][2:a]concat=n=3:v=0:a=1",
                        "-c:a", "libmp3lame", str(out_path)], check=True)
        return Path(out_path)

    monkeypatch.setattr(voiceover, "synthesize", padded_synthesize)
    speech = asyncio.run(voiceover.measure_speech(["one line"], tmp_path / "cache", "v", "+0%"))
    assert speech[0] == pytest.approx(1.4, abs=0.12)        # was 1.9 with padding
