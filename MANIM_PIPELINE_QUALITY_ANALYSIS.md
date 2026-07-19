# AetherLab Manim Pipeline — Brutally Honest Quality Analysis

**Scope:** architecture, generation pipeline, orchestration, prompt strategy, scene/animation
planning, rendering, failure modes, and creative ceilings — evaluated against a single goal:
**world-class, professionally directed Manim animations.** Cost, speed, and simplicity are
explicitly *not* goals; unlimited compute, tokens, and render time are assumed.

**Verdict up front:** AetherLab today is a *render-success* pipeline, not a *quality* pipeline.
Every gate in the system asks "did an MP4 come out?" — no gate ever asks "is the video good?"
The cinematic system prompt is genuinely strong creative direction, but it is **aspiration
without enforcement**: nothing downstream verifies that a single one of its demands
(three acts, hero frame, living ending, legible composition) actually happened on screen.
The gap between "renders without crashing" and "world-class" is where this entire document lives.

---

## 1. Pipeline map — where quality is (and isn't) enforced

```
prompt
  │
  ▼
AsyncLLMCoordinator.solve          llm.py            1 LLM call, temp 0.2
  │   summary / steps / keywords / variables / plot payload
  ▼
LocalVectorRag.search              rag.py            chromadb (or filesystem fallback)
  │   top-5 textbook excerpts
  ▼
SceneGenerator.generate            scene_generator.py  1 LLM call, temp 0.4, 32k tokens
  │   ONE completion = concept + staging + choreography + code
  │   gates: <think>/fence strip → class rename → compile() → (SyntaxError? 1 retry) → fallback
  ▼
ManimRuntime.render_scene_with_repair   manim_runtime.py
  │   subprocess `manim render` → on render-error: ≤2 LLM repair rounds (temp 0.2) → re-render
  ▼
MP4 exists  ──►  SUCCESS. Nobody looks at it. Ever.
```

Quality enforcement points in this pipeline: **zero.** The gates are syntactic
(`compile()`), procedural (subprocess exit code), and existential (`_find_video()` finds an
mp4). There is no aesthetic, compositional, temporal, or perceptual gate anywhere.

---

## 2. FATAL GAP #1 — Nobody ever watches the video

**Severity: critical. This is the single largest obstacle to world-class output.**

The definition of success is `returncode == 0` and an `.mp4` on disk
(`manim_runtime.py:194–218`). The system has:

- **No frame extraction.** Not one frame of the rendered video is ever inspected.
- **No VLM critique pass.** The task is inherently visual, yet no vision model exists anywhere
  in the pipeline. Confirmed by grep: zero matches for narration/audio/storyboard/critique/vision
  across `aetherlab/` (the only hit is a UI-copy comment, `main_window.py:781`).
- **No compositional checks.** Text off-frame, mobjects overlapping into mud, illegible
  font sizes at 480p, color collisions with the background, a title covering the hero object —
  all of these render "successfully" and ship.
- **No temporal checks.** Dead air, a 12-second static hold, an ending frozen on the last frame
  (explicitly forbidden by prompt §7), total duration wildly off the 15–22s target — invisible.
- **The repair loop only fires on crashes** (`manim_runtime.py:240–245`,
  `status == "render-error"`). A scene that renders *badly* is indistinguishable from a scene
  that renders *beautifully*. Aesthetic failure is not a recognized failure mode.

Consequence: the elaborate cinematic prompt (§1–§7, anti-patterns and all) is written into the
void. The model can ignore every directive and the system will happily cache the result as a
success (`cache.store_scene`), pinning the mediocrity forever (see §11).

**What world-class requires:** after every render, extract N frames (e.g. 1/sec + first/last),
feed them with the original creative brief to a vision-capable judge, score against an explicit
rubric (composition, legibility, palette discipline, act structure, hero frame present, living
ending), and loop refinement until the rubric passes. With unlimited compute this is not
optional — it is the core of the architecture, and it is entirely absent.

