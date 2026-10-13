"""Score rendered review-pack videos with AetherLab's configured visual critic.

Example:
    python tools/critic_review_pack.py .analysis/problem-pack-v6/review.json

Scores are descriptive machine ratings. They do not verify hidden physics or
calibrate a release gate. Results are saved after each case so interrupted
reviews can resume without repeating completed model calls.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aetherlab.core.atomic_json import atomic_write_json
from aetherlab.core.console import configure_utf8_stdio
from aetherlab.core.settings import load_settings
from aetherlab.services.scene_critic import critique_video


def _brief(case: dict[str, Any]) -> str:
    prompt = str(case.get("prompt", "Review this physics animation."))
    variables = case.get("variables")
    if isinstance(variables, dict) and variables:
        rendered = ", ".join(f"{name}={value}" for name, value in variables.items())
        prompt += f"\n\nProblem givens: {rendered}."
    return prompt


async def _run(
    review_path: Path, output_path: Path, frame_count: int, *, repeat: bool = False,
) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    if not settings.openai_api_key or not settings.vision_model:
        print("Critic scoring requires the configured model key and vision model.")
        return 3

    review = json.loads(review_path.read_text(encoding="utf-8"))
    cases = review.get("cases", [])
    if not isinstance(cases, list) or not cases:
        print("Review pack has no cases.")
        return 2

    existing: dict[str, Any] = {}
    if output_path.exists():
        try:
            old = json.loads(output_path.read_text(encoding="utf-8"))
            if isinstance(old.get("cases"), dict):
                existing = dict(old["cases"])
        except (OSError, json.JSONDecodeError):
            existing = {}

    review_bytes = review_path.read_bytes()
    review_sha256 = hashlib.sha256(review_bytes).hexdigest()
    report: dict[str, Any] = {
        "schema": "aetherlab.critic_review_pack.v1",
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "review_pack": str(review_path),
        "review_pack_sha256": review_sha256,
        "vision_model_configured": str(settings.vision_model),
        "frame_count": frame_count,
        "cases": existing,
        "release_gate_calibrated": False,
        "note": "Machine critic scores are descriptive and do not certify physics.",
    }
    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("id") or f"case-{index}")
        video_value = str(case.get("video_path", ""))
        video_path = Path(video_value)
        if not video_path.is_absolute():
            video_path = review_path.resolve().parent / video_path
        if not video_path.is_file():
            row = {"verdict": "skipped", "error": "review video is missing"}
        else:
            video_sha256 = hashlib.sha256(video_path.read_bytes()).hexdigest()
            saved = existing.get(case_id)
            if (
                not repeat
                and
                isinstance(saved, dict)
                and saved.get("verdict") != "skipped"
                and saved.get("video_sha256") == video_sha256
            ):
                print(f"[{index}/{len(cases)}] {case_id}: video hash unchanged; keeping score.")
                continue
            started = time.monotonic()
            critique = await critique_video(
                video_path,
                _brief(case),
                settings,
                frame_count=frame_count,
            )
            row = {
                "verdict": critique.verdict,
                "score": critique.score,
                "breakdown": critique.breakdown,
                "breakdown_source": critique.breakdown_source,
                "problem_times_s": critique.problem_times_s,
                "issues": critique.issues,
                "strengths": critique.strengths,
                "model_used": critique.model_used,
                "video_sha256": video_sha256,
                "wall_seconds": round(time.monotonic() - started, 3),
            }
        saved = existing.get(case_id)
        history = list(saved.get("history", [])) if isinstance(saved, dict) else []
        if isinstance(saved, dict) and "history" not in saved and saved.get("score") is not None:
            history.append({key: value for key, value in saved.items() if key != "history"})
        history.append(dict(row))
        row["history"] = history
        report["cases"][case_id] = row
        existing[case_id] = row
        report["created_at"] = datetime.now(UTC).isoformat(timespec="seconds")
        atomic_write_json(output_path, report)
        print(
            f"[{index}/{len(cases)}] {case_id}: {row.get('verdict')} "
            f"score={row.get('score', 'n/a')} model={row.get('model_used', '')}",
            flush=True,
        )

    scored = sum(
        isinstance(item, dict) and item.get("verdict") in {"ship", "revise"}
        for item in report["cases"].values()
    )
    print(f"Saved {scored}/{len(cases)} critic scores to {output_path}")
    return 0 if scored == len(cases) else 1


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review_json", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--frame-count", type=int, default=6)
    parser.add_argument(
        "--repeat", action="store_true",
        help="Score even when the same video hash already has a result.",
    )
    args = parser.parse_args()
    if args.frame_count < 2 or args.frame_count > 12:
        parser.error("--frame-count must be between 2 and 12")
    output = args.output or args.review_json.with_name("critic_scores.json")
    return asyncio.run(_run(
        args.review_json, output, args.frame_count, repeat=args.repeat
    ))


if __name__ == "__main__":
    raise SystemExit(main())
