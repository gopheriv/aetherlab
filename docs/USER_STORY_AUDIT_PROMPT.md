# AetherLab — User-Story Audit & Fix Loop (Detailed Mission Prompt)

Copy everything below into a fresh agent session. It is self-contained and
phase-gated: do not start a phase until the previous phase's exit gate passes.

---

/goal Go over every single feature in AetherLab, write a user story with
expected behaviour derived from the code, keep ONE canonical spreadsheet
tracking feature + story status. Then switch the loop to testing every user
story and documenting all errors. Then fix every logistical or UX error. Then
test every user behaviour again post-fix.

## Project snapshot

You are working on **AetherLab** at `C:\Users\sunak\Projects\aetherlab`
(branch `codex/stabilize-current-branch`), a PySide6 desktop physics
workbench. One prompt bar drives:

- **Solve**: derivation → RAG citations → storyboarded Manim scene →
  self-healing MP4 render → live parametric canvas.
- **Learn**: multi-chapter narrated lesson video with title cards, crossfades,
  subtitles, chapter seeking, quizzes, course progress, share/export bundles.

Rendering is local (Manim Community) or cloud (provisioned GitHub Actions
backend with artifact download and local fallback).

Current baseline (verify it still holds before you begin; if not, stop and
report):

- `python test_features.py` → 168/168 passed
- `python build_feature_tracker.py` regenerates CSV/XLSX cleanly
- `python tools\tracker_integrity_audit.py --check` passes
- `python tools\feature_surface_audit.py --check` passes
- `python -m pytest -q` → 37 passed
- `python -m compileall -q aetherlab test_features.py build_feature_tracker.py tools` passes
- Strict visual regression: 7/7, 0 warnings, 0 regressions
- Last documented defect: **BUG-23** in `ERRORS_FOUND.md` — your numbering
  continues from BUG-24.

## Why this mission exists (read before trusting anything)

Every serious AetherLab bug to date passed a fully green suite: crossfade
offset drift (BUG-6), chapter id-collision from LLM-omitted ids (BUG-7),
chapter-seek/subtitle desync (BUG-8), cloud dispatch 404 because the workflow
file was never installed (BUG-17), workflow `cache: pip` failing every cloud
run (BUG-18), artifact 401 from forwarding the Bearer token to signed storage
(BUG-20). The harness is broad but shallow — mostly static/construction/
happy-path checks. **A PASS cell means "the happy path executed", never "the
feature behaves correctly."** This mission exists to close that gap with
behaviour-level user stories and adversarial execution.

## Ground rules (non-negotiable)

1. **Hand-read before you trust.** For every feature you write a story for,
   read its implementation end-to-end and derive the expected behaviour from
   the code, not from the feature title or docs. If code and docs disagree,
   that is itself a finding.
2. **One canonical spreadsheet.** `AetherLab_Feature_Tracker.xlsx` (CSV
   mirror for diffs) stays the single source of truth, generated ONLY by
   `build_feature_tracker.py` from its in-code `FEATURES` list. Never hand-edit
   the XLSX/CSV. All new story data lives in the generator and flows out.
3. **Canonical defect workflow** for every fix:
   `DEFECTS["Fxx"]` entry in `build_feature_tracker.py` → row in
   `ERRORS_FOUND.md` (BUG-24, BUG-25, …) → regression assertion in
   `test_features.py` → rerun `test_features.py` → rerun
   `build_feature_tracker.py` → `tools\tracker_integrity_audit.py --check`.
4. **Never fix by weakening.** No loosened assertions, no widened tolerances,
   no removed checks to make a story pass.
5. Render-affecting work also runs
   `python tools\visual_regression.py --out visual_regression\runs\<name>
   --compare visual_regression\baseline\current --strict` and you open the
   MP4s yourself.
6. Do not commit `.env`, keys, `.analysis/`, temp renders, Chroma data, or raw
   regression videos (`docs/STABILIZATION_PLAN.md`).
7. Small commits, one concern each; commit at each phase gate at minimum.

## Key files

- Pipeline: `aetherlab/services/pipeline.py`, `manim_runtime.py`,
  `scene_generator.py`, `scene_validation.py`, `scene_critic.py`,
  `scene_templates.py`, `scene_exemplars.py`, `code_safety.py`
