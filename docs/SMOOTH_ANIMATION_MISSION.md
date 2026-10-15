# Smooth & Creative Animation Mission

Copy this into a fresh agent session to execute the smooth-operation /
buttery-animation upgrade. It is grounded in the project's cloud-based Manim
settings and in current Manim/ffmpeg upstream guidance (sources at the end).

## Project Snapshot

You are working on **AetherLab** at `C:\Users\sunak\Projects\aetherlab`, a
PySide6 desktop physics workbench. Rendering runs locally through Manim
Community 0.21.0 (Cairo) or remotely through the provisioned GitHub Actions
cloud-render backend (`.github/workflows/render.yml`, see
`docs/CLOUD_RENDERING.md`).

Current branch: `codex/stabilize-current-branch` (post-merge `c4ffb34`).

Recent baseline (2026-10-14):

- Feature harness: `python test_features.py` -> 250/250 passed.
- Pytest: `python -m pytest -q tests` -> 426 passed (run with the TMP/TEMP
  override below; `tests/test_batch.py::test_f29` separately without it).
- Tracker: `python build_feature_tracker.py` regenerated CSV/XLSX (250 features).

Cloud-render facts you must build on (do not redesign these):

- The workflow accepts `quality` (`l|m|h|k`) and `fps` (string) inputs and runs
  `manim render -q<quality> --fps <fps> --disable_caching --media_dir out`.
- The runtime ALWAYS passes an explicit `--fps` (prevents silent 15 fps output).
- Render tiers (`manim_runtime._detect_render_tier`): `standard`/`constrained`
  = 30 fps, `cinematic`/`cloud_cinematic` = 60 fps via `AETHERLAB_RENDER_TIER`
  (or `AETHERLAB_MANIM_FPS` override).
- Cloud cache keys cover scene code + class + quality + fps, so a quality
  ladder reuses artifacts instead of re-rendering.
- Local OpenGL exists only behind `AETHERLAB_MANIM_RENDERER=opengl`; Cairo is
  the default and the cloud worker is Cairo-only. Do not change the default
  renderer in this mission.

## Problem Statement

Final videos look mechanical: `scene_exemplars.py`, `scene_templates.py`, and
most `scene_components/*` drive nearly every `play()` with `rate_func=linear`,
and finals typically render at 30 fps. The generator prompt (`§3 ANIMATION
PRINCIPLES` in `scene_generator.py`) already teaches easing, but nothing
enforces it, exemplars contradict it, and there is no draft-vs-final
quality/fps ladder. Result: constant-velocity motion, visible 30 fps stepping
on fast moves, and flat camera work.

## Mission Goal

Ship a **smooth operation + smooth animation** pipeline:

1. **Buttery finals**: 1080p60 cloud finals (native 60 fps; motion-interpolated
   60 fps fallback where native is too costly).
2. **Cinematic motion**: easing policy enforced from prompt -> exemplar ->
   template -> lint, plus first-class moving-camera grammar.
3. **Fast drafts, calm ops**: drafts stay cheap (480p30, cached); finals climb
   a quality ladder; every step stays observable in the render-farm ledger.

## Workstreams

### A. Draft/Final render ladder (operation smoothness)

- Define the ladder in one place (settings + runtime, not scattered env reads):
  - `draft`: 480p30, local-or-cloud, cache-friendly, critic keyframes only.
  - `review`: 720p30, cloud preferred.
  - `final`: 1080p60 cloud (`cloud_cinematic`), Cairo.
- Wire the ladder into `manim_runtime` tier selection and `render_backend`
  cloud dispatch so callers request `draft|review|final`, not raw flags.
- Keep the explicit-`--fps` invariant: every Manim invocation passes `--fps`.
- Record ladder step + effective quality/fps per job in the render ledger.
- Out of scope: changing the 15-minute worker cap or the cache-key contract
  (bump the workflow contract version ONLY if worker inputs change shape).

### B. Easing policy (animation smoothness)

Research-backed policy (Manim `rate_functions` docs):

- KEEP `linear` ONLY for time-faithful motion: physics `ValueTracker` sweeps
  (`t.animate.set_value(...)`) and constant-speed `MoveAlongPath` rides.
