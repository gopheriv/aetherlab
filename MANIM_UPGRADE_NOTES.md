# Manim System — Upgrade Research & Notes

_Research date: 2026-09-23. Installed in the AetherLab Python 3.14 environment and pinned in local/cloud setup: **Manim Community 0.21.0**._
Default invocation: `python -m manim render -q{l|m|h} --fps N --renderer cairo --disable_caching --media_dir …`
on the **Cairo** renderer, one isolated subprocess per render, with a self-heal +
vision-critic + multi-candidate tournament loop on top._

This is a punch list of everything that could upgrade our Manim system, ranked by
leverage. Each item notes **what**, **why it helps us specifically**, and **effort/risk**.

> **Implemented 2026-09-23**: Manim 0.21.0 is pinned in local extras, CI, and cloud
> workers; focused compatibility checks passed. Local renderer selection is gated by
> `AETHERLAB_MANIM_RENDERER` (Cairo default). Repair-chain caching and critic-guided
> partial revisions are opt-in local experiments via `AETHERLAB_MANIM_REPAIR_CACHE=1`
> and `AETHERLAB_MANIM_PARTIAL_REVISIONS=1`; ordinary renders still isolate and disable
> Manim partial caching. The local OpenGL comparison found a compatibility failure and
> missing geometry, so Cairo remains the default and Cloud renderer. Measure cache
> behavior against reviewed golden scenes before enabling either cache experiment.

---

## 0. TL;DR — highest-leverage moves

1. **Bump 0.20.1 → 0.21.0** and absorb the two breaking changes that touch code we
   already maintain (MathTex splitting rewrite; new/`fixed` color constants). Low effort, de-risks our repair passes.
2. **Adopt `--seed` for reproducible renders** (new in 0.20.0) — makes the tournament
   fair (candidates differ by prompt, not RNG) and makes bug repro deterministic.
3. **Evaluate the OpenGL renderer for the render worker** — GPU rasterization is the
   single biggest wall-clock win available, but it changes the compatibility surface.
   Gate it behind a setting, keep Cairo as the default.
4. **Mine `manim-physics` and `manim-voiceover` for ideas** — not necessarily as
   dependencies, but their mobjects/patterns are directly relevant to our scene library and narration sync.

---

## 1. Version upgrade: 0.20.1 → 0.21.0

**What changed (0.20.0 → 0.21.0)** that intersects our code:

- **MathTex rewrite** — splitting/substring behavior for `MathTex`/`Tex` is more robust.
  We generate LaTeX-heavy scenes and run `check_latex_strings` /
  `repair_text_mode_math` in `scene_validation.py`. Re-validate those repairs against
  0.21.0; some of our workarounds for double-brace `{{ }}` splitting may now be
  unnecessary (0.20.1 fixed double-brace splitting; 0.21 continues that line).
- **Color constants**: `YELLOW_C` fixed; **new** `PURE_CYAN`, `PURE_MAGENTA`, `PURE_YELLOW`.
  Our `repair_unknown_color_constants()` builds its allowed set from the installed
  Manim namespace, so this is auto-absorbed — but we should add the three PURE_* names
  to any hardcoded palette tests and to `scene_templates` palettes if we want them.
- **`always` animation builder** (`Mobject.always`) — declarative "keep this updater on"
  helper; cleaner than manual `add_updater` in generated code. Worth teaching the codegen prompt.
- **`--seed` config option** — see §2.
- **ImageMobject 3D rotation/flip fixes**; removal of `lanczos`/`box`/`hamming` resampling.
  Only matters if a scene passes those resampling names — our safety gate should flag them as unknown kwargs.

**Status**: `manim==0.21.0` is pinned in the optional render extra, CI, and the Cloud
worker. Focused F105/F106/F132 checks passed; a complete golden-scene visual comparison
remains a separate benchmark.

**Risk**: low–medium. The breaking changes are narrow and we already build our
name/color allowlists dynamically from the installed package.

---

## 2. Reproducible renders with `--seed`

**What**: 0.20.0 added a `seed` config + `--seed` CLI flag that fixes Python/NumPy RNG
for a render.

**Why it helps us**:
- **Fair tournaments**: today two candidates can differ purely because of RNG in
  particle/field scenes. Seeding removes that noise so the vision critic scores
  *direction*, not *dice*. Give each candidate a deterministic seed derived from its id.
- **Deterministic bug repro**: a failed render can be replayed exactly, which makes the
  `error_learner` signal cleaner and support tickets reproducible.

**Status**: every AetherLab render command includes a deterministic code-derived
`--seed`, with candidate variants isolated by their distinct scene code.
**Effort**: tiny. **Risk**: negligible (deterministic-only change).

---

## 3. Renderer: Cairo vs OpenGL

**Today**: Cairo (Manim default). Correct, portable, CPU-bound.

