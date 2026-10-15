"""Owned cached pipeline probe; no provider, UI or render process."""
import asyncio
from types import SimpleNamespace
import pytest

from aetherlab.core.cache import SessionCache
from aetherlab.core.models import OutputPlan, ProblemRequest, RagResult, SceneBundle, SolverResult
from aetherlab.services.pipeline import AetherLabPipeline
from aetherlab.core.render_cache import requested_profile_key, record_scene_profile


@pytest.fixture(autouse=True)
def owned_environment(monkeypatch):
    import os
    for key in tuple(os.environ):
        if key.startswith(("AETHERLAB_", "MANIM_", "RENDER_")):
            monkeypatch.delenv(key, raising=False)


def test_unverified_rendered_session_does_not_bypass_requested_profile(tmp_path, monkeypatch):
    pipeline = AetherLabPipeline.__new__(AetherLabPipeline)
    pipeline.settings = SimpleNamespace(openai_api_key=None, llm_model="owned",
        min_quality_score=0, tts_voice="", render_preset="cinematic",
        render_width=1920, render_height=1080, render_fps=60, adaptive_quality=False)
    pipeline.cache = SessionCache(tmp_path / "owned.sqlite3")
    request = ProblemRequest("Explain changing velocity")
    key = pipeline.cache.ensure_request(request)
    pipeline.cache.store_solver(key, SolverResult("Owned", [], [], {}, "owned"))
    pipeline.cache.store_rag(key, RagResult([], [], "owned"))
    old_video = tmp_path / "old-480p.mp4"
    old_video.write_bytes(b"owned old media; container decoding is out of scope")
    pipeline.cache.store_scene(key, SceneBundle("Owned", "class Owned: pass", "owned", "rendered",
                                               video_path=str(old_video)))
    calls = []
    async def forbidden(*args, **kwargs):
        raise AssertionError("Cached solver/RAG/code must not be regenerated")
    async def no_ingest():
        pass
    async def plan(*args):
        return OutputPlan(needs_animation=True)
    async def render(scene, settings, **kwargs):
        calls.append((scene.status, scene.code))
        scene.status = "rendered"
        return scene
    pipeline.llm = SimpleNamespace(solve=forbidden)
    pipeline.rag = SimpleNamespace(search=forbidden)
    pipeline._ensure_ingested = no_ingest
    pipeline.manim = SimpleNamespace(detect_engine=lambda: ("owned", []),
        generate_scene_async=forbidden, render_scene_with_repair=render)
    monkeypatch.setattr("aetherlab.services.pipeline.Planner.plan", plan)
    monkeypatch.setattr("aetherlab.services.pipeline._video_exists", lambda path: path == str(old_video))
    result = asyncio.run(pipeline.run(request))
    assert result.solver.cached and result.rag.cached
    assert calls == [("compiled", "class Owned: pass")]
    assert old_video.read_bytes().startswith(b"owned old media")


