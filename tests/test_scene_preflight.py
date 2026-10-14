"""Preflight: dry-run AI scenes before the slow render (crash, off-frame, exact duration)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from aetherlab.core.models import SceneBundle
from aetherlab.services import scene_preflight
from aetherlab.services.scene_preflight import PreflightReport, preflight_scene

_CLEAN = '''from manim import *
class S(Scene):
    def construct(self):
        dots = VGroup(*[Dot() for _ in range(6)]).arrange(RIGHT)
        self.play(LaggedStart(*[FadeIn(d) for d in dots], lag_ratio=0.3))
        self.wait(0.5)
        self.play(dots.animate.shift(UP), run_time=0.75)
'''


# ── real dry runs (Manim in a child process; no LaTeX, a few seconds each) ──

def test_preflight_measures_exact_duration_including_lagged_groups():
    report = preflight_scene(_CLEAN, "S")
    assert report.ran and report.ok, report.error or report.note
    assert report.duration_s == pytest.approx(3.75, abs=0.01)   # 2.5 + 0.5 + 0.75
    assert report.off_frame == []


def test_preflight_catches_a_runtime_crash_static_gates_miss():
    crash = _CLEAN.replace(
        "self.wait(0.5)",
        "self.play(dots.animate.set_color(interpolate_color('#FF0000', '#0000FF', 0.5)))",
    )
    report = preflight_scene(crash, "S")
    assert report.ran and report.crashed
    assert "AttributeError: 'str' object has no attribute" in report.error


def test_preflight_reports_objects_that_leave_the_frame():
    off = _CLEAN.replace("self.wait(0.5)", "self.play(dots[0].animate.move_to(UP * 9))")
    report = preflight_scene(off, "S")
    assert report.ran and report.ok
    lines = report.off_frame_lines()
    assert lines and lines[0].startswith("[PREFLIGHT:OFF_FRAME]")


# ── pipeline integration (fakes; no Manim, no LLM) ─────────────────────────

_ORIGINAL = ("from manim import *\nclass AetherLabScene(Scene):\n    def construct(self):\n"
             "        d = Dot()\n        self.play(Create(d))\n        self.play(d.animate.shift(UP))\n")
_FIXED = _ORIGINAL.replace("Dot()", "Dot(color=RED)")


def _run(monkeypatch, reports, *, diagnostics=(), used_fallback=False, key="sk-test",
         repaired=_FIXED):
    from aetherlab.services import manim_runtime
    from aetherlab.services.scene_generator import SceneGenerator

    queue = list(reports)
    preflights, rendered = [], []

    def fake_preflight(code, class_name, *args, **kwargs):
        preflights.append(code)
        return queue.pop(0)

    async def fake_repair(self, code, error, class_name, *, full_scene=False):
        return repaired

    async def fake_render(bundle, *args, **kwargs):
        rendered.append(bundle.code)
        bundle.status, bundle.video_path = "render-error", ""   # stop before critic/HQ
        return bundle

    monkeypatch.setattr(scene_preflight, "preflight_scene", fake_preflight)
    monkeypatch.setattr(SceneGenerator, "repair", fake_repair)
    import tempfile
    from pathlib import Path

    settings = SimpleNamespace(openai_api_key=key, vision_model=None, llm_model="m",
                               render_mode="local", narration_enabled=False,
                               data_dir=Path(tempfile.mkdtemp(prefix="aetherlab_pf_")))
    runtime = manim_runtime.ManimRuntime(settings)
    monkeypatch.setattr(runtime, "_render_once", fake_render)
    bundle = SceneBundle("AetherLabScene", _ORIGINAL, "manim-community", "compiled",
                         diagnostics=list(diagnostics), used_fallback=used_fallback)
    result = asyncio.run(runtime.render_scene_with_repair(bundle, settings, max_repairs=0))
    return result, preflights, rendered


def _ok(off=0, duration=30.0):
    return PreflightReport(ran=True, ok=True, duration_s=duration, seconds=3.0,
                           off_frame=[{"mobject": "ParametricFunction", "time_s": 5, "after": "play",
                                       "bounds": [-5, 5, -2, 6], "overflow": 2.0}] * off)


def _crash(error="AttributeError: 'str' object has no attribute '_internal_space'"):
    return PreflightReport(ran=True, ok=False, error=error, seconds=3.0)


def test_preflight_crash_is_repaired_before_the_first_render(monkeypatch):
    result, preflights, rendered = _run(monkeypatch, [_crash(), _ok()])
    assert preflights == [_ORIGINAL, _FIXED]
    assert rendered == [_FIXED]                       # one render, already fixed
    assert any("fixed the crash before rendering" in d for d in result.diagnostics)


def test_unrepaired_preflight_crash_still_renders_the_original(monkeypatch):
    result, _preflights, rendered = _run(monkeypatch, [_crash(), _crash(), _crash()])
    assert rendered == [_ORIGINAL]
    assert any("rendering the original" in d for d in result.diagnostics)


def test_off_frame_layout_repair_is_kept_only_when_it_helps(monkeypatch):
    _result, _p, rendered = _run(monkeypatch, [_ok(off=3), _ok(off=1)])
    assert rendered == [_FIXED]
    _result, _p, rendered = _run(monkeypatch, [_ok(off=2), _ok(off=2)])
    assert rendered == [_ORIGINAL]


def test_curated_fallback_and_keyless_scenes_skip_repairs(monkeypatch):
    curated = ["Scene composed from curated component library (numeric-driven)."]
    _r, preflights, rendered = _run(monkeypatch, [], diagnostics=curated)
    assert preflights == [] and rendered == [_ORIGINAL]
    _r, preflights, rendered = _run(monkeypatch, [], used_fallback=True)
    assert preflights == [] and rendered == [_ORIGINAL]
    result, preflights, rendered = _run(monkeypatch, [_crash()], key=None)
    assert preflights == [_ORIGINAL] and rendered == [_ORIGINAL]
    assert any("crashed before rendering" in d for d in result.diagnostics)


def test_preflight_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("AETHERLAB_PREFLIGHT", "0")
    report = preflight_scene(_CLEAN, "S")
    assert not report.ran and report.note == "preflight disabled"
