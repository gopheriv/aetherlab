"""Topic → rendered, narrated, multi-chapter lesson (the orchestrator).

Ties the topic-explainer phases together, reusing the EXISTING per-scene
pipeline for every chapter (no parallel renderer):

  plan_lesson (Phase 1)
    → for each renderable chapter: synthesize a per-chapter SolverResult,
      ManimRuntime.generate_scene_async → render_scene_with_repair (compile /
      safety / lint gates + self-heal, unchanged), then narrate the chapter
      clip (Phase 2)
    → assemble the chapter clips into one lesson MP4 (Phase 3) + build .srt

Fail-soft throughout: a chapter that won't render is skipped and the lesson
continues; with no API key every chapter uses the deterministic domain
template; assembly failure falls back to the first chapter clip. Per-chapter
caching (keyed by the chapter's plan) means editing one chapter re-renders
only that chapter.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from aetherlab.core.models import (
    LessonBundle,
    LessonChapter,
    LessonPlan,
    ProblemRequest,
    RagResult,
    SceneBundle,
    SolverResult,
)
from aetherlab.services.lesson_planner import plan_lesson
from aetherlab.services.manim_runtime import ManimRuntime

if TYPE_CHECKING:
    from aetherlab.core.settings import AppSettings

log = logging.getLogger(__name__)

_LESSON_DIR = Path(tempfile.gettempdir()) / "aetherlab" / "lessons"

# Chapter kinds that produce a rendered Manim clip. 'interactive' hands off to
# the live canvas (no clip); 'recap' still renders a short summary scene.
_RENDERED_KINDS = {"scene", "equation_card", "recap"}

ProgressCb = Callable[[str, int, int], None]  # (message, done, total)


class LessonPipeline:
    def __init__(self, settings: "AppSettings") -> None:
        self.settings = settings
        self.manim = ManimRuntime(settings)

    async def run(
        self,
        topic: str,
        *,
        audience: str = "undergrad",
        quality: str = "l",
        max_concurrent: int = 2,
        progress: ProgressCb | None = None,
    ) -> LessonBundle:
        """Plan, render, narrate, and assemble a lesson. Never raises."""
        def report(msg: str, done: int, total: int) -> None:
            if progress:
                try:
                    progress(msg, done, total)
                except Exception:  # noqa: BLE001
                    pass
            log.info("Lesson: %s (%d/%d)", msg, done, total)

        report("Planning lesson", 0, 1)
        plan = await plan_lesson(topic, self.settings, audience=audience)
        # Ground the plan in textbooks: attach citations + fact-check narration
        # (fail-soft — corrected narration then flows into render + voiceover).
        report("Grounding in textbooks", 0, 1)
        try:
            from aetherlab.services.fact_check import fact_check_lesson

            plan = await fact_check_lesson(plan, self.settings)
        except Exception:  # noqa: BLE001 — grounding must never block a lesson
            pass
        chapters = [c for c in plan.chapters if c.kind in _RENDERED_KINDS]
        total = len(chapters) or 1

        out_dir = _LESSON_DIR / _lesson_id(plan)
        out_dir.mkdir(parents=True, exist_ok=True)

        # Render chapters (bounded concurrency), preserving order.
        sem = asyncio.Semaphore(max(1, max_concurrent))
        done = 0
        lock = asyncio.Lock()

        async def do_chapter(index: int, ch: LessonChapter) -> tuple[int, SceneBundle | None]:
            nonlocal done
            async with sem:
                report(f"Chapter {index + 1}/{total}: {ch.title}", done, total)
                bundle = await self._render_chapter(ch, plan, out_dir, quality)
                async with lock:
                    done += 1
                    report(f"Chapter {index + 1}/{total} done", done, total)
                return index, bundle

        results = await asyncio.gather(
            *(do_chapter(i, ch) for i, ch in enumerate(chapters))
        )
        by_index = {i: b for i, b in results}
        rendered = [by_index[i] for i in range(len(chapters)) if by_index.get(i)]

        # Narrate each rendered chapter + accumulate a transcript timeline.
        report("Narrating chapters", total, total)
        clips, segments = await self._narrate_chapters(chapters, rendered, out_dir)

        # Assemble into one lesson video (+ .srt).
        report("Assembling lesson", total, total)
        video_path, srt_path = await self._assemble(clips, segments, out_dir)

        status = "assembled" if video_path else ("rendering" if rendered else "error")
        report("Lesson ready" if video_path else "Lesson incomplete", total, total)
        bundle = LessonBundle(
            plan=plan,
            chapter_scenes=[b for b in rendered if b is not None],
            video_path=str(video_path) if video_path else "",
            status=status,
        )
        # stash the srt path on the plan-less side via diagnostics-free attr
        bundle_srt = str(srt_path) if srt_path else ""
        setattr(bundle, "srt_path", bundle_srt)  # noqa: B010 — optional extra
        return bundle

    async def _render_chapter(
        self, ch: LessonChapter, plan: LessonPlan, out_dir: Path, quality: str
    ) -> SceneBundle | None:
        """Render one chapter clip, reusing the existing scene pipeline.

        Cache-keyed by the chapter's plan: an unchanged chapter reuses its clip.
        """
        cache = _ChapterCache(out_dir)
        key = _chapter_key(ch, plan)
        cached = cache.get(key)
        if cached is not None:
            return cached

        solver = _chapter_solver(ch, plan)
        rag = RagResult(keywords=list(solver.keywords), hits=[], backend="lesson")
        request = ProblemRequest(prompt=_chapter_prompt(ch, plan))
        brief = json.dumps({"chapter": ch.title, "goal": ch.goal, "beats": ch.beats,
                            "narration": ch.narration})
        try:
            scene = await self.manim.generate_scene_async(request, solver, rag, self.settings)
            scene = await self.manim.render_scene_with_repair(
                scene, self.settings, quality=quality, brief=brief
            )
        except Exception as exc:  # noqa: BLE001 — one bad chapter must not kill the lesson
            log.warning("Chapter '%s' failed to render: %s", ch.title, exc)
            return None
        if scene.status == "rendered" and scene.video_path:
            cache.put(key, scene)
        return scene

    async def _narrate_chapters(
        self, chapters: list[LessonChapter], rendered: list[SceneBundle | None], out_dir: Path
    ) -> tuple[list[Path], list[tuple[str, float]]]:
        from aetherlab.services.voiceover import narrate_segment

        clips: list[Path] = []
        segments: list[tuple[str, float]] = []
        # rendered is index-aligned with the renderable chapters
        ch_iter = [c for c in chapters if c.kind in _RENDERED_KINDS]
        for ch, scene in zip(ch_iter, rendered, strict=False):
            if not scene or scene.status != "rendered" or not scene.video_path:
                continue
            video = Path(scene.video_path)
            if self.settings.narration_enabled and ch.narration.strip():
                narrated, dur = await narrate_segment(
                    video, ch.narration, out_dir,
                    voice=self.settings.tts_voice, rate=self.settings.tts_rate,
                )
                clip = narrated or video
            else:
                from aetherlab.services.voiceover import get_duration
                clip = video
                dur = await get_duration(video)
            clips.append(clip)
            segments.append((ch.narration, dur))
        return clips, segments

    async def _assemble(
        self, clips: list[Path], segments: list[tuple[str, float]], out_dir: Path
    ) -> tuple[Path | None, Path | None]:
        from aetherlab.services.assembly import assemble_lesson
        from aetherlab.services.voiceover import build_srt

        if not clips:
            return None, None
        lesson_mp4 = out_dir / "lesson.mp4"
        video = await assemble_lesson(clips, lesson_mp4)
        srt_path = None
        srt = build_srt(segments)
        if srt.strip():
            srt_path = out_dir / "lesson.srt"
            srt_path.write_text(srt, encoding="utf-8")
        return video, srt_path


# ── chapter → scene inputs ───────────────────────────────────────────────────


def _chapter_prompt(ch: LessonChapter, plan: LessonPlan) -> str:
    beats = "; ".join(ch.beats) if ch.beats else ch.goal
    return f"{plan.topic} — {ch.title}: {ch.goal}. {beats}"


def _chapter_solver(ch: LessonChapter, plan: LessonPlan) -> SolverResult:
    """Synthesize a SolverResult so the existing scene generator has chapter
    content to visualize (summary/steps/equations/variables)."""
    from aetherlab.services.llm import DEFAULT_VARIABLES, extract_keywords
    from aetherlab.services.scene_templates import detect_domain

    keywords = extract_keywords(f"{plan.topic} {ch.title} {ch.goal}") or [plan.topic]
    domain = detect_domain(keywords, {})
    variables = dict(_DOMAIN_VARS.get(domain, DEFAULT_VARIABLES))
    return SolverResult(
        summary=ch.goal or ch.title,
        derivation_steps=list(ch.beats) or [ch.goal],
        keywords=keywords,
        variables=variables,
        model_name="lesson-chapter",
        key_equations=list(ch.key_equations),
    )


_DOMAIN_VARS: dict[str, dict[str, float]] = {
    "oscillator": {"damping": 0.15, "stiffness": 1.0, "mass": 1.0},
    "pendulum": {"gravity": 9.81, "length": 1.0},
    "orbit": {"eccentricity": 0.5, "semi_major": 1.0},
    "wave": {"frequency": 2.0, "wave_speed": 1.0},
}


# ── per-chapter cache (edit ch.N ⇒ only ch.N re-renders) ─────────────────────


def _lesson_id(plan: LessonPlan) -> str:
    return hashlib.sha256((plan.topic + "|" + plan.audience).encode("utf-8")).hexdigest()[:12]


def _chapter_key(ch: LessonChapter, plan: LessonPlan) -> str:
    payload = json.dumps(
        {"topic": plan.topic, "audience": plan.audience, "chapter": ch.to_json()},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class _ChapterCache:
    """Disk-backed map of chapter-key → rendered SceneBundle (video reused only
    if the file still exists)."""

    def __init__(self, out_dir: Path) -> None:
        self.path = out_dir / "chapters_cache.json"

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def get(self, key: str) -> SceneBundle | None:
        entry = self._load().get(key)
        if not entry:
            return None
        scene = SceneBundle.from_json(entry, cached=True)
        if scene.video_path and Path(scene.video_path).exists():
            return scene
        return None

    def put(self, key: str, scene: SceneBundle) -> None:
        data = self._load()
        data[key] = scene.to_json()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=1), encoding="utf-8")
        except OSError:
            pass
