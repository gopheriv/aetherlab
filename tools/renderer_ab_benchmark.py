"""Compare Cairo and OpenGL on representative deterministic AetherLab scenes.

This is an opt-in local benchmark. It does not read or change app settings and
does not alter the Cloud renderer. Results are written under ``.analysis``.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageChops, ImageDraw

from aetherlab.core.console import configure_utf8_stdio

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".analysis" / f"opengl-ab-{datetime.now():%Y%m%d-%H%M%S}"
FPS = 30
QUALITY = "l"


def scenes() -> dict[str, str]:
    from aetherlab.services.scene_components import field_lines, fourier_epicycles, kinetic_theory

    definitions = {
        "field_lines": (
            field_lines.build,
            SimpleNamespace(
                summary="Electric dipole field lines",
                variables={"separation": 2.4},
            ),
        ),
        "kinetic_theory": (
            kinetic_theory.build,
            SimpleNamespace(
                summary="Kinetic theory of an ideal gas",
                variables={"particles": 40, "temperature": 550.0},
            ),
        ),
        "fourier_epicycles": (
            fourier_epicycles.build,
            SimpleNamespace(
                summary="Fourier series with rotating vectors",
                variables={"terms": 9},
            ),
        ),
    }
    result: dict[str, str] = {}
    for name, (builder, solver) in definitions.items():
        code = builder("AetherLabBenchmarkScene", solver)
        if not code:
            raise RuntimeError(f"Could not build representative scene: {name}")
        result[name] = code
    return result


def video_for(run_dir: Path, name: str) -> Path:
    matches = [
        path
        for path in (run_dir / "media" / "videos" / name).rglob("*.mp4")
        if "partial_movie_files" not in path.parts
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one MP4 for {name}; found {matches}")
    return matches[0]


def frame_at(video: Path, seconds: float) -> Image.Image:
    import imageio.v2 as imageio

    reader = imageio.get_reader(str(video), format="ffmpeg")
    try:
        meta = reader.get_meta_data()
        index = min(int(round(seconds * float(meta["fps"]))), reader.count_frames() - 1)
        return Image.fromarray(reader.get_data(max(index, 0))).convert("RGB")
    finally:
        reader.close()


def compare_frames(cairo: Path, opengl: Path) -> tuple[list[dict], list[Image.Image]]:
    import imageio.v2 as imageio

    cairo_reader = imageio.get_reader(str(cairo), format="ffmpeg")
    gl_reader = imageio.get_reader(str(opengl), format="ffmpeg")
    try:
        a_meta, b_meta = cairo_reader.get_meta_data(), gl_reader.get_meta_data()
        duration = min(float(a_meta["duration"]), float(b_meta["duration"]))
        times = sorted({min(0.5, duration / 4), duration / 3, duration * 2 / 3, max(0.0, duration - 0.5)})
        rows, tiles = [], []
        for at in times:
            ai = min(int(round(at * float(a_meta["fps"]))), cairo_reader.count_frames() - 1)
            bi = min(int(round(at * float(b_meta["fps"]))), gl_reader.count_frames() - 1)
            a = Image.fromarray(cairo_reader.get_data(max(ai, 0))).convert("RGB")
            b = Image.fromarray(gl_reader.get_data(max(bi, 0))).convert("RGB")
            same_size = a.size == b.size
            if not same_size:
                b_for_diff = b.resize(a.size)
            else:
                b_for_diff = b
            diff = ImageChops.difference(a, b_for_diff)
            pixels = list(diff.getdata())
            channel_values = [channel for pixel in pixels for channel in pixel]
            mae = statistics.fmean(channel_values) if channel_values else 0.0
            close_pct = 100.0 * sum(value <= 16 for value in channel_values) / max(len(channel_values), 1)
            rows.append({
                "time_s": round(at, 3),
                "mean_absolute_pixel_error": round(mae, 4),
                "pixels_with_channel_delta_le_16_pct": round(close_pct, 3),
                "same_dimensions": same_size,
                "dimensions": list(a.size),
            })
            label_height = 26
            tile = Image.new("RGB", (a.width * 2, a.height + label_height), "white")
            tile.paste(a, (0, label_height))
            tile.paste(b_for_diff, (a.width, label_height))
            draw = ImageDraw.Draw(tile)
            draw.text((8, 6), f"Cairo  t={at:.2f}s", fill="black")
            draw.text((a.width + 8, 6), f"OpenGL  t={at:.2f}s", fill="black")
            tiles.append(tile)
        return rows, tiles
    finally:
        cairo_reader.close()
        gl_reader.close()


def main() -> int:
    configure_utf8_stdio()
    OUT.mkdir(parents=True, exist_ok=False)
    reports = {}
    for name, code in scenes().items():
        source = OUT / f"{name}.py"
        source.write_text(code, encoding="utf-8")
        seed = int(hashlib.sha256(code.encode("utf-8")).hexdigest()[:8], 16) % (2**31 - 1)
        # Alternate which renderer runs first to reduce order and warm-up bias.
        renderer_order = ["cairo", "opengl"] if len(reports) % 2 == 0 else ["opengl", "cairo"]
        runs = {}
        for renderer in renderer_order:
            run_dir = OUT / name / renderer
            media_dir = run_dir / "media"
            run_dir.mkdir(parents=True)
            command = [
                sys.executable, "-m", "manim", "render", f"-q{QUALITY}",
                "--fps", str(FPS), "--seed", str(seed), "--renderer", renderer,
            ]
            if renderer == "opengl":
                command.append("--write_to_movie")
            command.extend([
                "--disable_caching", "--media_dir", str(media_dir), str(source),
                "AetherLabBenchmarkScene",
            ])
            started = time.perf_counter()
            proc = subprocess.run(
                command, cwd=ROOT, text=True, encoding="utf-8", errors="replace",
                capture_output=True,
            )
            wall = time.perf_counter() - started
            (run_dir / "render.log").write_text(
                proc.stdout + ("\n--- STDERR ---\n" if proc.stderr else "") + proc.stderr,
                encoding="utf-8",
            )
            if proc.returncode:
                runs[renderer] = {
                    "status": "failed",
                    "return_code": proc.returncode,
                    "wall_seconds": round(wall, 3),
                    "error_tail": (proc.stderr or proc.stdout)[-1800:],
                    "log": str((run_dir / "render.log").relative_to(ROOT)),
                }
                continue
            video = video_for(run_dir, name)
            import imageio.v2 as imageio

            reader = imageio.get_reader(str(video), format="ffmpeg")
            try:
                metadata = reader.get_meta_data()
                frames = reader.count_frames()
            finally:
                reader.close()
            runs[renderer] = {
                "status": "rendered",
                "wall_seconds": round(wall, 3),
                "video_seconds": round(float(metadata["duration"]), 3),
                "fps": float(metadata["fps"]),
                "frame_count": int(frames),
                "dimensions": list(metadata["size"]),
                "video_bytes": video.stat().st_size,
                "video": str(video.relative_to(ROOT)),
                "log": str((run_dir / "render.log").relative_to(ROOT)),
            }
        frames = []
        sheet = None
        if all(runs[renderer]["status"] == "rendered" for renderer in ("cairo", "opengl")):
            cairo_video = ROOT / runs["cairo"]["video"]
            gl_video = ROOT / runs["opengl"]["video"]
            frames, tiles = compare_frames(cairo_video, gl_video)
            sheet = OUT / f"{name}_comparison.png"
            sheet_image = Image.new(
                "RGB", (tiles[0].width, sum(tile.height for tile in tiles)), "white"
            )
            y = 0
            for tile in tiles:
                sheet_image.paste(tile, (0, y))
                y += tile.height
            sheet_image.save(sheet)
        reports[name] = {
            "render_order": renderer_order,
            "runs": runs,
            "frames": frames,
            "mean_absolute_pixel_error": (
                round(statistics.fmean(row["mean_absolute_pixel_error"] for row in frames), 4)
                if frames else None
            ),
            "comparison_sheet": str(sheet.relative_to(ROOT)) if sheet else None,
        }
        print(
            f"Finished {name}: "
            f"Cairo {runs['cairo']['status']} ({runs['cairo']['wall_seconds']}s), "
            f"OpenGL {runs['opengl']['status']} ({runs['opengl']['wall_seconds']}s)",
            flush=True,
        )
    result = {
        "schema": "aetherlab.renderer_ab_benchmark.v1",
        "manim_version": "0.21.0",
        "quality": QUALITY,
        "fps_target": FPS,
        "renderers": ["cairo", "opengl"],
        "scenes": reports,
        "scope": "local Windows machine; timings include process startup and encoding",
        "conclusion": "Failures are included as compatibility findings; no renderer default is changed.",
    }
    (OUT / "report.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Report: {OUT / 'report.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
