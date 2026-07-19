"""Typed payloads moving through the AetherLab pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


JsonDict = dict[str, Any]


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class ProblemRequest:
    prompt: str
    parameters: dict[str, float] = field(default_factory=dict)
    session_id: str = "default"
    created_at: str = field(default_factory=utc_now_iso)

    def normalized_prompt(self) -> str:
        return " ".join(self.prompt.strip().split())

    def canonical_payload(self) -> JsonDict:
        return {
            "prompt": self.normalized_prompt(),
            "parameters": {key: self.parameters[key] for key in sorted(self.parameters)},
            "session_id": self.session_id,
        }


@dataclass
class SolverResult:
    summary: str
    derivation_steps: list[str]
    keywords: list[str]
    variables: dict[str, float]
    model_name: str
    raw_response: str = ""
    cached: bool = False
    # Optional plottable-curve payload (see services/plotting.py). Old cache
    # rows lack the key and load as None (legacy name-based canvas curves).
    plot: dict | None = None
    # Optional ODE ground-truth spec (see services/numeric.py): a system the
    # canvas/PDF integrate numerically instead of trusting a guessed curve.
    numeric_spec: dict | None = None
    # Governing equations as LaTeX strings (mathtext subset), most important
    # first — drives the hero equation banner. Old cache rows load as [].
    key_equations: list[str] = field(default_factory=list)

    def to_json(self) -> JsonDict:
        return asdict(self)

    @classmethod
    def from_json(cls, payload: JsonDict, *, cached: bool = False) -> "SolverResult":
        data = dict(payload)
        data["cached"] = cached
        plot = data.get("plot")
        numeric_spec = data.get("numeric_spec")
        equations = data.get("key_equations")
        return cls(
            summary=str(data.get("summary", "")),
            derivation_steps=list(data.get("derivation_steps", [])),
            keywords=list(data.get("keywords", [])),
            variables={str(k): float(v) for k, v in dict(data.get("variables", {})).items()},
            model_name=str(data.get("model_name", "cached")),
            raw_response=str(data.get("raw_response", "")),
            cached=bool(data.get("cached", cached)),
            plot=plot if isinstance(plot, dict) else None,
            numeric_spec=numeric_spec if isinstance(numeric_spec, dict) else None,
            key_equations=[str(e) for e in equations] if isinstance(equations, list) else [],
        )


@dataclass
class RagHit:
    source_path: str
    page_number: int | None
    score: float
    excerpt: str
    # v3: origin distinguishes local library hits from web references
    # (e.g. Wikipedia); source_label is a clean display title. Both default so
    # old cached RagResult rows deserialize unchanged.
    source_label: str | None = None
    origin: str = "library"

    @property
    def source_name(self) -> str:
        return self.source_label or Path(self.source_path).name

    @property
    def is_web(self) -> bool:
        return self.origin == "web" or self.source_path.startswith(("http://", "https://"))


@dataclass
class RagResult:
    keywords: list[str]
    hits: list[RagHit]
    backend: str
    cached: bool = False

    def to_json(self) -> JsonDict:
        return {
            "keywords": self.keywords,
            "hits": [asdict(hit) for hit in self.hits],
            "backend": self.backend,
            "cached": self.cached,
        }

    @classmethod
    def from_json(cls, payload: JsonDict, *, cached: bool = False) -> "RagResult":
        return cls(
            keywords=list(payload.get("keywords", [])),
            hits=[RagHit(**hit) for hit in payload.get("hits", [])],
            backend=str(payload.get("backend", "cached")),
            cached=cached,
        )


@dataclass
class SceneBundle:
    class_name: str
    code: str
    engine: str
    status: str
    diagnostics: list[str] = field(default_factory=list)
    cached: bool = False
    video_path: str = ""
    # Creative treatment the scene implements (see SceneGenerator.storyboard).
    # The visual critic judges renders against it. Old cache rows load as None.
    storyboard: dict | None = None
    # Classified render-failure kind (latex/hallucinated-api/timeout/ffmpeg/oom/
    # spawn/""), set by the renderer so the UI and repair loop can react. Old
    # cache rows load as "".
    failure_kind: str = ""
    # When narration is added, video_path points at the narrated mp4 and this
    # keeps the original silent render as a fallback. Old cache rows load as "".
    silent_video_path: str = ""
    # Persisted perceptual-quality metadata from services/scene_critic.py.
    # Old cache rows load as 0/"", preserving today's reuse behavior unless a
    # nonzero min_quality_score setting opts into cache rejection.
    quality_score: float = 0.0
    critique_verdict: str = ""
    critique_issues: list[str] = field(default_factory=list)
    # Per-axis 0-2 critic breakdown (keys == scene_critic.CRITIC_AXES). Empty on
    # old cache rows and when no judgement was made; additive, so reuse behaviour
    # is unchanged.
    critique_breakdown: dict[str, float] = field(default_factory=dict)

    def to_json(self) -> JsonDict:
        data = asdict(self)
        return data

    @classmethod
    def from_json(cls, payload: JsonDict, *, cached: bool = False) -> "SceneBundle":
        storyboard = payload.get("storyboard")
        return cls(
            class_name=str(payload.get("class_name", "AetherLabScene")),
            code=str(payload.get("code", "")),
            engine=str(payload.get("engine", "cached")),
            status=str(payload.get("status", "cached")),
            diagnostics=list(payload.get("diagnostics", [])),
            failure_kind=str(payload.get("failure_kind", "")),
            silent_video_path=str(payload.get("silent_video_path", "")),
            cached=cached,
            video_path=str(payload.get("video_path", "")),
            storyboard=storyboard if isinstance(storyboard, dict) else None,
            quality_score=float(payload.get("quality_score", 0.0) or 0.0),
            critique_verdict=str(payload.get("critique_verdict", "")),
            critique_issues=[str(i) for i in payload.get("critique_issues", [])]
            if isinstance(payload.get("critique_issues"), list) else [],
            critique_breakdown={
                str(k): float(v)
                for k, v in payload.get("critique_breakdown", {}).items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            }
            if isinstance(payload.get("critique_breakdown"), dict) else {},
        )


@dataclass
class NumericSolution:
    """Ground-truth trajectory from integrating an ODE spec (services/numeric.py).

    `t` is the time grid; `states` maps each state-variable name to its values
    over that grid. `ok` is False (with a `note`) when integration was skipped
    or failed, so callers can fall back to the analytic curve.
    """

    t: list[float] = field(default_factory=list)
    states: dict[str, list[float]] = field(default_factory=dict)
    observe: str = ""
    method: str = "RK45"
    ok: bool = False
    note: str = ""

    def series(self, name: str = "") -> list[float]:
        """Values of the observed (or named) state variable."""
        key = name or self.observe or (next(iter(self.states), ""))
        return self.states.get(key, [])


@dataclass
class OutputPlan:
    """Which output modalities a given problem actually warrants.

    Produced by services/planner.py (one LLM classification call with a
    deterministic keyword heuristic fallback). The pipeline gates each stage on
    these flags so a problem only pays for the outputs it needs. (Distinct from
    LessonPlan below, which is the multi-chapter narrated-lesson structure.)
    """

    needs_numeric: bool = False
    needs_2d: bool = True
    needs_3d: bool = False
    needs_animation: bool = True
    needs_pdf: bool = True
    rationale: str = ""
    model_name: str = "heuristic-fallback"

    def enabled(self) -> list[str]:
        """Human-readable list of the modalities this plan turns on."""
        flags = [
            ("numeric", self.needs_numeric),
            ("2d", self.needs_2d),
            ("3d", self.needs_3d),
            ("animation", self.needs_animation),
            ("pdf", self.needs_pdf),
        ]
        return [name for name, on in flags if on]

    def to_json(self) -> JsonDict:
        return asdict(self)

    @classmethod
    def from_json(cls, payload: JsonDict, *, model_name: str | None = None) -> "OutputPlan":
        data = dict(payload)

        def _flag(key: str, default: bool) -> bool:
            value = data.get(key, default)
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.strip().lower() in {"true", "yes", "1", "y"}
            return bool(value)

        return cls(
            needs_numeric=_flag("needs_numeric", False),
            needs_2d=_flag("needs_2d", True),
            needs_3d=_flag("needs_3d", False),
            needs_animation=_flag("needs_animation", True),
            needs_pdf=_flag("needs_pdf", True),
            rationale=str(data.get("rationale", "")),
            model_name=str(model_name or data.get("model_name", "cached")),
        )


@dataclass
class PipelineResult:
    request: ProblemRequest
    cache_key: str
    solver: SolverResult
    rag: RagResult
    scene: SceneBundle
    plan: "OutputPlan" = field(default_factory=lambda: OutputPlan())


@dataclass
class PipelineError:
    stage: str
    message: str
    traceback: str = ""


# ── Topic-explainer lesson model (multi-chapter narrated lessons) ────────────


@dataclass
class LessonChapter:
    """One teaching beat of a lesson.

    kind: 'scene' (a rendered Manim chapter), 'equation_card' (a typeset
    still), 'interactive' (hand off to the live canvas), or 'recap'.
    """
    id: str
    title: str
    goal: str = ""
    kind: str = "scene"
    beats: list[str] = field(default_factory=list)
    narration: str = ""
    key_equations: list[str] = field(default_factory=list)
    citation_query: str = ""
    # Resolved textbook citations (source labels) + a fact-check note, filled by
    # services/fact_check.py. Old caches load with empty defaults.
    citations: list[str] = field(default_factory=list)
    fact_check: str = ""

    def to_json(self) -> JsonDict:
        return asdict(self)

    @classmethod
    def from_json(cls, payload: JsonDict) -> "LessonChapter":
        data = dict(payload)
        return cls(
            id=str(data.get("id", "")),
            title=str(data.get("title", "")),
            goal=str(data.get("goal", "")),
            kind=str(data.get("kind", "scene")),
            beats=[str(b) for b in data.get("beats", [])],
            narration=str(data.get("narration", "")),
            key_equations=[str(e) for e in data.get("key_equations", [])],
            citation_query=str(data.get("citation_query", "")),
            citations=[str(c) for c in data.get("citations", [])],
            fact_check=str(data.get("fact_check", "")),
        )


@dataclass
class LessonQuestion:
    """A check-yourself item. Empty ``choices`` => an open question."""
    q: str
    answer: str = ""
    why: str = ""
    choices: list[str] = field(default_factory=list)

    @property
    def is_open(self) -> bool:
        return not self.choices

    def to_json(self) -> JsonDict:
        return asdict(self)

    @classmethod
    def from_json(cls, payload: JsonDict) -> "LessonQuestion":
        data = dict(payload)
        return cls(
            q=str(data.get("q", "")),
            answer=str(data.get("answer", "")),
            why=str(data.get("why", "")),
            choices=[str(c) for c in data.get("choices", [])],
        )


@dataclass
class LessonPlan:
    """A topic turned into a structured, narrated curriculum (see
    services/lesson_planner.py). Defensive from_json so old caches load."""
    title: str
    topic: str = ""
    audience: str = "undergrad"  # high_school | ap | undergrad
    prerequisites: list[str] = field(default_factory=list)
    objectives: list[str] = field(default_factory=list)
    misconception: str = ""
    chapters: list[LessonChapter] = field(default_factory=list)
    questions: list[LessonQuestion] = field(default_factory=list)
    model_name: str = ""
    cached: bool = False

    def to_json(self) -> JsonDict:
        return {
            "title": self.title,
            "topic": self.topic,
            "audience": self.audience,
            "prerequisites": self.prerequisites,
            "objectives": self.objectives,
            "misconception": self.misconception,
            "chapters": [c.to_json() for c in self.chapters],
            "questions": [q.to_json() for q in self.questions],
            "model_name": self.model_name,
            "cached": self.cached,
        }

    @classmethod
    def from_json(cls, payload: JsonDict, *, cached: bool = False) -> "LessonPlan":
        data = dict(payload)
        audience = str(data.get("audience", "undergrad")).lower().replace(" ", "_")
        if audience not in {"high_school", "ap", "undergrad"}:
            audience = "undergrad"
        return cls(
            title=str(data.get("title", "")) or "Untitled lesson",
            topic=str(data.get("topic", "")),
            audience=audience,
            prerequisites=[str(p) for p in data.get("prerequisites", [])],
            objectives=[str(o) for o in data.get("objectives", [])],
            misconception=str(data.get("misconception", "")),
            chapters=[
                LessonChapter.from_json(c)
                for c in data.get("chapters", [])
                if isinstance(c, dict)
            ],
            questions=[
                LessonQuestion.from_json(q)
                for q in data.get("questions", [])
                if isinstance(q, dict)
            ],
            model_name=str(data.get("model_name", "cached")),
            cached=bool(data.get("cached", cached)),
        )


@dataclass
class LessonBundle:
    """A planned (and, after Phase 3, rendered + assembled) lesson.

    chapter_scenes and video_path are populated by the lesson pipeline; the
    plan alone is a valid Phase-1 result (status 'planned').
    """
    plan: LessonPlan
    chapter_scenes: list[SceneBundle] = field(default_factory=list)
    video_path: str = ""
    status: str = "planned"  # planned | rendering | assembled | error
    cached: bool = False
    # Start time (seconds) of each rendered chapter clip WITHIN the assembled
    # video, accounting for intro/chapter title cards + crossfades. Used to seek
    # the inline player and to time subtitles; empty for old caches / plain
    # concats, where the UI falls back to a plain cumulative sum.
    chapter_offsets: list[float] = field(default_factory=list)
    # Plan-chapter indexes for chapter_scenes/chapter_offsets. A failed middle
    # render leaves a gap in plan.chapters; this keeps surviving clips mapped to
    # their original titles/narration/UI outline rows. Empty for old caches.
    rendered_chapter_indexes: list[int] = field(default_factory=list)

    def to_json(self) -> JsonDict:
        return {
            "plan": self.plan.to_json(),
            "chapter_scenes": [s.to_json() for s in self.chapter_scenes],
            "video_path": self.video_path,
            "status": self.status,
            "cached": self.cached,
            "chapter_offsets": list(self.chapter_offsets),
            "rendered_chapter_indexes": list(self.rendered_chapter_indexes),
        }

    @classmethod
    def from_json(cls, payload: JsonDict, *, cached: bool = False) -> "LessonBundle":
        data = dict(payload)
        return cls(
            plan=LessonPlan.from_json(data.get("plan", {}), cached=cached),
            chapter_scenes=[
                SceneBundle.from_json(s, cached=cached)
                for s in data.get("chapter_scenes", [])
                if isinstance(s, dict)
            ],
            video_path=str(data.get("video_path", "")),
            status=str(data.get("status", "planned")),
            cached=bool(data.get("cached", cached)),
            chapter_offsets=[
                float(x)
                for x in data.get("chapter_offsets", [])
                if isinstance(x, (int, float))
            ],
            rendered_chapter_indexes=[
                int(x)
                for x in data.get("rendered_chapter_indexes", [])
                if isinstance(x, int)
            ],
        )
