"""Stage M parts 1-3: pin versions + final cloud renders (1080p30, 3 langs).

Usage: python tools/lesson_pipeline/stage_m_final.py [ru kk en] [BlockB0 ...]
  (default: all 24 segments)
Saves output/stage_m_final/{lang}/{Class}.mp4, params.json, versions.json,
frames/{lang}/{Class}_t<SS>.png. Resumes: skips segments whose mp4 exists
with a params entry. Up to 3 attempts per segment; failures are recorded
and the run continues (exit code 1 + FAILED list at the end).
"""

if __package__:
    from ._console import configure_utf8_stdio
else:
    from _console import configure_utf8_stdio

configure_utf8_stdio()


import asyncio
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
OUT = ROOT / "output" / "stage_m_final"
QUALITY = "h"
FPS = 30
LANGS = ["ru", "kk", "en"]
CLASS_NAMES = [f"BlockB{i}" for i in range(8)]
MAX_ATTEMPTS = 3
FRAMES = {"BlockB0": [2, 14, 19], "BlockB1": [2, 16, 49],
          "BlockB2": [2, 20, 39], "BlockB3": [2, 38, 49],
          "BlockB4": [2, 21, 39], "BlockB5": [2, 12, 29],
          "BlockB6": [2, 16, 29], "BlockB7": [2, 20, 39]}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_versions() -> dict:
    from aetherlab.services.render_backend import (
        CLOUD_WORKFLOW_VERSION,
        MANIM_VERSION_PIN,
    )

    clips = sorted((ROOT / "output" / "stage_k2_fragments" / "clips").glob("*.mp3"))
    assert len(clips) == 135, f"expected 135 clips, found {len(clips)}"
    clip_hash = hashlib.sha256(
        "".join(f"{p.name}:{sha256_file(p)}" for p in clips).encode()).hexdigest()
    versions = {
        "stage": "M-final",
        "quality": QUALITY,
        "fps": FPS,
        "langs": LANGS,
        "manim_pin": f"manim=={MANIM_VERSION_PIN}",
        "workflow_version": CLOUD_WORKFLOW_VERSION,
        "content": {
            "canonical": sha256_file(ROOT / "output" / "stage_f_content" / "canonical.json"),
            "shots": sha256_file(ROOT / "output" / "stage_j_scenario" / "shots.json"),
            "fragments": sha256_file(ROOT / "output" / "stage_k2_fragments" / "fragments.json"),
            "durations": sha256_file(ROOT / "output" / "stage_k2_fragments" / "durations.json"),
            "mux_plan": sha256_file(ROOT / "output" / "stage_k2_fragments" / "mux_plan.json"),
            "clips_sha256": clip_hash,
        },
        "scenes": {lang: sha256_file(ROOT / "output" / "stage_l_scenes" / f"lesson_{lang}.py")
                   for lang in LANGS},
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (OUT / "versions.json").write_text(json.dumps(versions, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    print(f"versions pinned: manim {versions['manim_pin']}, "
          f"workflow {versions['workflow_version']}, clips {clip_hash[:12]}", flush=True)
    return versions


def budgets() -> dict[str, float]:
    canon = json.loads((ROOT / "output" / "stage_f_content" / "canonical.json")
                       .read_text(encoding="utf-8"))
    return {f"Block{b['id']}": b["end_s"] - b["start_s"] for b in canon["blocks"]}


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


def extract_frames(video: Path, lang: str, class_name: str) -> list[str]:
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    frames_dir = OUT / "frames" / lang
    frames_dir.mkdir(parents=True, exist_ok=True)
    names = []
    for t in FRAMES[class_name]:
        dst = frames_dir / f"{class_name}_t{t:02d}.png"
        cmd = [ffmpeg, "-y", "-ss", str(t), "-i", str(video),
               "-frames:v", "1", str(dst)]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        assert proc.returncode == 0, f"ffmpeg t={t}: {proc.stderr[-500:]}"
        assert dst.is_file() and dst.stat().st_size > 0, dst.name
        names.append(dst.name)
    return names


async def render_one(backend, code: str, lang: str, class_name: str,
                     settings, timeout: int, budget: float) -> dict:
    from aetherlab.core.models import SceneBundle
    from aetherlab.services.render_backend import cloud_job_id, render_fps_for

    scene = SceneBundle(class_name=class_name, code=code,
                        engine="manim", status="compiled")
    job_id = cloud_job_id(scene, quality=QUALITY, fps=render_fps_for(code, QUALITY))
    last_error = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        def say(message: str, att: int = attempt) -> None:
            print(f"[{time.strftime('%H:%M:%S')}] {lang}/{class_name} "
                  f"a{att}: {message}", flush=True)

        t0 = time.monotonic()
        result = await backend.render(
            scene, quality=QUALITY, settings=settings, timeout=timeout, progress=say)
        wall = time.monotonic() - t0
        print(f"{lang}/{class_name} a{attempt}: status={result.status} "
              f"wall={wall:.0f}s job={job_id}", flush=True)
        for diag in result.diagnostics[-3:]:
            print(f"{lang}/{class_name} diag: {diag[:250]}", flush=True)
        if result.status == "rendered" and result.video_path:
            dst = OUT / lang / f"{class_name}.mp4"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(result.video_path, dst)
            facts = stream_facts(dst)
            drift = abs(facts["duration_s"] - budget)
            facts.update({"status": "rendered", "wall_s": round(wall, 1),
                          "job_id": job_id, "attempts": attempt,
                          "budget_s": budget, "drift_s": round(drift, 3),
                          "frames": extract_frames(dst, lang, class_name)})
            if drift >= 0.6:
                last_error = f"duration drift {drift:.2f}s"
                print(f"{lang}/{class_name}: {last_error}, retrying", flush=True)
                dst.unlink(missing_ok=True)
                continue
            return facts
        last_error = f"{result.status}: {result.failure_kind}"
        await asyncio.sleep(30)
    return {"status": "failed", "job_id": job_id, "attempts": MAX_ATTEMPTS,
            "error": last_error}


async def main(langs: list[str], classes: list[str]) -> None:
    from aetherlab.core.settings import load_settings
    from aetherlab.services.render_backend import (
        CloudRenderBackend, render_timeout_for)

    settings = load_settings()
    assert str(getattr(settings, "render_mode", "")).lower() == "cloud"
    backend = CloudRenderBackend(settings)
    ok, reason = backend.available()
    print(f"backend available={ok} ({reason})", flush=True)
    assert ok, reason

    OUT.mkdir(exist_ok=True)
    write_versions()
    canon_budgets = budgets()
    params_path = OUT / "params.json"
    params = json.loads(params_path.read_text(encoding="utf-8")) if params_path.exists() else {}
    failed: list[str] = []
    for lang in langs:
        code = (ROOT / "output" / "stage_l_scenes" / f"lesson_{lang}.py").read_text(encoding="utf-8")
        timeout = render_timeout_for(code, QUALITY, settings)
        print(f"lang={lang} quality={QUALITY} timeout={timeout}s classes={classes}", flush=True)
        params.setdefault(lang, {})
        for class_name in classes:
            seg = f"{lang}/{class_name}"
            if (OUT / lang / f"{class_name}.mp4").is_file() \
                    and params.get(lang, {}).get(class_name, {}).get("status") == "rendered":
                print(f"{seg}: cached, skipping", flush=True)
                continue
            params[lang][class_name] = await render_one(
                backend, code, lang, class_name, settings, timeout, canon_budgets[class_name])
            params_path.write_text(json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8")
            if params[lang][class_name]["status"] != "rendered":
                failed.append(seg)
    print(f"done: failed={failed} -> {OUT.resolve()}", flush=True)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    want_langs = [a for a in sys.argv[1:] if a in LANGS] or LANGS
    want_classes = [a for a in sys.argv[1:] if a in CLASS_NAMES] or CLASS_NAMES
    assert set(sys.argv[1:]) <= set(LANGS) | set(CLASS_NAMES), sys.argv[1:]
    asyncio.run(main(want_langs, want_classes))
