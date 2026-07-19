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

    def to_json(self) -> JsonDict:
        return asdict(self)

    @classmethod
    def from_json(cls, payload: JsonDict, *, cached: bool = False) -> "SolverResult":
        data = dict(payload)
        data["cached"] = cached
        plot = data.get("plot")
        numeric_spec = data.get("numeric_spec")
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
        )


@dataclass
class RagHit:
    source_path: str
    page_number: int | None
    score: float
    excerpt: str

    @property
    def source_name(self) -> str:
        return Path(self.source_path).name


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

    def to_json(self) -> JsonDict:
        data = asdict(self)
        return data

    @classmethod
    def from_json(cls, payload: JsonDict, *, cached: bool = False) -> "SceneBundle":
        return cls(
            class_name=str(payload.get("class_name", "AetherLabScene")),
            code=str(payload.get("code", "")),
            engine=str(payload.get("engine", "cached")),
            status=str(payload.get("status", "cached")),
            diagnostics=list(payload.get("diagnostics", [])),
            cached=cached,
            video_path=str(payload.get("video_path", "")),
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
class LessonPlan:
    """Which output modalities a given problem actually warrants.

    Produced by services/planner.py (one LLM classification call with a
    deterministic keyword heuristic fallback). The pipeline gates each stage on
    these flags so a problem only pays for the outputs it needs.
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
    def from_json(cls, payload: JsonDict, *, model_name: str | None = None) -> "LessonPlan":
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
    plan: "LessonPlan" = field(default_factory=lambda: LessonPlan())


@dataclass
class PipelineError:
    stage: str
    message: str
    traceback: str = ""
