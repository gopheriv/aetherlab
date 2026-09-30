# AetherLab — Engineering Handoff Brief

**Written:** 2026-09-22 · **For:** an AI engineer picking this up cold
**Repo:** `C:\Users\sunak\Projects\aetherlab` (Windows, Python 3.14, git repo)

You have no prior context on this codebase. Read §1–§3 before touching anything;
they contain landmines that will otherwise cost you hours. §4 is the actual work.

---

## 1. What AetherLab is

A **desktop physics workbench** (PyQt6). The user types a physics problem or topic and gets a
narrated, animated explanation. Two modes from one prompt bar:

- **Solve** — one problem → 4-stage pipeline: **Solve** (LLM derivation) → **RAG** (citations
  from real textbooks) → **Scene** (AI-storyboarded Manim animation) → **Render** (self-healing MP4).
- **Learn** — a topic → multi-chapter narrated video lesson with transcript, fact-checks,
  quiz questions, and a study-guide PDF.

Plus a **live parametric canvas**: drag sliders (damping, stiffness, gravity) and watch solution
curves respond in real time.

### Architecture map (only what you need)

```
aetherlab/
  core/
    settings.py          # AppSettings + load_settings(); provider resolution precedence
    models.py            # ProblemRequest, SolverResult, RagResult, RagHit, SceneBundle
  services/
    model_policy.py      # ★ LLM PATHWAY layer — timeouts/retry/thinking per model family
    scene_generator.py   # LLM prompts + storyboard pass + codegen pass + repair/revise
    manim_runtime.py     # render subprocess, self-heal, tournament, generate_scene_async
    scene_validation.py  # static pre-render lint (names/kwargs/LaTeX/hygiene/PERF)
    code_safety.py       # fail-closed AST safety gate (generated code runs w/ full privileges)
    scene_templates.py   # deterministic LaTeX-free fallback templates (5 domains)
    scene_components/    # 15 curated numeric-driven components (pendulum, orbit, quantum…)
    rag.py               # ChromaDB retrieval + filesystem fallback
    web_references.py    # Wikipedia + Wikibooks providers
    starter_library.py   # OpenStax catalog + downloader
    render_backend.py    # local vs GitHub-Actions cloud render
  ui/
    live_canvas.py       # the interactive parametric canvas
```

### Critical control flow — `generate_scene_async()` (`manim_runtime.py:194`)

```
1. _compose_curated()   → if a curated component matches the topic, RETURN IT.
                          The LLM is never called. This is INTENTIONAL and good.
2. if api_key:          → SceneGenerator.generate() → LLM storyboard + codegen
3. else / on failure:   → _build_scene_code() deterministic template
```

**You will misdiagnose things if you forget step 1.** Topics like pendulum/orbit/wave have curated
components and never reach the LLM. To exercise the LLM path, pick a topic with **no** component
(e.g. "blackbody radiation", "Planck's law").

---

## 2. Current configuration (verified 2026-09-22)

**Provider: MiniMax-M3** via MiniMax's OpenAI-compatible endpoint.

| Setting | Value | Where |
|---|---|---|
| `AETHERLAB_OPENAI_API_KEY` | `sk-cp-JfBv…` (working) | persistent Windows **User env** |
| `AETHERLAB_OPENAI_BASE_URL` | `https://api.minimax.io/v1` | persistent User env |
| `AETHERLAB_LLM_MODEL` | `MiniMax-M3` | persistent User env |
| `AETHERLAB_LLM_TIMEOUT` | `900` | persistent User env |
| `llm_timeout_seconds` | `900` | `%LOCALAPPDATA%\AetherLab\settings.json` |

**Resolution precedence** (`core/settings.py::load_settings`):
`AETHERLAB_OPENAI_API_KEY` > `OPENAI_API_KEY` > `GPT_API_KEY` > `DASHSCOPE_API_KEY` > app-config.
Env wins over the app config file. **Env changes need a fresh process** (already-running apps keep the old env).

### Measured MiniMax-M3 characteristics (live probe, not guesses)
- One codegen call: **335 s**
- Spends **all 32 767 completion tokens on reasoning** (`reasoning_tokens == completion_tokens`)
- Returns `finish_reason: "length"` **but still contains a complete, usable scene class**
- Supports `thinking: {"type": "disabled"}` in the request body (currently **not** used — see M6)

