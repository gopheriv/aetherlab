"""Compare installed Manim 0.21.0 with an extracted 0.20.1 wheel.

The benchmark renders one fixed AetherLab scene with Cairo, cache disabled,
and a shared Python/dependency environment. The older wheel is selected only
through PYTHONPATH for its subprocesses; this tool never installs packages or
reads/writes AetherLab settings. MP4s, logs, and a JSON report are retained in
an isolated .analysis directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import time
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw

from aetherlab.core.console import configure_utf8_stdio

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / ".analysis" / "manim-version-ab-20261002"
LEGACY_PACKAGE = BASE / "legacy-package"
SCENE = ROOT / ".analysis" / "manim-parity-20260925" / "local" / "scene.py"
EXPECTED = {"0.20.1": LEGACY_PACKAGE, "0.21.0": None}
FPS = 30
RESOLUTION = "854,480"
SEED = 20261002
QUALITY = "l"


def _environment(version_name: str) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    if EXPECTED[version_name] is not None:
        env["PYTHONPATH"] = str(EXPECTED[version_name])
    return env


def _preflight() -> dict[str, dict[str, str]]:
    if not SCENE.is_file():
        raise FileNotFoundError(f"Benchmark scene is missing: {SCENE}")
    if not LEGACY_PACKAGE.is_dir():
        raise FileNotFoundError(f"Extracted legacy Manim package is missing: {LEGACY_PACKAGE}")
    native_version = version("manim")
    if native_version != "0.21.0":
        raise RuntimeError(f"Expected installed Manim 0.21.0; found {native_version}")

    evidence: dict[str, dict[str, str]] = {}
    for version_name in EXPECTED:
        command = [
            sys.executable,
            "-c",
            "import manim, sys; print(manim.__version__); print(manim.__file__); print(sys.version.split()[0])",
        ]
        proc = subprocess.run(
            command,
            cwd=ROOT,
            env=_environment(version_name),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        if proc.returncode or len(lines) < 3 or lines[0] != version_name:
            raise RuntimeError(
                f"Manim {version_name} preflight failed ({proc.returncode}): "
                f"{(proc.stderr or proc.stdout)[-1200:]}"
            )
        module_path = Path(lines[1]).resolve()
        if version_name == "0.20.1" and LEGACY_PACKAGE.resolve() not in module_path.parents:
            raise RuntimeError(f"Legacy import came from an unexpected path: {module_path}")
        evidence[version_name] = {
            "version": lines[0],
            "module_path": str(module_path),
            "python_version": lines[2],
        }
    return evidence


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _video_path(run_dir: Path) -> Path:
    matches = [
        item
        for item in (run_dir / "media").rglob("*.mp4")
        if "partial_movie_files" not in item.parts
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one rendered MP4 under {run_dir}; found {matches}")
    return matches[0]


def _video_metadata(video: Path) -> dict[str, Any]:
    import imageio.v2 as imageio

    reader = imageio.get_reader(str(video), format="ffmpeg")
    try:
        meta = reader.get_meta_data()
        return {
            "duration_seconds": round(float(meta["duration"]), 4),
            "fps": float(meta["fps"]),
            "frame_count": int(reader.count_frames()),
            "dimensions": [int(value) for value in meta["size"]],
        }
    finally:
        reader.close()


def _sample_frames(video: Path, seconds: list[float]) -> list[Image.Image]:
    import imageio.v2 as imageio

    reader = imageio.get_reader(str(video), format="ffmpeg")
    try:
        meta = reader.get_meta_data()
        fps = float(meta["fps"])
        count = reader.count_frames()
        return [
            Image.fromarray(reader.get_data(min(max(round(at * fps), 0), count - 1))).convert("RGB")
            for at in seconds
        ]
    finally:
        reader.close()


def _compare(videos: dict[str, Path], out_dir: Path) -> dict[str, Any]:
    metadata = {name: _video_metadata(path) for name, path in videos.items()}
    duration = min(item["duration_seconds"] for item in metadata.values())
    sample_seconds = [round(duration * portion, 3) for portion in (0.08, 0.28, 0.5, 0.72, 0.92)]
    frames = {
        name: _sample_frames(path, sample_seconds)
        for name, path in videos.items()
    }
    rows = []
    tiles = []
    old_label, new_label = "Manim 0.20.1", "Manim 0.21.0"
    for at, old_frame, new_frame in zip(sample_seconds, frames["0.20.1"], frames["0.21.0"]):
        same_size = old_frame.size == new_frame.size
        compare_frame = new_frame if same_size else new_frame.resize(old_frame.size)
        diff = ImageChops.difference(old_frame, compare_frame)
        histogram = diff.histogram()
        total_channels = max(old_frame.width * old_frame.height * 3, 1)
        close_channels = sum(sum(histogram[channel * 256 : channel * 256 + 17]) for channel in range(3))
        # ImageStat computes a per-channel mean; average the channels for a single pixel MAE.
        from PIL import ImageStat

        mean_absolute_error = statistics.fmean(ImageStat.Stat(diff).mean)
        rows.append({
            "time_seconds": at,
            "mean_absolute_pixel_error": round(mean_absolute_error, 5),
            "channels_with_delta_at_most_16_pct": round(100 * close_channels / total_channels, 4),
            "same_dimensions": same_size,
            "dimensions": list(old_frame.size),
        })
        label_height = 24
        tile = Image.new("RGB", (old_frame.width * 2, old_frame.height + label_height), "white")
        tile.paste(old_frame, (0, label_height))
        tile.paste(compare_frame, (old_frame.width, label_height))
        draw = ImageDraw.Draw(tile)
        draw.text((8, 5), f"{old_label}  t={at:.2f}s", fill="black")
        draw.text((old_frame.width + 8, 5), f"{new_label}  t={at:.2f}s", fill="black")
        tiles.append(tile)
    sheet = Image.new("RGB", (tiles[0].width, sum(tile.height for tile in tiles)), "white")
    y = 0
    for tile in tiles:
        sheet.paste(tile, (0, y))
        y += tile.height
    sheet_path = out_dir / "comparison.png"
    sheet.save(sheet_path)
    return {
        "video_metadata": metadata,
        "sample_frames": rows,
        "mean_sampled_mae": round(statistics.fmean(row["mean_absolute_pixel_error"] for row in rows), 5),
        "mean_channels_with_delta_at_most_16_pct": round(
            statistics.fmean(row["channels_with_delta_at_most_16_pct"] for row in rows), 4
        ),
        "comparison_sheet": str(sheet_path.relative_to(ROOT)),
    }


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3, help="Number of renders per version (default: 3)")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")

    versions = _preflight()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = BASE / f"benchmark-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)
    report_path = out_dir / "report.json"
    scene_hash = hashlib.sha256(SCENE.read_bytes()).hexdigest()
    report: dict[str, Any] = {
        "schema": "aetherlab.manim_version_benchmark.v1",
        "created_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "manim_versions": versions,
        "scene": str(SCENE.relative_to(ROOT)),
        "scene_sha256": scene_hash,
        "method": {
            "renderer": "cairo",
            "quality": QUALITY,
            "resolution": RESOLUTION,
            "fps": FPS,
            "seed": SEED,
            "cache": "disabled",
            "repeats_per_version": args.repeats,
            "ordering": "alternating; first version alternates by pair",
            "wall_clock_scope": "fresh Python/Manim subprocess through completed MP4; excludes inspection and artifact copying",
            "environment": "same Python interpreter and installed dependencies; only Manim 0.20.1 package is prepended through PYTHONPATH for legacy runs",
        },
        "runs": [],
        "summary": {},
    }
    _write_report(report_path, report)
    all_videos: dict[str, Path] = {}

    for pair in range(args.repeats):
        order = ["0.20.1", "0.21.0"] if pair % 2 == 0 else ["0.21.0", "0.20.1"]
        for version_name in order:
            run_dir = out_dir / f"run-{pair + 1:02d}" / version_name
            media_dir = run_dir / "media"
            run_dir.mkdir(parents=True)
            command = [
                sys.executable,
                "-m", "manim", "render",
                "-q", QUALITY,
                "--fps", str(FPS),
                "--resolution", RESOLUTION,
                "--seed", str(SEED),
                "--renderer", "cairo",
                "--disable_caching",
                "--media_dir", str(media_dir),
                str(SCENE),
                "AetherLabParityScene",
            ]
            started = time.perf_counter()
            proc = subprocess.run(
                command,
                cwd=ROOT,
                env=_environment(version_name),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            wall_seconds = time.perf_counter() - started
            log_path = run_dir / "render.log"
            log_path.write_text(
                proc.stdout + ("\n--- STDERR ---\n" if proc.stderr else "") + proc.stderr,
                encoding="utf-8",
            )
            entry: dict[str, Any] = {
                "pair": pair + 1,
                "version": version_name,
                "wall_seconds": round(wall_seconds, 3),
                "return_code": proc.returncode,
                "log": str(log_path.relative_to(ROOT)),
            }
            if proc.returncode == 0:
                try:
                    source_video = _video_path(run_dir)
                    saved_video = run_dir / "render.mp4"
                    shutil.copy2(source_video, saved_video)
                    entry.update({
                        "status": "rendered",
                        "video": str(saved_video.relative_to(ROOT)),
                        "video_bytes": saved_video.stat().st_size,
                        "video_sha256": hashlib.sha256(saved_video.read_bytes()).hexdigest(),
                        "metadata": _video_metadata(saved_video),
                    })
                    all_videos[version_name] = saved_video
                except Exception as exc:  # preserve an actionable partial report
                    entry.update({"status": "artifact_error", "error": f"{type(exc).__name__}: {exc}"})
            else:
                entry.update({
                    "status": "render_failed",
                    "error_tail": (proc.stderr or proc.stdout)[-2500:],
                })
            report["runs"].append(entry)
            _write_report(report_path, report)
            print(
                f"{version_name} pair {pair + 1}/{args.repeats}: "
                f"{entry['status']} in {wall_seconds:.3f}s",
                flush=True,
            )

    by_version = {
        name: [row["wall_seconds"] for row in report["runs"] if row["version"] == name and row["status"] == "rendered"]
        for name in EXPECTED
    }
    summary: dict[str, Any] = {
        name: {
            "successful_runs": len(times),
            "wall_seconds": times,
            "median_wall_seconds": round(statistics.median(times), 3) if times else None,
        }
        for name, times in by_version.items()
    }
    old_median = summary["0.20.1"]["median_wall_seconds"]
    new_median = summary["0.21.0"]["median_wall_seconds"]
    if old_median is not None and new_median is not None:
        summary["0.21.0_vs_0.20.1"] = {
            "speedup_factor": round(old_median / new_median, 4) if new_median else None,
            "wall_time_reduction_pct": round(100 * (old_median - new_median) / old_median, 2) if old_median else None,
        }
    report["summary"] = summary
    if len(all_videos) == 2 and all(summary[name]["successful_runs"] == args.repeats for name in EXPECTED):
        report["visual_comparison"] = _compare(all_videos, out_dir)
    _write_report(report_path, report)
    print(f"Report: {report_path.relative_to(ROOT)}", flush=True)
    return 0 if all(summary[name]["successful_runs"] == args.repeats for name in EXPECTED) else 1


if __name__ == "__main__":
    raise SystemExit(main())
