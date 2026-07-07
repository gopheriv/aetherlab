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
     "As a user, my AETHERLAB_*/OPENAI_* env vars configure the app, and I can reuse compatible manim-bot env names during migration.",
     "load_settings() reads AETHERLAB_DATA_DIR/CACHE_PATH/CHROMA_PATH/LIBRARY_DIR, AETHERLAB_OPENAI_API_KEY|OPENAI_API_KEY, base URL, LLM_MODEL, LLM_TIMEOUT. It also accepts manim-bot aliases for compatible fields: MANIM_MODEL/GPT_MODEL/CHAT_MODEL, GPT_API_KEY/DASHSCOPE_API_KEY, GPT_BASE_URL/LLM_BASE_URL, LLM_TIMEOUT, and VISUAL_CRITIC_* knobs; a legacy .env can fill still-unset compatible fields unless disabled. Missing → defaults.",
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
     "SettingsDialog: API key (password + reveal eye), Base URL, Model, Render engine (Manim only), Default quality, Library path + Browse, Data path + Browse. The long settings form is scrollable and screen-fitted so Save/Cancel remain reachable on small displays. Save persists via save_app_config and applies via dataclasses.replace.",
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
    ("F49", "Scene", "LLM scene generation (cinematic)",
     "As a user, the LLM writes custom, cinematic Manim code for my problem.",
     "SceneGenerator sends the cinematic system prompt via .replace (the prompt has literal {palette} braces) + structured context (temperature 0.4, max_tokens 32768). _extract_code strips <think>/fences, renames the class (Scene/MovingCameraScene/ThreeDScene), injects imports, requires class+construct(). A finish_reason=='length' truncation raises to route to retry/fallback.",
     "services/scene_generator.py", "gui", "Documented", ""),
    ("F50", "Scene", "Generate retry + compile validation",
     "As a user, a failed generation is retried before falling back, and generated code is compile()-checked.",
     "generate() attempts _generate_remote twice (transient/truncation hiccups) before the fallback; generate_scene_async compiles each attempt and retries on SyntaxError, else falls back to the static template (status compiled/compile-error).",
     "services/scene_generator.py / manim_runtime.py", "gui", "Documented", ""),
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
     "render_scene writes the .py to a temp render dir, runs `python -m manim render -q<q> --fps <tier> --media_dir ...`, CREATE_NO_WINDOW on Windows, cleans old renders, then finds the newest MP4. render-error keeps a 1500-char stderr tail for the repair pass. Entry point is render_scene_with_repair (see F101).",
     "services/manim_runtime.py", "gui", "Documented", ""),
    ("F55", "Render", "Hardware render tier",
     "As a user, rendering matches my hardware (fps + priority), with override knobs when I know my machine or cloud target.",
     "_detect_render_tier: ≥16GB/≥6cpu → cinematic 60fps; ≥10GB → standard 30fps; else constrained 30fps below-normal priority. AETHERLAB_RENDER_TIER/RENDER_TIER can force cinematic|standard|constrained|cloud_cinematic, and AETHERLAB_MANIM_FPS/MANIM_FPS can force explicit --fps.",
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
     "As a user, the app fits laptop, desktop, and large-screen workspaces without clipping the scene tools.",
     "MainWindow sizes to min(1500, 92% width) x min(950, 92% height), applies screen-relative minimums, keeps the Params drawer between 220-320px, and lowers canvas/video minimums so Scene and Lesson views can shrink cleanly.",
     "ui/main_window.py / ui/widgets.py / ui/live_canvas.py", "gui", "Documented", ""),
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
    ("F101", "Render", "Render self-heal (LLM repair)",
     "As a user, a scene that errors OR times out at render gets auto-fixed instead of failing.",
     "render_scene_with_repair renders, and while status in {render-error, render-timeout} with an API key, feeds an 8000-char stderr tail (12000 at the repair prompt) plus — for timeouts — actionable load-reduction direction to SceneGenerator.repair (temp 0.2), compile+safety+lint-checks the fix, and re-renders (max_repairs=2). Without a key it's exactly render_scene. Wired into both the Qt worker and the headless pipeline.",
     "services/manim_runtime.py / scene_generator.py / workers.py / pipeline.py", "headless", "Documented", ""),
    ("F102", "Solver", "Truncation guard on LLM replies",
     "As a user, a reply cut off at the token limit fails cleanly instead of yielding broken code.",
     "Both _generate_remote and repair raise ValueError when choice.finish_reason=='length', routing to the retry/fallback path rather than compiling a half-written scene.",
     "services/scene_generator.py", "headless", "Documented", ""),
    ("F103", "Scene", "Fail-closed code safety gate",
     "As a user, generated scene code can't execute arbitrary host actions from the render subprocess.",
     "validate_code_safety AST-walks generated and repaired code against an import allowlist (manim/numpy/math/...), banned builtins (exec/eval/open/__import__...), and sandbox-escape dunders (__globals__/__subclasses__...). Unsafe code counts as a failed attempt (generation) or aborts the repair.",
     "services/code_safety.py / manim_runtime.py", "headless", "Documented", ""),
    ("F104", "Scene", "Cross-run error learning",
     "As a user, the pipeline stops repeating the same render mistakes across runs.",
     "error_learner keeps a curated Manim-CE pitfall KB (ShowCreation/TexMobject/get_graph/CONFIG...) plus a JSON store of normalized error signatures (30-day TTL) at data_dir/error_patterns.json. Preventive pitfalls block is appended to the generation system prompt; hints_for() (incl. a recurrence warning) is appended to every repair error.",
     "services/error_learner.py / scene_generator.py / manim_runtime.py", "headless", "Documented", ""),
    ("F105", "Scene", "Domain-aware fallback scenes",
     "As a user without a key (or after LLM failure), the fallback video still shows MY physics domain.",
     "scene_templates.detect_domain maps keywords/variables to pendulum/orbit/wave/oscillator; build_scene emits a themed (palette via data_dir/ui_prefs.json), Text-only, compile-guaranteed scene. Replaces the generic damped-wave template in both SceneGenerator._fallback_scene and ManimRuntime._build_scene_code.",
     "services/scene_templates.py / scene_generator.py / manim_runtime.py", "headless", "Documented", ""),
    ("F106", "Scene", "Static pre-render validation battery",
     "As a user, hallucinated APIs and broken LaTeX are caught before an expensive render, not after.",
     "scene_validation: lint_manim_names (unknown names vs installed manim namespace — guaranteed NameErrors), lint_constructor_kwargs (provably-invalid kwargs, conservative: only classes without **kwargs), check_latex_strings (brace/environment/left-right balance, double scripts), estimate_duration (advisory beat-sum diagnostic). Wired into generate_scene_async (lint failure = regenerate) and the repair loop (lint report becomes the next repair's error).",
     "services/scene_validation.py / manim_runtime.py", "headless", "Documented", ""),
    ("F107", "Scene", "Storyboard→codegen split (two-call generation)",
     "As a user, my scene is first *directed* (creative treatment), then *implemented* — not improvised in one shot.",
     "SceneGenerator.storyboard() runs a hot directing pass (temp 0.9) returning strict JSON (concept/staging/palette/3 acts with durations/hero_frame/idle_loop/narration script); _generate_remote then implements the locked storyboard cold (temp 0.15) via SCENE_CODEGEN_SYSTEM_PROMPT. Any storyboard failure fails soft to the proven single-call cinematic path (temp 0.4). The storyboard rides on SceneBundle.storyboard through the cache.",
     "services/scene_generator.py / core/models.py / manim_runtime.py", "headless", "Documented", ""),
    ("F108", "Render", "Perceptual critique loop (VLM watches the video)",
     "As a user with a vision model configured, rendered videos are actually *watched* and revised until they pass a quality rubric.",
     "scene_critic samples frames uniformly (PyAV — Manim's own backend — with ffmpeg-CLI fallback), sends them + the storyboard/brief to settings.vision_model (AETHERLAB_VISION_MODEL/VISION_MODEL / app-config), and returns ship/revise + score + issues against a 5-point rubric. render_scene_with_repair loops SceneGenerator.revise() up to settings.visual_critic_max_passes (AETHERLAB_VISUAL_CRITIC_MAX_PASSES/VISUAL_CRITIC_MAX_PASSES, default 2) and samples settings.visual_critic_keyframes (AETHERLAB_VISUAL_CRITIC_KEYFRAMES/VISUAL_CRITIC_KEYFRAMES, default 6). A revision is adopted only if it still renders. No vision model → skipped.",
     "services/scene_critic.py / scene_generator.py / manim_runtime.py / core/settings.py", "headless", "Documented", ""),
    ("F109", "Canvas", "Cursor-anchored smooth zoom",
     "As a user, zooming keeps the data point under my cursor pinned under the cursor, with a smooth glide instead of jumps.",
     "wheelEvent retargets a 120ms OutCubic QVariantAnimation toward the new zoom; every animation frame re-applies _apply_zoom(zoom, anchor_px), which measures the anchor's data coords before/after the zoom and shifts _pan_offset by the delta, so the anchored point is invariant. Ctrl+0 and double-click reset.",
     "ui/live_canvas.py", "gui", "Documented", ""),
    ("F110", "Canvas", "Data-space trail + wall-clock tracer",
     "As a user, the comet trail stays glued to the curve through zoom/pan, and the sweep speed never depends on frame rate.",
     "Trail points are stored as (x, y) DATA coords and mapped to pixels at paint time (<=24 points). The tracer advances by QElapsedTimer wall-clock dt (clamped 0.25s after stalls) so one sweep takes SWEEP_SECONDS=6.0 exactly; the first tick after pause/resume only restarts the clock.",
     "ui/live_canvas.py", "gui", "Documented", ""),
    ("F111", "Canvas", "Nearest-point hover snapping",
     "As a user, hovering near a curve snaps the crosshair to the nearest sample and shows me (t, x, y), not just raw cursor coordinates.",
     "Paint publishes per-curve pixel arrays; _update_hover does a vectorized nanargmin over visible non-reference curves and snaps within 24px — crosshair locks to the sample, a ring marks it, the readout shows t plus data coords, and the legend entry highlights. Beyond 24px it falls back to raw coords.",
     "ui/live_canvas.py", "gui", "Documented", ""),
    ("F112", "Canvas", "Centralized canvas palette",
     "As a maintainer, every canvas color comes from one palette that mirrors the design tokens.",
     "Module-level CANVAS_PALETTE dict (documented as mirroring ui/style.py) consumed by every draw call, curve factory, and role assignment; the module body contains zero stray hex literals (asserted by test F112).",
     "ui/live_canvas.py / ui/style.py", "static", "Documented", ""),
    ("F113", "Canvas", "Viewport-independent sample cache + NaN-gap branches",
     "As a user, zooming is instant (no recompute) and asymptotes render as separate arms instead of a false bridge.",
     "Curve samples (t, xs, ys) are cached keyed by (params, t_range, t_steps) only — zoom/pan never rebuilds them; the data-to-pixel affine map is re-applied per paint with vectorized numpy into QPolygonF via the sip buffer (no per-point Python loops). Non-finite samples split polylines into finite runs (>=2 points), so 1/t draws exactly 2 branches.",
     "ui/live_canvas.py", "gui", "Documented", ""),
    ("F114", "Canvas", "Multi-curve solver payloads (roles, envelopes, fills, points)",
     "As a user, the solver can describe a richer picture: a hero curve plus dashed envelopes, shaded regions, and labeled markers.",
     "plotting.compile_plot accepts curves:[{name,x?,y,style,role}] (<=6, roles primary/secondary/reference, palette colors by role, dashed references excluded from tracer/trail), fill_between:{upper,lower} (translucent <=0.12 alpha gradient), points:[{t,label}] (<=8, out-of-range dropped) — all through the unchanged AST whitelist. Legacy single-curve payloads and cached SolverResults load exactly as before. The solver prompt documents the schema with an example; fallback_plot_payload showcases oscillation + two dashed envelopes.",
     "services/plotting.py / services/llm.py / ui/live_canvas.py", "headless", "Documented", ""),
    ("F115", "Canvas", "Time scrubbing + double-click reset + progress bar",
     "As a user, I can grab the animation's time axis and scrub it by hand, see progress at a glance, and double-click to reset the view.",
     "Right-drag (or Shift+drag) maps cursor x across the plot to tracer t on the primary curve; the sweep pauses while scrubbing and resumes cleanly on release (clock invalidated so no jump). A 2px t-progress bar hugs the bottom axis (brighter while scrubbing). Double-click calls reset_view() alongside Ctrl+0.",
     "ui/live_canvas.py", "gui", "Documented", ""),
    ("F116", "Canvas", "PNG export (2x) with hover camera button",
     "As a user, I can save the exact canvas I'm looking at as a crisp PNG.",
     "save_png(path=None) renders the widget into a 2x devicePixelRatio pixmap (export button hidden during render) and emits png_exported(str); no path opens a save dialog. A ghost-style camera QToolButton appears top-right on hover, per the design system.",
     "ui/live_canvas.py / ui/icons.py", "gui", "Documented", ""),
    ("F117", "Canvas", "Interactive legend",
     "As a user, the legend names every curve (even a single one) and clicking an entry hides/shows that curve.",
     "Legend renders whenever any curve is named; entries register hit rects, clicks toggle CurveSpec.visible (hidden entries render muted with a hollow swatch), the cursor becomes a pointing hand over entries, and the snapped curve's name highlights during hover.",
     "ui/live_canvas.py", "gui", "Documented", ""),
    ("F118", "Canvas", "Live parameter chip + first-paint fade-in",
     "As a user, I always see the active parameter values on the canvas, and the first curve fades in instead of popping.",
     "A mono Cascadia chip top-right renders sorted 'name=value' pairs (plus the zoom factor when zoomed) live with the sliders, placed above the legend so they never collide. The first state with curves ramps opacity 0-1 over 300ms via QVariantAnimation; subsequent slider-driven rebuilds never re-fade.",
     "ui/live_canvas.py", "gui", "Documented", ""),
    ("F119", "Design v2", "v2 token system (bright cyan, new surfaces, 56px rail)",
     "As a user, the app reads as a precision instrument: brighter cyan, richer dark surfaces, a tighter icon rail.",
     "style.py adopts CYAN #22D3EE as primary (v1 #06B6D4 kept as CYAN_DEEP for fills/spines) and adds STAGE #000000, ELEV #181822, HOVER_SURFACE #1C1C27, LINE_0 #141A24; hover/menu/list surfaces move to the new tints. CANVAS_PALETTE primary tracks the bright cyan. The nav rail shrinks to a 56px icon-first strip (labels move to tooltips).",
     "ui/style.py / ui/live_canvas.py / ui/widgets.py", "static", "Documented", ""),
    ("F120", "Design v2", "Math typesetting service (formulas-as-brand)",
     "As a user, equations render as real typeset math, not ASCII.",
     "services/mathtext.py renders a LaTeX subset via matplotlib mathtext (STIX fonts) to transparent 2x QPixmaps, cached and never-raising (bad input → None → text fallback). Provides a parameter symbol map (damping→ζ, omega0→ω₀, …), a math/prose discriminator, unicode→LaTeX cleanup, and the ambient watermark formula set.",
     "services/mathtext.py", "headless", "Documented", ""),
    ("F121", "Design v2", "Hero equation banner + param symbols + ambient math texture",
     "As a user, the derivation leads with a typeset hero equation, parameters show their real symbols, and empty surfaces carry faint formula texture.",
     "AnalysisPanel typesets a math summary into the banner pixmap (prose stays styled text); ParameterDock renders each row's symbol via render_param_symbol with a name-text fallback; EmptyStateView paints a 28px dot grid plus ≤6%-opacity watermark formulas in the corners, never behind the centered content.",
     "ui/widgets.py / services/mathtext.py", "gui", "Documented", ""),
    ("F122", "Design v2", "Scene-meta parser (storyboard / critique / self-heal state)",
     "As a user, the pipeline's directing and quality metadata drive the UI instead of hiding in logs.",
     "parse_scene_meta distills a SceneBundle's diagnostics into {repaired, revised, critique{verdict,score,issues}, duration}; _storyboard_acts normalizes SceneBundle.storyboard into ordered ESTABLISH/EVOLVE/REVEAL acts with durations, beats, and per-act narration. Both degrade cleanly on old/empty bundles (no storyboard → [], no critique → None).",
     "ui/widgets.py / core/models.py", "headless", "Documented", ""),
    ("F123", "Design v2", "Screening room + storyboard dock + code artifact",
     "As a user, the video is a screening room (true-black stage, Manim CE badge, violet act ticks + amber hero bookmark on the seek bar), the storyboard is a clickable act strip that seeks the video, and code is an artifact (line numbers, Manim-aware syntax accents, engine/status/duration chips, diagnostics drawer, repaired/revised pills).",
     "SimulationPanel swaps in CodeArtifactView (_ManimHighlighter + line numbers), ActSeekSlider (paints act ticks + hero bookmark from the storyboard), StoryboardStrip (act cards; click emits a seek fraction → _seek_fraction), CritiqueBadge (verdict/score/expandable issues), ManimBadge, a _DiagnosticsDrawer, and repaired/revised _Pill chips — populated by _apply_scene_meta from the SceneBundle.",
     "ui/widgets.py", "gui", "Documented", ""),
    ("F124", "Design v2", "Research bookshelf + Vision·Critique settings",
     "As a user, the library reads as a research bookshelf (coloured spine, chunk count, freshness dot) and Settings exposes the vision-critique model.",
     "LibraryPanel.refresh paints a _BookSpine per row and shows the manifest chunk count with an emerald-indexed / amber-re-indexing / grey-pending freshness chip. SettingsDialog gains a VISION·CRITIQUE section (vision_model field + hint) persisted through save_app_config into AppSettings.vision_model.",
     "ui/widgets.py / ui/main_window.py / core/settings.py", "gui", "Documented", ""),
    ("F125", "References", "Web references (Wikipedia) provider",
     "As a user, every run also pulls relevant encyclopedia references, not just my local textbooks.",
     "services/web_references.py fetches article intros via the public MediaWiki API (stdlib urllib, physics-biased query, short timeout) and returns them as RagHit(origin='web', source_label=title, source_path=URL). It never raises — offline/rate-limit/malformed all return []. RagHit gained origin + source_label with defaults so old cached RagResult rows deserialize unchanged; source_name prefers the clean label and is_web detects web origin.",
     "services/web_references.py / core/models.py", "headless", "Documented", ""),
    ("F126", "References", "Time-boxed web-reference merge (fail-soft)",
     "As a user, web references enrich my results without ever slowing down or breaking a solve.",
     "pipeline._merge_web_references runs the provider via asyncio.to_thread under asyncio.wait_for, keeps library hits first, appends web hits, and tags the backend '<local>+web'. Any error (or the settings toggle off) returns the original RagResult untouched. Wired into both the headless pipeline and the Qt worker (with a status line). Governed by AppSettings.web_references (env AETHERLAB_WEB_REFS / app config, default on) + web_ref_timeout.",
     "services/pipeline.py / ui/workers.py / core/settings.py", "headless", "Documented", ""),
    ("F127", "Graphics", "Reference provenance UI + blueprint backdrop + focus filament",
     "As a user, web vs library references are visually distinct, low-relevance hits recede, and the app reads like a precision instrument with clear keyboard focus.",
     "Reference cards show a globe + violet 'Wikipedia' badge and open URLs in the browser (local files still open in the OS viewer); score < 0.5 dims the card (QGraphicsOpacityEffect); the panel header counts 'N library · M web'. BlueprintBackdrop paints a 40px cyan cross-line + dot grid behind the (now-transparent) workspace; the command bar grows a cyan focus filament while the prompt is focused; and QSS adds 1.5px cyan focus rings to inputs/combos/buttons/sliders/checkboxes (v2 §9 keyboard-first). Settings gains a Web-references toggle.",
     "ui/widgets.py / ui/style.py / ui/main_window.py / ui/icons.py", "gui", "Documented", ""),
    ("F128", "Providers", "Provider presets + qwen autoload gate",
     "As a student, I never inherit someone else's provider config, and picking 'Local Ollama' just works.",
     "load_settings resolves provider_preset (env AETHERLAB_PROVIDER > app-config): 'ollama' fills base_url=http://localhost:11434/v1 + placeholder key when unset (provider_source 'ollama-local'); env vars still win. The ~/.qwen autoload is gated behind AETHERLAB_QWEN_AUTOLOAD=1 (dev opt-in).",
     "core/settings.py", "headless", "Documented", ""),
    ("F129", "Providers", "Ollama discovery + one-click local AI + connection test",
     "As a student without an API key, AetherLab finds my local Ollama and enables it in one click; any provider can be verified before saving.",
     "services/providers.py: detect_ollama (GET /api/tags, 2s, never raises) and test_connection (1-token chat ping, always returns displayable (ok,msg)). SettingsDialog gains a preset combo (Custom/Ollama/No AI) that autofills fields and lists installed models, plus a Test-connection button. MainWindow probes Ollama in a background QThread when keyless; EmptyStateView shows a 'Use local AI (Ollama)' CTA whose click persists the preset and reloads settings with a success toast.",
     "services/providers.py / ui/main_window.py / ui/widgets.py", "headless", "Documented", ""),
    ("F130", "Math", "key_equations solver contract (hero equation end-to-end)",
     "As a student, every solve leads with its governing equation, typeset — even without AI.",
     "SolverResult.key_equations (LaTeX strings, mathtext subset; old cache rows load []). The solver prompt requests 1-4 equations, governing first, no environments; the keyless fallback supplies domain-matched equations (oscillator/pendulum/orbit/wave via detect_domain). AnalysisPanel's hero banner prefers key_equations[0] via render_math; LaTeX/PDF export gains a verbatim Key Equations section (backward-compatible kwarg).",
     "core/models.py / services/llm.py / ui/widgets.py / services/pdf.py", "headless", "Documented", ""),
    ("F131", "Product", "Version, logging, and app identity",
     "As a student filing a bug report, I can name my version and attach a log; the taskbar shows the real app icon.",
     "--version prints AetherLab __version__; _setup_logging writes a rotating data_dir/logs/aetherlab.log (3x1MB, best-effort); assets/aetherlab.ico (7 sizes) is set via QApplication.setWindowIcon + SetCurrentProcessExplicitAppUserModelID so the Windows taskbar shows the atom (works from source and PyInstaller via _icon_path).",
     "aetherlab/__init__.py / __main__.py / ui/app.py / assets/", "headless", "Documented", ""),
    ("F132", "Product", "Windows packaging + LaTeX-aware scene prompts + docs/CI",
     "As a student, I install AetherLab with one Setup.exe and scenes render even without LaTeX installed.",
     "packaging/: aetherlab.spec (PyInstaller onedir; collect_all manim/chromadb/av, metadata copies, tk excluded), installer.iss (Inno Setup, Start-menu/desktop shortcuts, per-user data survives uninstall), build.py (freeze -> keyless frozen smoke that must print 'Scene status: rendered' -> installer). Frozen renders relay through the exe itself (`aetherlab --manim render ...` -> manim's CLI), since `sys.executable -m manim` is meaningless in a bundle. detect_latex() gates a 'NO LaTeX: Text-only, unicode math' rule into scene generation so MathTex is an enhancement, not a requirement. docs/QUICKSTART + TROUBLESHOOTING; .github/workflows/ci.yml runs the offscreen suite on windows-latest.",
     "packaging/ / services/manim_runtime.py / scene_generator.py / docs/ / .github/", "headless", "Documented", ""),
    ("F133", "Render", "Cross-platform render subprocess",
     "As a user on any OS (and any cloud/Linux runner), rendering and the ffmpeg/pdflatex helpers work.",
     "core/proc.subprocess_kwargs() returns creationflags (CREATE_NO_WINDOW, optional BELOW_NORMAL_PRIORITY) on Windows and start_new_session=True on POSIX — the Windows-only flags never reach a Linux subprocess. All six call sites (manim render, pdflatex, GIF ffmpeg, ffprobe/ffmpeg frame sampling) use it; zero raw creationflags remain. Prerequisite for cloud rendering (runners are Linux).",
     "core/proc.py / services/manim_runtime.py / pdf.py / scene_critic.py / ui/main_window.py", "headless", "Documented", ""),
    ("F134", "Render", "Frame-cache desync fix (the sync bug)",
     "As a user, a regenerated/repaired scene renders exactly its current code — never spliced with stale frames from a previous render.",
     "Each render runs in an isolated uuid-suffixed media dir (_RUNS_DIR/<scene>_<q>_<uuid>) with --disable_caching, so Manim can never reuse a partial-movie file across renders. _find_video_in returns THIS render's mp4 (class-named, mtime-fresh) instead of 'newest mp4 in a shared tree'. Old run dirs are LRU-pruned (bounded temp); a pruned cached video self-heals via the pipeline's video-missing re-render.",
     "services/manim_runtime.py", "headless", "Documented", ""),
    ("F135", "Render", "Hard-scene survival (draft→final, weight-aware)",
     "As a user, ambitious scenes get the render time they need and always return the best result achieved.",
     "render_scene scales the timeout by _estimate_render_cost (duration + updater/play/3D counts, capped 5x, hard ceiling 1800s) and halves fps on heavy hi-res scenes. render_scene_with_repair validates+repairs at draft quality first, then promotes to the requested quality; if the final render fails/times out it keeps the draft (partial success) instead of returning nothing. Timeout-repair instructs the model to reduce load, not gut the scene.",
     "services/manim_runtime.py", "headless", "Documented", ""),
    ("F136", "Render", "Render observability + failure classification",
     "As a user hitting a render failure, it's diagnosable and it teaches the repair loop.",
     "On any render-error/timeout the failing scene .py + full stderr are dumped to data_dir/logs/renders/<ts>_<kind>/. _classify_failure buckets stderr into latex/hallucinated-api/ffmpeg/oom/unknown; the class is stored on SceneBundle.failure_kind (round-trips through cache) and fed, with error_learner hints, into the repair prompt.",
     "services/manim_runtime.py / core/models.py", "headless", "Documented", ""),
    ("F137", "Render", "Frozen-bundle render dependencies",
     "As a student running the installer, generated scenes render from the packaged app.",
     "packaging/aetherlab.spec collect_all's the full Manim native ecosystem — manimpango (renders every Text/MarkupText — the missing piece that made frozen renders fail), skia_pathops, moderngl/moderngl_window, av, cloup — plus manim.plugins/CLI hidden imports and metadata, so `aetherlab --manim render` works in a frozen dist. Manim 0.20 encodes via PyAV, so the bundle isn't ffmpeg-CLI-dependent. VERIFIED: the frozen build.py smoke rendered a video inside the bundle ('Scene status: rendered').",
     "packaging/aetherlab.spec / __main__.py", "headless", "Documented", ""),
    ("F138", "Narration", "Voiceover engine (fit-to-video whole-clip sync)",
     "As a user, the generated video can carry a voiceover that stays in step with the animation.",
     "services/voiceover.py (ported from manim-bot's decision): edge-tts synthesize → measure video vs audio (PyAV, no ffprobe) → if the durations diverge >10%/15%, re-synthesize ONCE at an adjusted speaking rate → merge with imageio-ffmpeg's bundled binary. Audio longer than video pads the last frame (tpad); audio shorter keeps the FULL video (no -shortest) so closing beats survive. Cross-platform via core.proc.subprocess_kwargs; fully fail-soft (no edge-tts/ffmpeg → None, silent render kept).",
     "services/voiceover.py", "headless", "Documented", ""),
    ("F139", "Narration", "Narration derived from the final animation",
     "As a user, the spoken narration describes what's actually on screen, in order.",
     "SceneGenerator.narrate() writes a flowing voiceover FROM the final scene code (seeded by the storyboard's per-beat lines, length-budgeted to the storyboard's act durations) — not the impossible per-beat sync. render_scene_with_repair calls _add_narration after a successful render when settings.narration_enabled: derive script → add_voiceover(fit_to_video) → swap video_path to the narrated mp4, keeping the silent render on silent_video_path. Any failure keeps the silent video.",
     "services/scene_generator.py / manim_runtime.py / core/models.py", "headless", "Documented", ""),
    ("F140", "Narration", "Narration settings + toggle",
     "As a user, I turn narration on/off and pick a voice; it persists.",
     "AppSettings.narration_enabled/tts_voice/tts_rate resolved from env (AETHERLAB_NARRATION/AETHERLAB_TTS_*, plus manim-bot VOICEOVER_ENABLED/TTS_ENABLED/TTS_VOICE/TTS_RATE aliases) then app-config (default off). SettingsDialog gains a NARRATION section (enable checkbox + voice field) persisted via save_app_config. Old cache rows keep working (silent_video_path defaults to '').",
     "core/settings.py / ui/main_window.py / core/models.py", "headless", "Documented", ""),
    ("F141", "Lesson", "Lesson planner (topic → curriculum)",
     "As a student, I give a topic and get a structured multi-chapter lesson plan, grounded in textbooks, that works even offline.",
     "services/lesson_planner.plan_lesson runs a hot LLM pass (temp 0.8) → strict JSON lesson (title/audience/prerequisites/objectives/misconception/chapters[kind: scene|equation_card|interactive|recap, narration, key_equations, citation_query]/questions), grounded via rag.search on the topic + citation queries. Keyless/failure fails soft to a deterministic per-domain template lesson (oscillator/pendulum/orbit/wave via detect_domain, equations from FALLBACK_EQUATIONS) with a hook, misconception, interactive + recap chapters, and check-yourself questions. LessonChapter/LessonQuestion/LessonPlan/LessonBundle dataclasses (defensive from_json; old caches load).",
     "services/lesson_planner.py / core/models.py", "headless", "Documented", ""),
    ("F142", "Lesson", "Per-chapter narration + transcript timeline",
     "As a student, each chapter is narrated and the lesson has synced subtitles.",
     "voiceover.narrate_segment narrates one short chapter clip (whole-clip fit — exact-enough at chapter granularity, no fragile per-beat sync) and reports its spoken duration; build_srt turns the ordered (text, duration) timeline into cumulative .srt cues (blank chapters consume time but emit no cue). Fail-soft: missing video/edge-tts/ffmpeg keeps the silent clip.",
     "services/voiceover.py", "headless", "Documented", ""),
    ("F143", "Lesson", "Multi-chapter lesson pipeline + ffmpeg assembly",
     "As a student, a topic becomes ONE narrated multi-chapter lesson video.",
     "services/lesson_pipeline.LessonPipeline.run plans → renders each renderable chapter via the EXISTING per-scene pipeline (generate_scene_async → render_scene_with_repair, unchanged; synthesized per-chapter SolverResult from goal/beats/key_equations) with bounded concurrency, streamed progress, per-chapter disk cache (edit ch.N ⇒ only ch.N re-renders), and per-chapter narration; services/assembly.assemble_lesson (bundled imageio-ffmpeg, cross-platform) normalizes clips to 1280x720/30fps and concatenates them (+ generated silence for mixed audio; video-only fallback), emitting lesson.mp4 + lesson.srt. Surviving partial renders carry plan indexes so narration/titles/subtitles stay attached after skipped chapters. Fail-soft: a bad chapter is skipped, keyless uses domain templates, assembly failure keeps individual clips.",
     "services/lesson_pipeline.py / assembly.py / voiceover.py", "headless", "Documented", ""),
    ("F144", "Lesson", "Textbook grounding (fact-check) + study-guide export",
     "As a student, the lesson is checked against real textbooks and I can print a study guide.",
     "services/fact_check.fact_check_lesson attaches per-chapter citations (source+page) from rag.search and runs a temp-0 LLM check of each chapter's narration against retrieved passages, recording a ✓/⚠ note and applying a correction when a claim is clearly unsupported. Fail-soft (no key attaches citations only; RAG errors leave chapters untouched); wired into lesson_pipeline before rendering so corrected narration flows through. pdf.export_lesson_study_guide writes a LaTeX study guide (objectives, prerequisites, the misconception, per-chapter summaries with verbatim display-math key_equations + citations, and a self-check with answers).",
     "services/fact_check.py / lesson_pipeline.py / services/pdf.py / core/models.py", "headless", "Documented", ""),
    ("F145", "Lesson", "Lesson view + worker + Learn wiring",
     "As a student, I type a topic, press Learn, and get a self-contained lesson: inline narrated video, clickable chapter outline that seeks it, transcript, interactive questions, references, study-guide export.",
     "CommandBar gains a Learn button (emits learn_requested(topic); hidden while busy). MainWindow.start_lesson runs LessonWorker (QThread → progress/lesson_ready/failure), shows the running view, then on_lesson_ready populates LessonView (workspace PAGE_LESSON=6) and loads the assembled lesson.mp4 into its INLINE player. LessonView tabs: Video (QMediaPlayer, play/pause/stop, guarded if QtMultimedia absent) + Transcript + Questions (_QuestionCard MCQ with ✓/✗ feedback + why; open reveal) + References. The chapter outline click seeks the inline player to the chapter start and shows the Video tab (chapter_seek_requested), using rendered_chapter_indexes to keep partial lessons aligned when a middle chapter failed. A 'Play with it' tab embeds a LiveCanvas seeded from the lesson's domain (detect_domain → params) with the interactive chapter's guiding prompt, completing the pedagogy loop. Export-study-guide → pdf.export_lesson_study_guide. closeEvent waits on the lesson worker. Validated end-to-end: a keyless 'Kepler orbit' lesson renders 4 chapters and assembles a 21.9s lesson.mp4 + .srt in ~52s.",
     "ui/widgets.py / ui/workers.py / ui/main_window.py", "gui", "Documented", ""),
    ("F146", "Lesson", "Distinct chapter aspects (keyless lessons)",
     "As a student, a keyless lesson's chapters look different from each other, not the same clip N times.",
     "scene_templates.build_scene takes an `aspect` (setup/evolution/math/recap/full). Each aspect selects a distinct header composition — hero title-card (setup), boxed governing-idea banner (math), one-by-one takeaway bullets (recap), the classic top strip (evolution/full) — with matching intro animations, and scales the domain animation's run_time, so the SAME domain template renders four visually distinct clips. Every aspect×domain still compiles and passes the code-safety + pre-render lint gates and is Text-only (no LaTeX). Threaded through ManimRuntime.generate_scene_async → _build_scene_code; the Solve path defaults to `full` (unchanged).",
     "services/scene_templates.py / services/manim_runtime.py", "headless", "Documented", ""),
    ("F147", "Lesson", "Chapter→aspect assignment by role",
     "As a student, the opening chapter sets up, the math chapter shows the equation, the recap sums up — automatically.",
     "lesson_pipeline._chapter_aspect keys the aspect off the chapter's ROLE, not the domain: kind 'recap'→recap and 'equation_card'→math; goal/title keywords (deriv/equation/…, recap/summary/…) override; the first renderable chapter is 'setup'; everything else is 'evolution'. Passed into generate_scene_async per chapter so a keyless multi-chapter lesson gets a coherent setup→evolution→math→recap arc of distinct compositions.",
     "services/lesson_pipeline.py", "headless", "Documented", ""),
    ("F148", "Lesson", "Produced lesson — title cards + crossfades",
     "As a student, the lesson feels authored: a title card, a card announcing each chapter, an end card, and smooth crossfades — not a raw concatenation.",
     "services/cards.render_card_png draws intro/chapter/end cards as PNGs with Pillow + the bundled DejaVu font (no fragile ffmpeg drawtext escaping; works in the frozen bundle). assembly.assemble_lesson, given lesson/chapter titles, builds the segment plan (intro, then chapter-card+clip per chapter, then end), normalizes every segment to a uniform 1280x720/30fps mp4 (silent audio for cards), and crossfades them with xfade+acrossfade using the standard cumulative offset. Fully fail-soft: PIL/ffmpeg/xfade failure falls back to the plain normalized concat, then to the individual clips. Fonts bundled via aetherlab.spec.",
     "services/cards.py / services/assembly.py / packaging/aetherlab.spec", "headless", "Documented", ""),
    ("F149", "Lesson", "Lesson plan cache (instant re-open)",
     "As a student, re-opening a topic I already studied is instant instead of re-planning every time.",
     "lesson_pipeline._PlanCache stores the planned + fact-checked LessonPlan on disk under the data dir, keyed by a case/space-insensitive topic + audience hash, so run() reuses it and skips both the planner LLM call and the grounding pass, going straight to the per-chapter render cache. Audience-scoped (high_school/ap/undergrad key separately). regenerate=True bypasses the plan cache AND the chapter clip cache to rebuild fresh. Fail-soft: any read/write error simply misses.",
     "services/lesson_pipeline.py", "headless", "Documented", ""),
    ("F150", "Lesson", "Cancellable Learn + Regenerate control",
     "As a student, I can cancel a long lesson build (it stops promptly, keeping finished chapters) and I have a visible Regenerate button to rebuild from scratch.",
     "LessonPipeline.run polls a cancel_check between chapters and before assembly; on cancel it returns a 'cancelled' bundle with whatever rendered (never raises). LessonWorker holds a threading.Event, exposes cancel(), and passes cancel_check=event.is_set; MainWindow._cancel_pipeline (Esc / running-view Cancel) now cancels the lesson worker too, and closeEvent cancels+waits. on_lesson_ready handles 'cancelled' without ever leaving a blank page (shows finished chapters or a plain message). LessonView gains a Regenerate button (regenerate_requested → MainWindow.regenerate_lesson → start_lesson(regenerate=True)).",
     "services/lesson_pipeline.py / ui/workers.py / ui/main_window.py / ui/widgets.py", "headless", "Documented", ""),
    ("F151", "Lesson", "Partial lesson gap markers",
     "As a student, if a chapter fails to render, I can see that the lesson is partial instead of mistaking the next clip for that chapter.",
     "LessonView uses LessonBundle.rendered_chapter_indexes to mark skipped renderable chapters in the outline as '(not rendered)' with a muted row + tooltip, while surviving chapters keep their true produced-video offsets. Old bundles without the mapping keep the legacy cumulative fallback.",
     "ui/widgets.py / core/models.py", "gui", "Documented", ""),
    ("F152", "Render", "Pluggable render backend seam",
     "As a developer, local and cloud renderers share one contract without disturbing repair, critique, or narration.",
     "services/render_backend.py defines RenderBackend, LocalRenderBackend, CloudRenderBackend, select_backend(), cloud_job_id(), and render timeout/fps helpers. ManimRuntime.render_scene_with_repair routes each one-shot render through _render_once(), while render_scene() remains the local compatibility path.",
     "services/render_backend.py / services/manim_runtime.py", "headless", "Documented", ""),
    ("F153", "Render", "Cloud render settings",
     "As a user, I can configure Local/Cloud/Auto rendering and a GitHub render repo.",
     "AppSettings adds render_mode, cloud_provider, github_repo/token/workflow/branch/client id, cloud threshold, poll seconds, and cloud timeout with env > app-config precedence. It accepts manim-bot CLOUD_RENDER_ENABLED/REPO/WORKFLOW/BRANCH/TIMEOUT/POLL aliases from env or a legacy .env fallback; CLOUD_RENDER_ENABLED=true maps to AetherLab auto mode unless AETHERLAB_RENDER_MODE is explicit. SettingsDialog persists the fields; default render_mode='local' preserves current behavior.",
     "core/settings.py / ui/main_window.py", "headless", "Documented", ""),
    ("F154", "Render", "GitHub Actions cloud backend",
     "As a user, heavy scenes can render on a Linux GitHub Actions runner and return as a normal SceneBundle.",
     "CloudRenderBackend scans for secrets, computes a content job id from scene/code/quality/fps/manim pin, provisions the render workflow, commits jobs/<job_id>.py, dispatches workflow_dispatch, polls the run, follows signed artifact/log redirects without leaking GitHub auth to storage, downloads/validates the MP4 artifact into the local isolated render dir, and records a manifest so identical scenes reuse artifacts instead of re-dispatching. GitHub auth can come from Settings/env or an existing `gh auth login` token.",
     "services/render_backend.py / .github/workflows/render.yml", "headless", "Documented", ""),
    ("F155", "Render", "Cloud fail-soft local fallback",
     "As a user, missing token/network/CI never crashes a solve; AetherLab just renders locally.",
     "Cloud unavailable returns an internal cloud-unavailable SceneBundle status; ManimRuntime._render_once restores compiled status and invokes LocalRenderBackend. Successful fallback appends a diagnostic and MainWindow shows a warning toast/status message.",
     "services/render_backend.py / services/manim_runtime.py / ui/main_window.py", "headless", "Documented", ""),
    ("F156", "Security", "Cloud render secret guard",
     "As a user, cloud rendering must not commit API keys or private config material.",
     "scan_cloud_payload refuses common GitHub/OpenAI/Slack/private-key/API-key patterns before upload; _mask redacts GitHub and OpenAI token shapes in diagnostics/log messages. Public render repos are allowed, but docs warn that generated scene code itself may be visible.",
     "services/render_backend.py / docs/CLOUD_RENDERING.md", "headless", "Documented", ""),
    ("F157", "UI", "Cloud render controls and backend chip",
     "As a user, I can configure cloud rendering and see whether a scene used local, cloud, or fallback rendering.",
     "SettingsDialog adds render mode, GitHub repo/token/workflow/branch, auto threshold, Get token, and Test cloud render controls. PipelineWorker streams backend progress via status; SimulationPanel shows a Local/Cloud/Local fallback chip from render diagnostics.",
     "ui/main_window.py / ui/workers.py / ui/widgets.py", "gui", "Documented", ""),
    ("F158", "Docs", "Cloud rendering workflow and setup guide",
     "As a user, I can create the render repo and understand permissions, privacy, and fallback behavior.",
     ".github/workflows/render.yml pins ubuntu-24.04, Python 3.14, manim==0.20.1, ffmpeg/cairo/pango, optional TeX, renders the committed scene, and uploads MP4/log artifacts. docs/CLOUD_RENDERING.md covers setup, permissions, modes, cache, privacy, parity, and failure behavior.",
     ".github/workflows/render.yml / docs/CLOUD_RENDERING.md", "static", "Documented", ""),
    ("F159", "UI", "Precision-instrument graphic redesign pass",
     "As a student, AetherLab feels like a calm, legible physics instrument rather than a generic dark app.",
     "The active QSS tightens the shell around 8px radii, bright-cyan primary focus, true-black stage/code surfaces, styled tabs/radio/progress controls, setup/library dashed states, scene toolbar, and canvas export button. Theme defaults now align QPainter/Manim palette with #22D3EE. Key widgets expose stable object names (AnalysisCard, SceneToolbar, SetupStrip, RunningStatusStrip, LibraryEmptyState, CanvasExportButton), and docs/UI_GRAPHIC_REDESIGN.md maps the brief to Qt implementation hooks.",
     "ui/style.py / ui/theme.py / ui/widgets.py / ui/live_canvas.py / docs/UI_GRAPHIC_REDESIGN.md", "gui", "Documented", ""),
    ("F160", "Quality", "Persisted scene quality score and cache threshold",
     "As a user, once AetherLab has judged a render's visual quality, that score follows the scene through cache reuse and can opt into regenerating low-quality cached cuts.",
     "SceneBundle stores quality_score, critique_verdict, and critique_issues. ManimRuntime.render_scene_with_repair copies the existing visual critic's score/verdict/issues onto the rendered SceneBundle. AppSettings.min_quality_score defaults to 0.0 (today's behavior); when set above zero, AetherLabPipeline and lesson chapter cache reuse reject cached scenes below the threshold and regenerate them instead.",
     "core/models.py / core/settings.py / services/manim_runtime.py / services/pipeline.py / services/lesson_pipeline.py", "headless", "Documented", ""),
    ("F161", "Quality", "Opt-in scene candidate tournament",
     "As a user with vision critique enabled, AetherLab can try several scene concepts and keep the strongest one instead of pinning the first valid render.",
     "AppSettings.scene_candidates defaults to 1, preserving the legacy single-shot path. When scene_candidates>1 and both an API key and vision_model are configured, ManimRuntime.generate_render_tournament generates seeded storyboards, implements each with the normal cold codegen pass, applies code-safety and scene-validation gates, draft-renders surviving candidates through the existing backend seam with bounded concurrency, scores each draft with scene_critic, drops failed/unscored candidates, chooses by score/fewer issues/duration-contract closeness, then re-renders only the winner through the existing repair/critique/final-quality path. Any error, N=1, or missing vision config falls back to today's single path.",
     "core/settings.py / services/scene_generator.py / services/manim_runtime.py / services/pipeline.py / services/lesson_pipeline.py / ui/workers.py", "headless", "Documented", ""),
    ("F162", "Quality", "Visual-regression quality gate (strict mode + regression flags)",
     "As a maintainer, my visual-regression run FAILS when a render comes out broken (empty, frozen, too short) or measurably worse than the baseline — not only when rendering crashes.",
     "tools/visual_regression.py records per-render metrics (duration, fps, blank/static spans, subtitle cues) but previously only failed on render crashes: quality 'warn' cases and baseline deltas never affected the exit code. Adds pure, unit-tested gate logic: quality_failures(case) returns hard violations (duration<2s, fps<5, blank span>0.5s, dominant static span, a lesson with zero subtitle cues); compare_report flags regressions vs. a baseline run (duration collapse >25%, blank/static-ratio increases) with a regression_count; and decide_exit(report, strict) fails on render crashes always, and additionally on quality violations, soft warnings, and regressions under the new --strict flag. Default (non-strict) behavior is unchanged.",
     "tools/visual_regression.py", "headless", "Documented", ""),
    ("F163", "Quality", "Domain-matched scene exemplars (few-shot codegen)",
     "As a user, generated scenes follow a proven, well-directed template for my problem's physics instead of the model improvising Manim API usage from prose alone.",
     "services/scene_exemplars.py ships four curated, Text-only (LaTeX-free) exemplar scenes — oscillator, pendulum, orbit, wave — built from scene_templates' render-proven vocabulary and verified to compile, pass code_safety, pass scene_validation, and render to MP4. exemplar_for()/exemplar_block() select one by scene_templates.detect_domain(keywords, variables) and format a few-shot block; SceneGenerator._generate_remote appends the domain-matched exemplar to the codegen system prompt (both the storyboard and single-call paths), truncation-safe since only the user message is budget-trimmed. Fail-soft: any selection error yields no exemplar and the prompt is unchanged. Reduces hallucinated-API render crashes and flat 'axes + one curve' compositions by showing, not just describing, a correct 3-beat scene.",
     "services/scene_exemplars.py / services/scene_generator.py", "headless", "Documented", ""),
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
        writer = csv.writer(fh, lineterminator="\n")
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
    "F148": "BUG-6: xfade chain double-subtracted the overlap (cum += durs[k]-d), drifting every later crossfade early and over-clipping produced-lesson segments.",
    "F147": "BUG-7: _chapter_aspect compared chapter .id (LLM plans default to ''), tagging every id-less chapter 'setup'; now compares by object identity.",
    "F143": "BUG-9: partial lesson renders compacted successful scenes, then zipped them against all renderable chapters; surviving clips could receive the wrong narration/title. Pipeline now carries plan indexes with rendered scenes.",
    "F145": "BUG-8/BUG-9: chapter-seek offsets use produced-video starts, and partial lessons map chapter offsets by plan index so skipped middle chapters do not mislabel surviving clips.",
    "F86": "BUG-10: compile_latex_to_pdf could return a stale PDF after a failed pdflatex run; it now removes stale output first and requires returncode 0 plus fresh output.",
    "F15": "BUG-11: pipeline cancellation did not explicitly clear the scene loading stack; it now calls SimulationPanel.hide_loading() during cancel.",
    "F103": "BUG-13: safety gate allowed string-based runtime escape helpers (`getattr(__builtins__, 'open')`, dunder strings); these handles are now blocked.",
    "F43": "BUG-14: incremental Chroma ingestion left stale chunks when a source file shrank or changed shape; changed files now delete old path chunks before upsert.",
    "F153": "BUG-19: legacy manim-bot .env and existing gh auth sessions were ignored; settings now migrate CLOUD_RENDER_* aliases and GitHub CLI tokens without exposing secrets.",
    "F154": "BUG-15: exact job_id polling prevents attaching to unrelated runs. BUG-17: bundled workflow is provisioned before dispatch/test. BUG-18: removed setup-python cache:pip failure. BUG-20: artifact 302 downloads drop the Bearer header on the signed URL.",
    "F160": "BUG-16: visual critique score/verdict/issues were not persisted, so cached low-quality renders could be pinned; SceneBundle now stores them and min_quality_score can reject low-score cache.",
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
