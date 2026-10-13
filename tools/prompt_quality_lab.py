"""Prompt quality evaluation harness for AetherLab.

This is a lightweight layer above the real render pipeline and the visual
regression metrics. It answers a product question the unit suite cannot:
"did this prompt/exemplar/scoring change make our generated scenes better?"

Default runs are keyless/local and write only JSON, Markdown, CSV, and contact
sheets under `.analysis/prompt-quality-lab/`. Raw videos stay in the normal
render cache and are not copied into the report directory.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import math
import os
import sys
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / ".analysis" / "prompt-quality-lab"
# Committed, tracked baseline (NOT under the gitignored .analysis/). The gate
# ratchets fresh runs against this file so quality can only move up over time.
DEFAULT_BASELINE = ROOT / "tools" / "prompt_quality_baseline.json"
# How far the mean score may fall before the gate fails (render non-determinism
# tolerance). Pass-rate is not allowed to drop at all.
DEFAULT_SCORE_TOLERANCE = 0.5
HUMAN_REVIEW_AXES = ("legibility", "physics", "pacing", "teaching_value")
MIN_CALIBRATION_CASES = 8

CANONICAL_PROMPTS: list[dict[str, Any]] = [
    {
        "id": "pendulum",
        "mode": "solve",
        "quality": "l",
        "prompt": "Explain the small-angle pendulum and render the period dependence.",
    },
    {
        "id": "kepler_orbit",
        "mode": "solve",
        "quality": "l",
        "prompt": "Visualize Kepler's equal-area law for an elliptical orbit.",
    },
    {
        "id": "standing_wave",
        "mode": "solve",
        "quality": "l",
        "prompt": "Show a standing wave forming from two travelling waves on a string.",
    },
    {
        "id": "fourier_series",
        "mode": "solve",
        "quality": "l",
        "prompt": "Build intuition for Fourier series by adding sine harmonics.",
    },
    {
        "id": "em_field",
        "mode": "solve",
        "quality": "l",
        "prompt": "Animate electric field lines around a dipole.",
    },
    # ── Phase-0 golden-set expansion (Quality Flywheel) ─────────────────────
    # Six more solve prompts so the gated baseline spans the domains AetherLab
    # claims to serve (mechanics / waves / fields / orbital). Every prompt
    # renders in keyless template mode too, so the baseline is reproducible
    # without an API key.
    {
        "id": "projectile",
        "mode": "solve",
        "quality": "l",
        "prompt": "Show the parabolic trajectory of a projectile and its range.",
    },
    {
        "id": "collision",
        "mode": "solve",
        "quality": "l",
        "prompt": "Illustrate an elastic collision between two masses on a track.",
    },
    {
        "id": "doppler",
        "mode": "solve",
        "quality": "l",
        "prompt": "Visualize the Doppler effect for a moving sound source.",
    },
    {
        "id": "interference",
        "mode": "solve",
        "quality": "l",
        "prompt": "Show two-source interference producing a fringe pattern.",
    },
    {
        "id": "rc_circuit",
        "mode": "solve",
        "quality": "l",
        "prompt": "Animate the charging curve of an RC circuit over time.",
    },
    {
        "id": "escape_velocity",
        "mode": "solve",
        "quality": "l",
        "prompt": "Explain escape velocity by launching a body from a planet's surface.",
    },
    {
        "id": "lesson_kepler",
        "mode": "lesson",
        "quality": "l",
        "topic": "Kepler orbit",
        "audience": "undergrad",
    },
]

SECRET_ENV_KEYS = (
    "AETHERLAB_OPENAI_API_KEY",
    "OPENAI_API_KEY",
    "GPT_API_KEY",
    "DASHSCOPE_API_KEY",
    "AETHERLAB_GITHUB_TOKEN",
    "GITHUB_TOKEN",
    "AETHERLAB_RENDER_REPO",
    "CLOUD_RENDER_REPO",
    "AETHERLAB_PROVIDER",
    "AETHERLAB_QWEN_AUTOLOAD",
    "QWEN_SETTINGS_PATH",
)


def main(argv: list[str] | None = None) -> int:
    from aetherlab.core.console import configure_utf8_stdio

    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--prompts", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--compare", type=Path, default=None)
    parser.add_argument(
        "--human-review",
        type=Path,
        default=None,
        help="Join a completed human-review JSON file and report critic calibration.",
    )
    parser.add_argument(
        "--gate",
        action="store_true",
        help="Ratchet: fail (exit 2) if this run regresses the mean score beyond "
        "--score-tolerance or drops the render pass rate vs the committed baseline.",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE,
        help=f"Committed baseline summary.json for --gate (default {DEFAULT_BASELINE}).",
    )
    parser.add_argument(
        "--score-tolerance",
        type=float,
        default=DEFAULT_SCORE_TOLERANCE,
        help="How far the mean score may fall before --gate fails.",
    )
    parser.add_argument(
        "--allow-provider",
        action="store_true",
        help="Use configured LLM/vision providers. Reports still never write secrets.",
    )
    parser.add_argument(
        "--ab",
        action="store_true",
        help="Run the golden set twice (tournament ON vs OFF) and report the "
        "per-prompt score lift, win/tie/loss, and extra render cost. Meaningful "
        "only with --allow-provider (keyless renders never enter the tournament); "
        "provider runs without full vision/tournament evidence exit 2.",
    )
    args = parser.parse_args(argv)

    prompt_set = load_prompt_set(args.prompts)
    if args.limit:
        prompt_set = prompt_set[: max(0, args.limit)]
    args.out.mkdir(parents=True, exist_ok=True)
    if not args.allow_provider and not args.ab:
        harden_environment(args.out)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    if args.ab:
        return run_ab(prompt_set, args.out, allow_provider=args.allow_provider)

    started = datetime.now(timezone.utc)
    report = asyncio.run(run_prompt_lab(prompt_set, args.out, allow_provider=args.allow_provider))
    report["started_at"] = started.isoformat(timespec="seconds")
    report["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    report["compare"] = compare_lab_reports(args.compare, report) if args.compare else None
    if args.human_review:
        try:
            report["human_review"] = calibrate_human_review(report, args.human_review)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"Human review file is invalid: {exc}")
            return 3
    write_outputs(args.out, report)
    print(f"Prompt quality lab wrote {args.out}")
    print(
        f"Prompts: {len(report['cases'])}; failures: "
        f"{sum(1 for c in report['cases'] if c['status'] == 'fail')}; "
        f"mean score: {report['summary']['mean_score']:.2f}"
    )

    render_failed = any(c["status"] == "fail" for c in report["cases"])

    if args.gate:
        if not args.baseline.exists():
            print(f"GATE: no baseline at {args.baseline}; run once and commit it first.")
            return 3
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        gate = evaluate_gate(baseline, report, score_tolerance=args.score_tolerance)
        print(
            f"GATE: baseline mean {gate['baseline_mean']:.2f} -> run mean "
            f"{gate['report_mean']:.2f} (delta {gate['mean_delta']:+.2f}); "
            f"{'PASS' if gate['ok'] and not render_failed else 'FAIL'}"
        )
        for reason in gate["reasons"]:
            print(f"  - {reason}")
        if not gate["ok"]:
            return 2

    return 1 if render_failed else 0


def load_prompt_set(path: Path | None = None) -> list[dict[str, Any]]:
    prompts = json.loads(path.read_text(encoding="utf-8-sig")) if path else CANONICAL_PROMPTS
    if not isinstance(prompts, list):
        raise ValueError("prompt set must be a JSON list")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(prompts, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"prompt {index} must be an object")
        prompt_id = str(item.get("id", "")).strip()
        mode = str(item.get("mode", "")).strip()
        if not prompt_id or not prompt_id.replace("_", "").replace("-", "").isalnum():
            raise ValueError(f"prompt {index} has invalid id")
        if prompt_id in seen:
            raise ValueError(f"duplicate prompt id {prompt_id}")
        if mode not in {"solve", "lesson"}:
            raise ValueError(f"{prompt_id} has invalid mode {mode!r}")
        if mode == "solve" and not str(item.get("prompt", "")).strip():
            raise ValueError(f"{prompt_id} needs prompt text")
        if mode == "lesson" and not str(item.get("topic", "")).strip():
            raise ValueError(f"{prompt_id} needs topic")
        seen.add(prompt_id)
        out.append(dict(item))
    return out


def harden_environment(out_dir: Path) -> None:
    data_dir = out_dir / "data"
    for key in SECRET_ENV_KEYS:
        os.environ.pop(key, None)
    os.environ["AETHERLAB_DATA_DIR"] = str(data_dir)
    os.environ["AETHERLAB_CACHE_PATH"] = str(data_dir / "cache.sqlite3")
    os.environ["AETHERLAB_CHROMA_PATH"] = str(data_dir / "chroma")
    os.environ["AETHERLAB_LIBRARY_DIR"] = str(data_dir / "library")
    os.environ["AETHERLAB_RENDER_MODE"] = "local"
    os.environ["AETHERLAB_WEB_REFS"] = "0"
    os.environ["AETHERLAB_NARRATION"] = "0"
    os.environ["CLOUD_RENDER_ENABLED"] = "0"
    data_dir.mkdir(parents=True, exist_ok=True)


async def run_prompt_lab(
    prompt_set: list[dict[str, Any]],
    out_dir: Path,
    *,
    allow_provider: bool,
    settings_override: Any | None = None,
    state_dir: Path | None = None,
    tournament: bool | None = None,
) -> dict[str, Any]:
    from aetherlab.core.settings import load_settings
    from aetherlab.services.lesson_pipeline import LessonPipeline
    from aetherlab.services.pipeline import AetherLabPipeline

    settings = settings_override or load_settings()
    if state_dir is not None:
        settings = replace(
            settings,
            data_dir=state_dir,
            cache_path=state_dir / "cache.sqlite3",
            chroma_path=state_dir / "chroma",
            library_path=state_dir / "library",
        )
    if tournament is not None:
        settings = replace(settings, auto_tournament=tournament)
    if not allow_provider:
        settings = replace(
            settings,
            openai_api_key=None,
            openai_base_url=None,
            web_references=False,
            narration_enabled=False,
            render_mode="local",
            github_repo="",
            github_token="",
            fallback_api_key=None,
            fallback_base_url=None,
            fallback_llm_model=None,
            vision_model=None,
            auto_tournament=False,
            scene_candidates=1,
            visual_critic_max_passes=0,
            visual_critic_keyframes=0,
        )
    pipeline = AetherLabPipeline(settings)
    lesson_pipeline = LessonPipeline(settings)
    cases = []
    for index, prompt in enumerate(prompt_set, start=1):
        print(f"[{index}/{len(prompt_set)}] evaluate {prompt['id']}", flush=True)
        try:
            cases.append(await run_one_prompt(prompt, pipeline, lesson_pipeline, out_dir))
        except Exception as exc:  # noqa: BLE001
            cases.append({
                "id": prompt.get("id", f"prompt_{index}"),
                "mode": prompt.get("mode", ""),
                "status": "fail",
                "score": 0.0,
                "error": f"{type(exc).__name__}: {exc}",
            })
    return {
        "schema": "aetherlab.prompt_quality_lab.v1",
        "allow_provider": allow_provider,
        "configuration": {
            "render_mode": str(getattr(settings, "render_mode", "local")),
            "cloud_provider": str(getattr(settings, "cloud_provider", "")),
            "cloud_repository_configured": bool(getattr(settings, "github_repo", "")),
            "model": str(getattr(settings, "llm_model", "")),
            "vision_model": str(getattr(settings, "vision_model", "") or ""),
            "tournament": bool(getattr(settings, "auto_tournament", False)),
        },
        "cases": cases,
        "summary": summarize_cases(cases),
    }


# ── A/B: tournament ON vs OFF (Quality Flywheel "Prove It", F180) ────────────
# The flywheel's payoff claim is "the tournament produces better scenes." The
# gate only proves the keyless floor never regresses; it cannot prove a lift. The
# A/B harness runs the golden set twice with the tournament forced on and off, in
# ISOLATED data dirs (so the ON arm's learned exemplars/pitfalls never leak into
# the OFF arm), and reports the paired score lift and its render cost. Keyless it
# is a no-op comparison by construction — the report says so rather than pretend.
_AB_EPS = 0.05  # per-prompt score noise band: |delta| <= this counts as a tie
_AB_VISION_AXES = ("legibility", "composition", "palette", "structure", "substance")


def _isolate_arm_env(
    arm_dir: Path,
    *,
    tournament: bool,
    allow_provider: bool,
    state_dir: Path | None = None,
) -> None:
    """Point every state path at an arm-private data dir and set the tournament
    toggle, so neither arm nor a prior A/B run can contaminate this run."""
    data_dir = state_dir or (arm_dir / "data")
    data_dir.mkdir(parents=True, exist_ok=True)
    if not allow_provider:
        for key in SECRET_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["AETHERLAB_RENDER_MODE"] = "local"
        os.environ["AETHERLAB_WEB_REFS"] = "0"
        os.environ["AETHERLAB_NARRATION"] = "0"
        os.environ["CLOUD_RENDER_ENABLED"] = "0"
    os.environ["AETHERLAB_DATA_DIR"] = str(data_dir)
    os.environ["AETHERLAB_CACHE_PATH"] = str(data_dir / "cache.sqlite3")
    os.environ["AETHERLAB_CHROMA_PATH"] = str(data_dir / "chroma")
    os.environ["AETHERLAB_LIBRARY_DIR"] = str(data_dir / "library")
    os.environ["AETHERLAB_AUTO_TOURNAMENT"] = "1" if tournament else "0"


def _count_extra_renders(data_dir: Path) -> int:
    """Count renders beyond one candidate from this A/B arm's private ledger."""
    try:
        from tools.ledger_report import load_jobs

        jobs = load_jobs(data_dir / "render_ledger.json")
        return sum(max(0, len(j.get("candidates") or []) - 1) for j in jobs if j.get("candidates"))
    except Exception:  # noqa: BLE001 — a cost estimate must never fail the run
        return 0


