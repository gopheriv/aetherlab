# AetherLab Design System

AetherLab turns a natural-language physics/math prompt into an analytical derivation, textbook references (RAG), a generated Manim animation, and a live interactive parametric canvas. Users are students, educators, and researchers; the core loop is **type a prompt → watch a 4-stage pipeline (Solve → RAG → Scene → Render) → read, watch, and tweak the result.**

The target surface is a **PyQt6 desktop application** — every component here is built to map cleanly onto Qt widgets (`QStackedWidget`, `QSplitter`, `QSlider`, `QListWidget`, `QComboBox`, `QMediaPlayer`, custom `QPainter` canvases), not web-only effects.

### Source of this system
This system was authored **from a single written redesign brief**, not from an attached codebase or Figma file — none was provided. No existing product screenshots, logo, or copy deck were supplied either. Every visual and copy decision below is a reasoned extrapolation from that brief (retaining its explicit color tokens, layout description, and named problems), not a recreation of shipped AetherLab UI. If a real codebase, Figma file, or brand kit becomes available, re-run this system against it — component structure, exact copy, and the logo should all be reconciled against ground truth at that point.

**Reference document:** `AetherLab — GUI Redesign Brief` (pasted in full at project start; not a linkable file). Mentioned but not attached: `AetherLab_Feature_Tracker.xlsx` (feature scope reference — request from the user if deeper feature detail is needed).

## Spatial model (rationale)
The brief's core UX problem is navigation ambiguity — some sidebar items swapped the left column, others acted on the right panel. This system commits to **one model**: a persistent left icon rail (`Solve / Refs / Scene / Params / History`) whose items are pure destinations — each one drives what the single right-hand workspace shows — plus a workspace whose actual content is sequenced by pipeline stage, not by hidden internal tabs. The pipeline timeline is promoted to a first-class, always-visible strip across the top of the workspace so "where am I" is answered by the timeline state, not by guessing which panel reacts to which control.

## Index
- `styles.css` — root stylesheet; import this one file.
- `tokens/` — `colors.css`, `typography.css`, `spacing.css` (spacing, radii, shadow, motion tokens).
- `guidelines/` — 17 foundation specimen cards (Colors, Type, Spacing, Brand groups) visible in the Design System tab.
- `components/` — 12 React primitives, grouped by concern:
  - `core/` — `Icon`, `Button`
  - `navigation/` — `NavRailItem`
  - `pipeline/` — `PipelineTimeline` (the hero component)
  - `forms/` — `CommandBar`, `ParameterRow`, `SettingsField`
  - `content/` — `ReferenceCard` / `ReferenceEmptyState`, `DerivationBlock`
  - `media/` — `VideoControls`
  - `feedback/` — `Toast`
- `ui_kits/aetherlab-desktop/` — click-through recreation of the 8 briefed screens/states.
- `assets/` — icon note (see Iconography below; no logo supplied).
- `SKILL.md` — portable skill definition for use in Claude Code or elsewhere.

## Components
`Icon`, `Button`, `NavRailItem`, `PipelineTimeline`, `CommandBar`, `ParameterRow`, `SettingsField`, `ReferenceCard`, `ReferenceEmptyState`, `DerivationBlock`, `VideoControls`, `Toast`.

### Intentional additions
No source defined a component inventory (brief-only run), so the standard set above was authored to cover every state in brief §6. `Icon` is an intentional addition beyond §6 — a thin Lucide wrapper needed as a shared glyph primitive since the brief doesn't ship its own icon assets.