- Lessons: `lesson_planner.py`, `lesson_pipeline.py`, `assembly.py`,
  `cards.py`, `voiceover.py`, `fact_check.py`
- New & least battle-tested (prioritize): `share_export.py` (F166),
  `course_mode.py` (F167), `tools/prompt_quality_lab.py` (F168)
- Cloud: `render_backend.py`, `.github/workflows/render.yml`,
  `docs/CLOUD_RENDERING.md`, `docs/MANIM_BOT_SETTINGS_COMPAT.md`
- UI: `aetherlab/ui/main_window.py`, `widgets.py` (very large), `live_canvas.py`,
  `workers.py`, `theme.py`, `style.py`
- Core: `core/settings.py`, `models.py`, `cache.py`, `proc.py`, `events.py`
- Tracker machinery: `test_features.py`, `build_feature_tracker.py`,
  `tools/tracker_integrity_audit.py`, `tools/feature_surface_audit.py`

## Personas (used by every story)

- **P1 Student, no AI key** — offline-capable template mode; must never see a
  stack trace or a dead button.
- **P2 Student, local Ollama** — free local model; slower, occasionally
  malformed LLM output.
- **P3 Educator, cloud AI + vision critic** — full pipeline, quality matters.
- **P4 Power user, cloud rendering** — GitHub render repo + token; cares about
  job visibility and fallback.
- **P5 Returning user** — second session; caches, persisted settings, course
  progress, old lesson bundles from previous app versions.

---

# PHASE 1 — User stories for every feature (F01–F168)

For **every** feature in the `FEATURES` list, write one primary user story
plus edge-case expectations, derived from the code.

### Story format (stored in the generator, one per feature)

- **Story id**: `US-<feature id>` (e.g. `US-F148`).
- **Persona**: P1–P5 (the persona most exposed to this feature).
- **Story**: "As <persona>, when I <concrete action>, I expect <observable
  behaviour>." Observable means a user could verify it with eyes/ears — a
  window state, a file on disk, a video that plays correctly, a message.
- **Preconditions**: exact state needed (AI key? render repo? cached run?
  clean profile?).
- **Steps**: numbered, concrete UI-level steps (which button, which field).
- **Expected**: the behaviour **as implemented** (cite `file.py:line` for the
  code that defines it). If the implemented behaviour seems wrong while
  writing the story, record the code's actual behaviour as "Expected
  (implemented)" AND file a candidate defect immediately — do not silently
  write the story to match your wish.
- **Failure-mode expectation**: what the user should see when the sad path
  hits (LLM down, render fails, file missing, token expired). "Undefined" is
  not acceptable — if the code has no defined sad-path behaviour, that is a
  logistical finding.
- **Test method**: one of `harness` (assertable in `test_features.py`),
  `scripted-ui` (offscreen Qt interaction), `manual` (needs a real render /
  eyes on video), `live-cloud` (needs real GitHub credentials).

### Spreadsheet integration

Extend `build_feature_tracker.py` so the canonical spreadsheet gains story
columns: `Story`, `Persona`, `Expected behaviour`, `Failure-mode expectation`,
`Test method`, `Phase-2 result`, `Errors found`, `Phase-4 result`. Keep the
CSV mirror in sync (same generator run). `tools/tracker_integrity_audit.py`
must still pass; extend it to require a non-empty story for every feature so
the gate is machine-checked.

### Coverage discipline

- Run `tools\feature_surface_audit.py` and hand-sweep `main_window.py`,
  `widgets.py`, and the services for user-reachable behaviour with **no
  feature row** (context menus, keyboard shortcuts, drag-drop, settings
  fields, CLI/module entry points, `aetherlab_watchdog.py`, `start.bat`).
  Every orphan surface gets a new feature id + story.
- Group work in passes of ~20 features and commit each pass; do not attempt
  all 168 in one sitting without checkpoints.

### Phase-1 exit gate

Every feature id has a story with all fields non-empty; integrity audit
enforces it; tracker regenerated; candidate defects found *while writing
stories* are logged (they often appear here — expected-vs-implemented
mismatches are exactly how BUG-3/BUG-4 were found).

