# AetherLab v2 — Component sheet & Qt mapping

States listed as default / hover / active / disabled where applicable. Dark theme.

## Carried from v1 (evolved)
| Component | States | Qt widget |
|---|---|---|
| Rail item | default / hover / active (cyan tint + left bar) / disabled | `QToolButton` in `QFrame` |
| Timeline node | done (emerald ✓) / active (violet pulse) / pending / error | custom `QWidget` + `QPainter` |
| Command bar | idle / running (Run→Cancel) | `QFrame` + `QLineEdit` + `QPushButton` |
| Parameter row | symbol · slider · value · reset | `QLabel(pixmap)` + `QSlider` + `QLabel` |
| Reference card | default / hover / dimmed (low relevance) | `QFrame` |
| Video controls | frame-step / play-pause / seek / speed | `QSlider` + `QToolButton`s |
| Derivation block | prose + inline math | `QLabel(pixmap)` fragments in flow |
| Toast | success / warn / error | `QFrame` overlay, auto-dismiss |
| Settings field | text / select / toggle / slider | `QLineEdit` / `QComboBox` / custom `QCheckBox` / `QSlider` |

## New in v2
| Component | States | Qt widget |
|---|---|---|
| **Hero equation banner** | normal / long-equation (shrink + h-scroll) / loading shimmer | `QLabel(pixmap)` in `QScrollArea`; shimmer = animated `QWidget` |
| **Inline-math step** | collapsed preview / expanded | `QLabel(pixmap)` inline in `QTextBrowser`/flow |
| **Equation chip** | result (cyan) / concept (violet) / neutral | `QLabel(pixmap)` with pill `QFrame` bg |
| **Storyboard act card** | pending (dashed) / active (violet shimmer) / complete | `QFrame`; shimmer via `QPropertyAnimation` on gradient |
| **Act timeline strip** | filling (while rendering) / static (done) | `QHBoxLayout` of act cards |
| **Narration line** | act label + italic spoken line | `QLabel` (label) + `QLabel` (script) |
| **Critique badge** | ship (emerald ≥ threshold) / revise (amber) / skipped (muted) + issues popover | `QFrame` + popover `QFrame` |
| **“revised ×N” / “repaired ×N” pill** | count ≥ 1 | `QLabel` pill |
| **Diagnostics drawer** | collapsed / expanded; rows w/ severity dots | `QToolBox`/`QFrame` + mono `QPlainTextEdit` rows |
| **Library book card** | indexed (emerald) / re-indexing (amber) / pending (grey) | `QFrame` with painted spine |
| **Seek bar w/ act markers** | act ticks (violet) + hero bookmark (amber) | `QSlider` subclass, `paintEvent` overlays |
| **Manim CE badge** | large / small | `QFrame` + `QLabel` |
| **Code view** | Manim-aware syntax highlight | `QPlainTextEdit` + `QSyntaxHighlighter` |

## Syntax accent map (code view)
- keywords / imports → violet `#8B5CF6`
- class names → cyan `#22D3EE`
- `self.play` verbs (Create/Write/Transform…) → emerald `#10B981`
- strings & numbers → amber `#F59E0B`
- comments → tx-3 `#64748B`

## Build notes
- Equations are **pixmaps** (LaTeX via MiKTeX or mathtext) with a stored baseline offset for inline alignment — never selectable rich text.
- Canvas is custom-painted (`QPainter`); only its chrome is designed here (toolbar, readout chips, legend, export).
- No CSS grid/flex-only effects, no web fonts assumed, no blur-heavy glass — translucency only.
- Every control has a visible focus state (1.5px cyan outline) for keyboard-first use.
