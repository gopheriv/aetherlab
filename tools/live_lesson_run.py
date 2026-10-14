"""Run one narrated AI lesson end to end and audit its sync (local or CI).

Usage:
    python tools/live_lesson_run.py <out_dir> "<prompt>" [seconds] [--solver solver.json]

Everything runs in this process: solve, voice-first storyboard, segment code,
preflight, render (always local to this machine, which on GitHub Actions is
the cloud), narration and assembly. Saved settings are never changed; the
run turns narration on in memory only. Writes to <out_dir>:
    run.log, lesson.mp4, lesson.srt, lesson_bundle.json, sync_audit.json,
    solver.json (reuse it with --solver to skip the slow solve next time)

The model comes from the usual AETHERLAB_OPENAI_* environment variables.
Exit code: 0 when the lesson rendered, 1 when it stopped incomplete,
2 when the solver fell back (model unreachable), so CI shows the outcome.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import logging
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aetherlab.core.console import configure_utf8_stdio  # noqa: E402
from aetherlab.core.models import ProblemRequest, SolverResult  # noqa: E402
from aetherlab.core.settings import load_settings  # noqa: E402

T0 = time.monotonic()


def say(msg: str) -> None:
    print(f"[{time.monotonic() - T0:7.1f}s] {msg}", flush=True)


async def run(out: Path, prompt: str, seconds: float, solver_path: Path | None) -> int:
    from aetherlab.services.llm import AsyncLLMCoordinator
    from aetherlab.services.manim_runtime import ManimRuntime
    from aetherlab.services.pipeline import _merge_web_references
    from aetherlab.services.rag import LocalVectorRag
    from aetherlab.services.scene_preflight import beat_timings, preflight_scene
    from aetherlab.services.segmented_pipeline import render_segmented_scene

    settings = dataclasses.replace(
        load_settings(), narration_enabled=True, render_mode="local",
    )
    request = ProblemRequest(prompt=prompt, duration_target_s=seconds)
    say(f"model={settings.llm_model} vision={settings.vision_model} render=local "
        f"narration=on target={seconds:.0f}s voice={settings.tts_voice}")

    if solver_path and solver_path.is_file():
        solver = SolverResult.from_json(json.loads(solver_path.read_text(encoding="utf-8")))
        say(f"reusing solver result from {solver_path.name} ({solver.model_name})")
    else:
        solver = await AsyncLLMCoordinator(settings).solve(request)
        if solver.model_name.startswith("deterministic"):
            say("solver fell back (model unreachable?); stopping instead of planning on a scaffold")
            return 2
    (out / "solver.json").write_text(
        json.dumps(solver.to_json(), indent=2, default=str), encoding="utf-8")
    say(f"solved by {solver.model_name}: {solver.summary[:140]!r}")

    rag = await LocalVectorRag(settings).search(solver.keywords)
    rag = await _merge_web_references(rag, solver.keywords, settings)
    scene = await render_segmented_scene(
        request, solver, rag, settings, runtime=ManimRuntime(settings), quality="l",
        progress=lambda message: say(f"  progress: {message}"),
    )
    say(f"lesson: status={scene.status} video={scene.video_path}")
    for line in scene.diagnostics:
        say(f"  diag: {line}")
    (out / "lesson_bundle.json").write_text(
        json.dumps(scene.to_json(), indent=2, default=str), encoding="utf-8")

    manifests = sorted(Path(settings.data_dir, "segmented_scenes").glob("*/manifest.json"),
                       key=lambda path: path.stat().st_mtime)
    if manifests:
        shutil.copy2(manifests[-1], out / "manifest.json")
        manifest = json.loads(manifests[-1].read_text(encoding="utf-8"))
        board = manifest.get("storyboard", {})
        audit = {"timing_basis": board.get("timing_basis"), "speech": board.get("speech"),
                 "segments": []}
        for record in manifest.get("segments", []):
            bundle = record.get("bundle") or {}
            sync = bundle.get("narration_sync") or {}
            drift = None
            code = bundle.get("code", "")
            if code:
                report = await asyncio.to_thread(
                    preflight_scene, code, bundle.get("class_name", "AetherLabScene"))
                if report.ok:
                    drift = max((abs(t.drift_s) for t in beat_timings(code, report)), default=None)
            entry = {
                "index": record.get("index"), "state": record.get("state"),
                "duration_s": record.get("duration_s"),
                "sync_method": sync.get("method"),
                "max_boundary_overrun_s": sync.get("max_boundary_overrun_s"),
                "max_rate_adjustment_pct": sync.get("max_rate_adjustment_pct"),
                "max_beat_drift_s": drift,
            }
            audit["segments"].append(entry)
            say(f"  segment {entry}")
        (out / "sync_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")

    if scene.video_path and Path(scene.video_path).is_file():
        shutil.copy2(scene.video_path, out / "lesson.mp4")
        if scene.subtitle_path and Path(scene.subtitle_path).is_file():
            shutil.copy2(scene.subtitle_path, out / "lesson.srt")
    say("DONE")
    return 0 if scene.status == "rendered" else 1


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("prompt")
    parser.add_argument("seconds", nargs="?", type=float, default=60.0)
    parser.add_argument("--solver", type=Path, default=None)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(args.out_dir / "run.log", encoding="utf-8"),
                  logging.StreamHandler()],
    )
    return asyncio.run(run(args.out_dir, args.prompt, args.seconds, args.solver))


if __name__ == "__main__":
    raise SystemExit(main())