## Qt widget mapping
| Design element | Qt widget |
|---|---|
| Left nav rail / `NavRailItem` | `QToolBar` or a custom `QListWidget` in icon mode, single selection |
| Workspace switch (by pipeline output) | `QStackedWidget` |
| Left column / right panel split | `QSplitter` (horizontal), collapsible via `setSizes` |
| `PipelineTimeline` | Custom `QWidget` painted with `QPainter` (nodes + connecting lines) or a `QHBoxLayout` of styled `QLabel`/`QProgressBar` pairs |
| `CommandBar` prompt field | `QLineEdit` (or `QPlainTextEdit` for multi-line prompts) |
| Examples menu | `QComboBox` or `QMenu` anchored above the bar |
| Quality selector | `QComboBox` |
| Run / Cancel | `QPushButton`, swapped via `QStackedLayout` or icon+text change |
| `ParameterRow` slider | `QSlider` (horizontal) + `QLabel` (mono value) + `QToolButton` (reset) |
| `ReferenceCard` list | `QListWidget` with a custom item delegate, or a `QScrollArea` of `QFrame` cards |
| `DerivationBlock` | `QTextBrowser` (rich text / MathJax-rendered HTML) or a `QLabel` per step with an embedded LaTeX renderer |
| `VideoControls` | `QMediaPlayer` + `QVideoWidget` + `QSlider` (seek) + `QComboBox` (speed) |
| Live 2D canvas | Custom `QWidget` with `paintEvent` (QPainter) |
| Code viewer | `QPlainTextEdit` with a syntax-highlighting `QSyntaxHighlighter` |
| `Toast` | Custom frameless `QFrame` overlay, or `QStatusBar` replacement widget anchored to the workspace top |
| Settings dialog | `QDialog` with `QFormLayout`; `SettingsField` variants map to `QLineEdit`, `QComboBox`, `QLineEdit` + `QToolButton` (path), `QLineEdit` in password mode + toggle |
| History list | `QListWidget` / `QTableWidget` |

## Content fundamentals
No shipped copy deck was provided, so tone is inferred from the brief's own register (technical, precise, instructional) and the audience (students/educators/researchers). Guidelines for anyone writing AetherLab copy:
- **Voice:** precise and unhurried, like a good physics TA — never hypey, never cute. No exclamation points, no emoji anywhere (the brief never uses them and the "engineering blueprint" identity reads as instrument-panel serious).
- **Person:** direct address in UI chrome ("Describe a physics or math problem…", "Add textbooks…") — second person, imperative for actions, no "I" from the product.
- **Casing:** sentence case for all UI labels and buttons ("Add textbooks…", not "Add Textbooks"); nav rail labels are short single words, title case only because they're proper nouns for the destinations (Solve, Refs, Scene, Params, History).
- **Numbers & units:** always shown, never rounded away — `9.81 m/s²`, `ζ = 0.15`, `0.92` relevance score, `1.2s` elapsed. This is a physics tool; precision in copy signals precision in the math.
- **Errors:** stated as fact + cause, not apology — "Render failed: Manim exited with code 1", with a secondary "Details" affordance rather than a wall of text inline.
- **Empty states:** name the missing thing and give exactly one action — "No textbooks indexed yet" + "Add textbooks…", not multi-sentence onboarding copy.

