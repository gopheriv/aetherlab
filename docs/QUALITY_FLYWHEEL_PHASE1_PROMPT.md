# Quality Flywheel — Phase 1 Mission Prompt (Trustworthy Per-Axis Judge)

> Paste this into a fresh agent session. It is self-contained: it repeats the
> essential context and ground rules so you need not read anything else first,
> though `docs/QUALITY_FLYWHEEL_MISSION.md` holds the full 7-phase plan and
> `docs/PROMPT_QUALITY_LAB.md` documents the gate you must keep green.

---

## Where this sits

You are working on **AetherLab** (`C:\Users\sunak\Projects\aetherlab`, branch
`codex/stabilize-current-branch`), a PySide6 desktop physics workbench that turns
a prompt into a derivation, RAG citations, an AI-storyboarded Manim animation
(self-healing render, local or GitHub-Actions cloud), a live parametric canvas,
and multi-chapter narrated video lessons. Canonical feature catalog is F01–F169
(tracked in `AetherLab_Feature_Tracker.xlsx`/`.csv`, generated **only** by
`build_feature_tracker.py`); the harness is `test_features.py`. Last defect is
**BUG-28**.

This is **Phase 1 of the Quality Flywheel** — the mission to connect AetherLab's
existing-but-disconnected quality parts into a measurable, self-improving loop
(plan → parallel fan-out → judge → select → learn → ship → ratchet → observe).

**Phase 0 is already done (F169):** `tools/prompt_quality_lab.py` now has a
12-prompt keyless golden set and a `--gate` release ratchet that fails on a mean
score or render-pass-rate regression against the committed
`tools/prompt_quality_baseline.json` (current baseline: 12/12 pass, mean 5.22).
**Every change you make must keep `python tools\prompt_quality_lab.py --gate`
passing** (or, if you *deliberately and defensibly* raise quality, regenerate the
baseline — see the last section).

## Why Phase 1 exists (the thesis)

The flywheel selects the best of N rendered candidates and learns from the rest.
**A selection loop is only as trustworthy as its judge.** Today
`services/scene_critic.py` collapses a rich 5-axis rubric down to a single
aggregate `score` (0–10). That single number is fine for a coarse "ship/revise"
verdict, but it is too lossy to (a) rank candidates reliably in Phase 2's
tournament, and (b) tell the Phase 3 error-learner *why* a candidate lost so it
can steer the next prompt. Phase 1 makes the judge return a **structured
per-axis breakdown**, persists it, and gives keyless/no-vision users an
intelligent fallback score so the flywheel still ranks sensibly offline.

**Read this first (verify before you build — a green suite is not proof):**
- `services/scene_critic.py` — the `Critique` dataclass (`verdict`, `score`,
  `issues`, `strengths`), `CRITIC_SYSTEM_PROMPT` (which already *names* five
  axes — LEGIBILITY, COMPOSITION, PALETTE, STRUCTURE, SUBSTANCE — but only asks
  for one aggregate `score`), and `critique_video()` (async; degrades to
  `verdict="skipped"` with no `vision_model`/`api_key`/frames or on any error).
- `core/models.py::SceneBundle` (~line 121) — persisted fields `quality_score`,
  `critique_verdict`, `critique_issues`, and the backward-compatible
  `from_json` (~line 151) that defensively parses them. This is the template
  for adding a new persisted field so **old caches and exported bundles still
  load**.
- `services/manim_runtime.py` — the **three** places a `Critique` is copied onto
  a `SceneBundle`: the tournament winner (~line 266), and two critique loops
  (~lines 384 and 686). All three must also copy the new breakdown.
- `services/scene_validation.py` — the static battery you will reuse for the
  no-vision fallback: `scene_hygiene_warnings(code)`, `validate_scene(code)`,
  `estimate_duration(code) -> DurationEstimate`, `lint_manim_names`,
  `lint_constructor_kwargs`, `check_latex_strings`.
- `tools/prompt_quality_lab.py::critic_summary` — reads the scene's critique
  fields into reports; it should surface the new breakdown.

## What to build

### 1. A fixed, structured rubric in the critic

In `scene_critic.py`, change `CRITIC_SYSTEM_PROMPT` so the model returns a
**per-axis breakdown** whose axes sum to (or map deterministically to) the total
`score`. Use the five axes the prompt already describes, made explicit and
scored **0–2 each** (total 0–10), plus keep `verdict`/`issues`/`strengths`:

