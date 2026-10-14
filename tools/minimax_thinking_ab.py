"""Run a one-scene MiniMax thinking on/off Cloud A/B without changing settings."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import shutil
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from aetherlab.core.atomic_json import atomic_write_json
from aetherlab.core.console import configure_utf8_stdio
from aetherlab.core.models import ProblemRequest, RagResult, SolverResult
from aetherlab.core.settings import load_settings
from aetherlab.services.manim_runtime import ManimRuntime

_ACTIVE_AB_RUN: dict[str, object] = {}


def _redact(value: object) -> str:
    text = str(value or "")
    return re.sub(r"(?i)(sk-[A-Za-z0-9_-]{8,}|bearer\s+\S+)", "[redacted]", text)


def _safe(value: object) -> str:
    return _redact(value)[:1000]


def _persist_scene_artifacts(scene, output_dir: Path, thinking: str, *, stage: str) -> dict[str, str]:
    """Keep redacted source and diagnostics so an arm can be reproduced."""
    if thinking not in {"enabled", "disabled"}:
        raise ValueError(f"unknown thinking arm: {thinking}")
    if stage not in {"generated", "final"}:
        raise ValueError(f"unknown scene artifact stage: {stage}")
    output_dir = output_dir.resolve()
    stem = f"thinking-{thinking}-{stage}"
    scene_path = output_dir / "scenes" / f"{stem}.py"
    diagnostics_path = output_dir / "diagnostics" / f"{stem}.txt"
    scene_path.parent.mkdir(parents=True, exist_ok=True)
    diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
    source = _redact(scene.code)
    scene_path.write_text(source, encoding="utf-8", newline="\n")
    diagnostics = "\n\n".join(_redact(item) for item in scene.diagnostics)
    diagnostics_path.write_text(diagnostics + ("\n" if diagnostics else ""), encoding="utf-8")
    return {
        "scene_path": scene_path.relative_to(output_dir).as_posix(),
        "scene_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "diagnostics_path": diagnostics_path.relative_to(output_dir).as_posix(),
    }


def _record_interruption(report_path: Path, report: dict, thinking: str) -> None:
    stopped_at = datetime.now(UTC).isoformat(timespec="seconds")
    started_at = report.get("current_arm_started_at", "")
    try:
        elapsed_seconds = round(
            (datetime.fromisoformat(str(stopped_at)) - datetime.fromisoformat(str(started_at))).total_seconds(),
            1,
        )
    except ValueError:
        elapsed_seconds = None
    report["run_status"] = "interrupted"
    report["interruption"] = {
        "arm": thinking,
        "started_at": started_at,
        "stopped_at": stopped_at,
        "elapsed_seconds": elapsed_seconds,
        "reason": "The active arm was cancelled before it returned a result.",
    }
    report["conclusion"] = (
        "Incomplete: an arm was interrupted before its result was recorded; "
        "this report does not establish a matched comparison."
    )
    report["updated_at"] = stopped_at
    atomic_write_json(report_path, report)
    _ACTIVE_AB_RUN.clear()


def _persist_video_artifact(video: Path, output_dir: Path, thinking: str) -> dict[str, str]:
    """Copy a completed arm's MP4 beside the report and bind it by hash."""
    if thinking not in {"enabled", "disabled"}:
        raise ValueError(f"unknown thinking arm: {thinking}")
    output_dir = output_dir.resolve()
    destination = output_dir / "videos" / f"thinking-{thinking}.mp4"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(video, destination)
    with destination.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {
        "video_path": destination.relative_to(output_dir).as_posix(),
        "video_sha256": digest,
    }


async def _run_variant(
    settings, request, solver, rag, *, thinking: bool, artifact_dir: Path,
) -> dict:
    runtime = ManimRuntime(settings)
    generation_started = time.monotonic()
    scene = await runtime.generate_scene_async(
        request,
        solver,
        rag,
        settings,
        max_retries=1,
        minimax_thinking=thinking,
    )
    generation_seconds = time.monotonic() - generation_started
    curated = any("curated component library" in item.lower() for item in scene.diagnostics)
    from aetherlab.services.scene_validation import (
        count_construct_play_calls,
        estimate_duration,
    )

    estimate = estimate_duration(scene.code)
    scene_origin = (
        "fallback" if scene.used_fallback
        else "curated" if curated
        else "ai_generated"
    )
    row = {
        "thinking": "enabled" if thinking else "disabled",
        "scene_origin": scene_origin,
        "used_fallback": bool(scene.used_fallback),
        "fallback_reason": _safe(scene.fallback_reason),
        "code_characters": len(scene.code),
        "estimated_duration_seconds": round(estimate.total_seconds, 3),
        "self_play_calls": count_construct_play_calls(scene.code),
        "generation_wall_seconds": round(generation_seconds, 3),
        "render_status": "not_started",
        "video_exists": False,
        "duration_seconds": 0.0,
        "quality_score": 0.0,
        "critique_verdict": "skipped",
        "generation_repair_count": sum(
            any(
                marker in item.lower()
                for marker in (
                    "repaired the generated scene",
                    "applied a targeted timing and layout repair",
                )
            )
            for item in scene.diagnostics
        ),
        "render_repair_count": sum(
            bool(re.search(r"(?:Applied|Render) render repair \d+", item))
            for item in scene.diagnostics
        ),
        "diagnostics": [_safe(item) for item in scene.diagnostics[-8:]],
    }
    row.update(_persist_scene_artifacts(scene, artifact_dir, row["thinking"], stage="generated"))
    if scene.used_fallback or curated or not scene.code:
        return row

    render_started = time.monotonic()
    scene = await runtime.render_scene_with_repair(
        scene,
        settings,
        quality="l",
        max_repairs=2,
        max_revisions=0,
        brief=request.prompt,
    )
    row["render_wall_seconds"] = round(time.monotonic() - render_started, 3)
    row["render_status"] = scene.status
    row["render_repair_count"] = sum(
        bool(re.search(r"(?:Applied|Render) render repair \d+", item))
        for item in scene.diagnostics
    )
    row.update(_persist_scene_artifacts(scene, artifact_dir, row["thinking"], stage="final"))
    video = Path(scene.video_path) if scene.video_path else None
    row["video_exists"] = bool(video and video.is_file() and video.stat().st_size > 0)
    if row["video_exists"]:
        row.update(_persist_video_artifact(video, artifact_dir, row["thinking"]))
        from aetherlab.services.scene_critic import critique_video
        from aetherlab.services.voiceover import get_duration

        row["duration_seconds"] = round(await get_duration(video), 3)
        critique = await critique_video(video, request.prompt, settings, frame_count=6)
        row["quality_score"] = float(critique.score or 0.0)
        row["critique_verdict"] = str(critique.verdict or "skipped")
        row["critique_model"] = str(critique.model_used or "")
        row["critique_issues"] = [_safe(issue) for issue in critique.issues[:6]]
    row["diagnostics"] = [_safe(item) for item in scene.diagnostics[-8:]]
    return row