**OpenGL renderer** (`--renderer=opengl`): rasterizes on the GPU, materially faster for
scenes with many mobjects, and enables interactivity. FAQ + community guides confirm
big wall-clock wins.

**Trade-offs for a render *farm* (our use case, not interactive)**:
- Needs a working GL context. On headless Linux Actions workers (our cloud backend) that
  means EGL/`xvfb` + Mesa — extra provisioning and a new class of "black frame" failures.
- Do **not** mix Cairo and OpenGL mobjects (documented footgun). Our generated code and
  templates assume Cairo idioms; some would need review.
- To write a video file (not just a window) you pass `--write_to_movie`; the OpenGL path
  historically has more sharp edges for file output than for live preview.

**Status**: local renderer selection is gated by `AETHERLAB_MANIM_RENDERER`; the
default is `cairo`, and `opengl` is available for an explicit experiment. Cloud
workers stay on Cairo. The representative local benchmark is complete; its
compatibility and visual failures do not support enabling OpenGL for regular
renders. Projection shader flags (`--use_projection_*_shaders`) may help 3D scenes.

**Effort**: high. **Risk**: high (compatibility + headless GL). High ceiling though.

---

## 4. Re-enable caching where it is safe

**Today**: we pass `--disable_caching` and isolate every render. That is the right call
for *one-shot correctness* and for the tournament (no cross-candidate bleed), but it
throws away Manim's per-`play()` hash cache.

**Opportunity**: for the **self-heal retry** path, the repaired scene often differs from
the crashed one by only a few `play()` calls. With caching *on* and a stable
`--media_dir` per repair lineage, unchanged segments are reused, so retries get cheaper.

**Status**: `AETHERLAB_MANIM_REPAIR_CACHE=1` enables a unique cache directory for a
single local repair lineage, with the same deterministic seed. It never shares partial
files between jobs. `AETHERLAB_MANIM_PARTIAL_REVISIONS=1` maps critic timestamps to
simple, static top-level `self.play`/`self.wait` calls, renders that range, then runs a
full pass to assemble the complete clip from the lineage cache. Dynamic or ambiguous
timing skips the partial pass. Both flags are off by default; compare cache-hit logs and
visual output before recommending them broadly.
**Effort**: medium. **Risk**: medium — cache invalidation bugs are subtle; keep it opt-in.

---

## 5. Quality / cost knobs we are not using

- **`-r W,H` explicit resolution** instead of only `-ql/-qm/-qh`. Lets us decouple
  resolution from fps and hit a target pixel budget on constrained tiers.
- **`--fps` we already set** (good — prevents silent 15fps). Consider dropping to 24fps
  for draft/tournament passes and only rendering the *winner* at 30/60.
- **`-n <start>,<end>` partial render** — used for opt-in local revisions when critic
  timestamps map unambiguously to top-level play calls; a later full pass assembles the
  complete output from Manim's lineage-local cache.
- **`--format=webm`/`gif` for previews** — lighter artifacts for the tournament gallery;
  keep mp4 only for the final. (We already validate mp4 via `validate_mp4`.)
- **Section API (`self.next_section`)** — render/skip logical sections; useful if we ever
  want per-chapter re-render in the Learn pipeline without re-running the whole scene.

**Effort**: low each. **Risk**: low. Pick the partial-render-on-revise one first — it
directly cuts our most expensive loop.

---

## 6. Plugins worth mining (as deps *or* as design references)

- **`manim-physics`** — 2D physics simulation mobjects (rigid mechanics, EM, waves) built
  on a real 2D physics engine. Two ways to use it:
  1. as an optional dependency for a "simulated" scene family (pendulums, collisions,
     field lines that obey real dynamics), or
  2. as a **reference** for how to structure our own `scene_components` more physically.
  Caveat: adds a heavy dep and its own version-compat surface; our components are
  deterministic and LaTeX-free by design, which is a feature. Prefer *mining ideas*.
- **`manim-voiceover`** — narration-in-Python with **per-word timing via OpenAI Whisper**,
  so animations trigger on specific spoken words. We already build narration
  (`voiceover.py` + edge-tts) and a storyboard bookmark system. Their **bookmark /
  `tracker.duration` API** and Whisper-based alignment are directly relevant to tightening
  our narration↔visual sync (F139/F140). Strong candidate to study; possibly adopt the
  timing approach without the whole plugin.
- **`manim-slides`** — live/step presentations from rendered scenes. Lower priority for
  a video product, but interesting if the Learn page ever wants a "present mode" that
  advances chapter-by-chapter.

**Effort**: variable. **Risk**: dependency weight. Default stance: **study, don't bundle**,
except possibly the voiceover timing model.

---

## 7. Codegen-prompt upgrades (no new deps, pure prompt/validation wins)

These make the *LLM* produce better Manim, which is cheaper than fixing renders after:

- Teach the prompt the **0.21 idioms**: `Mobject.always`, `next_section`, the fixed color
  constants, and the more robust `MathTex` splitting (so it stops emitting the old
  `{{ }}` workarounds).
- **Ban known-slow patterns**: per-frame Python loops in updaters over large mobjects,
  `Transform` on huge VGroups, redundant `Create` of off-screen objects. Add these to
  `scene_hygiene_warnings` so they are caught pre-render.
- **Encourage `VGroup` batching** and `AnimationGroup`/`LaggedStart` over N sequential
  `play()` calls — fewer partial-movie files, faster assembly.
- **Prefer `Axes`/`NumberPlane` `.plot()`** over hand-rolled `ParametricFunction` where
  possible — fewer API-name hallucinations, which is our top render-failure class.

**Effort**: low. **Risk**: low. This is probably the best effort:reward ratio on the list.

---

## 8. Robustness / observability

- **Profile the heavy templates** with Scalene/cProfile (Manim's own perf guide recommends
  this) to find which scene families dominate render time, then target §5/§7 at them.
- **Structured render telemetry**: implemented for per-stage duration, peak RSS,
  failure class, renderer, repair-cache use, cache hits, retry count, and final quality.
- **Pin the full transitive stack** (manimpango, skia-pathops, moderngl, pycairo) — a
  silent transitive bump is a common source of "it renders differently now". Our cloud
  spec already collects manimpango/skia/moderngl (F137); mirror that pin locally.

---

## 9. Explicitly NOT recommended (and why)