---

# PHASE 2 — Test every user story, document every error

Switch the loop: execute each story per its test method and record the result
in the spreadsheet (`Phase-2 result`: PASS / FAIL / BLOCKED / PARTIAL, plus
error ids).

### Execution rules

- **harness** stories: add/extend the assertion in `test_features.py` so the
  story's *observable behaviour* is asserted, not construction. If the
  existing feature check only proves "widget constructs", upgrade it.
- **scripted-ui** stories: drive the offscreen Qt widgets (click, type,
  signal) and assert the resulting state. Reuse the existing offscreen
  patterns in `test_features.py`.
- **manual** stories: actually run the app (`python -m aetherlab`), perform
  the steps, watch the video, click the chapter, export the bundle and open
  it. Record evidence (paths under `.analysis/story-audit/`, gitignored).
- **live-cloud** stories: one consolidated live smoke (provision → dispatch →
  poll → download → fallback) if credentials are available; otherwise mark
  BLOCKED with the reason, never fake a PASS.

### Adversarial variants (the bug-hunt — run these against every applicable story)

These are the exact families that produced BUG-1…BUG-23. For each story, run
every variant that applies:

1. **Run it twice** — second run must hit the cache and behave identically.
   Then corrupt the cache: delete the MP4 behind a cached `SceneBundle`,
   truncate a cached JSON, remove a field (schema drift) — expect graceful
   re-render/rebuild, never a stale-path error (BUG-21 family).
2. **Cancel mid-flight** — cancel during solve, during render, during lesson
   assembly, during ingest. Expect: no zombie subprocess, no stale loading
   surface (BUG-11), UI fully reusable, partial artifacts cleaned or clearly
   marked.
3. **Malformed LLM output** — empty response, truncated JSON, JSON missing
   optional ids (`id=""`, the BUG-7 trigger), wrong types, code fenced in
   prose. Expect re-ask or clean fallback, never a default that silently
   changes meaning.
4. **Timing math** — for anything touching `assembly.py`, `voiceover.py`,
   offsets or SRT: test 1, 2, 3, and 10+ segments, a lesson with a
   non-rendered `interactive` chapter, and verify on paper that
   `offset_k == sum(durs[0..k-1]) - k*d`. Click every chapter in the real
   player and check subtitles land on the spoken sentence (BUG-6/8/9 family).
5. **No-AI / offline** — pull the network and the key: every P1 story must
   still complete via templates, and every AI-only control must degrade with
   a clear message, not a dead click.
6. **Settings precedence** — for each settings-backed story: set the value in
   the dialog, restart, confirm it survived (BUG-4 family); then set a
   conflicting env var and legacy `.env` and confirm the documented
   precedence (BUG-19 family). Every field visible in the dialog must
   round-trip to app config.
7. **Hostile filesystem** — data dir and library paths with spaces, unicode
   (`Éxàmple 物理`), OneDrive-synced dirs, read-only files, a PDF that is
   actually a renamed JPEG. Windows cp1252 console for subprocess output.
8. **Windowing** — 400–600px width, 125%/150% DPI, maximize→restore, both
   themes. No clipped text, no unreachable primary control (BUG-22 family).
9. **Concurrency** — trigger a second run while one is active; dispatch two
   cloud jobs close together and confirm run-matching stays exact (BUG-15
   family); course-progress writes from rapid quiz answers must not corrupt
   `course_progress.json`.
10. **Old data** — open a lesson bundle / cache / progress file produced
    before the newest fields existed (P5). Expect legacy fallback, not a
    KeyError (the `chapter_offsets` cache-safety pattern is the model).
11. **Code-safety probes** — for the scene-code gate, attempt bypasses via
    string assembly, `chr()` joins, `importlib`, aliased `__import__`, and
    Manim file-writing APIs. Any that executes is a Blocker (BUG-13 family).
12. **Export/ingest round-trips** — F166 bundles: export, move to another
    folder, open the HTML player from the moved location (relative paths!),
    re-import/replay; PDF study guide opens; SRT timestamps match the
    exported MP4, including intro/chapter cards.