def _valid_vision_critique(critique: Any) -> bool:
    """Return true only for a complete, bounded real vision-critic result."""
    if not isinstance(critique, dict) or critique.get("breakdown_source") != "vision":
        return False
    if critique.get("verdict") not in {"ship", "revise"}:
        return False
    score = critique.get("score")
    breakdown = critique.get("breakdown")
    if not _bounded_number(score, 0.0, 10.0) or not isinstance(breakdown, dict):
        return False
    return all(
        axis in breakdown
        and _bounded_number(breakdown[axis], 0.0, 2.0)
        for axis in _AB_VISION_AXES
    )


def _bounded_number(value: Any, lower: float, upper: float) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError):
        return False
    return math.isfinite(number) and lower <= number <= upper


def _provider_arm_evidence(report: dict[str, Any]) -> dict[str, int]:
    cases = report.get("cases", [])
    if not isinstance(cases, list):
        cases = []
    cases = [case for case in cases if isinstance(case, dict)]
    solve_cases = [case for case in cases if case.get("mode") == "solve"]
    vision_scored = sum(1 for case in solve_cases if _valid_vision_critique(case.get("critic")))
    return {
        "solve_cases": len(solve_cases),
        "passed": sum(1 for case in solve_cases if case.get("status") == "pass"),
        "vision_scored": vision_scored,
        "static_or_skipped": len(solve_cases) - vision_scored,
        "failures": sum(1 for case in cases if case.get("status") != "pass"),
    }


