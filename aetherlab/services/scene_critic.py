"""Perceptual quality loop: look at the rendered video and judge it.

This closes the pipeline's biggest gap — historically nothing ever *watched*
the output; success meant "an MP4 exists". The critic samples frames from the
rendered video with ffmpeg, shows them (with the creative brief/storyboard) to
a vision-capable model on the same OpenAI-compatible endpoint, and returns a
structured verdict: ship, or revise with concrete critique points.

Wholly optional: without ``settings.vision_model`` (env AETHERLAB_VISION_MODEL
or app-config "vision_model") every entry point degrades to "ship" so the
pipeline behaves exactly as before. Frame extraction requires ffmpeg (already
an optional dependency for GIF export); its absence also degrades gracefully.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

from aetherlab.services.model_policy import codegen_request_kwargs, request_temperature

if TYPE_CHECKING:
    from aetherlab.core.settings import AppSettings

log = logging.getLogger(__name__)

_FRAME_DIR = Path(tempfile.gettempdir()) / "aetherlab" / "critic_frames"

# The five rubric axes, each scored 0-2, summing to the 0-10 total. Fixed and
# ordered so per-axis scores are comparable across runs and models — the
# flywheel ranks candidates on these, and Phase 3 learns from the weakest axis.
CRITIC_AXES: tuple[str, ...] = (
    "legibility",
    "composition",
    "palette",
    "structure",
    "substance",
)
_AXIS_MAX = 2.0

CRITIC_SYSTEM_PROMPT = """You are the AetherLab visual critic — a demanding animation director reviewing
frames sampled uniformly from a rendered Manim physics scene. Judge the RENDER,
not the idea. Score each axis from 0 (broken) to 2 (excellent):

1. LEGIBILITY — all text readable, nothing cut off by the frame edge,
   no overlapping elements collapsing into clutter.
2. COMPOSITION — clear focal point, balanced negative space, scaffolding
   (axes/grids) dimmer than the physics.
3. PALETTE — few deliberate colors used consistently; accent reserved for
   the climax.
4. STRUCTURE — evidence of a beginning (setup), middle (evolution), and end
   (reveal); the final frames must not be identical to the middle (no frozen
   ending) and not empty.
5. SUBSTANCE — the physics is actually visualized (motion, curves, fields),
   not just a title card; frames change meaningfully across the video.

For layout reports, overlay a 6×6 grid on each frame: columns C1-C6 run left to
right and rows R1-R6 run top to bottom. Name the cells when locating clipped,
crowded, or overlapping objects. A deterministic check may also accompany the
frames; use it as evidence, not as a substitute for looking at the images.

Physics expectations may be supplied separately. Check only facts that the
sampled frames make observable. If visible motion contradicts one, add an issue
prefixed `physics:`. Never certify equations, values, or motion hidden between
sampled frames from appearance alone.

The total score is the sum of the five axes (0-10).

Return STRICT JSON only:
{"verdict": "ship" | "revise",
 "score": <0-10>,
 "breakdown": {"legibility": 0-2, "composition": 0-2, "palette": 0-2,
               "structure": 0-2, "substance": 0-2},
 "problem_frames": [<1-based frame numbers with actionable issues>],
 "issues": ["specific, actionable problems, worst first; name the weak axis"],
 "strengths": ["what works"]}