### Error log

Document every deviation — including "works but confusing", "message is
technically true but unactionable", and doc-vs-behaviour drift. For each:

- id `BUG-NN` (continue from BUG-24), severity from this taxonomy:
  **Blocker** (data loss, crash, security, wrong artifact) /
  **Logistical** (wrong behaviour, desync, stale state) /
  **UX** (misleading, dead-end, inconsistent) /
  **Cosmetic** / **Doc-drift**;
- feature + story id, file:line, exact reproduction steps, expected vs
  actual, and **why the existing harness missed it** (this column has been
  the most valuable one in `ERRORS_FOUND.md` — keep it).
- During Phase 2 you **document only** — no fixing yet, except a Blocker that
  prevents further testing (fix it via the canonical workflow, note the
  exception, continue).

### Phase-2 exit gate

Every story has a Phase-2 result in the spreadsheet; every FAIL/PARTIAL maps
to at least one logged BUG; BLOCKED items list the concrete unblocking need;
tracker regenerated.

---

# PHASE 3 — Fix every logistical and UX error

Fix order: Blockers → Logistical → UX → Cosmetic → Doc-drift. For each fix:

1. Re-read the whole code path first; fix the root cause, not the symptom
   (BUG-17's lesson: the gate passed while a later required step was missing —
   reproduce the entire user path before declaring a cause).
2. Apply the canonical defect workflow (ground rule 3) — every fix gets a
   regression assertion that would have caught it, written to fail against
   the pre-fix code (verify this by stashing the fix once if cheap).
3. Prefer single-source-of-truth designs over synchronized duplicates: derived
   values (offsets, cue times, cached paths, workflow copies) should be
   *returned by* the process that owns them, as `assemble_lesson(...,
   return_offsets=True)` did — this pattern killed the whole BUG-8 class.
4. If a fix touches rendering/assembly, rerun strict visual regression and
   eyeball the MP4s; if it touches cloud, rerun the stubbed suite plus one
   live smoke when credentials allow.
5. Cosmetic/Doc-drift items you deliberately defer must be marked DEFERRED
   in the spreadsheet with a one-line reason — nothing silently dropped.

### Phase-3 exit gate

Zero open Blocker/Logistical/UX errors (fixed or explicitly DEFERRED with
reason); `ERRORS_FOUND.md`, `DEFECTS`, and the tracker are mutually
consistent; full harness + pytest + compileall + integrity audit green.

---

# PHASE 4 — Retest every user behaviour post-fix

Not just the failed ones — **every** story runs again, because fixes regress
neighbours (that is how BUG-8 was born: a produced-video improvement broke
seeking that used to line up).

1. Re-execute all stories per their test method; record `Phase-4 result`.
2. Rerun the full adversarial variant set on every story whose feature was
   touched in Phase 3, and on all stories in the same subsystem.
3. Full mechanical battery: `test_features.py`, `pytest -q`, `compileall`,
   ruff, `tracker_integrity_audit.py --check`, `feature_surface_audit.py
   --check`, strict visual regression, one live cloud smoke (or documented
   waiver).
4. **Clean-profile manual QA**: fresh `%LOCALAPPDATA%\AetherLab` (or temp
   `AETHERLAB_DATA_DIR`), follow `docs/QUICKSTART.md` exactly as a new P1
   user, then as P3 with a key. Anything surprising gets logged — if it needs
   fixing, loop back through Phase 3 for that item and re-gate.
5. Final report: spreadsheet fully stamped (Phase-2, errors, Phase-4 columns);
   summary table of bugs found/fixed/deferred by severity; the "why the suite
   missed it" lessons appended to `ERRORS_FOUND.md`; a short hand-audit note
   listing the paths read and adversarial cases reasoned through.

### Definition of done

- 100% of features have stories; 100% of stories have Phase-2 AND Phase-4
  results; zero unexplained FAIL/BLOCKED cells.
- Every logged bug is fixed-with-regression or DEFERRED-with-reason.
- All mechanical checks green; visual regression 0/0; tracker artifacts
  regenerated from the generator only.
- Commits grouped by phase and concern; final status lists any intentionally
  untracked files.
