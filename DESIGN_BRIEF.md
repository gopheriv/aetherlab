# AetherLab — GUI Redesign Brief (for Claude / a design agent)

Paste this whole file to the design tool. It is self-contained: it describes the
current prototype, the problems to solve, the visual language to keep, and exactly
what to produce. Deliver **high-fidelity mockups** of each screen/state listed in
§7, plus a component sheet (§6). Target platform is a **PyQt6 desktop app**, so
every element must be buildable with standard Qt widgets (no web-only effects).

---

## 1. Product in one line
AetherLab turns a natural-language physics/math prompt into: an analytical
derivation → textbook references (RAG) → a generated Manim animation (MP4) → a
live interactive parametric canvas driven by parameter sliders.

## 2. Users & primary job
Students, educators, and researchers. Core loop: **type a prompt → watch a
4-stage pipeline (Solve → RAG → Scene → Render) → read the derivation, inspect
references, watch the video, and tweak parameters live.**

## 3. Current prototype (what exists today)
- **Window:** 1500×950, dark theme, title "AetherLab".
- **Layout:** left icon sidebar `Solve / Refs / Scene / Params / History` │ a
  stacked content column (Analysis, References, History) │ a large right panel
  holding the Simulation view + a 4-stage horizontal **pipeline stepper** + a
  collapsible **parameter dock**. A **command bar** (examples dropdown + prompt
  input + quality selector + Run) spans the bottom.
- **Simulation view** has pill tabs `Canvas / Video / Code`, a loading overlay
  (animated concentric rings), a live QPainter canvas, a video player
  (play/pause/stop, seek, speed), and a code viewer.
- **Known UX problems to fix in the redesign:**
  1. Navigation model is inconsistent — some sidebar items swap the left column,
     others act on the right panel. Users lose track of "where am I."
  2. The derivation is shown as **plain text**; a physics tool must show typeset
     math (LaTeX/MathJax-style).
  3. No visible **Settings** (API key/model), no **library manager** for RAG,
     no **cancel** for a running pipeline, weak empty/first-run states.
  4. Status/feedback is scattered across a status bar, an inline error banner,
     and the stepper.
  5. Parameter sliders and the two visualizations (2D canvas vs Manim video)
     feel disconnected.

## 4. Design goals (priority order)
1. **One clear spatial model.** A person should always know what each nav item
   changes. Prefer: persistent left rail (destinations) + a single primary
   workspace whose content is driven by the pipeline, not by hidden tabs.
2. **Make the pipeline the hero.** Solve → RAG → Scene → Render should read as a
   living timeline with per-stage status, timing, and the ability to cancel.
3. **Physics-grade typography.** First-class typeset equations in the derivation.
4. **Progressive disclosure.** Simple by default (prompt + result); advanced
   controls (engine, quality, paths, model) tucked into Settings.
5. **Keep it fast & native.** All layouts must map to Qt; no reliance on effects
   Qt can't render.

## 5. Visual language (KEEP — evolve, don't replace)
Retain the current "engineering blueprint / dark lab" identity. Use these exact
tokens as the baseline palette (introduce tints/shades as needed, keep contrast
AA+):

| Role | Hex |
|---|---|
| Base bg (deepest) | `#0A0A0F` |
| Panel bg | `#0D0D14` / `#13131A` |
| Canvas bg gradient | `#0F1520` → `#0A0A0F` |
| Hairline / border | `#1E293B`, `#334155` |
| Primary accent (cyan) | `#06B6D4` |
| Secondary (emerald) | `#10B981` |
| Tertiary (violet) | `#8B5CF6` |
| Warning (amber) | `#F59E0B` |
| Error (rose) | `#F43F5E` |
| Text high / mid / low | `#F8FAFC` / `#94A3B8` / `#64748B` |

Type: UI in **Segoe UI** (or Inter), code/numbers in **Cascadia Code** (mono).
Corner radius 8px, generous hairline separators, subtle glow only on the cyan
accent and the live tracer. Motion: purposeful (stage transitions, tracer,
loading), never decorative-forever.

## 6. Component sheet to deliver (states shown)
Design each in default + hover + active/selected + disabled, dark theme:
- Left nav rail item (icon + label), with a "current" indicator.
- **Pipeline timeline** node: pending / active (animated) / complete / error,
  with elapsed time and an inline cancel affordance on the active node.
- Command bar: prompt field (empty/placeholder, focused, filled, busy),
  examples menu, quality selector, primary **Run** and **Cancel** buttons.
- Parameter control row: label + slider + live monospace value + reset;
  show how a large value (e.g. gravity 9.81) and a small one (damping 0.15)
  both look on the same rail.
- Reference (RAG) card: source, page, score chip, excerpt, "open" action;
  plus the empty state ("add textbooks…").
- Video controls bar: transport + seek + speed + "save/open output".
- Derivation block: typeset equation + numbered step list + "copy/export".
- Toast/banner for errors (inline, dismissible, "Details").
- Settings form controls (text field, dropdown, path picker, secret field).

## 7. Screens / states to mock (the deliverables)
1. **Empty / first-run** — no API key, no library. Clear call-to-action to open
   Settings and to add textbooks; sample prompts front and center.
2. **Prompt entered, pipeline running** — the timeline mid-flight (Scene active),
   a cancel control, live status, loading state in the workspace.
3. **Result — Derivation focus** — typeset summary + steps, keyword chips,
   references list beside or below.
4. **Result — Visualization focus** — the Manim **video** and the **live canvas**
   presented as two views of one result; parameter rail visible; show the
   phase-portrait overlay toggle on.
5. **Result — Code focus** — generated Manim code with export.
6. **References / Library manager** — list of indexed sources + "add folder /
   ingest / re-index" and index status.
7. **Settings dialog** — provider (API key, base URL, model), render engine &
   quality, data/library paths, with sensible defaults.
8. **History** — past runs (prompt, time, status, refs count), click to re-run,
   clear.

## 8. Hard constraints
- Buildable in **PyQt6 / QSS**: use widgets (QStackedWidget, QSplitter, QSlider,
  QListWidget, QComboBox, QMediaPlayer view, custom QPainter canvas). No CSS
  grid/flex tricks that Qt can't do; no external web fonts assumed present.
- Must work at **1280×720 up to 4K**; define how panels reflow/collapse when the
  window is narrow (the right panel and left column should degrade gracefully).
- Preserve keyboard-first use: Run (Ctrl+Enter), toggle code (Ctrl+Shift+C);
  show focus states.
- Dark theme is primary; note any tokens that would need a light variant later.

## 9. Output format requested
- A short rationale (2–4 sentences) on the chosen spatial model.
- Annotated mockups for each screen in §7.
- The component sheet in §6.
- A tokens table (colors, spacing scale, radii, type scale) so it can be
  translated directly into `aetherlab/ui/style.py` QSS.
- A mapping note: for each redesigned element, name the Qt widget it maps to.

## 10. Out of scope
No backend/pipeline changes, no new engines, no auth. Visual + interaction
redesign only; keep the existing feature set (see the tracker
`AetherLab_Feature_Tracker.xlsx`) and just make it clearer and more cohesive.
