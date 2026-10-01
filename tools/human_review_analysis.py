"""Summarize human scene ratings and compare them with optional critic scores.

The report is descriptive. It never picks a quality threshold or grants a
release gate; eight scenes are a pilot-sized calibration set, not certification.
Physics/substance and pacing/structure are explicitly treated as proxy axes.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any

from aetherlab.core.console import configure_utf8_stdio

HUMAN_AXES = ("legibility", "physics", "pacing", "teaching_value")
CRITIC_AXIS_MAP = {
    "legibility": "legibility",
    "physics": "substance",
    "pacing": "structure",
}
CRITIC_AXIS_MAPPING_KIND = {
    "legibility": "direct",
    "physics": "proxy",
    "pacing": "proxy",
}


def analyze_reviews(
    review: dict[str, Any],
    critic_scores: dict[str, Any] | None = None,
    *,
    review_path: Path | None = None,
) -> dict[str, Any]:
    """Validate rating coverage and compute descriptive human/critic agreement."""
    cases = review.get("cases", [])
    if not isinstance(cases, list):
        cases = []
    external = critic_scores.get("cases", {}) if isinstance(critic_scores, dict) else {}
    if not isinstance(external, dict):
        external = {}
    required = max(1, _integer(review.get("human_ratings_required"), 8))
    base_dir = Path(review_path).resolve().parent if review_path else Path.cwd()
    errors: list[str] = []
    missing_videos: list[str] = []
    complete_ids: list[str] = []
    human_case_scores: list[float] = []
    critic_case_scores: list[float] = []
    paired_human_scores: list[float] = []
    human_axis_values: dict[str, list[float]] = {axis: [] for axis in HUMAN_AXES}
    axis_pairs: dict[str, tuple[list[float], list[float]]] = {
        axis: ([], []) for axis in HUMAN_AXES
    }
    critic_count = 0

    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            errors.append(f"case {index} is not an object")
            continue
        case_id = str(case.get("id") or f"case-{index}")
        video_value = case.get("video_path")
        if video_value:
            video_path = Path(str(video_value))
            if not video_path.is_absolute():
                video_path = base_dir / video_path
            if not video_path.is_file():
                missing_videos.append(case_id)
        else:
            missing_videos.append(case_id)

        ratings = case.get("ratings", {})
        if not isinstance(ratings, dict):
            errors.append(f"{case_id}: ratings must be an object")
            ratings = {}
        human: dict[str, float] = {}
        for axis in HUMAN_AXES:
            value = ratings.get(axis)
            if value is None or value == "":
                continue
            numeric = _score(value, 1.0, 5.0)
            if numeric is None:
                errors.append(f"{case_id}: {axis} must be a number from 1 to 5")
            else:
                human[axis] = numeric
                human_axis_values[axis].append(numeric)
        if len(human) == len(HUMAN_AXES):
            complete_ids.append(case_id)
            human_case_scores.append(mean(human.values()))

        scores = case.get("critic_scores")
        if not isinstance(scores, dict):
            scores = external.get(case_id, {})
        if not isinstance(scores, dict):
            scores = {}
        breakdown = scores.get("breakdown", {})
        if not isinstance(breakdown, dict):
            breakdown = {}
        overall_critic = _score(scores.get("score"), 0.0, 10.0)
        if overall_critic is not None:
            critic_count += 1
        if len(human) == len(HUMAN_AXES) and overall_critic is not None:
            paired_human_scores.append(mean(human.values()))
            critic_case_scores.append(overall_critic)

        for human_axis, critic_axis in CRITIC_AXIS_MAP.items():
            if human_axis not in human:
                continue
            critic_value = _score(breakdown.get(critic_axis), 0.0, 2.0)
            if critic_value is not None:
                axis_pairs[human_axis][0].append(human[human_axis])
                axis_pairs[human_axis][1].append(critic_value)

    paired_complete = len(critic_case_scores)
    corr = _spearman(paired_human_scores, critic_case_scores) if paired_complete else None
    axis_correlations = {
        axis: {
            "pair_count": len(values[0]),
            "spearman_rho": _spearman(*values),
            "critic_axis": CRITIC_AXIS_MAP.get(axis),
            "mapping_kind": CRITIC_AXIS_MAPPING_KIND.get(axis, "unavailable"),
        }
        for axis, values in axis_pairs.items()
    }
    human_means = {
        axis: round(mean(values), 4) if values else None
        for axis, values in human_axis_values.items()
    }
    ready = len(complete_ids) >= required and paired_complete >= required and not missing_videos and not errors
    return {
        "schema": "aetherlab.human_review_analysis.v1",
        "status": "ready_for_calibration_review" if ready else "incomplete",
        "case_count": len(cases),
        "required_human_ratings": required,
        "complete_human_ratings": len(complete_ids),
        "complete_case_ids": complete_ids,
        "critic_scored_cases": critic_count,
        "paired_human_critic_cases": paired_complete,
        "human_axis_means_1_to_5": human_means,
        "overall_mean_human_score_1_to_5": (
            round(mean(human_case_scores), 4) if human_case_scores else None
        ),
        "overall_spearman_rho": corr,
        "axis_correlations": axis_correlations,
        "missing_videos": missing_videos,
        "errors": errors,
        "release_gate_calibrated": False,
        "guidance": (
            "Physics/substance and pacing/structure are proxy matches, not identical constructs. "
            "Review paired scores, sample uncertainty, and deterministic regressions with people; "
            "this report does not set a blocking threshold."
        ),
    }


def _score(value: Any, minimum: float, maximum: float) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and minimum <= number <= maximum else None


def _integer(value: Any, default: int) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError, OverflowError):
        return default


def _average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    index = 0
    while index < len(order):
        stop = index + 1
        while stop < len(order) and values[order[stop]] == values[order[index]]:
            stop += 1
        average_rank = ((index + 1) + stop) / 2.0
        for item in order[index:stop]:
            ranks[item] = average_rank
        index = stop
    return ranks


def _spearman(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 3:
        return None
    x, y = _average_ranks(left), _average_ranks(right)
    x_mean, y_mean = mean(x), mean(y)
    numerator = sum((a - x_mean) * (b - y_mean) for a, b in zip(x, y, strict=True))
    x_norm = sum((a - x_mean) ** 2 for a in x)
    y_norm = sum((b - y_mean) ** 2 for b in y)
    denominator = math.sqrt(x_norm * y_norm)
    return round(numerator / denominator, 6) if denominator else None


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "review_json", nargs="?", type=Path,
        default=Path(".analysis/human-review-pack/review.json"),
    )
    parser.add_argument(
        "--critic-scores", type=Path,
        help="Optional JSON with {'cases': {case_id: {'score': 0..10, 'breakdown': {...}}}}.",
    )
    parser.add_argument("--output", type=Path, help="Write the summary JSON to this path.")
    parser.add_argument("--require-complete", action="store_true", help="Exit 2 unless calibration inputs exist.")
    args = parser.parse_args()
    review = json.loads(args.review_json.read_text(encoding="utf-8"))
    scores = (
        json.loads(args.critic_scores.read_text(encoding="utf-8"))
        if args.critic_scores else None
    )
    report = analyze_reviews(review, scores, review_path=args.review_json)
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 2 if args.require_complete and report["status"] != "ready_for_calibration_review" else 0


if __name__ == "__main__":
    raise SystemExit(main())
