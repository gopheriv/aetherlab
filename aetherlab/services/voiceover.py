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
import math
from pathlib import Path
from typing import Any

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


def speech_cache_path(cache_dir: Path, text: str, voice: str, rate: str) -> Path:
    """Content-addressed location of one synthesized line (text + voice + rate)."""
    import hashlib

    # "trim1": cached clips have their edge silence removed (see _trim_edges).
    key = hashlib.sha256(
        f"trim1\n{voice}\n{rate}\n{' '.join(text.split())}".encode("utf-8")
    ).hexdigest()[:24]
    return Path(cache_dir) / f"{key}.mp3"


async def _trim_edges(source: Path, target: Path) -> bool:
    """Copy ``source`` to ``target`` without its leading and trailing silence.

    edge-tts pads every clip (about 0.15 s before and 0.3 s after the words;
    22% of a short line, measured 2026-10-02). Over a 22-line plan that is
    ~10 s of silence counted as speech, so a 128-word, ~45 s script measured
    62.5 s and could not fit 60 s. The beat timing adds its own breath.
    """
    ffmpeg = _ffmpeg_exe()
    if not ffmpeg:
        return False
    edge = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.03"
    ok = await _run_ffmpeg([
        ffmpeg, "-y", "-i", str(source),
        "-af", f"{edge},areverse,{edge},areverse",
        "-c:a", "libmp3lame", "-q:a", "3", str(target),
    ])
    return ok and target.is_file() and target.stat().st_size > 0


async def synthesize_cached(
    text: str, cache_dir: Path, voice: str, rate: str
) -> Path | None:
    """Synthesize once per (text, voice, rate); later calls reuse the same clip.

    Voice-first timing measures these clips to set the beat windows, and the
    final mux places the very same files, so the measured length is exactly the
    length that plays.
    """
    path = speech_cache_path(cache_dir, text, voice, rate)
    if path.is_file() and path.stat().st_size > 0:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".part.mp3")
    audio = await synthesize(" ".join(text.split()), partial, voice, rate)
    if audio is None:
        return None
    trimmed = path.with_suffix(".trim.mp3")
    try:
        if await _trim_edges(partial, trimmed) and _duration_sync(trimmed) > 0.05:
            trimmed.replace(path)
            partial.unlink(missing_ok=True)
        else:
            trimmed.unlink(missing_ok=True)
            partial.replace(path)
    except OSError:
        return None
    return path


async def measure_speech(
    lines: list[str], cache_dir: Path, voice: str, rate: str, *, concurrency: int = 4
) -> list[float] | None:
    """Spoken seconds for each line (0.0 for blank lines); None if any line fails."""
    gate = asyncio.Semaphore(max(1, concurrency))

    async def one(text: str) -> float | None:
        if not text.strip():
            return 0.0
        async with gate:
            path = await synthesize_cached(text, cache_dir, voice, rate)
        if path is None:
            return None
        seconds = await get_duration(path)
        return seconds if seconds > 0.05 else None

    durations = await asyncio.gather(*(one(line) for line in lines))
    if any(value is None for value in durations):
        return None
    return [float(value) for value in durations]


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


def storyboard_timed_narration_segments(storyboard: dict | None) -> list[dict[str, Any]]:
    """Return validated, ordered narration/subtitle cues from the beat schedule."""
    if not isinstance(storyboard, dict):
        return []
    timeline = storyboard.get("timeline")
    if not isinstance(timeline, list):
        return []
    segments = []
    for index, beat in enumerate(timeline):
        if not isinstance(beat, dict):
            continue
        text = " ".join(str(beat.get("narration_cue") or "").split())
        subtitle = " ".join(str(beat.get("subtitle_cue") or text).split())
        if not text or not subtitle:
            continue
        try:
            start, end = float(beat.get("start_s")), float(beat.get("end_s"))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start:
            continue
        segments.append({
            "beat_id": str(beat.get("id") or f"beat-{index + 1}"),
            "start_s": start,
            "end_s": end,
            "text": text,
            "subtitle_text": subtitle,
            "target_object": str(beat.get("target_object") or ""),
            "target_equation": str(beat.get("target_equation") or ""),
            "anchor_cell": str(beat.get("anchor_cell") or ""),
        })
    segments.sort(key=lambda item: (item["start_s"], item["end_s"]))
    previous_end = 0.0
    for item in segments:
        if item["start_s"] < previous_end:
            return []
        previous_end = item["end_s"]
    return segments


