"""Mine the render-farm ledger for offline signal about the quality flywheel.

The tournament records, on every solve, a ledger entry (services/render_ledger)
carrying the per-candidate DRAFT critic scores, the winner, the difficulty/budget
that governed the fan-out, and — once the repair loop re-critiques the winner at
HQ — the winner's FINAL HQ score. That data has been accumulating silently. This
tool reads it (never writes, never renders) and answers the questions the flywheel
could previously only reason about:

* **Is the fan-out worth it?** How often do we escalate, and when we do, how much
  does the winner actually beat the runner-up (the *margin*)? A tournament whose
  winners barely edge their losers is paying for renders that buy little.
* **Does the cheap draft proxy predict reality?** The winner is SELECTED on a 480p
  draft score but SHIPS at HQ. If those correlate, the cheap signal is trustworthy
  (the BUG-31 concern, now measurable); if the HQ score is systematically lower,
  the draft score is optimistic and the escalation threshold is miscalibrated.
* **Where should "losers teach" aim?** Which rubric axis is weakest across renders.

Design (mirrors the other flywheel leaves): **standard library only**, **read-only**,
**fail-soft** — a missing or corrupt ledger yields an empty report, never a crash.

    python tools/ledger_report.py [--ledger PATH] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# Difficulty-bucket edges for the spend report (storyboard_difficulty is [0,1]).
_DIFF_BUCKETS = (("easy", 0.0, 0.34), ("medium", 0.34, 0.67), ("hard", 0.67, 1.01))
# A winner margin at/below this over the runner-up means the fan-out changed little.
_TIE_MARGIN = 0.25
# Rubric axes, kept in step with scene_critic.CRITIC_AXES without importing it (so
# this stays a stdlib-only leaf); validated defensively against whatever is stored.
_AXES = ("legibility", "composition", "palette", "structure", "substance")


# ── pure aggregation (no I/O — unit tested on synthetic job dicts) ───────────
def _is_tournament(job: dict) -> bool:
    return bool(job.get("candidates"))


def _winner_draft(job: dict) -> dict | None:
    """The winning candidate's recorded DRAFT entry, or None."""
    idx = job.get("winner_index")
    if idx is None:
        return None
    for cand in job.get("candidates") or []:
        if int(cand.get("index", -1)) == int(idx):
            return cand
    return None


def _mean(xs: list[float]) -> float:
    return round(sum(xs) / len(xs), 3) if xs else 0.0


def _median(xs: list[float]) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    mid = len(s) // 2
    return round((s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2.0), 3)


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    """Pearson correlation, or None when it is undefined (n<2 or zero variance)."""
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx <= 1e-12 or syy <= 1e-12:
        return None
    return round(sxy / (sxx ** 0.5 * syy ** 0.5), 3)


def _bucket(difficulty: float) -> str:
    for name, lo, hi in _DIFF_BUCKETS:
        if lo <= difficulty < hi:
            return name
    return "hard"