### Installed stack
manim **0.20.1** (latest is 0.21.0), chromadb, PyQt6, PyMuPDF, edge-tts, PyAV, matplotlib,
ffmpeg, LaTeX (pdflatex/dvisvgm) — all present and working.

---

## 3. LANDMINES — read before running anything

1. **`python test_features.py` DELETES the user's live config.**
   `test_features.py:286` and `:3432` call `app_config_path().unlink(missing_ok=True)` against the
   *real* `%LOCALAPPDATA%\AetherLab\settings.json`. Running the suite wipes provider settings.
   → **Back up that file before running the suite.** Fixing this is **Mission M2**.

2. **`render_mode` is currently `cloud`.** Per the project's own history, cloud + tournament =
   **~12 HOURS per solve** (GitHub dispatch + queue + 30-min poll timeouts + HTTP 409 races).
   Local renders take ~30 s–3 min. It should almost certainly be `local`.
   `render_backend._github_token()` falls back to `gh auth token`, so cloud can be **live even when
   `settings.github_token` is empty** — never conclude cloud is off from an empty token.

3. **Two test failures are expected and NOT your fault:**
   - **F165** — tracker-artifact audit; `AetherLab_Feature_Tracker.csv/.xlsx` are stale vs
     `build_feature_tracker.py`. Pre-existing uncommitted WIP.
   - **F128 / F153** — pass only in a **clean env**. They assert a pristine provider environment,
     but the machine has persistent `AETHERLAB_*` vars. Run them as:
     `env -u AETHERLAB_OPENAI_API_KEY -u AETHERLAB_OPENAI_BASE_URL -u AETHERLAB_LLM_MODEL -u DASHSCOPE_API_KEY python test_features.py`

4. **`t_f06` enforces a "no hidden timeout floors" contract (BUG-34).** It asserts
   `openai_client_kwargs(bounded)["timeout"] == 17` and greps source for `timeout=max(`.
   **Never silently override an explicitly configured timeout.** Change *defaults*, not effective values.

5. **MiniMax keys are scoped per domain.** The current key works on `api.minimax.io` and returns
   401 on `api.minimaxi.com`. A previous key was the inverse. **Probe both** when a key 401s.

6. Don't put secrets in files in the repo. Pass keys via env.

---

## 4. MISSIONS

Ordered by value. Each has **Goal → Approach → Acceptance criteria**.

---

### M1 — Confirm the AI scene path actually produces a real scene ★ START HERE

**Background.** The headline bug was: every AI scene silently became a generic ~5 s template
("a placeholder video… it doesn't even answer my question") while the pipeline reported
`status=rendered` with no repairs. Root cause was a **timeout** (config 180 s < the 335 s M3 needs),
compounded by a retry that burned a second full budget, and a fallback that was invisible.

Fixes already landed (see §5). What is **not yet proven** is a full successful run: MiniMax
generating a real scene that renders.

