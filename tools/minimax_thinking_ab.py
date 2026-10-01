"""Run a one-scene MiniMax thinking on/off Cloud A/B without changing settings."""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from aetherlab.core.console import configure_utf8_stdio
from aetherlab.core.models import ProblemRequest, RagResult, SolverResult
from aetherlab.core.settings import load_settings
from aetherlab.services.manim_runtime import ManimRuntime


def _safe(value: object) -> str:
    text = str(value or "")
    text = re.sub(r"(?i)(sk-[A-Za-z0-9_-]{8,}|bearer\s+\S+)", "[redacted]", text)
    return text[:1000]


async def _run_variant(settings, request, solver, rag, *, thinking: bool) -> dict:
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
    video = Path(scene.video_path) if scene.video_path else None
    row["video_exists"] = bool(video and video.is_file() and video.stat().st_size > 0)
    if row["video_exists"]:
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
    variants = []
    for thinking in (False, True):
        label = "enabled" if thinking else "disabled"
        print(f"Starting MiniMax thinking={label} variant.", flush=True)
        variants.append(await _run_variant(
            experiment_settings, request, solver, rag, thinking=thinking
        ))
        print(json.dumps(variants[-1], indent=2), flush=True)

    quality_scores = [row["quality_score"] for row in variants if row["quality_score"] > 0]
    report = {
        "schema": "aetherlab.minimax_thinking_ab.v1",
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": settings.llm_model,
        "sample_count_per_arm": 1,
        "prompt": request.prompt,
        "variants": variants,
        "conclusion": (
            "Pilot only: both arms need a successful AI scene, completed Cloud render, "
            "and nonzero vision score before comparing latency, quality, and repairs."
            if len(quality_scores) < 2
            else "Pilot only: one scene per arm is directional evidence, not a calibrated benchmark."
        ),
    }
    output = Path(".analysis") / f"minimax-thinking-ab-{datetime.now(UTC):%Y%m%d-%H%M%S}"
    output.mkdir(parents=True, exist_ok=False)
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"A/B report: {report_path}", flush=True)
    return 0 if len(quality_scores) == 2 else 1


if __name__ == "__main__":
    configure_utf8_stdio()
    raise SystemExit(asyncio.run(run()))