async def add_timed_beat_voiceover(
    video: Path,
    storyboard: dict | None,
    out_dir: Path,
    *,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    max_rate_adjustment_pct: int = 20,
    speech_cache_dir: Path | None = None,
    measured_starts: dict[str, float] | None = None,
) -> dict[str, Any] | None:
    """Synthesize per-beat speech and place it on the storyboard's time windows.

    With ``speech_cache_dir`` (voice-first timing), each line is taken from the
    clip that was measured to build the windows, so it fits by construction.

    A segment is re-synthesized at most once and only within a bounded rate
    adjustment. If any sentence still overruns its beat, timed mode declines
    the whole track so the caller can use the existing whole-clip fitting path.
    The returned report measures each synthesized segment against its beat and
    records the actual caption/audio schedule.
    """
    video = Path(video)
    if not video.is_file():
        return None
    cues = storyboard_timed_narration_segments(storyboard)
    if not cues or not narration_available():
        return None
    ffmpeg = _ffmpeg_exe()
    if not ffmpeg:
        return None
    video_duration = await get_duration(video)
    if video_duration <= 0.5:
        return None
    if measured_starts and speech_cache_dir is not None:
        # Each line starts when its beat's first animation really starts in
        # the final code (measured by a dry run), whatever repairs and
        # revisions did to the length. Live 2026-10-02: a 13.3 s plan rendered
        # 16.0 s after a render repair and the stretched timing was declined.
        for item in cues:
            start = measured_starts.get(item["beat_id"])
            if start is not None and 0 <= start < video_duration:
                item["start_s"] = round(float(start), 3)
        cues.sort(key=lambda item: item["start_s"])
        for item, following in zip(cues, cues[1:] + [None]):
            item["end_s"] = round(following["start_s"] if following else video_duration, 3)
        if any(item["end_s"] - item["start_s"] <= 0.05 for item in cues):
            log.info("Beat narration declined: measured beat starts collide.")
            return None
    timeline_end = max(item["end_s"] for item in cues)
    scale = video_duration / timeline_end if timeline_end > 0 else 1.0
    if measured_starts and speech_cache_dir is not None:
        scale = 1.0                      # windows already come from the final code
    elif not 0.85 <= scale <= 1.15:
        log.info("Beat narration declined: storyboard/video scale %.3f is too large.", scale)
        return None
    if speech_cache_dir is not None and video_duration >= timeline_end - 0.25:
        # Voice-first scenes: the preflight verified each beat STARTS on time,
        # and extra length sits in the final hold. Stretching every cue by the
        # overall ratio would push early lines late (live 2026-10-02: 15.13 s
        # for a 13.59 s plan would have moved them up to 1.3 s), so lines stay
        # at their planned starts and the last window runs to the video's end.
        scale = 1.0
        cues[-1]["end_s"] = round(max(cues[-1]["end_s"], video_duration), 3)
    for item in cues:
        item["start_s"] = round(item["start_s"] * scale, 3)
        item["end_s"] = round(item["end_s"] * scale, 3)

    work_dir = Path(out_dir) / f"{video.stem}_beat_audio"
    work_dir.mkdir(parents=True, exist_ok=True)
    audio_paths: list[Path] = []
    durations: list[float] = []
    rate_adjustments: list[int] = []
    output: Path | None = None
    subtitle_path: Path | None = None
    output_ready = False
    base_rate = _parse_rate(rate)
    allowed_delta = max(0, min(int(max_rate_adjustment_pct), 30))
    try:
        for index, cue in enumerate(cues):
            audio_path = work_dir / f"beat_{index:02d}.mp3"
            beat_window = cue["end_s"] - cue["start_s"]
            audio = None
            if speech_cache_dir is not None:
                cached = await synthesize_cached(cue["text"], speech_cache_dir, voice, rate)
                if cached is not None:
                    import shutil

                    shutil.copyfile(cached, audio_path)
                    audio = audio_path
            if audio is None:
                audio = await synthesize(cue["text"], audio_path, voice, rate)
            if audio is None:
                return None
            duration = await get_duration(audio)
            adjustment = 0
            max_speech = max(0.25, beat_window - 0.15)
            if duration > max_speech:
                adjustment = min(allowed_delta, max(0, math.ceil((duration / max_speech - 1.0) * 100)))
                if adjustment <= 0:
                    return None
                faster_rate = _format_rate(base_rate + adjustment)
                audio = await synthesize(cue["text"], audio_path, voice, faster_rate)
                if audio is None:
                    return None
                duration = await get_duration(audio)
            if duration <= 0.05 or duration > beat_window:
                log.info(
                    "Beat narration declined: %s runs %.2fs in a %.2fs window.",
                    cue["beat_id"], duration, beat_window,
                )
                return None
            audio_paths.append(Path(audio))
            durations.append(duration)
            rate_adjustments.append(adjustment)

        output = Path(out_dir) / f"{video.stem}_narrated.mp4"
        subtitle_path = Path(out_dir) / f"{video.stem}.srt"
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        filters = []
        inputs = [ffmpeg, "-y", "-i", str(video)]
        mix_labels = []
        for index, (cue, audio_path) in enumerate(zip(cues, audio_paths, strict=True)):
            inputs.extend(["-i", str(audio_path)])
            label = f"beat{index}"
            delay_ms = round(cue["start_s"] * 1000)
            filters.append(
                f"[{index + 1}:a]adelay={delay_ms}:all=1,"
                f"apad=whole_dur={video_duration:.3f}[{label}]"
            )
            mix_labels.append(f"[{label}]")
        filters.append(
            f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:"
            "duration=longest:normalize=0,alimiter=limit=0.95[aout]"
        )
        cmd = inputs + [
            "-filter_complex", ";".join(filters),
            "-map", "0:v:0", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
            "-t", f"{video_duration:.3f}", "-movflags", "+faststart",
            str(output),
        ]
        output.unlink(missing_ok=True)
        if not await _run_ffmpeg(cmd):
            return None
        if not output.is_file() or output.stat().st_size <= 0:
            log.info("Beat narration mux produced no playable output file.")
            return None

        actual_captions = [
            (cue["subtitle_text"], min(duration, cue["end_s"] - cue["start_s"]))
            for cue, duration in zip(cues, durations, strict=True)
        ]
        subtitle_path.write_text(
            build_srt(actual_captions, [cue["start_s"] for cue in cues]),
            encoding="utf-8", newline="\n",
        )
        output_ready = True
        per_beat = []
        for cue, duration, adjustment in zip(cues, durations, rate_adjustments, strict=True):
            window = cue["end_s"] - cue["start_s"]
            per_beat.append({
                "beat_id": cue["beat_id"],
                "start_s": cue["start_s"],
                "end_s": cue["end_s"],
                "speech_duration_s": round(duration, 3),
                "boundary_overrun_s": round(max(0.0, duration - window), 3),
                "rate_adjustment_pct": adjustment,
                "target_object": cue["target_object"],
                "target_equation": cue["target_equation"],
                "anchor_cell": cue["anchor_cell"],
            })
        return {
            "video_path": str(output),
            "subtitle_path": str(subtitle_path),
            "sync": {
                "method": "storyboard_beat_windows",
                "timeline_scale": round(scale, 4),
                "beat_count": len(cues),
                "max_boundary_overrun_s": max(
                    (item["boundary_overrun_s"] for item in per_beat), default=0.0,
                ),
                "max_rate_adjustment_pct": max(rate_adjustments, default=0),
                "beats": per_beat,
            },
        }
    except Exception as exc:  # noqa: BLE001 - narration must stay fail-soft
        log.info("Timed beat narration failed (%s); keeping the silent cut.", exc)
        return None
    finally:
        if not output_ready:
            for incomplete in (output, subtitle_path):
                if incomplete is not None:
                    try:
                        incomplete.unlink(missing_ok=True)
                    except OSError:
                        pass
        for audio_path in audio_paths:
            try:
                audio_path.unlink(missing_ok=True)
            except OSError:
                pass
        try:
            work_dir.rmdir()
        except OSError:
            pass


