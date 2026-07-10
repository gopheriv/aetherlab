# AetherLab UI Graphic Redesign Notes

## Direction

This pass pushes the existing dark PyQt shell toward the attached "precision
instrument for seeing physics" brief: true-black stages, bright cyan active
signals, tighter 8px-or-less component radii, visible keyboard focus, mono
telemetry, and restrained blueprint/math texture. It keeps the current
information architecture: title bar, persistent rail, pipeline stepper,
workspace, command bar, and status bar.

## Active Tokens

Primary accent is `#22D3EE`; `#06B6D4` remains available as the pressed/deep
cyan for filled spines and progress accents. Surfaces stay on the dark ramp:
`#0A0A0F` app background, `#0D0D14` docks, `#13131A` panels, `#181822`
elevated controls, `#000000` video/code/canvas stage. Semantic accents remain
emerald, amber, rose, and violet.

## Qt Mapping

- `aetherlab/ui/style.py`: central QSS now owns the refined component chrome,
  including tabs, progress bars, radio buttons, scene toolbar, setup strip,
  running strip, canvas export button, and tighter card/list/video radii.
- `aetherlab/ui/theme.py`: default palette aligns QPainter/Manim scene colors
  with the bright-cyan primary.
- `aetherlab/ui/widgets.py`: key surfaces expose stable object names:
  `AnalysisCard`, `SceneToolbar`, `VideoStage`, `SetupStrip`,
  `RunningStatusStrip`, and `LibraryEmptyState`.
- `aetherlab/ui/live_canvas.py`: the hover camera button now uses
  `CanvasExportButton`, so it inherits the same instrument-button styling.

## Screen Coverage

The current implementation covers the brief's first-run, running, solve,
scene, params, references, library, history, lesson, and settings surfaces with
the existing app widgets. Storyboard, critique, diagnostics, Manim attribution,
book-spine library rows, and typeset-math banners were already present; this
pass makes their graphic treatment consistent with the shell.
