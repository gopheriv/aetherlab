# AetherLab — Phase 2 Error Log

Testing method: `test_features.py` exercises all 100 catalogued features
(headless logic, offscreen-Qt widget construction, and source assertions).
**Automated result: 100/100 pass at the behavioural/happy-path level.**

Green happy-path tests do not prove the absence of defects, so this log records
the logistical/UX errors found by close code review of paths the happy-path
tests don't reach. Each is fixed in Phase 3 and re-verified in Phase 4.

| # | Severity | Feature | File | Defect |
|---|----------|---------|------|--------|
| BUG-1 | Logistical | F17 Pipeline stepper | `ui/widgets.py:316,449` | `PipelineStepper` defines `reset()` **twice**. The second (`set_stage(-1)`) shadows the first and never clears `_started`/`_elapsed`, so **stale per-stage elapsed times leak across runs**. `MainWindow.start_pipeline` calls `reset()` expecting a clean slate. |
| BUG-2 | Logistical | F70 Parameter sync | `ui/widgets.py:906-919` | `ParameterDock.update_variable` expands range with `setRange(0, span)` and tests `if value > span`, contradicting `set_variables` which uses `[-span, span]`. A large **negative** value pushed from the canvas is clamped and the spinbox loses its negative range — inconsistent with the negative-value support elsewhere. |
| BUG-3 | UX / consistency | F36/F38 References | `services/rag.py:140`, `ui/widgets.py:1213` | Filesystem RAG sets `score` = raw keyword **count** (unbounded: 1, 5, 12…). ChromaDB sets `score` = `1/(1+dist)` in `[0,1]`. The reference card renders `{score:.2f}` and colours the pill with 0-1 thresholds (`≥0.8` emerald / `≥0.5` amber). So filesystem hits always show emerald and a misleading number like `12.00`. The two backends are visually incomparable. |
| BUG-4 | UX / consistency | F10 Settings dialog | `ui/main_window.py:611-648`, `core/settings.py:68-76` | The Settings dialog shows a **Data path** field, but `_open_settings` never passes `data_dir` to `save_app_config`, and `load_settings` reads `data_dir` only from env/default (never app-config). So editing Data path silently does not persist across restarts — unlike Library path, which does. Misleading field. |
| BUG-5 | Dead config | F06 Settings | `core/settings.py:28` | `llm_context_window` (default `250_000`) is defined but **referenced nowhere** in the codebase. It is inert configuration that implies an effect it doesn't have. (This is the very value the user opened the session asking to change from 1M to 250k.) |

## Notes on non-issues considered and dismissed
- `SimulationPanel.show_loading` is defined but unused — the shell drives the
  running state via `RunningView`; `hide_loading` is still used. Harmless dead
  method, not fixed.
- `llm.awaitable_pause()` is effectively a no-op; harmless, left as-is.
- No infinite-loop risk in the param↔canvas signal path: `blockSignals`
  guards the mirror updates.
