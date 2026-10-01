"""Local/Cloud parity check for a curated physics component plus text and MathTex.

The tool uses isolated analysis data directories and never changes saved app
settings. The Cloud leg only runs when explicitly selected on the command line.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import time
from dataclasses import replace
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from aetherlab.core.console import configure_utf8_stdio
from aetherlab.core.models import SceneBundle
from aetherlab.core.settings import load_settings
from aetherlab.services.code_safety import validate_code_safety
from aetherlab.services.manim_runtime import ManimRuntime
from aetherlab.services.scene_components import field_lines
from aetherlab.services.scene_validation import (
    check_latex_strings,
    repair_text_mode_math,
    validate_scene,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".analysis" / "manim-parity-20260925"
FPS = 30
QUALITY = "l"
DURATION_S = 9.2


def scene_source() -> tuple[str, list[str]]:
    solver = SimpleNamespace(
        summary="Electric dipole field lines",
        variables={"separation": 2.4},
    )
    code = field_lines.build("AetherLabParityScene", solver)
    if not code:
        raise RuntimeError("Curated field-lines component did not produce a scene.")
    construct = "    def construct(self):\n"
    if code.count(construct) != 1:
        raise RuntimeError("Expected one construct() in the component scene.")
    intro = '''\
        intro_title = Text("CURATED FIELD LINES", font_size=34, color=WHITE)
        intro_equation = Tex(r"\\mathbf{E}(\\mathbf{r}) = \\sum_i \\frac{k q_i}{r_i^2}")
        intro_equation.scale(0.55)
        intro_equation.next_to(intro_title, DOWN, buff=0.45)
        self.play(Write(intro_title), FadeIn(intro_equation), run_time=0.8)
        self.wait(0.5)
        self.play(FadeOut(intro_title), FadeOut(intro_equation), run_time=0.5)
'''
    code = code.replace(construct, construct + intro, 1)
    code, repair_notes = repair_text_mode_math(code)
    if not repair_notes or "intro_equation = MathTex(" not in code:
        raise RuntimeError("Text-mode math repair did not promote the golden equation.")
    issues = check_latex_strings(code)
    if issues:
        raise ValueError("Golden MathTex failed structural validation: " + "; ".join(issues))
    safe, safety_issues = validate_code_safety(code)
    lint_ok, lint_issues = validate_scene(code, require_motion=True)
    if not safe or not lint_ok:
        raise ValueError(
            "Golden scene failed its pre-render gates: "
            + "; ".join((safety_issues + lint_issues)[:8])
        )
    compile(code, "<aetherlab-manim-parity>", "exec")
    return code, repair_notes


def _isolated_settings(backend: str):
    base = load_settings()
    data_dir = OUT / backend / "app_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return replace(
        base,
        data_dir=data_dir,
        cache_path=data_dir / "cache.sqlite3",
        chroma_path=data_dir / "chroma",
        render_mode=backend,
        narration_enabled=False,
        vision_model=None,
        visual_critic_max_passes=0,
        auto_tournament=False,
        scene_candidates=1,
    )


async def render(backend: str) -> dict[str, Any]:
    code, repair_notes = scene_source()
    settings = _isolated_settings(backend)
    run_dir = OUT / backend
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "scene.py").write_text(code, encoding="utf-8", newline="\n")
    bundle = SceneBundle(
        class_name="AetherLabParityScene",
        code=code,
        engine="manim-community",
        status="compiled",
        diagnostics=[],
        storyboard={"timeline_duration_s": DURATION_S},
    )
    runtime = ManimRuntime(settings)
    started = time.monotonic()
    if backend == "local":
        result = await asyncio.to_thread(runtime.render_scene, bundle, settings, QUALITY)
    else:
        result = await runtime.render_scene_with_repair(
            bundle,
            settings,
            quality=QUALITY,
            max_repairs=0,
            max_revisions=0,
            brief="Render the curated electric dipole field-line parity scene.",
            progress=lambda message: print(f"[cloud] {message}", flush=True),
        )
    source_video = Path(result.video_path) if result.video_path else None
    video_exists = bool(source_video and source_video.is_file() and source_video.stat().st_size)
    saved_video = run_dir / "render.mp4"
    if video_exists:
        shutil.copy2(source_video, saved_video)
    record: dict[str, Any] = {
        "schema": "aetherlab.manim_parity_smoke.v1",
        "backend": backend,
        "status": result.status,
        "video_exists": video_exists,
        "video": str(saved_video.relative_to(ROOT)) if video_exists else "",
        "bytes": saved_video.stat().st_size if video_exists else 0,
        "local_manim_version": version("manim"),
        "renderer": "cairo",
        "quality": QUALITY,
        "target_duration_s": DURATION_S,
        "fps_target": FPS,
        "render_wall_seconds": round(time.monotonic() - started, 3),
        "text_mode_math_repairs": repair_notes,
        "diagnostics": result.diagnostics[-8:],
    }
    if backend == "cloud":
        from aetherlab.services.render_ledger import RenderJobLedger

        rows = RenderJobLedger(settings.data_dir / "render_ledger.json").list()
        row = next((item for item in reversed(rows) if item.get("status") == "rendered"), {})
        metrics = row.get("metrics", {}) if isinstance(row, dict) else {}
        record["cloud_render_id"] = row.get("job_id", "") if isinstance(row, dict) else ""
        record["cloud_metrics"] = {
            key: metrics[key]
            for key in (
                "backend", "queue_seconds", "worker_seconds", "render_wall_seconds",
                "peak_rss_mb", "retry_count", "manim_version",
            )
            if isinstance(metrics, dict) and key in metrics
        }
    (run_dir / "result.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(record, indent=2), flush=True)
    return record


def _video_info(path: Path) -> tuple[dict[str, Any], dict[float, Any]]:
    import av

    targets = [1.5, 2.8, 4.0, 7.0, 8.5]
    frames: dict[float, Any] = {}
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        fps = float(stream.average_rate or FPS)
        duration = (
            float(stream.duration * stream.time_base)
            if stream.duration and stream.time_base
            else 0.0
        )
        frame_count = 0
        pending = list(targets)
        for frame in container.decode(stream):
            frame_count += 1
            timestamp = (
                float(frame.pts * stream.time_base)
                if frame.pts is not None else (frame_count - 1) / fps
            )
            while pending and timestamp >= pending[0]:
                frames[pending.pop(0)] = frame.to_ndarray(format="rgb24")
        return {
            "duration_s": round(duration, 4),
            "fps": fps,
            "frame_count": frame_count,
            "width": stream.codec_context.width,
            "height": stream.codec_context.height,
        }, frames


def compare() -> dict[str, Any]:
    import numpy as np
    from PIL import Image, ImageDraw

    local_path, cloud_path = OUT / "local" / "render.mp4", OUT / "cloud" / "render.mp4"
    if not local_path.is_file() or not cloud_path.is_file():
        raise FileNotFoundError("Render both parity legs before comparison.")
    local_info, local_frames = _video_info(local_path)
    cloud_info, cloud_frames = _video_info(cloud_path)
    local_record = json.loads((OUT / "local" / "result.json").read_text(encoding="utf-8"))
    cloud_record = json.loads((OUT / "cloud" / "result.json").read_text(encoding="utf-8"))
    rows, tiles = [], []
    for timestamp in sorted(local_frames.keys() & cloud_frames.keys()):
        local = Image.fromarray(local_frames[timestamp]).convert("RGB")
        cloud = Image.fromarray(cloud_frames[timestamp]).convert("RGB")
        same_dimensions = local.size == cloud.size
        if cloud.size != local.size:
            cloud = cloud.resize(local.size, Image.Resampling.LANCZOS)
        delta = np.abs(np.asarray(local, dtype=np.int16) - np.asarray(cloud, dtype=np.int16))
        rows.append({
            "time_s": timestamp,
            "mean_absolute_pixel_error": round(float(delta.mean()), 4),
            "pixels_with_channel_delta_le_16_pct": round(
                float((delta <= 16).all(axis=2).mean() * 100), 3
            ),
            "same_dimensions": same_dimensions,
        })
        local.thumbnail((480, 270))
        cloud.thumbnail((480, 270))
        tile = Image.new("RGB", (980, 300), "#101521")
        tile.paste(local, (5, 25))
        tile.paste(cloud, (495, 25))
        draw = ImageDraw.Draw(tile)
        draw.text((8, 5), f"Local  t={timestamp:.1f}s", fill="white")
        draw.text((498, 5), f"Cloud  t={timestamp:.1f}s", fill="white")
        tiles.append(tile)
    sheet_path = OUT / "comparison.png"
    sheet = Image.new("RGB", (980, max(1, len(tiles)) * 300), "#101521")
    for index, tile in enumerate(tiles):
        sheet.paste(tile, (0, index * 300))
    sheet.save(sheet_path)
    same_duration = abs(local_info["duration_s"] - cloud_info["duration_s"]) <= 0.1
    same_fps = abs(local_info["fps"] - cloud_info["fps"]) < 0.01
    same_dimensions = (
        local_info["width"] == cloud_info["width"]
        and local_info["height"] == cloud_info["height"]
    )
    mean_pixel_error = (
        float(np.mean([row["mean_absolute_pixel_error"] for row in rows]))
        if rows else float("inf")
    )
    min_close_pixels = min(
        (row["pixels_with_channel_delta_le_16_pct"] for row in rows),
        default=0.0,
    )
    visual_parity = mean_pixel_error <= 2.0 and min_close_pixels >= 97.5
    local_manim = str(local_record.get("local_manim_version", ""))
    cloud_metrics = cloud_record.get("cloud_runner_metrics") or cloud_record.get("cloud_metrics", {})
    cloud_manim = str(cloud_metrics.get("manim_version", "")) if isinstance(cloud_metrics, dict) else ""
    same_manim_version = local_manim == cloud_manim == "0.21.0"
    record = {
        "schema": "aetherlab.manim_parity_comparison.v1",
        "local": local_info,
        "cloud": cloud_info,
        "same_duration_s": same_duration,
        "same_fps": same_fps,
        "same_dimensions": same_dimensions,
        "local_manim_version": local_manim,
        "cloud_runner_manim_version": cloud_manim,
        "same_manim_version": same_manim_version,
        "visual_parity": visual_parity,
        "visual_parity_thresholds": {
            "mean_absolute_pixel_error_max": 2.0,
            "min_channel_delta_le_16_pct": 97.5,
        },
        "frame_comparisons": rows,
        "mean_absolute_pixel_error": round(mean_pixel_error, 4) if rows else None,
        "min_channel_delta_le_16_pct": round(min_close_pixels, 3) if rows else None,
        "comparison_sheet": str(sheet_path.relative_to(ROOT)),
    }
    (OUT / "comparison.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(record, indent=2))
    return record


def capture_cloud_runner_metrics() -> dict[str, Any]:
    """Refresh this golden job's runner metrics from its authoritative Actions log."""
    from aetherlab.services.render_backend import GitHubActionsClient, _parse_runner_metrics

    cloud_dir = OUT / "cloud"
    result_path = cloud_dir / "result.json"
    manifest_path = cloud_dir / "app_data" / "cloud_renders.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    job_id = str(result.get("cloud_render_id", ""))
    run_id = (manifest.get(job_id) or {}).get("run_id")
    if not job_id or not run_id:
        raise RuntimeError("Cloud render id/run id is missing from its manifest.")
    client = GitHubActionsClient.from_settings(load_settings())
    logs = client.download_run_logs(int(run_id))
    metrics = _parse_runner_metrics(logs)
    if metrics.get("manim_version") != "0.21.0":
        raise RuntimeError(
            f"Cloud runner Manim version could not be verified: {metrics!r}"
        )
    evidence = {
        "schema": "aetherlab.cloud_runner_metrics.v1",
        "job_id": job_id,
        "run_id": int(run_id),
        "runner_log_bytes": len(logs.encode("utf-8")),
        "metrics": metrics,
        "source": "GitHub Actions run log, parsed by _parse_runner_metrics",
    }
    evidence_path = cloud_dir / "runner-metrics.json"
    evidence_path.write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    result["cloud_runner_metrics"] = metrics
    result["cloud_runner_metrics_evidence"] = str(evidence_path.relative_to(ROOT))
    result_path.write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(evidence, indent=2))
    return evidence


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "backend", choices=("local", "cloud", "cloud-metrics", "compare")
    )
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.backend == "compare":
        report = compare()
        return 0 if all((
            report["same_duration_s"], report["same_fps"],
            report["same_dimensions"], report["same_manim_version"],
            report["visual_parity"],
        )) else 1
    if args.backend == "cloud-metrics":
        capture_cloud_runner_metrics()
        return 0
    record = asyncio.run(render(args.backend))
    return 0 if record["status"] == "rendered" and record["video_exists"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