def _candidate_has_vision_score(candidate: dict[str, Any]) -> bool:
    # The ledger predates breakdown_source. Its only real-critic verdicts are
    # "ship" and "revise"; static proxy fallback is recorded as "skipped".
    if candidate.get("verdict") not in {"ship", "revise"}:
        return False
    return _valid_vision_critique({
        "breakdown_source": "vision",
        "verdict": candidate.get("verdict"),
        "score": candidate.get("score"),
        "breakdown": candidate.get("breakdown"),
    })


def _tournament_critic_evidence(data_dir: Path) -> dict[str, int]:
    """Count real-vision-ranked candidates in this isolated arm's ledger."""
    try:
        from tools.ledger_report import load_jobs

        jobs = load_jobs(data_dir / "render_ledger.json")
    except Exception:  # noqa: BLE001 — measurement diagnostics stay fail-soft
        jobs = []
    tournaments = [
        job for job in jobs
        if isinstance(job.get("candidates"), list) and job.get("candidates")
    ]
    candidates = [
        candidate
        for job in tournaments
        for candidate in job.get("candidates", [])
        if isinstance(candidate, dict)
    ]
    vision_scored = sum(1 for candidate in candidates if _candidate_has_vision_score(candidate))
    return {
        "tournaments": len(tournaments),
        "candidates": len(candidates),
        "vision_scored": vision_scored,
        "static_or_skipped": len(candidates) - vision_scored,
    }


