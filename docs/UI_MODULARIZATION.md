# UI Modularization

`aetherlab/ui/widgets.py` remains the stable import path for existing callers.
The widget implementations are split into modules by responsibility:

| Module | Contents |
| --- | --- |
| `shared_widgets.py` | Loading overlay, title bar, toast, empty/running states, backdrop, clipboard helper |
| `navigation.py` | Sidebar navigation, pipeline stepper, history |
| `command_bar.py` | Prompt dock and example prompts |
| `parameter_dock.py` | Simulation parameter controls |
| `analysis_panel.py` | Derivation and verification panel |
| `reference_panel.py` | RAG reference cards and panel |
| `simulation_panel.py` | Simulation player, storyboard, critique, code and diagnostics widgets |
| `library_panel.py` | Reference library, ingestion workers and download dialog |
| `lesson_view.py` | Lesson playback, chapter checks and question cards |

The facade re-exports all 41 classes, helper functions and constants that were
defined at the top level of the old `widgets.py`, including private names used
by the existing tests. Its previously available dependency names remain
available as module attributes too. No UI strings, signal signatures, object
names, layouts, stylesheets, or widget algorithms were intentionally changed.

## Hand audit

- Compared the Python AST for every extracted top-level declaration with the
  pre-refactor file: all 41 declaration bodies and constants matched.
- Imported the legacy widget names through `aetherlab.ui.widgets` after the
  split, including private widgets used by tests.
- `widgets.py` now contains only compatibility imports and no widget logic.
- This refactor does not change rendering code or the visual design system.

## Validation

- `python test_features.py` — 223/223 passed.
- `python -m pytest -q --basetemp .analysis\pytest-ui-modularization` — 217
  passed; one third-party ChromaDB `asyncio.iscoroutinefunction` deprecation
  warning.
- `python -m compileall -q aetherlab test_features.py build_feature_tracker.py
  tools` — passed.
- `python tools/tracker_integrity_audit.py --check` — 223 features, stories,
  results, and tests aligned; passed.
- `python tools/feature_surface_audit.py --check` — 89/89 surfaces covered;
  passed.
- Qt smoke — displayed and processed events for a `MainWindow` built through
  the modular widget facade; passed.