def narration_available() -> bool:
    """True when both TTS and an ffmpeg binary are present (narration can run)."""
    try:
        import edge_tts  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return _ffmpeg_exe() is not None


# ── Lesson support: per-chapter narration + transcript timeline (Phase 2) ────
#
# For a multi-chapter LESSON, the natural narration unit is the chapter: each
# chapter is a short, single-focus scene, so whole-clip fitting per chapter
# gives exact-enough narration↔visual sync WITHOUT the fragility of per-beat
# sync (which this module deliberately avoids) or a manim-voiceover dependency.
# narrate_segment narrates one chapter and reports its spoken duration so the
# lesson pipeline can accumulate a transcript timeline → .srt subtitles.


async def narrate_segment(
    video: Path,
    narration: str,
    out_dir: Path,
    *,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
) -> tuple[Path | None, float]:
    """Narrate one chapter clip. Returns (narrated_path_or_None, spoken_seconds).

    The narrated path is None (caller keeps the silent clip) when narration is
    unavailable; the duration is always the final clip length so the transcript
    timeline stays correct either way.
    """
    video = Path(video)
    narrated = await add_voiceover(video, narration, out_dir, voice=voice, rate=rate)
    final = narrated or (video if video.exists() else None)
    duration = await get_duration(final) if final else 0.0
    return narrated, duration