def pair_ab_reports(on: dict[str, Any], off: dict[str, Any]) -> dict[str, Any]:
    """Pair two lab reports (tournament on/off) into a lift summary.

    Pure function — no I/O — so the paired math is unit tested without rendering
    or a provider key. ``on``/``off`` are the dicts ``run_prompt_lab`` returns
    (optionally carrying an ``extra_renders`` cost field on the ON arm).
    """
    on_cases = {c["id"]: c for c in on.get("cases", []) if isinstance(c, dict) and "id" in c}
    off_cases = {c["id"]: c for c in off.get("cases", []) if isinstance(c, dict) and "id" in c}
    ids = [i for i in on_cases if i in off_cases]  # on-arm order, intersection only
    unmatched_on = sorted(set(on_cases) - set(off_cases))
    unmatched_off = sorted(set(off_cases) - set(on_cases))

    per_prompt: list[dict[str, Any]] = []
    wins = ties = losses = 0
    for i in ids:
        on_s = float(on_cases[i].get("score", 0.0) or 0.0)
        off_s = float(off_cases[i].get("score", 0.0) or 0.0)
        delta = round(on_s - off_s, 3)
        if delta > _AB_EPS:
            wins += 1
        elif delta < -_AB_EPS:
            losses += 1
        else:
            ties += 1
        per_prompt.append({"id": i, "on": on_s, "off": off_s, "delta": delta})

    mean_on = round(sum(p["on"] for p in per_prompt) / len(ids), 3) if ids else 0.0
    mean_off = round(sum(p["off"] for p in per_prompt) / len(ids), 3) if ids else 0.0
    mean_lift = round(mean_on - mean_off, 3)
    extra = int(on.get("extra_renders", 0) or 0)
    pairing = {
        "schema": "aetherlab.prompt_quality_ab.v1",
        "n": len(ids),
        "unmatched_on": unmatched_on,
        "unmatched_off": unmatched_off,
        "mean_on": mean_on,
        "mean_off": mean_off,
        "mean_lift": mean_lift,
        "wins": wins,
        "ties": ties,
        "losses": losses,
        "extra_renders": extra,
        "per_prompt": per_prompt,
        "verdict": _ab_verdict(len(ids), mean_lift, wins, losses, extra),
    }
    # Preserve the pure/keyless F180 report contract for direct callers that do
    # not describe provider use. Real CLI reports always carry allow_provider.
    if "allow_provider" in on or "allow_provider" in off:
        provider_requested = bool(on.get("allow_provider") and off.get("allow_provider"))
        on_evidence = _provider_arm_evidence(on)
        off_evidence = _provider_arm_evidence(off)
        tournament = on.get("tournament_evidence")
        if not isinstance(tournament, dict):
            tournament = {"tournaments": 0, "candidates": 0, "vision_scored": 0, "static_or_skipped": 0}
        tournament = {
            key: max(0, int(tournament.get(key, 0) or 0))
            if str(tournament.get(key, 0) or 0).lstrip("+-").isdigit() else 0
            for key in ("tournaments", "candidates", "vision_scored", "static_or_skipped")
        }
        pairing["provider_requested"] = provider_requested
        pairing["provider_evidence"] = {
            "on": {
                **on_evidence,
                "configuration": on.get("configuration", {}),
                "tournament": tournament,
            },
            "off": {
                **off_evidence,
                "configuration": off.get("configuration", {}),
            },
        }
        pairing["raw_verdict"] = pairing["verdict"]

        reasons: list[str] = []
        if not provider_requested:
            reasons.append("--allow-provider was not enabled for both arms")
        if unmatched_on or unmatched_off:
            reasons.append("the arms did not produce the same prompt IDs")
        for arm, evidence in (("ON", on_evidence), ("OFF", off_evidence)):
            if evidence["failures"]:
                reasons.append(f"{arm} arm has {evidence['failures']} failed case(s)")
            if evidence["solve_cases"] == 0:
                reasons.append(f"{arm} arm has no solve cases")
            elif evidence["passed"] != evidence["solve_cases"]:
                reasons.append(f"{arm} arm has a failed solve case")
            elif evidence["vision_scored"] != evidence["solve_cases"]:
                reasons.append(
                    f"{arm} arm has real vision scores for {evidence['vision_scored']} of "
                    f"{evidence['solve_cases']} solve cases"
                )
        if tournament["tournaments"] == 0 or tournament["candidates"] == 0:
            reasons.append("the ON arm recorded no tournament candidates")
        elif tournament["vision_scored"] != tournament["candidates"]:
            reasons.append(
                f"only {tournament['vision_scored']} of {tournament['candidates']} ON-arm "
                "tournament candidates have real vision scores"
            )
        if extra <= 0:
            reasons.append("the ON arm spent no extra render, so no multi-candidate choice was measured")

        pairing["measurement_valid"] = not reasons
        pairing["validation_reasons"] = reasons
        if reasons:
            pairing["verdict"] = (
                "INVALID provider measurement: " + "; ".join(reasons) +
                ". The numeric lift is exploratory only; do not use it as evidence or a baseline."
            )
        else:
            pairing["verdict"] += (
                f" Provider evidence passed: all solve cases were vision-scored and the ON arm "
                f"vision-ranked {tournament['candidates']} candidate(s) across "
                f"{tournament['tournaments']} tournament(s), with {extra} extra render(s)."
            )
    return pairing