---

## 3. FATAL GAP #2 — Single-shot generation; no planning stage

**Severity: critical.**

The entire creative act — concept, scenario, staging, palette, choreography, timing, *and* the
~150 lines of code implementing it — happens in **one completion**
(`SceneGenerator._generate_remote`, `scene_generator.py:255–322`). This forces the model to be
director, cinematographer, and programmer in a single token stream, with predictable results:

- **Creativity and correctness compete for the same attention.** Mid-generation, the model is
  simultaneously tracking Manim API minutiae and three-act structure. Code correctness pressure
  systematically flattens creative ambition — the model retreats to safe patterns (axes + curve)
  because they are less likely to crash.
- **No intermediate representation.** There is no storyboard, shot list, or scene plan that can
  be independently generated, critiqued, revised, or approved before a line of code exists.
  World-class animation pipelines (human or automated) *always* separate: creative treatment →
  storyboard → animatic → final. AetherLab has: prompt → final.
- **The 3-act structure is unenforceable prose.** Prompt §1 demands ESTABLISH → EVOLVE → REVEAL
  with act breaks and a hero frame. Nothing parses the generated code to verify acts exist, no
  plan object records where the hero frame is supposed to be, no critique compares intent to output.
- **No revision of *intent*, only of *code*.** The repair loop can fix a kwarg; it cannot fix a
  boring concept, because the concept was never reified as an artifact that could be evaluated.

**What world-class requires:** a planning call (high temperature, no code) producing a structured
storyboard — beats, durations, staging, palette, hero frame description, narration script — then
a *separate* codegen call (low temperature) that implements the approved storyboard beat by beat,
then verification that each beat exists in the code. The storyboard is also the contract that
narration sync (§4) and the VLM critique (§2) evaluate against.

---

## 4. FATAL GAP #3 — No narration/audio subsystem at all

**Severity: critical relative to the stated goal.**

The stated goal includes "accurate synchronization between narration, visuals, and animations."
The system has **no concept of narration whatsoever**:

