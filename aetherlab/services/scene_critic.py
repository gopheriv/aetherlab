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
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aetherlab.core.settings import AppSettings

log = logging.getLogger(__name__)

_FRAME_DIR = Path(tempfile.gettempdir()) / "aetherlab" / "critic_frames"

CRITIC_SYSTEM_PROMPT = """You are the AetherLab visual critic — a demanding animation director reviewing
frames sampled uniformly from a rendered Manim physics scene. Judge the RENDER,
not the idea. Score against this rubric:

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

Return STRICT JSON only:
{"verdict": "ship" | "revise",
 "score": <0-10>,
 "issues": ["specific, actionable problems, worst first"],
 "strengths": ["what works"]}

Verdict "ship" requires score >= 7 and no legibility failures. Be strict:
a bare axes-plus-curve screenshot deserves a 4 at most."""


@dataclass
class Critique:
    verdict: str  # "ship" | "revise" | "skipped"
    score: float = 0.0
    issues: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)

    @property
    def should_revise(self) -> bool:
        return self.verdict == "revise"


def extract_frames(video_path: str | Path, count: int = 6) -> list[Path]:
    """Sample ``count`` frames uniformly across the video.

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

    frames = _extract_with_pyav(video, out_dir, count)
    if frames:
        return frames
    return _extract_with_ffmpeg(video, out_dir, count)


def _extract_with_pyav(video: Path, out_dir: Path, count: int) -> list[Path]:
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
            wanted = sorted({min(int(i * total / count), total - 1) for i in range(count)})
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


def _extract_with_ffmpeg(video: Path, out_dir: Path, count: int) -> list[Path]:
    """CLI fallback: one frame per interval, downscaled to 640px wide."""
    try:
        duration = _probe_duration(video)
        interval = max(duration / count, 0.1)
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(video),
                "-vf", f"fps=1/{interval:.3f},scale=640:-1",
                "-frames:v", str(count),
                str(out_dir / "frame_%02d.png"),
            ],
            capture_output=True, text=True, timeout=60,
            creationflags=0x08000000,
        )
        return sorted(out_dir.glob("frame_*.png"))[:count]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        log.info("Frame extraction unavailable (%s); skipping critique.", exc)
        return []


def _probe_duration(video: Path) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(video)],
            capture_output=True, text=True, timeout=20,
            creationflags=0x08000000,
        )
        return max(float(result.stdout.strip()), 0.5)
    except Exception:  # noqa: BLE001
        return 15.0


async def critique_video(
    video_path: str | Path,
    brief: str,
    settings: "AppSettings",
    frame_count: int = 6,
) -> Critique:
    """Sample frames and ask the vision model for a verdict.

    ``brief`` is the creative intent (storyboard JSON or the problem prompt).
    Degrades to verdict "skipped" without a vision model, frames, or on any
    API failure — the pipeline then ships the render as before.
    """
    if not settings.vision_model or not settings.openai_api_key:
        return Critique(verdict="skipped")
    frames = extract_frames(video_path, frame_count)
    if not frames:
        return Critique(verdict="skipped")

    content: list[dict] = [
        {
            "type": "text",
            "text": (
                "## Creative intent this render must fulfil\n"
                f"{brief[:4000]}\n\n"
                f"## {len(frames)} frames sampled uniformly, in order:"
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
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=max(settings.llm_timeout_seconds, 300),
        )
        response = await client.chat.completions.create(
            model=settings.vision_model,
            messages=[
                {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            temperature=0.2,
            max_tokens=2048,
        )
        raw = response.choices[0].message.content or ""
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        payload = json.loads(match.group(0) if match else raw)
        verdict = str(payload.get("verdict", "ship")).lower()
        return Critique(
            verdict="revise" if verdict == "revise" else "ship",
            score=float(payload.get("score", 0.0) or 0.0),
            issues=[str(i) for i in payload.get("issues", [])],
            strengths=[str(s) for s in payload.get("strengths", [])],
        )
    except Exception as exc:  # noqa: BLE001 — critique must never break renders
        log.info("Visual critique unavailable (%s); shipping render as-is.", exc)
        return Critique(verdict="skipped")