def _ab_verdict(n: int, mean_lift: float, wins: int, losses: int, extra: int) -> str:
    if n == 0:
        return "No comparable prompts across the two arms."
    if abs(mean_lift) <= _AB_EPS and wins == 0 and losses == 0:
        return (
            "No measurable difference: the arms are identical. This is expected "
            "keyless: single-shot renders never enter the tournament. Re-run with "
            "--allow-provider (a vision critic) to measure a real lift."
        )
    if mean_lift > _AB_EPS and wins >= losses:
        return (
            f"Tournament LIFTS mean score by {mean_lift:+} across {n} prompts "
            f"({wins} win / {losses} loss) at {extra} extra render(s). Worth committing "
            f"a provider baseline."
        )
    if mean_lift < -_AB_EPS and losses >= wins:
        return (
            f"Tournament did NOT help (mean {mean_lift:+}, {wins} win / {losses} loss). "
            f"Investigate the escalation threshold / critic rubric with ledger_report."
        )
    # Sign and per-prompt counts disagree (e.g. a positive mean driven by a few big
    # wins while more prompts slightly regressed) — never call that a failure; a
    # positive mean must never read as "did NOT help" (BUG-32). Send the reader to
    # the per-prompt deltas rather than force a verdict the numbers don't support.
    return (
        f"Mixed result: mean {mean_lift:+} across {n} prompts ({wins} win / {losses} loss) "
        f"at {extra} extra render(s) — inspect the per-prompt deltas before deciding."
    )


def run_ab(prompt_set: list[dict[str, Any]], out_dir: Path, *, allow_provider: bool) -> int:
    """Run both arms, write the paired report, and print the verdict."""
    from aetherlab.core.settings import load_settings

    # Read settings before exporting arm-local paths. The render/provider
    # configuration is shared; caches and ledgers remain isolated per arm.
    base_settings = load_settings()
    arms: dict[str, dict[str, Any]] = {}
    run_id = uuid.uuid4().hex[:12]
    for arm, on in (("on", True), ("off", False)):
        arm_dir = out_dir / f"ab_{arm}"
        arm_dir.mkdir(parents=True, exist_ok=True)
        state_dir = arm_dir / "runs" / run_id / "data"
        _isolate_arm_env(
            arm_dir,
            tournament=on,
            allow_provider=allow_provider,
            state_dir=state_dir,
        )
        print(f"== A/B arm: tournament {'ON' if on else 'OFF'} ==", flush=True)
        started = datetime.now(timezone.utc)
        report = asyncio.run(run_prompt_lab(
            prompt_set,
            arm_dir,
            allow_provider=allow_provider,
            settings_override=base_settings,
            state_dir=state_dir,
            tournament=on,
        ))
        report["started_at"] = started.isoformat(timespec="seconds")
        report["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        report["auto_tournament"] = on
        report["ab_run_id"] = run_id
        report["extra_renders"] = _count_extra_renders(state_dir)
        report["tournament_evidence"] = _tournament_critic_evidence(state_dir)
        write_outputs(arm_dir, report)
        arms[arm] = report

    pairing = pair_ab_reports(arms["on"], arms["off"])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ab_summary.json").write_text(
        json.dumps(pairing, indent=2), encoding="utf-8", newline="\n"
    )
    (out_dir / "ab_summary.md").write_text(render_ab_markdown(pairing), encoding="utf-8", newline="\n")
    print(
        f"A/B: tournament ON mean {pairing['mean_on']:.2f} vs OFF {pairing['mean_off']:.2f} "
        f"(lift {pairing['mean_lift']:+.2f}); {pairing['wins']}W/{pairing['ties']}T/{pairing['losses']}L; "
        f"+{pairing['extra_renders']} render(s)"
    )
    print(pairing["verdict"])
    render_failed = any(
        c.get("status") == "fail" for report in arms.values() for c in report.get("cases", [])
    )
    if render_failed:
        return 1
    if pairing.get("provider_requested") and not pairing.get("measurement_valid"):
        return 2
    return 0


def render_ab_markdown(pairing: dict[str, Any]) -> str:
    lines = [
        "# AetherLab Prompt Quality — Tournament A/B",
        "",
        f"- Prompts compared: {pairing['n']}",
        f"- Mean score: ON {pairing['mean_on']} vs OFF {pairing['mean_off']} "
        f"(**lift {pairing['mean_lift']:+}**)",
        f"- Win / tie / loss: {pairing['wins']} / {pairing['ties']} / {pairing['losses']}",
        f"- Extra renders (tournament cost): {pairing['extra_renders']}",
    ]
    if pairing.get("provider_requested"):
        evidence = pairing.get("provider_evidence", {})
        on = evidence.get("on", {})
        off = evidence.get("off", {})
        on_config = on.get("configuration", {})
        off_config = off.get("configuration", {})
        tournament = on.get("tournament", {})
        lines.extend([
            f"- Render mode: ON {on_config.get('render_mode', 'unknown')}; "
            f"OFF {off_config.get('render_mode', 'unknown')}",
            f"- Vision model: ON {on_config.get('vision_model') or 'not configured'}; "
            f"OFF {off_config.get('vision_model') or 'not configured'}",
            f"- Provider measurement: **{'VALID' if pairing.get('measurement_valid') else 'INVALID'}**",
            f"- Real vision coverage: ON {on.get('vision_scored', 0)}/{on.get('solve_cases', 0)}; "
            f"OFF {off.get('vision_scored', 0)}/{off.get('solve_cases', 0)} solve cases",
            f"- ON tournament vision coverage: {tournament.get('vision_scored', 0)}/"
            f"{tournament.get('candidates', 0)} candidates across {tournament.get('tournaments', 0)} tournament(s)",
        ])
    elif "measurement_valid" in pairing:
        lines.append("- Provider measurement: not requested (keyless result is not a quality-lift measurement)")
    lines.extend([
        "",
        f"**Verdict:** {pairing['verdict']}",
    ])
    if pairing.get("raw_verdict") and not pairing.get("measurement_valid"):
        lines.extend(["", f"Exploratory numeric verdict: {pairing['raw_verdict']}"])
    lines.extend([
        "",
        "| Prompt | ON | OFF | Delta |",
        "|---|---:|---:|---:|",
    ])
    for p in pairing["per_prompt"]:
        lines.append(f"| {p['id']} | {p['on']} | {p['off']} | {p['delta']:+} |")
    return "\n".join(lines) + "\n"


