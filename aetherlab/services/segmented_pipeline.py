"""Resumable, independently rendered segments for long AI explanations.

Long scenes must not bypass the ordinary per-scene safety, timing, repair, and
critique gates. This module plans one global storyboard, rebases its beats into
bounded windows, then sends every window through those same gates. Segments
render serially for now; cloud concurrency is intentionally deferred until
per-attempt artifact isolation has been measured end to end.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from aetherlab.core.atomic_json import atomic_write_json
from aetherlab.core.models import ProblemRequest, RagResult, SceneBundle, SolverResult
from aetherlab.core.render_cache import requested_profile_key

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1
# About 5 beats per segment. Live 2026-10-02: 27 s segments carried ~9 beats and
# 24 animations, past the 16-play / 3.5-cost cloud limits, on every attempt.
DEFAULT_SEGMENT_MAX_S = 15.0
LONG_SCENE_THRESHOLD_S = 45.0


class SegmentPlanError(ValueError):
    """The global timeline cannot be divided without losing or reordering beats."""


def validate_timeline(storyboard: dict, target_seconds: float) -> list[dict[str, Any]]:
    """Return ordered beat records if the storyboard exactly covers its target."""
    timeline = storyboard.get("timeline")
    if not isinstance(timeline, list) or not timeline:
        raise SegmentPlanError("Long explanation storyboard has no timed beats.")
    target = float(target_seconds)
    if not target > 0:
        raise SegmentPlanError("Long explanation target must be positive.")
    beats: list[dict[str, Any]] = []
    for index, raw in enumerate(timeline):
        if not isinstance(raw, dict) or not raw.get("id"):
            raise SegmentPlanError(f"Timeline beat {index + 1} is missing a stable ID.")
        try:
            start, end = float(raw["start_s"]), float(raw["end_s"])
        except (KeyError, TypeError, ValueError) as exc:
            raise SegmentPlanError(f"Timeline beat {index + 1} has invalid times.") from exc
        if not (start >= 0 and end > start):
            raise SegmentPlanError(f"Timeline beat {raw['id']} has a non-positive interval.")
        beat = dict(raw)
        beat["start_s"], beat["end_s"] = start, end
        beats.append(beat)
    beats.sort(key=lambda item: (item["start_s"], item["end_s"], str(item["id"])))
    if abs(beats[0]["start_s"]) > 0.05:
        raise SegmentPlanError("Timeline must start at 0 seconds.")
    cursor = 0.0
    for beat in beats:
        start, end = beat["start_s"], beat["end_s"]
        if abs(start - cursor) > 0.05:
            relation = "overlaps" if start < cursor else "has a gap before"
            raise SegmentPlanError(f"Timeline {relation} beat {beat['id']}.")
        cursor = end
    if abs(cursor - target) > 0.05:
        raise SegmentPlanError(
            f"Timeline ends at {cursor:.3f}s, not the requested {target:.3f}s."
        )
    return beats


def partition_storyboard(
    storyboard: dict,
    target_seconds: float,
    *,
    max_segment_seconds: float = DEFAULT_SEGMENT_MAX_S,
) -> list[dict[str, Any]]:
    """Partition at beat boundaries and return local-time storyboards.

    A beat is never split across clips. If one individual beat exceeds the
    requested maximum, it remains intact and is surfaced as a long segment for
    the ordinary render-cost admission gate to decide.
    """
    if max_segment_seconds <= 0:
        raise ValueError("max_segment_seconds must be positive")
    beats = validate_timeline(storyboard, target_seconds)
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    group_start = beats[0]["start_s"]
    for beat in beats:
        if current and beat["end_s"] - group_start > max_segment_seconds + 1e-6:
            groups.append(current)
            current = []
            group_start = beat["start_s"]
        current.append(beat)
    if current:
        groups.append(current)
    # Avoid a tiny tail clip where moving its beats to the previous clip still
    # respects the admission bound. This keeps the narration/transition count low.
    if len(groups) > 1:
        final_end = groups[-1][-1]["end_s"]
        if final_end - groups[-2][0]["start_s"] <= max_segment_seconds + 1e-6:
            groups[-2].extend(groups.pop())

    result: list[dict[str, Any]] = []
    shared_keys = (
        "concept", "staging", "palette", "hero_frame", "idle_loop", "narration",
        # Voice-first boards: segments keep the measured windows and voice.
        "timing_basis", "speech",
    )
    for index, group in enumerate(groups):
        start, end = group[0]["start_s"], group[-1]["end_s"]
        local_beats = []
        local_timeline = []
        for local_index, source in enumerate(group):
            beat = dict(source)
            beat["global_id"] = str(source["id"])
            beat["global_start_s"] = source["start_s"]
            beat["global_end_s"] = source["end_s"]
            beat["id"] = f"S{index + 1}.B{local_index + 1}"
            beat["start_s"] = round(source["start_s"] - start, 3)
            beat["end_s"] = round(source["end_s"] - start, 3)
            beat["duration_s"] = round(beat["end_s"] - beat["start_s"], 3)
            local_beats.append(beat)
            local_timeline.append(dict(beat))
        act_name = str(group[0].get("act") or f"Segment {index + 1}")
        local_board = {key: storyboard[key] for key in shared_keys if key in storyboard}
        local_board.update({
            "title": storyboard.get("title", ""),
            "creative_direction": storyboard.get("creative_direction", ""),
            "global_duration_s": float(target_seconds),
            "segment_index": index + 1,
            "segment_count": len(groups),
            "segment_global_start_s": round(start, 3),
            "segment_global_end_s": round(end, 3),
            "continuity": {
                "entry_beat": group[0].get("detail", ""),
                "exit_beat": group[-1].get("detail", ""),
                "preserve_visual_identity": True,
            },
            "acts": [{
                "name": act_name,
                "duration_s": round(end - start, 3),
                "beats": local_beats,
            }],
            "timeline": local_timeline,
            "timeline_duration_s": round(end - start, 3),
        })
        result.append({
            "index": index,
            "start_s": round(start, 3),
            "end_s": round(end, 3),
            "duration_s": round(end - start, 3),
            "beat_ids": [str(beat["global_id"]) for beat in local_beats],
            "storyboard": local_board,
        })
    if abs(sum(item["duration_s"] for item in result) - target_seconds) > 0.05:
        raise SegmentPlanError("Partition changed the total requested duration.")
    return result


async def _hold_last_frame(video: Path, seconds: float) -> bool:
    """Extend ``video`` in place by freezing its last frame for ``seconds``."""
    from aetherlab.services.voiceover import _ffmpeg_exe, _run_ffmpeg

    ffmpeg = _ffmpeg_exe()
    if not ffmpeg or seconds <= 0:
        return False
    try:
        import av

        with av.open(str(video)) as container:
            has_audio = bool(container.streams.audio)
    except Exception:  # noqa: BLE001 - probe failure: treat as video-only
        has_audio = False
    held = video.with_name(video.stem + ".held.mp4")
    cmd = [ffmpeg, "-y", "-i", str(video),
           "-vf", f"tpad=stop_mode=clone:stop_duration={seconds:.3f}"]
    if has_audio:
        cmd += ["-af", f"apad=pad_dur={seconds:.3f}", "-c:a", "aac", "-b:a", "160k"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(held)]
    if not await _run_ffmpeg(cmd) or not held.is_file():
        held.unlink(missing_ok=True)
        return False
    held.replace(video)
    return True


def _segment_play_budget(segment: dict) -> int:
    """Top-level play calls a segment may use: two per beat plus an entry and exit."""
    return min(16, 2 * max(1, len(segment.get("beat_ids") or [])) + 2)


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _profile(settings: Any, quality: str) -> dict[str, Any]:
    try:
        from importlib.metadata import version

        manim_version = version("manim")
    except Exception:  # noqa: BLE001 - profile discovery must fail soft
        manim_version = "unavailable"
    try:
        from aetherlab.core.render_profile import get_effective_profile

        _rp = get_effective_profile(settings, quality=quality or "")
        _rp_key = _rp.identity_key()
        _rp_quality = str(getattr(_rp, "quality", quality) or quality)
        _rp_renderer = str(getattr(_rp, "renderer", "cairo") or "cairo")
        _rp_fps = str(getattr(_rp, "fps", ""))
        _rp_preset = str(getattr(_rp, "preset", ""))
        _rp_canvas = f"{getattr(_rp, 'width', '')}x{getattr(_rp, 'height', '')}"
    except Exception:  # noqa: BLE001 - profile discovery must fail soft
        _rp_key, _rp_quality = "", quality
        _rp_renderer = os.getenv("AETHERLAB_MANIM_RENDERER", "cairo").strip().lower()
        _rp_fps = os.getenv("AETHERLAB_MANIM_FPS", "")
        _rp_preset, _rp_canvas = "", ""
    return {
        "model": str(getattr(settings, "llm_model", "")),
        "quality": _rp_quality,
        "render_mode": str(getattr(settings, "render_mode", "local")),
        "renderer": _rp_renderer,
        "fps": _rp_fps,
        "render_preset": _rp_preset,
        "render_canvas": _rp_canvas,
        "render_identity": _rp_key,
        "manim": manim_version,
        "voice": str(getattr(settings, "tts_voice", "")),
        "voice_rate": str(getattr(settings, "tts_rate", "")),
        "narration": bool(getattr(settings, "narration_enabled", False)),
        "render_workflow": _render_workflow_hash(),
    }


def _render_workflow_hash() -> str:
    workflow = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "render.yml"
    try:
        return _file_hash(workflow)
    except OSError:
        return "unavailable"


def _request_fingerprint(
    request: ProblemRequest, solver: SolverResult, rag: RagResult, settings: Any, quality: str
) -> str:
    return _stable_hash({
        "schema": SCHEMA_VERSION,
        "request": request.canonical_payload(),
        "solver": solver.to_json(),
        "rag": rag.to_json(),
        "profile": _profile(settings, quality),
    })


def _valid_video(path: Path, expected_hash: str = "") -> bool:
    try:
        if not path.is_file() or path.stat().st_size <= 1024:
            return False
        if expected_hash and _file_hash(path) != expected_hash:
            return False
        import av

        with av.open(str(path)) as container:
            stream = next(iter(container.streams.video), None)
            return stream is not None and any(container.decode(stream))
    except ImportError:
        return path.is_file() and path.stat().st_size > 1024
    except Exception:  # noqa: BLE001 - damaged caches are invalidated
        return False


def _cancelled(cancel_check: Callable[[], bool] | None) -> bool:
    return bool(cancel_check and cancel_check())


def _incomplete(message: str, *, engine: str = "manim-community", diagnostics=None) -> SceneBundle:
    return SceneBundle(
        class_name="AetherLabSegmentedScene",
        code="",
        engine=engine,
        status="incomplete",
        diagnostics=list(diagnostics or []) + [message],
    )


async def render_segmented_scene(
    request: ProblemRequest,
    solver: SolverResult,
    rag: RagResult,
    settings: Any,
    *,
    runtime=None,
    quality: str = "l",
    max_segment_seconds: float = DEFAULT_SEGMENT_MAX_S,
    progress: Callable[[str], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> SceneBundle:
    """Generate, safely render, resume, and assemble one long explanation.

    This entry point is for AI-authored long-form scenes. Requests at or below
    45 seconds retain the established single-scene/curated path. If a complete
    storyboard cannot be obtained, no unrelated fallback is reported as a
    successful long explanation.
    """
    if float(request.duration_target_s) <= LONG_SCENE_THRESHOLD_S:
        raise ValueError("render_segmented_scene only accepts requests over 45 seconds")
    engine = "manim-community"
    if not getattr(settings, "openai_api_key", None):
        return _incomplete(
            "Long-form AI generation requires a configured model; no segmented fallback was substituted.",
            engine=engine,
        )
    from aetherlab.services.manim_runtime import ManimRuntime
    from aetherlab.services.scene_generator import SceneGenerator
    from aetherlab.services.voiceover import get_duration

    runtime = runtime or ManimRuntime(settings)
    fingerprint = _request_fingerprint(request, solver, rag, settings, quality)
    cache_dir = Path(settings.data_dir) / "segmented_scenes" / fingerprint
    manifest_path = cache_dir / "manifest.json"
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            not isinstance(manifest, dict)
            or manifest.get("schema_version") != SCHEMA_VERSION
            or manifest.get("fingerprint") != fingerprint
        ):
            manifest = {}
    except (OSError, json.JSONDecodeError):
        manifest = {}

    if not isinstance(manifest.get("storyboard"), dict):
        if progress:
            progress("Directing the full explanation before segment rendering.")
        # The whole lesson hangs on this one plan, and a single bad reply (cut
        # short, or too few beats) is common enough to retry once.
        global_board = None
        for attempt in range(2):
            global_board = await SceneGenerator(settings).storyboard(
                request, solver, rag, temperature=0.9,
            )
            if isinstance(global_board, dict):
                break
            if progress and attempt == 0:
                progress("The first plan was unusable; asking for the full plan again.")
        if not isinstance(global_board, dict):
            return _incomplete(
                "Could not produce a sufficiently detailed global storyboard; long-form generation stopped without a template substitute.",
                engine=engine,
            )
        try:
            segments = partition_storyboard(
                global_board,
                float(request.duration_target_s),
                max_segment_seconds=max_segment_seconds,
            )
        except (SegmentPlanError, TypeError, ValueError) as exc:
            return _incomplete(f"Invalid long-form beat schedule: {exc}", engine=engine)
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "fingerprint": fingerprint,
            "target_duration_s": float(request.duration_target_s),
            "profile": _profile(settings, quality),
            "storyboard": global_board,
            "segments": [{
                "index": item["index"], "start_s": item["start_s"],
                "end_s": item["end_s"], "duration_s": item["duration_s"],
                "beat_ids": item["beat_ids"],
                "storyboard_hash": _stable_hash(item["storyboard"]),
                "storyboard": item["storyboard"],
                "state": "pending",
                "code_hash": "", "video_hash": "", "bundle": None,
            } for item in segments],
            "state": "rendering",
        }
        atomic_write_json(manifest_path, manifest)
    else:
        global_board = manifest["storyboard"]
        try:
            segments = partition_storyboard(
                manifest["storyboard"], float(request.duration_target_s),
                max_segment_seconds=max_segment_seconds,
            )
        except (KeyError, SegmentPlanError, TypeError, ValueError) as exc:
            return _incomplete(f"Cached long-form storyboard is invalid: {exc}", engine=engine)
        cached_specs = manifest.get("segments", [])
        cached_specs_valid = (
            isinstance(cached_specs, list)
            and len(cached_specs) == len(segments)
            and all(
                isinstance(cached_specs[i], dict)
                and cached_specs[i].get("storyboard_hash") == _stable_hash(item["storyboard"])
                for i, item in enumerate(segments)
            )
        )
        if not cached_specs_valid:
            # The manifest is the cache authority; a changed global board cannot
            # reuse media whose entry/exit contract no longer matches.
            manifest["segments"] = [{
                "index": item["index"], "start_s": item["start_s"],
                "end_s": item["end_s"], "duration_s": item["duration_s"],
                "beat_ids": item["beat_ids"],
                "storyboard_hash": _stable_hash(item["storyboard"]),
                "storyboard": item["storyboard"],
                "state": "pending", "code_hash": "", "video_hash": "", "bundle": None,
            } for item in segments]
            atomic_write_json(manifest_path, manifest)

    segment_videos: list[Path] = []
    segment_bundles: list[SceneBundle] = []
    segment_subtitles: list[str] = []
    try:
        for index, item in enumerate(segments):
            if _cancelled(cancel_check):
                manifest["state"] = "cancelled"
                atomic_write_json(manifest_path, manifest)
                return _incomplete("Long-form render cancelled; completed segment artifacts are resumable.", engine=engine)
            record = manifest["segments"][index]
            segment_dir = cache_dir / f"segment_{index + 1:03d}"
            segment_dir.mkdir(parents=True, exist_ok=True)
            video_path = segment_dir / "segment.mp4"
            code_path = segment_dir / "scene.py"
            saved_bundle = record.get("bundle")
            if (
                isinstance(saved_bundle, dict)
                and record.get("state") == "rendered"
                and code_path.is_file()
                and _file_hash(code_path) == str(record.get("code_hash", ""))
                and _valid_video(video_path, str(record.get("video_hash", "")))
            ):
                bundle = SceneBundle.from_json(saved_bundle, cached=True)
                bundle.video_path = str(video_path)
                subtitle_text = str(record.get("subtitle_text", ""))
                if subtitle_text:
                    subtitle_file = segment_dir / "segment.srt"
                    subtitle_file.write_text(subtitle_text, encoding="utf-8")
                    bundle.subtitle_path = str(subtitle_file)
                # Keep the reused segment's cues: without this the merged track
                # dropped them, and a fully resumed narrated lesson was reported
                # incomplete even though every segment was verified.
                segment_subtitles.append(subtitle_text)
                if progress:
                    progress(f"Reusing verified segment {index + 1}/{len(segments)}.")
            else:
                target = float(item["duration_s"])
                can_resume_compiled = (
                    isinstance(saved_bundle, dict)
                    and record.get("state") == "compiled"
                    and code_path.is_file()
                    and bool(record.get("code_hash"))
                    and _file_hash(code_path) == str(record.get("code_hash"))
                )
                if can_resume_compiled:
                    bundle = SceneBundle.from_json(saved_bundle, cached=True)
                    bundle.status = "compiled"
                    bundle.code = code_path.read_text(encoding="utf-8")
                    if progress:
                        progress(f"Resuming compiled segment {index + 1}/{len(segments)}.")
                else:
                    segment_request = replace(
                        request,
                        prompt=(
                            f"{request.prompt}\n\n"
                            f"This is segment {index + 1} of {len(segments)} in one continuous explanation. "
                            f"Overall story: {global_board.get('creative_direction', global_board.get('title', ''))}. "
                            f"Cover only its assigned local beats and preserve the same equations, values, units, "
                            f"colors, objects, and visual style. Entry: {item['storyboard']['continuity']['entry_beat']}. "
                            f"Exit: {item['storyboard']['continuity']['exit_beat']}. Do not introduce a new scenario. "
                            f"Budget: at most {_segment_play_budget(item)} top-level self.play calls; "
                            f"animate simultaneous changes in one play call."
                        ),
                        duration_target_s=target,
                    )
                    if progress:
                        progress(f"Generating segment {index + 1}/{len(segments)} ({target:.1f}s).")
                    record["state"] = "generating"
                    atomic_write_json(manifest_path, manifest)
                    # One segment failing stops the whole lesson, so each gets a
                    # second full generation before that happens.
                    first_try: list[str] = []
                    for segment_try in range(2):
                        bundle = await runtime.generate_scene_async(
                            segment_request, solver, rag, settings,
                            locked_storyboard=item["storyboard"], force_ai=True,
                        )
                        if not bundle.used_fallback and bundle.status == "compiled":
                            break
                        if segment_try == 0:
                            first_try = [f"First try: {d}" for d in bundle.diagnostics]
                            if progress:
                                progress(f"Segment {index + 1} failed its checks; generating it once more.")
                    bundle.diagnostics = first_try + bundle.diagnostics
                    if bundle.used_fallback:
                        return _incomplete(
                            f"Segment {index + 1} fell back to a template; the long explanation is incomplete.",
                            engine=engine, diagnostics=bundle.diagnostics,
                        )
                    if bundle.status != "compiled":
                        return _incomplete(
                            f"Segment {index + 1} did not pass compilation/static checks.",
                            engine=engine, diagnostics=bundle.diagnostics,
                        )
                    code_path.write_text(bundle.code, encoding="utf-8")
                    record["code_hash"] = _file_hash(code_path)
                    record["state"] = "compiled"
                    record["bundle"] = bundle.to_json()
                    atomic_write_json(manifest_path, manifest)
                if progress:
                    progress(f"Rendering and reviewing segment {index + 1}/{len(segments)}.")
                bundle = await runtime.render_scene_with_repair(
                    bundle, settings, quality=quality,
                    brief=f"{request.prompt}\nSegment {index + 1}: {item['beat_ids']}",
                    progress=progress,
                    cancel_check=cancel_check,
                    duration_target_s=target,
                )
                if bundle.status != "rendered" or not bundle.video_path:
                    return _incomplete(
                        f"Segment {index + 1} failed to render; the parent lesson remains incomplete.",
                        engine=engine, diagnostics=bundle.diagnostics,
                    )
                if bool(getattr(settings, "narration_enabled", False)):
                    sync = bundle.narration_sync if isinstance(bundle.narration_sync, dict) else {}
                    if not bundle.silent_video_path or not bundle.narration_text:
                        return _incomplete(
                            f"Segment {index + 1} has no verified narration track.",
                            engine=engine, diagnostics=bundle.diagnostics,
                        )
                    if sync.get("method") != "storyboard_beat_windows":
                        return _incomplete(
                            f"Segment {index + 1} narration fell back from beat timing; alignment is unverified.",
                            engine=engine, diagnostics=bundle.diagnostics,
                        )
                    if (
                        float(sync.get("max_boundary_overrun_s", 0.0) or 0.0) > 0.25
                        or int(sync.get("max_rate_adjustment_pct", 0) or 0) > 20
                    ):
                        return _incomplete(
                            f"Segment {index + 1} narration exceeds the sync or speech-rate gate.",
                            engine=engine, diagnostics=bundle.diagnostics,
                        )
                source = Path(bundle.video_path)
                if not _valid_video(source):
                    return _incomplete(f"Segment {index + 1} produced an unreadable MP4.", engine=engine)
                shutil.copy2(source, video_path)
                measured = await get_duration(video_path)
                if 0 < measured < target - 0.05 and target - measured <= max(2.5, target * 0.2):
                    # A slightly short segment holds its final frame (and
                    # silence) to fill its slot: invisible, keeps every later
                    # segment and the total length on time. Live 2026-10-02:
                    # 13.17 s in a 14.24 s slot stopped the lesson.
                    held = await _hold_last_frame(video_path, target - measured)
                    if held:
                        bundle.diagnostics.append(
                            f"Held the final frame {target - measured:.2f}s to fill the {target:.2f}s slot."
                        )
                        measured = await get_duration(video_path)
                # Short segments were just held to fill their slot. A long one
                # keeps every beat start on time (preflight-verified) and only
                # holds its last beat longer, so it is accepted within the
                # scene gate's 20%; narration stays at the planned starts.
                short_limit = max(1.0, target * 0.05)
                long_limit = max(1.0, target * 0.20)
                if measured <= 0 or measured < target - short_limit or measured > target + long_limit:
                    return _incomplete(
                        f"Segment {index + 1} measures {measured:.2f}s; expected {target:.2f}s "
                        f"(-{short_limit:.2f}s / +{long_limit:.2f}s).",
                        engine=engine, diagnostics=bundle.diagnostics,
                    )
                if measured > target + short_limit:
                    bundle.diagnostics.append(
                        f"Segment runs {measured - target:.2f}s past its {target:.2f}s slot "
                        "(longer final hold; beat starts unchanged)."
                    )
                bundle.video_path = str(video_path)
                code_path.write_text(bundle.code, encoding="utf-8")
                subtitle_text = ""
                if bundle.subtitle_path and Path(bundle.subtitle_path).is_file():
                    subtitle_text = Path(bundle.subtitle_path).read_text(encoding="utf-8")
                    subtitle_file = segment_dir / "segment.srt"
                    subtitle_file.write_text(subtitle_text, encoding="utf-8")
                    bundle.subtitle_path = str(subtitle_file)
                segment_subtitles.append(subtitle_text)
                record["state"] = "rendered"
                record["code_hash"] = _file_hash(code_path)
                record["video_hash"] = _file_hash(video_path)
                record["subtitle_text"] = subtitle_text
                record["bundle"] = bundle.to_json()
                atomic_write_json(manifest_path, manifest)
            segment_videos.append(video_path)
            segment_bundles.append(bundle)
            if len(segment_subtitles) < index + 1:
                segment_subtitles.append("")

        if len(segment_videos) != len(segments):
            return _incomplete("One or more required segment artifacts are missing.", engine=engine)
        if progress:
            progress("Assembling continuous lesson and validating final duration.")
        final_path = cache_dir / "lesson.mp4"
        if not (
            manifest.get("state") == "complete"
            and _valid_video(final_path, str(manifest.get("lesson_video_hash", "")))
        ):
            from aetherlab.services.assembly import assemble_lesson

            try:
                from aetherlab.core.render_profile import get_effective_profile

                _seg_profile = get_effective_profile(settings, quality=quality or "")
            except Exception:  # noqa: BLE001 - assembly resolves its own canvas fallback
                _seg_profile = None
            assembled = await assemble_lesson(
                segment_videos, final_path, timeout=900,
                profile=_seg_profile, settings=settings, quality=quality or "",
            )
            if not assembled or not Path(assembled).is_file():
                return _incomplete("Segment assembly failed; no complete lesson was published.", engine=engine)
            final_path = Path(assembled)
        final_duration = await get_duration(final_path)
        target_duration = float(request.duration_target_s)
        # Segments never end short (they are held to fill), but each may run
        # up to 20% long, so the lesson may end up to 20% past its target.
        final_short = 1.0 if target_duration <= 60.0 else 2.0
        final_long = max(final_short, target_duration * 0.20)
        if (
            final_duration <= 0
            or final_duration < target_duration - final_short
            or final_duration > target_duration + final_long
        ):
            return _incomplete(
                f"Assembled lesson measures {final_duration:.2f}s; expected {target_duration:.2f}s "
                f"(-{final_short:.2f}s / +{final_long:.2f}s).",
                engine=engine,
            )
        subtitle_path = cache_dir / "lesson.srt"
        shifted = _shift_subtitles(segment_subtitles, segment_videos)
        if bool(getattr(settings, "narration_enabled", False)) and not shifted:
            return _incomplete("Narrated segments could not be merged into a valid subtitle track.", engine=engine)
        if shifted:
            subtitle_path.write_text(shifted, encoding="utf-8")
        manifest["state"] = "complete"
        manifest["lesson_video_hash"] = _file_hash(final_path)
        manifest["lesson_duration_s"] = final_duration
        manifest["subtitle_path"] = str(subtitle_path) if shifted else ""
        atomic_write_json(manifest_path, manifest)
        diagnostics = [
            f"Rendered and assembled {len(segments)} independently validated segments.",
            f"Final duration {final_duration:.2f}s (target {target_duration:.2f}s).",
            f"Resumable manifest: {manifest_path}",
        ]
        for bundle in segment_bundles:
            diagnostics.extend(bundle.diagnostics)
        return SceneBundle(
            class_name="AetherLabSegmentedScene",
            code="\n\n".join(bundle.code for bundle in segment_bundles),
            engine=engine,
            status="rendered",
            render_profile_key=requested_profile_key(settings, quality),
            diagnostics=diagnostics,
            video_path=str(final_path),
            silent_video_path="",
            storyboard=global_board,
            quality_score=min((bundle.quality_score for bundle in segment_bundles), default=0.0),
            critique_verdict="segment-level review complete",
            critique_issues=[issue for bundle in segment_bundles for issue in bundle.critique_issues],
            critique_breakdown={},
            subtitle_path=str(subtitle_path) if shifted else "",
            narration_text="\n".join(bundle.narration_text for bundle in segment_bundles),
            narration_sync={"segment_count": len(segments), "target_duration_s": target_duration,
                            "actual_duration_s": final_duration},
        )
    except asyncio.CancelledError:
        manifest["state"] = "cancelled"
        atomic_write_json(manifest_path, manifest)
        raise
    except Exception as exc:  # noqa: BLE001 - incomplete state is explicit and resumable
        log.exception("Segmented long scene failed")
        manifest["state"] = "incomplete"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        atomic_write_json(manifest_path, manifest)
        return _incomplete(
            f"Long explanation stopped incomplete: {type(exc).__name__}: {exc}", engine=engine
        )


_SRT_TIME = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2},\d{3})"
)


def _srt_seconds(value: str) -> float:
    hours, minutes, rest = value.split(":")
    seconds, millis = rest.split(",")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000.0


def _srt_timestamp(value: float) -> str:
    millis = max(0, round(value * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    seconds, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def _shift_subtitles(subtitles: list[str], videos: list[Path]) -> str:
    """Merge segment-local SRT cues onto the concatenated timeline."""
    try:
        from aetherlab.services.voiceover import _duration_sync

        offsets = []
        cursor = 0.0
        for video in videos:
            offsets.append(cursor)
            cursor += max(0.0, float(_duration_sync(video)))
    except Exception:  # noqa: BLE001
        return ""
    out: list[str] = []
    cue_index = 1
    for index, source in enumerate(subtitles):
        if index >= len(offsets):
            break
        normalized = source.replace("\r\n", "\n").strip()
        if not normalized:
            continue
        blocks = re.split(r"\n\s*\n", normalized)
        for block in blocks:
            match = _SRT_TIME.search(block)
            if not match:
                continue
            body = block[match.end():].strip()
            if not body:
                continue
            start = offsets[index] + _srt_seconds(match.group("start"))
            end = offsets[index] + _srt_seconds(match.group("end"))
            out.append(
                f"{cue_index}\n{_srt_timestamp(start)} --> {_srt_timestamp(end)}\n{body}"
            )
            cue_index += 1
    return "\n\n".join(out) + ("\n" if out else "")
