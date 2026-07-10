"""QThread workers for non-blocking AetherLab pipeline execution."""

from __future__ import annotations

import asyncio
import traceback

from aetherlab.core.cache import SessionCache
from aetherlab.core.models import (
    PipelineError,
    PipelineResult,
    ProblemRequest,
    RagResult,
    SceneBundle,
)
from aetherlab.core.settings import AppSettings
from aetherlab.services.ingestion import LibraryIngestor
from aetherlab.services.llm import AsyncLLMCoordinator
from aetherlab.services.manim_runtime import ManimRuntime
from aetherlab.services.rag import LocalVectorRag
from aetherlab.ui.qt_compat import QtCore, require_qt

require_qt()


class _PipelineCancelled(Exception):
    """Internal sentinel exception for pipeline cancellation (#2)."""
    pass


class PipelineWorker(QtCore.QThread):  # type: ignore[union-attr]
    solver_ready = QtCore.pyqtSignal(object)
    rag_ready = QtCore.pyqtSignal(object)
    scene_ready = QtCore.pyqtSignal(object)
    render_ready = QtCore.pyqtSignal(object)
    pipeline_finished = QtCore.pyqtSignal(object)
    failure = QtCore.pyqtSignal(object)
    status = QtCore.pyqtSignal(str)
    progress = QtCore.pyqtSignal(int, str)  # percent, label

    def __init__(self, request: ProblemRequest, settings: AppSettings, render_quality: str = "l") -> None:
        super().__init__()
        self.request = request
        self.settings = settings
        self.render_quality = render_quality
        self._cancelled = False  # #2: pipeline cancel flag

    def cancel(self) -> None:
        """Request cancellation of the running pipeline (#2)."""
        self._cancelled = True

    def _check_cancelled(self) -> None:
        """Raise if pipeline was cancelled — checked between stages (#2)."""
        if self._cancelled:
            raise _PipelineCancelled()

    def run(self) -> None:
        try:
            asyncio.run(self._run_async())
        except _PipelineCancelled:
            self.status.emit("Pipeline cancelled by user.")
        except Exception as exc:
            if self._cancelled:
                self.status.emit("Pipeline cancelled by user.")
                return
            self.failure.emit(
                PipelineError(
                    stage="pipeline",
                    message=str(exc),
                    traceback=traceback.format_exc(),
                )
            )

    async def _run_async(self) -> None:
        cache = SessionCache(self.settings.cache_path)
        key = cache.ensure_request(self.request)
        cached = cache.get(key)

        # ── Worker A: solve ──
        self.progress.emit(5, "Solving analytical scaffold\u2026")
        if cached and cached.solver and self._solver_cache_usable(cached.solver):
            solver = cached.solver
            self.status.emit("Loaded analytical solution from SQLite cache.")
        else:
            self.status.emit("Worker A: solving analytical scaffold.")
            solver = await AsyncLLMCoordinator(self.settings).solve(self.request)
            cache.store_solver(key, solver)
        self.solver_ready.emit(solver)
        self.progress.emit(30, "Analytical solution ready")

        self._check_cancelled()

        # ── Auto-ingest library (#16 — emit progress) ──
        self.progress.emit(32, "Indexing textbook library\u2026")
        await self._ensure_ingested()

        self._check_cancelled()

        # ── Workers B + C in parallel: RAG + scene gen ──
        self.progress.emit(35, "Searching references & generating scene in parallel\u2026")
        manim = ManimRuntime(self.settings)
        current_engine, _ = manim.detect_engine()

        async def _do_rag() -> RagResult:
            if cached and cached.rag:
                self.status.emit("Loaded RAG references from SQLite cache.")
                return cached.rag
            self.status.emit("Worker B: searching local textbook memory.")
            rag = await LocalVectorRag(self.settings).search(solver.keywords)
            if getattr(self.settings, "web_references", True):
                self.status.emit("Worker B: fetching web references (Wikipedia).")
                from aetherlab.services.pipeline import _merge_web_references
                rag = await _merge_web_references(rag, solver.keywords, self.settings)
            cache.store_rag(key, rag)
            return rag

        async def _do_scene(rag: RagResult) -> SceneBundle:
            if (
                cached
                and cached.scene
                and _scene_cache_usable(cached.scene, self.settings)
                and cached.scene.engine == current_engine
                and cached.scene.status in {"compiled", "rendered"}
            ):
                self.status.emit("Loaded generated Manim scene from SQLite cache.")
                return cached.scene
            self.status.emit("Worker C: generating dynamic Manim scene via LLM.")
            if manim.scene_tournament_enabled(self.settings):
                self.status.emit("Worker C: running scene candidate tournament.")
                scene = await manim.generate_render_tournament(
                    self.request,
                    solver,
                    rag,
                    self.settings,
                    quality=self.render_quality,
                    brief=self.request.prompt,
                    progress=lambda msg: self.status.emit(str(msg)),
                    cancel_check=lambda: self._cancelled,
                )
            else:
                scene = await manim.generate_scene_async(self.request, solver, rag, self.settings)
            cache.store_scene(key, scene)
            return scene

        rag = await _do_rag()
        self._check_cancelled()
        self.rag_ready.emit(rag)
        self.progress.emit(50, f"Found {len(rag.hits)} references")

        scene = await _do_scene(rag)
        self._check_cancelled()
        self.scene_ready.emit(scene)
        self.progress.emit(70, "Scene compiled")

        # ── Worker D: render Manim scene to video ──
        quality_label = {"l": "480p", "m": "720p", "h": "1080p"}.get(self.render_quality, "480p")
        self.progress.emit(75, f"Rendering Manim scene to MP4 ({quality_label})\u2026")
        self.status.emit(f"Worker D: rendering Manim scene to MP4 ({quality_label}).")
        from aetherlab.services.pipeline import _video_exists

        needs_render = scene.status == "compiled" or (
            scene.status == "rendered" and not _video_exists(scene.video_path)
        )
        if scene.status == "rendered" and needs_render:
            scene.diagnostics.append("Cached rendered video missing; re-rendering.")
            scene.status = "compiled"
            scene.video_path = ""
        if needs_render:
            rendered_scene = await manim.render_scene_with_repair(
                scene, self.settings, quality=self.render_quality,
                brief=self.request.prompt,
                progress=lambda msg: self.status.emit(str(msg)),
                cancel_check=lambda: self._cancelled,
            )
            if any("Applied render repair" in d for d in rendered_scene.diagnostics):
                self.status.emit("Scene needed a render repair pass; re-rendered.")
            if any("Applied visual revision" in d for d in rendered_scene.diagnostics):
                self.status.emit("Visual critic requested a revision; re-rendered.")
            cache.store_scene(key, rendered_scene)
        else:
            self.status.emit("Reusing cached rendered video.")
            rendered_scene = scene
        self._check_cancelled()
        self.render_ready.emit(rendered_scene)
        self.progress.emit(95, "Render complete")

        self.pipeline_finished.emit(
            PipelineResult(
                request=self.request,
                cache_key=key,
                solver=solver,
                rag=rag,
                scene=rendered_scene,
            )
        )
        self.progress.emit(100, "Pipeline complete")

    async def _ensure_ingested(self) -> None:
        """Auto-index library files into ChromaDB if empty (#16 — progress emitted)."""
        if self.settings.chroma_path.exists():
            try:
                import chromadb
                client = chromadb.PersistentClient(path=str(self.settings.chroma_path))
                collection = client.get_collection("textbooks")
                if collection.count() > 0:
                    self.progress.emit(33, f"RAG ready: {collection.count()} chunks indexed")
                    return
            except Exception:
                pass

        if self.settings.library_path.exists():
            try:
                ingestor = LibraryIngestor(self.settings)
                count = ingestor.ingest(should_cancel=lambda: self._cancelled)
                if count > 0:
                    self.status.emit(f"Ingested {count} chunks into ChromaDB.")
                    self.progress.emit(33, f"Ingested {count} chunks into ChromaDB")
            except Exception:
                pass

    def _solver_cache_usable(self, solver) -> bool:
        if solver.model_name == "deterministic-fallback" and self.settings.openai_api_key:
            return False
        if solver.model_name not in {"deterministic-fallback", self.settings.llm_model}:
            return False
        return True


