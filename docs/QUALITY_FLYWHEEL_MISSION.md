# AetherLab — The Quality Flywheel Mission (Detailed Plan + Agent Prompt)

> This document is deliberately over-explained. It is written to be handed to a
> fresh agent (or a new human contributor) who has never seen the project, and
> to survive being read six weeks from now with no other context. It contains
> **both** the plan and the copy-paste agent prompt. If you only want the
> prompt, jump to **Part 9**. If you want to understand *why* every step exists,
> read Parts 1–8 first.

---

## Part 0 — How to read this document

There are two audiences and two uses:

1. **A human deciding whether this is worth doing.** Read Part 1 (the thesis),
   Part 3 (the vision), and Part 6 (how we'll know it worked). Those three parts
   make the business/pedagogy case without any code.
2. **An agent about to execute it.** Read everything, but Part 9 is the
   self-contained prompt you actually paste into a new session. Part 9 restates
   the plan in condensed, imperative form and repeats the non-negotiable ground
   rules, so it works even if the reader never scrolls up.

Throughout, when a file or symbol is named it is real and current in the repo
(e.g. `aetherlab/services/manim_runtime.py::generate_render_tournament`). Verify
by reading it before you build on it — that is itself a ground rule (see
Part 8). Cited line numbers drift; cited *symbol names* are stable — search by
name.

---

## Part 1 — The thesis (why this mission, over-explained)

### 1.1 The one-sentence version

AetherLab already has every *part* of a system that gets better at making
physics animations over time, but the parts are not connected into a loop, so
the product's quality is flat instead of compounding. **This mission connects
them into a measurable, self-improving "quality flywheel."**

### 1.2 The longer version

AetherLab's core promise is: type a physics problem or topic, get an animation
you can learn from. The single thing that determines whether a user trusts the
product is **the quality of the rendered scene** — is it correct, is it on
screen, is it paced so a human can follow it, does it look authored rather than
auto-generated. Everything else (RAG citations, the parametric canvas, the
lesson structure) is supporting cast. If the animation is mediocre, the product
is mediocre.

Today, scene quality is produced by a **single-shot** process most of the time:
the LLM writes one storyboard, one scene file, it renders, and whatever comes
out is what the user sees (a self-heal loop repairs *crashes*, but not
*mediocrity*). The project's own honest self-assessment
(`MANIM_PIPELINE_QUALITY_ANALYSIS.md`) names this as the biggest unclaimed win:

> "No multi-candidate generation — the biggest unclaimed win from 'unlimited
> compute'."

Since then, three things changed that make the win finally cashable:

1. **A critic that can watch the video exists.** `services/scene_critic.py`
   samples frames (including motion frames and the final frame) and, with a
   vision model, returns a numeric `score`, a `verdict`, and a list of
   `issues`. Those now persist on the `SceneBundle`
   (`quality_score`, `critique_verdict`, `critique_issues` — feature F160,
   BUG-16). **We can now compare two renders objectively.**
2. **A candidate tournament exists but is dormant.**
   `manim_runtime.py::generate_render_tournament` /`_build_scene_candidates`
   /`_render_and_score_candidates` (feature F161) already generate N candidate
   scenes, render each, score each with the critic, and pick the winner. It is
   **opt-in** (`settings.scene_candidates > 1`), **sequential**, **local**, and
   **teaches nothing**. It is a race with no memory.
3. **A cloud render farm exists.** `services/render_backend.py`
   (`GitHubActionsClient`, `select_backend`, `provision_render_repo`) can
   provision, dispatch, poll, download, and fall back to local. This is the
   "unlimited compute" the quality analysis assumed we didn't have. Right now we
   use it like a *slower local renderer* — one job at a time — instead of a
   *fan-out farm* that renders 4 candidates in parallel for the price of one
   wall-clock render.

So all three ingredients — an objective judge, a tournament, and parallel
compute — exist and **do not talk to each other in a loop.** Worse, there are
two more assets that should be closing the loop and aren't:

4. **An error learner** (`services/error_learner.py`, feature F104) persists
   normalized render-error signatures and can emit preventive hints into the
   generation prompt. It learns from *crashes*. It does **not** learn from
   *aesthetic* losses ("this candidate scored 3/10 because text overlapped").
5. **Domain exemplars** (`services/scene_exemplars.py`, feature F163) provide
   few-shot code examples per domain. They are **hand-curated and static.** The
   tournament produces, every single run, a *proven-good* winning scene that
   could become a new exemplar — and we throw it away.

6. **A measurement rig** (`tools/prompt_quality_lab.py`, feature F168) already
   renders canonical prompts and scores them, reusing the visual-regression
   metrics. It exists to answer "did quality go up or down?" — but nothing
   *runs it as a gate*, so quality can silently regress between releases (which
   is exactly how BUG-8 shipped: a produced-video improvement broke seeking, and
   no quality gate caught it).

**The flywheel is the missing wiring.** When you connect judge → tournament →
parallel farm → learner → exemplars → measurement into a loop, each render makes
the *next* render more likely to be good, and each *release* is provably at
least as good as the last. That is a compounding asset, not a feature.

### 1.3 Why this is the right mission *now* and not the dashboard

The maintained backlog (`docs/NEXT_MISSION_PROMPT.md`) lists a "Render Farm
Dashboard" as the next mission and "UI Modularization" as a later candidate.
Both are good. But:

- The **dashboard observes** the cloud farm; the **flywheel uses** it to raise
  quality. Observability of a farm that renders one candidate at a time is a
  thin win. Observability of a farm running tournaments is a rich one. So the
  dashboard is **more valuable as a sub-component of this mission** (Phase 5)
  than as a standalone.
- **UI modularization** is pure maintainability with no user-visible upside; it
  is the right thing to do *around* a feature that already needs to touch those
  files, not as a mission of its own. This mission does not require it.

This mission subsumes the dashboard, defers the refactor, and delivers the one
thing that moves the product's core metric.

---

## Part 2 — Current state grounding (what exists, cited)

Before building, an agent must confirm these still hold (they were true at
BUG-28 / 168 features / all Phase-2+4 stamped):

| Asset | File / symbol | State | Gap this mission fills |
|---|---|---|---|
| Vision critic | `services/scene_critic.py::critique_video` | Scores a rendered video; result persists on `SceneBundle` (F160) | Not used to *learn*; only to *reject* cache below `min_quality_score` |
| Candidate tournament | `manim_runtime.py::generate_render_tournament`, `_build_scene_candidates`, `_render_and_score_candidates` | Works, opt-in via `settings.scene_candidates`, **sequential + local** | Not parallel, not cloud, no memory of winners/losers |
| Cloud farm | `services/render_backend.py::GitHubActionsClient`, `select_backend`, `provision_render_repo` | Provision/dispatch/poll/download/fallback all fixed (BUG-15/17/18/19/20) | Used one-job-at-a-time; no fan-out, no concurrency cap, no ledger |
| Error learner | `services/error_learner.py::ErrorLearner`, `known_pitfall_hints`, `preventive_pitfalls_block` | Persists crash signatures, injects preventive hints (F104) | Learns from crashes only, never from *low critic scores* |
| Domain exemplars | `services/scene_exemplars.py::EXEMPLARS` | Static hand-curated few-shot per domain (F163) | Never promotes a tournament winner into the exemplar set |
| Quality measurement | `tools/prompt_quality_lab.py` | Renders canonical prompts, scores, compares to prior report (F168) | Never run as a gate; no release-over-release ratchet |
| Visual regression | `tools/visual_regression.py` | Strict mode, quality-failure detection (F162, BUG-21) | Baseline is manual; no tie to the flywheel's winners |
| Config seam | `core/settings.py` fields `scene_candidates`, `scene_candidate_concurrency`, `min_quality_score`, `render_mode` | Present, mostly inert defaults (candidates=1) | The knobs exist; nothing drives them intelligently |

**Read-this-first list for the executing agent:** `manim_runtime.py`
(the tournament methods and the single-scene path they fall back to),
`scene_critic.py` (what `score`/`verdict`/`issues` actually contain and their
ranges), `render_backend.py` (the dispatch/poll/download/fallback state machine),
`error_learner.py` (the persistence format and hint injection points),
`scene_generator.py` (where prompts are assembled and where exemplars/pitfalls
are injected — `_generate_remote`), and `core/models.py::SceneBundle`
(the persisted fields).

---

## Part 3 — The vision: the flywheel, spelled out

Picture one "Solve" run with the flywheel on. Here is the loop, each arrow a
real hand-off between components that exist or that this mission builds:

```
        ┌──────────────────────────────────────────────────────────────┐
        │                     THE QUALITY FLYWHEEL                       │
        └──────────────────────────────────────────────────────────────┘

  (1) PLAN            (2) FAN-OUT             (3) JUDGE
  storyboard  ─────▶  N candidate scenes ───▶ critic scores each on a
  (validated          rendered IN PARALLEL    rubric (correctness, on-frame,
   JSON schema)       on the cloud farm       pacing, legibility, aesthetics)
      ▲                    │                        │
      │                    │                        ▼
      │                    │                 (4) SELECT
      │                    │                 highest-scoring candidate that
      │                    │                 also passes the static gates
      │                    │                        │
      │                    │        ┌───────────────┴───────────────┐
      │                    │        ▼                               ▼
      │              (5) LEARN                                (6) SHIP
      │        winner → promote toward an                 winner → user,
      │        exemplar; losers' critic issues →          quality_score persisted
      │        aesthetic-pitfall hints for the            in cache (min_quality_score
      │        NEXT generation prompt                     gate prevents pinning mediocrity)
      │                    │
      └────────────────────┘   the next run starts from a better prompt

        ┌──────────────────────────────────────────────────────────────┐
        │  (7) RATCHET: prompt_quality_lab runs the canonical suite as   │
        │  a gate. A release may not LOWER the mean critic score or the  │
        │  render success rate vs the committed baseline. CI-style.      │
        └──────────────────────────────────────────────────────────────┘

        ┌──────────────────────────────────────────────────────────────┐
        │  (8) OBSERVE: a render-farm dashboard shows every job, every   │
        │  candidate, every score, every fallback — so a human can SEE   │
        │  the flywheel turning and debug it when it stalls.             │
        └──────────────────────────────────────────────────────────────┘
```

The key insight is that steps (5) and (7) are what make it a *flywheel* rather
than a *tournament*. A tournament makes *this* render better. Learning (5) makes
*the next* render better. The ratchet (7) guarantees the improvement is real and
monotonic across releases. Without (5) and (7) you have spent compute for a
one-time gain; with them you have built an asset that appreciates.

---

## Part 4 — The detailed phased plan (over-explained)

Each phase is independently shippable and independently valuable — you can stop
after any phase and the product is better than before, with the tracker green.
Phases are ordered so that each one de-risks the next.

### Phase 0 — Instrumentation first (measure before you optimize)

**Rationale (over-explained):** The cardinal sin of quality work is optimizing
what you cannot measure — you convince yourself things improved because you
worked hard. The quality analysis names "Observability — you cannot improve what
you do not measure" as a fatal gap. So the very first thing we build is the
measurement, *before* any change to generation, so every later phase can be
judged against a fixed yardstick.

**Build:**
1. A **golden prompt set** frozen in the repo: ~12 prompts spanning the domains
   AetherLab claims to serve (mechanics: pendulum, projectile, collision; waves:
   standing wave, Doppler, interference; fields: dipole, RC circuit; orbital:
   Kepler, escape velocity; modern: relativity-of-simultaneity, photon
   emission). This extends `tools/prompt_quality_lab.py`'s existing 6.
2. A **baseline report** committed under version control (scores + durations +
   render success), produced by running the lab once and freezing the numbers
   (not the videos — videos stay gitignored per `STABILIZATION_PLAN.md`).
3. A `--gate` mode for the lab that **exits non-zero** if a new run's mean
   critic score drops by more than a tolerance, or if render success rate drops,
   vs the committed baseline. This is step (7) of the flywheel, built first so it
   guards everything after it.

**Done when:** `python tools\prompt_quality_lab.py --gate` passes against the
committed baseline; a deliberately-worsened prompt makes it fail; the baseline
JSON is committed; a new feature `F169` covers it.

**Why first:** every subsequent phase's PR must show the gate still passes. That
is how we prove we didn't trade a crash-fix for an aesthetic regression.

### Phase 1 — A real quality rubric (make the judge trustworthy)

**Rationale:** The flywheel is only as good as its judge. If `scene_critic`
returns a vibes-based single number, selecting the "best" candidate is noise.
Before we spend compute generating candidates, the critic must score on an
explicit, stable **rubric** so scores are comparable across runs and models.

**Build:**
1. Replace/augment the critic's scoring prompt with a **fixed structured rubric**
   returning per-axis scores that sum to the total: *physical correctness*,
   *everything-on-frame* (nothing clipped outside the 8×14.2 Manim frame),
   *pacing* (equations dwell ≥ ~3s; no dead `wait(0)`), *legibility* (no
   overlap; readable text size), *aesthetic cohesion* (palette, composition).
   Structured output, validated against a schema; reject-and-retry on malformed
   output rather than silently defaulting (the BUG-7 lesson: silent defaults on
   LLM output cause correctness bugs).
2. Persist the **per-axis breakdown** on `SceneBundle` (extend
   `critique_issues` or add a `critique_breakdown` field, keeping
   `from_json` backward-compatible so old caches still load — the
   `chapter_offsets` cache-safety pattern is the template).
3. A **no-vision fallback**: when no vision model is configured, derive a
   partial rubric score from the *static* validation battery
   (`scene_validation.py`) — out-of-frame checks, overlap heuristics, timing sum
   — so the flywheel still selects intelligently for offline/keyless users
   instead of degrading to random.

**Done when:** the critic returns a validated per-axis breakdown; two visibly
different renders get defensibly different scores; keyless mode still produces a
usable ordering; `F170` covers it; Phase-0 gate still green.

### Phase 2 — Parallel cloud fan-out (turn the farm into a farm)

**Rationale:** The tournament exists but renders candidates one at a time, so
"3 candidates" costs 3× wall-clock — nobody will wait. The cloud farm can render
all N candidates *concurrently*; the wall-clock cost of a 4-candidate tournament
becomes ≈ the cost of one render plus dispatch overhead. This is the step that
makes multi-candidate generation actually usable, which is the whole unclaimed
win.

**Build:**
1. Teach `generate_render_tournament` / `_render_and_score_candidates` to
   dispatch all candidates to the cloud backend **concurrently**, bounded by
   `settings.scene_candidate_concurrency` (the field already exists), with a
   small default cap so we never fan out N=8 workflows at once and trip GitHub
   rate limits.
2. **Fail-soft, per-candidate:** if a candidate's cloud render fails, it is
   scored 0 and dropped, not fatal to the tournament; if the *whole* cloud path
   is unavailable, fall back to the existing sequential-local tournament, which
   falls back to the single-scene path. Three nested safety nets, each already a
   pattern in the codebase.
3. **Deterministic candidate identity:** each candidate carries a stable id into
   dispatch/poll/download so the exact-`job_id` matching (BUG-15) keeps
   candidates from stealing each other's artifacts under concurrency. This is
   the single most likely bug in this phase — write the race test first.

**Done when:** with a live render repo, a 3-candidate tournament renders in
roughly one render's wall-clock, not three; a forced single-candidate failure
does not abort the tournament; no-cloud falls back cleanly; `F171` covers it
with **stubbed** GitHub plus a manual live-smoke script under `tools/`.

### Phase 3 — Close the learning loop (make it a flywheel, not a race)

**Rationale:** This is the phase that converts spent compute into a compounding
asset. Everything before this makes *one* render better; this makes *every
future* render better.

**Build two learning channels:**
1. **Aesthetic-pitfall learning (losers teach).** When a candidate scores low
   for a *specific, recurring reason* the critic can name ("text overlapped",
   "object left frame", "equation shown < 2s"), record it in the error learner
   as an *aesthetic* pitfall (a new category alongside the crash signatures it
   already stores). `scene_generator._generate_remote` already injects
   `preventive_pitfalls_block()`; extend that block to include the top aesthetic
   pitfalls so the *next* generation prompt actively steers away from them. This
   is the crash-learning mechanism (F104) generalized from "don't crash" to
   "don't be ugly."
2. **Exemplar promotion (winners teach).** When a tournament winner scores above
   a high bar *and* passes strict visual regression, offer it as a candidate
   **new exemplar** for its domain. To stay safe and reviewable, do **not**
   auto-mutate `scene_exemplars.py`; instead write the winner to a
   data-dir-backed "exemplar candidates" store, and add a `tools/` command that
   lets a maintainer review and promote one into the curated set via a normal
   code change. (Auto-editing generated code into the prompt path is a supply-
   chain risk; a human gate is the right call — see Part 8.)

**Done when:** a run whose candidate overlapped text causes the *next* run's
generation prompt to contain an anti-overlap hint; a high-scoring winner appears
in the exemplar-candidates store; promotion is a reviewed human step; `F172`
(pitfall learning) and `F173` (exemplar promotion) cover it; Phase-0 gate shows
the mean score trending **up** across two lab runs.

### Phase 4 — Intelligent budget control (spend compute where it pays)

**Rationale:** Rendering 4 candidates for a trivial pendulum is waste; rendering
1 for a hard multi-body scene is stingy. A flat `scene_candidates=N` is a blunt
instrument. Spend compute proportional to expected difficulty and to how bad the
first result is.

**Build:**
1. A **difficulty estimate** from the storyboard (number of acts, distinct
   mobjects, equation count, whether the domain historically renders badly per
   the error learner) that scales the candidate count between 1 and the cap.
2. An **escalation rule**: render 1; if its critic score is below a "good
   enough" threshold, *then* spend the fan-out budget on more candidates.
   Cheap-first, expensive-only-when-needed. This makes the flywheel affordable
   as an always-on default rather than an expert opt-in.

**Done when:** an easy prompt uses 1 candidate, a hard/low-scoring one escalates;
the behavior is deterministic and tested with a stubbed critic; the average
compute per run is bounded; `F174` covers it.

### Phase 5 — Observe the flywheel (the render-farm dashboard, now rich)

**Rationale:** A closed loop you cannot see is a closed loop you cannot debug.
This is the backlog's "Render Farm Dashboard," but now it visualizes something
worth watching: candidates, scores, winners, promotions, fallbacks.

**Build** (folding in the backlog's done-criteria):
1. A backend **job/candidate event ledger** with JSON persistence under the data
   dir: job id, source scene/class, quality, fps, backend, provider; the status
   timeline (queued → in_progress → completed/failed/cancelled/action_required →
   artifact_downloaded → fallback_local); per-candidate critic scores and the
   selected winner; sanitized failure log tails; rate-limit/token-scope messages;
   local-fallback reason and final path. **No secrets** in persisted events
   (reuse `scan_cloud_payload`, feature F156).
2. A **UI panel** reachable from the existing cloud/backend surfaces showing the
   live ledger and, crucially, the **per-run tournament**: N candidate thumbnails
   with their rubric breakdowns and the winner highlighted, so a user/maintainer
   sees *why* this scene was chosen.

**Done when:** a tournament run populates a visible ledger with per-candidate
scores and the winner; failures show a sanitized log tail; no secret ever
appears in persisted events; stub tests cover success/failure/cancel/rate-limit/
fallback; docs explain debugging cloud renders from the dashboard;
`F175`/`F176` cover it.

### Phase 6 — Make it the default, safely (ship the flywheel on)

**Rationale:** All of the above is worthless if it stays an expert opt-in behind
`scene_candidates > 1`. The final phase flips the flywheel on by default for
users who have a render backend and a critic, with escalation (Phase 4) keeping
the cost bounded, and every fail-soft path (Parts 2–3 nets) keeping keyless and
offline users exactly as fast as today.

**Build:** default `scene_candidates` behavior driven by Phase-4 escalation when
a backend+critic are configured; a single clear settings toggle; docs; a final
`prompt_quality_lab --gate` run committed as the new baseline showing the mean
score is up and success rate is not down.

**Done when:** a configured user gets flywheel quality with no new clicks; a
keyless/offline user sees no slowdown and no dead controls; the committed
baseline moves up; `F177` covers the default-on wiring.

---

## Part 5 — Cross-cutting architecture notes (over-explained)

- **Data model / caching.** Any new persisted field (`critique_breakdown`,
  candidate ledgers, exemplar-candidate store) MUST be added with a defensive
  `from_json`/loader so **old caches and old exported bundles still load**
  (P5 persona, the BUG-9/`chapter_offsets` cache-safety pattern). A cache hit
  must always validate the artifact still exists and is playable before reuse
  (BUG-21/23/25 — use the existing `_video_exists` helper).
- **Config.** Reuse the existing seam: `scene_candidates`,
  `scene_candidate_concurrency`, `min_quality_score`, `render_mode`,
  `cloud_*`. New knobs follow the env → app-config → default precedence in
  `load_settings` and MUST round-trip through the Settings dialog
  (the BUG-4 class: every dialog field must persist).
- **Security.** Candidate scene code is still LLM-generated and still runs in a
  real subprocess — it MUST pass `validate_code_safety` (fail-closed) exactly
  like the single-scene path, including the numpy-IO sinks closed in BUG-28.
  Exemplar promotion is a **human-reviewed code change**, never an automatic
  write into the prompt path. Persisted events/ledgers are scrubbed with
  `scan_cloud_payload` (F156).
- **Fail-soft everywhere.** The product must remain fully usable with **no AI
  key, no vision model, no render backend, and no network.** Every phase adds a
  capability *and* its degradation path in the same PR. A keyless student's
  experience may never get slower or more broken because a cloud feature was
  added.
- **Timing correctness.** If any phase touches lesson assembly/offsets, re-verify
  the crossfade offset invariant (`assembly.py::_segment_starts`,
  regression-locked in `t_f148`) — the BUG-6/8/9 family lives here.

---

## Part 6 — Metrics: how we will know it worked

This mission is judged by numbers, not vibes. Track, in the committed lab
reports, across releases:

1. **Mean critic score** on the golden set (Phase 0). Must trend up; must never
   regress past tolerance (the gate enforces this).
2. **Render success rate** on the golden set. Must not drop when candidate count
   rises (parallel fan-out must not add flakiness).
3. **P50 / P90 wall-clock per successful render.** Parallel fan-out (Phase 2) +
   escalation (Phase 4) must keep P90 within a small multiple of today's single
   render, or the feature is unusable regardless of quality.
4. **Compute per run** (candidate-renders issued). Escalation must keep the
   *average* near 1–2 even though the *max* is the cap.
5. **Flywheel evidence:** the number of aesthetic pitfalls learned and exemplar
   candidates promoted over time — the loop is turning if these grow and the
   mean score rises *without* prompt hand-edits.

If (1) rises while (2) holds and (3)/(4) stay bounded, the mission succeeded:
quality compounded and stayed affordable.

---

## Part 7 — Risks and mitigations (pre-mortem)

| Risk | Why it bites | Mitigation |
|---|---|---|
| Critic is noisy → selects the wrong candidate | Whole flywheel amplifies a bad judge | Phase 1 rubric + per-axis breakdown; sanity-check that visibly-different renders score differently before trusting selection |
| Parallel candidates steal each other's artifacts | Concurrent `workflow_dispatch` + branch polling (the BUG-15 race) | Deterministic per-candidate `job_id`; write the race test *first* |
| GitHub rate limits / cost blowup | Fan-out N×; Actions minutes are finite | `scene_candidate_concurrency` cap; escalation (Phase 4); respect `Retry-After` |
| Exemplar auto-promotion poisons the prompt | LLM-written code fed back into generation = supply-chain risk | Human-reviewed promotion only; candidates land in a store, never auto-edit `scene_exemplars.py` |
| Quality gate becomes flaky and gets ignored | Non-deterministic renders make the gate noisy | Tolerances + multi-sample; gate on *mean*, not per-prompt; keep the golden set small and stable |
| Keyless/offline users get slower or broken | Cloud/critic assumed present | Every phase ships its degradation path; keyless fast-path stays single-shot |
| The big files (`manim_runtime.py`, `widgets.py`) rot further | This mission touches them heavily | Localized edits; consider the deferred UI modularization *only* for files this mission already opens |

---

## Part 8 — Non-goals and guardrails

- **Not** a visual redesign; **not** the `widgets.py` refactor (defer unless a
  phase already must touch a module).
- **Not** auto-editing curated prompt/exemplar source from model output.
- **Not** a new provider integration; use the existing OpenAI-compatible seam.
- **Do not** weaken a test, tolerance, or safety check to make a phase pass.
- **Do not** commit secrets, `.env`, `.analysis/`, temp renders, Chroma data, or
  raw regression/candidate videos (`STABILIZATION_PLAN.md`).
- **A green suite is not proof.** For every path you touch, read it end-to-end
  and reason about adversarial inputs *before* trusting the tests — this project
  has shipped bugs behind a fully green 168/168 suite (BUG-6/7/8/17/18/20/26/27/
  28). Write the regression that would have caught the bug, verify it fails
  against the pre-fix code.

---

## Part 9 — The self-contained agent prompt (paste this)

> Everything below stands alone. It repeats the essentials so you need not
> scroll up.

You are working on **AetherLab** (`C:\Users\sunak\Projects\aetherlab`, branch
`codex/stabilize-current-branch`), a PySide6 desktop physics workbench that turns
a prompt into a derivation, RAG citations, an AI-storyboarded Manim animation
(self-healing render, local or GitHub-Actions cloud), a live parametric canvas,
and multi-chapter narrated video lessons. It has a canonical feature catalog
(F01–F168, tracked in `AetherLab_Feature_Tracker.xlsx`/`.csv`, generated only by
`build_feature_tracker.py`) and a harness (`test_features.py`). Last defect is
**BUG-28**; the full F01–F168 user-story audit (Phase-2/Phase-4) is complete.

**Your mission: build the Quality Flywheel** — connect the existing but
disconnected quality parts into a measurable, self-improving loop so scene/lesson
quality *compounds* per render and is *provably non-regressing* per release.

The parts that already exist and must be wired together (verify each by reading
it before building on it): the vision critic with persisted scores
(`services/scene_critic.py`, `SceneBundle.quality_score/critique_verdict/
critique_issues`, F160); the dormant sequential-local candidate tournament
(`manim_runtime.py::generate_render_tournament`, `_build_scene_candidates`,
`_render_and_score_candidates`, F161); the cloud farm
(`services/render_backend.py`, F153–F155); the crash-only error learner
(`services/error_learner.py`, F104); static hand-curated exemplars
(`services/scene_exemplars.py`, F163); the measurement rig
(`tools/prompt_quality_lab.py`, F168); and the config seam (`core/settings.py`:
`scene_candidates`, `scene_candidate_concurrency`, `min_quality_score`).

**Execute in these phases (each independently shippable; stop-anytime with the
tracker green). Do them in order — each de-risks the next:**

0. **Instrument first.** Freeze a ~12-prompt golden set in
   `tools/prompt_quality_lab.py`, commit a baseline report (numbers, not
   videos), and add a `--gate` mode that exits non-zero on a mean-score or
   success-rate regression vs the baseline. Every later phase's PR must keep the
   gate green. New feature `F169`.
1. **Trustworthy judge.** Give `scene_critic` a fixed structured rubric
   (correctness / on-frame / pacing / legibility / aesthetics) with per-axis
   scores validated against a schema (reject-and-retry on malformed LLM output —
   no silent defaults, the BUG-7 lesson). Persist a backward-compatible
   `critique_breakdown`. Add a static-validation-derived fallback score for the
   no-vision path so keyless users still get an intelligent ordering. `F170`.
2. **Parallel cloud fan-out.** Dispatch tournament candidates to the cloud
   backend concurrently, bounded by `scene_candidate_concurrency`; per-candidate
   fail-soft; deterministic per-candidate `job_id` so concurrent renders don't
   steal artifacts (the BUG-15 race — write that test first); nested fallback to
   sequential-local then single-scene. `F171` (stub GitHub + a manual live-smoke
   script).
3. **Close the loop (the flywheel).** (a) Record low-score *reasons* as
   *aesthetic* pitfalls in the error learner and inject them into the next
   generation prompt via the existing `preventive_pitfalls_block` path — losers
   teach. (b) Write high-scoring, regression-passing winners to a data-dir
   exemplar-candidate store and add a `tools/` command for a maintainer to
   review+promote into `scene_exemplars.py` via a normal code change (never
   auto-edit the prompt path — supply-chain risk) — winners teach. `F172`+`F173`.
4. **Budget control.** Estimate difficulty from the storyboard and escalate:
   render 1, and only fan out more candidates if the first scores below a
   threshold. Keeps average compute near 1–2 while the cap stays high. `F174`.
5. **Observe (render-farm dashboard, now rich).** A JSON-persisted job/candidate
   event ledger (status timeline, per-candidate scores, winner, sanitized
   failure tails, fallback reason — scrubbed with `scan_cloud_payload`, F156)
   plus a UI panel showing the per-run tournament (candidate thumbnails + rubric
   breakdowns, winner highlighted). `F175`/`F176`.
6. **Default-on, safely.** Drive default candidate count via Phase-4 escalation
   when a backend+critic exist; one clear settings toggle; commit a new baseline
   showing mean score up, success rate not down. Keyless/offline stays exactly
   as fast (single-shot). `F177`.

**Judge success by numbers** (committed lab reports): mean critic score trends
up and never regresses past tolerance; render success rate holds; P90 wall-clock
stays within a small multiple of one render; average compute per run stays
near 1–2; learned-pitfall and promoted-exemplar counts grow while the mean score
rises *without* prompt hand-edits.

**Non-negotiable ground rules:**
- A green 168/168 suite is **not** proof — this project ships bugs behind green
  (BUG-6/7/8/17/18/20/26/27/28). For every path you touch, read it end-to-end,
  reason about adversarial inputs, and write the regression that fails against
  the pre-fix code.
- Every defect fix follows the canonical workflow: `DEFECTS["Fxx"]` in
  `build_feature_tracker.py` → row in `ERRORS_FOUND.md` (continue BUG-29…) →
  regression in `test_features.py` → `python test_features.py` →
  `python build_feature_tracker.py` → `python tools\tracker_integrity_audit.py
  --check`. Every new feature gets an `Fxxx` catalog row + story + a `t_fxxx`
  test; run `tools\feature_surface_audit.py --check` too.
- Build order to keep the tracker self-test green: **rebuild tracker → run
  harness → rebuild tracker → integrity audit** (the generator consumes
  `feature_test_results.json`, and `t_f165` compares the CSV to the generator).
- Render-affecting work also runs strict visual regression
  (`python tools\visual_regression.py --out visual_regression\runs\<name>
  --compare visual_regression\baseline\current --strict`) and you open the MP4s.
- `ui/widgets.py` has **mixed CRLF/LF** — the Edit tool normalizes the whole file
  (a 600-line spurious diff). Patch it at the byte level with **LF** added lines
  and confirm `git diff --check` is clean.
- Fail-soft is sacred: no AI key, no vision model, no backend, no network — the
  product stays fully usable and no slower for keyless users. Every phase ships
  its degradation path.
- New persisted fields need backward-compatible loaders (old caches/bundles must
  load — the `chapter_offsets` pattern); cache hits validate the artifact via
  `_video_exists`; candidate code passes `validate_code_safety`; persisted events
  are secret-scrubbed; never commit `.env`/keys/`.analysis/`/temp renders/Chroma/
  raw videos.
- Small commits grouped by concern. End with all gates green
  (`test_features.py`, `pytest -q`, `compileall`, both audits, strict visual
  regression, `git diff --check`) and a hand-audit note listing the paths you
  read and the adversarial cases you reasoned through.

**Definition of done:** the flywheel runs default-on for configured users and
fail-soft for everyone else; the committed golden-set baseline shows mean critic
score up and success rate not down; the ledger/dashboard makes each tournament
visible; `F169`–`F177` are cataloged, story-written, tested, and stamped; all
mechanical gates green; a written hand-audit note accompanies the final status.
