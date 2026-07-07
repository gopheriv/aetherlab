# AetherLab Stabilization Plan

Branch: `codex/stabilize-current-branch`

This branch contains a broad working-tree snapshot from the audit, render-sync,
UI redesign, cloud-render, lesson, and external-project research passes. The
goal is to keep the useful work while making the diff understandable and safe to
review.

## Do Not Commit

- `.analysis/` - generated frame-split/contact-sheet output from render audits.
- Local temp renders under `%TEMP%\aetherlab`.
- Any `.env`, API keys, local Chroma data, or Manim `media/` cache.

## Source Assets To Keep

- `assets/fonts/DejaVuSans.ttf`
- `assets/fonts/DejaVuSans-Bold.ttf`

These fonts are used by produced lesson title cards and bundled in
`packaging/aetherlab.spec`.

## Proposed Commit Groups

1. Render backend and settings compatibility
   - GitHub Actions render workflow and cloud backend.
   - Render-mode settings, manim-bot environment aliases, packaging support.
   - Cloud setup docs.

2. Produced lessons and narration sync
   - Lesson title-card renderer, crossfaded assembly, chapter offsets.
   - Per-chapter narration/SRT timing, millisecond carry fix.
   - Lesson worker/view offset mapping and partial lesson behavior.

3. Render correctness and visual hygiene
   - Isolated render runs, robust render discovery/cache behavior.
   - Visual critic frame sampling including final frames.
   - NIMA-inspired static scene hygiene warnings.
   - Code safety, ingestion stale-chunk purge, validation hardening.

4. UI redesign and app experience
   - Theme/style refresh, DejaVu UI font loading.
   - Scene player frame stepping by encoded FPS.
   - Diagnostics drawer, backend chips, lesson/video UI polish.

5. Documentation, trackers, and regression suite
   - Feature tracker spreadsheet/CSV and `ERRORS_FOUND.md`.
   - `test_features.py`, `test_batch.py`, feature result JSON.
   - Cloud/settings/UI docs and stabilization notes.

## Current Verification

- `python test_features.py` passed: 163/163.
- `python -m pytest -q` passed: 37 passed, 1 external deprecation warning.
- `python -m compileall -q aetherlab test_features.py build_feature_tracker.py tools` passed.
- `git diff --check` passed.
- Live GitHub Actions cloud smoke passed after provisioning the render workflow
  and downloading a valid MP4 artifact.

## Review Notes

Several files contain changes from multiple groups, especially:

- `aetherlab/services/manim_runtime.py`
- `aetherlab/ui/main_window.py`
- `aetherlab/ui/widgets.py`
- `test_features.py`

If we require bisectable commits, those files should be split with patch-level
staging. If review clarity is the priority, file-level grouped commits are
acceptable, followed by one regression-suite commit.