**Approach**
1. Pick a topic with **no curated component** (blackbody radiation / Planck's law).
2. Build `ProblemRequest` + `SolverResult` + empty `RagResult`, call
   `ManimRuntime.generate_scene_async(...)`.
3. **Assert `bundle.used_fallback is False`** — this is the whole test. If True, read
   `bundle.fallback_reason`; it names the exact failure and remedy.
4. Then `render_scene_with_repair(bundle, s, quality="l", max_repairs=2, max_revisions=0)`.
5. Expect ~10–12 min total (two M3 calls at ~335 s each + render).

**Acceptance criteria**
- `used_fallback == False` and code length ≫ 1821 chars (the template's size).
- `status == "rendered"`, an MP4 exists, and the animation is actually *about the topic*.
- If it still falls back, `fallback_reason` tells you why — trust it, it is accurate.

---

### M2 — Stop the test suite destroying the live config

**Goal.** `python test_features.py` must never touch `%LOCALAPPDATA%\AetherLab\settings.json`.

**Approach**
- `test_features.py:286` and `:3432` call `app_config_path().unlink(missing_ok=True)`.
  `app_config_path()` resolves to `AETHERLAB_DATA_DIR` if set, else `%LOCALAPPDATA%\AetherLab`.
- Wrap both tests (`t_f07`-area and `t_f153`) so they set `AETHERLAB_DATA_DIR` to a temp dir for
  their duration and restore it in a `finally`. `t_f128` already does this pattern with
  `S._default_data_dir` — copy that approach for consistency.
- Bonus: have the harness snapshot/restore the real config around the whole run as a safety net.

**Acceptance criteria**
- Write a sentinel value into the real config, run the full suite, confirm it survives.
- F07/F153/F128 still pass in a clean env.

---

### M3 — Decide and set `render_mode`

**Goal.** Stop cloud rendering silently costing hours per solve.

**Approach**
- Ask the user first — this is a consequential switch.
- If yes: `save_app_config({"render_mode": "local"})`.
- Verify with `render_backend.select_backend(settings)` and by calling
  `CloudRenderBackend.available()` — remember it may return True via `gh auth token` even with an
  empty `github_token`.

**Acceptance criteria**
- A solve renders locally in ~30 s–3 min, not minutes-to-hours of polling.

---

### M4 — Make auto-generated animations longer and richer ★ HIGH USER VALUE

**Background.** The user asked for **30-second** animations. Findings:
- The **renderer** handles 30 s fine — a hand-authored 30 s scene rendered clean
  (exactly 30.0 s / 900 frames / 89 s wall).
- The **auto-generator** targets ~15–22 s by design, and an observed LLM run produced only **5 s**.
- Nothing threads a requested duration into the storyboard. That's the gap.

The user's last request (cut off mid-sentence) was *"more details on animations"* — they want
richer, longer, more detailed scenes.

**Approach**
1. Add `duration_target_s` to `ProblemRequest` (or thread it as a parameter) with a sensible default.
2. `scene_generator.STORYBOARD_SYSTEM_PROMPT` (line ~190) designs the acts — inject the target so
   the director allocates act durations to sum to it. This is the real lever: act durations are
   decided at storyboard time, and codegen just implements them.
3. `SCENE_CODEGEN_SYSTEM_PROMPT` constraint 7 already says "match each act's duration_s (±20%)" —
   keep that; it will follow the storyboard.
4. `scene_validation.estimate_duration()` gives an advisory beat-sum **without rendering** — use it
   as a cheap gate: if the estimate is far below target, regenerate rather than render.
5. For "more detail": raise the act count / required on-screen elements in the storyboard prompt
   (labelled axes, live DecimalNumber readouts, annotated hero frame, a recap beat).

**Acceptance criteria**
- Request 30 s → `estimate_duration()` within ±20 % of 30 s → rendered MP4 is ~30 s (verify with
  `ffprobe -show_entries format=duration`).
- Scene still passes `validate_scene(code, require_motion=True)` and the safety gate.
- Watch for `PERF:SEQUENTIAL_PLAY` warnings — longer scenes tempt the model into many `self.play`
  beats; it should batch with `LaggedStart`.

---

### M5 — Manim upgrades (backlog)

Full research is in **`MANIM_UPGRADE_NOTES.md`** in the repo root. Already done: `--seed`
(deterministic renders / fair tournaments) and `PERF:*` validation + prompt idioms. Remaining,
in recommended order:

1. **Version bump 0.20.1 → 0.21.0.** Two breaking changes touch code here: the **MathTex splitting
   rewrite** (revisit `repair_text_mode_math` / `check_latex_strings`) and **color constants**
   (`YELLOW_C` fixed; `PURE_CYAN/MAGENTA/YELLOW` added — the allowlist is built dynamically from the
   installed package, so mostly auto-absorbed). Run F105/F106/F132 after.
2. **Partial render on revise** (`-n start,end`) — render only the frames the vision critic flagged
   instead of the whole scene. Biggest saving on the most expensive loop.
3. **Repair-chain caching** — keep `--disable_caching` for first renders/tournament candidates, but
   allow caching within one scene's repair lineage (same media_dir, same seed). Measure before/after.
4. **Render telemetry** — `render_ledger` exists; add duration, peak RSS, failure-class per render.
5. **OpenGL renderer** behind a flag — biggest wall-clock ceiling, but headless GL on CI is a time
   sink. Benchmark locally first. Do this last.

---

### M6 — Consider disabling MiniMax "thinking" for codegen

**Background.** M3 burns its **entire** 32 k token budget reasoning and takes 335 s. MiniMax supports
`thinking: {"type": "disabled"}` in the request body. That would fix latency at the source rather
than paying for it with a 900 s timeout.

**Counter-argument (recorded as a deliberate earlier decision):** reasoning likely improves code
quality for scene generation, so thinking was intentionally left ON for M3.

**Approach.** `model_policy.codegen_request_kwargs()` is now pathway-driven — it returns
`{"extra_body": {"enable_thinking": False}}` for the `hybrid-qwen` pathway. Adding a MiniMax variant
is a small change. **Do it as an A/B**: generate N scenes each way, compare (a) wall-clock, (b) the
vision critic's `quality_score`, (c) how many needed repair. Decide on data, not vibes.

---

### M7 — Tracker artifacts (F165)

`AetherLab_Feature_Tracker.csv/.xlsx` are out of sync with `build_feature_tracker.py`.
Regenerating (`python build_feature_tracker.py`) would make F165 green — **but those files plus
`build_feature_tracker.py`, `feature_test_results.json` and `test_features.py` are all uncommitted
WIP from a prior session.** Confirm with the user that the WIP is expendable before regenerating.

---

## 5. What changed in the session before yours

All verified: ruff clean · pytest 37/37 · 214/215 features (only the pre-existing F165).

**LLM pathway layer** — new in `model_policy.py`:

| Pathway | Matches | Default budget | Retry on timeout | Thinking toggle |
|---|---|---|---|---|
| `reasoning` | MiniMax-M*, QwQ, DeepSeek-R*, o1–o9, GLM-*-think | 900 s | no | n/a |
| `hybrid-qwen` | qwen3.5/6/7-plus/max/flash | 60 s | yes | disabled |
| `standard` | everything else | 60 s | yes | — |

`ModelPathway` + `resolve_pathway()` + `settings_pathway()` + `default_timeout_for()` +
`timeout_shortfall()`. Every LLM caller (`llm.py`, `scene_generator`, `scene_critic`,
`lesson_planner`, `fact_check`) goes through `openai_client_kwargs()`, so **adding a model family
fixes timeouts everywhere at once**.

**Bug fixes**
- Timeout: reasoning default 900 s; ceiling 900 → 1800 s. *Explicit config is never overridden*
  (BUG-34) — only the default is model-aware; `timeout_shortfall()` warns instead.
- Fail-fast: `retry_on_timeout=False` for reasoning (a retry just burns a second budget).
- **Fallback made visible:** `SceneBundle.used_fallback` + `.fallback_reason` (cache round-trips;
  legacy rows default `False`/`""`), plus a `FALLBACK: …` diagnostic on all three non-AI paths.
- Truncation guard: `finish_reason == "length"` no longer discards a reply that contains a valid
  scene class — extract first, fail only if nothing usable survives.

**Manim:** `--seed` (code-derived, deterministic) + four `PERF:*` hygiene checks
(`REDRAW_REBUILD`, `UPDATER_LOOP`, `SEQUENTIAL_PLAY`, `PARAMETRIC`) + prompt clause 12.

**RAG:** hybrid vector+lexical rerank, `(path,page)` + excerpt dedup, MMR diversity, over-fetch pool;
added OpenStax **Physics** book and a **Wikibooks** provider alongside Wikipedia.

---

## 6. How to verify your work

```bash
# lint (only your files — ~19 pre-existing findings elsewhere)
python -m ruff check aetherlab/services/<file>.py --output-format=concise

# fast suite
python -m pytest -q                      # expect 37 passed

# full feature suite — BACK UP THE CONFIG FIRST (landmine #1), clean env (landmine #3)
env -u AETHERLAB_OPENAI_API_KEY -u AETHERLAB_OPENAI_BASE_URL -u AETHERLAB_LLM_MODEL \
    -u DASHSCOPE_API_KEY python test_features.py    # expect 214/215, only F165

# run a single feature test
python -c "import sys;sys.argv=['t'];import test_features as m;print(m.t_f106())"

# verify a rendered video's real duration
ffprobe -v error -show_entries format=duration -show_entries stream=nb_frames <file>.mp4
```

**Working principles for this codebase**
- It is unusually well-instrumented: fail-soft everywhere, advisory diagnostics, a 215-feature
  catalog. **Trust the diagnostics** — `fallback_reason` and the `PERF:`/`HYGIENE:` warnings are accurate.
- **Measure before fixing.** The headline bug was misdiagnosed twice from plausible-looking evidence
  (HTTP 200s in the log, a "successful" render) before a live probe showed the real cause. Two HTTP
  200s did **not** mean the scene came from the model.
- Prefer changing **defaults** over overriding explicit user configuration.
- Every new code path must be **fail-soft** — nothing in this pipeline is allowed to raise into a render.