```json
{"verdict": "ship" | "revise",
 "score": <0-10>,
 "breakdown": {"legibility": 0-2, "composition": 0-2, "palette": 0-2,
               "structure": 0-2, "substance": 0-2},
 "issues": ["worst first, each tagged with the axis it hurts"],
 "strengths": ["..."]}
```

- Extend the `Critique` dataclass with `breakdown: dict[str, float] =
  field(default_factory=dict)`.
- In `critique_video()`, parse `breakdown` defensively and **validate against a
  schema before trusting it**: it must be a dict of the five known axes with
  numeric 0–2 values. **On malformed/missing breakdown, do not silently default
  to zeros** — this is the BUG-7 lesson (silent defaults on LLM output cause
  correctness bugs). Instead, reconstruct the breakdown from the aggregate
  `score` as evenly as possible (so a valid `score` with a broken `breakdown`
  still yields a usable, clearly-marked approximation), and record that the
  breakdown was approximated. Prefer one cheap re-ask over shipping a lie only
  if it is cheap and bounded; otherwise approximate-and-flag.
- Keep every existing degradation path intact: no `vision_model`/`api_key` →
  `verdict="skipped"`, empty breakdown; any API/parse error → `"skipped"`, never
  a raised exception (the critic must never break a render).

### 2. Persist the breakdown (backward-compatibly)

In `core/models.py::SceneBundle`:
- Add `critique_breakdown: dict[str, float] = field(default_factory=dict)`.
- In `from_json`, parse it defensively exactly like `critique_issues`:
  `payload.get("critique_breakdown")` only if it `isinstance(dict)`, coercing
  values to float, else `{}`. **Old cached/exported bundles without the field
  must load unchanged** (P5 returning-user persona).
- Confirm the bundle's `to_json`/serialization path (wherever `quality_score`
  etc. are written) includes the new field.

In `services/manim_runtime.py`, update **all three** critique-copy sites
(~266, ~384, ~686) to also set `critique_breakdown=<critique>.breakdown`.

### 3. A no-vision fallback score (keyless users still rank intelligently)

When `critique_video()` returns `"skipped"` (no vision model, offline, keyless
— the common case), the flywheel currently has no signal to rank candidates.
Build a **static rubric estimate** from the code + render metrics so ranking is
never random:
- Add a function (in `scene_critic.py` or a small new `services` helper) that
  maps the existing static battery to the same five axes: e.g. out-of-frame /
  overlap hygiene warnings → *legibility* & *composition*; `estimate_duration`
  and equation-dwell vs total → *pacing* (fold into structure/substance);
  `check_latex_strings`/`lint_*` clean → baseline credit; blank/static frame
  ratios from `tools/visual_regression.audit_video` (already computed in the
  lab) → *substance*.
- This yields a `breakdown` + derived `score` with `verdict` left as
  `"skipped"` (so it is never confused with a real vision verdict) but a
  **non-zero, comparable** score. Document clearly that it is a heuristic proxy,
  not a vision judgment.
- Wire it so the tournament's candidate ranking (Phase 2 will consume this) and
  `prompt_quality_lab` both use the static score when no vision score exists.

### 4. Surface it in reports

In `tools/prompt_quality_lab.py::critic_summary`, include the breakdown (and
whether it was vision-derived or static-proxy) so `summary.md`/`scores.csv`
show per-axis quality. This makes Phase 1's improvement visible in the gate
reports and gives you before/after evidence.

## Edge cases you must handle (reason about these before trusting tests)

- **Malformed LLM breakdown** (missing axes, strings, out-of-range, extra keys):
  validate + approximate-and-flag; never silent-zero (BUG-7 family).
- **Old caches/bundles** without `critique_breakdown`: load cleanly (BUG-9
  `chapter_offsets` cache-safety pattern).
- **Keyless/offline**: static proxy produces a usable ordering; no dead paths;
  no slowdown; `verdict` stays `"skipped"`.
- **Breakdown/score disagreement**: if the model returns a `score` that does not
  match the axis sum, decide one source of truth (prefer the aggregate `score`
  for the ship/revise verdict; use the breakdown for *ranking* only) and
  document it. Do not let them silently diverge.