async def run_one_prompt(
    prompt: dict[str, Any],
    pipeline: Any,
    lesson_pipeline: Any,
    out_dir: Path,
) -> dict[str, Any]:
    from aetherlab.core.models import ProblemRequest
    from tools.visual_regression import audit_video, public_path, quality_failures

    mode = prompt["mode"]
    if mode == "lesson":
        bundle = await lesson_pipeline.run(
            str(prompt["topic"]),
            audience=str(prompt.get("audience", "undergrad")),
            quality=str(prompt.get("quality", "l")),
            max_concurrent=1,
        )
        if not bundle.video_path:
            raise RuntimeError(f"lesson did not produce video; status={bundle.status}")
        metrics = audit_video(
            Path(bundle.video_path),
            out_dir,
            str(prompt["id"]),
            getattr(bundle, "srt_path", ""),
        )
        case = {
            "id": prompt["id"],
            "mode": "lesson",
            "prompt": str(prompt["topic"]),
            "quality": str(prompt.get("quality", "l")),
            "status": "pass",
            "storyboard": {"present": False, "act_count": 0},
            "critic": {"score": 0.0, "verdict": "skipped", "issues": []},
            "artifact": {"video_path": public_path(Path(bundle.video_path))},
            "metrics": metrics,
        }
    else:
        request = ProblemRequest(
            prompt=str(prompt["prompt"]),
            session_id=f"prompt-quality-{prompt['id']}",
        )
        result = await pipeline.run(request)
        scene = result.scene
        if not scene.video_path:
            raise RuntimeError(f"scene did not produce video; status={scene.status}")
        metrics = audit_video(Path(scene.video_path), out_dir, str(prompt["id"]))
        case = {
            "id": prompt["id"],
            "mode": "solve",
            "prompt": str(prompt["prompt"]),
            "quality": str(prompt.get("quality", "l")),
            "status": "pass",
            "storyboard": storyboard_summary(scene.storyboard),
            "critic": critic_summary(scene),
            "artifact": {
                "video_path": public_path(Path(scene.video_path)),
                "class_name": scene.class_name,
                "engine": scene.engine,
            },
            "metrics": metrics,
        }
    case["quality_failures"] = quality_failures({"kind": case["mode"], "metrics": case["metrics"]})
    case["score"] = score_case(case)
    return case


def storyboard_summary(storyboard: dict | None) -> dict[str, Any]:
    if not isinstance(storyboard, dict):
        return {"present": False, "act_count": 0, "duration_s": 0.0, "has_hero_frame": False}
    acts = storyboard.get("acts", [])
    if not isinstance(acts, list):
        acts = []
    duration = 0.0
    for act in acts:
        if isinstance(act, dict):
            duration += float(act.get("duration_s", 0.0) or 0.0)
    return {
        "present": True,
        "act_count": len([a for a in acts if isinstance(a, dict)]),
        "duration_s": round(duration, 3),
        "has_hero_frame": bool(storyboard.get("hero_frame")),
    }


def critic_summary(scene: Any) -> dict[str, Any]:
    # Per-axis breakdown for visibility (F170). When the scene carries a real
    # vision breakdown, surface it; otherwise (keyless/offline — the golden set's
    # default) attach the static proxy so reports still show per-axis quality.
    # This is INFORMATIONAL ONLY: `score` stays the persisted vision score, so
    # score_case() and the committed --gate baseline are unaffected.
    breakdown = {str(k): float(v) for k, v in (getattr(scene, "critique_breakdown", {}) or {}).items()}
    source = "vision" if breakdown else ""
    if not breakdown:
        try:
            from aetherlab.services.scene_critic import static_quality_estimate

            est = static_quality_estimate(str(getattr(scene, "code", "") or ""))
            breakdown, source = est.breakdown, est.breakdown_source
        except Exception:  # noqa: BLE001 — report enrichment must never fail a run
            breakdown, source = {}, ""
    return {
        "score": float(getattr(scene, "quality_score", 0.0) or 0.0),
        "verdict": str(getattr(scene, "critique_verdict", "") or "skipped"),
        "issues": [str(i) for i in getattr(scene, "critique_issues", []) or []],
        "breakdown": breakdown,
        "breakdown_source": source,
    }