async def run() -> int:
    settings = load_settings()
    if not settings.openai_api_key or not settings.vision_model:
        print("A/B blocked: provider and vision critic must both be configured.")
        return 3
    if str(settings.render_mode).lower() != "cloud":
        print("A/B requires the existing Cloud-only setting; no setting was changed.")
        return 3

    request = ProblemRequest(
        prompt=(
            "Explain the blackbody spectrum using Planck's distribution. Compare "
            "the classical Rayleigh-Jeans prediction, its ultraviolet catastrophe, "
            "and the finite measured spectrum produced by discrete energy exchange."
        ),
        duration_target_s=30.0,
    )
    solver = SolverResult(
        summary=(
            "Planck's distribution models the blackbody spectrum and removes the "
            "ultraviolet divergence of the classical Rayleigh-Jeans approximation."
        ),
        derivation_steps=[
            "Compare the classical low-frequency approximation with the observed spectrum.",
            "Introduce discrete energy exchange and Planck's spectral distribution.",
            "Show the peak shifting with temperature and the finite high-frequency tail.",
        ],
        keywords=["blackbody spectrum", "Planck distribution", "ultraviolet catastrophe"],
        variables={"temperature": 5800.0},
        model_name="minimax-thinking-ab-reference",
        key_equations=[
            "B_\\lambda(T)=\\frac{2hc^2}{\\lambda^5}"
            "\\frac{1}{e^{hc/(\\lambda k_BT)}-1}"
        ],
        assumptions=["Ideal blackbody in thermal equilibrium."],
    )
    rag = RagResult(keywords=list(solver.keywords), hits=[], backend="A/B-smoke")
    experiment_settings = replace(
        settings,
        narration_enabled=False,
        visual_critic_max_passes=0,
    )
    output = Path(".analysis") / f"minimax-thinking-ab-{datetime.now(UTC):%Y%m%d-%H%M%S}"
    output.mkdir(parents=True, exist_ok=False)
    report_path = output / "report.json"
    report = {
        "schema": "aetherlab.minimax_thinking_ab.v1",
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": settings.llm_model,
        "sample_count_per_arm": 1,
        "prompt": request.prompt,
        "variants": [],
        "run_status": "in_progress",
        "conclusion": "Both arms have not completed yet.",
    }
    atomic_write_json(report_path, report)
    _ACTIVE_AB_RUN.update({"report_path": report_path, "report": report, "arm": None})
    variants = []
    for thinking in (False, True):
        label = "enabled" if thinking else "disabled"
        print(f"Starting MiniMax thinking={label} variant.", flush=True)
        report["current_arm"] = label
        report["current_arm_started_at"] = datetime.now(UTC).isoformat(timespec="seconds")
        _ACTIVE_AB_RUN["arm"] = label
        atomic_write_json(report_path, report)
        try:
            variant = await _run_variant(
                experiment_settings, request, solver, rag,
                thinking=thinking, artifact_dir=output,
            )
        except asyncio.CancelledError:
            _record_interruption(report_path, report, label)
            raise
        variants.append(variant)
        print(json.dumps(variants[-1], indent=2), flush=True)
        report["variants"] = variants
        report["current_arm"] = None
        report.pop("current_arm_started_at", None)
        _ACTIVE_AB_RUN["arm"] = None
        report["updated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
        atomic_write_json(report_path, report)

    quality_scores = [row["quality_score"] for row in variants if row["quality_score"] > 0]
    report["run_status"] = "complete"
    report["conclusion"] = (
        "Pilot only: both arms need a successful AI scene, completed Cloud render, "
        "and nonzero vision score before comparing latency, quality, and repairs."
        if len(quality_scores) < 2
        else "Pilot only: one scene per arm is directional evidence, not a calibrated benchmark."
    )
    report["updated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    atomic_write_json(report_path, report)
    _ACTIVE_AB_RUN.clear()
    print(f"A/B report: {report_path}", flush=True)
    return 0 if len(quality_scores) == 2 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    return asyncio.run(run())


if __name__ == "__main__":
    configure_utf8_stdio()
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        report_path = _ACTIVE_AB_RUN.get("report_path")
        report = _ACTIVE_AB_RUN.get("report")
        arm = _ACTIVE_AB_RUN.get("arm")
        if (
            isinstance(report_path, Path)
            and isinstance(report, dict)
            and isinstance(arm, str)
            and report.get("run_status") != "interrupted"
        ):
            _record_interruption(report_path, report, arm)
        raise SystemExit(130)