class LessonWorker(QtCore.QThread):  # type: ignore[union-attr]
    """Runs the topic-explainer LessonPipeline off the UI thread.

    Cancellable (like the Solve path): ``cancel()`` sets a threading Event the
    pipeline polls between chapters, so a long lesson stops promptly and returns
    whatever rendered so far. ``regenerate`` bypasses the plan + chapter caches.
    """

    progress = QtCore.pyqtSignal(str, int, int)   # message, done, total
    lesson_ready = QtCore.pyqtSignal(object)       # LessonBundle
    failure = QtCore.pyqtSignal(object)            # PipelineError

    def __init__(self, topic: str, settings: AppSettings, *,
                 audience: str = "undergrad", quality: str = "l",
                 regenerate: bool = False) -> None:
        super().__init__()
        self.topic = topic
        self.settings = settings
        self.audience = audience
        self.quality = quality
        self.regenerate = regenerate
        import threading
        self._cancel = threading.Event()

    def cancel(self) -> None:
        """Request cancellation; the pipeline stops after the current chapter."""
        self._cancel.set()

    def run(self) -> None:
        try:
            from aetherlab.services.lesson_pipeline import LessonPipeline

            pipeline = LessonPipeline(self.settings)
            bundle = asyncio.run(
                pipeline.run(
                    self.topic,
                    audience=self.audience,
                    quality=self.quality,
                    regenerate=self.regenerate,
                    cancel_check=self._cancel.is_set,
                    progress=lambda m, d, t: self.progress.emit(m, d, t),
                )
            )
            self.lesson_ready.emit(bundle)
        except Exception as exc:  # noqa: BLE001
            self.failure.emit(
                PipelineError(stage="lesson", message=str(exc), traceback=traceback.format_exc())
            )


def _scene_cache_usable(scene: SceneBundle, settings: AppSettings) -> bool:
    if scene.status == "rendered":
        from aetherlab.services.pipeline import _video_exists

        if not _video_exists(scene.video_path):
            return False
    min_score = float(getattr(settings, "min_quality_score", 0.0) or 0.0)
    if min_score <= 0:
        return True
    return float(getattr(scene, "quality_score", 0.0) or 0.0) >= min_score
