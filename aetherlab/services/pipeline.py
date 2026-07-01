"""Headless orchestrator used by both CLI smoke mode and Qt workers."""

from __future__ import annotations

from pathlib import Path

from aetherlab.core.cache import SessionCache
from aetherlab.core.models import PipelineResult, ProblemRequest
from aetherlab.core.settings import AppSettings, load_settings
from aetherlab.services.ingestion import LibraryIngestor
from aetherlab.services.llm import AsyncLLMCoordinator
from aetherlab.services.manim_runtime import ManimRuntime
from aetherlab.services.rag import LocalVectorRag


class AetherLabPipeline:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or load_settings()
        self.cache = SessionCache(self.settings.cache_path)
        self.llm = AsyncLLMCoordinator(self.settings)
        self.rag = LocalVectorRag(self.settings)
        self.manim = ManimRuntime(self.settings)
        self._ingested = False

    async def run(self, request: ProblemRequest) -> PipelineResult:
        key = self.cache.ensure_request(request)
        cached = self.cache.get(key)

        # Auto-ingest library into ChromaDB on first run
        await self._ensure_ingested()

        solver = cached.solver if cached and cached.solver and self._solver_cache_usable(cached.solver) else None
        if solver is None:
            solver = await self.llm.solve(request)
            self.cache.store_solver(key, solver)

        rag = cached.rag if cached and cached.rag else None
        if rag is None:
            rag = await self.rag.search(solver.keywords)
            self.cache.store_rag(key, rag)

        manim = self.manim
        current_engine, _ = manim.detect_engine()
        scene = cached.scene if cached and cached.scene else None
        if scene is None or scene.engine != current_engine or scene.status not in {"compiled", "rendered"}:
            scene = await manim.generate_scene_async(request, solver, rag, self.settings)
            self.cache.store_scene(key, scene)

        # Render to MP4 (skip if a valid cached video already exists).
        # render_scene_with_repair adds the error-aware self-heal loop (WP2b).
        if scene.status == "compiled" or (scene.status == "rendered" and not _video_exists(scene.video_path)):
            scene = await manim.render_scene_with_repair(scene, request, solver, rag, self.settings)
            self.cache.store_scene(key, scene)

        return PipelineResult(
            request=request,
            cache_key=key,
            solver=solver,
            rag=rag,
            scene=scene,
        )

    async def _ensure_ingested(self) -> None:
        """Auto-index library files into ChromaDB on first pipeline run."""
        if self._ingested:
            return
        self._ingested = True

        # Skip if ChromaDB already has data
        if self.settings.chroma_path.exists():
            try:
                import chromadb
                client = chromadb.PersistentClient(path=str(self.settings.chroma_path))
                collection = client.get_collection("textbooks")
                if collection.count() > 0:
                    return
            except Exception:
                pass

        # Ingest if library exists
        if self.settings.library_path.exists():
            try:
                ingestor = LibraryIngestor(self.settings)
                ingestor.ingest()
            except Exception:
                pass  # ChromaDB optional — filesystem fallback still works

    def _solver_cache_usable(self, solver) -> bool:
        if solver.model_name == "deterministic-fallback" and self.settings.openai_api_key:
            return False
        if solver.model_name not in {"deterministic-fallback", self.settings.llm_model}:
            return False
        return True


def _video_exists(video_path: str) -> bool:
    return bool(video_path) and Path(video_path).exists()