@pytest.mark.parametrize("entry", ["pipeline", "worker"])
@pytest.mark.parametrize("change", ["unchanged", "legacy", "canvas", "fps", "adaptive", "renderer", "backend", "quality"])
def test_cached_scene_profile_routes_only_media_back_to_render(tmp_path, monkeypatch, entry, change):
    from copy import copy
    from aetherlab.ui.workers import PipelineWorker

    old = SimpleNamespace(openai_api_key=None, llm_model="owned", min_quality_score=0,
        tts_voice="", render_preset="cinematic", render_width=960, render_height=540,
        render_fps=60, adaptive_quality=False, render_mode="cloud", render_renderer="cairo",
        cache_path=tmp_path / "session.sqlite3")
    current = copy(old)
    quality = "l"
    if change == "canvas":
        current.render_width = 1280
    elif change == "fps":
        current.render_fps = 48
    elif change == "adaptive":
        current.adaptive_quality = True
    elif change == "renderer":
        current.render_renderer = "opengl"
    elif change == "backend":
        current.render_mode = "local"
    elif change == "quality":
        # The headless pipeline has its existing implicit low-quality render
        # API; test cached HQ against it, and the worker's explicit HQ request.
        quality = "h" if entry == "worker" else "l"
    cache = SessionCache(current.cache_path)
    request = ProblemRequest("Owned velocity explanation")
    key = cache.ensure_request(request)
    cache.store_solver(key, SolverResult("Owned", [], [], {}, "owned"))
    cache.store_rag(key, RagResult([], [], "owned"))
    clip = tmp_path / "prior.mp4"
    clip.write_bytes(b"owned prior clip")
    bundle = SceneBundle("Owned", "class Owned: pass", "owned", "rendered",
        video_path=str(clip), silent_video_path=str(clip), subtitle_path="prior.srt",
        narration_text="Prior speech", narration_sync={"old": True})
    record_scene_profile(bundle, old, "h" if change == "quality" and entry == "pipeline" else "l")
    if change == "legacy":
        bundle.render_profile_key = ""
    cache.store_scene(key, bundle)
    calls = []
    async def forbidden(*args, **kwargs):
        raise AssertionError("Profile change must reuse solver, references and source code")
    async def no_ingest(*args):
        pass
    async def plan(*args):
        return OutputPlan(needs_animation=True)
    async def render(scene, settings, **kwargs):
        assert scene.status == "compiled" and scene.code == "class Owned: pass"
        assert not scene.video_path and not scene.silent_video_path and not scene.subtitle_path
        assert not scene.narration_sync and not scene.narration_text
        calls.append(kwargs.get("quality", "l"))
        scene.status = "rendered"
        scene.video_path = str(tmp_path / "new.mp4")
        return record_scene_profile(scene, settings, kwargs.get("quality", "l"))
    runtime = SimpleNamespace(detect_engine=lambda: ("owned", []),
        generate_scene_async=forbidden, render_scene_with_repair=render)
    monkeypatch.setattr("aetherlab.services.pipeline.Planner.plan", plan)
    monkeypatch.setattr("aetherlab.services.pipeline._video_exists", lambda path: path == str(clip))
    if entry == "pipeline":
        pipeline = AetherLabPipeline.__new__(AetherLabPipeline)
        pipeline.settings, pipeline.cache, pipeline.manim = current, cache, runtime
        pipeline.llm, pipeline.rag = SimpleNamespace(solve=forbidden), SimpleNamespace(search=forbidden)
        pipeline._ensure_ingested = no_ingest
        result = asyncio.run(pipeline.run(request))
    else:
        monkeypatch.setattr(PipelineWorker, "_ensure_ingested", no_ingest)
        monkeypatch.setattr("aetherlab.ui.workers.ManimRuntime", lambda settings: runtime)
        worker = PipelineWorker(request, current, render_quality=quality)
        outcomes = []
        worker.pipeline_finished.connect(outcomes.append)
        asyncio.run(worker._run_async())
        assert len(outcomes) == 1
        result = outcomes[0]
    assert calls == ([] if change == "unchanged" else [quality])
    assert result.solver.cached and result.rag.cached
    assert clip.read_bytes() == b"owned prior clip"
    assert cache.get(key).scene.render_profile_key == requested_profile_key(current, quality)


def test_scene_profile_round_trip_and_legacy_default():
    scene = SceneBundle("Owned", "code", "owned", "rendered", render_profile_key="owned-profile")
    assert SceneBundle.from_json(scene.to_json(), cached=True).render_profile_key == "owned-profile"
    payload = scene.to_json()
    del payload["render_profile_key"]
    assert SceneBundle.from_json(payload, cached=True).render_profile_key == ""


@pytest.mark.parametrize("state,quality,expected", [
    ("draft", "l", []), ("draft", "h", ["h"]),
    ("final", "h", []), ("changed", "l", ["l"]),
    ("legacy", "l", ["l"]), ("missing", "l", ["l"]),
])
def test_runtime_fast_path_requires_verified_profile(tmp_path, monkeypatch, state, quality, expected):
    from dataclasses import replace
    from aetherlab.core.settings import AppSettings
    from aetherlab.services.manim_runtime import ManimRuntime
    settings = AppSettings(data_dir=tmp_path, cache_path=tmp_path / "cache.sqlite3",
        chroma_path=tmp_path / "chroma", library_path=tmp_path / "library",
        openai_api_key=None, openai_base_url=None, llm_model="owned", render_mode="cloud")
    old_settings = replace(settings, render_fps=48) if state == "changed" else settings
    clip = tmp_path / "old.mp4"
    clip.write_bytes(b"owned runtime media")
    scene = SceneBundle("Owned", "class Owned: pass", "owned", "rendered", video_path=str(clip))
    record_scene_profile(scene, old_settings, "h" if state == "final" else "l")
    if state == "legacy":
        scene.render_profile_key = ""
    if state == "missing":
        clip.unlink()
    runtime = ManimRuntime(settings)
    calls = []
    async def preflight(bundle, settings, timeline):
        return bundle
    async def render(bundle, settings, quality, *args, **kwargs):
        calls.append(quality)
        output = tmp_path / f"new-{quality}.mp4"
        output.write_bytes(b"owned new render")
        return replace(bundle, status="rendered", video_path=str(output))
    monkeypatch.setattr(runtime, "_preflight_and_repair", preflight)
    monkeypatch.setattr(runtime, "_render_once", render)
    result = asyncio.run(runtime.render_scene_with_repair(scene, settings, quality=quality))
    assert calls == expected
    assert result.render_profile_key == requested_profile_key(settings, quality)
    if state != "missing":
        assert clip.read_bytes() == b"owned runtime media"


