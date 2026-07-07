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
        regenerate: bool = False,
        cancel_check: "Callable[[], bool] | None" = None,
        progress: ProgressCb | None = None,
    ) -> LessonBundle:
        """Plan, render, narrate, and assemble a lesson. Never raises.

        The planned (and fact-checked) LessonPlan is cached on disk keyed by
        topic+audience, so re-opening a topic is instant — it skips both the
        planner LLM call and the grounding pass and goes straight to the
        per-chapter render cache. ``regenerate=True`` ignores that cache (and
        the chapter clips) to build the lesson fresh.

        ``cancel_check`` is polled cooperatively (before each chapter and before
        assembly); when it returns True the lesson stops after the current
        chapter and returns a ``cancelled`` bundle with whatever rendered so far
        — the student never waits for a run they abandoned.
        """
        def report(msg: str, done: int, total: int) -> None:
            if progress:
                try:
                    progress(msg, done, total)
                except Exception:  # noqa: BLE001
                    pass
            log.info("Lesson: %s (%d/%d)", msg, done, total)

        def cancelled() -> bool:
            try:
                return bool(cancel_check and cancel_check())
            except Exception:  # noqa: BLE001
                return False

        plan_cache = _PlanCache(self.settings)
        plan = None if regenerate else plan_cache.get(topic, audience)
        if plan is not None:
            report("Reusing cached lesson plan", 0, 1)
        else:
            report("Planning lesson", 0, 1)
            plan = await plan_lesson(topic, self.settings, audience=audience)
            # Ground the plan in textbooks: attach citations + fact-check
            # narration (fail-soft — corrected narration then flows into render
            # + voiceover).
            report("Grounding in textbooks", 0, 1)
            try:
                from aetherlab.services.fact_check import fact_check_lesson

                plan = await fact_check_lesson(plan, self.settings)
            except Exception:  # noqa: BLE001 — grounding must never block a lesson
                pass
            plan_cache.put(topic, audience, plan)
        render_jobs = [(i, c) for i, c in enumerate(plan.chapters) if c.kind in _RENDERED_KINDS]
        chapters = [c for _, c in render_jobs]
        chapter_plan_indexes = [i for i, _ in render_jobs]
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
                if cancelled():
                    return index, None  # skip cheaply once cancel is requested
                report(f"Chapter {index + 1}/{total}: {ch.title}", done, total)
                bundle = await self._render_chapter(ch, plan, out_dir, quality, regenerate)
                async with lock:
                    done += 1
                    report(f"Chapter {index + 1}/{total} done", done, total)
                return index, bundle

        results = await asyncio.gather(
            *(do_chapter(i, ch) for i, ch in enumerate(chapters))
        )
        by_index = {i: b for i, b in results}
        rendered_items = [
            (chapter_plan_indexes[i], chapters[i], by_index[i])
            for i in range(len(chapters))
            if by_index.get(i) is not None
        ]
        rendered = [scene for _, _, scene in rendered_items]
        rendered_chapter_indexes = [idx for idx, _, _ in rendered_items]

        if cancelled():
            report("Lesson cancelled", done, total)
            return LessonBundle(
                plan=plan,
                chapter_scenes=[b for b in rendered if b is not None],
                video_path="",
                status="cancelled",
                rendered_chapter_indexes=rendered_chapter_indexes,
            )

        # Narrate each rendered chapter + accumulate a transcript timeline.
        report("Narrating chapters", total, total)
        clips, segments, titles = await self._narrate_chapters(rendered_items, out_dir)

        # Assemble into one produced lesson (title cards + crossfades) + .srt.
        report("Assembling lesson", total, total)
        video_path, srt_path, offsets = await self._assemble(
            clips, segments, titles, plan, out_dir
        )

        status = "assembled" if video_path else ("rendering" if rendered else "error")
        report("Lesson ready" if video_path else "Lesson incomplete", total, total)
        bundle = LessonBundle(
            plan=plan,
            chapter_scenes=[b for b in rendered if b is not None],
            video_path=str(video_path) if video_path else "",
            status=status,
            chapter_offsets=offsets,
            rendered_chapter_indexes=rendered_chapter_indexes,
        )
        # stash the srt path on the plan-less side via diagnostics-free attr
        bundle_srt = str(srt_path) if srt_path else ""
        setattr(bundle, "srt_path", bundle_srt)  # noqa: B010 — optional extra
        return bundle

    async def _render_chapter(
        self, ch: LessonChapter, plan: LessonPlan, out_dir: Path, quality: str,
        regenerate: bool = False,
    ) -> SceneBundle | None:
        """Render one chapter clip, reusing the existing scene pipeline.

        Cache-keyed by the chapter's plan: an unchanged chapter reuses its clip
        unless ``regenerate`` forces a fresh render.
        """
        cache = _ChapterCache(out_dir)
        key = _chapter_key(ch, plan)
        if not regenerate:
            cached = cache.get(key)
            if cached is not None and _scene_cache_usable(cached, self.settings):
                return cached

        solver = _chapter_solver(ch, plan)
        rag = RagResult(keywords=list(solver.keywords), hits=[], backend="lesson")
        request = ProblemRequest(prompt=_chapter_prompt(ch, plan))
        aspect = _chapter_aspect(ch, plan)
        brief = json.dumps({"chapter": ch.title, "goal": ch.goal, "beats": ch.beats,
                            "narration": ch.narration})
        try:
            scene = await self.manim.generate_scene_async(
                request, solver, rag, self.settings, aspect=aspect
            )
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
        self,
        rendered_items: list[tuple[int, LessonChapter, SceneBundle | None]],
        out_dir: Path,
    ) -> tuple[list[Path], list[tuple[str, float]], list[str]]:
        from aetherlab.services.voiceover import narrate_segment

        clips: list[Path] = []
        segments: list[tuple[str, float]] = []
        titles: list[str] = []
        for _plan_index, ch, scene in rendered_items:
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
            titles.append(ch.title)
        return clips, segments, titles

    async def _assemble(
        self, clips: list[Path], segments: list[tuple[str, float]],
        titles: list[str], plan: LessonPlan, out_dir: Path,
    ) -> tuple[Path | None, Path | None, list[float]]:
        from aetherlab.services.assembly import assemble_lesson
        from aetherlab.services.scene_templates import load_scene_palette
        from aetherlab.services.voiceover import build_srt

        if not clips:
            return None, None, []
        lesson_mp4 = out_dir / "lesson.mp4"
        palette = load_scene_palette(getattr(self.settings, "data_dir", None))
        video, offsets = await assemble_lesson(
            clips, lesson_mp4,
            lesson_title=plan.title or plan.topic,
            lesson_subtitle=_audience_label(plan.audience),
            chapter_titles=titles,
            palette=palette,
            return_offsets=True,
        )
        srt_path = None
        # Time the subtitles to the PRODUCED timeline (offsets account for the
        # title cards + crossfades) so cues stay in sync with lesson.mp4.
        srt = build_srt(segments, offsets or None)
        if srt.strip():
            srt_path = out_dir / "lesson.srt"
            srt_path.write_text(srt, encoding="utf-8")
        return video, srt_path, offsets