def score_case(case: dict[str, Any]) -> float:
    if case.get("status") != "pass":
        return 0.0
    metrics = case.get("metrics", {})
    duration = float(metrics.get("duration", 0.0) or 0.0)
    fps = float(metrics.get("fps", 0.0) or 0.0)
    blank = float(metrics.get("blank_ratio", 0.0) or 0.0)
    static = float(metrics.get("static_ratio", 0.0) or 0.0)
    critic = float((case.get("critic") or {}).get("score", 0.0) or 0.0)
    score = 5.0
    if duration >= 8.0:
        score += 1.0
    elif duration < 2.0:
        score -= 2.0
    if fps >= 20.0:
        score += 0.75
    if (case.get("storyboard") or {}).get("present"):
        score += 0.75
    score -= min(blank * 8.0, 2.0)
    score -= min(static * 4.0, 2.0)
    score -= len(case.get("quality_failures", []) or []) * 1.25
    if critic > 0:
        score = (score + critic) / 2.0
    return round(max(0.0, min(10.0, score)), 3)


def summarize_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [float(c.get("score", 0.0) or 0.0) for c in cases]
    passed = [c for c in cases if c.get("status") == "pass"]
    return {
        "case_count": len(cases),
        "pass_count": len(passed),
        "fail_count": len(cases) - len(passed),
        "mean_score": round(sum(scores) / len(scores), 3) if scores else 0.0,
        "quality_failure_count": sum(len(c.get("quality_failures", []) or []) for c in cases),
    }


def compare_lab_reports(compare_dir: Path | None, report: dict[str, Any]) -> dict[str, Any] | None:
    if compare_dir is None:
        return None
    baseline = compare_dir / "summary.json"
    if not baseline.exists():
        return None
    previous = json.loads(baseline.read_text(encoding="utf-8"))
    old = {c["id"]: c for c in previous.get("cases", []) if isinstance(c, dict) and "id" in c}
    deltas = []
    regressions = 0
    for case in report.get("cases", []):
        prior = old.get(case.get("id"))
        if not prior:
            continue
        old_score = float(prior.get("score", 0.0) or 0.0)
        new_score = float(case.get("score", 0.0) or 0.0)
        score_delta = round(new_score - old_score, 3)
        reasons = []
        if score_delta < -1.0:
            reasons.append(f"score dropped {old_score:.2f} -> {new_score:.2f}")
        old_duration = float((prior.get("metrics") or {}).get("duration", 0.0) or 0.0)
        new_duration = float((case.get("metrics") or {}).get("duration", 0.0) or 0.0)
        if old_duration > 0 and new_duration < old_duration * 0.75:
            reasons.append(f"duration dropped {old_duration:.1f}s -> {new_duration:.1f}s")
        regressions += len(reasons)
        deltas.append({
            "id": case.get("id"),
            "score_delta": score_delta,
            "duration_delta": round(new_duration - old_duration, 3),
            "regressions": reasons,
        })
    return {"baseline": str(baseline), "deltas": deltas, "regression_count": regressions}


def evaluate_gate(
    baseline: dict[str, Any],
    report: dict[str, Any],
    *,
    score_tolerance: float = DEFAULT_SCORE_TOLERANCE,
) -> dict[str, Any]:
    """The release ratchet (flywheel step 7): compare a fresh report to a
    committed baseline. A release may not drop the mean critic/quality score by
    more than ``score_tolerance`` (render non-determinism headroom), and may not
    drop the render pass rate at all. Pure function — no I/O — so it is unit
    testable without rendering anything.

    Returns ``{ok, reasons, mean_delta, pass_delta, baseline_mean, report_mean}``.
    """
    b = baseline.get("summary", {}) or {}
    r = report.get("summary", {}) or {}
    b_mean = float(b.get("mean_score", 0.0) or 0.0)
    r_mean = float(r.get("mean_score", 0.0) or 0.0)
    mean_delta = round(r_mean - b_mean, 3)

    b_cases = int(b.get("case_count", 0) or 0)
    r_cases = int(r.get("case_count", 0) or 0)
    b_pass = (int(b.get("pass_count", 0) or 0) / b_cases) if b_cases else 0.0
    r_pass = (int(r.get("pass_count", 0) or 0) / r_cases) if r_cases else 0.0
    pass_delta = round(r_pass - b_pass, 4)

    reasons: list[str] = []
    baseline_ids = {
        str(case.get("id")) for case in baseline.get("cases", [])
        if isinstance(case, dict) and case.get("id")
    }
    report_ids = {
        str(case.get("id")) for case in report.get("cases", [])
        if isinstance(case, dict) and case.get("id")
    }
    if baseline_ids and report_ids and baseline_ids != report_ids:
        missing = sorted(baseline_ids - report_ids)
        extra = sorted(report_ids - baseline_ids)
        reasons.append(
            "golden-set prompt IDs changed "
            f"(missing: {', '.join(missing) or 'none'}; extra: {', '.join(extra) or 'none'})"
        )
    tol = abs(float(score_tolerance))
    if mean_delta < -tol:
        reasons.append(
            f"mean score regressed {b_mean:.2f} -> {r_mean:.2f} "
            f"(delta {mean_delta:+.2f}, tolerance {tol:.2f})"
        )
    if pass_delta < -1e-9:
        reasons.append(f"render pass rate dropped {b_pass:.0%} -> {r_pass:.0%}")
    return {
        "ok": not reasons,
        "reasons": reasons,
        "mean_delta": mean_delta,
        "pass_delta": pass_delta,
        "baseline_mean": round(b_mean, 3),
        "report_mean": round(r_mean, 3),
    }