Verdict "ship" requires score >= 7 and no legibility failures. Be strict:
a bare axes-plus-curve screenshot deserves a 4 at most."""


@dataclass
class Critique:
    verdict: str  # "ship" | "revise" | "skipped"
    score: float = 0.0
    issues: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    # Per-axis 0-2 scores (keys == CRITIC_AXES). Empty when no judgement was
    # made. `breakdown_source` records how it was produced so callers never
    # mistake an approximation or a static proxy for a real vision judgement:
    #   "vision"        — the vision model returned a valid per-axis breakdown
    #   "vision-approx" — vision gave a score but a malformed/absent breakdown,
    #                     reconstructed evenly from the aggregate score
    #   "static"        — no vision available; heuristic proxy from static gates
    #   ""              — no breakdown at all (skipped, empty)
    breakdown: dict[str, float] = field(default_factory=dict)
    breakdown_source: str = ""
    retried: bool = False
    problem_times_s: list[float] = field(default_factory=list)
    model_used: str = ""

    @property
    def should_revise(self) -> bool:
        return self.verdict == "revise"


def _coerce_breakdown(raw: object, score: float) -> tuple[dict[str, float], str]:
    """Validate a model-supplied per-axis breakdown against the fixed schema.

    Returns ``(breakdown, source)``. A well-formed breakdown (a dict carrying
    every axis with a numeric value) is clamped to 0-2 and returned as
    ``"vision"``. Anything malformed is NOT silently zeroed (the BUG-7 lesson):
    a valid aggregate ``score`` is instead spread evenly across the axes and
    flagged ``"vision-approx"`` so the caller knows it is an approximation.
    """
    if isinstance(raw, dict) and all(
        axis in raw and isinstance(raw.get(axis), (int, float)) and not isinstance(raw.get(axis), bool)
        for axis in CRITIC_AXES
    ):
        return {a: max(0.0, min(_AXIS_MAX, float(raw[a]))) for a in CRITIC_AXES}, "vision"
    # Approximate from the aggregate score, spread evenly, clamped per axis.
    per_axis = max(0.0, min(_AXIS_MAX, float(score) / len(CRITIC_AXES)))
    return {a: round(per_axis, 3) for a in CRITIC_AXES}, "vision-approx"


def extract_frames(
    video_path: str | Path,
    count: int = 6,
    sample_times_s: list[float] | None = None,
) -> list[Path]:
    """Sample frames uniformly or at declared beat/event times.

    Prefers PyAV (bundled with Manim ≥0.19 — always present when renders work,
    no subprocess); falls back to the ffmpeg CLI. Returns [] when neither is
    available or extraction fails — callers treat that as "cannot critique"
    and ship.
    """
    video = Path(video_path)
    if not video.exists():
        return []
    out_dir = _FRAME_DIR / video.stem
    if out_dir.exists():
        for old in out_dir.glob("*.png"):
            old.unlink(missing_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    duration = _probe_duration(video)
    times = _normalize_sample_times(duration, count, sample_times_s)
    frames = _extract_with_pyav(video, out_dir, count, times)
    if frames:
        return frames
    return _extract_with_ffmpeg(video, out_dir, count, times)


def _normalize_sample_times(
    duration: float, count: int, requested: list[float] | None,
) -> list[float]:
    if count <= 0:
        return []
    if requested:
        values = sorted({round(max(0.0, min(duration - 0.05, float(value))), 3)
                         for value in requested})
        if len(values) > count:
            values = [values[round(i * (len(values) - 1) / (count - 1))]
                      for i in range(count)] if count > 1 else [values[len(values) // 2]]
        return values
    return _sample_times(duration, count)


def _extract_with_pyav(
    video: Path, out_dir: Path, count: int, sample_times_s: list[float] | None = None,
) -> list[Path]:
    """Decode uniformly-spaced frames with PyAV (Manim's own video backend)."""
    try:
        import av
    except Exception:  # pragma: no cover — PyAV ships with manim
        return []
    try:
        paths: list[Path] = []
        with av.open(str(video)) as container:
            stream = container.streams.video[0]
            total = stream.frames or 0
            if total <= 0:
                total = sum(1 for _ in container.decode(stream))
                container.seek(0)
            if total <= 0:
                return []
            if sample_times_s and stream.average_rate:
                fps = float(stream.average_rate)
                wanted = {max(0, min(total - 1, round(time_s * fps)))
                          for time_s in sample_times_s}
            else:
                wanted = set(_sample_indices(total, count))
            for index, frame in enumerate(container.decode(stream)):
                if index in wanted:
                    image = frame.to_image()
                    if image.width > 640:
                        image = image.resize((640, int(image.height * 640 / image.width)))
                    path = out_dir / f"frame_{len(paths):02d}.png"
                    image.save(path)
                    paths.append(path)
                    if len(paths) >= count:
                        break
        return paths
    except Exception as exc:  # noqa: BLE001 — extraction is best-effort
        log.info("PyAV frame extraction failed (%s); trying ffmpeg CLI.", exc)
        return []


def _sample_indices(total: int, count: int) -> list[int]:
    """Inclusive, uniformly spaced frame indexes for a decoded stream."""
    if total <= 0 or count <= 0:
        return []
    if count == 1:
        return [total // 2]
    count = min(count, total)
    if count == 1:
        return [0]
    return sorted({round(i * (total - 1) / (count - 1)) for i in range(count)})


def _sample_times(duration: float, count: int) -> list[float]:
    """Inclusive timestamps for ffmpeg fallback extraction."""
    if duration <= 0 or count <= 0:
        return []
    if count == 1:
        return [duration / 2]
    end = max(duration - 0.05, 0.0)
    return [i * end / (count - 1) for i in range(count)]


def _extract_with_ffmpeg(
    video: Path, out_dir: Path, count: int, sample_times_s: list[float] | None = None,
) -> list[Path]:
    """CLI fallback: exact timestamps, including the end frame."""
    try:
        from aetherlab.core.proc import subprocess_kwargs

        duration = _probe_duration(video)
        times = sample_times_s or _sample_times(duration, count)
        for i, t in enumerate(times[:count]):
            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", str(video), "-ss", f"{t:.3f}",
                    "-frames:v", "1", "-vf", "scale=640:-1",
                    str(out_dir / f"frame_{i:02d}.png"),
                ],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
                **subprocess_kwargs(),
            )
        return sorted(out_dir.glob("frame_*.png"))[:count]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        log.info("Frame extraction unavailable (%s); skipping critique.", exc)
        return []


