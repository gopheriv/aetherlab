# AetherLab → Topic Explainer for Students

Deep analysis of what must be added to turn AetherLab from a *single-problem
visualizer* into a *topic explainer* — a narrated, multi-chapter lesson a
student actually learns from — plus a detailed, phased, paste-ready prompt to
build it.

---

# PART 1 — The shift

**Today:** prompt → one problem → one ~20 s, 3-act narrated Manim scene + a live
canvas. It *shows* a result.

**Target:** a *topic* ("simple harmonic motion", "Gauss's law", "Fourier
series", "why is the sky blue") → a **3–8 minute, narrated, multi-chapter video
lesson** that *teaches* it: hook → intuition → the math, built up → worked
example → "play with it" → recap → a couple of check-yourself questions. The
3Blue1Brown / Khan-for-your-exact-question format, generated on demand, grounded
in real textbooks, and adaptable to the student's level.

The core mental model change: **narration is the spine.** In an explainer the
teacher's script drives everything; the visuals are timed *to the words*, not
the other way round. AetherLab currently renders visuals then (optionally) fits
narration — that must invert.

---

# PART 2 — Deep gap analysis: what must be added

Ranked by how essential each is to "a student can learn a topic from this."

### 1. A Lesson Planner (new top orchestration stage) — ESSENTIAL
Above today's single storyboard, add a pedagogical planner that turns a *topic*
into a **lesson plan** (structured JSON): title, audience level, prerequisites,
learning objectives, a common **misconception** to pre-empt, and an ordered list
of **chapters** — each with a teaching goal, the concept/derivation beat, and
whether it needs a Manim scene, a static equation card, or the interactive
canvas. This is the analogue of `SceneGenerator.storyboard()` but one level up
(topic → chapters), and it's what makes the output a *course* not a *clip*.

### 2. Narration-driven scene timing (invert the sync) — ESSENTIAL
Reuse/extend `services/voiceover.py`. Adopt the **manim-voiceover pattern**:
each chapter scene wraps its animations in `with self.voiceover(text=...) as
tracker: self.play(..., run_time=tracker.duration)` so the animation length is
*derived from the spoken line*. Sync becomes exact by construction — no
post-hoc fitting, no drift. edge-tts (already wired via `tts_voice`/`tts_rate`)
stays the engine; offline/no-TTS degrades to on-screen captions + silent timing.

### 3. Multi-scene pipeline + assembly — ESSENTIAL
Today's pipeline renders one `SceneBundle`. Add a `LessonBundle` = ordered
chapters, each produced by the *existing* per-scene pipeline
(`generate_scene_async` → `render_scene_with_repair` → critique), then an
**ffmpeg assembly** stage: intro title card → chapters (with lower-third chapter
titles + a progress dot) → recap → end card, joined with short crossfades, one
continuous audio track (narration + optional soft bed). Chapters render in
parallel; assembly concatenates. (Cross-platform subprocess is a prerequisite —
see RENDER_RELIABILITY_AND_CLOUD.md Bug 2.)

### 4. Pedagogy layer (make it *teach*, not just *show*) — HIGH
The planner and the per-chapter prompts must carry teaching craft:
  • **Hook** first (a question/surprise), not a definition.
  • **Concrete before abstract** (a real pendulum before `θ̈ + (g/ℓ)sinθ = 0`).
  • **Build the equation term-by-term**, naming each symbol as it appears.
  • **Name and correct the common misconception** explicitly.
  • **Analogies** and everyday referents.
  • **Worked example** with real numbers.
  • Audience level (high-school / AP / undergrad) sets depth, vocabulary, and
    how much calculus is assumed.

### 5. Factual grounding (don't teach wrong physics) — HIGH
Wire the existing RAG (OpenStax + web references) into the *planner and script*,
not just a sidebar: the narration should reflect the textbook treatment, use
correct constants/units, and the lesson should show **citations** ("OpenStax
University Physics, §15.2"). Add a lightweight **fact-check pass**: the script is
checked against retrieved passages; unsupported claims are flagged/revised.
Critical for student trust.

### 6. Assessment & interactivity — HIGH (this is what makes it a learning tool)
  • 2–4 **check-yourself questions** per lesson (MCQ + one open), with answers
    and one-line explanations — generated from the objectives.
  • A **"play with it"** chapter that hands off to the existing interactive
    `LiveCanvas` with the lesson's parameters, framed with a prompt
    ("what happens to the period as you increase length?").
  • **Pause points** / chapter navigation so a student learns at their pace.

### 7. Lesson UI (a classroom, not a clip player) — HIGH
A Lesson view: left **outline/chapter list** (click to jump), the narrated
**player with chapter markers** on the seek bar (the ActSeekSlider already does
act markers — extend to chapters), a synced **transcript** that highlights the
current line, the **check-questions** panel, and a **references** tab. Reuse the
screening-room player, StoryboardStrip → ChapterStrip, CritiqueBadge.

### 8. Lesson export / share — MEDIUM
Export the whole lesson as: the assembled **MP4** + a **PDF study-guide**
(objectives, the typeset key equations via `mathtext`, the worked example, the
questions with answers, citations) + a plain **transcript/subtitles (.srt)**.
Builds directly on `services/pdf.py` and the new narration timings (→ .srt).

### 9. Adaptivity — MEDIUM
"Explain simpler" / "go deeper" / "I'm stuck on chapter 3" → regenerate the
affected chapters at a different level, not the whole lesson. Level is a
first-class input to the planner.

### 10. Cost/time realism — MEDIUM (design, not a feature)
A lesson is N scenes × (generate + render + critique) — minutes, and many LLM
calls. Needs: aggressive per-chapter caching (a chapter is cache-keyed by its
plan, so editing chapter 5 doesn't re-render 1–4), a live progress model
("Chapter 3/6: rendering…"), draft-first rendering, and graceful partial
delivery (ship chapters as they finish). The **cloud batch renderer**
(RENDER_RELIABILITY_AND_CLOUD.md Part B.3) is the natural fit for full-quality
lesson renders.

---

# PART 3 — The detailed prompt (paste-ready)

```text
You are a senior Python/PyQt6 engineer, a Manim Community expert, and an
instructional designer. Turn AetherLab from a single-problem visualizer into a
TOPIC EXPLAINER: given a topic, it produces a narrated, multi-chapter video
lesson (3–8 min) a student learns from, grounded in real textbooks, with
check-yourself questions and an interactive "play with it" section. Reuse the
existing pipeline; do not rebuild it. Quality and pedagogy first; assume
unlimited time/compute.

READ FIRST (the pipeline you are extending, not replacing)
  services/scene_generator.py  — storyboard() (hot 0.9 directing pass → JSON) +
    generate()/repair() (cold codegen). This is your MODEL for the new planner.
  services/manim_runtime.py     — generate_scene_async + render_scene_with_repair
    (compile/safety/lint gates, self-heal). Each chapter reuses this unchanged.
  services/voiceover.py         — edge-tts narration (settings.narration_enabled/
    tts_voice/tts_rate). You will make narration DRIVE scene timing.
  services/scene_critic.py      — frame-sample + VLM critique per scene.
  services/rag.py, web_references.py — textbook + web grounding.
  services/pdf.py, mathtext.py  — LaTeX export + typeset equations (study guide).
  ui/widgets.py                 — SimulationPanel, ActSeekSlider, StoryboardStrip,
    CritiqueBadge, LiveCanvas (extend into the Lesson view).
  core/models.py, core/settings.py, services/pipeline.py, ui/workers.py.

════════════════════════════════════════════════════════════════════════
PHASE 1 — LESSON PLAN (topic → structured curriculum)
════════════════════════════════════════════════════════════════════════
New services/lesson_planner.py. A hot LLM pass (temp ~0.8) returns STRICT JSON:
  {
   "title", "audience": "high_school|ap|undergrad",
   "prerequisites": [...], "objectives": [...],
   "misconception": "the one wrong idea to pre-empt",
   "chapters": [
     {"id", "title", "goal": "what the student should get",
      "kind": "scene|equation_card|interactive|recap",
      "beats": [...], "narration": "the spoken script for this chapter",
      "key_equations": ["LaTeX"], "citation_query": "for RAG"}
   ],
   "questions": [{"q","choices"?,"answer","why"}]  // 2-4, mixed MCQ/open
  }
Rules: hook first, concrete before abstract, name the misconception, audience
sets depth. Ground objectives/citations in RAG (call rag.search on the topic +
each citation_query). Add core/models.py: LessonPlan + LessonBundle dataclasses
(JSON round-trip, defaults so old caches load). Fail-soft: no key → a
deterministic template lesson (reuse scene_templates.detect_domain to pick a
canned 3-chapter outline per domain).

════════════════════════════════════════════════════════════════════════
PHASE 2 — NARRATION-DRIVEN SCENES (invert the sync)
════════════════════════════════════════════════════════════════════════
Adopt the manim-voiceover timing pattern so animation length derives from the
narration, making sync exact:
  • Add manim-voiceover (or replicate its VoiceoverScene + tracker.duration) so
    generated chapter scenes do:
      with self.voiceover(text=CHAPTER_LINE) as t:
          self.play(<the beat's animation>, run_time=t.duration)
  • Teach this pattern in the codegen system prompt: the scene is a sequence of
    voiceover blocks, one per narration sentence, each with its own animation.
  • Keep edge-tts as the engine (offline via cached audio). No key / no
    edge-tts / offline → fall back to on-screen captions timed by estimated
    reading speed and a silent track; NEVER block the render.
  • Emit per-line timings so Phase 5 can build .srt subtitles + transcript sync.
Verify: a chapter's audio and animation start/stop together within 100 ms.

════════════════════════════════════════════════════════════════════════
PHASE 3 — MULTI-SCENE PIPELINE + FFMPEG ASSEMBLY
════════════════════════════════════════════════════════════════════════
New services/lesson_pipeline.py orchestrates: for each chapter, run the EXISTING
per-scene pipeline (generate_scene_async → render_scene_with_repair → critique),
cache-keyed by the chapter plan (edit ch.5 ⇒ ch.1–4 reuse cache). Render
chapters concurrently (bounded). Then services/assembly.py (ffmpeg) builds the
final lesson: intro card → each chapter (lower-third title + progress dot) →
recap → end card, crossfade transitions, single continuous audio track. Cross-
platform subprocess only (gate creationflags behind win32; see
RENDER_RELIABILITY_AND_CLOUD.md Bug 2). Stream progress
("Chapter 3/6 rendering…") through ui/workers.py; deliver chapters as they
finish so the student can start watching chapter 1 while 6 renders.

════════════════════════════════════════════════════════════════════════
PHASE 4 — PEDAGOGY + GROUNDING + ASSESSMENT
════════════════════════════════════════════════════════════════════════
  • Bake the teaching rules (hook, concrete→abstract, term-by-term equations,
    name the misconception, analogies, worked example) into the planner and the
    per-chapter codegen prompts.
  • Fact-check pass: check each chapter's narration against RAG-retrieved
    passages; flag unsupported claims and revise (bounded). Surface citations
    on screen and in the study guide.
  • Assessment: render the questions as an interactive panel (MCQ with
    immediate feedback + explanation; open questions reveal a model answer).
  • Interactive chapter: hand off to LiveCanvas seeded with the lesson's
    parameters + a guiding prompt.

════════════════════════════════════════════════════════════════════════
PHASE 5 — LESSON UI + EXPORT
════════════════════════════════════════════════════════════════════════
  • Lesson view (extend SimulationPanel): outline/chapter list (click to jump),
    narrated player with CHAPTER markers on the seek bar (extend ActSeekSlider),
    a synced transcript that highlights the current line, a Questions tab, a
    References tab. A new rail destination "Learn".
  • Export a lesson as: assembled MP4 + PDF study guide (objectives, typeset
    key_equations via mathtext, worked example, questions+answers, citations —
    build on pdf.py) + .srt subtitles/transcript (from Phase 2 timings).

CONSTRAINTS
  • Reuse the existing per-scene pipeline for every chapter — no parallel
    renderer. Keep the AST safety gate + static lint in front of every scene.
  • Everything degrades offline/keyless to a coherent template lesson.
  • Per-chapter caching so iterating a lesson is cheap.
  • New behavior ships with tests in test_features.py (offscreen-safe) and rows
    in build_feature_tracker.py; `python test_features.py` stays green.
  • Manim + subprocess isolation stay; don't import manim into the UI process.

DELIVERABLE ORDER: Phase 1 (plan) → Phase 2 (narration-driven sync) → Phase 3
(multi-scene + assembly) → Phase 4 (pedagogy/grounding/assessment) → Phase 5
(UI + export). Each phase lands working, tested, and demoable before the next.
```