## Visual foundations
- **Identity:** "engineering blueprint / dark lab" — a near-black instrument panel, cyan-accented, hairline-gridded, built to feel like a precision tool rather than a consumer app.
- **Color:** deep near-black base (`#0A0A0F`) with two panel tiers (`#0D0D14`, `#13131A`); a single primary accent (cyan `#06B6D4`) reserved for the active/primary action and the pipeline's live state; emerald for "complete/success," amber for warning, rose for error, violet used sparingly for keyword/tag accents. One accent per meaning — never mix cyan and violet for the same semantic role.
- **Backgrounds:** flat panel fills, no photography, no illustration. The one textured background is the simulation canvas: a subtle top-to-bottom gradient (`#0F1520` → `#0A0A0F`) with a faint blueprint grid — the only place a "texture" motif appears, and it's literal (graph paper), not decorative.
- **Type:** UI in Inter (Segoe UI on native Windows), numbers/code/equations-as-placeholder in JetBrains Mono (Cascadia Code stand-in). Mono is used generously — parameter values, timestamps, scores, code — reinforcing the instrument-panel feel.
- **Spacing:** 4px base rhythm (4/8/12/16/24/32/48/64); card interior padding is consistently 16px (`--space-4`) with 12px (`--space-3`) gaps between inline controls.
- **Radii:** small and consistent — 4px for tight chips/badges, 8px for buttons and inputs, 12px for cards and panels, full pill only for progress rails, sliders, and status chips. Nothing is fully rounded except literal pills.
- **Elevation:** panels use a soft inset highlight + outer shadow (`--shadow-panel`) rather than heavy drop shadows; cards use a lighter `--shadow-card`. The only glow effect is the cyan accent glow on the active pipeline node and focused primary controls — glow is a status signal, not decoration.
- **Borders:** 1px hairlines everywhere (`#1E293B` default, `#334155` for emphasis/hover) — the primary way panels and cards separate from each other, more often than shadow.
- **Motion:** purposeful only — stage-transition fades, an active-node pulse (1.6s, ease-standard), a determinate progress sweep (ease-out). No infinite decorative loops beyond the two live-status indicators (active pipeline node, busy command bar), and both stop the instant a stage resolves.
- **Hover states:** primary buttons lighten (cyan → lighter cyan); secondary/bordered controls gain a cyan border; ghost buttons brighten text from secondary to primary text color. Never a background-darken-only hover — always a visible color or border shift.
- **Press/active states:** primary buttons darken to `--accent-cyan-active`; nav rail "current" indicator is a persistent 3px cyan left-edge bar with glow, not a press effect.
- **Transparency/blur:** used only for the loading/busy overlay (`--surface-overlay`, translucent near-black) and popovers (examples menu) — never on persistent chrome.
- **Imagery:** none supplied or invented — see Iconography below for the icon system; no photography or illustration exists in this identity.
- **Cards:** 1px hairline border + 12px radius + `--shadow-card`, no colored left-border accent, no gradient fills.

## Iconography
No icon font, sprite sheet, or SVG set was supplied with the brief. This system uses **Lucide** (MIT-licensed, CDN-loaded) as a substitute — flagged here as a substitution, not a discovered brand asset. Lucide's thin (1.75px), geometric line style matches the "engineering blueprint" identity better than a filled/duotone set would.
- Load via `<script src="https://unpkg.com/lucide@latest"></script>` and mount through the `Icon` component (`components/core/Icon.jsx`), which renders `<i data-lucide="name">` and calls `lucide.createIcons()`.
- No emoji, no Unicode-glyph icons — every icon is a real Lucide glyph, sized 13–24px, always `currentColor` or an explicit token color, never a raster PNG.
- If real product iconography exists (a custom icon font, exported SVGs from the PyQt build, or a Qt resource file), replace this substitution and update this section — do not keep Lucide once ground truth is available.

## Fonts — substitution flag
The brief specifies **Segoe UI** (or Inter) for UI and **Cascadia Code** for mono. Cascadia Code's font files aren't redistributable from this environment, so **JetBrains Mono** (Google Fonts, similar geometric monospace with comparable weight range) is substituted in `tokens/typography.css`, loaded via Google Fonts `@import`. **Please supply actual Cascadia Code (or Segoe UI, if pixel-exact system-font matching matters) font files if you'd like the real fonts embedded** rather than this substitute.

## Caveats / open questions
- No codebase, Figma file, or existing screenshots were attached — every screen in the UI kit is a plausible reconstruction from the brief's prose description (§3, §7), not a pixel-accurate recreation of a shipped app. Flag anything that doesn't match reality.
- No logo was supplied — the wordmark is set in plain type (Inter Semibold) everywhere a mark would go. Do not treat this as a designed logotype.
- Derivation math is shown as styled monospace-italic strings, not real LaTeX/MathJax typesetting — the brief calls this out as a hard requirement (§4.3) but actual equation rendering needs a real typesetting library wired into the Qt build; this system stops at the visual placeholder.
- `AetherLab_Feature_Tracker.xlsx` was referenced but not attached — feature-completeness beyond what's described in the brief hasn't been verified against it.