def _probe_duration(video: Path) -> float:
    try:
        from aetherlab.core.proc import subprocess_kwargs

        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(video)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
            **subprocess_kwargs(),
        )
        return max(float(result.stdout.strip()), 0.5)
    except Exception:  # noqa: BLE001
        return 15.0


async def critique_video(
    video_path: str | Path,
    brief: str,
    settings: "AppSettings",
    frame_count: int = 6,
    expected_physics: list[str] | None = None,
    event_times_s: list[float] | None = None,
) -> Critique:
    """Sample frames and ask the vision model for a verdict.

    ``brief`` is the creative intent (storyboard JSON or the problem prompt).
    Degrades to verdict "skipped" without a vision model, frames, or on any
    API failure — the pipeline then ships the render as before.
    """
    if not settings.vision_model or not settings.openai_api_key:
        return Critique(verdict="skipped")
    duration = _probe_duration(Path(video_path))
    sample_times = _normalize_sample_times(duration, frame_count, event_times_s)
    frames = (
        extract_frames(video_path, frame_count, sample_times)
        if event_times_s else extract_frames(video_path, frame_count)
    )
    if not frames:
        return Critique(verdict="skipped")
    sample_times = sample_times[:len(frames)]

    content: list[dict] = [
        {
            "type": "text",
            "text": (
                "## Creative intent this render must fulfil\n"
                f"{brief[:4000]}\n\n"
                "## Deterministic 6x6 layout coordinates\n"
                "Columns C1-C6 go left to right; rows R1-R6 go top to bottom. "
                "Use these cell labels in any layout issue.\n\n"
                "## Physics expectations from the numerical verifier\n"
                + ("\n".join(f"- {fact}" for fact in expected_physics[:8])
                   if expected_physics else "No numerical expectations were available.")
                + "\n\n"
                f"## {len(frames)} frames sampled "
                f"{'at storyboard beat anchors' if event_times_s else 'uniformly'}, in order:\n"
                + "\n".join(
                    f"Frame {index + 1}: approximately {time_s:.2f} seconds."
                    for index, time_s in enumerate(sample_times)
                )
                + "\nFor each issue, identify the affected frame number. Put all affected "
                "1-based frame numbers in `problem_frames`; use [] when none."
            ),
        }
    ]
    for frame in frames:
        b64 = base64.b64encode(frame.read_bytes()).decode("ascii")
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            }
        )

    try:
        from aetherlab.services.llm_client import make_client

        client = make_client(settings)
        models = [str(settings.vision_model)]
        language_model = str(getattr(settings, "llm_model", "") or "")
        if language_model and language_model not in models:
            models.append(language_model)
        # Skip a vision model this endpoint already rejected as unknown.
        endpoint = str(getattr(settings, "openai_base_url", "") or "")
        if len(models) > 1 and (endpoint, models[0]) in _UNAVAILABLE_VISION_MODELS:
            models = models[1:]
        response = None
        model_used = ""
        for index, model in enumerate(models):
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
                        {"role": "user", "content": content},
                    ],
                    temperature=request_temperature(settings, 0.2),
                    max_tokens=2048,
                    # A JSON verdict needs no chain of thought. With MiniMax
                    # thinking on, the reasoning used up the 2048-token budget
                    # and the critic got an empty reply, so every critique was
                    # silently "skipped" (live, 2026-09-30).
                    **codegen_request_kwargs(
                        SimpleNamespace(llm_model=model), minimax_thinking=False
                    ),
                )
                model_used = model
                break
            except Exception as exc:  # noqa: BLE001 - optional alternate model
                if index == 0 and len(models) > 1 and _is_unknown_model_error(exc):
                    _UNAVAILABLE_VISION_MODELS.add((endpoint, model))
                    log.info(
                        "Visual critic model %s is unavailable; retrying configured LLM %s.",
                        model, language_model,
                    )
                    continue
                raise
        if response is None:
            return Critique(verdict="skipped")
        from aetherlab.services.model_json import load_model_json

        raw = response.choices[0].message.content or ""
        payload = load_model_json(raw)
        verdict = str(payload.get("verdict", "ship")).lower()
        score = float(payload.get("score", 0.0) or 0.0)
        breakdown, source = _coerce_breakdown(payload.get("breakdown"), score)
        raw_frames = payload.get("problem_frames", [])
        problem_frames = sorted({
            int(value) for value in raw_frames
            if isinstance(value, int) and not isinstance(value, bool)
            and 1 <= value <= len(sample_times)
        }) if isinstance(raw_frames, list) else []
        return Critique(
            verdict="revise" if verdict == "revise" else "ship",
            score=score,
            issues=[str(i) for i in payload.get("issues", [])],
            strengths=[str(s) for s in payload.get("strengths", [])],
            breakdown=breakdown,
            breakdown_source=source,
            problem_times_s=[sample_times[index - 1] for index in problem_frames],
            model_used=model_used,
        )
    except Exception as exc:  # noqa: BLE001 — critique must never break renders
        log.info("Visual critique unavailable (%s); shipping render as-is.", exc)
        return Critique(verdict="skipped")