# ── chapter → scene inputs ───────────────────────────────────────────────────


_AUDIENCE_LABELS = {
    "high_school": "High-school level",
    "ap": "AP / honors level",
    "undergrad": "Undergraduate level",
}


def _audience_label(audience: str) -> str:
    return _AUDIENCE_LABELS.get(audience, "")


def _chapter_prompt(ch: LessonChapter, plan: LessonPlan) -> str:
    beats = "; ".join(ch.beats) if ch.beats else ch.goal
    return f"{plan.topic} — {ch.title}: {ch.goal}. {beats}"


# Words that mark a chapter as math/derivation- or recap-focused, so a keyless
# chapter picks the right template aspect even when its kind is a plain "scene".
_MATH_WORDS = ("math", "equation", "deriv", "formula", "solve", "law", "proof")
_RECAP_WORDS = ("recap", "summary", "summar", "review", "takeaway", "consolidat")


def _chapter_aspect(ch: LessonChapter, plan: LessonPlan) -> str:
    """Pick a template aspect (setup/evolution/math/recap) for a chapter.

    Keyed off the chapter's *role* — kind first, then goal/title keywords, then
    position — so that a lesson whose chapters all detect the same domain still
    renders as visually distinct clips. The first renderable chapter is the
    "setup"; equation/recap chapters get their matching aspect; everything else
    is "evolution" (the full dynamic motion).
    """
    kind = (ch.kind or "").lower()
    if kind == "recap":
        return "recap"
    if kind == "equation_card":
        return "math"
    text = f"{ch.title} {ch.goal}".lower()
    if any(w in text for w in _RECAP_WORDS):
        return "recap"
    if any(w in text for w in _MATH_WORDS):
        return "math"
    renderable = [c for c in plan.chapters if c.kind in _RENDERED_KINDS]
    # Compare by object identity, not .id: an LLM-planned lesson may omit chapter
    # ids (from_json defaults them to ""), and "" == "" would tag EVERY id-less
    # chapter as "setup", collapsing the setup→evolution→math→recap arc.
    if renderable and renderable[0] is ch:
        return "setup"
    return "evolution"


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


def _scene_cache_usable(scene: SceneBundle, settings: "AppSettings") -> bool:
    min_score = float(getattr(settings, "min_quality_score", 0.0) or 0.0)
    if min_score <= 0:
        return True
    return float(getattr(scene, "quality_score", 0.0) or 0.0) >= min_score


_DOMAIN_VARS: dict[str, dict[str, float]] = {
    "oscillator": {"damping": 0.15, "stiffness": 1.0, "mass": 1.0},
    "pendulum": {"gravity": 9.81, "length": 1.0},
    "orbit": {"eccentricity": 0.5, "semi_major": 1.0},
    "em_field": {"separation": 2.2},
    "wave": {"frequency": 2.0, "wave_speed": 1.0},
}


# ── per-chapter cache (edit ch.N ⇒ only ch.N re-renders) ─────────────────────


def _lesson_id(plan: LessonPlan) -> str:
    return _topic_id(plan.topic, plan.audience)


def _topic_id(topic: str, audience: str) -> str:
    return hashlib.sha256(
        ((topic or "").strip().lower() + "|" + audience).encode("utf-8")
    ).hexdigest()[:12]


class _PlanCache:
    """Disk-backed cache of the planned+grounded LessonPlan, keyed by
    topic+audience, so re-opening a topic skips planning and grounding.

    Stored under the data dir (persists across runs, unlike the temp render
    cache). Fail-soft: any read/write error simply misses the cache.
    """

    def __init__(self, settings: "AppSettings") -> None:
        base = getattr(settings, "data_dir", None) or _LESSON_DIR
        self.dir = Path(base) / "lesson_plans"

    def _path(self, topic: str, audience: str) -> Path:
        return self.dir / f"{_topic_id(topic, audience)}.json"

    def get(self, topic: str, audience: str) -> LessonPlan | None:
        path = self._path(topic, audience)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        plan = LessonPlan.from_json(payload, cached=True)
        plan.cached = True  # from_json honours a stored cached=False; force it
        return plan if plan.chapters else None

    def put(self, topic: str, audience: str, plan: LessonPlan) -> None:
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            self._path(topic, audience).write_text(
                json.dumps(plan.to_json(), indent=1), encoding="utf-8"
            )
        except OSError:
            pass


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
