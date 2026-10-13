"""Summarize de-identified local delayed-recall events without efficacy claims.

Example:
    python tools/learner_study_analysis.py progress-a.json progress-b.json \
        --output study-summary.json

Only aggregate results are written. Participant identifiers and source paths
are not copied into the report. Open-response self-ratings stay separate from
objectively scored multiple-choice reviews.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Sequence

from aetherlab.core.atomic_json import atomic_write_json
from aetherlab.core.console import configure_utf8_stdio
from aetherlab.services.course_mode import CourseProgressStore

TARGET_DAYS = {"day_1": 1.0, "day_7": 7.0}


def analyze_participants(
    participant_events: Sequence[Iterable[dict[str, Any]]],
    *,
    as_of: datetime | None = None,
    tolerance_days: float = 1.0,
    transfer_rows: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return aggregate return/recall counts, keeping recall modes distinct."""
    if not math.isfinite(tolerance_days) or tolerance_days < 0:
        raise ValueError("tolerance_days must be a finite non-negative number")
    now = _utc(as_of or datetime.now(UTC))
    clean: list[list[dict[str, Any]]] = [
        [dict(event) for event in events if isinstance(event, dict)]
        for events in participant_events
    ]
    first_quiz: dict[tuple[int, str, str], dict[str, Any]] = {}
    reviews: dict[tuple[int, str, str], list[dict[str, Any]]] = defaultdict(list)

    for participant_index, events in enumerate(clean):
        for event in events:
            key = _item_key(participant_index, event)
            if key is None:
                continue
            if event.get("kind") == "quiz":
                previous = first_quiz.get(key)
                if previous is None or _event_time(event) < _event_time(previous):
                    first_quiz[key] = event
            elif event.get("kind") == "spaced_review":
                reviews[key].append(event)

    due_items = returned_items = 0
    for key, quiz in first_quiz.items():
        started = _event_time(quiz)
        if started is None:
            continue
        interval = _positive_days(quiz.get("scheduled_interval_days"), default=1.0)
        due_at = started + timedelta(days=interval)
        if now < due_at:
            continue
        due_items += 1
        if any((at := _event_time(review)) is not None and at >= due_at for review in reviews[key]):
            returned_items += 1

    selected: dict[str, dict[tuple[int, str, str], dict[str, Any]]] = {
        name: {} for name in TARGET_DAYS
    }
    for key, item_reviews in reviews.items():
        first = first_quiz.get(key)
        first_at = _event_time(first) if first else None
        for event in item_reviews:
            elapsed = _finite_float(event.get("days_since_first_attempt"))
            if elapsed is None and first_at is not None:
                event_at = _event_time(event)
                if event_at is not None:
                    elapsed = (event_at - first_at).total_seconds() / 86400.0
            if elapsed is None or elapsed < 0:
                continue
            for bucket, target in TARGET_DAYS.items():
                if abs(elapsed - target) > tolerance_days:
                    continue
                previous = selected[bucket].get(key)
                previous_elapsed = (
                    _finite_float(previous.get("days_since_first_attempt"))
                    if previous else None
                )
                if previous_elapsed is None and previous and first_at:
                    previous_at = _event_time(previous)
                    previous_elapsed = (
                        (previous_at - first_at).total_seconds() / 86400.0
                        if previous_at else None
                    )
                if previous is None or previous_elapsed is None or abs(elapsed - target) < abs(previous_elapsed - target):
                    selected[bucket][key] = event

    measures = {}
    for bucket, events_by_item in selected.items():
        objective = [
            event for event in events_by_item.values()
            if event.get("recall_mode") == "objective_mcq"
            and isinstance(event.get("correct"), bool)
        ]
        self_reported = [
            event for event in events_by_item.values()
            if event.get("recall_mode", "self_reported") != "objective_mcq"
            and isinstance(event.get("recalled"), bool)
        ]
        unscored = len(events_by_item) - len(objective) - len(self_reported)
        objective_correct = sum(event["correct"] for event in objective)
        self_reported_recalled = sum(event["recalled"] for event in self_reported)
        measures[bucket] = {
            "window_days": [
                max(0.0, TARGET_DAYS[bucket] - tolerance_days),
                TARGET_DAYS[bucket] + tolerance_days,
            ],
            "unique_reviewed_items": len(events_by_item),
            "objective_mcq": {
                "n": len(objective),
                "correct": objective_correct,
                "accuracy": _rate(objective_correct, len(objective)),
            },
            "self_reported_open_response": {
                "n": len(self_reported),
                "recalled": self_reported_recalled,
                "recall_rate": _rate(self_reported_recalled, len(self_reported)),
            },
            "unscored": unscored,
        }

    return {
        "schema": "aetherlab.learner_study_analysis.v1",
        "as_of": now.isoformat(timespec="seconds"),
        "participant_count": len(clean),
        "due_return": {
            "eligible_items": due_items,
            "returned_items": returned_items,
            "return_rate": _rate(returned_items, due_items),
        },
        "delayed_recall": measures,
        "transfer": _analyze_transfer_rows(
            transfer_rows or (), len(clean), tolerance_days
        ),
        "interpretation": (
            "Descriptive pilot data only. These counts do not establish a causal "
            "learning benefit or replace a controlled learner study."
        ),
    }


def _item_key(participant_index: int, event: dict[str, Any]) -> tuple[int, str, str] | None:
    lesson = str(event.get("lesson_key", "")).strip()
    question = str(event.get("question_index", "")).strip()
    if not lesson or not question:
        return None
    return participant_index, lesson, question