async def critique_video_with_retry(
    video_path: str | Path,
    brief: str,
    settings: "AppSettings",
    frame_count: int = 6,
    expected_physics: list[str] | None = None,
    event_times_s: list[float] | None = None,
) -> Critique:
    """Retry one configured transient skip with a smaller image payload."""
    critique = await critique_video(
        video_path, brief, settings, frame_count=frame_count,
        expected_physics=expected_physics, event_times_s=event_times_s,
    )
    if (
        critique.verdict != "skipped"
        or not settings.openai_api_key
        or not settings.vision_model
    ):
        return critique
    retry_frames = max(1, min(int(frame_count or 1), 3))
    critique = await critique_video(
        video_path,
        brief,
        settings,
        frame_count=retry_frames,
        expected_physics=expected_physics,
        event_times_s=event_times_s,
    )
    critique.retried = True
    return critique


# (endpoint, vision model) pairs rejected as unknown in this process, so later
# critiques go straight to the configured LLM instead of re-failing first.
# Keyed by endpoint so switching provider in Settings starts clean.
_UNAVAILABLE_VISION_MODELS: set[tuple[str, str]] = set()


def _is_unknown_model_error(exc: Exception) -> bool:
    """Recognize only endpoint model-name failures for the in-memory fallback."""
    detail = str(exc).casefold()
    return "unknown model" in detail or "2013" in detail


# ── Learned keyless quality proxy (Quality Flywheel "Prove It", F182) ────────
# The static proxy below scores a scene by SUMMING its five axis estimates — an
# equal-weight guess at how a critic would score it. When a model trained on real
# tournament data (draft axis breakdown -> shipped HQ score, mined from the render
# ledger by tools/train_quality_proxy.py) is present, we instead apply its learned
# per-axis weights so the keyless ranking better predicts real critic quality.
#
# The model file is NEVER auto-written into the app: the trainer produces it and it
# is committed only after human review (supply-chain safety, like curated exemplars).
# Absent a model, behaviour is byte-identical to the equal-weight sum — so the
# keyless --gate floor is provably unchanged until a reviewed model ships.
_QUALITY_PROXY_CACHE: dict | None = None


def _quality_proxy_path() -> Path:
    override = os.getenv("AETHERLAB_QUALITY_PROXY")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "tools" / "quality_proxy_model.json"