- **Switching to ManimGL (3b1b's fork)** — we already detect it as a fallback, but it is
  less API-stable and less documented than Community; our validation/allowlists target
  Community. Keep Community as the target.
- **Bundling `manim-physics` by default** — heavy, and it fights our LaTeX-free,
  deterministic template guarantee. Optional-extra at most.
- **OpenGL on the cloud worker first** — do local benchmarking first; headless GL on
  Actions is where this turns into a time sink.

---

## Suggested sequencing

1. Landed: seed, codegen hygiene, Manim 0.21.0, telemetry, and opt-in local cache/partial-revision experiments.
2. Remaining: review a generated golden-scene set and compare cache hit rates and visual output.
3. Benchmark outcome: keep OpenGL opt-in; Cairo remains the Cloud and default renderer.

## Sources

- [Manim Community releases](https://github.com/ManimCommunity/manim/releases) · [changelog](https://docs.manim.community/en/stable/changelog.html) · [PyPI](https://pypi.org/project/manim/)
- [Improving performance guide](https://docs.manim.community/en/stable/contributing/performance.html) · [Configuration](https://docs.manim.community/en/stable/guides/configuration.html) · [Deep dive internals](https://docs.manim.community/en/stable/guides/deep_dive.html)
- [FAQ: OpenGL rendering](https://docs.manim.community/en/stable/faq/opengl.html)
- [manim-physics](https://www.manim.community/plugin/manim-physics/) · [manim-voiceover](https://www.manim.community/plugin/manim-voiceover/) ([add voiceovers guide](https://docs.manim.community/en/stable/guides/add_voiceovers.html)) · [manim-slides](https://www.manim.community/plugin/manim-slides/) · [plugin library](https://plugins.manim.community/)


## Upgrade status (2026-09-25)

AetherLab source installs, CI, and the Cloud render worker pin Manim 0.21.0. The focused F105/F106/F132 compatibility checks passed. On the current Windows machine, `tools/renderer_ab_benchmark.py` compared the deterministic `field_lines`, `kinetic_theory`, and `fourier_epicycles` scenes at 854x480 and 30 fps. OpenGL failed `field_lines` because a Cairo `VMobject` was added to an OpenGL `VGroup`. `kinetic_theory` rendered in 17.3s (OpenGL) versus 17.6s (Cairo), but its OpenGL contact sheet omitted the box and graph axes. `fourier_epicycles` took 56.5s (OpenGL) versus 49.7s (Cairo), and its OpenGL contact sheet omitted most moving geometry. The comparison images are under `.analysis/opengl-ab-20260925-011248/`. The benchmark therefore found no safe speed win; OpenGL stays opt-in, and Cloud/default rendering stays on Cairo. The cache/partial-revision paths remain opt-in and record cache hits plus render wall time. Typst remains optional. No project call site uses the removed `Camera.convert_pixel_array(convert_from_floats=...)` argument.

## Timed-scene runtime validation - 2026-09-25

Static beat-marker validation now also sums literal top-level `self.play` and
`self.wait` durations within each marked interval and compares cumulative start/end
times against the storyboard with a 0.35-second tolerance. It counts any action
before the first marker. Dynamic durations and uncertain control flow deliberately
skip this estimate rather than produce false precision. When a measurable scene
drifts, the bounded repair pass is instructed to adjust only literal animation or
hold times while preserving visuals and the full schedule.

The Planck radiation smoke exposed a 1.1-second cumulative shortfall: comment windows
matched the storyboard, but action durations totaled 28.9 seconds for a 30-second
schedule. Four holds were extended by 1.1 seconds in total. The repaired code passed
the static timing gate and rendered through the saved Cloud workflow as a 30.0-second
900-frame MP4 at 854x480 and 30 fps; Cloud wall time was 199.425 seconds. Evidence is
in `.analysis/ai-radiation-smoke/result.json` and
`.analysis/ai-radiation-smoke/timed-cloud-contact-sheet.png`.

An optional narration probe then used seven beat cues and subtitles against this
exact MP4. Video and audio both measure 30.0 seconds, cue overrun is zero, the rate
stayed at +8%, and the closing cue ends at 28.236 seconds inside the final 26-30
second window. Files are in `.analysis/timed-narration-cloud-20260925/`. Normal-speed
human listening review is still pending; the saved setting `narration_enabled` remains
false.

## Cross-backend golden coverage - 2026-09-25

The original 4-second plot/text parity scene is supplemented by
`tools/manim_parity_smoke.py`, an integrated 9.2-second golden render. It uses the
curated electric field-lines component, generated `Text`, and a `Tex` expression
that must be promoted to `MathTex` by the existing pre-render repair. Local and
Cloud renders both produced 276 frames at 30 fps and 854x480. Five sampled frames
had mean absolute pixel error 0.3945; at least 98.854% of channels stayed within 16
levels. Both the local Python environment and the Cloud Actions run log report
Manim 0.21.0. The comparison gate requires duration/fps/dimensions/version parity,
mean pixel error at most 2.0, and at least 97.5% of channels within 16 levels.

Local wall time was 23.667 seconds. Cloud call wall time was 153.168 seconds; the
runner log reports 3.74 seconds for Manim rendering and 304.406 MB peak RSS. The
remainder is upload/dispatch/poll/download overhead, so the wall-time comparison
does not claim Cloud is faster for this small scene. Inspection of the real Actions
log found that GitHub prefixes each line, preventing the previous anchored regex
from capturing runner metrics. `_parse_runner_metrics` now accepts prefixed markers;
the regression test verifies Cloud ledger capture of Manim version, render time,
and peak memory. Evidence is under `.analysis/manim-parity-20260925/`.

## Manim package-version benchmark - 2026-10-02

`tools/manim_version_benchmark.py` compares the installed Manim 0.21.0 with an
extracted 0.20.1 wheel without installing or changing either package. It uses
the same Python 3.14.4 interpreter and installed dependency set for both
versions, renders the fixed field-lines golden scene with Cairo at 854x480 and
30 fps, disables Manim caching, alternates run order, and retains every MP4 and
log. Run it with `python tools/manim_version_benchmark.py --repeats 3`.

Across eight matched pairs, median end-to-end render wall time was 17.804s for
0.20.1 and 16.681s for 0.21.0 (6.3% lower). The newer version was faster in
each pair. Timings were noisy: 0.20.1 ranged from 16.965s to 47.387s, and
0.21.0 ranged from 15.522s to 25.905s. One 47.387s old-version run paired with
a 16.811s new-version run, so the medians should be read as evidence for this
scene and machine rather than a general performance guarantee. All videos
measured 9.2s, 276 frames, 854x480, and 30 fps; sampled frames were pixel
identical. Evidence, including both reports, all renders, logs, and contact
sheets, is under `.analysis/manim-version-ab-20261002/benchmark-20261002-160006/`
and `.analysis/manim-version-ab-20261002/benchmark-20261002-160401/`.

A retained Cloud traceback from the MiniMax A/B probe exposed another Manim
family-interpolation failure: a `DecimalNumber` updater changed the digit count
while the readout faded in during the same play as its `ValueTracker`. The new
`check_dynamic_numeric_fade_conflicts` pre-render gate rejects that same-play
pattern, and the generation/repair prompts require a separate readout entrance
before the tracker animation. It flags both affected counters in the captured
scene. A regression covers the unsafe and split-play forms; the full pytest and
223-feature harness pass with the gate enabled.

## ЕНТ MVP render defaults - 2026-10-07

The desktop quality selector now starts at Standard (Manim `-qm`: 1280x720 at
30 fps) instead of Draft. Draft remains available for fast previews, and High
remains available for 1080p output. Automatic local render tiers keep a stable
30 fps cadence; users can still explicitly choose the cinematic tier or set
`AETHERLAB_MANIM_FPS` when a lesson needs 60 fps. The Cairo backend, isolated
per-render media directory, and disabled Manim cache remain unchanged so render
quality changes do not reintroduce the prior cache/synchronization collision.