def _event_time(event: dict[str, Any] | None) -> datetime | None:
    if not isinstance(event, dict):
        return None
    value = str(event.get("at", "")).strip()
    if not value:
        return None
    try:
        return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _positive_days(value: object, *, default: float) -> float:
    days = _finite_float(value)
    return days if days is not None and days > 0 else default


def _finite_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _analyze_transfer_rows(
    rows: Iterable[dict[str, Any]], participant_count: int, tolerance_days: float,
) -> dict[str, Any]:
    candidates: dict[str, dict[tuple[int, str], dict[str, Any]]] = {
        name: {} for name in TARGET_DAYS
    }
    excluded_non_novel = 0
    valid_novel_rows = 0
    for row_number, row in enumerate(rows, start=2):
        if not isinstance(row, dict):
            raise ValueError(f"transfer row {row_number} must be an object")
        try:
            participant_slot = int(row.get("participant_slot", ""))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"transfer row {row_number} has an invalid participant_slot") from exc
        if not 1 <= participant_slot <= participant_count:
            raise ValueError(
                f"transfer row {row_number} participant_slot must be between 1 and {participant_count}"
            )
        novel = _parse_bool(row.get("novel"))
        if novel is None:
            raise ValueError(f"transfer row {row_number} must set novel to true or false")
        if not novel:
            excluded_non_novel += 1
            continue
        item_id = str(row.get("item_id", "")).strip()
        elapsed = _finite_float(row.get("days_since_first_attempt"))
        correct = _parse_bool(row.get("correct"))
        if not item_id or elapsed is None or elapsed < 0 or correct is None:
            raise ValueError(
                f"transfer row {row_number} needs item_id, non-negative days_since_first_attempt, and boolean correct"
            )
        valid_novel_rows += 1
        for bucket, target in TARGET_DAYS.items():
            if abs(elapsed - target) > tolerance_days:
                continue
            key = participant_slot, item_id
            previous = candidates[bucket].get(key)
            if previous is None or abs(elapsed - target) < abs(
                float(previous["days_since_first_attempt"]) - target
            ):
                candidates[bucket][key] = {
                    "days_since_first_attempt": elapsed,
                    "correct": correct,
                }

    measures: dict[str, Any] = {}
    for bucket, items in candidates.items():
        correct_count = sum(bool(row["correct"]) for row in items.values())
        measures[bucket] = {
            "window_days": [
                max(0.0, TARGET_DAYS[bucket] - tolerance_days),
                TARGET_DAYS[bucket] + tolerance_days,
            ],
            "n": len(items),
            "correct": correct_count,
            "accuracy": _rate(correct_count, len(items)),
        }
    has_results = any(measure["n"] for measure in measures.values())
    return {
        "status": "scored" if has_results else (
            "no_rows_in_target_windows" if valid_novel_rows else "not_collected"
        ),
        "measures": measures,
        "non_novel_rows_excluded": excluded_non_novel,
        "note": "Transfer rows must be pre-scored against novel physics problems.",
    }


def _parse_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().casefold()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    return None


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "progress_files", nargs="+", type=Path,
        help="Local course_progress.json files, one per participant.",
    )
    parser.add_argument("--output", required=True, type=Path, help="Aggregate JSON output path.")
    parser.add_argument("--as-of", help="UTC study cutoff (ISO datetime); defaults to now.")
    parser.add_argument(
        "--tolerance-days", type=float, default=1.0,
        help="Half-width of the day-1/day-7 observation windows (default: 1 day).",
    )
    parser.add_argument(
        "--transfer-csv", type=Path,
        help=(
            "Optional scored CSV with participant_slot,item_id,"
            "days_since_first_attempt,correct,novel columns."
        ),
    )
    args = parser.parse_args()
    if not math.isfinite(args.tolerance_days) or args.tolerance_days < 0:
        parser.error("--tolerance-days must be finite and non-negative")
    missing_progress = [path for path in args.progress_files if not path.is_file()]
    if missing_progress:
        parser.error(
            "course progress file not found: "
            + ", ".join(str(path) for path in missing_progress)
        )
    if args.transfer_csv is not None and not args.transfer_csv.is_file():
        parser.error("transfer CSV file not found: " + str(args.transfer_csv))
    try:
        as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00")) if args.as_of else None
    except ValueError:
        parser.error("--as-of must be an ISO datetime")
    participant_events = [
        CourseProgressStore(path).evaluation_events()
        for path in args.progress_files
    ]
    transfer_rows = None
    if args.transfer_csv is not None:
        with args.transfer_csv.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            required = {
                "participant_slot", "item_id", "days_since_first_attempt", "correct", "novel",
            }
            if not required.issubset(reader.fieldnames or []):
                parser.error(
                    "--transfer-csv must include columns: " + ", ".join(sorted(required))
                )
            transfer_rows = list(reader)
    try:
        report = analyze_participants(
            participant_events,
            as_of=as_of,
            tolerance_days=args.tolerance_days,
            transfer_rows=transfer_rows,
        )
    except ValueError as exc:
        parser.error(str(exc))
    atomic_write_json(args.output, report)
    print(f"Participants: {report['participant_count']}")
    print(
        "Due review return: "
        f"{report['due_return']['returned_items']}/{report['due_return']['eligible_items']}"
    )
    for name, measure in report["delayed_recall"].items():
        objective = measure["objective_mcq"]
        self_reported = measure["self_reported_open_response"]
        print(
            f"{name}: objective MCQ {objective['correct']}/{objective['n']}; "
            f"self-reported {self_reported['recalled']}/{self_reported['n']}"
        )
    transfer_7d = report["transfer"]["measures"]["day_7"]
    print(
        f"Transfer day 7: {transfer_7d['correct']}/{transfer_7d['n']} "
        f"({report['transfer']['status']}); saved {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
