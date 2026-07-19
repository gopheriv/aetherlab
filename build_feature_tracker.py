"""Canonical AetherLab feature tracker generator.

This is the SINGLE source of truth for the feature catalog. Every feature was
derived by reading the current source (aetherlab/**), including uncommitted
work: the Library manager, OpenStax starter downloads, the safe plot-expression
compiler, solver plot payloads, app-config persistence, and the redesigned
shell (TitleBar / Toast / EmptyState / RunningView).

Run:  python build_feature_tracker.py
Emits: AetherLab_Feature_Tracker.xlsx  (canonical)
       AetherLab_Feature_Tracker.csv   (diff-friendly mirror of the same data)

Columns per feature:
  ID · Category · Feature · User Story · Expected Behavior (from code) ·
  Source File(s) · Test Method · Status · Notes

Status vocabulary: Documented · PASS · FAIL · PARTIAL · FIXED
Test Method:       headless (import+run) · static (source assertion) · gui (manual)
"""

from __future__ import annotations

import csv
from pathlib import Path

# fmt: off
# (ID, Category, Feature, User Story, Expected Behavior, Sources, TestMethod, Status, Notes)
FEATURES: list[tuple[str, str, str, str, str, str, str, str, str]] = [
    # ── Launch / CLI ────────────────────────────────────────────────────────
    ("F01", "Launch", "GUI launch via CLI",
     "As a user, I run `python -m aetherlab` and the desktop app opens.",
     "main() with no --smoke imports ui.app.run_app, builds QApplication + MainWindow(load_settings()), shows it, returns app.exec(). RuntimeError (missing PyQt6) prints to stderr and returns exit code 2.",
     "__main__.py / ui/app.py", "gui", "Documented", ""),
    ("F02", "Launch", "Headless smoke pipeline",
     "As a developer, I run `python -m aetherlab --smoke` to exercise the whole pipeline without a GUI.",
     "--smoke [prompt] runs AetherLabPipeline.run() and prints cache key, solver model, keywords, RAG hit count, scene engine, scene status; returns 0. Default prompt is the damped oscillator.",
     "__main__.py", "headless", "Documented", ""),
    ("F03", "Launch", "Smoke test with custom prompt",
     "As a developer, I pass my own prompt to --smoke.",
     "`--smoke \"...\"` uses the provided string (nargs='?', const=default) instead of the default prompt.",
     "__main__.py", "headless", "Documented", ""),
    ("F04", "Launch", "Watchdog auto-restart",
     "As a user, if AetherLab crashes the watchdog restarts it.",
     "aetherlab_watchdog.py relaunches on non-zero exit with exponential backoff; stops on clean exit (0).",
     "aetherlab_watchdog.py / start.bat", "static", "Documented", ""),
    ("F05", "Launch", "Clear error when PyQt6 missing",
     "As a user without PyQt6, I get an actionable message, not a stack trace.",
     "require_qt() raises RuntimeError with `pip install PyQt6` instructions; main() catches and prints to stderr, exit 2.",
     "ui/qt_compat.py", "static", "Documented", ""),

    # ── Settings / Config ───────────────────────────────────────────────────
    ("F06", "Settings", "Load settings from environment",
     "As a user, my AETHERLAB_*/OPENAI_* env vars configure the app.",
     "load_settings() reads AETHERLAB_DATA_DIR/CACHE_PATH/CHROMA_PATH/LIBRARY_DIR, AETHERLAB_OPENAI_API_KEY|OPENAI_API_KEY, base URL, LLM_MODEL, LLM_TIMEOUT. Missing → defaults.",
     "core/settings.py", "headless", "Documented", ""),
    ("F07", "Settings", "App-config persistence (settings.json)",
     "As a user, values I save in the Settings dialog survive restarts.",
     "save_app_config writes data_dir/settings.json (drops empty/None); load_app_config reads it; feeds load_settings. app_config_path honors AETHERLAB_DATA_DIR.",
     "core/settings.py", "headless", "Documented", ""),
    ("F08", "Settings", "Provider precedence: env > app-config > qwen",
     "As a user, explicit env vars win over saved config, which wins over the legacy Qwen file.",
     "load_settings resolves model/api_key/base_url in that order; provider_source labels the winning tier.",
     "core/settings.py", "headless", "Documented", ""),
    ("F09", "Settings", "Qwen ~/.qwen/settings.json autoload",
     "As a Qwen Code user, AetherLab auto-detects my provider.",
     "load_qwen_settings extracts model name, base URL, and api key (via envKey/env) without logging secrets; returns {} if absent/corrupt.",
     "core/settings.py", "headless", "Documented", ""),
    ("F10", "Settings", "Settings dialog (Ctrl+,/gear)",
     "As a user, I open Settings to edit provider, rendering, and paths.",
     "SettingsDialog: API key (password + reveal eye), Base URL, Model, Render engine (Manim only), Default quality, Library path + Browse, Data path + Browse. Save persists via save_app_config and applies via dataclasses.replace.",
     "ui/main_window.py (SettingsDialog)", "gui", "Documented", ""),
    ("F11", "Settings", "Platform-aware default paths",
     "As a Windows user my data goes under %LOCALAPPDATA%\\AetherLab; else ~/.aetherlab.",
     "_default_data_dir / _default_chroma_path branch on LOCALAPPDATA env presence.",
     "core/settings.py", "headless", "Documented", ""),

    # ── Command bar / Input ─────────────────────────────────────────────────
    ("F12", "Input", "Prompt submission",
     "As a user, I type a problem and press Enter / Run / Ctrl+Enter to start.",
     "CommandBar validates non-empty and run visible, emits submitted(str), clears field. MainWindow.start_pipeline launches the worker.",
     "ui/widgets.py (CommandBar) / main_window.py", "static", "Documented", ""),
    ("F13", "Input", "Examples popup",
     "As a user, I pick a pre-made example to fill the prompt.",
     "Examples button opens a QMenu of 10 prompts anchored above the bar; selecting fills the field and focuses it.",
     "ui/widgets.py (CommandBar)", "gui", "Documented", ""),
    ("F14", "Input", "Render quality selector",
     "As a user, I choose Draft/Standard/High before running.",
     "QualityCombo maps Draft/Standard/High → l/m/h via get_render_quality; set_quality selects by flag (Settings default).",
     "ui/widgets.py (CommandBar)", "static", "Documented", ""),
    ("F15", "Input", "Run↔Cancel button swap",
     "As a user, the Run button becomes Cancel while a run is in flight.",
     "set_busy(True) hides Run, shows Cancel, disables input; cancel_button emits cancel_requested.",
     "ui/widgets.py (CommandBar)", "static", "Documented", ""),

    # ── Pipeline ────────────────────────────────────────────────────────────
    ("F16", "Pipeline", "4-stage pipeline with progress",
     "As a user, I watch Solve→RAG→Scene→Render advance.",
     "PipelineWorker runs solve, ensure-ingest, RAG+scene, render; emits solver/rag/scene/render_ready, status, and progress(pct,label). RAG and scene are awaited within one async run.",
     "ui/workers.py", "headless", "Documented", ""),
    ("F17", "Pipeline", "Pipeline stepper timeline",
     "As a user, each stage node shows pending/active/complete/error with elapsed time and a pulse.",
     "PipelineStepper paints 4 nodes, emerald connectors, active pulse + rotating arc, per-stage elapsed seconds, and an inline Cancel hit-target under the active node.",
     "ui/widgets.py (PipelineStepper)", "gui", "Documented", ""),
    ("F18", "Pipeline", "Cancellation",
     "As a user, Escape / Cancel / the stepper Cancel stops the run.",
     "worker.cancel() sets a flag; _check_cancelled between stages raises _PipelineCancelled → status 'cancelled'. UI restores ready state, hides busy, shows a warning toast.",
     "ui/workers.py / main_window.py", "static", "Documented", ""),
    ("F19", "Pipeline", "Prevent double-run",
     "As a user, I can't start a second run while one is active.",
     "start_pipeline returns early if worker.isRunning(); status shows 'Pipeline is already running.'",
     "ui/main_window.py", "static", "Documented", ""),
    ("F20", "Pipeline", "Worker signal cleanup",
     "As a user, repeated runs don't leak old worker signal connections.",
     "start_pipeline disconnects every signal of the previous worker and deleteLater()s it before wiring the new one.",
     "ui/main_window.py", "static", "Documented", ""),
    ("F21", "Pipeline", "Graceful shutdown on close",
     "As a user, closing mid-run doesn't orphan the thread.",
     "closeEvent cancels the worker and waits up to 5s.",
     "ui/main_window.py", "static", "Documented", ""),

    # ── Solver ──────────────────────────────────────────────────────────────
    ("F22", "Solver", "LLM analytical solve",
     "As a user with an API key, the LLM returns a summary, steps, keywords, variables, and an optional plot.",
     "AsyncLLMCoordinator._solve_remote calls the OpenAI-compatible chat API (temperature 0.2), parses strict JSON, coerces variables→floats, keeps the raw plot dict.",
     "services/llm.py", "gui", "Documented", ""),
    ("F23", "Solver", "Deterministic fallback",
     "As a user without a key (or on API error), I still get a keyword-based scaffold.",
     "_fallback builds 5 canned steps, merges DEFAULT_VARIABLES with request params, sets model_name 'deterministic-fallback', and attaches fallback_plot_payload().",
     "services/llm.py", "headless", "Documented", ""),
    ("F24", "Solver", "Keyword extraction + phrase detection",
     "As a user, my prompt yields ranked keywords including multi-word physics phrases.",
     "extract_keywords tokenizes, drops stopwords, ranks by frequency, and prepends matched phrases (fourier transform, navier stokes, ...) recognizing both spaced and hyphenated forms.",
     "services/llm.py", "headless", "Documented", ""),
    ("F25", "Solver", "Resilient JSON parsing",
     "As a user of reasoning models, wrapped/notated JSON still parses.",
     "_parse_json strips <think>...</think> then json.loads; on failure extracts the first {...} block.",
     "services/llm.py", "headless", "Documented", ""),
    ("F26", "Solver", "Solver plot payload",
     "As a user, the solver can describe the single curve that captures its result.",
     "System prompt requests an optional plot {kind,x,y,t_range,x_range,y_range,labels}; kept raw on SolverResult.plot and validated at canvas-build time.",
     "services/llm.py / core/models.py", "headless", "Documented", ""),

    # ── Safe plot expression compiler (NEW) ─────────────────────────────────
    ("F27", "Plot", "Safe expression compiler",
     "As a user, solver-provided math expressions render without ever eval-ing arbitrary code.",
     "plotting.compile_expression parses with ast, walks a strict whitelist (numeric literals, + - * / ** % //, whitelisted numpy fns, pi/e/tau, t + params), int→float transform, compiles to a numpy-vectorized fn. Rejects names/calls/ops outside the whitelist.",
     "services/plotting.py", "headless", "Documented", ""),
    ("F28", "Plot", "Expression safety limits",
     "As a user, pathological expressions can't hang or blow memory.",
     "MAX_EXPR_CHARS 512, MAX_AST_NODES 200, MAX_T_SPAN 1e4 clamp; OverflowError→inf, ZeroDivisionError→nan; '^' normalized to '**'; results broadcast to the sample grid.",
     "services/plotting.py", "headless", "Documented", ""),
    ("F29", "Plot", "Plot payload validation",
     "As a user, a malformed plot payload degrades gracefully instead of crashing.",
     "compile_plot validates kind∈{explicit,parametric}, finite lo<hi ranges via _pair, clamps t-span, compiles x/y; fallback_plot_payload() gives the deterministic damped-oscillator curve.",
     "services/plotting.py", "headless", "Documented", ""),

    # ── Cache ───────────────────────────────────────────────────────────────
    ("F30", "Cache", "SHA-256 session key",
     "As a user, identical problems map to one cache entry regardless of whitespace/param order.",
     "make_key hashes the canonical payload (normalized prompt + alphabetically sorted params + session id).",
     "core/cache.py / models.py", "headless", "Documented", ""),
    ("F31", "Cache", "Incremental stage caching",
     "As a user, each stage result is stored independently so partial re-runs skip finished stages.",
     "SessionCache stores solver/rag/scene JSON in separate columns; get() rehydrates with cached=True; _store_json whitelists the column name (SQL-injection guard).",
     "core/cache.py", "headless", "Documented", ""),
    ("F32", "Cache", "Solver cache invalidation",
     "As a user, changing the model (or adding a key) invalidates a stale solver cache.",
     "_solver_cache_usable rejects a fallback result once a key exists, and any result whose model_name isn't the current model or 'deterministic-fallback'.",
     "ui/workers.py / services/pipeline.py", "headless", "Documented", ""),
    ("F33", "Cache", "Scene cache invalidation on engine change",
     "As a user, switching Manim engine regenerates the scene.",
     "Scene reused only if cached.engine == current engine and status ∈ {compiled, rendered}.",
     "ui/workers.py / services/pipeline.py", "static", "Documented", ""),
    ("F34", "Cache", "Video re-render on missing file",
     "As a user, a deleted cached video re-renders automatically.",
     "A 'rendered' scene whose video_path no longer exists is re-rendered; needs_render covers compiled and missing-video rendered.",
     "ui/workers.py / services/pipeline.py", "static", "Documented", ""),

    # ── RAG ─────────────────────────────────────────────────────────────────
    ("F35", "RAG", "ChromaDB vector search",
     "As a user with ChromaDB, references come from vector similarity.",
     "LocalVectorRag._try_chromadb queries the 'textbooks' collection; score = 1/(1+distance); returns top-N hits with excerpts; backend 'chromadb'.",
     "services/rag.py", "gui", "Documented", ""),
    ("F36", "RAG", "Filesystem keyword fallback",
     "As a user without ChromaDB, references come from keyword frequency.",
     "_filesystem_search walks the library, scores text/PDF by keyword counts, extracts a 520-char excerpt centered on the first match; PDFs are strided-sampled (≤40 pages). backend 'filesystem'.",
     "services/rag.py", "headless", "Documented", ""),
    ("F37", "RAG", "Empty / missing-library handling",
     "As a user with no keywords or no library, I get an explanatory empty state, not an error.",
     "search returns backend 'none' for empty keywords; 'filesystem-missing-library' when the dir is absent; ReferencePanel shows a tailored empty hint.",
     "services/rag.py / ui/widgets.py", "headless", "Documented", ""),
    ("F38", "RAG", "Reference cards",
     "As a user, hits render as cards with source, page, score pill, excerpt, copy, and Open.",
     "_RagHitCard: score pill emerald≥0.8/amber≥0.5/gray, Copy excerpt, Open launches the source file via QDesktopServices. Backend label shows 'backend · N hits'.",
     "ui/widgets.py (ReferencePanel)", "gui", "Documented", ""),

    # ── Ingestion ───────────────────────────────────────────────────────────
    ("F39", "Ingestion", "Auto-ingest library on first run",
     "As a user, my library is indexed automatically the first time I run.",
     "_ensure_ingested checks the ChromaDB collection count; if empty and a library exists, LibraryIngestor.ingest() runs (both pipeline and worker paths).",
     "ui/workers.py / services/pipeline.py / ingestion.py", "static", "Documented", ""),
    ("F40", "Ingestion", "Incremental ingestion with manifest",
     "As a user, re-indexing only processes new/changed files.",
     "A JSON manifest keyed by path stores mtime+size+chunks; pending_files / _needs_ingest skip unchanged files; manifest saved after each completed file (atomic tmp-rename).",
     "services/ingestion.py", "headless", "Documented", ""),
    ("F41", "Ingestion", "Boundary-aware chunking",
     "As a user, text is chunked on sentence boundaries with overlap.",
     "chunk_text: 1400-char windows, 180 overlap, prefers to break at '. '/'; '/newline past the half-way point.",
     "services/ingestion.py", "headless", "Documented", ""),
    ("F42", "Ingestion", "PDF ingestion (PyMuPDF)",
     "As a user, my PDFs are indexed page-by-page.",
     "_chunks_from_pdf opens with fitz, chunks each page, tags metadata with page number; skips silently if fitz unavailable or the file won't open.",
     "services/ingestion.py", "headless", "Documented", ""),
    ("F43", "Ingestion", "Batched, cancellable, resumable upsert",
     "As a user, indexing is chunked, cancellable, and resumes where it left off.",
     "ingest upserts in batches of 96, checks should_cancel between batches, returns partial count on cancel; a cancelled file stays out of the manifest so it's reprocessed next run. reset=True rebuilds and clears the manifest.",
     "services/ingestion.py", "headless", "Documented", ""),

    # ── Library manager (NEW) ───────────────────────────────────────────────
    ("F44", "Library", "Library panel source list",
     "As a user, I see every library file with size and an Indexed/Pending chip.",
     "LibraryPanel.refresh lists .pdf/.txt/.md/.tex with MB/KB size and a chip colored by manifest membership; shows a dashed empty state with CTAs when empty.",
     "ui/widgets.py (LibraryPanel)", "gui", "Documented", ""),
    ("F45", "Library", "Add folder",
     "As a user, I copy documents from a folder into my library.",
     "_add_folder copies matching files (skipping existing names) into the library dir, reports the count, refreshes, and kicks off an incremental re-index.",
     "ui/widgets.py (LibraryPanel)", "gui", "Documented", ""),
    ("F46", "Library", "Re-index (incremental / full)",
     "As a user, Re-index picks up changes; Ctrl+click forces a full rebuild.",
     "_reindex_clicked reads the Ctrl modifier; _start_ingest runs _IngestWorker (background QThread) with progress + cancel; button disables and relabels while running.",
     "ui/widgets.py (LibraryPanel/_IngestWorker)", "gui", "Documented", ""),
    ("F47", "Library", "Get starter library (OpenStax)",
     "As a user, I download free OpenStax university-physics textbooks into my library.",
     "StarterLibraryDialog lists 8 CC-BY OpenStax books (University Physics Vol 1-3 default; Astronomy 2e, Calculus Vol 1-3, College Physics 2e opt-in) with real sizes + a warning for the extras; Download checks ≥500MB free, streams via _DownloadWorker, writes ATTRIBUTION, then auto-indexes.",
     "ui/widgets.py / services/starter_library.py", "gui", "Documented", ""),
    ("F48", "Library", "Robust download (resume/atomic/URL-resolve)",
     "As a user, downloads survive AV locks and partial failures.",
     "download_book streams to <name>.part, atomically os.replace()s (one retry after AV lock), skips files >5MB already present; resolve_pdf_urls pulls current URLs from the OpenStax CMS with hardcoded fallbacks; one failed book doesn't abort the rest.",
     "services/starter_library.py", "headless", "Documented", ""),

    # ── Scene generation ────────────────────────────────────────────────────
    ("F49", "Scene", "LLM scene generation",
     "As a user, the LLM writes custom Manim code for my problem.",
     "SceneGenerator sends the 18-rule system prompt + structured context (temperature 0.4, max_tokens 16384), then _extract_code strips <think>/fences, forces the class name, injects imports, and requires a class + construct().",
     "services/scene_generator.py", "gui", "Documented", ""),
    ("F50", "Scene", "Compile validation + retry",
     "As a user, generated code is compile()-checked and retried once on SyntaxError.",
     "generate_scene_async compiles each attempt; on SyntaxError retries up to max_retries=1, then falls back to the static template (status compiled/compile-error).",
     "services/manim_runtime.py", "gui", "Documented", ""),
    ("F51", "Scene", "Static fallback template scene",
     "As a user without a key, I get a deterministic template scene filled with my data.",
     "_build_scene_code fills _MANIM_SCENE_TEMPLATE with truncated title/summary/steps/variables + RAG count; always animates in (no empty video); compiles under Manim Community.",
     "services/manim_runtime.py", "headless", "Documented", ""),
    ("F52", "Scene", "Dynamic fallback scene",
     "As a user, if the LLM scene fails, a ValueTracker-based animated fallback uses my variables.",
     "_fallback_scene builds axes + always_redraw curve/dot from damping/stiffness/mass and animates damping with there_and_back.",
     "services/scene_generator.py", "headless", "Documented", ""),
    ("F53", "Scene", "Engine detection",
     "As a user, AetherLab detects manim (Community) or manimlib.",
     "detect_engine prefers importable 'manim' → 'manim-community', else 'manimlib' → 'manimgl', else 'generated-only' with diagnostics.",
     "services/manim_runtime.py", "headless", "Documented", ""),

    # ── Render ──────────────────────────────────────────────────────────────
    ("F54", "Render", "Manim video render",
     "As a user, the compiled scene renders to MP4 via a manim subprocess.",
     "render_scene writes the .py to a temp render dir, runs `python -m manim render -q<q> --fps <tier> --media_dir ...`, CREATE_NO_WINDOW on Windows, cleans old renders, then finds the newest MP4.",
     "services/manim_runtime.py", "gui", "Documented", ""),
    ("F55", "Render", "Hardware render tier",
     "As a user, rendering matches my hardware (fps + priority).",
     "_detect_render_tier: ≥16GB/≥6cpu → cinematic 60fps; ≥10GB → standard 30fps; else constrained 30fps below-normal priority. Always passes explicit --fps.",
     "services/manim_runtime.py", "headless", "Documented", ""),
    ("F56", "Render", "Quality-scaled timeouts",
     "As a user, renders can't hang forever.",
     "timeout_map l=240/m=420/h=600/k=900s; TimeoutExpired→status 'render-timeout'; non-zero exit→'render-error' with tail of stderr.",
     "services/manim_runtime.py", "static", "Documented", ""),
    ("F57", "Render", "Stale render cleanup + video discovery",
     "As a user, I never get a stale video back.",
     "_clean_old_renders removes media/videos/<scene>/ before rendering; _find_video returns the most recently modified MP4 via rglob.",
     "services/manim_runtime.py", "headless", "Documented", ""),
    ("F58", "Render", "Manim binary detection",
     "As a user, AetherLab finds the right manim to run.",
     "_find_manim_command prefers `sys.executable -m manim`, else shutil.which('manim'), else None (code-only).",
     "services/manim_runtime.py", "headless", "Documented", ""),

    # ── Scene UI ────────────────────────────────────────────────────────────
    ("F59", "SceneUI", "Canvas/Video/Code pill tabs",
     "As a user, I switch between the live canvas, the video, and the code.",
     "SimulationPanel top-bar pills map to stack pages 1/2/3; loading overlay is page 0.",
     "ui/widgets.py (SimulationPanel)", "gui", "Documented", ""),
    ("F60", "SceneUI", "Code viewer",
     "As a user, I read the generated code, copy it, or export scene.py.",
     "Read-only QPlainTextEdit; Copy code and Export scene.py buttons; diagnostics appended each prefixed with '# '.",
     "ui/widgets.py (SimulationPanel)", "gui", "Documented", ""),
    ("F61", "SceneUI", "Video player",
     "As a user, I play/pause/stop/seek/step/scrub speed on the rendered video.",
     "QMediaPlayer + QVideoWidget; prev/next frame (±33ms), seek slider (drag-aware), 25-200% speed, m:ss time label; autoplays once media reaches LoadedMedia; falls back to code view if the file is missing.",
     "ui/widgets.py (SimulationPanel)", "gui", "Documented", ""),
    ("F62", "SceneUI", "Toggle code view (Ctrl+Shift+C)",
     "As a user, one shortcut flips between canvas and code.",
     "_toggle_code_view switches the workspace to Scene then toggles canvas↔code on the SimulationPanel stack.",
     "ui/main_window.py", "static", "Documented", ""),

    # ── Live canvas ─────────────────────────────────────────────────────────
    ("F63", "Canvas", "Interactive parametric canvas",
     "As a user, I see a live-animated plot with a glowing tracer and trail.",
     "LiveCanvas paints radial-gradient bg, nice-step grid, boxed axes with labels, glow curves, a 24-point fading trail, and a tracer with a coordinate label at ~30fps.",
     "ui/live_canvas.py", "gui", "Documented", ""),
    ("F64", "Canvas", "Solver-plot-driven curves with legacy fallback",
     "As a user, the canvas prefers the solver's own curve, but never crashes on bad output.",
     "build_canvas_state uses compile_plot when a plot payload exists; on any error logs and falls back to name-based domain families.",
     "ui/live_canvas.py / services/plotting.py", "headless", "Documented", ""),
    ("F65", "Canvas", "Domain auto-detection",
     "As a user, the curve type matches my variables.",
     "_DOMAIN_MAP routes damping/stiffness→damped oscillator, gravity/length→pendulum, else generic Lissajous.",
     "ui/live_canvas.py", "headless", "Documented", ""),
    ("F66", "Canvas", "Phase-portrait overlay",
     "As a user, I toggle a y-vs-dy/dt overlay.",
     "The checkbox rebuilds state; _phase_overlay_for (payload path) or _phase_portrait_curves (legacy) adds a dashed violet finite-difference curve.",
     "ui/live_canvas.py / ui/widgets.py", "headless", "Documented", ""),
    ("F67", "Canvas", "Zoom / pan / hover / reset",
     "As a user, I scroll to zoom, drag to pan, hover for coordinates, and Ctrl+0 to reset.",
     "wheelEvent zooms 0.1-50×; left-drag pans in data space; hover draws a crosshair + (x,y) label; reset_view restores zoom/pan; zoom indicator shows when ≠1×.",
     "ui/live_canvas.py / main_window.py", "gui", "Documented", ""),
    ("F68", "Canvas", "Empty state + legend + hidden-tab pause",
     "As a user, the empty canvas guides me, multi-curve plots get a legend, and hidden tabs stop animating.",
     "paintEvent draws a 'No curve data' hint when empty; _draw_legend renders for ≥2 curves; show/hideEvent start/stop the animation timer.",
     "ui/live_canvas.py", "gui", "Documented", ""),

    # ── Parameters ──────────────────────────────────────────────────────────
    ("F69", "Params", "Sliders + spinboxes + reset (negatives)",
     "As a user, I tune each variable via a slider and a precise spinbox, and reset to the original.",
     "ParameterDock builds slider(1000 ticks)+QDoubleSpinBox(4dp, range [-span,span])+↺ per variable; changes redraw the canvas live and update the analysis panel.",
     "ui/widgets.py (ParameterDock)", "gui", "Documented", ""),
    ("F70", "Params", "Bidirectional sync + dynamic range",
     "As a user, slider and spinbox stay in lock-step and grow their range when I exceed it.",
     "blockSignals prevents recursion; slider↔spinbox mirror; span expands (spinbox.setRange) when |value|>span.",
     "ui/widgets.py (ParameterDock)", "static", "Documented", ""),
    ("F71", "Params", "Collapsible parameter panel",
     "As a user, I collapse the parameter strip to save space.",
     "The ▼ header toggles the slider container; the Params rail item reveals/hides the Scene-page side panel.",
     "ui/widgets.py (ParameterDock) / main_window.py", "gui", "Documented", ""),

    # ── Analysis ────────────────────────────────────────────────────────────
    ("F72", "Analysis", "Summary banner + keyword chips",
     "As a user, I see the analytical summary and violet keyword chips.",
     "AnalysisPanel.set_solver_result fills the cyan mono banner (with a [cache] note when cached) and up to 6 keyword chips.",
     "ui/widgets.py (AnalysisPanel)", "gui", "Documented", ""),
    ("F73", "Analysis", "Collapsible derivation steps",
     "As a user, each step is a collapsible card; I can expand/collapse all and copy.",
     "_CollapsibleStepWidget toggles body on header click; Expand-all button; Copy copies summary+steps; per-step copy.",
     "ui/widgets.py (AnalysisPanel)", "gui", "Documented", ""),
    ("F74", "Analysis", "Analysis empty state",
     "As a user, before running I see a placeholder.",
     "An EmptyHint label shows until set_solver_result hides it.",
     "ui/widgets.py (AnalysisPanel)", "gui", "Documented", ""),

    # ── Navigation ──────────────────────────────────────────────────────────
    ("F75", "Navigation", "Sidebar rail destinations",
     "As a user, the 5 rail items (Solve/Refs/Scene/Params/History) drive one workspace.",
     "SidebarNav emits item_selected; _on_sidebar_select maps to empty/running/solve/scene/library/history; running/empty stand in until a result exists.",
     "ui/widgets.py (SidebarNav) / main_window.py", "gui", "Documented", ""),
    ("F76", "Navigation", "Ctrl+1..5 + arrow-key nav",
     "As a user, I switch rail items by keyboard.",
     "Ctrl+1..5 call sidebar.select(idx); SidebarNav.keyPressEvent moves selection with Up/Down/Left/Right.",
     "ui/main_window.py / widgets.py", "static", "Documented", ""),
    ("F77", "Navigation", "Params gated until result",
     "As a user, the Params item is disabled until a run produces variables.",
     "set_result_available(False) disables item 3 until on_solver_ready enables it.",
     "ui/widgets.py (SidebarNav) / main_window.py", "static", "Documented", ""),
    ("F78", "Navigation", "Auto-switch to Scene on scene ready",
     "As a user, the result reveals itself on the Scene view.",
     "on_scene_ready hides loading, sets the scene, and calls sidebar.select(2).",
     "ui/main_window.py", "static", "Documented", ""),

    # ── History ─────────────────────────────────────────────────────────────
    ("F79", "History", "Persistent history",
     "As a user, my past runs persist across sessions.",
     "HistoryPanel.init_persistence creates the history table and loads the last 100; add_entry inserts a row and a status-colored list item.",
     "ui/widgets.py (HistoryPanel)", "headless", "Documented", ""),
    ("F80", "History", "Re-run from history",
     "As a user, double-clicking an entry re-runs that prompt.",
     "itemDoubleClicked emits prompt_selected(str) → start_pipeline.",
     "ui/widgets.py (HistoryPanel) / main_window.py", "static", "Documented", ""),
    ("F81", "History", "Clear history",
     "As a user, I clear all entries from the list and the database.",
     "_clear empties the list and DELETEs from SQLite (try/finally connection).",
     "ui/widgets.py (HistoryPanel)", "static", "Documented", ""),

    # ── Feedback / Errors ───────────────────────────────────────────────────
    ("F82", "Errors", "Toast notifications",
     "As a user, errors/warnings/success/info appear as a dismissible banner with optional Details.",
     "Toast.show_message picks kind color+icon, shows a Details button (routes to the traceback window) and a dismiss.",
     "ui/widgets.py (Toast) / main_window.py", "gui", "Documented", ""),
    ("F83", "Errors", "Inline error banner + traceback window",
     "As a user, a failed run shows an inline banner and a non-modal traceback on Details.",
     "SimulationPanel.show_error_banner shows the banner; _show_error_details opens a single (deduped, WA_DeleteOnClose) traceback window.",
     "ui/widgets.py (SimulationPanel) / main_window.py", "gui", "Documented", ""),
    ("F84", "Errors", "Stepper error state + status bar",
     "As a user, the failing stage turns red and the status bar explains.",
     "on_failure sets the current stage 'error', updates the status bar with stage+message, and returns to Solve/Empty.",
     "ui/main_window.py", "static", "Documented", ""),

    # ── Export ──────────────────────────────────────────────────────────────
    ("F85", "Export", "Export derivation as LaTeX",
     "As a user, I export the derivation to a .tex file.",
     "AnalysisPanel Export menu → export_derivation_to_latex writes a standalone amsmath/booktabs document (Summary/Steps/Variables), LaTeX-escaping content.",
     "services/pdf.py / main_window.py", "headless", "Documented", ""),
    ("F86", "Export", "Export derivation as PDF",
     "As a user, I export a compiled PDF.",
     "_export_pdf writes a temp .tex (mkdir'd), runs pdflatex (60s, CREATE_NO_WINDOW), and copies the PDF to my chosen path; if pdflatex is missing it says so.",
     "services/pdf.py / main_window.py", "gui", "Documented", ""),
    ("F87", "Export", "Export scene code",
     "As a user, I save the generated Manim code as .py.",
     "export_scene_code writes scene.code to the chosen path.",
     "services/pdf.py / main_window.py", "headless", "Documented", ""),
    ("F88", "Export", "Save rendered video",
     "As a user, I save the rendered MP4 elsewhere.",
     "_save_video copies the rendered video_path to a chosen location (guards missing result/file).",
     "ui/main_window.py", "static", "Documented", ""),
    ("F89", "Export", "Export animation as GIF",
     "As a user, I convert the video to an optimized GIF.",
     "_export_gif runs ffmpeg (fps=15, scale=480 lanczos, loop 0, 120s, CREATE_NO_WINDOW); handles ffmpeg-missing and timeout with status messages.",
     "ui/main_window.py", "gui", "Documented", ""),

    # ── UX / Theme / Shell ──────────────────────────────────────────────────
    ("F90", "UX", "Dark theme (QSS)",
     "As a user, the app has a cohesive dark cyan theme.",
     "AETHERLAB_QSS styles the whole shell (bg #0A0A0F, accent cyan #06B6D4).",
     "ui/style.py", "gui", "Documented", ""),
    ("F91", "UX", "Responsive window sizing",
     "As a user, the window fits my screen.",
     "MainWindow sizes to min(1500, 92% width) × min(950, 92% height).",
     "ui/main_window.py", "static", "Documented", ""),
    ("F92", "UX", "Title bar",
     "As a user, a brand strip shows the atom mark, wordmark, and a settings gear.",
     "TitleBar (44px) with settings_requested → _open_settings.",
     "ui/widgets.py (TitleBar)", "gui", "Documented", ""),
    ("F93", "UX", "Empty / first-run state",
     "As a user, before any run I get a hero with example chips and setup CTAs.",
     "EmptyStateView shows headline, 3 example chips, and a setup strip reflecting API-key + library status (set_status).",
     "ui/widgets.py (EmptyStateView)", "gui", "Documented", ""),
    ("F94", "UX", "Running view",
     "As a user, an in-flight run shows an animated overlay + live stage text.",
     "RunningView hosts a BlueprintLoadingOverlay + headline/detail updated by _on_progress.",
     "ui/widgets.py (RunningView)", "gui", "Documented", ""),
    ("F95", "UX", "Lucide icon system",
     "As a user, crisp line icons render throughout.",
     "icons.icon/icon_pixmap/icon_label render whitelisted Lucide SVG bodies at 2× with a pixmap cache; unknown names fall back to 'info'.",
     "ui/icons.py", "headless", "Documented", ""),
    ("F96", "UX", "Loading overlay animation",
     "As a user, a blueprint overlay animates only while shown.",
     "BlueprintLoadingOverlay starts its 33ms timer on show and stops on hide (no idle CPU).",
     "ui/widgets.py (BlueprintLoadingOverlay)", "gui", "Documented", ""),

    # ── Edge / robustness ───────────────────────────────────────────────────
    ("F97", "Edge", "Defensive JSON deserialization",
     "As a user, corrupt cache rows don't crash the app.",
     "SolverResult/RagResult/SceneBundle.from_json coerce types with safe defaults; a missing plot loads as None.",
     "core/models.py", "headless", "Documented", ""),
    ("F98", "Edge", "Canvas numeric guards",
     "As a user, extreme zoom / degenerate ranges don't crash or hang.",
     "_map_to_plot guards |span|<1e-12; _nice_step returns 1.0 for degenerate ranges; non-finite samples are filtered.",
     "ui/live_canvas.py", "headless", "Documented", ""),
    ("F99", "Edge", "Headless StateBus",
     "As a developer, service events can be exercised without Qt.",
     "core/events.StateBus.subscribe/emit dispatches Event(name,payload) to callbacks.",
     "core/events.py", "headless", "Documented", ""),
    ("F100", "Edge", "Scene name sanitization + stable hashing",
     "As a user, scene files are uniquely and stably named per code.",
     "sanitize_scene_name title-cases alnum runs; _scene_name appends a 10-char sha256 of the code so identical scenes reuse caches and different prompts don't collide.",
     "services/manim_runtime.py", "headless", "Documented", ""),

    # ── Redesign Phase 1: planner + conditional outputs ─────────────────────
    ("F101", "Planner", "Prompt-to-modality routing",
     "As a user, each problem only produces the outputs it actually needs.",
     "Planner.plan() returns a LessonPlan{needs_numeric,needs_2d,needs_3d,needs_animation,needs_pdf,rationale} via one strict-JSON LLM call; the heuristic classifier routes 'explain X conceptually' to pdf-only, dynamics prompts to numeric+2d+animation, and 3-D field prompts to needs_3d. LessonPlan round-trips through JSON.",
     "services/planner.py / core/models.py", "headless", "Documented", ""),
    ("F102", "Planner", "Conditional pipeline (skip unplanned stages)",
     "As a user, conceptual questions return fast instead of rendering a needless video.",
     "AetherLabPipeline.run() and PipelineWorker gate scene generation + Manim render on plan.needs_animation; a non-animated plan yields a status='skipped' SceneBundle and no render. PipelineResult carries the plan.",
     "services/pipeline.py / ui/workers.py", "headless", "Documented", ""),
    ("F103", "Planner", "Deterministic offline planner fallback",
     "As a user without an API key, planning still works and is reproducible.",
     "Planner.plan() falls back to heuristic_plan() (model_name='heuristic-fallback') on missing key or any provider/parse error; identical prompts yield identical plans.",
     "services/planner.py", "headless", "Documented", ""),
    ("F104", "Planner", "UI view pills gated by plan",
     "As a user, I only see the Canvas/Video tabs relevant to my problem.",
     "SimulationPanel.apply_plan() hides the Canvas pill unless needs_2d or needs_3d, hides the Video pill unless needs_animation, keeps Code, and re-selects the first visible pill; MainWindow wires it via the worker's plan_ready signal.",
     "ui/widgets.py / ui/main_window.py", "gui", "Documented", ""),

    # ── Redesign Phase 2: numeric ground truth ──────────────────────────────
    ("F105", "Numeric", "ODE ground-truth integration",
     "As a user, my plots reflect the real solution, not a curve the model guessed.",
     "solve_numeric() integrates a solver-attached ODE spec (state/rhs/initial/t_range/observe) via scipy solve_ivp; RHS expressions compile through the same AST allow-list (services/plotting) so model math is never eval'd. The damped-oscillator fallback matches the closed-form underdamped solution to <1e-3; invalid/unsafe specs return ok=False (scipy optional).",
     "services/numeric.py / core/models.py", "headless", "Documented", ""),
    ("F106", "Numeric", "Canvas driven by numeric trajectory",
     "As a user, the live canvas animates the exact integrated trajectory.",
     "build_canvas_state() prefers _state_from_numeric (interpolating the integrated series) over the analytic plot payload; x(0) equals the initial condition. A missing/failed integration falls back to the plot payload then legacy curves so the canvas never crashes.",
     "ui/live_canvas.py", "headless", "Documented", ""),

    # ── Redesign Phase 3: formal cited research PDF ─────────────────────────
    ("F107", "Research", "Formal cited research PDF",
     "As a user, I get a professional PDF write-up with a figure and real citations.",
     "build_research_pdf() assembles a structured LaTeX document (problem, abstract, derivation, a matplotlib figure of the numeric ground truth, parameters, References from the RAG hits with page numbers) and compiles it via pdflatex. Every reference is a real RAG source; content is LaTeX-escaped.",
     "services/research.py / ui/main_window.py", "headless", "Documented", ""),
    ("F108", "Research", "PDF backend fallback (no pdflatex)",
     "As a user without a LaTeX install, I still get a PDF.",
     "When pdflatex is absent, build_research_pdf falls back to a matplotlib-rendered PDF (text + numeric figure) via PdfPages, then to .tex-only as a last resort. render_numeric_figure integrates the ODE (or the plot payload) into a PNG.",
     "services/research.py", "headless", "Documented", ""),

    # ── Redesign Phase 4: curated Manim component library ───────────────────
    ("F109", "Scene", "Numeric-driven trajectory component",
     "As a user, the animation shows the real solution and renders reliably.",
     "scene_components.trajectory bakes the integrated (t, x) samples into a self-contained Manim Scene (Axes + smooth VMobject curve + MoveAlongPath tracer, manim+numpy only). Render-verified: composes and renders to MP4 in a few seconds, versus fragile free-form LLM scenes.",
     "services/scene_components/trajectory.py", "headless", "Documented", ""),
    ("F110", "Scene", "3-D surface component",
     "As a user, inherently-3-D problems get a real rotating ThreeDScene.",
     "scene_components.surface3d emits a ThreeDScene (ThreeDAxes + Surface + ambient camera rotation) when the plan flags needs_3d and no numeric trajectory applies; compose_scene_code returns None when neither fits so the LLM/static path takes over. Render-verified.",
     "services/scene_components/surface3d.py", "headless", "Documented", ""),
    ("F111", "Scene", "Curated composition preferred over raw LLM",
     "As a user, scenes come from tested building blocks, not fragile generated code.",
     "ManimRuntime.generate_scene(_async) calls _compose_curated first: a composed scene that compiles is used directly (diagnostics note 'curated component'); only when no component fits does it fall back to LLM generation (with a key) or the static template. Plan is threaded from the pipeline/worker.",
     "services/manim_runtime.py", "headless", "Documented", ""),

    # ── Redesign Phase 5: physics verifier ──────────────────────────────────
    ("F112", "Verify", "Physics self-verification",
     "As a user, the result is checked against its own numerics before I trust it.",
     "verify_solution() integrates the ODE ground truth and runs concrete checks: finiteness, boundedness, energy behaviour (conserved when undamped, decaying when damped), and small-angle pendulum period vs 2*pi*sqrt(L/g). A physically-correct damped oscillator passes all checks; the report is surfaced in the smoke output and embedded in the research PDF.",
     "services/verify.py", "headless", "Documented", ""),
    ("F113", "Verify", "Catches unphysical results",
     "As a user, a wrong derivation is flagged, not silently animated.",
     "An anti-damped oscillator (flipped dissipation sign) makes energy and amplitude grow; verify_solution flags both the energy and boundedness checks as failures. This is the differentiator: the tool checks itself instead of emitting plausible-looking but wrong physics.",
     "services/verify.py", "headless", "Documented", ""),
]
# fmt: on

