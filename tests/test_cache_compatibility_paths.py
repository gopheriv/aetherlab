"""Additional actual cache-consumer paths; controlled generator/renderer, no network."""
import asyncio
from types import SimpleNamespace

import pytest

from aetherlab.core.cache import SessionCache
from aetherlab.core.models import OutputPlan, ProblemRequest, RagResult, SceneBundle, SolverResult
from aetherlab.core.render_cache import record_scene_profile
from aetherlab.services.pipeline import AetherLabPipeline
from aetherlab.ui.workers import PipelineWorker


@pytest.mark.parametrize("entry", ["pipeline", "worker"])
@pytest.mark.parametrize("state", ["compatible", "engine", "status", "low-score", "compiled", "recovered-provider"])
def test_source_compatibility_routes_independently_from_media_profile(tmp_path, monkeypatch, entry, state):
    import os
    for name in tuple(os.environ):
        if name.startswith(("AETHERLAB_", "MANIM_", "RENDER_")):
            monkeypatch.delenv(name, raising=False)
    settings = SimpleNamespace(openai_api_key="owned-not-a-credential" if state == "recovered-provider" else None,
        llm_model="owned", min_quality_score=7 if state == "low-score" else 0, tts_voice="",
        cache_path=tmp_path / "cache.sqlite3")
    cache = SessionCache(settings.cache_path)
    request = ProblemRequest("Owned cache compatibility fixture")
    key = cache.ensure_request(request)
    cache.store_solver(key, SolverResult("Owned", [], [], {}, "owned"))
    cache.store_rag(key, RagResult([], [], "owned"))
    clip = tmp_path / "prior.mp4"
    clip.write_bytes(b"owned prior video")
    scene = record_scene_profile(SceneBundle("Old", "class Old: pass", "other" if state == "engine" else "owned",
        "compile-error" if state == "status" else "compiled" if state == "compiled" else "rendered",
        video_path=str(clip), quality_score=6 if state == "low-score" else 8,
        used_fallback=state == "recovered-provider"), settings)
    cache.store_scene(key, scene)
    calls = []
    async def forbidden(*args, **kwargs):
        raise AssertionError("Cached analytical solution/references must remain reusable")
    async def plan(*args):
        return OutputPlan(needs_animation=True)
    async def no_ingest(*args):
        pass
    async def generate(*args, **kwargs):
        calls.append("generate")
        return SceneBundle("Fresh", "class Fresh: pass", "owned", "compiled")
    async def render(bundle, settings, **kwargs):
        calls.append("render")
        bundle.status = "rendered"
        bundle.video_path = str(tmp_path / "new.mp4")
        return record_scene_profile(bundle, settings)
    runtime = SimpleNamespace(detect_engine=lambda: ("owned", []), scene_tournament_enabled=lambda _: False,
        generate_scene_async=generate, render_scene_with_repair=render)
    monkeypatch.setattr("aetherlab.services.pipeline.Planner.plan", plan)
    monkeypatch.setattr("aetherlab.services.pipeline._video_exists", lambda path: path == str(clip))
    if entry == "pipeline":
        pipeline = AetherLabPipeline.__new__(AetherLabPipeline)
        pipeline.settings, pipeline.cache, pipeline.manim = settings, cache, runtime
        pipeline.llm, pipeline.rag = SimpleNamespace(solve=forbidden), SimpleNamespace(search=forbidden)
        pipeline._ensure_ingested = no_ingest
        result = asyncio.run(pipeline.run(request))
    else:
        monkeypatch.setattr(PipelineWorker, "_ensure_ingested", no_ingest)
        monkeypatch.setattr("aetherlab.ui.workers.ManimRuntime", lambda _: runtime)
        worker = PipelineWorker(request, settings)
        results = []
        worker.pipeline_finished.connect(results.append)
        asyncio.run(worker._run_async())
        assert len(results) == 1
        result = results[0]
    expected = [] if state == "compatible" else ["render"] if state == "compiled" else ["generate", "render"]
    assert calls == expected
    assert result.solver.cached and result.rag.cached
    assert result.scene.code == ("class Old: pass" if state in {"compatible", "compiled"} else "class Fresh: pass")
    assert clip.read_bytes() == b"owned prior video"