def summarize_ledger(jobs: list[dict]) -> dict[str, Any]:
    """Aggregate a list of ledger job dicts into flywheel-observability metrics.

    Pure function: no file, clock, or import side effects, so it is fully unit
    testable on synthetic records.
    """
    jobs = [j for j in jobs if isinstance(j, dict)]
    tournaments = [j for j in jobs if _is_tournament(j)]
    escalated = [j for j in tournaments if len(j.get("candidates") or []) > 1]

    # Candidate-count histogram across tournaments.
    hist: dict[str, int] = {}
    for j in tournaments:
        hist[str(len(j.get("candidates") or []))] = hist.get(str(len(j.get("candidates") or [])), 0) + 1

    # Winner margin over the best losing candidate (only where a fan-out happened).
    margins: list[float] = []
    for j in escalated:
        win = _winner_draft(j)
        if win is None:
            continue
        others = [float(c.get("score", 0.0) or 0.0)
                  for c in j.get("candidates") or [] if c is not win
                  and int(c.get("index", -1)) != int(j.get("winner_index", -2))]
        if others:
            margins.append(round(float(win.get("score", 0.0) or 0.0) - max(others), 3))
    ties = sum(1 for m in margins if m <= _TIE_MARGIN)

    # Draft->HQ pairs: the winner's cheap draft score vs its final HQ critic score.
    draft_scores: list[float] = []
    hq_scores: list[float] = []
    for j in tournaments:
        hq = float(j.get("winner_hq_score", 0.0) or 0.0)
        win = _winner_draft(j)
        if hq > 0.0 and win is not None:
            draft_scores.append(float(win.get("score", 0.0) or 0.0))
            hq_scores.append(hq)
    biases = [round(h - d, 3) for d, h in zip(draft_scores, hq_scores)]
    draft_hq = {
        "n": len(hq_scores),
        "pearson_r": _pearson(draft_scores, hq_scores),
        "mean_draft": _mean(draft_scores),
        "mean_hq": _mean(hq_scores),
        "mean_bias_hq_minus_draft": _mean(biases),
        # A negative bias means the draft score is optimistic: scenes look worse at
        # HQ than the tournament thought when it picked them.
        "draft_optimistic": bool(biases) and _mean(biases) < -0.5,
    }

    # Spend by difficulty bucket: did we actually spend more renders on harder scenes?
    by_bucket: dict[str, dict[str, Any]] = {}
    for name, _lo, _hi in _DIFF_BUCKETS:
        rows = [j for j in tournaments if _bucket(float(j.get("difficulty", 0.0) or 0.0)) == name]
        if not rows:
            continue
        by_bucket[name] = {
            "tournaments": len(rows),
            "mean_candidates": _mean([float(len(j.get("candidates") or [])) for j in rows]),
            "mean_winner_score": _mean([
                float((_winner_draft(j) or {}).get("score", 0.0) or 0.0) for j in rows
            ]),
        }

    # Weakest rubric axis across all recorded candidate breakdowns.
    axis_totals: dict[str, list[float]] = {a: [] for a in _AXES}
    for j in tournaments:
        for cand in j.get("candidates") or []:
            bd = cand.get("breakdown") or {}
            for a in _AXES:
                if a in bd:
                    axis_totals[a].append(float(bd.get(a, 0.0) or 0.0))
    axis_means = {a: _mean(v) for a, v in axis_totals.items() if v}
    weakest_axis = min(axis_means, key=axis_means.get) if axis_means else ""

    # Verdict mix across candidates (ship/revise/skipped) — keyless renders are
    # "skipped" (static proxy), so this also reports how much keyed signal exists.
    verdicts: dict[str, int] = {}
    for j in tournaments:
        for cand in j.get("candidates") or []:
            v = str(cand.get("verdict", "") or "unknown")
            verdicts[v] = verdicts.get(v, 0) + 1

    fallbacks = sum(1 for j in jobs if j.get("status") == "fallback_local")
    failures = sum(1 for j in jobs if j.get("status") == "failed")

    telemetry_rows = [
        j for j in jobs if isinstance(j.get("metrics"), dict) and j.get("metrics")
    ]
    by_backend: dict[str, list[dict[str, Any]]] = {}
    for job in telemetry_rows:
        metrics = job.get("metrics") or {}
        backend = str(metrics.get("backend") or job.get("backend") or "unknown")
        by_backend.setdefault(backend, []).append(metrics)

    def metric_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
        fields = (
            "prepare_seconds", "upload_seconds", "dispatch_seconds",
            "queue_seconds", "worker_seconds", "download_seconds",
            "render_wall_seconds", "peak_rss_mb", "total_seconds",
            "quality_score", "retry_count", "cache_hits",
        )
        summary: dict[str, Any] = {"samples": len(rows)}
        for field in fields:
            values = []
            for row in rows:
                try:
                    value = float(row.get(field))
                except (TypeError, ValueError):
                    continue
                if value == value and abs(value) != float("inf"):
                    values.append(value)
            if values:
                summary[f"mean_{field}"] = _mean(values)
        return summary

    by_renderer: dict[str, int] = {}
    for job in telemetry_rows:
        renderer = str((job.get("metrics") or {}).get("manim_renderer") or "unknown")
        by_renderer[renderer] = by_renderer.get(renderer, 0) + 1
    cache_enabled = [
        (job.get("metrics") or {}) for job in telemetry_rows
        if bool((job.get("metrics") or {}).get("repair_cache"))
    ]
    cache_disabled = [
        (job.get("metrics") or {}) for job in telemetry_rows
        if "repair_cache" in (job.get("metrics") or {})
        and not bool((job.get("metrics") or {}).get("repair_cache"))
    ]
    cache_hits = [
        int(row.get("cache_hits", 0) or 0) for row in cache_enabled
    ]
    telemetry = {
        "jobs_with_metrics": len(telemetry_rows),
        "by_backend": {
            backend: metric_summary(rows) for backend, rows in sorted(by_backend.items())
        },
        "by_renderer": dict(sorted(by_renderer.items())),
        "repair_cache": {
            "jobs_enabled": len(cache_enabled),
            "jobs_with_hits": sum(1 for value in cache_hits if value > 0),
            "total_segment_hits": sum(cache_hits),
            "mean_render_wall_enabled_seconds": metric_summary(cache_enabled).get(
                "mean_render_wall_seconds", 0.0
            ),
            "mean_render_wall_disabled_seconds": metric_summary(cache_disabled).get(
                "mean_render_wall_seconds", 0.0
            ),
        },
    }

    return {
        "schema": "aetherlab.ledger_report.v1",
        "totals": {
            "jobs": len(jobs),
            "tournaments": len(tournaments),
            "escalated": len(escalated),
            "escalation_rate": round(len(escalated) / len(tournaments), 3) if tournaments else 0.0,
            "fallbacks": fallbacks,
            "failures": failures,
            "fallback_rate": round(fallbacks / len(jobs), 3) if jobs else 0.0,
            "failure_rate": round(failures / len(jobs), 3) if jobs else 0.0,
        },
        "telemetry": telemetry,
        "candidate_histogram": dict(sorted(hist.items(), key=lambda kv: int(kv[0]))),
        "winner_margin": {
            "n": len(margins),
            "mean": _mean(margins),
            "median": _median(margins),
            "min": round(min(margins), 3) if margins else 0.0,
            "max": round(max(margins), 3) if margins else 0.0,
            "tie_count": ties,
            "tie_rate": round(ties / len(margins), 3) if margins else 0.0,
        },
        "draft_vs_hq": draft_hq,
        "spend_by_difficulty": by_bucket,
        "axis_means": axis_means,
        "weakest_axis": weakest_axis,
        "verdict_mix": verdicts,
    }


