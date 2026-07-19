# Prompt Quality Lab

The Prompt Quality Lab measures whether prompt, exemplar, and generation
changes improve AetherLab's rendered output. It complements visual regression:
visual regression protects a baseline; the lab compares prompt quality across a
canonical set of physics tasks.

## Run

```powershell
python tools\prompt_quality_lab.py --out .analysis\prompt-quality-lab\today
```

By default the lab runs in keyless/local mode. It strips provider/cloud
credentials from the process environment, disables cloud rendering, disables
web references, and writes under `.analysis/`, which is ignored by git.

To intentionally evaluate live provider prompts and vision-critic scores:

```powershell
python tools\prompt_quality_lab.py --out .analysis\prompt-quality-lab\live --allow-provider
```

Even in provider mode, reports never write API keys, app config, environment
variables, or raw provider responses.

## Canonical Prompts

The built-in **golden set** (12 prompts) spans the domains AetherLab serves and
is renderable keyless so the committed baseline is reproducible:

- mechanics: pendulum, projectile, collision
- waves: standing wave, Fourier series, Doppler, interference
- fields: E&M field (dipole), RC circuit
- orbital: Kepler orbit, escape velocity
- lesson mode: Kepler lesson

You can pass a custom JSON list:

```powershell
python tools\prompt_quality_lab.py --prompts my_prompts.json --out .analysis\prompt-quality-lab\custom
```

Each prompt object has:

```json
{"id": "pendulum", "mode": "solve", "quality": "l", "prompt": "..."}
```

Lesson prompts use:

```json
{"id": "lesson_kepler", "mode": "lesson", "quality": "l", "topic": "Kepler orbit"}
```

## Outputs

- `summary.json`: structured report
- `summary.md`: readable score table
- `scores.csv`: spreadsheet-friendly score table
- `*_contact.jpg`: eight-frame contact sheets

The lab does not copy raw MP4s or frame directories into the report folder.
Video paths in reports are public-safe render-cache references.

## Score Meaning

Scores are 0-10 and combine:

- render success;
- duration and FPS health;
- blank/static frame penalties;
- storyboard presence and act count;
- visual critic score when available;
- strict quality failures from `tools/visual_regression.py`.

The score is a triage signal, not a replacement for watching the contact sheet
or the video.

## Compare

```powershell
python tools\prompt_quality_lab.py `
  --out .analysis\prompt-quality-lab\after `
  --compare .analysis\prompt-quality-lab\before
```

The comparison flags score drops greater than 1 point and duration collapses
greater than 25%.

## Gate (the release ratchet)

`--gate` turns the lab into a CI-style quality ratchet (Phase 0 of the Quality
Flywheel, `docs/QUALITY_FLYWHEEL_MISSION.md`). It runs the golden set, then
compares the fresh mean score and render pass rate against a **committed**
baseline (`tools/prompt_quality_baseline.json`, tracked in git — not under the
ignored `.analysis/`):

```powershell
python tools\prompt_quality_lab.py --out .analysis\prompt-quality-lab\gate --gate
```

- Exit **0**: quality held or improved.
- Exit **2**: the mean score fell by more than `--score-tolerance` (default
  `0.5`, absorbing render non-determinism) **or** the render pass rate dropped
  at all. Every later Quality-Flywheel phase's change must keep this green.
- Exit **3**: no committed baseline found — generate one and commit it first.

`evaluate_gate()` is a pure function (baseline dict + report dict → verdict), so
the ratchet logic is unit-tested without rendering (feature F169). To refresh
the baseline after a genuine, reviewed improvement, run the lab once and copy
its `summary.json` to `tools/prompt_quality_baseline.json`.
