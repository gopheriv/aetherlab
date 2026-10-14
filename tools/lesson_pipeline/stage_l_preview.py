"""Stage L part 2: cloud previews (ru, quality m) + first/key/final frames.

Usage: python .qwen/tmp/stage_l_preview.py [BlockB0 ...]  (default: all 8)
Saves output/stage_l_preview/<Class>.mp4, params.json, frames/<Class>_t<SS>.png.
Skips classes whose mp4 already exists (re-render by deleting the file).
"""

import asyncio
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
OUT = ROOT / "output" / "stage_l_preview"
QUALITY = "m"
CLASS_NAMES = [f"BlockB{i}" for i in range(8)]
# first / key-transformation / final moments per block (block-local seconds)
FRAMES = {"BlockB0": [2, 14, 19], "BlockB1": [2, 16, 49],
          "BlockB2": [2, 20, 39], "BlockB3": [2, 38, 49],
          "BlockB4": [2, 21, 39], "BlockB5": [2, 12, 29],
          "BlockB6": [2, 16, 29], "BlockB7": [2, 20, 39]}


# UTF-8 stdio for redirected Cyrillic output (F133).
try:
    from aetherlab.core.console import configure_utf8_stdio  # noqa: E402
    configure_utf8_stdio()
except ImportError:
    pass

def stream_facts(path: Path) -> dict:
    import av

    facts: dict = {"path": str(path), "bytes": path.stat().st_size}
    with av.open(str(path)) as container:
        video = next((s for s in container.streams if s.type == "video"), None)
        assert video is not None, "no video stream"
        facts["video_streams"] = sum(1 for s in container.streams if s.type == "video")
        facts["width"] = video.width
        facts["height"] = video.height
        facts["fps"] = float(video.average_rate) if video.average_rate else 0.0
        if video.duration and video.time_base:
            facts["duration_s"] = float(video.duration * video.time_base)
        elif container.duration:
            facts["duration_s"] = float(container.duration) / 1_000_000
        else:
            facts["duration_s"] = 0.0
        facts["codec"] = video.codec_context.name if video.codec_context else ""
    return facts


def extract_frames(video: Path, class_name: str) -> list[str]:
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    frames_dir = OUT / "frames"
    frames_dir.mkdir(exist_ok=True)
    names = []
    for t in FRAMES[class_name]:
        dst = frames_dir / f"{class_name}_t{t:02d}.png"
        cmd = [ffmpeg, "-y", "-ss", str(t), "-i", str(video),
               "-frames:v", "1", str(dst)]
        proc = subprocess.run(cmd, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=120)
        assert proc.returncode == 0, f"ffmpeg t={t}: {proc.stderr[-500:]}"
        assert dst.is_file() and dst.stat().st_size > 0, dst.name
        names.append(dst.name)
    return names


async def render_one(backend, code: str, class_name: str, settings, timeout: int) -> dict:
    from aetherlab.core.models import SceneBundle

    scene = SceneBundle(class_name=class_name, code=code,
                        engine="manim", status="compiled")

    def say(message: str) -> None:
        print(f"[{time.strftime('%H:%M:%S')}] {class_name}: {message}", flush=True)

    t0 = time.monotonic()
    result = await backend.render(
        scene, quality=QUALITY, settings=settings, timeout=timeout, progress=say)
    wall = time.monotonic() - t0
    print(f"{class_name}: status={result.status} wall={wall:.0f}s", flush=True)
    for diag in result.diagnostics[-4:]:
        print(f"{class_name} diag: {diag[:300]}", flush=True)
    assert result.status == "rendered" and result.video_path, \
        f"{class_name} failed: {result.failure_kind}"
    video = Path(result.video_path)
    dst = OUT / f"{class_name}.mp4"
    shutil.copy2(video, dst)
    facts = stream_facts(dst)
    facts.update({"status": result.status, "wall_s": round(wall, 1),
                  "frames": extract_frames(dst, class_name)})
    return facts


async def main(classes: list[str]) -> None:
    from aetherlab.core.settings import load_settings
    from aetherlab.services.render_backend import (
        CloudRenderBackend, render_timeout_for)

    settings = load_settings()
    assert str(getattr(settings, "render_mode", "")).lower() == "cloud"
    backend = CloudRenderBackend(settings)
    ok, reason = backend.available()
    print(f"backend available={ok} ({reason})", flush=True)
    assert ok, reason

    code = (ROOT / "output" / "stage_l_scenes" / "lesson_ru.py").read_text(encoding="utf-8")
    timeout = render_timeout_for(code, QUALITY, settings)
    print(f"quality={QUALITY} timeout={timeout}s classes={classes}", flush=True)
    OUT.mkdir(exist_ok=True)

    params_path = OUT / "params.json"
    params = json.loads(params_path.read_text(encoding="utf-8")) if params_path.exists() else {}
    for class_name in classes:
        if (OUT / f"{class_name}.mp4").is_file() and class_name in params:
            print(f"{class_name}: cached, skipping", flush=True)
            continue
        params[class_name] = await render_one(backend, code, class_name, settings, timeout)
        params_path.write_text(json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"done: {sorted(params)} -> {OUT.resolve()}", flush=True)


if __name__ == "__main__":
    wanted = sys.argv[1:] or CLASS_NAMES
    assert set(wanted) <= set(CLASS_NAMES), wanted
    asyncio.run(main(wanted))
