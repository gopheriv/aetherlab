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
        )


@dataclass
class PipelineResult:
    request: ProblemRequest
    cache_key: str
    solver: SolverResult
    rag: RagResult
    scene: SceneBundle


@dataclass
class PipelineError:
    stage: str
    message: str
    traceback: str = ""
