"""Train the keyless quality proxy from real tournament outcomes (F182).

The keyless static proxy (`scene_critic.static_quality_estimate`) ranks scenes by
SUMMING five axis estimates — an equal-weight guess. But the render ledger has been
recording, for every keyed tournament, the winner's per-axis DRAFT breakdown and
the score it actually SHIPPED at (HQ). That is exactly a supervised dataset:

    features = the winner's 5 draft-axis scores      target = its HQ critic score

This tool fits a small ridge regression (numpy — the project's one hard math dep)
over those pairs and writes learned per-axis weights to `tools/quality_proxy_model.json`.
`scene_critic._load_quality_proxy()` picks that file up and uses the learned weights
instead of the equal-weight sum, so the *keyless* ranking is calibrated by *keyed*
reality (e.g. if legibility predicts HQ quality more than palette does, it earns a
higher weight).

Safety, deliberately: the model is data, not code, and is written to a reviewable
JSON that is committed only after a human looks at it (like curated exemplars). Until
such a file ships, `static_quality_estimate` is byte-identical to the old sum, so the
committed keyless --gate baseline never moves underneath anyone.

    python tools/train_quality_proxy.py [--ledger PATH] [--min-samples N] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ledger_report import default_ledger_path, load_jobs  # noqa: E402

# In step with scene_critic.CRITIC_AXES; ordered so the feature vector is stable.
AXES = ("legibility", "composition", "palette", "structure", "substance")


def collect_pairs(jobs: list[dict]) -> list[tuple[list[float], float]]:
    """Extract (winner draft 5-axis vector, winner HQ score) training pairs.

    Only tournaments carrying a real HQ score (> 0) AND a full winner breakdown
    contribute — i.e. keyed runs, where both the draft breakdown and the HQ score
    are genuine vision judgements. Pure function (no I/O); unit tested.
    """
    pairs: list[tuple[list[float], float]] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        hq = float(job.get("winner_hq_score", 0.0) or 0.0)
        idx = job.get("winner_index")
        if hq <= 0.0 or idx is None:
            continue
        winner = next(
            (c for c in job.get("candidates") or [] if int(c.get("index", -1)) == int(idx)),
            None,
        )
        if not winner:
            continue
        breakdown = winner.get("breakdown") or {}
        if not all(axis in breakdown for axis in AXES):
            continue
        pairs.append(([float(breakdown[axis]) for axis in AXES], hq))
    return pairs


def fit_quality_proxy(
    pairs: list[tuple[list[float], float]], lam: float = 1e-3
) -> dict | None:
    """Ridge-fit per-axis weights + intercept mapping the axis vector to HQ score.

    Returns ``{weights, intercept, r2, n_samples, lambda, axes}`` or None when there
    is too little data. The axis weights are L2-regularised; the intercept is not.
    """
    import numpy as np

    if len(pairs) < 2:
        return None
    X = np.asarray([vec for vec, _ in pairs], dtype=float)
    y = np.asarray([score for _, score in pairs], dtype=float)
    n, d = X.shape
    Xb = np.hstack([X, np.ones((n, 1))])  # bias column
    reg = lam * np.eye(d + 1)
    reg[d, d] = 0.0  # do not regularise the intercept
    try:
        w = np.linalg.solve(Xb.T @ Xb + reg, Xb.T @ y)
    except np.linalg.LinAlgError:
        w, *_ = np.linalg.lstsq(Xb, y, rcond=None)
    pred = Xb @ w
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 1.0
    return {
        "weights": {axis: round(float(w[i]), 6) for i, axis in enumerate(AXES)},
        "intercept": round(float(w[d]), 6),
        "r2": round(float(r2), 4),
        "n_samples": int(n),
        "lambda": float(lam),
        "axes": list(AXES),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=None,
                        help="render_ledger.json to train from (default: the app's data dir).")
    parser.add_argument("--out", type=Path, default=ROOT / "tools" / "quality_proxy_model.json",
                        help="Where to write the model (review before committing).")
    parser.add_argument("--lambda", dest="lam", type=float, default=1e-3,
                        help="Ridge regularisation strength (default 1e-3).")
    parser.add_argument("--min-samples", type=int, default=20,
                        help="Refuse to write a model from fewer than this many keyed pairs.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fit and report, but do not write the model file.")
    args = parser.parse_args(argv)

    path = args.ledger or default_ledger_path()
    pairs = collect_pairs(load_jobs(path))
    print(f"Collected {len(pairs)} keyed draft->HQ pairs from {path}")
    if len(pairs) < max(2, args.min_samples):
        print(
            f"Need >= {args.min_samples} pairs to train a trustworthy model; nothing "
            f"written. Run more keyed solves (a vision critic must be configured so the "
            f"tournament runs and records HQ scores)."
        )
        return 1

    model = fit_quality_proxy(pairs, lam=args.lam)
    if not model:
        print("Could not fit a model from the collected pairs.")
        return 1
    model["trained_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    model["source_ledger"] = str(path)
    print(f"Fit on {model['n_samples']} pairs; R^2 = {model['r2']}")
    print(
        "weights: "
        + ", ".join(f"{a}={model['weights'][a]:+.3f}" for a in AXES)
        + f", intercept={model['intercept']:+.3f}"
    )
    if args.dry_run:
        print("--dry-run: model not written.")
        return 0
    args.out.write_text(json.dumps(model, indent=2), encoding="utf-8", newline="\n")
    print(
        f"Wrote {args.out}. REVIEW before committing — a committed model changes the "
        f"keyless quality score and therefore the --gate baseline."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
