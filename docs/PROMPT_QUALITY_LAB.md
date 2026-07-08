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

The built-in set covers:

- pendulum
- Kepler orbit
- standing wave
- Fourier series
- E&M field
- Kepler lesson mode

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
