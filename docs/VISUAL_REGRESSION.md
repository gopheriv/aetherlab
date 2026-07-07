# Visual Regression Harness

AetherLab's render quality risk lives in video output, not only in unit-testable code paths. The visual regression harness renders a small canonical prompt set through the real local pipeline, samples each produced MP4, and stores lightweight reports plus contact sheets.

## Run

```powershell
python tools\visual_regression.py --out visual_regression\runs\manual
```

To refresh the checked-in baseline:

```powershell
python tools\visual_regression.py --out visual_regression\baseline\current --regenerate
```

The script intentionally clears provider, cloud-render, and narration environment variables and points AetherLab at `.analysis/visual-regression-data`, so reports do not depend on or expose private API keys/settings.

## What It Records

- duration, fps, width, height, decoded frame count
- blank-frame spans and longest blank span
- static visual ranges and longest static span
- high-motion transition samples
- final-frame brightness/contrast sample
- subtitle cue count, cue ranges, cue overruns, and rough cue-to-transition distance when an `.srt` exists
- one JPEG contact sheet per case

The harness keeps reports and contact sheets only. It does not copy frames or videos into the repository.

## Canonical Cases

The case list lives in `visual_regression/cases.json` and currently covers:

- pendulum
- Kepler orbit
- standing wave
- Fourier/series
- E&M field
- derivation/math mode
- lesson mode

## Outputs

Each run writes:

- `summary.json`: full machine-readable audit
- `metrics.csv`: one row per case for quick diffing
- `summary.md`: human-readable report
- `*_contact.jpg`: visual contact sheets

Generated ad hoc runs under `visual_regression/runs/` are ignored by git. The checked-in baseline lives under `visual_regression/baseline/current/`.