def _fmt_srt_time(seconds: float) -> str:
    total_ms = max(0, int(round(float(seconds) * 1000)))
    total_s, ms = divmod(total_ms, 1000)
    h, rem = divmod(total_s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(
    segments: list[tuple[str, float]],
    starts: list[float] | None = None,
) -> str:
    """Build .srt subtitles from ordered (text, clip_duration_seconds) pairs.

    Each chapter becomes one cue spanning its clip; blank narration is skipped.

    ``starts`` gives each chapter's explicit start time (seconds) in the final
    video. Pass it for a PRODUCED lesson, whose intro/chapter title cards and
    crossfades push chapters later than a plain concat — without it the cues use
    a naive running sum of clip durations and drift out of sync with the video.
    """
    cues: list[str] = []
    t = 0.0
    index = 1
    for i, (text, duration) in enumerate(segments):
        duration = max(float(duration), 0.0)
        start = float(starts[i]) if starts and i < len(starts) else t
        text = " ".join(str(text).split())
        if text:
            cues.append(
                f"{index}\n{_fmt_srt_time(start)} --> {_fmt_srt_time(start + duration)}\n{text}\n"
            )
            index += 1
        t += duration
    return "\n".join(cues)


def storyboard_narration_script(storyboard: dict | None) -> str:
    """Join beat cues in timeline order, retaining the windows for the narrator."""
    if not isinstance(storyboard, dict):
        return ""
    timeline = storyboard.get("timeline")
    if isinstance(timeline, list):
        beats = []
        for item in timeline:
            if not isinstance(item, dict):
                continue
            cue = str(item.get("narration_cue", "")).strip()
            if not cue:
                continue
            beats.append(cue)
        if beats:
            return "\n".join(beats)
    lines = storyboard.get("narration")
    if isinstance(lines, list):
        return " ".join(str(x).strip() for x in lines if str(x).strip())
    if isinstance(lines, str):
        return lines.strip()
    return ""


def storyboard_narration_timing(storyboard: dict | None) -> str:
    """Human-readable beat windows for the script writer (never passed to TTS)."""
    if not isinstance(storyboard, dict):
        return ""
    lines = []
    for beat in storyboard.get("timeline", []) or []:
        if not isinstance(beat, dict):
            continue
        try:
            start, end = float(beat.get("start_s", 0)), float(beat.get("end_s", 0))
        except (TypeError, ValueError):
            continue
        cue = str(beat.get("narration_cue", "")).strip()
        lines.append(
            f"{beat.get('id', 'beat')} | {start:.1f}-{end:.1f}s | "
            f"target {end - start:.1f}s | cue: {cue}"
        )
    return "\n".join(lines)


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