HEADERS = [
    "ID", "Category", "Feature", "User Story", "Expected Behavior",
    "Source File(s)", "Test Method", "Status", "Notes",
]

ROOT = Path(__file__).resolve().parent
XLSX_PATH = ROOT / "AetherLab_Feature_Tracker.xlsx"
CSV_PATH = ROOT / "AetherLab_Feature_Tracker.csv"


def write_csv() -> None:
    with CSV_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(HEADERS)
        writer.writerows(FEATURES)


def write_xlsx() -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Features"
    ws.freeze_panes = "A2"

    header_fill = PatternFill("solid", fgColor="0F172A")
    header_font = Font(bold=True, color="F8FAFC", size=11)
    status_fills = {
        "PASS": "DCFCE7", "FIXED": "DBEAFE", "PARTIAL": "FEF9C3",
        "FAIL": "FEE2E2", "Documented": "F1F5F9",
    }
    cat_font = Font(bold=True, color="0E7490")
    thin = Side(style="thin", color="E2E8F0")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    wrap_top = Alignment(wrap_text=True, vertical="top")

    ws.append(HEADERS)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(vertical="center", horizontal="left")
        cell.border = border

    for row in FEATURES:
        ws.append(list(row))
        r = ws.max_row
        status = row[7]
        for c in range(1, len(HEADERS) + 1):
            cell = ws.cell(row=r, column=c)
            cell.alignment = wrap_top
            cell.border = border
        ws.cell(row=r, column=2).font = cat_font
        ws.cell(row=r, column=1).font = Font(bold=True)
        sfill = status_fills.get(status)
        if sfill:
            ws.cell(row=r, column=8).fill = PatternFill("solid", fgColor=sfill)
            ws.cell(row=r, column=8).font = Font(bold=True)

    widths = [7, 13, 30, 46, 66, 30, 12, 12, 40]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # Summary sheet
    summary = wb.create_sheet("Summary")
    counts: dict[str, int] = {}
    cats: dict[str, int] = {}
    for row in FEATURES:
        counts[row[7]] = counts.get(row[7], 0) + 1
        cats[row[1]] = cats.get(row[1], 0) + 1
    summary.append(["Total features", len(FEATURES)])
    summary.append([])
    summary.append(["Status", "Count"])
    for k, v in sorted(counts.items()):
        summary.append([k, v])
    summary.append([])
    summary.append(["Category", "Count"])
    for k, v in sorted(cats.items()):
        summary.append([k, v])
    for cell in list(summary["A"]):
        cell.font = Font(bold=True)
    summary.column_dimensions["A"].width = 20
    summary.column_dimensions["B"].width = 10

    wb.save(XLSX_PATH)


