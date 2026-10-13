"""Stitch rendered chapter clips into one produced lesson video (ffmpeg).

Quality-first and fail-soft: uses imageio-ffmpeg's bundled binary (no system
ffmpeg, works in the frozen bundle) via the cross-platform subprocess helper.

Two levels:
- ``assemble_lesson`` with card metadata builds a PRODUCED lesson — a title
  card, a per-chapter card ("Chapter 2 — The idea"), an end card, and short
  crossfades between every segment, so it feels authored rather than concaten-
  ated.
- Without metadata (or if the produced path fails) it falls back to a plain
  normalized concat, and finally to the individual chapter clips.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import subprocess
import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger(__name__)

# Uniform canvas every segment is normalized to before crossfading.
_W, _H, _FPS = 1280, 720, 30
_CARD_INTRO_SEC = 3.0
_CARD_CHAPTER_SEC = 2.2
_CARD_END_SEC = 3.0
_XFADE_SEC = 0.5


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
    lesson_title: str = "",
    lesson_subtitle: str = "",
    chapter_titles: list[str] | None = None,
    palette: dict[str, str] | None = None,
    timeout: int = 300,
    return_offsets: bool = False,
    cancel_check: Callable[[], bool] | None = None,
):
    """Assemble ordered chapter clips into one lesson MP4.

    When ``lesson_title`` or ``chapter_titles`` are supplied, a PRODUCED lesson
    is built — intro/chapter/end title cards and crossfades. Otherwise (or if
    that path fails) it falls back to a plain normalized concat. Every clip is
    normalized to a common resolution/fps with an audio track (silent chapters
    get generated silence) so the filters always have matching streams.

    Returns the lesson ``Path`` (or ``None`` on failure). With
    ``return_offsets=True`` returns ``(path, chapter_starts)`` where
    ``chapter_starts[i]`` is chapter ``i``'s readable start time (seconds) in the final
    video — the cards+crossfades push every chapter later than a plain concat,
    so callers that seek/subtitle the produced video MUST use these offsets.
    """
    def _result(path, offsets):
        return (path, list(offsets)) if return_offsets else path

    clips = [Path(v) for v in chapter_videos if v and Path(v).exists()]
    if not clips:
        return _result(None, [])

    ffmpeg = _ffmpeg_exe()
    if not ffmpeg:
        log.info("No bundled ffmpeg; lesson stays as separate chapter clips.")
        return _result(None, [])

    # Produced lesson (cards + crossfades) when we have card metadata.
    if lesson_title or chapter_titles:
        produced = None
        # One retry before downgrading: a failure at the very end of an
        # otherwise complete encode (seen on a Windows CI runner) is usually
        # transient, and the fallback silently drops every card and crossfade.
        for _attempt in range(2):
            produced = await _assemble_produced(
                ffmpeg, clips, Path(out_path),
                lesson_title=lesson_title, lesson_subtitle=lesson_subtitle,
                chapter_titles=chapter_titles or [], palette=palette, timeout=timeout,
                cancel_check=cancel_check,
            )
            if produced:
                break
        if produced:
            path, chapter_starts = produced
            return _result(path, chapter_starts)
        log.info("Produced-lesson assembly failed; falling back to plain concat.")

    # Plain concat / single-clip fallbacks have no cards or crossfades, so a
    # chapter starts at the running sum of the preceding clip durations.
    plain_offsets = _plain_offsets(clips)

    if len(clips) == 1:
        return _result(clips[0], plain_offsets)  # nothing to stitch

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Silent lessons (the common keyless case) have no audio streams, so the
    # audio filtergraph below would fail on every clip — go straight to the
    # video-only path and skip a doomed ffmpeg attempt.
    if not all(_has_audio(c) for c in clips):
        return _result(
            await _assemble_silent(
                ffmpeg, clips, len(clips), out_path, timeout, cancel_check=cancel_check,
            ),
            plain_offsets,
        )

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

    if await _run(cmd, timeout, cancel_check=cancel_check):
        log.info("Assembled lesson: %s (%.1f MB, %d chapters)",
                 out_path, out_path.stat().st_size / 1e6, len(clips))
        return _result(out_path, plain_offsets)
    # Retry once treating every clip as silent (some clips may lack an audio
    # stream, which breaks the [i:a] mapping above).
    return _result(
        await _assemble_silent(
            ffmpeg, clips, silence_idx, out_path, timeout, cancel_check=cancel_check,
        ),
        plain_offsets,
    )


async def _assemble_silent(
    ffmpeg: str, clips: list[Path], silence_idx: int, out_path: Path, timeout: int,
    *, cancel_check: Callable[[], bool] | None = None,
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
    if await _run(cmd, timeout, cancel_check=cancel_check):
        log.info("Assembled lesson (video-only): %s", out_path)
        return out_path
    return None


# ── produced lesson (title cards + crossfades) ──────────────────────────────


def _plain_offsets(clips: list[Path]) -> list[float]:
    """Chapter start times for a plain (card-less, crossfade-less) concat: the
    running sum of preceding clip durations."""
    starts: list[float] = []
    t = 0.0
    for clip in clips:
        starts.append(t)
        t += _probe(clip)[0] or 6.0
    return starts


def _probe(clip: Path) -> tuple[float, bool]:
    """Return (duration_seconds, has_audio) via PyAV; (0, False) if unprobeable."""
    try:
        import av

        with av.open(str(clip)) as container:
            dur = float(container.duration) / 1e6 if container.duration else 0.0
            if not math.isfinite(dur) or dur < 0:
                dur = 0.0
            return dur, bool(container.streams.audio)
    except Exception:  # noqa: BLE001
        return 0.0, False


_VNORM = (
    f"scale={_W}:{_H}:force_original_aspect_ratio=decrease,"
    f"pad={_W}:{_H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={_FPS},"
    "format=yuv420p"
)


async def _normalize_card(
    ffmpeg: str, png: Path, dur: float, out: Path, timeout: int,
    *, cancel_check: Callable[[], bool] | None = None,
) -> bool:
    """PNG → a `dur`-second clip with a silent stereo audio track."""
    cmd = [
        ffmpeg, "-y", "-loop", "1", "-t", f"{dur:.2f}", "-i", str(png),
        "-f", "lavfi", "-t", f"{dur:.2f}", "-i", "anullsrc=r=44100:cl=stereo",
        "-vf", _VNORM, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-ar", "44100", "-ac", "2", "-shortest",
        "-movflags", "+faststart", str(out),
    ]
    return await _run(cmd, timeout, cancel_check=cancel_check)


async def _normalize_clip(
    ffmpeg: str, clip: Path, has_audio: bool, out: Path, timeout: int,
    *, cancel_check: Callable[[], bool] | None = None,
) -> bool:
    """Chapter clip → uniform canvas/fps with a guaranteed stereo audio track."""
    if has_audio:
        cmd = [
            ffmpeg, "-y", "-i", str(clip), "-vf", _VNORM,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart", str(out),
        ]
    else:
        cmd = [
            ffmpeg, "-y", "-i", str(clip),
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-vf", _VNORM, "-map", "0:v", "-map", "1:a", "-shortest",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart", str(out),
        ]
    return await _run(cmd, timeout, cancel_check=cancel_check)


async def _assemble_produced(
    ffmpeg: str,
    clips: list[Path],
    out_path: Path,
    *,
    lesson_title: str,
    lesson_subtitle: str,
    chapter_titles: list[str],
    palette: dict[str, str] | None,
    timeout: int,
    cancel_check: Callable[[], bool] | None = None,
) -> tuple[Path, list[float]] | None:
    """Build a title-carded, crossfaded lesson.

    Returns ``(out_path, chapter_starts)`` where ``chapter_starts[i]`` is the
    start time (seconds) of chapter ``i``'s clip within the produced video —
    the caller needs this to seek/time subtitles past the intro/chapter cards
    and crossfades. Returns None on any failure so the caller can fall back to
    a plain concat.
    """
    from aetherlab.services.cards import chapter_kicker, render_card_png

    work = Path(tempfile.gettempdir()) / "aetherlab" / "assembly" / uuid.uuid4().hex[:8]
    work.mkdir(parents=True, exist_ok=True)

    # 1) Draw the cards as PNGs.
    n = len(clips)
    intro_png = render_card_png(
        work / "intro.png", kicker="PhysLab lesson",
        title=lesson_title or "A visual explainer", subtitle=lesson_subtitle,
        palette=palette,
    )
    end_png = render_card_png(
        work / "end.png", kicker="That's the idea",
        title=lesson_title or "", subtitle="Review the questions to check yourself.",
        palette=palette,
    )
    chapter_pngs: list[Path | None] = []
    for i in range(n):
        raw = chapter_titles[i] if i < len(chapter_titles) else ""
        png = render_card_png(
            work / f"ch{i}.png", kicker=chapter_kicker(i + 1, n),
            title=raw, palette=palette,
        )
        chapter_pngs.append(png)

    if not intro_png:  # PIL unavailable → no produced lesson
        return None

    # 2) Build the ordered segment plan: intro, then (chapter card, clip)*, end.
    #    Each entry is (kind, source, duration). clip_seg_idx[i] records the
    #    segment index of chapter i's clip so we can report its start time.
    segments: list[tuple[str, Path, float]] = [("card", intro_png, _CARD_INTRO_SEC)]
    clip_seg_idx: list[int] = []
    for i, clip in enumerate(clips):
        dur, has_audio = _probe(clip)
        if dur <= 0:
            dur = 6.0  # unprobeable but exists — assume a typical chapter length
        if chapter_pngs[i]:
            segments.append(("card", chapter_pngs[i], _CARD_CHAPTER_SEC))  # type: ignore[arg-type]
        clip_seg_idx.append(len(segments))
        segments.append(("clip", clip, dur, has_audio))  # type: ignore[arg-type]
    segments.append(("card", end_png or intro_png, _CARD_END_SEC))

    # 3) Normalize every segment to a uniform mp4 (cards get silent audio).
    norm: list[Path] = []
    durations: list[float] = []
    for idx, seg in enumerate(segments):
        dst = work / f"seg{idx:02d}.mp4"
        if seg[0] == "card":
            ok = await _normalize_card(
                ffmpeg, seg[1], seg[2], dst, timeout, cancel_check=cancel_check,
            )
        else:
            ok = await _normalize_clip(
                ffmpeg, seg[1], seg[3], dst, timeout, cancel_check=cancel_check,
            )
        if not ok or not dst.exists():
            return None
        # Trust the requested card duration; probe clips for the exact length.
        real = seg[2] if seg[0] == "card" else (_probe(dst)[0] or seg[2])
        norm.append(dst)
        durations.append(real)

    if len(norm) < 2:
        return None

    # 4) Crossfade-chain the normalized segments (video + audio together).
    #    xfade needs the fade shorter than the shortest neighbour.
    # A transition must fit inside even the shortest chapter. The old 0.2 s
    # floor made a one- or two-frame clip request a fade longer than itself,
    # which FFmpeg rejected and silently downgraded to plain concatenation.
    xfade = min(_XFADE_SEC, min(durations) * 0.4)
    if not math.isfinite(xfade) or xfade <= 0:
        return None
    ok = await _xfade_chain(
        ffmpeg, norm, durations, xfade, out_path, timeout,
        cancel_check=cancel_check,
    )
    if not ok:
        return None

    # Start time of each segment in the produced timeline — identical to the
    # xfade offsets: seg 0 at 0, seg k at sum(durs[0..k-1]) - k*xfade. Map the
    # recorded clip segment indices to their start times for the caller. Add one
    # fade duration for human-facing seek/subtitle offsets so they land on the
    # chapter content, not the previous card at the start of the crossfade.
    seg_starts = _segment_starts(durations, xfade)
    chapter_starts = [
        min(seg_starts[m] + xfade, max(sum(durations) - xfade, 0.0))
        for m in clip_seg_idx if m < len(seg_starts)
    ]

    log.info("Assembled produced lesson: %s (%.1f MB, %d segments)",
             out_path, out_path.stat().st_size / 1e6, len(norm))
    return out_path, chapter_starts


def _segment_starts(durs: list[float], d: float) -> list[float]:
    """Start time of each segment in an xfade chain: seg 0 at 0, seg k at
    ``sum(durs[0..k-1]) - k*d``. Single source of truth shared by the filter
    graph (so a segment's rendered position and its reported start never drift).
    """
    starts = [0.0]
    cum = durs[0] if durs else 0.0
    for k in range(1, len(durs)):
        starts.append(max(cum - k * d, 0.0))
        cum += durs[k]
    return starts


async def _xfade_chain(
    ffmpeg: str, segs: list[Path], durs: list[float], d: float,
    out_path: Path, timeout: int,
    *, cancel_check: Callable[[], bool] | None = None,
) -> bool:
    """Chain uniform segments with xfade (video) + acrossfade (audio).

    Offset for adding segment k (k>=1) is sum(durs[0..k-1]) - k*d, the standard
    xfade cumulative offset so successive crossfades line up seamlessly (see
    ``_segment_starts``, which computes these same offsets for the caller).
    """
    cmd: list[str] = [ffmpeg, "-y"]
    for seg in segs:
        cmd += ["-i", str(seg)]

    starts = _segment_starts(durs, d)
    vfilters: list[str] = []
    afilters: list[str] = []
    v_prev, a_prev = "[0:v]", "[0:a]"
    for k in range(1, len(segs)):
        offset = starts[k]
        vlabel = f"[vx{k}]"
        alabel = f"[ax{k}]"
        vfilters.append(
            f"{v_prev}[{k}:v]xfade=transition=fade:duration={d:.6f}:"
            f"offset={offset:.6f}{vlabel}"
        )
        afilters.append(f"{a_prev}[{k}:a]acrossfade=d={d:.6f}{alabel}")
        v_prev, a_prev = vlabel, alabel

    filtergraph = ";".join(vfilters + afilters)
    cmd += [
        "-filter_complex", filtergraph,
        "-map", v_prev, "-map", a_prev,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(out_path),
    ]
    return await _run(cmd, timeout, cancel_check=cancel_check)


def _ffmpeg_error_summary(stderr: bytes, tail: int = 400) -> str:
    """ffmpeg's error lines plus the end of its log.

    The tail alone is mostly encoder statistics, which hid the actual error
    behind "Conversion failed!" (Windows CI, 2026-10-01).
    """
    text = stderr.decode(errors="replace")
    markers = ("error", "invalid", "failed", "denied", "no such", "cannot", "unable")
    errors = [
        line.strip() for line in text.splitlines()
        if any(marker in line.lower() for marker in markers)
        and "conversion failed" not in line.lower()
    ]
    summary = " | ".join(dict.fromkeys(errors[:8]))
    return (summary + " || tail: " if summary else "") + text[-tail:]


async def _run(
    cmd: list[str], timeout: int, *, cancel_check: Callable[[], bool] | None = None,
) -> bool:
    from aetherlab.core.atomic_file import unique_staging_path
    from aetherlab.core.proc import ProcessCancelledError, run_process_tree, subprocess_kwargs

    target = Path(cmd[-1])
    staging = unique_staging_path(target)
    staged_cmd = [*cmd[:-1], str(staging)]
    try:
        if cancel_check is not None and cancel_check():
            raise ProcessCancelledError("Lesson assembly cancelled")
        result = await asyncio.to_thread(
            run_process_tree,
            staged_cmd,
            timeout=timeout,
            cancel_check=cancel_check,
            capture_output=True,
            **subprocess_kwargs(),
        )
    except ProcessCancelledError:
        staging.unlink(missing_ok=True)
        raise
    except subprocess.TimeoutExpired as exc:
        staging.unlink(missing_ok=True)
        stderr = exc.stderr if isinstance(exc.stderr, bytes) else b""
        log.warning("ffmpeg assembly timed out: %s", _ffmpeg_error_summary(stderr))
        return False
    except (FileNotFoundError, OSError) as exc:
        staging.unlink(missing_ok=True)
        log.warning("ffmpeg assembly could not complete: %s", exc)
        return False
    except BaseException:
        staging.unlink(missing_ok=True)
        raise
    if result.returncode != 0:
        staging.unlink(missing_ok=True)
        log.warning("ffmpeg assembly failed: %s", _ffmpeg_error_summary(result.stderr or b""))
        return False
    try:
        complete_output = staging.is_file() and staging.stat().st_size > 0
    except OSError:
        complete_output = False
    if not complete_output:
        staging.unlink(missing_ok=True)
        log.warning("ffmpeg assembly reported success without a complete output file.")
        return False
    try:
        os.replace(staging, target)
    except OSError as exc:
        staging.unlink(missing_ok=True)
        log.warning("ffmpeg assembly output could not be installed: %s", exc)
        return False
    return True