def _load_quality_proxy(path: Path | None = None) -> dict | None:
    """Load learned proxy weights, or None when absent/invalid (fail-soft).

    An explicit ``path`` bypasses the process cache (tests use it); the default
    path is cached so per-candidate scoring never re-reads the file.
    """
    global _QUALITY_PROXY_CACHE
    explicit = path is not None
    if not explicit and _QUALITY_PROXY_CACHE is not None:
        return _QUALITY_PROXY_CACHE or None
    model: dict = {}
    try:
        p = path or _quality_proxy_path()
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            weights = data.get("weights") if isinstance(data, dict) else None
            if isinstance(weights, dict) and all(
                a in weights
                and isinstance(weights[a], (int, float))
                and not isinstance(weights[a], bool)
                for a in CRITIC_AXES
            ):
                model = {
                    "weights": {a: float(weights[a]) for a in CRITIC_AXES},
                    "intercept": float(data.get("intercept", 0.0) or 0.0),
                }
    except Exception as exc:  # noqa: BLE001 — a proxy must never break a render
        log.info("Quality proxy model unavailable (%s); using equal-weight sum.", exc)
        model = {}
    if not explicit:
        _QUALITY_PROXY_CACHE = model
    return model or None


def _proxy_score(breakdown: dict[str, float], model: dict) -> float:
    """Apply learned per-axis weights to a breakdown, clamped to 0-10."""
    weights = model["weights"]
    total = float(model.get("intercept", 0.0) or 0.0)
    for axis in CRITIC_AXES:
        total += float(weights[axis]) * float(breakdown.get(axis, 0.0) or 0.0)
    return round(max(0.0, min(10.0, total)), 3)


def static_quality_estimate(
    code: str, metrics: dict | None = None
) -> Critique:
    """Heuristic per-axis proxy when no vision model can watch the render.

    Keyless/offline is the common case; without this the flywheel has no signal
    to rank candidates and the tournament silently drops them all. This maps the
    existing *static* gates (``services/scene_validation``) — and optional render
    metrics from ``tools/visual_regression.audit_video`` — onto the same five
    axes so ranking is deterministic and discriminating (a worse scene scores
    lower), never random.

    ``verdict`` stays ``"skipped"`` so this is never mistaken for a real vision
    judgement; ``breakdown_source`` is ``"static"``.
    """
    # Import here so this module keeps importing with no heavy deps.
    from aetherlab.services.scene_validation import (
        check_latex_strings,
        estimate_duration,
        scene_hygiene_warnings,
        validate_scene,
    )

    axes = {a: _AXIS_MAX for a in CRITIC_AXES}
    try:
        ok, lint_issues = validate_scene(code or "")
        if not ok:
            # A scene that fails the lint battery is structurally broken.
            axes["legibility"] -= min(1.5, 0.5 * len(lint_issues))
            axes["structure"] -= min(1.0, 0.5 * len(lint_issues))
        hygiene = scene_hygiene_warnings(code or "")
        # Out-of-frame / overlap / leftover-mobject warnings hurt what a viewer
        # can actually read and how balanced the frame is.
        axes["legibility"] -= min(1.5, 0.5 * len(hygiene))
        axes["composition"] -= min(1.5, 0.5 * len(hygiene))
        if check_latex_strings(code or ""):
            axes["substance"] -= 0.5
        est = estimate_duration(code or "")
        # Pacing/structure: a 2-second scene has no beginning-middle-end; a scene
        # that never calls play() has no motion (no substance).
        if est.total_seconds < 4.0:
            axes["structure"] -= 1.0
            axes["substance"] -= 0.5
        elif est.total_seconds < 8.0:
            axes["structure"] -= 0.5
        if est.play_calls == 0:
            axes["substance"] -= 1.5
        if metrics:
            blank = float(metrics.get("blank_ratio", 0.0) or 0.0)
            static = float(metrics.get("static_ratio", 0.0) or 0.0)
            axes["substance"] -= min(1.5, blank * 6.0 + static * 3.0)
    except Exception as exc:  # noqa: BLE001 — a proxy must never break a render
        log.info("Static quality estimate failed (%s); returning neutral proxy.", exc)

    breakdown = {a: round(max(0.0, min(_AXIS_MAX, v)), 3) for a, v in axes.items()}
    # Prefer a reviewed, ledger-trained weighting when one is present; otherwise the
    # historical equal-weight sum (so the keyless score is unchanged until a model
    # ships). Either way the per-axis breakdown and "static" source are the same.
    model = _load_quality_proxy()
    score = _proxy_score(breakdown, model) if model else round(sum(breakdown.values()), 3)
    return Critique(
        verdict="skipped",
        score=score,
        issues=[],
        strengths=[],
        breakdown=breakdown,
        breakdown_source="static",
    )
