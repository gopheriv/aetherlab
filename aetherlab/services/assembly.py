"""Stitch rendered chapter clips into one lesson video (ffmpeg concat).

Quality-first and fail-soft: uses imageio-ffmpeg's bundled binary (no system
ffmpeg, works in the frozen bundle) via the cross-platform subprocess helper.
Any failure returns None and the caller can fall back to the individual
chapter clips. Re-encodes on concat so clips with slightly different
codecs/audio (silent vs narrated) join cleanly.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def _ffmpeg_exe() -> str | None:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return None


def _has_audio(clip: Path) -> bool:
    """True if the clip carries an audio stream (PyAV probe, no ffprobe)."""
    try:
        import av

        with av.open(str(clip)) as container:
            return bool(container.streams.audio)
    except Exception:  # noqa: BLE001 — treat unprobeable as silent (safe path)
        return False


async def assemble_lesson(
    chapter_videos: list[Path | str],
    out_path: Path | str,
    *,
    timeout: int = 300,
) -> Path | None:
    """Concatenate ordered chapter clips into one lesson MP4.

    Every clip is normalized to a common resolution/fps and given an audio
    track (silent chapters get generated silence) so the concat filter always
    has matching streams. Returns the lesson path, or None on any failure.
    """
    clips = [Path(v) for v in chapter_videos if v and Path(v).exists()]
    if not clips:
        return None
    if len(clips) == 1:
        return clips[0]  # nothing to stitch

    ffmpeg = _ffmpeg_exe()
    if not ffmpeg:
        log.info("No bundled ffmpeg; lesson stays as separate chapter clips.")
        return None

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Silent lessons (the common keyless case) have no audio streams, so the
    # audio filtergraph below would fail on every clip — go straight to the
    # video-only path and skip a doomed ffmpeg attempt.
    if not all(_has_audio(c) for c in clips):
        return await _assemble_silent(ffmpeg, clips, len(clips), out_path, timeout)

    # Normalize each clip: fixed 1280x720 canvas (pad, don't stretch), 30 fps,
    # and a guaranteed stereo audio track (real audio, or generated silence),
    # so the concat filter's inputs are uniform.
    cmd: list[str] = [ffmpeg, "-y"]
    for clip in clips:
        cmd += ["-i", str(clip)]
    # anullsrc supplies silence for clips that have no audio stream.
    cmd += ["-f", "lavfi", "-t", "0.1", "-i", "anullsrc=r=44100:cl=stereo"]
    silence_idx = len(clips)

    filters: list[str] = []
    concat_inputs = ""
    for i, _clip in enumerate(clips):
        filters.append(
            f"[{i}:v]scale=1280:720:force_original_aspect_ratio=decrease,"
            f"pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"setsar=1,fps=30,format=yuv420p[v{i}]"
        )
        # Use the clip's own audio if present, else the silence source.
        filters.append(
            f"[{i}:a]aresample=44100,asetpts=N/SR/TB[a{i}]"
        )
        concat_inputs += f"[v{i}][a{i}]"
    filters.append(f"{concat_inputs}concat=n={len(clips)}:v=1:a=1[v][a]")

    cmd += [
        "-filter_complex", ";".join(filters),
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart", str(out_path),
    ]

    if await _run(cmd, timeout):
        log.info("Assembled lesson: %s (%.1f MB, %d chapters)",
                 out_path, out_path.stat().st_size / 1e6, len(clips))
        return out_path
    # Retry once treating every clip as silent (some clips may lack an audio
    # stream, which breaks the [i:a] mapping above).
    return await _assemble_silent(ffmpeg, clips, silence_idx, out_path, timeout)


async def _assemble_silent(
    ffmpeg: str, clips: list[Path], silence_idx: int, out_path: Path, timeout: int
) -> Path | None:
    """Fallback: video-only concat (drop audio) — never fail to produce a lesson
    just because one chapter had no audio stream."""
    cmd: list[str] = [ffmpeg, "-y"]
    for clip in clips:
        cmd += ["-i", str(clip)]
    filters = []
    vins = ""
    for i in range(len(clips)):
        filters.append(
            f"[{i}:v]scale=1280:720:force_original_aspect_ratio=decrease,"
            f"pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=30,"
            f"format=yuv420p[v{i}]"
        )
        vins += f"[v{i}]"
    filters.append(f"{vins}concat=n={len(clips)}:v=1:a=0[v]")
    cmd += [
        "-filter_complex", ";".join(filters), "-map", "[v]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-movflags", "+faststart", str(out_path),
    ]
    if await _run(cmd, timeout):
        log.info("Assembled lesson (video-only): %s", out_path)
        return out_path
    return None


async def _run(cmd: list[str], timeout: int) -> bool:
    from aetherlab.core.proc import subprocess_kwargs

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            **subprocess_kwargs(),
        )
    except (FileNotFoundError, OSError) as exc:
        log.warning("ffmpeg assembly could not start: %s", exc)
        return False
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
            await proc.wait()
        except Exception:  # noqa: BLE001
            pass
        log.warning("ffmpeg assembly timed out.")
        return False
    if proc.returncode != 0:
        log.warning("ffmpeg assembly failed: %s", stderr.decode(errors="replace")[-600:])
        return False
    return True
