"""Narration → speech → narrated video (the narration↔visual sync engine).

Ported from the manim-bot project's proven decision for the "sync bug":
per-beat narration↔animation sync is architecturally fragile, so instead we
sync the WHOLE clip. Render the silent video first, derive narration from the
final animation, synthesize speech (edge-tts), then FIT the audio to the video —
re-synthesize once at an adjusted speaking rate when the durations diverge, and
pad/silence-fill the remainder — so the voiceover tracks the animation without
chopping its closing beats.

Everything here is fail-soft: no edge-tts, no ffmpeg, or any error returns None
and the caller keeps the silent render. Uses imageio-ffmpeg's bundled binary
(no system ffmpeg required, works in the frozen bundle) and PyAV for duration
(no external ffprobe). Cross-platform via core.proc.subprocess_kwargs.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path

from aetherlab.core.proc import subprocess_kwargs

log = logging.getLogger(__name__)

# edge-tts defaults (same voice/rate family manim-bot settled on).
DEFAULT_VOICE = "en-US-AndrewMultilingualNeural"
DEFAULT_RATE = "+8%"


def _ffmpeg_exe() -> str | None:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001 — no bundled ffmpeg → narration disabled
        return None


def _duration_sync(path: Path) -> float:
    """Media duration in seconds via PyAV (video or audio); 0.0 on failure."""
    try:
        import av

        with av.open(str(path)) as container:
            streams = container.streams.video or container.streams.audio
            if streams:
                st = streams[0]
                if st.duration and st.time_base:
                    return float(st.duration * st.time_base)
            if container.duration:
                return container.duration / 1_000_000.0
    except Exception:  # noqa: BLE001
        pass
    return 0.0


async def get_duration(path: Path) -> float:
    return await asyncio.to_thread(_duration_sync, path)


def _parse_rate(rate: str | None) -> int:
    try:
        return int(str(rate).replace("%", "").replace("+", "").strip())
    except (ValueError, TypeError):
        return 0


def _format_rate(pct: int) -> str:
    return f"+{pct}%" if pct >= 0 else f"{pct}%"


async def synthesize(text: str, out_path: Path, voice: str, rate: str) -> Path | None:
    """Text → speech (edge-tts) → mp3. None if edge-tts is unavailable/fails."""
    try:
        import edge_tts
    except Exception:  # noqa: BLE001
        log.info("edge-tts not installed; narration disabled.")
        return None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        await edge_tts.Communicate(text, voice, rate=rate).save(str(out_path))
        return out_path if out_path.exists() and out_path.stat().st_size > 0 else None
    except Exception:  # noqa: BLE001 — network/voice errors must not break render
        log.warning("TTS synthesis failed; keeping silent video.", exc_info=True)
        return None


async def _run_ffmpeg(cmd: list[str], timeout: int = 120) -> bool:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        **subprocess_kwargs(),
    )
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
            await proc.wait()
        except Exception:  # noqa: BLE001
            pass
        log.warning("ffmpeg mux timed out; keeping silent video.")
        return False
    if proc.returncode != 0:
        log.warning("ffmpeg mux failed: %s", stderr.decode(errors="replace")[-500:])
        return False
    return True


async def merge(video: Path, audio: Path, out_path: Path) -> Path | None:
    """Mux audio over video into a narrated mp4.

    Audio longer than video → pad the video's last frame (tpad) so the tail
    isn't cut. Audio shorter → keep the FULL video (no -shortest) with trailing
    silence, so the animation's closing beats survive.
    """
    ffmpeg = _ffmpeg_exe()
    if not ffmpeg:
        return None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    video_dur = await get_duration(video)
    audio_dur = await get_duration(audio)
    log.info("Narration merge: video %.1fs, audio %.1fs", video_dur, audio_dur)

    if audio_dur > video_dur and video_dur > 0:
        cmd = [
            ffmpeg, "-y", "-i", str(video), "-i", str(audio),
            "-filter_complex",
            f"[0:v]tpad=stop_mode=clone:stop_duration={audio_dur - video_dur:.2f}[v]",
            "-map", "[v]", "-map", "1:a",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-b:a", "160k",
            "-shortest", "-movflags", "+faststart", str(out_path),
        ]
    else:
        # Audio <= video: bitstream-copy the full video (no re-encode, no
        # -shortest) so no closing beats are dropped.
        cmd = [
            ffmpeg, "-y", "-i", str(video), "-i", str(audio),
            "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
            "-map", "0:v:0", "-map", "1:a:0",
            "-movflags", "+faststart", str(out_path),
        ]
    if await _run_ffmpeg(cmd):
        log.info("Narrated video: %s (%.1f MB)", out_path, out_path.stat().st_size / 1e6)
        return out_path
    return None


async def add_voiceover(
    video: Path,
    narration: str,
    out_dir: Path,
    *,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    fit_to_video: bool = True,
) -> Path | None:
    """Full pipeline: narration text → TTS → fit-to-video → merge → narrated mp4.

    Returns the narrated video path, or None (caller keeps the silent render).
    """
    video = Path(video)
    if not narration or not narration.strip() or not video.exists():
        return None
    out_dir = Path(out_dir)
    audio_path = out_dir / f"{video.stem}_narration.mp3"
    narrated_path = out_dir / f"{video.stem}_narrated.mp4"

    audio = await synthesize(narration, audio_path, voice, rate)
    if audio is None:
        return None

    # Fit the narration to the video by adjusting the speaking rate ONCE.
    if fit_to_video:
        try:
            video_dur = await get_duration(video)
            audio_dur = await get_duration(audio)
            if video_dur > 0.5 and audio_dur > 0.5:
                ratio = audio_dur / video_dur
                if ratio > 1.10 or ratio < 0.85:  # too long / too short
                    base = _parse_rate(rate)
                    new_rate = _format_rate(max(-40, min(80, base + round((ratio - 1.0) * 100))))
                    if new_rate != rate:
                        log.info(
                            "Fitting narration: audio %.1fs vs video %.1fs (ratio %.2f) → rate %s",
                            audio_dur, video_dur, ratio, new_rate,
                        )
                        refit = await synthesize(narration, audio_path, voice, new_rate)
                        if refit is not None:
                            audio = refit
        except Exception:  # noqa: BLE001
            log.warning("Narration fit-to-video failed; using base rate.", exc_info=True)

    result = await merge(video, audio, narrated_path)
    try:
        audio_path.unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        pass
    return result


def narration_available() -> bool:
    """True when both TTS and an ffmpeg binary are present (narration can run)."""
    try:
        import edge_tts  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return _ffmpeg_exe() is not None


def storyboard_narration_script(storyboard: dict | None) -> str:
    """Join a storyboard's per-beat narration lines into one seed script."""
    if not isinstance(storyboard, dict):
        return ""
    lines = storyboard.get("narration")
    if isinstance(lines, list):
        return " ".join(str(x).strip() for x in lines if str(x).strip())
    if isinstance(lines, str):
        return lines.strip()
    return ""


def storyboard_target_seconds(storyboard: dict | None) -> float | None:
    """Sum a storyboard's act durations → a target length for the narration."""
    if not isinstance(storyboard, dict):
        return None
    total = 0.0
    for act in storyboard.get("acts", []) or []:
        if isinstance(act, dict):
            try:
                total += float(act.get("duration_s") or 0)
            except (TypeError, ValueError):
                pass
    return total or None