# ── I/O + CLI (fail-soft) ────────────────────────────────────────────────────
def load_jobs(path: Path) -> list[dict]:
    """Read a ledger file, returning [] on absence/corruption (never raises)."""
    try:
        if not path or not Path(path).exists():
            return []
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return [j for j in data if isinstance(j, dict)] if isinstance(data, list) else []
    except Exception:  # noqa: BLE001 — a report tool must never crash on bad input
        return []


def default_ledger_path() -> Path:
    """Best-effort location of the live ledger (settings data dir, else env)."""
    try:
        from aetherlab.core.settings import load_settings

        return Path(load_settings().data_dir) / "render_ledger.json"
    except Exception:  # noqa: BLE001 — stdlib fallback when the app isn't importable
        base = os.getenv("AETHERLAB_DATA_DIR") or str(Path.home() / ".aetherlab")
        return Path(base) / "render_ledger.json"


def render_report(summary: dict[str, Any], source: Path) -> str:
    t = summary.get("totals", {})
    margin = summary.get("winner_margin", {})
    dh = summary.get("draft_vs_hq", {})
    lines = [
        "AetherLab render-ledger report",
        f"  source: {source}",
        "",
        f"  jobs recorded ......... {t.get('jobs', 0)}",
        f"  tournaments ........... {t.get('tournaments', 0)}"
        f"  (escalated {t.get('escalated', 0)}, rate {t.get('escalation_rate', 0.0):.0%})",
        f"  fallback / failure .... {t.get('fallbacks', 0)} / {t.get('failures', 0)}"
        f"  (rates {t.get('fallback_rate', 0.0):.0%} / {t.get('failure_rate', 0.0):.0%})",
        "",
        "  Is the fan-out worth it? (winner margin over the runner-up)",
        f"    samples ............. {margin.get('n', 0)}",
        f"    mean / median ....... {margin.get('mean', 0.0)} / {margin.get('median', 0.0)}",
        f"    ties (<= {_TIE_MARGIN}) ...... {margin.get('tie_count', 0)}"
        f"  ({margin.get('tie_rate', 0.0):.0%} of fan-outs barely moved the winner)",
        "",
        "  Does the cheap draft score predict the shipped HQ score?",
        f"    paired samples ...... {dh.get('n', 0)}",
        f"    pearson r ........... {dh.get('pearson_r')}",
        f"    mean draft -> HQ .... {dh.get('mean_draft', 0.0)} -> {dh.get('mean_hq', 0.0)}"
        f"  (bias {dh.get('mean_bias_hq_minus_draft', 0.0):+})",
    ]
    if dh.get("draft_optimistic"):
        lines.append("    ! draft scores look OPTIMISTIC vs HQ — review the escalation threshold")
    if summary.get("weakest_axis"):
        lines += ["", f"  weakest rubric axis ... {summary['weakest_axis']}  (losers-teach target)"]
    spend = summary.get("spend_by_difficulty", {})
    if spend:
        lines += ["", "  spend by difficulty (mean candidates / mean winner score):"]
        for name, row in spend.items():
            lines.append(
                f"    {name:<7} {row['tournaments']:>3} tourn  "
                f"{row['mean_candidates']:>4} cand  {row['mean_winner_score']:>5} score"
            )
    if dh.get("n", 0) == 0:
        lines += [
            "",
            "  NOTE: no keyed draft->HQ pairs recorded yet. Correlation and margin",
            "  quality need a vision critic configured (keyless renders are single-shot,",
            "  static-scored, and never enter the tournament).",
        ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    from aetherlab.core.console import configure_utf8_stdio

    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=None,
                        help="Path to render_ledger.json (default: the app's data dir).")
    parser.add_argument("--json", action="store_true", help="Emit the raw summary as JSON.")
    args = parser.parse_args(argv)

    path = args.ledger or default_ledger_path()
    summary = summarize_ledger(load_jobs(path))
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(render_report(summary, path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
