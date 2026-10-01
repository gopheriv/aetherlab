"""End-to-end proof that an uncatalogued physics topic gets a real AI scene."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from importlib.metadata import version
from pathlib import Path

from aetherlab.core.console import configure_utf8_stdio
from aetherlab.core.models import ProblemRequest, RagResult, SolverResult
from aetherlab.core.settings import load_settings
from aetherlab.services.manim_runtime import ManimRuntime


def _safe(value: object) -> str:
    text = str(value or "")
    text = re.sub(r"(?i)(sk-[A-Za-z0-9_-]{8,}|bearer\s+\S+)", "[redacted]", text)
    return text[:1200]


_BEAT_MARKER = re.compile(
    r"(?m)^\s*#\s*BEAT\s+(A\d+\.B\d+)\s*\|\s*"
    r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*s\s*$"
)


def _timeline_from_scene_code(code: str) -> list[dict[str, object]]:
    """Recover the explicit beat windows so reused scenes get the same timing gate."""
    return [
        {
            "id": match.group(1),
            "start_s": float(match.group(2)),
            "end_s": float(match.group(3)),
            "duration_s": float(match.group(3)) - float(match.group(2)),
        }
        for match in _BEAT_MARKER.finditer(code)
    ]


async def run(
    minimax_thinking: bool | None = None,
    reuse_code_path: Path | None = None,
    validate_only: bool = False,
) -> int:
    settings = load_settings()
    if not settings.openai_api_key:
        print("AI scene smoke blocked: no provider key is configured.")
        return 3
    if str(settings.render_mode).lower() != "cloud":
        print("AI scene smoke requires the user's explicit Cloud render mode; no setting was changed.")
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
            "Introduce quantized energy exchanges and Planck's spectral distribution.",
            "Show the peak shifting with temperature and the finite high-frequency tail.",
        ],
        keywords=["blackbody spectrum", "Planck distribution", "ultraviolet catastrophe"],
        variables={"temperature": 5800.0},
        model_name="smoke-test-ground-truth",
        key_equations=[
            "B_\\lambda(T)=\\frac{2hc^2}{\\lambda^5}"
            "\\frac{1}{e^{hc/(\\lambda k_BT)}-1}"
        ],
        assumptions=["Ideal blackbody in thermal equilibrium."],
    )
    rag = RagResult(keywords=list(solver.keywords), hits=[], backend="smoke-test")
    runtime = ManimRuntime(settings)
    from aetherlab.services.scene_generator import SceneGenerator

    generated_dir = Path(".analysis") / "ai-radiation-smoke"
    generated_dir.mkdir(parents=True, exist_ok=True)
    generated_files: list[str] = []
    if reuse_code_path is not None:
        from aetherlab.core.models import SceneBundle
        from aetherlab.services.code_safety import validate_code_safety
        from aetherlab.services.scene_validation import (
            count_construct_play_calls,
            estimate_duration,
            scene_hygiene_warnings,
            validate_scene,
        )

        code = reuse_code_path.read_text(encoding="utf-8")
        timeline = _timeline_from_scene_code(code)
        compile(code, str(reuse_code_path), "exec")
        safe, safety_issues = validate_code_safety(code)
        lint_ok, lint_issues = validate_scene(
            code, require_motion=True, timeline=timeline or None
        )
        overlap_issues = [
            issue for issue in scene_hygiene_warnings(code)
            if issue.startswith("[HYGIENE:OVERLAP]")
        ]
        estimate = estimate_duration(code)
        play_calls = count_construct_play_calls(code)
        from aetherlab.services.manim_runtime import _estimate_render_cost

        cost = _estimate_render_cost(code)
        duration_miss = (
            abs(estimate.total_seconds - request.duration_target_s)
            > request.duration_target_s * 0.2
        )
        if (
            not safe or not lint_ok or overlap_issues or play_calls > 16
            or cost > 3.5 or duration_miss
        ):
            raise ValueError(
                "Captured scene failed a fresh safety/layout/performance/duration gate: "
                + "; ".join((
                    safety_issues + lint_issues + overlap_issues
                    + ([f"[PERF:PLAY_BUDGET] {play_calls} calls exceed 16."]
                       if play_calls > 16 else [])
                    + ([f"[PERF:CLOUD_COST] estimate {cost:.1f} exceeds 3.5."]
                       if cost > 3.5 else [])
                    + ([
                        f"[TIMING:DURATION] estimate {estimate.total_seconds:.1f}s "
                        f"misses target {request.duration_target_s:.1f}s."
                    ] if duration_miss else [])
                )[:8])
            )
        scene = SceneBundle(
            class_name="AetherLabScene",
            code=code,
            engine="minimax-m3",
            status="compiled",
            diagnostics=["Reused captured AI scene after fresh static checks."],
            used_fallback=False,
            storyboard=(
                {"timeline": timeline, "timeline_duration_s": request.duration_target_s}
                if timeline else None
            ),
        )
        generated_files.append(str(reuse_code_path))
        generation_seconds = 0.0
    else:
        original_generate = SceneGenerator.generate

        async def capture_generated_code(self, *args, **kwargs):
            code = await original_generate(self, *args, **kwargs)
            generated_path = generated_dir / f"generated-attempt-{len(generated_files) + 1}.py"
            generated_path.write_text(code, encoding="utf-8", newline="\n")
            generated_files.append(str(generated_path))
            return code

        SceneGenerator.generate = capture_generated_code
        generation_started = time.monotonic()
        try:
            scene = await runtime.generate_scene_async(
                request, solver, rag, settings, max_retries=1,
                minimax_thinking=minimax_thinking,
            )
        finally:
            SceneGenerator.generate = original_generate
        generation_seconds = time.monotonic() - generation_started
    curated = any("curated component library" in item.lower() for item in scene.diagnostics)
    scene_origin = (
        "built_in_fallback" if scene.used_fallback
        else "curated" if curated
        else "ai_generated_reused" if reuse_code_path is not None
        else "ai_generated"
    )
    syntax_excerpt = ""
    for generated_file in generated_files:
        try:
            compile(Path(generated_file).read_text(encoding="utf-8"), generated_file, "exec")
        except SyntaxError as exc:
            source_lines = Path(generated_file).read_text(encoding="utf-8").splitlines()
            center = max(0, int(exc.lineno or 1) - 1)
            syntax_excerpt = "\n".join(
                f"{index + 1}: {source_lines[index]}"
                for index in range(max(0, center - 2), min(len(source_lines), center + 3))
            )
            break
    print(json.dumps({
        "stage": "generation",
        "model_configured": True,
        "manim_version": version("manim"),
        "minimax_thinking": (
            "reused-captured-code" if reuse_code_path is not None
            else "enabled" if minimax_thinking is True
            else "disabled" if minimax_thinking is False
            else "current-default"
        ),
        "scene_origin": scene_origin,
        "used_fallback": scene.used_fallback,
        "fallback_reason": _safe(scene.fallback_reason),
        "diagnostics": [_safe(message) for message in scene.diagnostics[-12:]],
        "generated_attempt_files": generated_files,
        "syntax_excerpt": _safe(syntax_excerpt),
        "generation_wall_seconds": round(generation_seconds, 3),
        "code_characters": len(scene.code),
        "status": scene.status,
    }))
    if curated or scene.used_fallback or len(scene.code) <= 1821:
        print("AI scene acceptance failed; cloud rendering was not started.")
        out = Path(".analysis") / "ai-radiation-smoke" / "generation-failure.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "scene_origin": scene_origin,
            "minimax_thinking": (
                "reused-captured-code" if reuse_code_path is not None
                else "enabled" if minimax_thinking is True
                else "disabled" if minimax_thinking is False
                else "current-default"
            ),
            "used_fallback": scene.used_fallback,
            "fallback_reason": _safe(scene.fallback_reason),
            "diagnostics": [_safe(message) for message in scene.diagnostics[-12:]],
            "generated_attempt_files": generated_files,
            "syntax_excerpt": _safe(syntax_excerpt),
            "generation_wall_seconds": round(generation_seconds, 3),
        }, indent=2), encoding="utf-8", newline="\n")
        return 2

    if validate_only:
        print("AI scene passed static acceptance; Cloud render was not started.")
        return 0

    from aetherlab.services.scene_validation import estimate_duration

    duration_estimate = estimate_duration(scene.code)

    render_started = time.monotonic()
    scene = await runtime.render_scene_with_repair(
        scene, settings, quality="l", max_repairs=2, max_revisions=0,
        brief=request.prompt,
    )
    video = Path(scene.video_path) if scene.video_path else None
    exists = bool(video and video.is_file() and video.stat().st_size > 0)
    duration = 0.0
    critique = None
    if exists:
        from aetherlab.services.scene_critic import critique_video
        from aetherlab.services.voiceover import get_duration

        duration = await get_duration(video)
        critique = await critique_video(video, request.prompt, settings, frame_count=6)
        scene.quality_score = critique.score
        scene.critique_verdict = critique.verdict
        scene.critique_issues = list(critique.issues)
        scene.critique_model = str(critique.model_used or "")
    result = {
        "stage": "render",
        "status": scene.status,
        "video_exists": exists,
        "video_path": str(video) if exists else "",
        "bytes": video.stat().st_size if exists else 0,
        "duration_seconds": round(duration, 3),
        "estimated_duration_seconds": round(duration_estimate.total_seconds, 3),
        "duration_estimate_notes": duration_estimate.notes,
        "render_wall_seconds": round(time.monotonic() - render_started, 3),
        "duration_target_seconds": request.duration_target_s,
        "failure_kind": scene.failure_kind,
        "quality_score": float(critique.score) if critique else 0.0,
        "critique_verdict": critique.verdict if critique else "skipped",
        "critique_model": critique.model_used if critique else "",
        "diagnostic_tail": [_safe(message) for message in scene.diagnostics[-5:]],
    }
    print(json.dumps(result, indent=2))
    out = Path(".analysis") / "ai-radiation-smoke" / "result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8", newline="\n")
    duration_ok = abs(duration - request.duration_target_s) <= request.duration_target_s * 0.20
    return 0 if scene.status == "rendered" and exists and duration_ok else 1


if __name__ == "__main__":
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--thinking", choices=("enabled", "disabled"),
        help="Set only the MiniMax scene-codegen thinking mode for the experiment.",
    )
    parser.add_argument(
        "--reuse-code-path", type=Path,
        help="Render a previously captured scene after fresh static safety checks.",
    )
    parser.add_argument(
        "--validate-only", action="store_true",
        help="Check a reused scene and stop before Cloud dispatch.",
    )
    options = parser.parse_args()
    override = None if options.thinking is None else options.thinking == "enabled"
    raise SystemExit(asyncio.run(
        run(override, options.reuse_code_path, options.validate_only)
    ))