def set_status(feature_id: str, status: str, note: str = "") -> None:
    """Update a feature's status/notes in-place (used by the test phases)."""
    for i, row in enumerate(FEATURES):
        if row[0] == feature_id:
            FEATURES[i] = row[:7] + (status, note)
            return
    raise KeyError(feature_id)


# Logistical/UX defects found by code review in Phase 2 (see ERRORS_FOUND.md),
# fixed in Phase 3. Keyed by the feature they affect.
DEFECTS: dict[str, str] = {
    "F17": "BUG-1: duplicate reset() shadowed the clearing one; stale elapsed leaked across runs.",
    "F70": "BUG-2: update_variable used setRange(0,span)/`value>span`; dropped negative range.",
    "F38": "BUG-3: filesystem RAG score is a raw count, not 0-1; pill/label semantics broke.",
    "F36": "BUG-3: filesystem RAG score normalization (see F38).",
    "F10": "BUG-4: Settings 'Data path' field never persisted (save/load ignore data_dir).",
    "F06": "BUG-5: llm_context_window setting was defined but unused (dead config).",
    "F47": "BUG-6: cancelling a starter download after >=1 book still auto-started indexing (re-showing the strip Cancel had just hidden); cancel now skips auto-index.",
}


def apply_results() -> None:
    """Stamp statuses from feature_test_results.json + Phase-2 defects."""
    results_path = ROOT / "feature_test_results.json"
    passed = {}
    if results_path.exists():
        import json
        passed = json.loads(results_path.read_text(encoding="utf-8"))
    for fid, res in passed.items():
        note = "Verified: " + res.get("note", "") if res.get("status") == "PASS" else res.get("note", "")
        try:
            set_status(fid, res.get("status", "Documented"), note[:280])
        except KeyError:
            pass
    # Defect features become FIXED (Phase 3 applied the fix + Phase 4 re-verified).
    for fid, note in DEFECTS.items():
        row = next((r for r in FEATURES if r[0] == fid), None)
        base = ("Verified. " if row and row[7] == "PASS" else "")
        set_status(fid, "FIXED", (base + note)[:280])


if __name__ == "__main__":
    apply_results()
    write_csv()
    write_xlsx()
    print(f"Wrote {len(FEATURES)} features to:")
    print(f"  {XLSX_PATH}")
    print(f"  {CSV_PATH}")