- No narration script generation (the solver's `derivation_steps` are UI text, never voiced).
- No TTS integration of any kind.
- No use of Manim's `Scene.add_sound` or any audio muxing (no ffmpeg audio stage).
- **No timeline/beat model to sync against** — and this is the deeper problem. Even if TTS were
  bolted on tomorrow, there is nothing to align it *to*: `run_time` values are free-form LLM
  guesses scattered through generated code, with no machine-readable schedule of what happens when.

Narration sync is not a feature you add at the end; it is a *timing contract* the whole pipeline
must honor. The storyboard (§3) must specify per-beat durations; codegen must emit code that
respects them; the renderer must verify actual durations match (Manim scene duration is
deterministic and computable); TTS must be generated per-beat and fitted (or the beat stretched).
None of the scaffolding for this exists.

---

## 5. Validation gap — `compile()` is the only static gate

**Severity: high.**

`compile(code, '<generated>', 'exec')` (`manim_runtime.py:81`, `:100`, `:255`) catches syntax
errors and nothing else. The dominant real-world failure classes all pass it:

| Failure class | Passes compile? | Caught where? |
|---|---|---|
| Invented kwargs (`Axes(show_numbers=True)`) | ✅ | render crash → repair |
| Nonexistent methods (`mobject.set_glow()`) | ✅ | render crash → repair |
| Bad LaTeX in `MathTex` (unbalanced braces, undefined macros) | ✅ | render crash (LaTeX is a top Manim killer) |
| Wrong-but-valid API (mobject drawn off-frame) | ✅ | **never** |
| Runtime math errors (div-by-zero in a lambda at t=0) | ✅ | render crash → repair |
| Infinite/pathological updaters | ✅ | render **timeout** → **no repair** (see §6) |

Missing static gates that would convert crash-repair cycles into first-try successes:
- **Manim API linting**: AST-walk the generated code against the installed Manim's actual
  signatures (`inspect.signature` on real classes) — invented kwargs and methods are detectable
  *before* render.
- **LaTeX pre-validation**: extract every `MathTex`/`Tex` string and compile it against the same
  LaTeX toolchain in isolation (milliseconds each).
- **Import-and-instantiate dry run**: `manim --dry_run` (or importing the module and constructing
  the scene without rendering) catches a large class of runtime errors in seconds.
- **Duration estimation**: sum `run_time`s + `wait`s statically; reject scenes wildly outside the
  15–22s contract.

Bitter footnote: an AST safety/validation gate (`code_safety.py`) **existed in this repo** and was
removed from `master` in this session's force-push (recoverable — see §17).

---

## 6. Repair-loop weaknesses — including one bug-level hole

**Severity: high.**

`render_scene_with_repair` (`manim_runtime.py:222–264`) is a genuinely good idea implemented
with four material weaknesses:

1. **`render-timeout` is terminal — repair never fires.** The loop condition is
   `status == "render-error"` only (`:241`). A scene that times out (`render-timeout`, `:203`)
   gets no repair attempt. This is exactly backwards for a quality-first system: the *most
   ambitious* scenes — heavy `always_redraw`, many beats, high fps — are the likeliest to time
   out, so the pipeline selectively kills its best attempts while patiently repairing its
   mediocre ones. A timeout with the elapsed time fed back ("your scene exceeded 600s; reduce
   updater load, keep the design") is an eminently repairable failure.
2. **Repair is aesthetics-blind by design.** The repair prompt commands "change as little as
   possible" (`scene_generator.py:188`). Correct for crashes; but it means the repair path can
   only ever preserve the original's quality, never lift it. There is no "make it better" loop
   anywhere — only "make it not crash."
3. **1500-char stderr tail can truncate the root cause** (`manim_runtime.py:198`,
   `scene_generator.py:346`). Manim tracebacks are long; the actual exception is at the end
   (usually fine), but multi-error output, LaTeX log spew, or a chained exception can push the
   real cause out of the window. With unlimited tokens, truncating the error context is a pure
   own-goal — send the whole thing.
4. **No cross-session error learning.** Every repair rediscovers the same model-specific failure
   habits from scratch. The same invented kwarg will crash next week's scene too. A persistent
   error-pattern store, fed back into the *generation* prompt ("APIs you have previously
   hallucinated: ..."), converts repair knowledge into first-try quality. This also existed
   (`error_learner.py`) and was lost in the force-push (§17).

Also worth noting: repairs are capped at 2 (`max_repairs=2`, `:227`) — an arbitrary economy
measure that contradicts the unlimited-budget stance. The right cap is "until the VLM judge says
ship it or the candidate is abandoned for a better one."

---

## 7. The fallback ladder is anti-creative by construction

**Severity: high.**

Every failure path terminates in `_fallback_scene` (`scene_generator.py:395–447`) or the static
template (`manim_runtime.py::_MANIM_SCENE_TEMPLATE`): a title, one set of axes, one damped-sine
curve, one dot. Prompt §7 explicitly names this composition as the anti-pattern
("a bare Axes with a single static curve and a title... That is a screenshot, not a scene").

**The system's floor is the thing its own creative direction defines as unacceptable.** And the
floor is common: no key → fallback; two generation hiccups → fallback; truncation twice →
fallback; compile failure after retry → fallback. Worse, the fallback hardcodes the
damped-oscillator visual regardless of domain — a Kepler-orbit prompt that falls back gets…
a damped sine wave. Wrong physics, presented confidently.

A serious fallback ladder has rungs: full cinematic scene → domain-aware rich template (orbit
template for orbits, wave template for waves — parameterized by solver variables) → minimal
correct scene. Domain-aware templates (`scene_templates.py`) existed in the discarded PRs (§17).

---

## 8. Prompt-engineering critique

**Severity: medium-high.** The cinematic prompt (`scene_generator.py:14–178`) is well-written
creative direction. Its weaknesses are structural, not stylistic:

1. **No few-shot exemplars — the single highest-leverage missing piece.** The prompt *describes*
   greatness for ~7,000 characters but never *shows* one line of it. One or two complete,
   curated, verified-rendering exemplar scenes (a Kepler orbit with swept sectors; a Fourier
   build-up) would do more for output quality than every adjective in §1–§7 combined. Models
   imitate far better than they follow abstract direction. With a 250k context window
   (`llm_context_window`), there is room for an entire exemplar *library* selected by domain.
2. **One mega-prompt for all domains dilutes attention.** All seven domain playbooks (§6) ship
   on every request; six are noise. The playbook, palette suggestions, and anti-patterns should
   be *assembled per-request* from the solver's keywords — a Kepler prompt should carry the
   orbit playbook and an orbit exemplar, nothing about thermodynamics pistons.
3. **Flat temperature 0.4 (`:310`) serves neither master.** Too cold for bold scenario ideation,
   too warm for precise API-correct codegen. The two-call architecture (§3) resolves this
   properly: ideation at 0.9–1.0, codegen at 0.1–0.2. In the current single-call design, 0.4 is
   a compromise that guarantees mediocrity on both axes.
4. **Fragile templating.** The system prompt is injected via `.replace("{class_name}", ...)`
   (`:287`) because the body contains literal braces (palette sets like `{BLUE_D, TEAL, ...}`).
   This works but is one careless edit away from a silent no-op (a typo'd placeholder simply
   doesn't get replaced, and the class-rename regex downstream papers over it — until it doesn't).
5. **RAG is decorative.** Three hits × 200 chars (`:281–283`) of textbook excerpt, labeled
   "reference flavor." A 28,000-chunk university-physics corpus is available and the scene
   generator sniffs 600 characters of it. Retrieved content could drive *factual staging* (real
   constants, correct orbital eccentricities, actual formulas via the textbook's own notation)
   — right now it cannot influence anything meaningfully.
6. **Solver → scene information loss** (see also §14): `derivation_steps[:6]` as prose strings
   (`:272–274`), variables as bare `name = value` with no units, ranges, or semantics (`:276–278`).
   The model then *invents* LaTeX for equations the solver already derived — and invented
   `MathTex` is a top render-crash source. The solver should emit equations *as LaTeX* and
   variables with units/ranges/meaning; the scene prompt should forbid inventing formulas
   not present in the brief.

---

## 9. No multi-candidate generation — the biggest unclaimed win from "unlimited compute"

**Severity: high (given the stated budget).**

The pipeline generates exactly **one** scene per request. Single-sample generation means output
quality is a lottery ticket on one draw of a stochastic process. With unlimited compute, the
canonical architecture is a **tournament**:

- Generate N storyboards (different seeds/temperatures/staging concepts) → judge → keep top k.
- Implement the k storyboards → static-validate → render at draft quality (480p15 is *perfect*
  for this — its true calling is candidate evaluation, not final output).
- VLM-judge the draft renders against the rubric → pick the winner → refine it (targeted
  critique → revision), then render the final at 1080p/4K/60fps.

Nothing in the codebase anticipates this: there is no candidate abstraction, no scoring
interface, no notion of "several SceneBundles competing for one slot." `SceneBundle` is
singular by design (`models.py`), the cache stores one scene per key (`cache.store_scene`),
and the UI has one Scene tab. Retrofitting a tournament is the largest architectural change
recommended here — and the one most directly translating "unlimited compute" into quality.

---

## 10. Rendering-pipeline ceilings

**Severity: medium-high.**

- **The default output is 480p15.** `_RENDER_QUALITY = "l"` (`manim_runtime.py:28`), and the UI
  quality selector defaults to Draft (`widgets.py::CommandBar`, index 0). A quality-first product
  whose default artifact is 480p at 15fps is self-refuting. (The `--fps` flag from the render
  tier does override the fps half on capable machines — but 480p remains the default canvas.)
- **4K exists only as a timeout entry.** `timeout_map` knows `"k": 900` (`manim_runtime.py:167`)
  but no UI surface, config, or pipeline path ever requests `-qk`. The ceiling users can reach
  is 1080p.
- **Renders ignore the app's design system.** Manim's stock black background and default fonts
  are used as-is; the app's own visual identity (cyan/emerald/violet on `#0A0A0F`, Cascadia
  Code) never reaches the video. A "consistent visual style" goal requires injecting a theme
  (background, `Text` font, default palette) into every generated scene — mechanically trivial
  via a preamble, currently absent. (Render theming — `theme.py` — existed in the discarded
  PRs; §17.)
- **One Scene per video, no assembly stage.** The pipeline renders a single `Scene` class and
  stops. No multi-scene compositions, no cross-scene transitions, no ffmpeg
  concat/crossfade/grade stage, no title cards or end cards. The 15–22s ceiling is a prompt
  instruction, not a pipeline limit — but the pipeline offers no path past it either. Longer,
  chaptered explanations (the natural evolution of this product) are architecturally
  unreachable.
- **Frame-caching tradeoff unexamined.** Renders run *without* `--disable_caching`
  (`manim_runtime.py:180`) for speed. Manim's partial-movie caching is occasionally implicated
  in stale/incorrect segment reuse across near-identical scenes; a quality-first pipeline should
  at minimum disable it for final renders (the scene-name hash mitigates but does not eliminate
  the risk).

---

## 11. Caching pins mediocrity forever

**Severity: medium, and philosophically corrosive.**

Scenes are cached by prompt hash and reused whenever the engine matches and status is
`compiled`/`rendered` (`workers.py:108–120`, `pipeline.py:44–47`). Sensible economy — but with
no quality score attached to the cached artifact, the cache cannot distinguish a masterpiece
from a barely-rendering dud. The **first** result a prompt ever produces becomes its **permanent**
result. There is no re-roll affordance in the pipeline semantics (re-running the prompt returns
the cache), no "regenerate" action, no quality bar below which a cached scene is deemed
unworthy of reuse. Once the VLM judge (§2) exists, the fix is natural: cache the *score* with
the scene; reuse only above a threshold; otherwise treat the cached scene as one candidate in
the next tournament.

---

## 12. Timing and synchronization correctness

**Severity: high (it is the prerequisite for the narration goal).**

- Every `run_time` and `self.wait()` in generated code is an unverified guess. Nothing sums
  them, nothing compares actual rendered duration (trivially available from the mp4) against
  the 15–22s contract, nothing detects a scene that is 80% dead air.
- There is no machine-readable timeline. Without one, "accurate synchronization between
  narration, visuals, and animations" is unachievable *in principle* — sync requires two
  schedules and the system has zero.
- Manim is actually the *easy* case for this: scene duration is deterministic given the code.
  A static pass can compute the full beat schedule pre-render; a probe render confirms it. The
  pipeline computes neither.

---

## 13. Orchestration & model strategy — one model wears every hat

**Severity: medium-high.**

The same configured model (`settings.llm_model`) plays physicist (solve), director+programmer
(generate), and debugger (repair). No role separation, no ensemble, and — most damningly for a
visual medium — **no vision-capable model anywhere**. A quality-first orchestration would cast
roles: a creative model for storyboarding (high temp), a code-specialized model for Manim
implementation, a vision model as the critic/judge, possibly a different model as the repair
engineer (diversity of failure modes helps repair). The current single-model design also means a
provider's particular Manim hallucination habits are systematic across every stage with no
cross-check.

Additional orchestration gaps:
- Solve and scene-gen run **sequentially** with RAG (`workers.py:122–127` labels them
  "parallel" but awaits them serially) — irrelevant for cost, but it means the scene generator
  can never *ask the solver a follow-up* (e.g., "give me the trajectory as LaTeX"). A
  conversation-shaped orchestration (agentic loop with tools) would let the scene director
  query the solver, the RAG store, and the Manim docs mid-design.
- `awaitable_pause()` in `llm.py:193` is a vestigial no-op — harmless, but emblematic of
  plumbing that grew rather than was designed.

---

## 14. Solver → scene information loss (data-model ceiling)

**Severity: medium.**

`SolverResult` (`models.py:36–66`) is too thin a wire for a cinematic pipeline:

- `variables: dict[str, float]` — no units, no valid ranges, no semantic role (is `damping` a
  rate? dimensionless? per-second?). The scene generator cannot label axes correctly or choose
  meaningful slider ranges except by guessing.
- `plot` supports exactly **one** curve (`plotting.compile_plot`) — superposition, mode
  families, before/after comparisons, phase+position pairs cannot be expressed by the solver
  even when it derived them.
- `derivation_steps: list[str]` — prose. The equations inside are not LaTeX, so the scene
  generator re-derives/invents notation (crash-prone, §8.6) and the beautiful
  `TransformMatchingTex` algebra-morphing the prompt requests (§B) has no reliable source
  material.
- No `key_equations: list[str]` (LaTeX), no `invariants`, no `initial_conditions`, no
  `interesting_parameter_values` ("resonance at k=4"), all of which the solver *knows* at
  derivation time and the director *needs* at staging time.

---

## 15. Observability — you cannot improve what you do not measure

**Severity: medium.**

- Failures live as ad-hoc strings in `SceneBundle.diagnostics`. No taxonomy (hallucinated-API /
  LaTeX / timeout / truncation / layout), no counters, no way to ask "what fraction of scenes
  needed repair last month, and for what?"
- The 102-test feature suite verifies *plumbing* (signals fire, files write, guards raise). It
  contains **zero output-quality regression tests**: no golden-frame comparisons, no SSIM/pixel
  diffs against approved renders, no "the Kepler exemplar still renders to ≥N seconds with the
  planet completing an orbit." Prompt tweaks — the highest-frequency change to this system —
  ship with no regression net whatsoever: nothing detects that a prompt edit made scenes worse.
- No archive of generated scenes + their renders + their (future) scores — the training data
  for every future improvement (exemplar mining, error learning, prompt A/B) is being discarded
  on every run (renders go to a temp dir, `manim_runtime.py:24`).

---

## 16. Creative limitations summarized

Pulling the threads together — the ceilings on creativity specifically:

1. Single completion = concept and code entangled (§3) — the model plays it safe.
2. No exemplars = the model has never *seen* what "good" means here (§8.1).
3. Temperature 0.4 = ideation permanently throttled (§8.3).
4. One sample = no exploration of the concept space at all (§9).
5. Fallbacks = failure produces the exact slop the system forbids (§7).
6. No critique loop = ambition is never rewarded, only punished (crash → repair → conservative).
7. Timeout kills ambition selectively (§6.1) — the boldest scenes die uncorrected.
8. Cache = the first draw is the final answer, forever (§11).
9. 15–22s single-scene format = no room for narrative development (§10).
10. No narration = the most powerful storytelling channel is absent (§4).

The system, as built, applies *negative* selection pressure on creativity: every mechanism that
reacts to failure pushes toward simpler, safer, smaller — and no mechanism ever pushes back
toward bolder.

---

## 17. The force-push casualty list (recoverable)

An uncomfortable, necessary note: this session's history overwrite of `master` (preserved on
branch `backup/remote-master-pr1-pr2`) discarded merged work that implemented several of the
exact mechanisms this analysis calls for:

| Discarded module | What it did | Which section it answers |
|---|---|---|
| `code_safety.py` | AST safety/validation gate on generated code | §5 |
| `error_learner.py` | Persistent render-error pattern learning | §6.4 |
| `scene_templates.py` | Domain-aware deterministic fallback scenes | §7 |
| `theme.py` | Palette theming for app **and rendered videos** | §10 |
| `tests/` (10 files) | incl. self-heal & extract-code regression tests | §15 |

Recommendation: cherry-pick these from the backup branch and reconcile — they are complementary,
not conflicting, with the current design. Re-deriving them from scratch would be waste.

---

## 18. Target architecture — ranked by quality leverage

What "world-class, unlimited budget" actually looks like for this system, in order of impact:

1. **Close the perceptual loop (VLM critic).** Frame-sample every render; judge against an
   explicit rubric derived from the cinematic prompt (acts present, hero frame, legibility,
   palette discipline, living ending, duration contract); loop *targeted revision* (critique →
   revise → re-render) until pass. This single change converts the prompt from aspiration into
   a contract. Everything else compounds on it.
2. **Split planning from codegen.** Storyboard call (temp ~0.9, structured JSON: beats,
   durations, staging, palette, hero frame, narration script) → codegen call (temp ~0.15,
   implements the storyboard beat-by-beat) → static verification that every beat exists. The
   storyboard becomes the sync contract for narration and the rubric for the critic.
3. **Candidate tournament.** N storyboards → k implementations → draft renders (480p15's true
   purpose) → VLM ranking → refine the winner → final render at 1080p60/4K. This is the direct
   cash-out of "unlimited compute."
4. **Narration track.** Script per beat (from the storyboard), TTS per beat, fit beat durations
   to narration (or stretch/trim narration to beats), mux via ffmpeg, verify total duration.
   Requires #2's timeline contract; impossible without it.
5. **Static validation battery** (pre-render): Manim-API AST lint against the installed
   library's real signatures; LaTeX pre-compilation of every Tex string; `--dry_run`
   instantiation; static duration estimate. Converts crash-repair cycles into first-try passes.
   (Recover `code_safety.py` as the seed.)
6. **Exemplar library.** 5–10 curated, verified-rendering, genuinely beautiful scenes, tagged by
   domain; inject 1–2 matching exemplars per request. Highest prompt-side leverage available.
7. **Repair upgrades:** repair on `render-timeout` too (feed elapsed/limit); send full stderr;
   lift the round cap; add an *aesthetic* revision mode driven by critic feedback (distinct from
   crash repair). Recover `error_learner.py` for cross-session learning.
8. **Fallback ladder with domain rungs.** Recover `scene_templates.py`; make the bottom rung
   domain-correct rather than damped-sine-for-everything.
9. **Render identity & assembly.** Inject the app's design tokens into every scene (background,
   font, palette — recover `theme.py`); add an ffmpeg finishing stage (multi-scene concat,
   crossfades, end card, loudness-normalized audio mux); surface 4K; default the *final* render
   quality to High, keep Draft for tournament drafts.
10. **Quality observability.** Failure taxonomy; archive every (prompt, storyboard, code, render,
    score) tuple; golden-render regression tests so prompt changes are measured, not vibed.
11. **Richer solver contract.** `key_equations` (LaTeX), variable units/ranges/roles,
    multi-curve plot payloads, interesting parameter values — feed the director real material.

---

### Closing statement

The current system is a competent *reliability* pipeline wearing a beautiful creative brief as a
hat. Its every instinct — compile gates, crash repair, conservative temperature, caching,
fallbacks — was built to guarantee that *something* renders. Nothing in it was built to
guarantee that what renders is *worth watching*, and several of its mechanisms actively select
against ambition. The path to world-class is not more rules in the prompt; it is closing the
loop the system has never had: **look at the output, judge it against the intent, and refuse to
ship until they match.**