def calibrate_human_review(report: dict[str, Any], path: Path) -> dict[str, Any]:
    """Attach complete human ratings and compare critic ranks conservatively."""
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict) or payload.get("schema") != "aetherlab.human_review.v1":
        raise ValueError("expected schema aetherlab.human_review.v1")
    review_rows = payload.get("cases")
    if not isinstance(review_rows, list):
        raise ValueError("cases must be a list")
    reviews = {
        str(row.get("id")): row for row in review_rows
        if isinstance(row, dict) and str(row.get("id", "")).strip()
    }
    reviewed = []
    critic_reviewed = []
    for case in report.get("cases", []):
        row = reviews.get(str(case.get("id", "")))
        ratings = row.get("ratings") if isinstance(row, dict) else None
        values = {}
        if isinstance(ratings, dict):
            for axis in HUMAN_REVIEW_AXES:
                value = ratings.get(axis)
                if isinstance(value, (int, float)) and not isinstance(value, bool) and 1 <= value <= 5:
                    values[axis] = float(value)
        if len(values) == len(HUMAN_REVIEW_AXES):
            mean = round(sum(values.values()) / len(HUMAN_REVIEW_AXES), 3)
            case["human_review"] = {"ratings": values, "mean": mean}
            critic = float((case.get("critic") or {}).get("score", 0.0) or 0.0)
            reviewed.append((str(case.get("id")), mean, critic))
            if critic > 0:
                critic_reviewed.append((mean, critic))
        else:
            case["human_review"] = None

    correlation = None
    if len(critic_reviewed) >= MIN_CALIBRATION_CASES:
        correlation = round(
            _spearman([r[0] for r in critic_reviewed], [r[1] for r in critic_reviewed]), 3
        )
    return {
        "reviewed_count": len(reviewed),
        "critic_comparable_count": len(critic_reviewed),
        "required_for_calibration": MIN_CALIBRATION_CASES,
        "critic_human_spearman": correlation,
        "calibration_status": (
            "ready_for_review" if correlation is not None else "insufficient_vision_scored_reviews"
        ),
        "axes": list(HUMAN_REVIEW_AXES),
    }


def _spearman(left: list[float], right: list[float]) -> float:
    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=values.__getitem__)
        out = [0.0] * len(values)
        start = 0
        while start < len(order):
            end = start + 1
            while end < len(order) and values[order[end]] == values[order[start]]:
                end += 1
            rank = (start + 1 + end) / 2.0
            for position in order[start:end]:
                out[position] = rank
            start = end
        return out

    if len(left) != len(right) or len(left) < 2:
        return 0.0
    a, b = ranks(left), ranks(right)
    am, bm = sum(a) / len(a), sum(b) / len(b)
    numerator = sum((x - am) * (y - bm) for x, y in zip(a, b, strict=True))
    denominator = (
        sum((x - am) ** 2 for x in a) * sum((y - bm) ** 2 for y in b)
    ) ** 0.5
    return numerator / denominator if denominator else 0.0


def write_outputs(out_dir: Path, report: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    (out_dir / "summary.md").write_text(render_markdown(report), encoding="utf-8", newline="\n")
    write_csv(out_dir / "scores.csv", report)


def write_csv(path: Path, report: dict[str, Any]) -> None:
    fields = ["id", "mode", "status", "score", "duration", "fps", "storyboard_acts", "critic_score", "contact_sheet"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for case in report.get("cases", []):
            metrics = case.get("metrics", {})
            writer.writerow({
                "id": case.get("id", ""),
                "mode": case.get("mode", ""),
                "status": case.get("status", ""),
                "score": case.get("score", ""),
                "duration": metrics.get("duration", ""),
                "fps": metrics.get("fps", ""),
                "storyboard_acts": (case.get("storyboard") or {}).get("act_count", ""),
                "critic_score": (case.get("critic") or {}).get("score", ""),
                "contact_sheet": metrics.get("contact_sheet", ""),
            })


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# AetherLab Prompt Quality Lab",
        "",
        f"- Started: {report.get('started_at', '')}",
        f"- Finished: {report.get('finished_at', '')}",
        f"- Mean score: {report.get('summary', {}).get('mean_score', 0)}",
    ]
    configuration = report.get("configuration")
    if isinstance(configuration, dict):
        lines.extend([
            f"- Render mode: {configuration.get('render_mode', 'unknown')}",
            f"- Vision model: {configuration.get('vision_model') or 'not configured'}",
            f"- Tournament: {'on' if configuration.get('tournament') else 'off'}",
        ])
    lines.extend([
        "",
        "| Prompt | Mode | Status | Score | Duration | FPS | Storyboard | Critic | Contact |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ])
    for case in report.get("cases", []):
        metrics = case.get("metrics", {})
        story = case.get("storyboard") or {}
        critic = case.get("critic") or {}
        lines.append(
            "| {id} | {mode} | {status} | {score} | {duration} | {fps} | {acts} | {critic} | {contact} |".format(
                id=case.get("id", ""),
                mode=case.get("mode", ""),
                status=case.get("status", ""),
                score=case.get("score", ""),
                duration=metrics.get("duration", ""),
                fps=metrics.get("fps", ""),
                acts=story.get("act_count", ""),
                critic=critic.get("score", ""),
                contact=metrics.get("contact_sheet", ""),
            )
        )
    compare = report.get("compare")
    if compare:
        lines.extend(["", "## Comparison", ""])
        for delta in compare.get("deltas", []):
            lines.append(
                f"- {delta['id']}: score {delta['score_delta']:+.3f}, "
                f"duration {delta['duration_delta']:+.3f}s"
            )
    human = report.get("human_review")
    if human:
        lines.extend([
            "", "## Human Review Calibration", "",
            f"- Fully reviewed cases: {human.get('reviewed_count', 0)}",
            f"- Vision-scored cases: {human.get('critic_comparable_count', 0)}",
            f"- Status: {human.get('calibration_status', 'unknown')}",
            f"- Critic / human Spearman correlation: {human.get('critic_human_spearman')}",
        ])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