@pytest.mark.parametrize("entry", ["pipeline", "worker"])
@pytest.mark.parametrize("state", ["changed", "unchanged", "unverified-output"])
def test_segmented_cache_never_renders_joined_source(tmp_path, monkeypatch, entry, state):
    from copy import copy
    from aetherlab.ui.workers import PipelineWorker
    from aetherlab.services import segmented_pipeline
    old = SimpleNamespace(openai_api_key=None, llm_model="owned", min_quality_score=0,
        tts_voice="", render_width=960, render_height=540, render_fps=24,
        cache_path=tmp_path / "session.sqlite3")
    current = copy(old)
    if state != "unchanged":
        current.render_width = 1280
    request = ProblemRequest("Explain acceleration", duration_target_s=120)
    cache = SessionCache(current.cache_path)
    key = cache.ensure_request(request)
    cache.store_solver(key, SolverResult("Owned", [], [], {}, "owned"))
    cache.store_rag(key, RagResult([], [], "owned"))
    clip = tmp_path / "old.mp4"
    clip.write_bytes(b"owned previous assembly")
    source = "class Owned: pass\n\nclass Owned: pass"
    cache.store_scene(key, record_scene_profile(SceneBundle("AetherLabSegmentedScene", source,
        "owned", "rendered", video_path=str(clip)), old))
    calls = []
    async def forbidden(*args, **kwargs):
        raise AssertionError("Joined segment code, solver and references must not be regenerated here")
    async def no_ingest(*args):
        pass
    async def plan(*args):
        return OutputPlan(needs_animation=True)
    async def resume(*args, **kwargs):
        calls.append("resume")
        rebuilt = SceneBundle("AetherLabSegmentedScene", source, "owned", "rendered",
                              video_path=str(clip))
        return rebuilt if state == "unverified-output" else record_scene_profile(rebuilt, current)
    runtime = SimpleNamespace(detect_engine=lambda: ("owned", []),
        generate_scene_async=forbidden, render_scene_with_repair=forbidden)
    monkeypatch.setattr(segmented_pipeline, "render_segmented_scene", resume)
    monkeypatch.setattr("aetherlab.services.pipeline.Planner.plan", plan)
    monkeypatch.setattr("aetherlab.services.pipeline._video_exists", lambda path: path == str(clip))
    if entry == "pipeline":
        pipeline = AetherLabPipeline.__new__(AetherLabPipeline)
        pipeline.settings, pipeline.cache, pipeline.manim = current, cache, runtime
        pipeline.llm, pipeline.rag = SimpleNamespace(solve=forbidden), SimpleNamespace(search=forbidden)
        pipeline._ensure_ingested = no_ingest
        result = asyncio.run(pipeline.run(request))
    else:
        monkeypatch.setattr(PipelineWorker, "_ensure_ingested", no_ingest)
        monkeypatch.setattr("aetherlab.ui.workers.ManimRuntime", lambda settings: runtime)
        worker = PipelineWorker(request, current)
        outcomes = []
        worker.pipeline_finished.connect(outcomes.append)
        asyncio.run(worker._run_async())
        assert len(outcomes) == 1
        result = outcomes[0]
    assert calls == ([] if state == "unchanged" else ["resume"])
    assert result.scene.status == ("incomplete" if state == "unverified-output" else "rendered")
    if state == "unverified-output":
        assert not result.scene.video_path
    assert clip.read_bytes() == b"owned previous assembly"
