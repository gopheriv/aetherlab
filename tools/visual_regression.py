"""Render and audit AetherLab's canonical visual regression set.

The harness uses AetherLab's real local scene/lesson pipelines, then stores
only lightweight audit reports and JPEG contact sheets. It deliberately strips
provider/cloud credentials from the process environment before loading app
settings so generated reports are public-safe and deterministic.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import av
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "visual_regression" / "cases.json"
DEFAULT_OUT = ROOT / "visual_regression" / "runs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

SECRET_ENV_KEYS = (
    "AETHERLAB_OPENAI_API_KEY",
    "OPENAI_API_KEY",
    "GPT_API_KEY",
    "DASHSCOPE_API_KEY",
    "AETHERLAB_GITHUB_TOKEN",
    "GITHUB_TOKEN",
    "AETHERLAB_RENDER_REPO",
    "CLOUD_RENDER_REPO",
    "AETHERLAB_OPENAI_BASE_URL",
    "OPENAI_BASE_URL",
    "GPT_BASE_URL",
    "LLM_BASE_URL",
    "AETHERLAB_PROVIDER",
    "AETHERLAB_QWEN_AUTOLOAD",
    "QWEN_SETTINGS_PATH",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--quality", default="l", choices=("l", "m", "h", "p", "k"))
    parser.add_argument("--limit", type=int, default=0, help="Audit only the first N cases.")
    parser.add_argument("--regenerate", action="store_true", help="Bypass lesson/chapter caches where supported.")
    parser.add_argument("--compare", type=Path, default=None, help="Optional previous run directory with summary.json.")
    args = parser.parse_args(argv)

    cases = load_cases(args.cases)
    if args.limit:
        cases = cases[: max(0, args.limit)]
    args.out.mkdir(parents=True, exist_ok=True)

    _harden_environment()
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    started = datetime.now(timezone.utc)
    report = asyncio.run(run_cases(cases, args.out, args.quality, args.regenerate))
    report["started_at"] = started.isoformat(timespec="seconds")
    report["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    report["case_file"] = str(args.cases.resolve())
    report["quality"] = args.quality
    report["compare"] = compare_report(args.compare, report) if args.compare else None

    write_outputs(args.out, report)
    failures = [c for c in report["cases"] if c["status"] == "fail"]
    print(f"Visual regression audit wrote {args.out}")
    print(f"Cases: {len(report['cases'])}; failures: {len(failures)}")
    return 1 if failures else 0


def load_cases(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON list")
    cases: list[dict[str, Any]] = []
    for i, entry in enumerate(payload, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"case {i} must be an object")
        case_id = str(entry.get("id", "")).strip()
        kind = str(entry.get("kind", "")).strip()
        if not re.fullmatch(r"[a-z0-9_-]+", case_id):
            raise ValueError(f"case {i} has invalid id: {case_id!r}")
        if kind not in {"scene", "lesson"}:
            raise ValueError(f"case {case_id} has invalid kind: {kind!r}")
        if kind == "scene" and not str(entry.get("prompt", "")).strip():
            raise ValueError(f"scene case {case_id} needs a prompt")
        if kind == "lesson" and not str(entry.get("topic", "")).strip():
            raise ValueError(f"lesson case {case_id} needs a topic")
        cases.append(entry)
    return cases


def _harden_environment() -> None:
    data_dir = ROOT / ".analysis" / "visual-regression-data"
    for key in SECRET_ENV_KEYS:
        os.environ.pop(key, None)
    os.environ["AETHERLAB_DATA_DIR"] = str(data_dir / "data")
    os.environ["AETHERLAB_CACHE_PATH"] = str(data_dir / "cache.sqlite3")
    os.environ["AETHERLAB_CHROMA_PATH"] = str(data_dir / "chroma")
    os.environ["AETHERLAB_LIBRARY_DIR"] = str(data_dir / "library")
    os.environ["AETHERLAB_RENDER_MODE"] = "local"
    os.environ["AETHERLAB_WEB_REFS"] = "0"
    os.environ["AETHERLAB_NARRATION"] = "0"
    os.environ["AETHERLAB_VISUAL_CRITIC_MAX_PASSES"] = "0"
    os.environ["AETHERLAB_VISUAL_CRITIC_KEYFRAMES"] = "0"
    os.environ["CLOUD_RENDER_ENABLED"] = "0"
    os.environ["VOICEOVER_ENABLED"] = "0"
    os.environ["TTS_ENABLED"] = "0"
    data_dir.mkdir(parents=True, exist_ok=True)


async def run_cases(cases: list[dict[str, Any]], out_dir: Path, quality: str, regenerate: bool) -> dict[str, Any]:
    from aetherlab.core.settings import load_settings
    from aetherlab.services.lesson_pipeline import LessonPipeline
    from aetherlab.services.pipeline import AetherLabPipeline

    settings = replace(
        load_settings(),
        openai_api_key=None,
        openai_base_url=None,
        web_references=False,
        narration_enabled=False,
        render_mode="local",
        github_repo="",
        github_token="",
        cloud_provider="github_actions",
        visual_critic_max_passes=0,
        visual_critic_keyframes=0,
    )
    pipeline = AetherLabPipeline(settings)
    lesson_pipeline = LessonPipeline(settings)
    results: list[dict[str, Any]] = []

    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] render {case['id']}", flush=True)
        try:
            artifact = await render_case(case, pipeline, lesson_pipeline, quality, regenerate)
            metrics = audit_video(Path(artifact["video_path"]), out_dir, case["id"], artifact.get("srt_path"))
            public_artifact = public_artifact_paths(artifact)
            results.append({
                "id": case["id"],
                "kind": case["kind"],
                "status": "warn" if metrics["warnings"] else "pass",
                "artifact": public_artifact,
                "expect": case.get("expect", []),
                "metrics": metrics,
            })
        except Exception as exc:  # noqa: BLE001
            results.append({
                "id": case.get("id", f"case_{index}"),
                "kind": case.get("kind", "unknown"),
                "status": "fail",
                "error": f"{type(exc).__name__}: {exc}",
            })
    return {"schema": 1, "cases": results}


async def render_case(
    case: dict[str, Any],
    pipeline: Any,
    lesson_pipeline: Any,
    quality: str,
    regenerate: bool,
) -> dict[str, Any]:
    from aetherlab.core.models import ProblemRequest

    if case["kind"] == "lesson":
        bundle = await lesson_pipeline.run(
            str(case["topic"]),
            audience=str(case.get("audience", "undergrad")),
            quality=quality,
            max_concurrent=1,
            regenerate=regenerate,
        )
        if not bundle.video_path:
            raise RuntimeError(f"lesson did not produce a video; status={bundle.status}")
        return {
            "status": bundle.status,
            "video_path": bundle.video_path,
            "srt_path": getattr(bundle, "srt_path", ""),
            "chapter_count": len(bundle.chapter_scenes),
            "chapter_offsets": list(bundle.chapter_offsets),
            "rendered_chapter_indexes": list(bundle.rendered_chapter_indexes),
        }

    request = ProblemRequest(prompt=str(case["prompt"]), session_id=f"visual-regression-{case['id']}")
    if regenerate:
        key = pipeline.cache.ensure_request(request)
        pipeline.cache.clear_artifacts(key)
    result = await pipeline.run(request)
    if not result.scene.video_path:
        raise RuntimeError(f"scene did not produce a video; status={result.scene.status}")
    return {
        "status": result.scene.status,
        "video_path": result.scene.video_path,
        "cache_key": result.cache_key,
        "engine": result.scene.engine,
        "class_name": result.scene.class_name,
        "diagnostics": result.scene.diagnostics,
    }


def audit_video(video_path: Path, out_dir: Path, case_id: str, srt_path: str | None = None) -> dict[str, Any]:
    if not video_path.exists():
        raise FileNotFoundError(video_path)

    frames = decode_video(video_path)
    if not frames:
        raise RuntimeError(f"{video_path} decoded to zero frames")

    times = np.array([f["time"] for f in frames], dtype=np.float64)
    grays = np.stack([f["gray"] for f in frames])
    means = grays.mean(axis=(1, 2))
    stds = grays.std(axis=(1, 2))
    diffs = frame_diffs(grays)
    duration = max(float(times[-1]), 0.0) + estimate_frame_period(times)
    fps = (len(frames) / duration) if duration > 0 else 0.0

    blank_flags = (means < 7.0) & (stds < 5.0)
    # Treat only near-identical consecutive frames as static. Smooth Manim
    # motion can have low per-frame RMS, especially after compression, so this
    # threshold is intentionally tight and range-based.
    static_flags = np.concatenate([[False], diffs < 0.035]) if len(diffs) else np.array([False] * len(frames))
    blank_ranges = flag_ranges(blank_flags, times, min_duration=0.20)
    static_ranges = flag_ranges(static_flags, times, min_duration=0.75)
    transitions = top_transitions(diffs, times)

    contact_sheet = out_dir / f"{case_id}_contact.jpg"
    write_contact_sheet(frames, contact_sheet, case_id)

    subtitle = audit_subtitles(Path(srt_path), duration, transitions) if srt_path else None
    warnings: list[str] = []
    if duration < 2.0:
        warnings.append("duration below 2s")
    if fps < 5.0:
        warnings.append("fps below 5")
    if blank_ranges:
        warnings.append(f"{len(blank_ranges)} blank range(s)")
    if static_ranges and max(r["duration"] for r in static_ranges) > max(3.0, duration * 0.45):
        warnings.append("long static visual range")
    if subtitle and subtitle["warnings"]:
        warnings.extend(f"subtitle: {w}" for w in subtitle["warnings"])

    width, height = frames[0]["size"]
    return {
        "video_path": public_path(video_path),
        "contact_sheet": str(contact_sheet),
        "width": width,
        "height": height,
        "duration": round(duration, 3),
        "fps": round(fps, 3),
        "frame_count": len(frames),
        "blank_frame_count": int(blank_flags.sum()),
        "blank_ratio": round(float(blank_flags.mean()), 4),
        "blank_ranges": blank_ranges,
        "static_frame_count": int(static_flags.sum()),
        "static_ratio": round(float(static_flags.mean()), 4),
        "static_ranges": static_ranges,
        "transitions": transitions,
        "final_frame": {
            "time": round(float(times[-1]), 3),
            "mean": round(float(means[-1]), 3),
            "std": round(float(stds[-1]), 3),
        },
        "subtitle": subtitle,
        "warnings": warnings,
    }


def decode_video(video_path: Path) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    with av.open(str(video_path)) as container:
        stream = next((s for s in container.streams if s.type == "video"), None)
        if stream is None:
            raise RuntimeError(f"{video_path} has no video stream")
        guessed_fps = float(stream.average_rate) if stream.average_rate else 24.0
        for index, frame in enumerate(container.decode(stream)):
            image = frame.to_image().convert("RGB")
            thumb = image.copy()
            thumb.thumbnail((320, 180), Image.Resampling.LANCZOS)
            gray = image.convert("L").resize((160, 90), Image.Resampling.BILINEAR)
            time_value = frame.time if frame.time is not None else index / guessed_fps
            frames.append({
                "time": float(time_value),
                "gray": np.asarray(gray, dtype=np.float32),
                "thumb": thumb,
                "size": image.size,
            })
    return frames


def frame_diffs(grays: np.ndarray) -> np.ndarray:
    if len(grays) < 2:
        return np.array([], dtype=np.float32)
    delta = grays[1:] - grays[:-1]
    return np.sqrt(np.mean(delta * delta, axis=(1, 2)))


def estimate_frame_period(times: np.ndarray) -> float:
    if len(times) < 2:
        return 1 / 24
    deltas = np.diff(times)
    deltas = deltas[deltas > 0]
    return float(np.median(deltas)) if len(deltas) else 1 / 24


def flag_ranges(flags: np.ndarray, times: np.ndarray, min_duration: float) -> list[dict[str, float]]:
    if len(flags) == 0:
        return []
    period = estimate_frame_period(times)
    ranges: list[dict[str, float]] = []
    start: int | None = None
    for i, flag in enumerate(flags):
        if flag and start is None:
            start = i
        if (not flag or i == len(flags) - 1) and start is not None:
            end_index = i if flag and i == len(flags) - 1 else i - 1
            start_t = float(times[start])
            end_t = float(times[end_index] + period)
            duration = max(0.0, end_t - start_t)
            if duration >= min_duration:
                ranges.append({
                    "start": round(start_t, 3),
                    "end": round(end_t, 3),
                    "duration": round(duration, 3),
                })
            start = None
    return ranges


def top_transitions(diffs: np.ndarray, times: np.ndarray, limit: int = 8) -> list[dict[str, float]]:
    if len(diffs) == 0:
        return []
    order = np.argsort(diffs)[::-1][:limit]
    transitions = [
        {"time": round(float(times[int(i) + 1]), 3), "rms": round(float(diffs[int(i)]), 3)}
        for i in order
    ]
    return sorted(transitions, key=lambda item: item["time"])


def write_contact_sheet(frames: list[dict[str, Any]], path: Path, case_id: str) -> None:
    sample_points = [0.0, 0.10, 0.25, 0.40, 0.55, 0.70, 0.85, 1.0]
    picks = [min(len(frames) - 1, max(0, round(p * (len(frames) - 1)))) for p in sample_points]
    thumbs = [frames[i]["thumb"].copy() for i in picks]
    cell_w, cell_h, label_h = 320, 180, 28
    cols = 4
    rows = 2
    sheet = Image.new("RGB", (cols * cell_w, rows * (cell_h + label_h)), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for n, (idx, thumb) in enumerate(zip(picks, thumbs, strict=True)):
        col = n % cols
        row = n // cols
        x = col * cell_w
        y = row * (cell_h + label_h)
        frame_canvas = Image.new("RGB", (cell_w, cell_h), (18, 20, 24))
        ox = (cell_w - thumb.width) // 2
        oy = (cell_h - thumb.height) // 2
        frame_canvas.paste(thumb, (ox, oy))
        sheet.paste(frame_canvas, (x, y))
        label = f"{case_id}  t={frames[idx]['time']:.2f}s  #{idx}"
        draw.text((x + 8, y + cell_h + 7), label[:58], fill=(20, 24, 32), font=font)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, quality=86, optimize=True)


SRT_RE = re.compile(
    r"(\d+)\s*\n"
    r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n"
    r"(.*?)(?=\n\s*\d+\s*\n\d{2}:|\Z)",
    re.DOTALL,
)


def audit_subtitles(path: Path, duration: float, transitions: list[dict[str, float]]) -> dict[str, Any] | None:
    if not path.exists():
        return {"path": public_path(path), "cue_count": 0, "warnings": ["srt path missing"]}
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    cues = []
    transition_times = [t["time"] for t in transitions]
    warnings: list[str] = []
    for match in SRT_RE.finditer(text):
        start = parse_srt_time(match.group(2))
        end = parse_srt_time(match.group(3))
        body = " ".join(match.group(4).split())
        nearest_delta = min((abs(start - t) for t in transition_times), default=None)
        if end > duration + 0.5:
            warnings.append(f"cue {match.group(1)} ends after video")
        if end <= start:
            warnings.append(f"cue {match.group(1)} has non-positive duration")
        cues.append({
            "index": int(match.group(1)),
            "start": round(start, 3),
            "end": round(end, 3),
            "duration": round(max(0.0, end - start), 3),
            "nearest_transition_delta": round(nearest_delta, 3) if nearest_delta is not None else None,
            "text_sample": body[:90],
        })
    if text and not cues:
        warnings.append("srt file had text but no parsed cues")
    return {
        "path": public_path(path),
        "cue_count": len(cues),
        "cues": cues,
        "warnings": warnings,
    }


def public_artifact_paths(artifact: dict[str, Any]) -> dict[str, Any]:
    public = dict(artifact)
    for key in ("video_path", "srt_path"):
        value = public.get(key)
        if value:
            public[key] = public_path(Path(str(value)))
    return public


def public_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return f"<render-cache>/{path.name}"


def parse_srt_time(value: str) -> float:
    hms, ms = value.split(",", 1)
    hours, minutes, seconds = (int(part) for part in hms.split(":"))
    return hours * 3600 + minutes * 60 + seconds + int(ms) / 1000


def compare_report(compare_dir: Path, report: dict[str, Any]) -> dict[str, Any] | None:
    baseline = compare_dir / "summary.json"
    if not baseline.exists():
        return None
    previous = json.loads(baseline.read_text(encoding="utf-8"))
    by_id = {case["id"]: case for case in previous.get("cases", []) if isinstance(case, dict)}
    deltas = []
    for case in report["cases"]:
        old = by_id.get(case["id"])
        if not old or "metrics" not in case or "metrics" not in old:
            continue
        new_metrics = case["metrics"]
        old_metrics = old["metrics"]
        deltas.append({
            "id": case["id"],
            "duration_delta": round(new_metrics["duration"] - old_metrics["duration"], 3),
            "frame_count_delta": int(new_metrics["frame_count"]) - int(old_metrics["frame_count"]),
            "blank_ratio_delta": round(new_metrics["blank_ratio"] - old_metrics["blank_ratio"], 4),
            "static_ratio_delta": round(new_metrics["static_ratio"] - old_metrics["static_ratio"], 4),
        })
    return {"baseline": str(baseline), "deltas": deltas}


def write_outputs(out_dir: Path, report: dict[str, Any]) -> None:
    (out_dir / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8", newline="\n")
    write_metrics_csv(out_dir / "metrics.csv", report)
    (out_dir / "summary.md").write_text(render_summary_md(report), encoding="utf-8", newline="\n")


def write_metrics_csv(path: Path, report: dict[str, Any]) -> None:
    fields = [
        "id",
        "kind",
        "status",
        "duration",
        "fps",
        "frame_count",
        "blank_ratio",
        "static_ratio",
        "warning_count",
        "contact_sheet",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for case in report["cases"]:
            metrics = case.get("metrics", {})
            writer.writerow({
                "id": case.get("id", ""),
                "kind": case.get("kind", ""),
                "status": case.get("status", ""),
                "duration": metrics.get("duration", ""),
                "fps": metrics.get("fps", ""),
                "frame_count": metrics.get("frame_count", ""),
                "blank_ratio": metrics.get("blank_ratio", ""),
                "static_ratio": metrics.get("static_ratio", ""),
                "warning_count": len(metrics.get("warnings", [])) if metrics else "",
                "contact_sheet": metrics.get("contact_sheet", ""),
            })


def render_summary_md(report: dict[str, Any]) -> str:
    lines = [
        "# AetherLab Visual Regression Report",
        "",
        f"- Started: {report.get('started_at', '')}",
        f"- Finished: {report.get('finished_at', '')}",
        f"- Quality: {report.get('quality', '')}",
        "",
        "| Case | Kind | Status | Duration | FPS | Frames | Blank | Static | Warnings |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for case in report["cases"]:
        metrics = case.get("metrics", {})
        warnings = "; ".join(metrics.get("warnings", [])) if metrics else case.get("error", "")
        lines.append(
            "| {id} | {kind} | {status} | {duration} | {fps} | {frames} | {blank} | {static} | {warnings} |".format(
                id=case.get("id", ""),
                kind=case.get("kind", ""),
                status=case.get("status", ""),
                duration=metrics.get("duration", ""),
                fps=metrics.get("fps", ""),
                frames=metrics.get("frame_count", ""),
                blank=metrics.get("blank_ratio", ""),
                static=metrics.get("static_ratio", ""),
                warnings=warnings.replace("|", "\\|"),
            )
        )
    if report.get("compare"):
        lines.extend(["", "## Comparison", ""])
        for delta in report["compare"].get("deltas", []):
            lines.append(
                f"- {delta['id']}: duration {delta['duration_delta']:+.3f}s, "
                f"frames {delta['frame_count_delta']:+d}, blank {delta['blank_ratio_delta']:+.4f}, "
                f"static {delta['static_ratio_delta']:+.4f}"
            )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