- **The critic must never break a render**: every new path is inside the
  existing fail-soft `try/except`.

## Testing (feature F170)

Add `t_f170` to `test_features.py` (auto-discovered; no registry edit needed):
- `Critique` and `SceneBundle` carry `critique_breakdown`; `SceneBundle.from_json`
  round-trips it **and** loads an old payload (no `critique_breakdown` key)
  without error.
- A parse of a well-formed critic JSON yields the five-axis breakdown; a
  malformed breakdown with a valid `score` yields an approximated,
  clearly-flagged breakdown (not all-zeros).
- The static fallback returns a non-zero, deterministic breakdown for a known
  scene and a *lower* one for a deliberately worse scene (proving it
  discriminates), with `verdict="skipped"`.
- All three `manim_runtime` copy sites propagate the breakdown (source
  assertion is acceptable where a full render is impractical, but prefer a
  constructed-bundle behavioural check).
Prefer deterministic tests that do not require a live vision model or a real
render where possible.

## Definition of done

- The critic returns a validated five-axis breakdown; two visibly different
  renders get defensibly different per-axis scores; malformed LLM output is
  handled without silent zeros.
- `critique_breakdown` persists and old caches/bundles still load.
- Keyless mode produces a non-zero, discriminating static ranking.
- `F170` is cataloged (row + story + `t_f170` test + Phase-2/4 stamp).
- **All gates green**: `python test_features.py` (rebuild-tracker → harness →
  rebuild-tracker → `tools\tracker_integrity_audit.py --check`),
  `tools\feature_surface_audit.py --check`, `python -m pytest -q`,
  `python -m compileall -q aetherlab test_features.py build_feature_tracker.py tools`,
  and **`python tools\prompt_quality_lab.py --gate`** (the Phase-0 ratchet).
- A hand-audit note listing the paths you read and the adversarial cases you
  reasoned through.

## Non-negotiable ground rules (repeated so this stands alone)

1. **A green 168/169 suite is not proof.** This project ships bugs behind green
   (BUG-6/7/8/17/18/20/26/27/28). Read each touched path end-to-end, reason
   about adversarial inputs, and write the regression that fails against the
   pre-fix code.
2. **Canonical defect workflow** for any bug you fix along the way:
   `DEFECTS["Fxx"]` in `build_feature_tracker.py` → row in `ERRORS_FOUND.md`
   (continue **BUG-29**…) → regression in `test_features.py` → run
   `python test_features.py` → `python build_feature_tracker.py` →
   `tools\tracker_integrity_audit.py --check`.
3. **New feature = catalog row + story + `t_fxxx` test + Phase-2/4 stamp.** Use
   the `PHASE_RESULTS` dict in `build_feature_tracker.py` to stamp; keep story
   columns non-empty (the integrity audit enforces it).
4. **Build order** to keep the tracker self-test (`t_f165`) green: **rebuild
   tracker → run harness → rebuild tracker → integrity audit** (the generator
   consumes `feature_test_results.json`).
5. **`ui/widgets.py` has mixed CRLF/LF** — the Edit tool normalizes the whole
   file (a 600-line spurious diff). If you must touch it, patch at the byte
   level with **LF** added lines and confirm `git diff --check` is clean.
   (Phase 1 likely does not need to touch it.)
6. **Fail-soft is sacred**: no AI key, no vision model, no backend, no network
   — the product stays fully usable and no slower for keyless users.
7. **Never** weaken a test/tolerance/safety check to pass; **never** commit
   `.env`, keys, `.analysis/`, temp renders, Chroma data, or raw videos
   (`docs/STABILIZATION_PLAN.md`). Small commits grouped by concern.

## A decision to make before you start (surface it to the user)

The committed baseline (mean 5.22) was generated **keyless** (template scenes,
no vision critic). Phase 1's whole point is a better *vision* judge, whose effect
only shows with `--allow-provider`. Decide with the user whether to:
- keep the keyless baseline (gate protects the offline floor), and evaluate the
  vision improvements separately with `--allow-provider` runs; or
- regenerate the baseline with `--allow-provider` so the ratchet reflects the
  quality real (keyed) users see.
Do not silently change what the gate protects — it is a genuine product choice.