- DEFAULT everything else (reveals, transports, camera, emphasis exits) to the
  smooth family: `smooth`, `smootherstep`/`smoothererstep`, `slow_into`,
  `rush_into`/`rush_from`, `lingering`.
- CREATIVE accents (sparingly, must "earn it"): `rate_functions.ease_out_back`
  for playful arrivals, `wiggle`/`there_and_back` for attention pulses,
  `squish_rate_func` / `not_quite_there` for chained anticipation.
- Concrete changes:
  1. Update `scene_exemplars.py` + `scene_templates.py`: replace mechanical
     `linear` on non-tracker plays with the policy default; keep tracker
     sweeps linear with a one-line comment why.
  2. Tighten generator prompt `§3`: restate the linear-only-for-physics rule
     and name the approved smooth set explicitly.
  3. Add a `scene_validation` lint: flag `rate_func=linear` on plays that do
     NOT animate a `ValueTracker`/`MoveAlongPath` (heuristic on source; must
     have zero false positives on the physics components — prove with tests).
  4. Add the critic rubric: motion-quality scoring (easing variety, no pops
     between beats, camera earns its moves).

### C. Cinematic camera grammar (creative)

- Add a `MovingCameraScene` exemplar following the upstream pattern:
  `save_state()` -> `camera.frame.animate.move_to(x).set(width=...)` ->
  `Restore(camera.frame)`; plus `camera.auto_zoom(target)` follow shots.
- Promote camera from "only if it earns it" to a beat-level choice: each
  storyboard beat declares `static | push-in | follow | restore`.
- Keep camera moves on the smooth family (`smooth`/`slow_into`) with
  run_times >= 1.2 s; forbid camera motion under 0.8 s (reads as a glitch).

### D. 60 fps fallback via motion interpolation (post-pass)

- When native 60 fps is unavailable/too slow, upsample 30 fps finals with
  ffmpeg `minterpolate` (motion-compensated):
  `minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1:scd=fdiff`
  (balanced preset: `mc_mode=obmc:vsbmc=0`; preview preset: `mi_mode=blend`).
- `scd=fdiff` is MANDATORY (never interpolate across cuts).
- Gate the pass behind a setting (default off for drafts, on for cloud finals
  rendered below 60 fps); record `interpolated_60=true` in the ledger and
  bundle diagnostics; validate output (container, dims, decoded frame,
  duration match) through the existing artifact checks.

### E. Verification & rollout

- Follow the repo ground rules for every behavior change: `DEFECTS` entry in
  `build_feature_tracker.py`, row in `ERRORS_FOUND.md`, regression assertion
  in `test_features.py`, then `python test_features.py` +
  `python build_feature_tracker.py`.
- Strict visual regression for render-path changes:
  `python tools\visual_regression.py --out visual_regression\runs\<name> --compare visual_regression\baseline\current --strict`
  (render one physics scene + one camera scene at draft AND final ladder steps).
- pytest with the machine override:
  `set TMP=C:\Users\sunak\Projects\aetherlab\.qwen\tmp\pytest-tmp & set TEMP=... & python -m pytest -q tests`
  plus `python -m pytest -q tests/test_batch.py::test_f29` WITHOUT the override.
- Measure and report: draft vs final wall-time, cloud artifact reuse rate,
  and a before/after motion-quality note from the critic on the same scene.

## Research Sources

- Manim `rate_functions` reference (easing catalog + smooth-family guidance):
  `https://docs.manim.community/en/stable/reference/manim.utils.rate_functions.html`
- Manim `MovingCameraScene` reference (pan/zoom/restore/auto_zoom grammar):
  `https://docs.manim.community/en/stable/reference/manim.scene.moving_camera_scene.html`
- ffmpeg `minterpolate` filter docs (`mci`/`aobmc`/`bidir`/`scd=fdiff` 30->60):
  `https://ffmpeg.org/ffmpeg-filters.html#minterpolate`

## Out of Scope (do not do these)

- Switching the default renderer to OpenGL or touching cloud worker Cairo.
- Changing narration/voiceover, RAG, lesson assembly, or the A/B lab.
- Committing `.env`, keys, `.analysis/`, temp renders, Chroma data, or raw
  visual-regression run videos.
