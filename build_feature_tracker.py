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
  Source File(s) · Feature test method · Status · Notes · Story · Persona ·
  Expected behaviour · Failure-mode expectation · Test method · Phase-2 result ·
  Errors found · Phase-4 result

Status vocabulary: Documented · PASS · FAIL · PARTIAL · FIXED
Feature test method: headless (import+run) · static (source assertion) · gui (manual)
Story Test method:   harness · scripted-ui · manual · live-cloud
"""

from __future__ import annotations

import ast
import csv
import re
from functools import lru_cache
from pathlib import Path

# fmt: off
# (ID, Category, Feature, User Story, Expected Behavior, Sources, TestMethod, Status, Notes)
FEATURES: list[tuple[str, ...]] = [
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
     "load_settings() reads AETHERLAB_DATA_DIR/CACHE_PATH/CHROMA_PATH/LIBRARY_DIR, provider fields, and bounded LLM controls (`llm_timeout_seconds` via AETHERLAB_LLM_TIMEOUT, 5–900s; `llm_max_retries` via AETHERLAB_LLM_MAX_RETRIES, 0–1; both persisted in app config). Every asynchronous OpenAI-compatible client uses the same effective policy, so SDK retries cannot multiply a slow call. Compatible manim-bot aliases and a legacy .env can fill still-unset fields unless disabled.",
     "core/settings.py", "headless", "Documented", ""),
    ("F07", "Settings", "App-config persistence (settings.json)",
     "As a user, values I save in the Settings dialog survive restarts.",
     "save_app_config writes data_dir/settings.json (drops empty/None); load_app_config reads it; feeds load_settings. app_config_path honors AETHERLAB_DATA_DIR.",
     "core/settings.py", "headless", "Documented", ""),
    ("F08", "Settings", "Provider precedence: env > app-config > qwen",
     "As a user, explicit env vars win over saved config, which wins over the legacy Qwen file.",
     "load_settings resolves model/api_key/base_url in that order; provider_source labels the winning tier, api_key_source names the exact credential source, and provider_warning reports when an environment key shadows the saved key without exposing either value.",
     "core/settings.py", "headless", "Documented", ""),
    ("F09", "Settings", "Qwen ~/.qwen/settings.json opt-in loader",
     "As a Qwen Code user, I can intentionally reuse my provider settings.",
     "load_qwen_settings extracts model name, base URL, and api key (via envKey/env) without logging secrets; returns {} if absent/corrupt. load_settings only applies it when AETHERLAB_QWEN_AUTOLOAD=1 so student installs do not silently inherit unrelated credentials.",
     "core/settings.py", "headless", "Documented", ""),
    ("F10", "Settings", "Settings dialog (Ctrl+,/gear)",
     "As a user, I open Settings to edit provider, rendering, and paths.",
     "SettingsDialog shows the active provider/model and exact API-key source, warns when env shadows saved config, and never copies an active environment key into the editable field. It exposes bounded model timeout and retry choices ('No automatic retries' / 'Retry once') plus provider/render/path fields in a scrollable screen-fitted form. Save persists then reloads through load_settings so in-memory behavior follows restart precedence.",
     "ui/main_window.py (SettingsDialog) / ui/provider_status.py", "gui", "Documented", ""),
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
     "QualityCombo maps Draft (480p), Standard (720p · 30 fps), and High (1080p) → l/m/h via get_render_quality; set_quality selects by flag (Settings default).",
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
     "worker.cancel() sets a flag; _check_cancelled between stages raises _PipelineCancelled. UI stays visibly busy with repeat Cancel disabled until QThread.finished, then restores ready state and shows the cancellation toast.",
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
     "closeEvent cancels workers and waits up to 5s; if any still runs, it ignores that close event and retries from finished instead of destroying a live QThread.",
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
    ("F34", "Cache", "Video re-render on missing/unplayable file",
     "As a user, a deleted or corrupted cached video re-renders automatically.",
     "A 'rendered' scene whose video_path is missing, empty, or unplayable is re-rendered; playable-video validation covers compiled and stale rendered scenes.",
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
    ("F44", "Library", "Library sources: Books 7–11 and ENT mock sets",
     "As a student, I can distinguish Books 7–11 used as references from ENT mock sets used for practice.",
     "LibraryPanel lists .pdf/.txt/.md/.tex with size and index freshness, and separates Books 7–11 from ENT mock sets in the source picker; empty state offers Add textbooks / Get starter library.",
     "ui/library_panel.py (LibraryPanel)", "gui", "Documented", ""),
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
     "As a user, each step is a collapsible card; I can Show hints, Reveal worked step, expand/collapse all, and copy.",
     "_CollapsibleStepWidget toggles body on header click; Show hints expands steps; Reveal worked step opens its evidence; Copy copies summary+steps; per-step copy.",
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
    ("F77", "Navigation", "Keep Lab destination available before a solve",
     "As a user, I can open the Lab workspace before or after producing a result.",
     "SidebarNav.set_result_available keeps the Lab destination enabled while solver availability changes.",
     "ui/navigation.py (SidebarNav) / main_window.py", "static", "Documented", ""),
    ("F78", "Navigation", "Open Lab when a scene is ready",
     "As a user, the completed scene opens in the Lab workspace.",
     "on_scene_ready hides loading, sets the scene, and calls sidebar.select(7).",
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
     "As a user, the app has a cohesive blue-graphite theme with a sky-blue accent.",
     "AETHERLAB_QSS styles the whole shell with blue-graphite surfaces and accent #60A5FA.",
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
     "scene_validation checks unknown Manim names, provably-invalid kwargs, malformed LaTeX, duration, and (for remote generated/revised code) an obvious-motion contract. SceneGenerator token-repairs unknown color-like constants such as GREEN_SCREEN/BROWN without touching strings/comments/defined names. Generation/repair/revision gates require .animate/Transform/updater evolution; prompt rules enumerate the safe palette, require visible motion in every act and differing final sampled frames, and require every requested on-screen element.",
     "services/scene_validation.py / manim_runtime.py", "headless", "Documented", ""),
    ("F107", "Scene", "Storyboard→codegen split (two-call generation)",
     "As a user, my scene is first *directed* (creative treatment), then *implemented* — not improvised in one shot.",
     "SceneGenerator.storyboard() runs a hot directing pass (temp 0.9); _generate_remote implements the locked storyboard cold (temp 0.15). Any storyboard failure fails soft to single-call generation. For hybrid Qwen 3.5/3.6/3.7 plus/max/flash models, every non-streaming SceneGenerator request explicitly sets enable_thinking=false to prevent default-on reasoning from consuming the bounded codegen timeout; thinking-only models remain bounded and Settings recommends qwen3-coder-plus.",
     "services/scene_generator.py / core/models.py / manim_runtime.py", "headless", "Documented", ""),
    ("F108", "Render", "Perceptual critique loop (VLM watches the video)",
     "As a user with a vision model configured, rendered videos are actually *watched* and revised until they pass a quality rubric.",
     "scene_critic samples frames uniformly, sends them + the storyboard/brief to settings.vision_model, and returns ship/revise + score + issues. Model JSON gets a conservative recovery pass before fail-soft skip. `visual_critic_max_passes` bounds SceneGenerator.revise()/repair rounds and `visual_critic_keyframes` controls sampling; failed static/trial-render revisions get one targeted repair, and only a successfully rendered revision replaces the prior cut. No vision model → skipped.",
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
    ("F113", "Canvas", "Viewport-independent sample cache + discontinuity-safe branches",
     "As a user, zooming is instant (no recompute) and asymptotes render as separate arms instead of a false bridge.",
     "Curve samples (t, xs, ys) are cached keyed by (params, t_range, t_steps) only — zoom/pan never rebuilds them; the data-to-pixel affine map is re-applied per paint with vectorized numpy into QPolygonF via the sip buffer (no per-point Python loops). Non-finite and extreme off-screen samples split polylines into finite runs (>=2 points), so 1/t and finite-valued tan(t) asymptotes draw separate branches without false chords.",
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
    ("F119", "Design v2", "Student app palette tokens and 74px rail",
     "As a user, the app has blue-graphite surfaces, a sky-blue accent, and a labeled navigation rail.",
     "style.py defines CYAN #60A5FA, CYAN_DEEP #3B82F6, STAGE #0B1220, ELEV #1A2A41, HOVER_SURFACE #20324A, and LINE_0 #172338; the canvas and Theme accent track CYAN. SidebarNav uses a 74px labeled rail.",
     "ui/style.py / ui/live_canvas.py / ui/widgets.py", "static", "Documented", ""),
    ("F120", "Design v2", "Math typesetting service (formulas-as-brand)",
     "As a user, equations render as real typeset math, not ASCII.",
     "services/mathtext.py renders a LaTeX subset via matplotlib mathtext (STIX fonts) to transparent 2x QPixmaps, cached and never-raising (bad input → None → text fallback). Provides a parameter symbol map (damping→ζ, omega0→ω₀, …), a math/prose discriminator, unicode→LaTeX cleanup, and the ambient watermark formula set.",
     "services/mathtext.py", "headless", "Documented", ""),
    ("F121", "Design v2", "Hero equation, parameter symbols, and Open practice entry",
     "As a user, the derivation leads with a typeset equation, parameters show their symbols, and the empty state offers Open practice.",
     "AnalysisPanel typesets a math summary into the banner pixmap (prose stays styled text); ParameterDock renders row symbols with a text fallback; EmptyStateView includes the ENT Open practice card and setup strip.",
     "ui/analysis_panel.py / ui/parameter_dock.py / ui/shared_widgets.py / services/mathtext.py", "gui", "Documented", ""),
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
     "pipeline._merge_web_references runs the provider via asyncio.to_thread under asyncio.wait_for, keeps library hits first, appends web hits, and tags the backend '<local>+web'. Any error (or the settings toggle off) returns the original RagResult untouched. Wired into both the headless pipeline and the Qt worker (with a status line). Governed by AppSettings.web_references (Settings checkbox 'Pull web references (Wikipedia) alongside the local library', env AETHERLAB_WEB_REFS / app config, default on) + web_ref_timeout.",
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
     "services/providers.py: detect_ollama (GET /api/tags, 2s, never raises) and test_connection (1-token chat ping, always returns displayable (ok,msg)). SettingsDialog gains a preset combo (Custom endpoint/Ollama/No AI (offline)) that autofills fields and lists installed models, plus a Test-connection button. MainWindow probes Ollama in a background QThread when keyless; EmptyStateView shows a 'Use local AI (Ollama)' CTA whose click persists the preset and reloads settings with a success toast.",
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
     "core/proc.subprocess_kwargs() keeps Windows creationflags off POSIX. Every text-capturing subprocess specifies UTF-8 with replacement, every Path/open text call specifies an encoding, and print-producing CLI entry points call core.console.configure_utf8_stdio so redirected legacy-code-page streams cannot raise. F133 performs an AST audit across aetherlab, tools, packaging, the tracker builder, watchdog, and feature harness instead of relying on a hand-maintained call-site list.",
     "core/proc.py / core/console.py / services/ / ui/ / tools/ / packaging/", "headless", "Documented", ""),
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
     "AppSettings.narration_enabled/tts_voice/tts_rate resolved from env (AETHERLAB_NARRATION/AETHERLAB_TTS_*, plus manim-bot VOICEOVER_ENABLED/TTS_ENABLED/TTS_VOICE/TTS_RATE aliases) then app-config (default off). SettingsDialog gains a NARRATION section with the checkbox label 'Add a voiceover fit to the rendered video' plus a voice field, persisted via save_app_config. Old cache rows keep working (silent_video_path defaults to '').",
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
     "CommandBar gains a Learn button (emits learn_requested(topic); hidden while busy). MainWindow.start_lesson runs LessonWorker (QThread → progress/lesson_ready/failure), shows the running view, then on_lesson_ready populates LessonView (workspace PAGE_LESSON=6) and loads the assembled lesson.mp4 into its INLINE player. LessonView tabs: Video (QMediaPlayer, play/pause/stop, guarded if QtMultimedia absent) + Transcript + Questions (_QuestionCard MCQ with ✓/✗ feedback + why; Reveal answer button) + References. The chapter outline click seeks the inline player to the chapter start and shows the Video tab (chapter_seek_requested), using rendered_chapter_indexes to keep partial lessons aligned when a middle chapter failed. A 'Play with it' tab embeds a LiveCanvas seeded from the lesson's domain (detect_domain → params) with the interactive chapter's guiding prompt, completing the pedagogy loop. Export-study-guide → pdf.export_lesson_study_guide. closeEvent waits on the lesson worker. Validated end-to-end: a keyless 'Kepler orbit' lesson renders 4 chapters and assembles a 21.9s lesson.mp4 + .srt in ~52s.",
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
     "AppSettings adds render_mode, cloud_provider, github_repo/token/workflow/branch, github_oauth_client_id, cloud threshold, poll seconds, and cloud timeout with env > app-config precedence. It accepts manim-bot CLOUD_RENDER_ENABLED/REPO/WORKFLOW/BRANCH/TIMEOUT/POLL aliases from env or a legacy .env fallback; CLOUD_RENDER_ENABLED=true maps to AetherLab auto mode unless AETHERLAB_RENDER_MODE is explicit. SettingsDialog persists the fields; default render_mode='local' preserves current behavior.",
     "core/settings.py / ui/main_window.py", "headless", "Documented", ""),
    ("F154", "Render", "GitHub Actions cloud backend",
     "As a user, heavy scenes can render on a Linux GitHub Actions runner and return as a normal SceneBundle.",
     "CloudRenderBackend scans for secrets, computes a content job id from scene/code/quality/fps/manim pin, provisions the render workflow, commits jobs/<job_id>.py, dispatches workflow_dispatch, polls the run, follows signed artifact/log redirects without leaking GitHub auth to storage, downloads/validates the MP4 artifact into the local isolated render dir, and records a manifest so identical scenes reuse artifacts instead of re-dispatching. GitHub auth can come from Settings/env or an existing `gh auth login` token.",
     "services/render_backend.py / .github/workflows/render.yml", "headless", "Documented", ""),
    ("F155", "Render", "Cloud fail-soft local fallback",
     "As a user, missing token/network/CI never crashes a solve; AetherLab just renders locally.",
     "Missing configuration/network or an exhausted adaptive cloud poll budget returns an internal cloud-unavailable SceneBundle status; ManimRuntime._render_once restores compiled status and invokes LocalRenderBackend. Timed-out Actions runs are cancelled best-effort first. Successful fallback preserves a clear diagnostic and MainWindow warning.",
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
     ".github/workflows/render.yml pins ubuntu-24.04, Python 3.14, manim==0.21.0 and render dependencies; uploads only one exact final scene MP4, excludes fragments, and fails for missing or ambiguous matches. The bundled worker matches the shipped workflow. docs/CLOUD_RENDERING.md covers setup, permissions, modes, cache, privacy and failure behavior.",
     ".github/workflows/render.yml / docs/CLOUD_RENDERING.md / tests/test_cloud_output_identity.py", "headless", "Documented", ""),
    ("F159", "UI", "Precision-instrument graphic redesign pass",
     "As a student, AetherLab feels calm and legible, with blue-graphite surfaces and a consistent sky-blue accent.",
     "The active QSS uses blue-graphite surfaces, sky-blue primary focus, styled tabs/radio/progress controls, setup/library cards, scene toolbar, and canvas export button. Theme defaults align QPainter and scene colors with #60A5FA. Stable object names support UI checks without changing the design.",
     "ui/style.py / ui/theme.py / ui/shared_widgets.py / ui/simulation_panel.py / ui/live_canvas.py", "gui", "Documented", ""),
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
     "tools/visual_regression.py records per-render metrics (duration, fps, blank/static spans, subtitle cues) but previously only failed on render crashes: quality 'warn' cases and baseline deltas never affected the exit code. Adds pure, unit-tested gate logic: quality_failures(case) returns hard violations (duration<2s, fps<5, sustained blank span, dominant static span, a lesson with zero subtitle cues); compare_report flags duration collapse >25% and normalized blank/static-ratio increases when clip durations are comparable; decide_exit(report, strict) fails on render crashes always, and additionally on quality violations, soft warnings, and comparable-baseline regressions under --strict. Default (non-strict) behavior is unchanged.",
     "tools/visual_regression.py", "headless", "Documented", ""),
    ("F163", "Quality", "Domain-matched scene exemplars (few-shot codegen)",
     "As a user, generated scenes follow a proven, well-directed template for my problem's physics instead of the model improvising Manim API usage from prose alone.",
     "services/scene_exemplars.py ships four curated, Text-only (LaTeX-free) exemplar scenes — oscillator, pendulum, orbit, wave — built from scene_templates' render-proven vocabulary and verified to compile, pass code_safety, pass scene_validation, and render to MP4. exemplar_for()/exemplar_block() select one by scene_templates.detect_domain(keywords, variables) and format a few-shot block; SceneGenerator._generate_remote appends the domain-matched exemplar to the codegen system prompt (both the storyboard and single-call paths), truncation-safe since only the user message is budget-trimmed. Fail-soft: any selection error yields no exemplar and the prompt is unchanged. Reduces hallucinated-API render crashes and flat 'axes + one curve' compositions by showing, not just describing, a correct 3-beat scene.",
     "services/scene_exemplars.py / services/scene_generator.py", "headless", "Documented", ""),
    ("F164", "Quality", "Feature-surface tracker coverage audit",
     "As a maintainer, when the app gains a visible control, CLI flag, or user-configurable setting, the canonical tracker must name it and keep its expected behavior testable.",
     "tools/feature_surface_audit.py parses aetherlab/**/*.py for argparse --flags, AppSettings fields, QPushButton/QCheckBox labels, menu actions, and combo items, then checks each non-generic surface against AetherLab_Feature_Tracker.csv. `python tools/feature_surface_audit.py --check` exits non-zero on uncovered surfaces; --json emits the matched feature IDs. This turns 'every single feature is tracked' into a repeatable audit gate.",
     "tools/feature_surface_audit.py / AetherLab_Feature_Tracker.csv", "headless", "Documented", ""),
    ("F165", "Quality", "Canonical tracker artifact integrity audit",
     "As a maintainer, the generated spreadsheet, CSV, feature-test results, test functions, and defect ledger must agree before I trust the audit status.",
     "tools/tracker_integrity_audit.py imports build_feature_tracker.py, applies feature_test_results.json, and verifies the CSV and XLSX match the generator exactly; feature IDs are unique/contiguous; every row has a user story and expected behavior; statuses/test methods are valid; feature_test_results.json and t_fXX definitions exactly match tracker IDs; DEFECTS entries point to known features marked FIXED; and all DEFECTS bug IDs are documented in ERRORS_FOUND.md. `python tools/tracker_integrity_audit.py --check` exits non-zero on drift.",
     "tools/tracker_integrity_audit.py / build_feature_tracker.py / feature_test_results.json / ERRORS_FOUND.md", "headless", "Documented", ""),
    ("F166", "Export", "Lesson share bundle export",
     "As a student or teacher, I export a completed lesson as one portable package I can hand off or open offline.",
     "services/share_export.export_lesson_bundle writes a ZIP containing index.html, metadata.json, README.txt, study_guide.tex, media/lesson.mp4, subtitles as SRT plus browser-friendly VTT when available, and per-chapter Manim source files. The metadata is share-safe (relative asset names, no API keys, no app config, no absolute local paths). LessonView exposes an Export bundle button, wired through MainWindow to a ZIP save dialog with status feedback.",
     "services/share_export.py / ui/widgets.py / ui/main_window.py / docs/LESSON_SHARE_EXPORT.md", "headless", "Documented", ""),
    ("F167", "Course", "Course progress from lesson quizzes",
     "As a student, I can use the Submit answer control on lesson quizzes, answer due multiple-choice reviews before feedback, keep open-response recall self-rated, and see my progress shape review recommendations.",
     "services/course_mode.CourseProgressStore persists quiz attempts to data_dir/course_progress.json keyed by lesson topic+audience, with per-question correctness, last choice, concept, and timestamp. LessonView question cards emit graded multiple-choice answers; MainWindow records them and updates a course status strip with score plus a recommended next topic. Review due questions brings missed or low-confidence concepts back on a spaced schedule. Due MCQ reviews require an answer before feedback and record objective correctness; open responses remain explicitly self-reported. Evaluation events retain response mode and days since first attempt without exporting the answer or selected choice. tools/learner_study_analysis.py computes aggregate due-return and day-1/day-7 recall measures, keeping objective accuracy separate from self-reported recall, and can aggregate separately scored novel-transfer rows from an optional CSV; no learner or transfer data has been collected yet. Each quiz card has a Confidence selector (Confidence: low / Confidence: medium / Confidence: high); a low-confidence correct answer returns at the first interval without advancing the mastery streak. The review schedule is the review_intervals_days setting, edited in Settings > Learning with presets 1,3,7,14 / 1,2,4,8 / 1,7,14 / 1 (up to eight intervals of 1-365 days). Wrong answers recommend the mapped objective; clean scores recommend a domain-appropriate follow-up. docs/COURSE_MODE.md documents the local-only scope and privacy boundary.",
     "services/course_mode.py / ui/widgets.py / ui/main_window.py / docs/COURSE_MODE.md", "headless", "Documented", ""),
    ("F168", "Quality", "Prompt Quality Lab reports",
     "As a maintainer improving prompts, I can measure whether scene and lesson generations got better across canonical physics tasks.",
     "tools/prompt_quality_lab.py defines six canonical prompts (pendulum, Kepler orbit, standing wave, Fourier series, E&M field, and Kepler lesson mode), renders them through the real local pipeline, reuses visual_regression audit metrics/contact sheets, records storyboard presence/act count plus persisted critic score/verdict/issues, writes summary.json/summary.md/scores.csv under an ignored .analysis run directory, and compares against a previous report for score drops or duration collapse. docs/PROMPT_QUALITY_LAB.md documents safe provider mode and report interpretation.",
     "tools/prompt_quality_lab.py / docs/PROMPT_QUALITY_LAB.md", "headless", "Documented", ""),
    ("F169", "Quality", "Quality flywheel gate (golden-set ratchet)",
     "As a maintainer, a release cannot silently lower scene/lesson quality: a committed golden-set baseline gates every run.",
     "tools/prompt_quality_lab.py expands the canonical prompt set to a 12-prompt golden set spanning mechanics/waves/fields/orbital plus a lesson, all renderable keyless so the baseline is reproducible. evaluate_gate() is a pure ratchet: it fails (CLI exit 2) when a run's mean score drops beyond --score-tolerance (render-noise headroom, default 0.5) or the render pass rate drops at all vs the committed tools/prompt_quality_baseline.json. --gate/--baseline/--score-tolerance wire it into the CLI so it can guard later Quality-Flywheel phases. Phase 0 of docs/QUALITY_FLYWHEEL_MISSION.md.",
     "tools/prompt_quality_lab.py / tools/prompt_quality_baseline.json / docs/QUALITY_FLYWHEEL_MISSION.md", "headless", "Documented", ""),
    ("F170", "Quality", "Per-axis critic rubric + no-vision fallback",
     "As a maintainer, the visual critic scores each render on five explicit axes so candidates can be ranked and losers can be diagnosed — even with no vision model.",
     "services/scene_critic.py defines CRITIC_AXES (legibility/composition/palette/structure/substance, 0-2 each = 0-10). CRITIC_SYSTEM_PROMPT requests a per-axis breakdown; critique_video parses it via _coerce_breakdown, which validates against the fixed schema and — rather than silently zeroing malformed LLM output (the BUG-7 lesson) — spreads a valid aggregate score evenly and flags it vision-approx. static_quality_estimate() maps the scene_validation static battery (+ optional visual-regression metrics) onto the same axes for a deterministic, discriminating keyless proxy (verdict stays skipped). SceneBundle persists critique_breakdown backward-compatibly; all three manim_runtime copy sites propagate it and the tournament ranks keyless candidates by the static proxy instead of dropping them. prompt_quality_lab surfaces the breakdown without changing the gated score. Phase 1 of docs/QUALITY_FLYWHEEL_MISSION.md.",
     "services/scene_critic.py / core/models.py / services/manim_runtime.py / tools/prompt_quality_lab.py", "headless", "Documented", ""),
    ("F171", "Quality", "Parallel cloud fan-out with per-candidate isolation",
     "As a power user with cloud rendering, when the tournament renders N candidates, I expect them to render concurrently on the farm without stealing each other's artifacts.",
     "manim_runtime._render_and_score_candidates fans candidates out through the cloud backend with a per-candidate variant salt, so byte-identical scenes keep distinct job paths/artifacts while the empty variant preserves single-scene cache keys. Because those distinct files still commit to one branch tip, GitHubActionsClient serializes Contents API writes per repository/branch and retries HTTP 409 conflicts with bounded backoff. Keyless candidates still use the static proxy; tools/cloud_tournament_smoke.py remains the live end-to-end check.",
     "services/render_backend.py / services/manim_runtime.py / tools/cloud_tournament_smoke.py", "headless", "Documented", ""),
    ("F172", "Quality", "Aesthetic pitfall learning (losers teach)",
     "As a maintainer, when the critic keeps naming the same visual problems, I expect the next generation to actively avoid them.",
     "error_learner.AestheticPitfallStore is a JSON-backed, TTL-pruned, fail-soft tally of normalized critic issue phrases (numbers/paths/axis-tags stripped so variants cluster). learned_aesthetic_block() renders the top offenders and preventive_pitfalls_block(store) appends them to the generation system prompt; preventive_pitfalls_block() with no store stays the static block (backward compatible). scene_generator._generate_remote builds the store from data_dir and injects it at both codegen sites; manim_runtime.generate_render_tournament records the LOSING candidates' critic issues via _record_aesthetic_pitfalls after selecting the winner. Phase 3 of docs/QUALITY_FLYWHEEL_MISSION.md — the flywheel's cross-run learning.",
     "services/error_learner.py / services/scene_generator.py / services/manim_runtime.py", "headless", "Documented", ""),
    ("F173", "Quality", "Exemplar promotion (winners teach)",
     "As a maintainer, when a tournament produces a critic-approved, high-scoring winner, I expect it stashed as an exemplar candidate I can review and promote — never auto-injected.",
     "scene_exemplars.ExemplarCandidateStore (data-dir JSON, fail-soft) records a tournament winner only when the VISION critic returned verdict 'ship' at score >= PROMOTE_MIN_SCORE (8.5); static-proxy/skipped, 'revise', low-score, and empty-code winners are rejected, and identical code deduplicates. manim_runtime.generate_render_tournament records the winner via _record_exemplar_candidate (domain from detect_domain). tools/promote_exemplar.py lists candidates and emits a paste-ready snippet but NEVER writes scene_exemplars.py — promotion into the curated EXEMPLARS is a deliberate human-reviewed code change (feeding LLM code back into every prompt is a supply-chain risk). Phase 3 of docs/QUALITY_FLYWHEEL_MISSION.md.",
     "services/scene_exemplars.py / services/manim_runtime.py / tools/promote_exemplar.py", "headless", "Documented", ""),
    ("F174", "Quality", "Cheap-first tournament escalation",
     "As a power user, I expect the tournament to spend compute only when it helps: one render first, more candidates only if that render is weak and the scene is hard.",
     "manim_runtime.storyboard_difficulty() scores a storyboard 0..1 from its acts/beats/duration; candidate_budget() truncates that to a conservative candidate count in [1, cap] (cap = min(scene_candidates, 8)). generate_render_tournament renders ONE candidate first, computes the budget from its storyboard, and fans out the remaining budget concurrently ONLY when the first render scores below ESCALATE_BELOW_SCORE (8.0) AND the budget allows — so an easy or already-good scene costs one render while a hard, weak one escalates. _build_scene_candidates gained count/start_index so batches preserve absolute indices (temperature diversity + per-candidate cloud variant). Phase 4 of docs/QUALITY_FLYWHEEL_MISSION.md.",
     "services/manim_runtime.py", "headless", "Documented", ""),
    ("F175", "Quality", "Render-farm job/candidate ledger",
     "As a power user, I expect a persisted, secret-scrubbed ledger of render jobs and tournaments — what queued, ran, failed, downloaded, or fell back — so cloud rendering is debuggable.",
     "services/render_ledger.RenderJobLedger is a JSON-backed, fail-soft, standard-library ledger under data_dir/render_ledger.json. It records a status timeline (queued/in_progress/completed/failed/cancelled/rate_limited/artifact_downloaded/fallback_local/rendered), per-candidate critic scores + the winner index, sanitized failure log tails, fallback reason and final path, capped to the most recent jobs. scrub() redacts GitHub/OpenAI/Slack tokens, bearer tokens, private keys, and api_key/secret assignments from every persisted free-text field. generate_render_tournament records the tournament (candidates + winner + backend); CloudRenderBackend.render records the cloud lifecycle (queued->in_progress->failed-with-log/timeout->artifact_downloaded->rendered); manim_runtime._render_once records the cloud->local fallback against the same job id. Phase 5 of docs/QUALITY_FLYWHEEL_MISSION.md.",
     "services/render_ledger.py / services/render_backend.py / services/manim_runtime.py", "headless", "Documented", ""),
    ("F176", "Quality", "Render-farm dashboard panel",
     "As a power user, I open a render-farm dashboard to see each job's status, per-candidate scores, the winner, sanitized failures, and any local fallback.",
     "ui/ledger_panel.RenderLedgerPanel is a self-contained read-only widget (its own module, not widgets.py) that lists render-ledger jobs and, per job, shows the status timeline, per-candidate critic scores with the winner highlighted, the sanitized failure log tail, and the local-fallback reason/output path. It reads services/render_ledger (already scrubbed at write time), shows an empty state when there are no jobs, and never crashes on a missing/corrupt ledger. SettingsDialog exposes it via a 'View render ledger' button in the cloud row (_open_render_ledger opens it in a dialog). docs/CLOUD_RENDERING.md explains debugging cloud renders from the dashboard. Phase 5 of docs/QUALITY_FLYWHEEL_MISSION.md.",
     "ui/ledger_panel.py / ui/main_window.py", "gui", "Documented", ""),
    ("F177", "Quality", "Multi-candidate quality default-on (configured critics)",
     "As a user with a vision critic configured, I get the multi-candidate quality loop automatically — no extra clicks — while keyless/offline stays exactly as fast.",
     "core/settings.auto_tournament (bool, default True; env AETHERLAB_AUTO_TOURNAMENT + app-config, round-trips through the Settings dialog). manim_runtime.effective_candidate_cap() returns the effective cap: an explicit scene_candidates>1 wins; else, when a vision critic (api key + vision model) is configured and auto_tournament is on, it defaults to AUTO_TOURNAMENT_CAP (3); else 1. scene_tournament_enabled() now gates on a critic AND effective_candidate_cap>1, so configured users get the tournament by default and keyless/offline resolves to a single render, exactly as fast. Phase-4 escalation keeps the typical configured cost at one render. The Settings toggle 'Multi-candidate quality (auto): render extra takes only when the first is weak' opts out. Phase 6 (final) of docs/QUALITY_FLYWHEEL_MISSION.md.",
     "core/settings.py / services/manim_runtime.py / ui/main_window.py", "headless", "Documented", ""),
    ("F178", "Quality", "Global local-render concurrency bound",
     "As a user rendering lessons with the tournament on, I expect AetherLab not to thrash my machine with unbounded simultaneous local renders.",
     "render_backend defines a process-wide LOCAL_RENDER_LIMIT (default max(1, min(4, cpu//2)); override via AETHERLAB_LOCAL_RENDER_LIMIT) and a threading (loop-agnostic) semaphore _LOCAL_RENDER_SEM acquired inside LocalRenderBackend.render's worker thread. Lessons render chapters concurrently (lesson_pipeline max_concurrent) and each chapter's tournament renders candidates concurrently (scene_candidate_concurrency), so the nesting would otherwise multiply into many CPU-bound Manim subprocesses at once — thrashing the machine and risking render timeouts. The bound caps total concurrent LOCAL renders globally; cloud renders are I/O-bound and intentionally not bounded here.",
     "services/render_backend.py", "headless", "Documented", ""),
    ("F179", "Quality", "Semantic exemplar retrieval (embeddings)",
     "As a user, I expect AetherLab to reuse a past proven-good scene when I ask about a semantically-similar problem — even if the wording differs.",
     "services/embeddings.py is a fail-soft, offline local text-embedding leaf that reuses ChromaDB's bundled all-MiniLM model (already a [rag] dependency; no new hard dep) to turn text into unit vectors where cosine similarity == semantic similarity; it degrades to unavailable (None) so callers keep their non-semantic fallback and numpy is the only hard requirement. ExemplarCandidateStore.record now embeds the winning scene's query_text and retrieve() returns the stored winner whose embedding is cosine-nearest above RETRIEVE_MIN_SIM; exemplar_block(data_dir=...) appends that retrieved winner as a second few-shot example so the model imitates a scene that already scored highly on a similar problem (keyword matching, e.g. detect_domain, cannot connect 'escape velocity' to a stored 'kepler orbit' winner — embeddings can). This makes the flywheel's F173 'winners teach' channel a LIVE retrieval source, not just a manual-promotion queue. Fully fail-soft: no model or empty store leaves generation exactly as before, and the deterministic keyless template path is untouched.",
     "services/embeddings.py / services/scene_exemplars.py / services/scene_generator.py", "headless", "Documented", ""),
    ("F180", "Quality", "Tournament A/B quality harness",
     "As a maintainer, I can measure whether the multi-candidate tournament actually produces better scenes, not merely that it never regresses the keyless floor.",
     "tools/prompt_quality_lab.py --ab runs the 12-prompt golden set twice - tournament forced ON (AETHERLAB_AUTO_TOURNAMENT=1) and OFF (=0) - in fresh, isolated per-arm data dirs, so neither the other arm nor a prior A/B run can leak cached output, exemplars or ledger candidates into the comparison. pair_ab_reports() pairs runs by prompt id into a lift summary: per-prompt delta, mean lift, win/tie/loss (0.05 noise band), and extra-render cost. With --allow-provider it validates real vision coverage for every solve in both arms, real vision scores for every ON-arm tournament candidate, matching prompt IDs, passing cases, and at least one extra candidate render before marking the measurement VALID; otherwise the numeric lift is explicitly exploratory and the CLI exits 2. Keyless reports remain clearly labelled as not a provider measurement. ab_summary.json/.md include coverage evidence and never persist secrets. Phase A of the 'Prove It' mission.",
     "tools/prompt_quality_lab.py", "headless", "Documented", ""),
    ("F181", "Quality", "Render-ledger flywheel report",
     "As a maintainer, I can mine the render ledger the tournament has been silently accumulating to see if the fan-out is worth its cost and whether the cheap draft score predicts the shipped HQ quality.",
     "The tournament now records, per solve, the storyboard difficulty and candidate budget that governed the fan-out and - after the repair loop re-critiques the winner at HQ - the winner's FINAL HQ score (render_ledger gains difficulty/budget/winner_hq_score/winner_hq_verdict; manim_runtime records them via _record_tournament_hq against the same job the draft scores were logged under). tools/ledger_report.py (read-only, stdlib-only, fail-soft) aggregates: escalation rate, candidate histogram, winner MARGIN over the runner-up (is the fan-out worth it, or do winners barely edge the losers?), the draft-to-HQ Pearson correlation and mean bias (does the 480p proxy predict the 1080p critic - the BUG-31 concern, now measured), spend by difficulty bucket, the weakest rubric axis (a losers-teach target), and fallback/failure rates. summarize_ledger() is a pure function and a missing/corrupt ledger yields an empty report, never a crash. Phase B of the 'Prove It' mission.",
     "services/render_ledger.py / services/manim_runtime.py / tools/ledger_report.py", "headless", "Documented", ""),
    ("F182", "Quality", "Learned keyless quality proxy",
     "As a keyless/offline user, I get scene ranking calibrated by real keyed outcomes, with no new dependency and no change at all until a reviewed model ships.",
     "The keyless static proxy (scene_critic.static_quality_estimate) historically scored a scene by SUMMING its five axis estimates (equal weight). tools/train_quality_proxy.py mines the render ledger's (winner draft axis breakdown -> winner HQ critic score) pairs and fits a numpy ridge regression (the project's one hard math dep) to learn per-axis weights, writing them to a reviewable tools/quality_proxy_model.json. scene_critic._load_quality_proxy() picks that model up (cached, fail-soft) and _proxy_score() applies the learned weights + intercept (clamped 0-10) instead of the equal-weight sum. Crucially the model is DATA, not code, committed only after human review (supply-chain safety, like curated exemplars): absent a model file the keyless score is byte-identical to the old sum, so the committed --gate baseline cannot move underneath anyone. collect_pairs()/fit_quality_proxy() are pure and deterministically unit-tested (they recover known weights at R^2 ~= 1). Phase C of the 'Prove It' mission.",
     "services/scene_critic.py / tools/train_quality_proxy.py", "headless", "Documented", ""),

    # ── Redesign: planner-first / numeric-grounded / self-verifying pipeline ──
    ("F183", "Planner", "Prompt-to-modality routing",
     "As a user, each problem only produces the outputs it actually needs.",
     "Planner.plan() returns a LessonPlan{needs_numeric,needs_2d,needs_3d,needs_animation,needs_pdf,rationale} via one strict-JSON LLM call; the heuristic classifier routes 'explain X conceptually' to pdf-only, dynamics prompts to numeric+2d+animation, and 3-D field prompts to needs_3d. LessonPlan round-trips through JSON.",
     "services/planner.py / core/models.py", "headless", "Documented", ""),
    ("F184", "Planner", "Conditional pipeline (skip unplanned stages)",
     "As a user, conceptual questions return fast instead of rendering a needless video.",
     "AetherLabPipeline.run() and PipelineWorker gate scene generation + Manim render on plan.needs_animation; a non-animated plan yields a status='skipped' SceneBundle and no render. PipelineResult carries the plan.",
     "services/pipeline.py / ui/workers.py", "headless", "Documented", ""),
    ("F185", "Planner", "Deterministic offline planner fallback",
     "As a user without an API key, planning still works and is reproducible.",
     "Planner.plan() falls back to heuristic_plan() (model_name='heuristic-fallback') on missing key or any provider/parse error; identical prompts yield identical plans.",
     "services/planner.py", "headless", "Documented", ""),
    ("F186", "Planner", "UI view pills gated by plan",
     "As a user, I only see the Canvas/Video tabs relevant to my problem.",
     "SimulationPanel.apply_plan() hides the Canvas pill unless needs_2d or needs_3d, hides the Video pill unless needs_animation, keeps Code, and re-selects the first visible pill; MainWindow wires it via the worker's plan_ready signal.",
     "ui/widgets.py / ui/main_window.py", "gui", "Documented", ""),
    ("F187", "Numeric", "ODE ground-truth integration",
     "As a user, my plots reflect the real solution, not a curve the model guessed.",
     "solve_numeric() integrates a solver-attached ODE spec (state/rhs/initial/t_range/observe) via scipy solve_ivp; RHS expressions compile through the same AST allow-list (services/plotting) so model math is never eval'd. The damped-oscillator fallback matches the closed-form underdamped solution to <1e-3; invalid/unsafe specs return ok=False (scipy optional).",
     "services/numeric.py / core/models.py", "headless", "Documented", ""),
    ("F188", "Numeric", "Canvas driven by numeric trajectory",
     "As a user, the live canvas animates the exact integrated trajectory.",
     "build_canvas_state() prefers _state_from_numeric (interpolating the integrated series) over the analytic plot payload; x(0) equals the initial condition. A missing/failed integration falls back to the plot payload then legacy curves so the canvas never crashes.",
     "ui/live_canvas.py", "headless", "Documented", ""),
    ("F189", "Research", "Formal cited research PDF",
     "As a user, I get a professional PDF write-up with a figure and real citations.",
     "build_research_pdf() assembles a structured LaTeX document (problem, abstract, derivation, a matplotlib figure of the numeric ground truth, parameters, References from the RAG hits with page numbers, and a Verification section) and compiles it via pdflatex; wired to the Analysis 'Export PDF' action through the cancellable background export task.",
     "services/research.py / ui/main_window.py", "headless", "Documented", ""),
    ("F190", "Research", "PDF backend fallback (no pdflatex)",
     "As a user without a LaTeX install, I still get a PDF.",
     "When pdflatex is absent, build_research_pdf falls back to a matplotlib-rendered PDF (text + numeric figure) via PdfPages, then to .tex-only. render_numeric_figure integrates the ODE (or the plot payload) into a PNG.",
     "services/research.py", "headless", "Documented", ""),
    ("F191", "Scene", "Numeric-driven trajectory component",
     "As a user, the animation shows the real solution and renders reliably.",
     "scene_components.trajectory bakes the integrated (t, x) samples into a self-contained Manim Scene (Axes + smooth VMobject curve + MoveAlongPath tracer, manim+numpy only). Render-verified: composes and renders to MP4 in seconds, versus fragile free-form LLM scenes.",
     "services/scene_components/trajectory.py", "headless", "Documented", ""),
    ("F192", "Scene", "3-D surface component",
     "As a user, inherently-3-D problems get a real rotating ThreeDScene.",
     "scene_components.surface3d emits a ThreeDScene (ThreeDAxes + Surface + ambient camera rotation) when the plan flags needs_3d and no numeric trajectory applies; compose_scene_code returns None when neither fits so the LLM/static path takes over. Render-verified.",
     "services/scene_components/surface3d.py", "headless", "Documented", ""),
    ("F193", "Scene", "Curated composition preferred over raw LLM",
     "As a user, scenes come from tested building blocks, not fragile generated code.",
     "ManimRuntime.generate_scene(_async) calls _compose_curated first: a composed scene that compiles is used directly (diagnostics note 'curated component'); only when no component fits does it fall back to LLM generation (safety-gated) or the static template. Plan is threaded from the pipeline/worker; coexists with the scene tournament.",
     "services/manim_runtime.py", "headless", "Documented", ""),
    ("F194", "Verify", "Physics self-verification",
     "As a user, the result is checked against its own numerics before I trust it.",
     "verify_solution() integrates the ODE ground truth and runs concrete checks: finiteness, boundedness, energy behaviour (conserved when undamped, decaying when damped), and small-angle pendulum period vs 2*pi*sqrt(L/g). A physically-correct damped oscillator passes all checks; the report is surfaced in --smoke and embedded in the research PDF.",
     "services/verify.py", "headless", "Documented", ""),
    ("F195", "Verify", "Catches unphysical results",
     "As a user, a wrong derivation is flagged, not silently animated.",
     "An anti-damped oscillator (flipped dissipation sign) makes energy and amplitude grow; verify_solution flags both the energy and boundedness checks. The differentiator: the tool checks itself instead of emitting plausible-looking but wrong physics.",
     "services/verify.py", "headless", "Documented", ""),

    # ── Quality integrity: no silent degradation (found by driving the app) ──
    ("F196", "Quality", "Solver never silently downgrades",
     "As a user, a transient provider hiccup must not quietly hand me canned physics.",
     "AsyncLLMCoordinator.solve() retries the remote solve SOLVER_ATTEMPTS times with backoff and recovers to the real model; only after every attempt fails does it use the deterministic scaffold, logging an ERROR and stating in the result note that the output is 'a generic scaffold, not solved physics'.",
     "services/llm.py", "headless", "Documented", ""),
    ("F197", "Quality", "Planner floor — outputs never under-planned",
     "As a user, the same question doesn't randomly lose its video between runs.",
     "Planner.plan() retries the model and UNIONs its answer with the deterministic heuristic floor, so a flaky or stingy reply can never drop a modality the prompt clearly warrants; the added modalities are recorded in the rationale, and total failure degrades to the floor rather than below it.",
     "services/planner.py", "headless", "Documented", ""),
    ("F199", "Scene", "Text-mode math auto-repair (render-killer)",
     "As a user, a scene isn't thrown away because the model wrote Tex instead of MathTex.",
     "Tex() renders in LaTeX text mode, so 'm_1', '\\theta_1' or '\\mathcal{L}' abort the compile ('Missing $ inserted.' / 'allowed only in math mode') and kill the whole render — minutes of a cloud job. repair_text_mode_math() promotes those calls to MathTex before render (allow-listing text-safe commands rather than blacklisting math macros, so \\mathcal-class misses can't recur), leaving plain Tex and existing MathTex untouched; check_latex_strings also reports it. Verified against a real failed cloud scene, which then rendered.",
     "services/scene_validation.py / services/scene_generator.py", "headless", "Documented", ""),
    ("F198", "Quality", "Honest offline verification scope",
     "As a user, verification never claims to have checked physics it didn't.",
     "The keyless fallback's ODE models a damped harmonic oscillator, so it is attached only when the question is oscillator-like (OSCILLATOR_STEMS). An off-topic prompt (e.g. entropy) gets no numeric_spec and verify_solution reports 'No numeric model to verify' instead of '3/3 physics checks passed' about a system the user never asked about.",
     "services/llm.py / services/verify.py", "headless", "Documented", ""),
    ("F200", "Scene", "Curated pendulum component (nonlinear, numeric-driven)",
     "As a user, a pendulum problem shows a real swinging bob obeying the true physics, not an abstract theta(t) line.",
     "compose_scene_code routes pendulum-domain problems (detect_domain == 'pendulum' via keyword or gravity+length variables) to scene_components.pendulum, which integrates the FULL nonlinear pendulum theta'' = -(g/L) sin(theta) - 2*damping*theta' through services/numeric (AST-allow-listed RHS, so large-angle motion is the real solution, not a small-angle cosine), then bakes theta(t) into a self-contained rod+bob scene with a TracedPath comet tail and a synchronized theta-vs-t readout. Chosen ahead of the generic trajectory; a non-pendulum oscillator is unaffected. Render-verified (480p MP4 in seconds).",
     "services/scene_components/pendulum.py / services/scene_components/__init__.py", "headless", "Documented", ""),
    ("F201", "Scene", "Curated phase-portrait component (state space)",
     "As a user asking about phase space, I see the v-vs-x spiral collapse onto the attractor, not just a time series.",
     "compose_scene_code composes scene_components.phase_portrait when the prompt/summary asks for a phase-space view (phase portrait/plane/space, limit cycle, attractor, state space) and the solver's numeric_spec has exactly two state variables. It integrates the same ODE ground truth and bakes the (x, v) samples into Axes + a smooth VMobject trajectory + a MoveAlongPath tracer sweeping toward the fixed point. A plain oscillator without that framing keeps the time-series trajectory. Render-verified (480p MP4 in seconds).",
     "services/scene_components/phase_portrait.py / services/scene_components/__init__.py", "headless", "Documented", ""),
    ("F202", "Scene", "Curated electric field-line component",
     "As a user, an electrostatics problem shows real field lines threading from + to -, not a generic curve.",
     "Electrostatics is not a time-ODE, so no numeric-trajectory component fires; compose_scene_code routes em_field-domain problems (detect_domain == 'em_field') to scene_components.field_lines, which integrates the field-line streamlines of the charge configuration in Python (E = sum q_i (r-r_i)/|r-r_i|^3, stepped along the normalized field, dipole by default from the 'separation' variable) and bakes the polylines into a self-contained scene: +/- charge dots, the field lines, and a test charge that rides the longest line so the frame moves. Render-verified (480p MP4 in seconds).",
     "services/scene_components/field_lines.py / services/scene_components/__init__.py", "headless", "Documented", ""),
    ("F203", "Scene", "Curated Fourier-epicycle component",
     "As a user asking about a Fourier series, I watch rotating vectors sum tip-to-tail to build a square wave.",
     "The series/transforms domain had no non-LLM visual; compose_scene_code composes scene_components.fourier_epicycles when the prompt is about Fourier / epicycles / a square wave (excluding the bare word 'harmonic', which belongs to the harmonic oscillator). A chain of phasors — one per odd harmonic, amplitude 4/(pi k), rotating at frequency k — sums tip-to-tail so the tip traces the epicycle drawing (TracedPath) while its height builds the square wave on a synchronized time axis. Fully parametric, deterministic. Render-verified (480p MP4 in seconds).",
     "services/scene_components/fourier_epicycles.py / services/scene_components/__init__.py", "headless", "Documented", ""),
    ("F204", "Scene", "Curated quantum-wavepacket component",
     "As a user, a quantum problem shows a probability density sloshing in a potential well, not a bare graph.",
     "The quantum domain had no non-LLM visual; compose_scene_code composes scene_components.quantum on quantum/wavefunction/wavepacket/Schrodinger/potential-well phrasing (distinctive stems only, so it never steals the *classical* harmonic oscillator). It stages a harmonic potential well V=0.5kx^2, a few quantized energy levels, and a Gaussian |psi(x,t)|^2 coherent state whose centre oscillates, shaded as a redrawn Polygon. Parametric + deterministic. Render-verified (480p MP4 in seconds).",
     "services/scene_components/quantum.py / services/scene_components/__init__.py", "headless", "Documented", ""),
    ("F205", "Scene", "Curated double-slit interference component",
     "As a user asking about interference, I see two coherent sources and the fringe pattern build on a screen.",
     "Optics/interference had no non-LLM visual; compose_scene_code composes scene_components.double_slit on double-slit/interference/diffraction/Young's phrasing. Two slits emit expanding circular wavefronts (Arc rings driven by a ValueTracker) and a screen on the right shows the intensity I(y) proportional to cos^2, with bright-fringe markers at the maxima. Parametric + deterministic. Render-verified (480p MP4 in seconds).",
     "services/scene_components/double_slit.py / services/scene_components/__init__.py", "headless", "Documented", ""),
    ("F206", "Scene", "Curated kinetic-theory (ideal-gas) component",
     "As a user, a thermodynamics problem shows real gas particles bouncing in a box behind temperature/pressure.",
     "Thermo/stat-mech had no non-LLM visual; compose_scene_code composes scene_components.kinetic_theory on kinetic-theory/ideal-gas/Maxwell-Boltzmann/thermodynamics phrasing. N particles with seeded (deterministic LCG) initial conditions bounce elastically off the box walls via a per-frame add_updater with wall reflection, alongside a Maxwell-Boltzmann speed-distribution reference curve. Same prompt -> identical scene (seeded). Render-verified (480p MP4 in seconds).",
     "services/scene_components/kinetic_theory.py / services/scene_components/__init__.py", "headless", "Documented", ""),
    ("F207", "Scene", "Curated chaotic double-pendulum component",
     "As a user, a double-pendulum problem shows the real tangled chaotic trajectory, integrated from the true equations.",
     "compose_scene_code checks the double pendulum BEFORE the single one (whose domain also matches 'pendulum') on double-pendulum/chaotic-pendulum phrasing, and composes scene_components.double_pendulum, which integrates the full nonlinear 4-state system (th1, th2, w1, w2) through services/numeric (AST-allow-listed RHS) and bakes the exact bob positions into two rods + two bobs + a TracedPath painting the chaotic path on the lower bob. A single-pendulum prompt still gets the single component. Render-verified (480p MP4 in seconds).",
     "services/scene_components/double_pendulum.py / services/scene_components/__init__.py", "headless", "Documented", ""),
    ("F208", "Scene", "Curated thin-lens ray-diagram component",
     "As a user, an optics problem shows the principal rays converging to form the real inverted image.",
     "Geometric optics had no non-LLM visual; compose_scene_code composes scene_components.lens on lens/refraction/focal-length/image-formation phrasing. It draws the textbook converging-lens ray diagram — object, the three principal rays (parallel-through-far-focus, chief-through-centre, focal-emerging-parallel), and the real inverted image placed by the thin-lens equation 1/f = 1/do + 1/di — with a light pulse travelling a ray. Render-verified (480p MP4 in seconds).",
     "services/scene_components/lens.py / services/scene_components/__init__.py", "headless", "Documented", ""),
    ("F209", "Scene", "Curated standing-wave (normal-mode) component",
     "As a user, a normal-mode problem shows a standing wave breathing between its envelopes with marked nodes.",
     "The standing wave (resonant normal mode) had no non-LLM visual (only the traveling-wave template); compose_scene_code composes scene_components.standing_wave on standing-wave/normal-mode/vibrating-string/node-antinode phrasing. It animates y(x,t) = A sin(n*pi*x/L) cos(wt) between its dashed envelopes, with fixed nodes and antinodes marked. Render-verified (480p MP4 in seconds).",
     "services/scene_components/standing_wave.py / services/scene_components/__init__.py", "headless", "Documented", ""),
    ("F210", "Scene", "Curated Kepler-orbit component (equal-area law)",
     "As a user, an orbit problem shows a real Kepler ellipse where equal-time sectors have equal area.",
     "compose_scene_code composes scene_components.orbit when the domain is an orbit/Kepler/gravitation problem (detect_domain == 'orbit'), guarded against the 'orbital' substring so an atomic orbital is NOT treated as a planetary orbit. It integrates the real two-body problem r'' = -mu r/|r|^3 through services/numeric (so the planet moves faster at perihelion), bakes the trajectory, and stages the star at the focus, a comet-tail planet with a sweeping radius vector, and two equal-TIME sectors that come out equal in AREA (Kepler's 2nd law) as the hero frame. Render-verified (480p MP4 in seconds).",
     "services/scene_components/orbit.py / services/scene_components/__init__.py", "headless", "Documented", ""),
    ("F211", "Scene", "3-D surface renders the problem's real field",
     "As a user, an inherently-3-D problem shows the actual potential/field surface, not one generic bump.",
     "surface3d.build previously emitted a single Gaussian bump regardless of the problem. It now selects the surface from the solver's keywords/summary: a point-charge 1/r peak, a dipole's +/- pair, a saddle (unstable equilibrium), a p-orbital's two lobes, or the Gaussian default — each a real ThreeDScene (ThreeDAxes + Surface + ambient camera orbit) with an on-screen label. Reached as the needs_3d fallback (F192 path preserved: still a ThreeDScene, still None when needs_3d is false). Render-verified (480p MP4).",
     "services/scene_components/surface3d.py / services/scene_components/__init__.py", "headless", "Documented", ""),
    ("F212", "Scene", "Curated components track solver parameters",
     "As a user, each curated scene reflects the actual numbers of my problem, not a fixed canonical example.",
     "Every curated component reads its physical parameters from the solver's variables with clamped, sensible defaults, so an empty solver still renders the canonical default (no regression) while a specified problem is tracked: orbit reads eccentricity; quantum reads stiffness/mass (well frequency) and amplitude; double_slit reads slit separation + wavelength (fringe spacing); fourier_epicycles reads the number of terms; kinetic_theory reads particle count + temperature (speed scale); and lens/standing_wave/pendulum/double_pendulum/field_lines already read focal length, mode, gravity/length/mass, and charge separation. The numeric-driven components (trajectory/phase_portrait) are inherently problem-specific.",
     "services/scene_components/__init__.py / services/scene_components/problems/_kit.py / services/scene_components/orbit.py / services/scene_components/quantum.py / services/scene_components/double_slit.py", "headless", "Documented", ""),
    ("F213", "Scene", "Curated coupled-oscillators component",
     "As a user, a coupled-oscillator problem shows two masses on springs with the energy visibly beating between them.",
     "compose_scene_code composes scene_components.coupled_oscillators on coupled-oscillator/two-mass phrasing, checked BEFORE the single standing wave (whose 'normal mode' stem would otherwise match). It integrates the real coupled ODE (state x1, x2, v1, v2; m x1'' = -2k x1 + k x2, etc.) through services/numeric, started with one mass displaced so the energy sloshes between them (the two normal modes' beat), and bakes the motion into two masses on drawn springs above plus the x1(t)/x2(t) traces below. Reads stiffness/mass. Render-verified (480p MP4 in seconds).",
     "services/scene_components/coupled_oscillators.py / services/scene_components/__init__.py", "headless", "Documented", ""),
    ("F214", "Scene", "Curated concave-mirror ray-diagram component",
     "As a user, a curved-mirror problem shows the principal rays reflecting to form the real inverted image.",
     "compose_scene_code composes scene_components.mirror on concave/convex/curved-mirror/mirror-equation phrasing ('mirror' is excluded from the lens stems so a mirror prompt is not stolen by the lens). It draws the concave-mirror ray diagram — the mirror arc (radius 2f), optical axis, F and C marked, the object, the three principal rays (parallel->through F, through F->parallel, through C->back on itself), and the real inverted image placed by the mirror equation 1/f = 1/do + 1/di — with a light pulse travelling a ray. Reads focal length/object distance/height. Render-verified (480p MP4 in seconds).",
     "services/scene_components/mirror.py / services/scene_components/__init__.py", "headless", "Documented", ""),
    ("F215", "Quality", "Verification gate fails loudly on a failing run",
     "As a maintainer, when a feature test fails, I expect every gate to go red instead of absorbing the failure into a green spreadsheet.",
     "The three layers that used to swallow a failing feature now propagate it. test_features.py returns failure_exit_code(results) — non-zero whenever any feature is FAIL — so the CI step that runs the harness can actually fail. build_feature_tracker.apply_results() no longer relabels a failing defect-linked feature 'FIXED'; it stamps 'REGRESSED' with the failure note, and a failing run overrides the hand-stamped Phase-4 column to FAIL. tools/tracker_integrity_audit.py refuses to certify a tracker whose feature_test_results.json contains any FAIL, and names a regressed defect feature explicitly, so regenerating the spreadsheet can no longer launder a red run green.",
     "test_features.py / build_feature_tracker.py / tools/tracker_integrity_audit.py", "headless", "Documented", ""),
    ("F216", "Scene", "Curated scenes explain what they show",
     "As a student, when a curated animation plays, I expect a short intro (concept, equation, what to watch) and a closing card with the key numbers and the takeaway.",
     "compose_scene_code wraps every 2-D curated scene with scene_components/explain.py: an intro card, then after the animation a centred closing card with the equation, 2-4 key numbers and a boxed takeaway. Numbers come from each scene's own params() or numeric solve, holds are sized with estimate_duration toward request.duration_target_s, text is LaTeX-free and restricted to verified glyphs, and 3-D or unparseable scenes pass through unchanged. v3 wrapped every topic in the same prediction card, captions, crossed-out misconception and thumbnail; it was rated below v2, so those devices are now opt-in ingredients an explanation may request (predict/answer, misconception, captions pinned to the scene's schedule, outro='beside'), never applied uniformly. The clutter heuristic treats FadeOut(*self.mobjects) and Group(*self.mobjects) as whole-stage cleanup.",
     "services/scene_components/explain.py / services/scene_components/__init__.py / services/manim_runtime.py / services/scene_validation.py", "headless", "Documented", ""),
    ("F217", "Scene", "Each topic tells its story its own way",
     "As a student, I expect each physics topic's video to use its own creative scenario instead of one template for every topic.",
     "scene_components/scenarios/ restages seven topics with a device chosen per topic, reusing each component's params() and numeric solve: the pendulum race (1 kg vs 3 kg in lockstep, double length √2 slower, 10° vs 60° release), Kepler's stopwatch (a wedge per equal time slice; distance-per-tick bars vary while area-per-tick bars stay flat), two waves meet (right- and left-moving waves summing to a standing wave), a square wave one circle at a time (harmonics added per round with the corner overshoot stalling near 9%), follow the arrows (a force-arrow field, lines grown along it, a probe with a live force readout), photon by photon (single hits building bands; covering a slit leaves one hump), and energy buckets (the two normal modes, then energy pouring between the masses). compose_scene_code prefers a topic's scenario and falls back to the plain component (compose_component_code) if the scenario cannot build.",
     "services/scene_components/scenarios/ / services/scene_components/__init__.py", "headless", "Documented", ""),
    ("F218", "Scene", "Animation that solves a concrete physics problem",
     "As a student, when I give a concrete problem with numbers, I expect a video of about a minute that solves it step by step with animation and proves the answer.",
     "scene_components/problems/ turns a problem with its givens into a self-contained video of about 60-66 s, following the Minnesota solving arc with short subgoal labels. Each problem has its own device. Where does the kicked ball land: two shadows (a steady ground shadow and a rising-and-falling wall shadow) give the flight time and distance, the simulated flight lands on the computed flag, and 30°/60° land on the same spot. A grandfather clock on another world: two clocks, each advanced by its own numerically simulated pendulum, show the drift, then a shortened pendulum ticks in step. How long is one lap of the ISS: Newton's cannon, a to-scale orbit, a time-lapse lap timed against the computed period, and a zoom out to the one-day orbit. Numbers come from the solver's variables with safe defaults, and every build checks the simulation against the analytic answer before emitting the scene. Without the givens, the topic's explainer scenario plays instead.",
     "services/scene_components/problems/ / services/scene_components/__init__.py", "headless", "Documented", ""),
    ("F219", "Provider", "Backup model provider takes over failed calls",
     "As a user, when the primary model provider has a bad day, I expect my video to be made by the backup model instead of turning into a placeholder.",
     "AppSettings gains fallback_api_key, fallback_base_url and fallback_llm_model (env AETHERLAB_FALLBACK_OPENAI_API_KEY / AETHERLAB_FALLBACK_OPENAI_BASE_URL / AETHERLAB_FALLBACK_LLM_MODEL, or app config fallback_api_key / fallback_base_url / fallback_model). Every LLM caller (solver, planner, storyboard and codegen, critic, lesson planner, fact check, research) now gets its client from llm_client.make_client. When the primary fails with a connection cut, timeout or any API error status, or returns an empty reply, the same request is retried once on the backup with its own model name, a temperature re-derived from what the task wanted (PolicyTemperature.wanted), and its own thinking flags. The switch is logged, and the solver records which model actually answered. model_policy adds a kimi-reasoning pathway (K3 / K2.8 / kimi-*: temperature pinned to 1, which their API requires, no timeout retry), and every chat.completions call routes its temperature through request_temperature.",
     "services/llm_client.py / services/model_policy.py / core/settings.py / services/llm.py", "headless", "Documented", ""),
    ("F220", "Export", "Well-explained LaTeX study guide or worked-solution PDF",
     "As a student, I expect a topic to export as a well-explained LaTeX study guide, and a problem to export as its theory plus a step-by-step worked solution in a PDF.",
     "services/study_document.py classifies the request (a question with numbers or an explicit task is a problem, otherwise a topic). The configured model writes structured JSON: for a topic an overview, 4-6 sections with step-by-step derivations, boxed key results, a worked example, common mistakes and a summary; for a problem a restatement, Given/Find, the theory it needs, a plan, 5-10 explained solution steps, a boxed final answer, sanity checks, common mistakes and a summary. The app typesets it (tcolorbox, booktabs, fancyhdr, hyperref). Prose is escaped and math travels in dedicated fields, and LaTeX commands written with single backslashes are recovered before JSON parsing, so \\frac is not read as a form feed. The compile heals itself: a failing block is swapped for a safe rendering and recompiled. AetherLab's own simulations (projectile, pendulum clock, orbit) add independent checks, and RAG hits become references. With no model, or when authoring fails, the document is built from the solver's derivation, with matplotlib as the last resort. Export PDF in the app and the new CLI option aetherlab --pdf PROMPT --out FILE both use it.",
     "services/study_document.py / ui/main_window.py / __main__.py / services/scene_components/problems/", "headless", "Documented", ""),
    ("F221", "Visualization", "Harder problem videos: relativity, quantum, chaos, normal modes",
     "As a student working on harder physics, I expect a creative video that solves my problem in full detail, with real equations, and proves the answer.",
     "Four new self-contained problem videos (80-110 s), each with its own device. Do the muons reach the ground: two stories, one ending; the everyday guess (33 half-lives) kills 400 muons in the first kilometres, Earth's story slows the muon's clock (γ = 10) and a zoomed muon's view shows the air contracted to 1.5 km; 400 muons with random lifetimes and an ODE check the 10.1% survival. What colour does the trapped electron glow: size decides colour; whole half-waves build the n²E₁ ladder, the n = 3 → 2 photon lands at 659 nm on a spectrum, a finite-difference Schrödinger solve reproduces the ladder, and squeezing the box shifts the light to green and blue. How far ahead can we predict a double pendulum: twins 10⁻⁶ rad apart, a live log-scale gap graph whose slope is the Lyapunov exponent, and 1000× better starts that buy only ~7 s each. How long until the swing walks across: in-step and opposite normal modes added into beats, T = π/(ω₂ − ω₁) checked by the full nonlinear simulation, and the spring-stiffness what-if. Equations are typeset with MathTex (Cloud installs TeX automatically) and fall back to text when LaTeX is missing; every number is computed from the solver's givens and verified before the scene is emitted.",
     "services/scene_components/problems/__init__.py / services/scene_components/problems/_kit.py / services/scene_components/problems/muon_paradox.py / services/scene_components/problems/quantum_dot.py / services/scene_components/problems/chaos_horizon.py / services/scene_components/problems/coupled_swing.py", "headless", "Documented", ""),
    ("F222", "Render", "Partial revision renders include every sampled animation",
     "As a student, when a critic-driven scene revision is rendered around sampled problem frames, I expect the preview to include the complete animation containing each sampled frame.",
     "_animation_range_for_times maps each timestamp to its top-level play/wait event and returns a Manim -n range whose exclusive end is one past the last selected event; ambiguous dynamic timing falls back to a full render.",
     "aetherlab/services/manim_runtime.py / tests/test_upgrade_missions.py", "headless", "Documented", ""),
    ("F223", "Export", "Study-document prose claims carry review evidence",
     "As a student, when a study guide makes a numerical comparison, I expect a trusted reference check or a clear not-checked status before treating it as fact.",
     "Study-document exports audit recognized solar-irradiance comparisons against NASA's Earth-orbit value, correct mismatched ratios with a citation, and store the result beside the content. When source excerpts are available, a bounded advisory review can report supported, issues found, or not checked; missing evidence remains explicitly not checked. The PDF displays this review and does not certify the rest of the prose.",
     "aetherlab/services/study_document.py / aetherlab/services/research.py / tests/test_study_claim_review.py", "headless", "Documented", ""),
    ("F224", "Quality", "Visual regression accounts for fades and duration shifts",
     "As a maintainer, I expect strict visual checks to catch sustained blank output without failing on ordinary scene fades or comparing unlike clip lengths as if their ratios were directly equivalent.",
     "The audit permits brief fades up to 1.0 s, warns and fails on longer blank spans or a blank-frame ratio above 10%, and compares blank/static ratios only when baseline and current clip durations are within 25%. Duration collapses remain regressions regardless of ratio comparability, and skipped comparisons are reported explicitly.",
     "tools/visual_regression.py / test_features.py", "headless", "Documented", ""),
    ("F225", "ENT Practice", "Fixed-key 40-question physics bank and scoring",
     "As a Kazakhstan high-school student preparing for the ЕНТ, I want a practice bank with clear answer keys and explanations so I can study without AI grading.",
     "ent_physics_bank defines 40 original study questions in Kazakh, Russian, and English across the official 25-topic format; 25 single-answer, five context, five multiple-answer, and five matching items sum to 50 points. Keys and worked explanations are fixed in code, multi-answer/matching use 0/1/2 partial credit, and teacher/language review stays explicitly pending until a Kazakhstan physics teacher signs off.",
     "aetherlab/services/ent_physics_bank.py / tests/test_ent_practice_mvp.py", "headless", "Documented", "Question content and translations still require teacher review; PASS covers software invariants only."),
    ("F226", "ENT Practice", "Three-language practice and timed mock UI",
     "As a student, I want to practice in Kazakh, Russian, or English by topic and difficulty, then review my answer and the explanation.",
     "ExamPracticeDialog and the main selector localize setup, filters, single/multiple/matching controls, feedback, Kazakh terms, result key and timed mode. The full timed set is 40 questions / 50 points / 90 minutes. Timed setup hides the entire practice-size field; switching modes/languages preserves the practice count. The authored set is labelled educational, not an official ЕНТ variant, with NCT preparation/free-practice links.",
     "aetherlab/ui/exam_practice.py / aetherlab/ui/command_bar.py / aetherlab/services/ent_physics_bank.py / tests/test_ent_practice_mvp.py / tests/test_timed_practice_acceptance.py", "gui", "Documented", "Original practice items are not an official NCT variant."),
    ("F227", "ENT Progress", "Local study goals and mistake review",
     "As an ЕНТ student, I want my goals, topic progress, and missed questions to persist locally so I can plan what to review next.",
     "Goals, bounded attempts, points and mistakes persist locally. IO errors preserve data with unavailable/stale states and retry; unknown goals/mistake actions are disabled. Nonfinite preferences/points and invalid attempt aggregates cannot crash views: invalid records are omitted from calculations, recovery is disclosed and reads preserve file bytes. Draft/result failures permit retry; answers/timer freeze until a confirmed commit. Completed history omits selected answers.",
     "aetherlab/services/ent_practice_progress.py / aetherlab/ui/exam_practice.py / aetherlab/ui/progress_notice.py / test_features.py / tests/test_ent_practice_mvp.py / tests/test_progress_storage_recovery.py / tests/test_progress_read_views.py / tests/test_practice_result_consistency.py", "gui", "Documented", ""),
    ("F228", "Export", "Searchable localized ЕНТ practice PDF",
     "As a student, I want to save a readable report of my practice answers, explanations, and progress in my chosen language.",
     "The Kazakh/Russian/English A4 study report keeps searchable prose, answers, complete study key, terms, progress and NCT links. Scored count/denominator match screen/history: unattempted practice is excluded, timed items count. Shared LaTeX steps are equation images; formula questions/sources have explicit pages. Fonts register per Qt instance. QPdfWriter exports without system-printer discovery. A fresh staged PDF is parsed/text-checked before atomic replacement; failures preserve old reports. Items are authored, not official variants.",
     "aetherlab/services/ent_practice_pdf.py / aetherlab/ui/exam_practice.py / aetherlab/ui/fonts.py / tests/test_ent_practice_mvp.py / tests/test_practice_result_consistency.py / tests/test_ui_fonts.py / tests/test_practice_pdf_transaction.py", "gui", "Documented", "Formula images are not selectable text. Sample PDF review and first-question formula templates do not certify all 2500 item layouts."),
    ("F229", "ENT Lesson", "Source-grounded accelerated-motion lesson route",
     "As a beginner preparing for the ЕНТ, I want a simple lesson with a worked example and verified practice task in my chosen language.",
     "ent_lesson_catalog supplies the fixed constant-acceleration route in Kazakh, Russian, and English, with plain-language terms, beginner-first theory, formula conditions, a worked example, one NCT sample task and fixed key, citations to the Kazakhstan grade-10 textbook and NCT PDF pages, and shared numeric values across translations. The route carries explicit source and teacher-review states; it does not claim the draft translations are approved.",
     "aetherlab/services/ent_lesson_catalog.py / tests/test_ent_route_stage_a.py / tools/verify_accelerated_motion_route.py", "headless", "Documented", "Kazakh terminology and translated NCT sample wording still need teacher review."),
    ("F230", "ENT Dashboard", "Localized student preparation dashboard",
     "As an ЕНТ student, I want a home screen in my selected language that points me to practice, topics, progress, and mistakes to revisit.",
     "Kazakh/Russian/English home and progress screens show goals, best mock, attempts, mistakes and companion from one consistent file snapshot. Perfect samples invite practice without inventing mistakes/mastery. Pending exercise and mock IDs in the selected topic prompt review; cleared topics invite new questions and retain historical counts. Failed refresh retains data with a stale notice and Reload. Unavailable data shows unknown values and hides personal recommendations. File-keyed caches cannot show another learner's results after an unreadable profile switch. Successful retry restores current data.",
     "aetherlab/ui/student_views.py / aetherlab/ui/progress_notice.py / aetherlab/services/ent_practice_progress.py / tests/test_ent_practice_mvp.py / tests/test_progress_read_views.py / tests/test_practice_explanation_display.py", "gui", "Documented", ""),
    ("F231", "References", "Localized textbook and ЕНТ source browser",
     "As a student, I want the source browser to match my selected language and keep textbooks separate from ЕНТ practice files.",
     "ReferenceSourcesDialog uses the selected Kazakh, Russian, or English locale for its title, guidance, folder picker, tabs, empty states, source status, and error messages, and registers the bundled Cyrillic/Kazakh-safe font when opened independently. It separates grade-7–11 references from ЕНТ question sets, keeps the folder read-only, opens only the chosen archive member, and persists a validated source-folder selection. MainWindow and Practice pass the active language into the dialog.",
     "aetherlab/ui/reference_sources.py / aetherlab/ui/library_panel.py / aetherlab/ui/exam_practice.py / tests/test_ent_practice_mvp.py", "gui", "Documented", ""),
]
# fmt: on

# Student features added after the first catalog sweep. These are distinct user
# behaviours, not an assertion that the legacy 231 checks cover the new modules.
FEATURES.extend([
    ("F232", "ENT Practice", "100 authored exercises per physics topic",
     "As a student, I want many exercises in each topic so repeated practice does not stop after one question.",
     "build_topic_exercises produces 2500 original variations across 25 topics, 100 per topic, with stable IDs, deterministic choices and shared numerical answers for Kazakh, Russian and English. They are authored practice and retain pending teacher-review status; numerical variants are not 2500 distinct solution methods.",
     "aetherlab/services/ent_topic_bank.py / aetherlab/services/ent_physics_bank.py / tests/test_ent_practice_mvp.py", "headless", "Documented", ""),
    ("F233", "ENT Practice", "LaTeX solutions and finish practice early",
     "As a student, I want readable worked formulas and the ability to stop a topic practice session when I need to.",
     "Practice feedback and completed practice/mock reviews typeset shared solution_latex. All 40 authored mock items now include language-invariant worked math, also used by PDF. A fresh review document isolates images per attempt; renderer failures use readable math or a localized diagnosis. The review uses a UI font. Answered practice alone affects totals; unattempted items say not counted. Timed items stay in totals. Screen/history/PDF share scoring; perfect samples invite further practice, later mistakes restore review. Early finish remains available.",
     "aetherlab/ui/exam_practice.py / aetherlab/services/practice_math.py / aetherlab/services/ent_topic_bank.py / aetherlab/services/ent_mock_solutions.py / tests/test_ent_practice_mvp.py / tests/test_ui_layout_regressions.py / tests/test_practice_result_consistency.py / tests/test_practice_explanation_display.py / tests/test_mock_solution_display.py", "gui", "Documented", ""),
    ("F234", "Profiles", "Switch local learners without sharing progress",
     "As a learner sharing this device, I want to select my profile and keep my goals, attempts and course progress separate.",
     "StudentProfileStore preserves legacy progress, separates learners and switches views to their files. An unreadable registry propagates IO failure without being reset/overwritten; missing/malformed files keep legacy recovery. Complete new profiles use one registry commit. Windows write refusals have bounded retries; failed activation/opening keeps current views and reports an error. This local selector is not authentication.",
     "aetherlab/services/student_profiles.py / aetherlab/ui/main_window.py / aetherlab/ui/profile_dialog.py / aetherlab/core/atomic_json.py / tests/test_student_profiles.py / tests/test_atomic_json.py / tests/test_profile_read_recovery.py", "gui", "Documented", ""),
    ("F235", "Profiles", "Edit learner identity and avatar",
     "As a student, I want to save my name, username, class, school code and picture in my local profile.",
     "StudentProfileDialog edits identity/photo in Kazakh, Russian and English. 40-character name fields reload safely; rejected commits preserve old photos and editable drafts. Read failures retain choices/drafts, disable unconfirmed selection actions and offer Retry. Saved-but-not-reloaded is distinct from a failed save. Cancel preserves saved data; image failures have localized errors. Displayed email is a local label.",
     "aetherlab/ui/profile_dialog.py / aetherlab/ui/profile_avatar.py / aetherlab/services/student_profiles.py / tests/test_student_profiles.py / tests/test_profile_editing.py / tests/test_profile_read_recovery.py", "gui", "Documented", "File-picker return paths are injected in offscreen checks; native dialog, layout and keyboard acceptance remain open."),
    ("F236", "AI Help", "Ten AI help attempts per learner per day",
     "As a student, I want a visible daily help allowance and access to ordinary practice even after using my AI quota.",
     "consume_ai_help atomically counts ten daily attempts per local profile/date. IO failure preserves the counter and launches no request. CommandBar shows confirmed counts or an unknown —/10 badge in Kazakh, Russian and English; unknown/exhausted states disable only AI actions. Practice remains available. Refresh restores confirmed usage and clears the stale file-error message. This is a local allowance, not server enforcement.",
     "aetherlab/services/ai_help_quota.py / aetherlab/ui/main_window.py / aetherlab/ui/command_bar.py / tests/test_ai_help_quota.py / tests/test_ai_quota_io.py", "gui", "Documented", ""),
    ("F237", "ENT Schedule", "Weekly mock reminder and shortcut",
     "As a student, I want to choose a weekly exam day and see when my next mock is due.",
     "Saved weekly_mock_day drives localized dashboard reminders for Kazakh, Russian and English; on the chosen day the shortcut opens timed practice. This schedules a reminder and does not prohibit practice on other days.",
     "aetherlab/services/ent_practice_progress.py / aetherlab/ui/student_views.py / aetherlab/ui/main_window.py / tests/test_ui_layout_regressions.py", "gui", "Documented", ""),
    ("F238", "ENT Exam", "Resume a timed mock with elapsed time retained",
     "As a student, I want to resume an interrupted mock without losing answers or resetting its deadline.",
     "Active answers, IDs, remaining seconds and timestamp persist; resume subtracts closed time, and a full mock starts at 90 minutes. Localized Resume/Start again/Cancel controls make replacement explicit; Escape/close keeps saved bytes. A valid saved ID incompatible with the selected bank is diagnosed without replacement. Unreadable resume blocks start. Autosave failures are visible and closing retries. Pending completion resumes frozen; attempt IDs prevent duplicate history/points after stale cleanup. Finish defaults to localized Continue.",
     "aetherlab/services/ent_practice_progress.py / aetherlab/ui/exam_practice.py / tests/test_exam_resume_and_proctoring.py / tests/test_progress_storage_recovery.py / tests/test_exam_confirmation_localization.py", "gui", "Documented", "Active exam answers are intentionally saved; completed attempt history does not store answer selections. ID deduplication covers the retained 100-attempt history."),
    ("F239", "ENT Exam", "Optional camera and focus review signals",
     "As a student, I want to understand what the optional camera observes during a mock and how it affects my result.",
     "The opt-in shadow pilot reports prolonged missing/multiple faces, camera interruptions and focus loss as sparse metadata. Kazakh, Russian and English notices explain that it does not track gaze, block screenshots, prove cheating or change scores. Frames are processed in memory and are not stored.",
     "aetherlab/services/proctoring.py / aetherlab/ui/camera_monitor.py / aetherlab/ui/exam_practice.py / tests/test_exam_resume_and_proctoring.py", "gui", "Documented", "Real camera availability and stream recovery require a hardware check."),
    ("F240", "Teacher Review", "Inspect local school attempts and event metadata",
     "As a reviewer using this device, I want to inspect completed school mocks and their optional review signals.",
     "TeacherReviewDialog lists completed local school mocks and allowlisted signals in Kazakh, Russian and English. Registry or individual progress read errors retain the loaded snapshot and show a file error; Reload restores rows and clears placeholder spans. Unreadable data is not labelled as no mocks. Access is open to device users; camera signals are not cheating verdicts.",
     "aetherlab/services/teacher_review.py / aetherlab/ui/teacher_review_dialog.py / aetherlab/ui/leaderboard_dialog.py / tests/test_teacher_review.py / tests/test_school_view_io_recovery.py", "gui", "Documented", "No teacher role authentication or remote review is implemented."),
    ("F241", "School Ranking", "Local school ranking and score history",
     "As a student, I want to compare completed mock results with local learners in my school and see each score history.",
     "school_leaderboard groups school IDs, excludes practice and ranks full mocks with ties. Kazakh, Russian and English distinguish local/synced data. Clearing the endpoint loads local rows before announcing local mode; failed reads retain the last snapshot with an error. Changing from an empty to a scored student's history clears old spans so the score is visible.",
     "aetherlab/services/school_leaderboard.py / aetherlab/ui/leaderboard_dialog.py / tests/test_school_leaderboard.py / tests/test_school_view_io_recovery.py / tests/test_leaderboard_mode_switch.py", "gui", "Documented", ""),
    ("F242", "School Ranking", "Sync mock scores across devices",
     "As a student, I want to explicitly synchronize my completed mocks to the configured school leaderboard.",
     "Sync validates the endpoint, submits limited identity/mock data and merges ranks; identity uses username+school and school HMAC storage. Endpoint write errors retain drafts and launch no worker. An unreadable progress file makes no request, keeps the ranking snapshot and reports a local file error. Environment overrides consistently govern getter/save/sync and are explained in three languages; invalid overrides block connection. Saved preferences apply after override removal.",
     "aetherlab/services/leaderboard_client.py / aetherlab/services/leaderboard_server.py / aetherlab/ui/leaderboard_dialog.py / tests/test_school_leaderboard.py / tests/test_school_view_io_recovery.py / tests/test_leaderboard_mode_switch.py", "gui", "Documented", "Automated loopback checks do not certify deployed HTTPS service availability."),
    ("F243", "School Ranking", "Run leaderboard HTTP service",
     "As an operator, I want to choose the leaderboard host, port and database and validate submitted exam records.",
     "leaderboard_server.main accepts host, port and database CLI arguments; LeaderboardHTTPServer exposes health and leaderboard routes and validates scores before storing them in SQLite. Remote HTTP endpoints are rejected by the client; loopback HTTP is allowed for development.",
     "aetherlab/services/leaderboard_server.py / aetherlab/services/leaderboard_client.py / tests/test_school_leaderboard.py", "headless", "Documented", ""),
    ("F244", "Companion", "Choose and remember a study companion",
     "As a student, I want to choose one of the available companions and keep my choice when I reopen my profile.",
     "CompanionPickerDialog shows three choices in Kazakh, Russian and English and persists the selection per profile. A failed update preserves stored progress and the confirmed dashboard choice, shows a translated error and permits retry. Legacy choices request reselection without losing earned points.",
     "aetherlab/ui/companion_dialog.py / aetherlab/ui/student_views.py / aetherlab/services/ent_practice_progress.py / tests/test_gamification_progress.py / tests/test_progress_storage_recovery.py", "gui", "Documented", ""),
    ("F245", "Companion", "Companion growth from lifetime earned points",
     "As a student, I want my companion to evolve with earned practice points without losing growth when old attempts are trimmed.",
     "companion_progress uses fixed point milestones; cumulative points persist per profile independently of topic accuracy and bounded history. Dashboard art follows stage and companion choice and remains aligned with its orbit paths.",
     "aetherlab/services/gamification.py / aetherlab/services/ent_practice_progress.py / aetherlab/ui/study_visuals.py / tests/test_gamification_progress.py / tests/test_localized_ui_regressions.py", "gui", "Documented", ""),
    ("F246", "ENT Topics", "Confidence labels, search and topic actions",
     "As a student, I want to find a topic and understand whether I have practiced enough to trust my progress label.",
     "The topic catalog filters search/confidence and preserves lesson/practice actions. One consistent snapshot supplies minimum-sample-aware study labels, not exam predictions. Unreadable progress retains labelled stale values or shows unknown state, hides false zero bars and disables progress filtering; search and learning actions remain available. Reload restores confirmed data without stray desktop windows.",
     "aetherlab/ui/student_views.py / aetherlab/ui/progress_notice.py / aetherlab/services/gamification.py / tests/test_ui_layout_regressions.py / tests/test_gamification_progress.py / tests/test_progress_read_views.py", "gui", "Documented", ""),
    ("F247", "Localization", "Settings and shared shell follow the selected language",
     "As a student, I want the settings, empty screens, library and simulation controls to use my language without losing entered values.",
     "Settings, shared empty state, library/history and simulation/lesson controls retranslate into Kazakh, Russian and English. Switching language preserves the current profile, entered prompt, render quality and lesson settings.",
     "aetherlab/ui/main_window.py / aetherlab/ui/shared_widgets.py / aetherlab/ui/simulation_panel.py / aetherlab/ui/lesson_view.py / aetherlab/ui/library_panel.py / tests/test_localized_ui_regressions.py", "gui", "Documented", ""),
    ("F248", "Settings", "Restore saved render quality at startup",
     "As a user, I want the saved render quality to be restored in the command bar when I start PhysLab.",
     "MainWindow synchronizes the command quality with saved default_quality on startup; absent or invalid quality falls back to Standard. This covers persistence and UI synchronization, not a live cloud render.",
     "aetherlab/ui/main_window.py / aetherlab/core/settings.py / tests/test_settings_startup_sync.py", "gui", "Documented", ""),
    ("F249", "Cloud Render", "Validate downloaded cloud video metadata",
     "As a learner, I want an invalid or incomplete cloud video to be reported before it is presented as ready.",
     "Cloud artifact validation checks exact scene output, container, video stream, positive duration, requested dimensions and a decoded frame. A missing/broken PyAV decoder refuses certification with a repair hint. Segmented assembly preserves job/content identities. Diagnostics distinguish invalid media from access/render failures. Sampling a frame does not certify every frame or artistic quality.",
     "aetherlab/services/render_backend.py / aetherlab/services/segmented_pipeline.py / tests/test_cloud_media_check.py / tests/test_cloud_failure_diagnosis.py", "headless", "Documented", "Live cloud delivery and full viewing remain separate verification requirements."),
    ("F250", "ENT Lesson", "Acceleration route contains varied follow-up practice",
     "As a beginner, I want to practice comprehension, calculations and graph reading after the acceleration example.",
     "The fixed acceleration route serves its anchor and follow-up practice in a stable order with unique options and recomputed answers. The content retains source and pending-review distinctions rather than declaring teacher approval from software tests.",
     "aetherlab/services/ent_lesson_catalog.py / tests/test_lesson_practice_h.py", "headless", "Documented", ""),
])

BASE_HEADERS = [
    "ID", "Category", "Feature", "User Story", "Expected Behavior",
    "Source File(s)", "Feature test method", "Status", "Notes",
]
STORY_COLUMNS = [
    "Story",
    "Persona",
    "Expected behaviour",
    "Failure-mode expectation",
    "Test method",
    "Phase-2 result",
    "Errors found",
    "Phase-4 result",
]
EVIDENCE_COLUMNS = ["Latest check (UTC)", "Verification scope", "Behaviour status", "Remaining verification"]
HEADERS = BASE_HEADERS + STORY_COLUMNS + EVIDENCE_COLUMNS

ROOT = Path(__file__).resolve().parent
XLSX_PATH = ROOT / "AetherLab_Feature_Tracker.xlsx"
CSV_PATH = ROOT / "AetherLab_Feature_Tracker.csv"

PERSONA_LABELS = {
    "P1": "P1 Student, no AI key",
    "P2": "P2 Student, local Ollama",
    "P3": "P3 Educator, cloud AI + vision critic",
    "P4": "P4 Power user, cloud rendering",
    "P5": "P5 Returning user",
}

PERSONA_PRECONDITIONS = {
    "P1": "No cloud credentials or API key are required; offline/template paths must remain usable.",
    "P2": "Local-provider settings may point at Ollama; slow or malformed local output must degrade cleanly.",
    "P3": "AI-backed generation and optional visual critique may be configured; quality feedback must be visible.",
    "P4": "A render repository/token may be configured; local rendering and clear fallback remain available.",
    "P5": "The data directory may already contain settings, caches, history, progress, or old exported bundles.",
}

FAILURE_EXPECTATIONS = {
    "cloud": "If cloud credentials, workflow provisioning, polling, or artifact download fails, the user sees a masked, actionable status and local fallback remains available.",
    "render": "If rendering fails, times out, or returns a missing/corrupt video, the user sees a failure state and can retry without stale artifacts being treated as valid.",
    "lesson": "If lesson planning, chapter rendering, narration, or assembly fails, successful partial context is preserved and the user sees which step failed.",
    "settings": "If saved config, environment values, or legacy files are absent/corrupt, defaults are used and secrets are never exposed.",
    "cache": "If cached data is missing, stale, corrupt, or schema-drifted, the app rebuilds or falls back instead of surfacing stale paths or KeyErrors.",
    "export": "If an export target is unavailable or an asset is missing, the user gets a clear error and no share bundle leaks secrets or absolute private paths.",
    "default": "If the dependency, file, or service behind this feature is unavailable, the user sees a recoverable message instead of a stack trace or dead control.",
}


def _persona_for(category: str, feature: str, source: str) -> str:
    text = f"{category} {feature} {source}".lower()
    if any(key in text for key in ("cloud", "render repo", "github", "workflow")):
        return "P4"
    if any(key in text for key in ("ollama", "provider", "qwen", "local model")):
        return "P2"
    if any(key in text for key in ("history", "cache", "progress", "settings", "bundle", "export", "library")):
        return "P5"
    if any(key in text for key in ("critic", "quality", "prompt quality", "tournament", "exemplar")):
        return "P3"
    return "P1"


def _failure_expectation(category: str, feature: str, expected: str) -> str:
    text = f"{category} {feature} {expected}".lower()
    for key in ("cloud", "render", "lesson", "settings", "cache", "export"):
        if key in text:
            return FAILURE_EXPECTATIONS[key]
    return FAILURE_EXPECTATIONS["default"]


def _story_test_method(category: str, feature: str, source: str, legacy_method: str) -> str:
    text = f"{category} {feature} {source}".lower()
    if "cloud" in text and "github actions" in text:
        return "live-cloud"
    if legacy_method == "gui":
        return "scripted-ui"
    if legacy_method in {"headless", "static"}:
        return "harness"
    return "manual"


def _story_steps(feature: str, legacy_method: str) -> str:
    if legacy_method == "gui":
        return (
            f"1. Open AetherLab. 2. Navigate to the UI surface for {feature}. "
            "3. Perform the visible action. 4. Observe the window state, artifact, or message."
        )
    if legacy_method == "headless":
        return (
            f"1. Run the harness or command path for {feature}. "
            "2. Inspect the returned object, generated artifact, or persisted state."
        )
    return (
        f"1. Read and trigger the code path for {feature}. "
        "2. Assert the documented branch, guard, or wiring remains present."
    )


@lru_cache(maxsize=512)
def _python_definitions(path_text: str) -> tuple[tuple[str, str, int, str], ...]:
    """Index named code blocks in a Python file for precise tracker citations."""
    path = Path(path_text)
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, UnicodeError, SyntaxError):
        return ()

    definitions: list[tuple[str, str, int, str]] = []

    def visit(node: ast.AST, parent: str = "") -> None:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            qualified = f"{parent}.{node.name}" if parent else node.name
            doc = ast.get_docstring(node) or ""
            definitions.append((node.name, qualified, node.lineno, doc))
            if isinstance(node, ast.ClassDef):
                for child in node.body:
                    visit(child, qualified)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    definitions.append((target.id, target.id, node.lineno, ""))
        elif isinstance(node, ast.Module):
            for child in node.body:
                visit(child)

    visit(tree)
    return tuple(definitions)


@lru_cache(maxsize=1)
def _project_symbol_index() -> dict[str, tuple[tuple[str, str, int], ...]]:
    """Map implementation symbols to their real source lines."""
    indexed: dict[str, list[tuple[str, str, int]]] = {}
    for search_root in (ROOT / "aetherlab", ROOT / "tools"):
        if not search_root.exists():
            continue
        for path in sorted(search_root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            relpath = path.relative_to(ROOT).as_posix()
            for simple, qualified, lineno, _doc in _python_definitions(str(path)):
                entry = (relpath, qualified, lineno)
                indexed.setdefault(qualified, []).append(entry)
                if simple != qualified:
                    indexed.setdefault(simple, []).append(entry)
    return {key: tuple(value) for key, value in indexed.items()}


def _symbol_candidates(context: str) -> list[str]:
    candidates: list[str] = []
    patterns = (
        r"`([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)`",
        r"(?<![\w.-])((?:[A-Za-z_]\w*\.)*[A-Za-z_]\w*)\s*\(",
        r"(\b[A-Z][A-Za-z0-9_]{1,}\b)",
        r"(\b_?[a-z][A-Za-z0-9]*_[A-Za-z0-9_]+\b)",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, context):
            symbol = match.group(1)
            if symbol not in candidates:
                candidates.append(symbol)
    return candidates


def _symbols_line_refs(context: str, source_hint: str = "") -> list[str]:
    symbol_index = _project_symbol_index()
    refs: list[str] = []
    hint = source_hint.replace("\\", "/").lower()
    for symbol in _symbol_candidates(context):
        entries = symbol_index.get(symbol, ())
        if not entries and "." in symbol:
            entries = symbol_index.get(symbol.rsplit(".", 1)[-1], ())
        if not entries:
            continue
        sorted_entries = sorted(
            entries,
            key=lambda entry: (
                -int(bool(hint and entry[0].lower().split("/")[-1] in hint)),
                -int(bool(hint and "/".join(entry[0].lower().split("/")[:-1]) in hint)),
                entry[0],
                entry[2],
            ),
        )
        for path, _qualified, lineno in sorted_entries:
            ref = f"{path}:{lineno}"
            if ref not in refs:
                refs.append(ref)
                break
        if len(refs) >= 5:
            break
    return refs


def _source_candidates(token: str) -> list[Path]:
    # Keep a leading dot in paths such as `.github/workflows/render.yml`;
    # stripping it silently made those source references disappear.
    cleaned = token.strip().strip("(), ").rstrip(".,;").replace("\\", "/")
    if not cleaned:
        return []
    if cleaned.startswith(("aetherlab/", "tools/", "docs/", ".github/")):
        pattern = ROOT / cleaned
    elif cleaned == "__main__.py":
        pattern = ROOT / "aetherlab" / cleaned
    elif cleaned.startswith(("core/", "services/", "ui/")):
        pattern = ROOT / "aetherlab" / cleaned
    else:
        pattern = ROOT / cleaned

    candidates: list[Path] = []
    if "*" in cleaned:
        candidates = sorted(pattern.parent.glob(pattern.name))
    elif pattern.is_file():
        candidates = [pattern]
    elif pattern.is_dir():
        candidates = sorted(pattern.rglob("*.py"))
    if not candidates and pattern.suffix == ".py":
        matches = list((ROOT / "aetherlab").rglob(pattern.name))
        if len(matches) == 1:
            candidates = matches
    return [path for path in candidates if path.is_file()]


def _best_definition(path: Path, context: str) -> int | None:
    definitions = _python_definitions(str(path))
    if not definitions:
        return None
    symbols = _symbol_candidates(context)
    exact = [
        entry for entry in definitions
        if entry[0] in symbols or entry[1] in symbols
        or any(symbol.endswith(f".{entry[0]}") for symbol in symbols)
    ]
    if exact:
        return exact[0][2]

    def words(value: str) -> set[str]:
        expanded = re.sub(r"([a-z])([A-Z])", r"\1 \2", value)
        return {part.lower() for part in re.findall(r"[A-Za-z]{3,}", expanded)}

    context_words = words(context)
    ranked = sorted(
        definitions,
        key=lambda entry: (-len(words(f"{entry[0]} {entry[1]} {entry[3]}") & context_words), entry[2]),
    )
    return ranked[0][2]


def _best_config_line(path: Path, context: str) -> int | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return None
    context_words = {
        word.lower()
        for word in re.findall(r"[A-Za-z_]{3,}", context)
    }
    ranked: list[tuple[int, int]] = []
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "//")):
            continue
        line_words = {word.lower() for word in re.findall(r"[A-Za-z_]{3,}", stripped)}
        score = len(line_words & context_words)
        if score:
            ranked.append((score, number))
    return max(ranked, default=(0, 0), key=lambda item: (item[0], -item[1]))[1] or None


def _source_line_refs(source: str, context: str = "") -> str:
    """Return real implementation locations, preferring named symbols to file headers."""
    symbol_refs = _symbols_line_refs(context, source)
    refs = list(symbol_refs)
    if not refs:
        tokens = re.findall(r"[\w./*\\-]+\.(?:py|md|yml|json|bat)", source)
        for token in tokens:
            for path in _source_candidates(token):
                if path.parts[-2:-1] == ("tests",):
                    continue
                if path.suffix == ".py":
                    lineno = _best_definition(path, context)
                elif path.suffix in {".yml", ".yaml"}:
                    lineno = _best_config_line(path, context)
                else:
                    continue
                if lineno is not None:
                    refs.append(f"{path.relative_to(ROOT).as_posix()}:{lineno}")
                if len(refs) >= 5:
                    break
            if len(refs) >= 5:
                break
    return " / ".join(dict.fromkeys(refs))


def _attach_implementation_references(
    expected: str, source: str, context: str
) -> str:
    body = re.split(r"\s*Implementation reference:", expected, maxsplit=1)[0].rstrip(" .")
    refs = _source_line_refs(source, f"{context}\n{body}")
    return f"{body}. Implementation reference: {refs}." if refs else f"{body}."


def _story_tuple(
    story: str,
    persona: str,
    expected: str,
    failure: str,
    test_method: str,
    phase2: str = "PENDING",
    errors: str = "None",
    phase4: str = "PENDING",
) -> tuple[str, ...]:
    return (story, persona, expected, failure, test_method, phase2, errors, phase4)


STORY_OVERRIDES: dict[str, tuple[str, ...]] = {
    "F01": _story_tuple(
        "US-F01: As P1 Student, no AI key, when I run `python -m aetherlab`, I expect the desktop workbench to open with settings loaded. Preconditions: PyQt6 is installed. Steps: 1. Start the CLI with no flags. 2. Wait for the main window. 3. Close the app. Primary existing story: As a user, I run `python -m aetherlab` and the desktop app opens.",
        "P1",
        "`main()` parses flags, sets best-effort logging, imports `run_app`, and returns the Qt event-loop result; `run_app()` calls `require_qt()`, creates `QApplication`, loads settings, constructs `MainWindow`, shows it, and runs `app.exec()`. Implementation reference: aetherlab/__main__.py:72 / aetherlab/ui/app.py:24 / aetherlab/ui/qt_compat.py:18.",
        "If Qt import or launch raises RuntimeError, the CLI prints the actionable message to stderr and exits 2 instead of showing a traceback.",
        "scripted-ui",
    ),
    "F02": _story_tuple(
        "US-F02: As P1 Student, no AI key, when I run `python -m aetherlab --smoke`, I expect a headless pipeline summary that proves solve, RAG, and scene generation completed. Preconditions: no GUI is required; built-in fallback solving may be used. Steps: 1. Run the smoke command. 2. Read stdout. 3. Confirm cache key, solver, keywords, RAG count, scene engine, and scene status are printed.",
        "P1",
        "`--smoke` runs `_run_smoke()`, builds `AetherLabPipeline(load_settings())`, awaits `pipeline.run(ProblemRequest(prompt=...))`, then prints cache key, solver model, keywords or `none`, RAG hit count, scene engine, and scene status before returning 0. Implementation reference: aetherlab/__main__.py:23 / aetherlab/__main__.py:57.",
        "If the pipeline raises, the CLI process fails rather than launching a half-initialized GUI; test harnesses catch this as a non-zero smoke result.",
        "harness",
    ),
    "F03": _story_tuple(
        "US-F03: As P1 Student, no AI key, when I pass a prompt after `--smoke`, I expect that exact prompt to drive the headless run. Preconditions: CLI is available. Steps: 1. Run `python -m aetherlab --smoke \"custom prompt\"`. 2. Compare behaviour with the default smoke run. 3. Confirm argparse accepted the custom string.",
        "P1",
        "`build_parser()` defines `--smoke` with `nargs='?'`, a default const prompt, and user-provided prompt override; `main()` passes `args.smoke` to `_run_smoke()`. Implementation reference: aetherlab/__main__.py:17 / aetherlab/__main__.py:23 / aetherlab/__main__.py:86.",
        "If the prompt is omitted, argparse uses the built-in damped-oscillator smoke prompt; if invalid CLI flags are passed, argparse exits with its normal usage error.",
        "harness",
    ),
    "F04": _story_tuple(
        "US-F04: As P5 Returning user, when the GUI process crashes under the watchdog, I expect AetherLab to restart with increasing delay, but a normal close should stop. Preconditions: watchdog is launched from the project root. Steps: 1. Start `aetherlab_watchdog.py` or `start.bat`. 2. Let the child exit non-zero. 3. Observe restart logging; then close cleanly and observe no relaunch.",
        "P5",
        "`aetherlab_watchdog.main()` runs `[sys.executable, '-m', 'aetherlab']`, logs exit code and uptime, stops on exit code 0, resets delay after a healthy run, and otherwise sleeps with exponential backoff capped at 60 seconds. Implementation reference: aetherlab_watchdog.py:37.",
        "If the child cannot start, the exception is logged, treated as exit -1, and the watchdog follows the same backoff path instead of crashing.",
        "harness",
    ),
    "F05": _story_tuple(
        "US-F05: As P1 Student, no AI key, when PyQt6 is missing, I expect an install hint instead of a Python stack trace. Preconditions: PyQt6 import fails. Steps: 1. Trigger `require_qt()` through app launch or directly in a harness. 2. Read stderr/exception text. 3. Confirm it names PyQt6 and a pip install command.",
        "P1",
        "`require_qt()` raises RuntimeError with a PyQt6 install instruction when the optional import shim captured an import error; `main()` catches RuntimeError from import/run_app and exits 2. Implementation reference: aetherlab/ui/qt_compat.py:18 / aetherlab/__main__.py:91 / aetherlab/__main__.py:97.",
        "The sad path is the feature: missing Qt returns an actionable message and exit code 2, not an uncaught import traceback.",
        "harness",
    ),
    "F06": _story_tuple(
        "US-F06: As P5 Returning user, when I launch with AETHERLAB, OpenAI, or compatible manim-bot environment values, I expect settings to reflect the highest-precedence explicit values. Preconditions: environment variables may be set; app config and legacy `.env` may also exist. Steps: 1. Set data/model/key/base-url/timeout variables. 2. Call `load_settings()`. 3. Verify paths, provider fields, timeout, and migration aliases.",
        "P5",
        "`load_settings()` reads AETHERLAB data/cache/chroma/library paths, OpenAI-compatible model/key/base URL aliases, LLM timeout, provider preset, legacy manim-bot `.env`, cloud aliases, and visual critic settings into `AppSettings`. Implementation reference: aetherlab/core/settings.py:106 / aetherlab/core/settings.py:133 / aetherlab/core/settings.py:137 / aetherlab/core/settings.py:185 / aetherlab/core/settings.py:317.",
        "If config files are absent or corrupt, loaders return empty mappings and defaults are used; secrets are read into settings but are not logged.",
        "harness",
    ),
    "F07": _story_tuple(
        "US-F07: As P5 Returning user, when I save fields in Settings, I expect non-empty values to survive restart and empty values to be removed. Preconditions: a writable data directory exists. Steps: 1. Save app config values. 2. Reload app config. 3. Call `load_settings()` and confirm saved path/provider values flow into settings.",
        "P5",
        "`app_config_path()` is under the AetherLab data dir, `save_app_config()` merges new values while dropping empty/None keys, and `load_app_config()` ignores missing/corrupt JSON. `load_settings()` uses saved data_dir/library/provider values below env precedence. Implementation reference: aetherlab/core/settings.py:71 / aetherlab/core/settings.py:76 / aetherlab/core/settings.py:92 / aetherlab/core/settings.py:106.",
        "If settings.json is missing, unreadable, or invalid JSON, the app falls back to defaults instead of blocking startup.",
        "harness",
    ),
    "F08": _story_tuple(
        "US-F08: As P5 Returning user, when the same provider value exists in env, app config, legacy `.env`, and Qwen settings, I expect the documented precedence to choose the explicit environment value first. Preconditions: conflicting provider tiers are available. Steps: 1. Seed app config and legacy mappings. 2. Set an env override. 3. Call `load_settings()` and inspect provider fields/source.",
        "P5",
        "`load_settings()` resolves model, API key, and base URL as environment, then app config, then legacy manim-bot `.env`, then opt-in Qwen settings; `provider_source` labels the winning tier. Implementation reference: aetherlab/core/settings.py:106 / aetherlab/core/settings.py:133 / aetherlab/core/settings.py:137 / aetherlab/core/settings.py:143 / aetherlab/core/settings.py:151 / aetherlab/core/settings.py:292.",
        "If lower-precedence files are corrupt or missing, they are skipped; if env values are blank, they do not override saved usable values.",
        "harness",
    ),
    "F09": _story_tuple(
        "US-F09: As P2 Student, local Ollama, when I intentionally opt into Qwen-compatible settings, I expect AetherLab to parse model, base URL, and API key without silently inheriting credentials by default. Preconditions: a Qwen settings JSON exists and `AETHERLAB_QWEN_AUTOLOAD=1` is set for full settings use. Steps: 1. Call `load_qwen_settings(path)` on a valid Qwen file. 2. Call `load_settings()` with and without the opt-in env. 3. Confirm default launches do not auto-use Qwen credentials.",
        "P2",
        "`load_qwen_settings()` reads model name, OpenAI provider baseUrl, envKey/env API key, and source; `load_settings()` only consults it when `AETHERLAB_QWEN_AUTOLOAD == '1'`. Implementation reference: aetherlab/core/settings.py:129 / aetherlab/core/settings.py:403.",
        "If the Qwen file is absent, corrupt, or not opted in, `{}` is returned or ignored and the app uses the next available/default provider without leaking secrets.",
        "harness",
        errors="BUG-24",
    ),
    "F10": _story_tuple(
        "US-F10: As P5 Returning user, when I open Settings, edit provider/rendering/path fields, and press Save, I expect the dialog to stay usable on small screens and persist the chosen values. Preconditions: main window is open with writable app config. Steps: 1. Press Ctrl+, or the gear. 2. Edit provider, quality, render mode, GitHub fields, library path, and data path. 3. Save and inspect the status message/reloaded settings.",
        "P5",
        "`SettingsDialog` builds a scrollable screen-fitted form, hides secret values, shows active provider/model/exact key source and shadow warnings, and exposes timeout/retry controls; `_open_settings()` saves through `save_app_config()` then calls `load_settings()` so current and restarted precedence match. Implementation reference: aetherlab/ui/main_window.py / aetherlab/ui/provider_status.py / aetherlab/core/settings.py.",
        "Cancel rejects without saving; corrupt config falls back to defaults; environment overrides remain active immediately after Save and are named without displaying credential values.",
        "scripted-ui",
    ),
    "F11": _story_tuple(
        "US-F11: As P5 Returning user, when I first launch on Windows or another OS, I expect AetherLab data and Chroma directories to be placed in a stable per-user location. Preconditions: `LOCALAPPDATA` may or may not be set. Steps: 1. Clear explicit path env vars. 2. Call `load_settings()`. 3. Inspect data_dir and chroma_path.",
        "P5",
        "`_default_data_dir()` and `_default_chroma_path()` use `%LOCALAPPDATA%/AetherLab` on Windows-like environments and `~/.aetherlab` elsewhere; `load_settings()` derives default cache/library paths from that data dir. Implementation reference: aetherlab/core/settings.py:106 / aetherlab/core/settings.py:433 / aetherlab/core/settings.py:441.",
        "If LOCALAPPDATA is absent, paths still resolve under the user's home directory; no launch-working-directory cache is used by default.",
        "harness",
    ),
    "F12": _story_tuple(
        "US-F12: As P1 Student, no AI key, when I type a prompt and press Enter, Run, or Ctrl+Enter, I expect one solve run to start and the prompt field to clear. Preconditions: command bar is visible and not busy. Steps: 1. Type a non-empty prompt. 2. Press Enter or Run, or use Ctrl+Enter from the main window. 3. Observe the submitted signal/start pipeline and cleared input.",
        "P1",
        "`CommandBar._submit()` trims text, emits `submitted(prompt)`, and clears the field only while Run is visible; `MainWindow._build_shortcuts()` wires Ctrl+Return to the same submit path and `_connect_signals()` wires submitted to `start_pipeline()`. Implementation reference: aetherlab/ui/widgets.py:782 / aetherlab/ui/main_window.py:774 / aetherlab/ui/main_window.py:794.",
        "Empty prompts and busy/cancel state do nothing, preventing duplicate blank runs or submit while the cancel button is active.",
        "scripted-ui",
    ),
    "F13": _story_tuple(
        "US-F13: As P1 Student, no AI key, when I open Examples and choose a prompt, I expect the prompt field to fill and focus without starting a run. Preconditions: command bar is visible. Steps: 1. Click Examples. 2. Pick a listed prompt. 3. Confirm it appears in the field and focus returns there.",
        "P1",
        "`CommandBar._show_examples_menu()` creates a QMenu from `EXAMPLE_PROMPTS`, truncates long labels for display, anchors the menu above the button, and `_pick_example()` writes the full prompt into the input and focuses it. Implementation reference: aetherlab/ui/widgets.py:609 / aetherlab/ui/widgets.py:745 / aetherlab/ui/widgets.py:760.",
        "If the menu is dismissed without choosing, no prompt is changed and no run starts.",
        "scripted-ui",
    ),
    "F14": _story_tuple(
        "US-F14: As P1 Student, no AI key, when I choose Draft, Standard, or High, I expect the selected render quality to be passed to Manim as l, m, or h. Preconditions: command bar is visible. Steps: 1. Select each quality. 2. Read `get_render_quality()`. 3. Start a run and inspect worker render_quality.",
        "P1",
        "`CommandBar._QUALITIES` maps Draft/Standard/High to `l/m/h`; `get_render_quality()` returns the current flag with Draft fallback, `set_quality()` selects by flag, and `MainWindow.start_pipeline()` passes the flag to `PipelineWorker`. Implementation reference: aetherlab/ui/widgets.py:640 / aetherlab/ui/widgets.py:764 / aetherlab/ui/widgets.py:769 / aetherlab/ui/main_window.py:1326.",
        "Unknown quality text falls back to Draft (`l`) rather than passing an invalid Manim quality flag.",
        "harness",
    ),
    "F15": _story_tuple(
        "US-F15: As P1 Student, no AI key, when a run starts, I expect Run/Learn to disappear, Cancel to appear, and the prompt field to be disabled until the run ends or is cancelled. Preconditions: command bar is idle. Steps: 1. Start a solve run. 2. Observe button/input state. 3. Cancel or finish and observe idle state restored.",
        "P1",
        "`CommandBar.set_busy()` hides Run and Learn, shows Cancel, and disables input; `start_pipeline()` calls it true, `_on_worker_finished()` calls it false, and `_cancel_pipeline()` resets it immediately on cancellation. Implementation reference: aetherlab/ui/widgets.py:776 / aetherlab/ui/main_window.py:1131 / aetherlab/ui/main_window.py:1326 / aetherlab/ui/main_window.py:1378.",
        "If cancellation happens during loading, `_cancel_pipeline()` also hides the simulation loading surface and returns to the best available page.",
        "scripted-ui",
    ),
    "F16": _story_tuple(
        "US-F16: As P1 Student, no AI key, when I submit a physics prompt, I expect the solve pipeline to progress through solver, references, scene generation, render, and final result. Preconditions: prompt is non-empty; local fallback generation is allowed. Steps: 1. Submit a prompt. 2. Watch Running view/status updates. 3. Confirm analysis, references, scene, video, and history are updated.",
        "P1",
        "`PipelineWorker._run_async()` ensures a cache key, solves or reuses solver output, ingests/searches references, generates/reuses scene code, renders/reuses MP4, emits intermediate ready signals, and finally emits `PipelineResult`; MainWindow handlers update the panels. Implementation reference: aetherlab/ui/workers.py:69 / aetherlab/ui/workers.py:174 / aetherlab/ui/main_window.py:1413 / aetherlab/ui/main_window.py:1421.",
        "If any stage raises, `PipelineWorker.run()` emits a `PipelineError`; `MainWindow.on_failure()` shows status, toast details, error banner, and returns to a recoverable page.",
        "harness",
    ),
    "F17": _story_tuple(
        "US-F17: As P1 Student, no AI key, when a pipeline run advances, I expect the Running view and stepper to show the current stage and reset cleanly for the next run. Preconditions: a solve run is active. Steps: 1. Start a run. 2. Observe progress labels for Solve/RAG/Scene/Render. 3. Start another run and confirm elapsed/stage state does not leak.",
        "P1",
        "`MainWindow.start_pipeline()` resets and shows the timeline, marks the stepper cancellable, sets stage 0, and `_on_progress()` maps progress percentages to Solve/RAG/Scene/Render stage states and RunningView text. Implementation reference: aetherlab/ui/main_window.py:1326 / aetherlab/ui/main_window.py:1378.",
        "If the run is cancelled or fails, the stepper becomes non-cancellable and moves to the cancelled/error state instead of leaving stale active UI.",
        "scripted-ui",
    ),
    "F18": _story_tuple(
        "US-F18: As P1 Student, no AI key, when I cancel a solve in progress, I expect queued or active rendering to stop promptly and the app to become usable again. Preconditions: a solve worker is running. Steps: 1. Start a run. 2. Press Cancel or Escape during a stage or local/cloud render. 3. Observe honest cancelling status, process cleanup, idle command bar, and no stale loading screen.",
        "P1",
        "`PipelineWorker.cancel()` sets a cancellation flag and `_check_cancelled()` raises between major stages. The same callback reaches tournament/single rendering, cancellible semaphore waits, cloud polling, and `run_process_tree()`, which terminates the full local Manim process tree. MainWindow remains visibly busy until QThread.finished confirms cleanup, then restores Run and reports cancellation. Implementation reference: aetherlab/ui/workers.py / aetherlab/services/manim_runtime.py / aetherlab/services/render_backend.py / aetherlab/core/proc.py / aetherlab/ui/main_window.py.",
        "Provider calls remain bounded by their configured request timeout, but queued/active local renders and cloud poll loops stop on cancellation; no false-ready UI appears before cleanup.",
        "scripted-ui",
    ),
    "F19": _story_tuple(
        "US-F19: As P1 Student, no AI key, when I try to start a second solve while one is running, I expect AetherLab to refuse the duplicate run and keep the current one intact. Preconditions: `self.worker` is running. Steps: 1. Start a run. 2. Submit another prompt before it finishes. 3. Read the status bar.",
        "P1",
        "`MainWindow.start_pipeline()` checks `self.worker.isRunning()` and returns after showing `Pipeline is already running.` before allocating a new worker. Implementation reference: aetherlab/ui/main_window.py:1326.",
        "The duplicate attempt does not disconnect signals, delete the current worker, clear current progress, or enqueue a hidden second run.",
        "scripted-ui",
    ),
    "F20": _story_tuple(
        "US-F20: As P5 Returning user, when I run another solve after a previous worker finished, I expect old worker signals to be disconnected so callbacks do not multiply. Preconditions: a completed worker object may still be attached. Steps: 1. Finish one run. 2. Start another. 3. Confirm old signals are disconnected and the stale worker is scheduled for deletion.",
        "P5",
        "`MainWindow.start_pipeline()` disconnects status/ready/failure/finished/progress signals from an existing non-running worker inside a guarded block, calls `deleteLater()`, clears `self.worker`, then constructs and wires a fresh `PipelineWorker`. Implementation reference: aetherlab/ui/main_window.py:1326.",
        "If a signal was already disconnected or the worker was deleted, TypeError/RuntimeError is ignored and a fresh worker is still created.",
        "harness",
    ),
    "F21": _story_tuple(
        "US-F21: As P5 Returning user, when I close AetherLab during a solve or lesson, I expect background work to be asked to stop and the window to close without orphaning known Qt workers. Preconditions: a solve worker, lesson worker, or Ollama probe may be running. Steps: 1. Start a run. 2. Close the window. 3. Confirm workers receive cancel/wait and close continues.",
        "P5",
        "`MainWindow.closeEvent()` cancels solve/lesson work, waits up to 5000 ms for each known thread, and if any remains running ignores the close event, connects `finished` to `_close_when_idle()`, then retries close only when all workers are idle. Implementation reference: aetherlab/ui/main_window.py.",
        "If a worker does not stop within the wait window, the window stays alive in cancelling state and closes automatically after `finished`; it never destroys or forcibly terminates a running QThread.",
        "scripted-ui",
    ),
    "F22": _story_tuple(
        "US-F22: As P3 Educator, cloud AI + vision critic, when I solve with an API key, I expect the remote model to return structured analysis, variables, keywords, equations, and optional plot data. Preconditions: an OpenAI-compatible key/model/base URL are configured. Steps: 1. Submit a prompt. 2. Let the remote solve complete. 3. Inspect the solver summary, steps, keywords, variables, equations, and raw plot payload.",
        "P3",
        "`AsyncLLMCoordinator.solve()` calls `_solve_remote()` when an API key exists; `_solve_remote()` lazy-creates `AsyncOpenAI`, sends a strict JSON system prompt at temperature 0.2, parses the response, coerces variables to floats, limits key equations to four, and keeps plot only when it is a dict. Implementation reference: aetherlab/services/llm.py:80 / aetherlab/services/llm.py:91 / aetherlab/services/llm.py:149.",
        "If the remote call or JSON handling raises, `solve()` falls back to the deterministic solver with a note naming the remote failure.",
        "harness",
    ),
    "F23": _story_tuple(
        "US-F23: As P1 Student, no AI key, when I solve offline or the remote model fails, I expect a useful deterministic scaffold instead of a dead run. Preconditions: no API key, or remote solve raises. Steps: 1. Submit a physics prompt. 2. Inspect the fallback solver result. 3. Confirm it has steps, keywords, variables, equations, and a plot payload.",
        "P1",
        "`solve()` calls `_fallback()` without an API key or after remote failure; `_fallback()` extracts keywords, merges default variables with request parameters, emits five scaffold steps, sets model_name to `deterministic-fallback`, selects fallback equations by domain, and attaches `fallback_plot_payload()`. Implementation reference: aetherlab/services/llm.py:80 / aetherlab/services/llm.py:176 / aetherlab/services/plotting.py:351.",
        "If keyword extraction finds nothing, fallback keywords default to differential equation, phase space, and stability so downstream RAG/scene paths still have input.",
        "harness",
    ),
    "F24": _story_tuple(
        "US-F24: As P1 Student, no AI key, when I write a prompt with physics phrases, I expect retrieval keywords to include important multi-word concepts before generic tokens. Preconditions: any solve prompt. Steps: 1. Call keyword extraction with spaced and hyphenated phrases. 2. Inspect the ranked keyword list. 3. Confirm phrase matches are prepended and limited.",
        "P1",
        "`extract_keywords()` tokenizes alphabetic words, drops common words, ranks by frequency, then prepends known phrase matches such as Fourier transform and Navier Stokes, accepting both spaced and hyphenated forms, and returns at most the requested limit. Implementation reference: aetherlab/services/llm.py:213.",
        "If no phrase is present, the ranked token list is returned; empty prompt downstream falls back in the deterministic solver.",
        "harness",
    ),
    "F25": _story_tuple(
        "US-F25: As P2 Student, local Ollama, when a reasoning model wraps JSON in thinking text or prose fences, I expect AetherLab to recover the first valid object. Preconditions: remote or local model response text may include `<think>` blocks or surrounding prose. Steps: 1. Feed wrapped response content to the parser. 2. Confirm think text is removed. 3. Confirm exact JSON or first brace block is parsed.",
        "P2",
        "`_parse_json()` removes `<think>...</think>` spans, tries `json.loads()` on the cleaned content, and if that fails extracts the first `{...}` block with DOTALL regex and parses it. Implementation reference: aetherlab/services/llm.py:164.",
        "If no parseable object exists, JSONDecodeError propagates to `solve()`, which uses deterministic fallback rather than breaking the user run.",
        "harness",
    ),
    "F26": _story_tuple(
        "US-F26: As P3 Educator, cloud AI + vision critic, when the solver supplies a plot, I expect the raw plot description to be preserved for canvas validation instead of being trusted early. Preconditions: remote JSON contains a `plot` key. Steps: 1. Parse a solver payload with dict and non-dict plot variants. 2. Inspect SolverResult.plot. 3. Build canvas state to validate expressions later.",
        "P3",
        "`_solve_remote()` reads `payload['plot']` and stores it only if it is a dict; `SolverResult.from_json()` keeps dict plots for old/new caches while rejecting non-dict values. Plot syntax is validated by the plotting/canvas path, not by the solver parser. Implementation reference: aetherlab/services/llm.py:149 / aetherlab/core/models.py:45 / aetherlab/core/models.py:59.",
        "Malformed or non-dict plot payloads become None, so the canvas can fall back to domain/default curves instead of crashing.",
        "harness",
    ),
    "F27": _story_tuple(
        "US-F27: As P1 Student, no AI key, when solver-provided math expressions render, I expect only whitelisted numeric math to execute. Preconditions: plot payload contains expression strings and variables. Steps: 1. Compile allowed expressions. 2. Try names/calls/operators outside the whitelist. 3. Confirm unsafe syntax is rejected before evaluation.",
        "P1",
        "`compile_expression()` limits length, normalizes `^` to `**`, parses AST in eval mode, validates only numeric constants, load names from params/t/constants/functions, whitelisted ops and functions, converts int literals to float, and evaluates with empty builtins. Implementation reference: aetherlab/services/plotting.py:62 / aetherlab/services/plotting.py:105 / aetherlab/services/plotting.py:156.",
        "Unsafe names, calls, assignment contexts, unsupported operators, bool constants, or syntax errors raise ExprError and prevent arbitrary code execution.",
        "harness",
    ),
    "F28": _story_tuple(
        "US-F28: As P1 Student, no AI key, when a plot expression is huge, pathological, or numerically unstable, I expect bounded failure or non-finite samples instead of a hang. Preconditions: expression compiler receives adversarial expressions or ranges. Steps: 1. Try overlong and oversized AST expressions. 2. Try overflow and division by zero. 3. Compile a plot with too-large t span.",
        "P1",
        "`MAX_EXPR_CHARS`, `MAX_AST_NODES`, and `MAX_T_SPAN` bound expression/range size; `_IntToFloat` avoids giant integer materialization; runtime OverflowError becomes inf, ZeroDivisionError becomes nan, and scalar outputs broadcast to the sample grid. Implementation reference: aetherlab/services/plotting.py:27 / aetherlab/services/plotting.py:101 / aetherlab/services/plotting.py:115 / aetherlab/services/plotting.py:285.",
        "Invalid complexity or range input raises ExprError; numeric non-finite outputs are left for the canvas filtering path rather than crashing compilation.",
        "harness",
    ),
    "F29": _story_tuple(
        "US-F29: As P1 Student, no AI key, when a plot payload is malformed, I expect validation to reject it and fallback plotting to remain available. Preconditions: plot payload may be explicit, parametric, legacy single-curve, or multi-curve. Steps: 1. Compile valid payloads. 2. Try wrong kind/ranges/curves. 3. Confirm fallback_plot_payload gives a deterministic damped oscillator plot.",
        "P1",
        "`compile_plot()` requires an object kind in explicit/parametric, finite t/x/y pairs with lo < hi, clamps large t spans, compiles legacy or multi-curve entries, limits curves/points/labels, chooses the primary curve, and `fallback_plot_payload()` emits a safe multi-curve damped oscillator. Implementation reference: aetherlab/services/plotting.py:204 / aetherlab/services/plotting.py:269 / aetherlab/services/plotting.py:351.",
        "Malformed payloads raise ExprError and the UI can use generated/domain fallback curves instead of showing an exception.",
        "harness",
    ),
    "F30": _story_tuple(
        "US-F30: As P5 Returning user, when I repeat the same problem with whitespace or parameter-order changes, I expect it to map to the same cache entry. Preconditions: session cache path is writable. Steps: 1. Build equivalent ProblemRequest objects. 2. Call make_key. 3. Confirm the hashes match.",
        "P5",
        "`SessionCache.make_key()` JSON-serializes `ProblemRequest.canonical_payload()` with sorted keys and compact separators, then hashes the UTF-8 bytes with SHA-256. Implementation reference: aetherlab/core/cache.py:37.",
        "If the canonical payload genuinely differs, a different key is produced so unrelated requests do not collide intentionally.",
        "harness",
    ),
    "F31": _story_tuple(
        "US-F31: As P5 Returning user, when only part of a run has completed, I expect cached stages to be reused independently on the next run. Preconditions: a cache row exists. Steps: 1. Store solver, RAG, and scene artifacts separately. 2. Reopen the cache. 3. Confirm each artifact rehydrates with cached=True and bad column names are rejected.",
        "P5",
        "`SessionCache` stores solver_json, rag_json, and scene_json independently, decodes each field fail-soft, rejects columns outside the artifact whitelist, verifies the database with `PRAGMA quick_check(1)`, and preserves a corrupt DB/WAL/SHM under a timestamped `.corrupt-*` name before rebuilding. Implementation reference: aetherlab/core/cache.py.",
        "Malformed artifact JSON becomes an isolated cache miss; an invalid/corrupt SQLite file is quarantined and replaced by an empty usable cache, while lock/permission errors still surface instead of moving a healthy database.",
        "harness",
    ),
    "F32": _story_tuple(
        "US-F32: As P5 Returning user, when my provider/model changes, I expect stale fallback or wrong-model solver output to be recomputed. Preconditions: a cached SolverResult exists. Steps: 1. Cache deterministic and wrong-model solver results. 2. Change settings to include an API key or a different model. 3. Confirm solver cache usability rejects stale output.",
        "P5",
        "`AetherLabPipeline._solver_cache_usable()` and `PipelineWorker._solver_cache_usable()` reject deterministic fallback once an API key is configured and reject model names that are neither deterministic-fallback nor the current settings model. Implementation reference: aetherlab/services/pipeline.py:102 / aetherlab/ui/workers.py:208.",
        "A rejected solver cache forces a fresh solve path instead of silently mixing old model assumptions into new runs.",
        "harness",
    ),
    "F33": _story_tuple(
        "US-F33: As P5 Returning user, when my Manim engine or scene status changes, I expect the scene cache to regenerate rather than replay incompatible code. Preconditions: cached SceneBundle exists. Steps: 1. Detect current engine. 2. Compare cached engine/status. 3. Confirm only compiled/rendered scenes from the current engine are reused.",
        "P5",
        "The headless pipeline and UI worker both compare cached scene engine to `current_engine` and require status in compiled/rendered before reuse; quality-score cache gating may reject low-score scenes. Implementation reference: aetherlab/services/pipeline.py:44 / aetherlab/services/pipeline.py:109 / aetherlab/ui/workers.py:97 / aetherlab/ui/workers.py:266.",
        "Mismatched engine, unsupported status, or failed quality threshold forces scene regeneration instead of a stale visual artifact.",
        "harness",
    ),
    "F34": _story_tuple(
        "US-F34: As P5 Returning user, when a cached rendered video path is missing, empty, or corrupt, I expect AetherLab to rebuild or re-render instead of opening the broken MP4. Preconditions: a cached SceneBundle has status rendered and a bad video_path. Steps: 1. Place a fake MP4 at the cached path. 2. Run headless and UI cache checks. 3. Confirm both reject the cache and clear stale video before rendering.",
        "P5",
        "`_video_exists()` rejects blank, missing, zero-byte, no-video-stream, and undecodable MP4s; the headless pipeline downgrades stale rendered scenes to compiled, and the UI worker now uses the same playable-video guard for cache usability and render decisions. Implementation reference: aetherlab/services/pipeline.py:56 / aetherlab/services/pipeline.py:116 / aetherlab/ui/workers.py:154 / aetherlab/ui/workers.py:266.",
        "If PyAV is unavailable, the helper falls back to a conservative size check; if validation fails, the app renders again rather than surfacing a stale path.",
        "harness",
        errors="BUG-23; BUG-25",
    ),
    "F35": _story_tuple(
        "US-F35: As P3 Educator, cloud AI + vision critic, when ChromaDB is available with indexed textbooks, I expect references to come from vector similarity with comparable scores. Preconditions: chroma_path exists and collection `textbooks` is present. Steps: 1. Search non-empty keywords. 2. Inspect returned hits. 3. Confirm backend, excerpts, pages, and scores.",
        "P3",
        "`LocalVectorRag.search()` tries `_try_chromadb()` first; Chroma queries the `textbooks` collection with joined keywords, converts distances to `1/(1+distance)`, trims document excerpts, preserves path/page metadata, and returns backend `chromadb`. Implementation reference: aetherlab/services/rag.py:21 / aetherlab/services/rag.py:32 / aetherlab/services/rag.py:62.",
        "If ChromaDB is missing, path absent, collection/query fails, or no usable result appears, search falls back to filesystem retrieval.",
        "harness",
    ),
    "F36": _story_tuple(
        "US-F36: As P1 Student, no AI key, when ChromaDB is absent but library files exist, I expect keyword-matched local excerpts with normalized relevance scores. Preconditions: library path contains text, markdown, tex, or PDF files. Steps: 1. Search keywords with no ChromaDB path. 2. Inspect filesystem hits. 3. Confirm scores are normalized to 0-1 and excerpts center on matches.",
        "P1",
        "`_filesystem_search()` walks supported text/PDF files, samples PDFs, scores keyword counts, sorts top hits, then normalizes the top scores against the strongest hit so UI pills remain comparable to ChromaDB relevance. Implementation reference: aetherlab/services/rag.py:64 / aetherlab/services/rag.py:86.",
        "Unreadable files, unsupported suffixes, missing PDF tooling, or no matches are skipped without failing the solve path.",
        "harness",
    ),
    "F37": _story_tuple(
        "US-F37: As P1 Student, no AI key, when there are no keywords or no library, I expect an explanatory empty references state. Preconditions: keyword list may be empty or library path missing. Steps: 1. Search with empty keywords. 2. Search with a missing library. 3. Open the reference panel with the result.",
        "P1",
        "`LocalVectorRag.search()` returns backend `none` for empty keyword input and `_filesystem_search()` returns backend `filesystem-missing-library` when the library directory does not exist; `ReferencePanel.set_rag_result()` shows a tailored empty message and clears backend label when hits are empty. Implementation reference: aetherlab/services/rag.py:21 / aetherlab/services/rag.py:64 / aetherlab/ui/widgets.py:1387.",
        "No-keyword and missing-library cases do not raise; the user is told to add PDFs/text files to the library directory.",
        "harness",
    ),
    "F38": _story_tuple(
        "US-F38: As P1 Student, no AI key, when references are found, I expect readable cards with provenance, excerpt copy, relevance colour, and Open affordance. Preconditions: RAG result has one or more hits. Steps: 1. Set the reference panel result. 2. Inspect each card. 3. Click copy/open where available.",
        "P1",
        "`_RagHitCard` renders source/page or web badge, score pill colours at >=0.8 emerald and >=0.5 amber, dims low scores, copies excerpts to clipboard, and opens local paths or URLs with `QDesktopServices`; `ReferencePanel` shows backend plus library/web counts. Implementation reference: aetherlab/ui/widgets.py:1258 / aetherlab/ui/widgets.py:1320 / aetherlab/ui/widgets.py:1343 / aetherlab/ui/widgets.py:1415.",
        "If a hit has no source path, the Open button is omitted; if no hits exist, cards are cleared and empty copy appears.",
        "scripted-ui",
    ),
    "F39": _story_tuple(
        "US-F39: As P5 Returning user, when I run the pipeline for the first time with a library, I expect AetherLab to index textbooks automatically before retrieval. Preconditions: Chroma collection is missing or empty and library_path exists. Steps: 1. Start a headless or UI solve. 2. Observe the ingest step. 3. Confirm subsequent searches can use indexed chunks.",
        "P5",
        "`AetherLabPipeline._ensure_ingested()` and `PipelineWorker._ensure_ingested()` check whether ChromaDB collection `textbooks` exists and has rows; if empty and the library path exists, they call `LibraryIngestor.ingest()` before/around retrieval, swallowing optional Chroma errors so filesystem fallback still works. Implementation reference: aetherlab/services/pipeline.py:77 / aetherlab/ui/workers.py:185.",
        "If ChromaDB is unavailable or ingestion fails, the solve continues with filesystem fallback rather than blocking the user.",
        "harness",
    ),
    "F40": _story_tuple(
        "US-F40: As P5 Returning user, when I re-index a library, I expect unchanged files to be skipped and changed files to replace stale chunks. Preconditions: ingest manifest may already exist. Steps: 1. Ingest a library. 2. Run pending_files with no changes. 3. Modify one file and ingest again. 4. Confirm only changed files process and manifest updates atomically.",
        "P5",
        "`LibraryIngestor.pending_files()` compares manifest mtime/size signatures, `ingest()` processes only `_needs_ingest()` files unless reset, deletes old chunks for a changed path before upsert, records chunk count per completed file, and writes the manifest via tmp file then replace. Implementation reference: aetherlab/services/ingestion.py:93 / aetherlab/services/ingestion.py:114 / aetherlab/services/ingestion.py:125 / aetherlab/services/ingestion.py:200 / aetherlab/services/ingestion.py:213.",
        "If ingest is cancelled mid-file, completed chunks remain but the file is not written to the manifest, so the next run reprocesses it cleanly.",
        "harness",
    ),
    "F41": _story_tuple(
        "US-F41: As P5 Returning user, when I index long textbook text, I expect chunks to be large enough for context but overlap so ideas do not split abruptly. Preconditions: a supported text-like file is readable. Steps: 1. Feed long text to chunk_text. 2. Inspect chunk lengths and overlap. 3. Confirm sentence/newline break preferences.",
        "P5",
        "`chunk_text()` compacts whitespace, emits roughly 1400-character windows with 180-character overlap, and prefers breakpoints after `. `, `; `, or newline beyond the halfway point before falling back to the hard window. Implementation reference: aetherlab/services/ingestion.py:33.",
        "Empty or whitespace-only text produces no chunks; very short text produces a single trimmed chunk.",
        "harness",
    ),
    "F42": _story_tuple(
        "US-F42: As P5 Returning user, when I add PDFs to the library, I expect each readable page to become page-tagged retrieval chunks. Preconditions: PyMuPDF may be installed; PDFs may be valid or broken. Steps: 1. Ingest a PDF. 2. Inspect TextChunk metadata. 3. Try an unreadable/renamed PDF and confirm ingest does not crash.",
        "P5",
        "`_chunks_from_pdf()` imports fitz lazily, opens the PDF, iterates pages, chunks extracted text per page, and records path, source name, page number, and chunk index metadata. Import/open failures return an empty list. Implementation reference: aetherlab/services/ingestion.py:250.",
        "If fitz is unavailable or the file cannot be opened as a PDF, the file is skipped silently and the broader ingest run continues.",
        "harness",
    ),
    "F43": _story_tuple(
        "US-F43: As P5 Returning user, when indexing is long-running, I expect batched progress, cancellation between batches, reset rebuilds, and no stale chunks after a file changes. Preconditions: ChromaDB is available and the library has supported files. Steps: 1. Start ingest. 2. Cancel during a file. 3. Re-run and reset once. 4. Confirm changed file chunks replace old path chunks.",
        "P5",
        "`LibraryIngestor.ingest()` optionally deletes the collection and manifest on reset, upserts chunks in batches of 96, checks `should_cancel` before files and batches, returns partial counts, excludes cancelled files from the manifest, deletes existing chunks by path before changed-file upsert, and saves manifest after each completed file. Implementation reference: aetherlab/services/ingestion.py:125 / aetherlab/services/ingestion.py:149 / aetherlab/services/ingestion.py:164 / aetherlab/services/ingestion.py:177 / aetherlab/services/ingestion.py:213.",
        "If ChromaDB is missing, ingest raises an install-hint RuntimeError; if cancellation happens, the next run resumes because the unfinished file remains pending.",
        "harness",
    ),
    "F44": _story_tuple(
        "US-F44: As a Kazakhstan ENT student, when I open the source library, I expect to distinguish Books 7–11 used for theory from ENT mock sets used for practice. Preconditions: source folder may be empty or populated. Steps: 1. Open Library. 2. Inspect the Books 7–11 and ENT mock sets selectors. 3. Confirm each source group remains separate.",
        "P5",
        "`LibraryPanel` offers separate Books 7–11 reference and ENT mock sets selectors; refresh lists supported files with size and index freshness. Implementation reference: aetherlab/ui/library_panel.py.",
        "The two source groups are not combined during lesson grounding or practice-bank selection.",
        "scripted-ui",
    ),
    "F45": _story_tuple(
        "US-F45: As P5 Returning user, when I add a folder of textbooks, I expect supported files to be copied into the library without overwriting same-name files, then indexed. Preconditions: a source folder is selected and library path is writable. Steps: 1. Click Add textbooks. 2. Choose a folder with PDFs/text files. 3. Observe count/status, refreshed list, and incremental indexing.",
        "P5",
        "`LibraryPanel._add_folder()` selects a directory, creates the library path, copies supported files while skipping existing destination names, reports copied count, refreshes the panel, and starts incremental ingest. Implementation reference: aetherlab/ui/widgets.py:2864.",
        "If the user cancels, no files are copied; existing filenames are skipped rather than overwritten.",
        "scripted-ui",
    ),
    "F46": _story_tuple(
        "US-F46: As P5 Returning user, when I re-index the library, I expect default incremental indexing, Ctrl-click full rebuild, progress, and cancellation. Preconditions: settings are attached. Steps: 1. Click Re-index normally. 2. Ctrl-click Re-index. 3. Cancel a running ingest. 4. Confirm button state and progress labels.",
        "P5",
        "`_reindex_clicked()` reads the Control modifier to choose reset/full mode, `_start_ingest()` disables and relabels the button, creates `_IngestWorker`, wires progress/finished, and the worker calls `LibraryIngestor.ingest(..., should_cancel=self.isInterruptionRequested)`. Cancel leaves the task visibly pending until the worker confirms completion, and live library workers participate in MainWindow's bounded close barrier. Implementation reference: aetherlab/ui/widgets.py / aetherlab/ui/main_window.py.",
        "If a worker is already running, a new ingest is not started; cancel requests interruption and the manifest semantics resume unfinished files later without exposing a false-ready state.",
        "scripted-ui",
    ),
    "F47": _story_tuple(
        "US-F47: As P5 Returning user, when I use Get starter library, I expect curated OpenStax choices, enough-disk validation, streamed downloads, attribution, and auto-indexing. Preconditions: network and disk space may vary. Steps: 1. Open starter dialog. 2. Select books. 3. Start download. 4. Observe progress and indexing.",
        "P5",
        "`StarterLibraryDialog` presents curated CC-BY OpenStax books with defaults; `LibraryPanel._download_starter_library()` checks free disk >=500 MB, `_DownloadWorker` resolves current URLs, downloads each selected book, writes attribution, and reindexes after normal completion. Cancelled downloads keep completed books but do not auto-start indexing, remain visibly pending until confirmed, and join the application close barrier. Implementation reference: aetherlab/ui/widgets.py / aetherlab/services/starter_library.py / aetherlab/ui/main_window.py.",
        "If disk space is too low, the user gets a warning; one failed book is reported while the remaining selected downloads can continue, and cancellation never starts a new indexing task.",
        "scripted-ui",
    ),
    "F48": _story_tuple(
        "US-F48: As P5 Returning user, when a starter PDF downloads, I expect robust URL resolution, partial-file safety, skip-existing behaviour, and one-book failure isolation. Preconditions: OpenStax CMS may be reachable or not. Steps: 1. Resolve URLs. 2. Download a book. 3. Retry with an existing large file. 4. Simulate a failed book in the worker.",
        "P5",
        "`resolve_pdf_urls()` fetches current high-resolution OpenStax PDF URLs with hardcoded fallbacks; `download_book()` streams to `<name>.part`, skips already-present files larger than 5 MB, uses `os.replace()` with an AV-lock retry, and `_DownloadWorker` catches per-book errors before continuing. Implementation reference: aetherlab/services/starter_library.py:128 / aetherlab/services/starter_library.py:154 / aetherlab/ui/widgets.py:2358.",
        "Network/CMS failure falls back to bundled URLs where possible; a single download failure emits progress/error information without aborting the rest.",
        "harness",
    ),
    "F49": _story_tuple(
        "US-F49: As P3 Educator, cloud AI + vision critic, when the LLM writes a Manim scene, I expect cinematic prompt context, safe code extraction, class normalization, and truncation detection. Preconditions: an API key is configured. Steps: 1. Generate remote scene code. 2. Inspect extracted class/imports/construct. 3. Simulate fenced/think/truncated output.",
        "P3",
        "`SceneGenerator._generate_remote()` builds structured cinematic context, uses cold codegen temperature after storyboard context, requests 32768 tokens, and raises on finish_reason `length`; `_extract_code()` strips think blocks/fences, injects imports, renames Scene/MovingCameraScene/ThreeDScene classes, and requires the target class plus construct method. Implementation reference: aetherlab/services/scene_generator.py:402 / aetherlab/services/scene_generator.py:451 / aetherlab/services/scene_generator.py:507 / aetherlab/services/scene_generator.py:510 / aetherlab/services/scene_generator.py:642.",
        "If extraction or truncation fails, generation routes to retry or fallback rather than accepting partial code.",
        "harness",
    ),
    "F50": _story_tuple(
        "US-F50: As P3 Educator, cloud AI + vision critic, when generated scene code has transient syntax or service hiccups, I expect bounded retries and then a safe fallback scene. Preconditions: remote scene generation may fail or return uncompilable code. Steps: 1. Trigger generation. 2. Force a SyntaxError. 3. Confirm retry/fallback status.",
        "P3",
        "`SceneGenerator.generate()` retries remote generation before fallback; `ManimRuntime.generate_scene_async()` compiles generated code, retries on SyntaxError/compile failure, and falls back to deterministic template code with compiled or compile-error status. Implementation reference: aetherlab/services/scene_generator.py:307 / aetherlab/services/manim_runtime.py:123.",
        "Persistent bad remote output does not block the solve; the static template path is used so the user still gets a scene artifact.",
        "harness",
    ),
    "F51": _story_tuple(
        "US-F51: As P1 Student, no AI key, when AI scene generation is unavailable, I expect a static Manim scene that compiles and animates visible content. Preconditions: solver and RAG results exist. Steps: 1. Generate a scene without remote AI. 2. Compile the returned code. 3. Confirm title, summary, steps, variables, and references are represented.",
        "P1",
        "`ManimRuntime.generate_scene()` uses `_build_scene_code()` to fill the Manim scene template with truncated title, summary, derivation steps, variables, and RAG hit count, producing non-empty animation code under Manim Community. Implementation reference: aetherlab/services/manim_runtime.py:397 / aetherlab/services/manim_runtime.py:880.",
        "If template compilation fails, the generated SceneBundle reports compile-error diagnostics instead of pretending a renderable scene exists.",
        "harness",
    ),
    "F52": _story_tuple(
        "US-F52: As P1 Student, no AI key, when the scene generator falls back dynamically, I expect axes, a curve, a moving dot, and a damping animation from solver variables. Preconditions: solver variables include damping/stiffness/mass or defaults. Steps: 1. Build fallback scene code. 2. Compile it. 3. Inspect for ValueTracker/always_redraw and there_and_back animation.",
        "P1",
        "`SceneGenerator._fallback_scene()` builds a Manim scene with axes, an always-redrawn damped curve and dot, parameter readouts from solver variables, and a damping ValueTracker animated with `there_and_back`. Implementation reference: aetherlab/services/scene_generator.py:680.",
        "If variables are missing, fallback defaults keep the animation code valid rather than rendering an empty scene.",
        "harness",
    ),
    "F53": _story_tuple(
        "US-F53: As P1 Student, no AI key, when AetherLab starts rendering, I expect it to detect the available Manim engine or degrade to code-only mode. Preconditions: Python environment may have manim, manimlib, or neither. Steps: 1. Call detect_engine. 2. Compare returned engine and diagnostics. 3. Confirm generated-only mode is reported when no engine imports.",
        "P1",
        "`ManimRuntime.detect_engine()` first imports `manim` and returns `manim-community`, then tries `manimlib` for `manimgl`, and otherwise returns `generated-only` with diagnostic messages. Implementation reference: aetherlab/services/manim_runtime.py:849.",
        "If no engine is importable, scene generation can still produce code while rendering is unavailable/diagnostic instead of crashing.",
        "harness",
    ),
    "F54": _story_tuple(
        "US-F54: As P3 Educator, cloud AI + vision critic, when a Manim scene renders locally, I expect AetherLab to write code into an isolated render directory, run Manim with quality/FPS settings, and return the newest MP4 or an actionable render error. Preconditions: Manim command is available. Steps: 1. Render a compiled SceneBundle. 2. Inspect command args/media_dir. 3. Force non-zero render and inspect stderr tail.",
        "P3",
        "`ManimRuntime.render_scene()` writes a scene file, cleans old media for the scene, invokes the Manim command with `render`, `-q<quality>`, `--fps`, and `--media_dir`, applies Windows no-window/process priority options, finds the newest MP4, and records timeout/non-zero stderr diagnostics. Implementation reference: aetherlab/services/manim_runtime.py:421 / aetherlab/services/manim_runtime.py:928 / aetherlab/services/manim_runtime.py:939.",
        "Timeouts and non-zero exits return SceneBundle statuses (`render-timeout` or `render-error`) with bounded stderr so the repair path can respond.",
        "harness",
    ),
    "F55": _story_tuple(
        "US-F55: As P4 Power user, cloud rendering, when rendering on different hardware or with env overrides, I expect FPS/tier choices to match resources or explicit settings. Preconditions: psutil/env values may vary. Steps: 1. Detect tier on low/high resource profiles. 2. Set AETHERLAB_RENDER_TIER or RENDER_TIER. 3. Set AETHERLAB_MANIM_FPS or MANIM_FPS. 4. Inspect tier/fps.",
        "P4",
        "`_detect_render_tier()` chooses cinematic 60 fps for >=16 GB and >=6 CPUs, standard 30 fps for >=10 GB, constrained 30 fps otherwise, honours forced tier values including cloud_cinematic, and lets explicit FPS env override the tier FPS. Implementation reference: aetherlab/services/manim_runtime.py:65 / aetherlab/services/manim_runtime.py:79 / aetherlab/services/manim_runtime.py:98.",
        "Invalid forced tier values are ignored back to auto detection; invalid FPS env values fall back to tier FPS.",
        "harness",
    ),
    "F56": _story_tuple(
        "US-F56: As P3 Educator, cloud AI + vision critic, when render quality changes, I expect timeout budgets to scale and failures to be classified clearly. Preconditions: local Manim render is invoked. Steps: 1. Render with l/m/h/k qualities. 2. Force timeout. 3. Force non-zero exit. 4. Inspect SceneBundle status and diagnostics.",
        "P3",
        "`render_scene()` uses quality-scaled timeout budgets (l/m/h/k), maps TimeoutExpired to `render-timeout`, maps non-zero subprocess exits to `render-error`, and captures a bounded stderr tail for repair. `run_process_tree()` terminates Manim plus descendant FFmpeg/LaTeX processes before returning a timeout. Implementation reference: aetherlab/services/manim_runtime.py / aetherlab/core/proc.py.",
        "A timed-out or failed render is not treated as a successful MP4; repair/fallback logic receives explicit status and diagnostics, and no descendant process keeps consuming CPU or locking render files.",
        "harness",
    ),
    "F57": _story_tuple(
        "US-F57: As P5 Returning user, when rendering the same scene repeatedly, I expect stale media to be removed and the newest MP4 to be selected. Preconditions: media/videos may contain old outputs. Steps: 1. Place old render files. 2. Render or call cleanup/discovery. 3. Confirm old scene media is removed and newest MP4 wins.",
        "P5",
        "`_clean_old_renders(scene_name)` removes `media/videos/<scene_name>` before rendering, and `_find_video(scene_name)` searches recursively for MP4s and returns the most recently modified file. Implementation reference: aetherlab/services/manim_runtime.py:928 / aetherlab/services/manim_runtime.py:939.",
        "If no MP4 is found, discovery returns None so render_scene can report render-missing instead of using stale output.",
        "harness",
    ),
    "F58": _story_tuple(
        "US-F58: As P1 Student, no AI key, when Manim is installed either as a Python module or executable, I expect AetherLab to find the right command. Preconditions: environment may contain module manim, `manim` executable, or neither. Steps: 1. Call `_find_manim_command()`. 2. Inspect preferred command. 3. Remove availability and confirm None.",
        "P1",
        "`ManimRuntime._find_manim_command()` prefers `[sys.executable, '-m', 'manim']`, falls back to `shutil.which('manim')`, and returns None when neither path is available. Implementation reference: aetherlab/services/manim_runtime.py:861.",
        "When no command is found, rendering degrades to code-only/generated diagnostics rather than invoking a missing process.",
        "harness",
    ),
    "F59": _story_tuple(
        "US-F59: As P1 Student, no AI key, when I use the Scene panel pills, I expect Canvas, Video, and Code to switch predictable stack pages. Preconditions: SimulationPanel is visible. Steps: 1. Click Canvas, Video, and Code pills. 2. Observe the stacked widget page. 3. Confirm loading overlay remains separate.",
        "P1",
        "`SimulationPanel` builds a stacked widget with loading page 0, live canvas page 1, video frame page 2, and code frame page 3; pill buttons call stack page switching helpers such as show_canvas/show_video/show_code. Implementation reference: aetherlab/ui/widgets.py:1434 / aetherlab/ui/widgets.py:1544 / aetherlab/ui/widgets.py:1611 / aetherlab/ui/widgets.py:1861.",
        "If a requested page index does not exist, `_select_tab()` guards against out-of-range stack access.",
        "scripted-ui",
    ),
    "F60": _story_tuple(
        "US-F60: As P3 Educator, cloud AI + vision critic, when I inspect generated code, I expect a read-only code view with copy/export actions and diagnostics separated from source code. Preconditions: a SceneBundle exists. Steps: 1. Open Code tab. 2. Inspect text edit state. 3. Use Copy code and Export scene.py. 4. Open diagnostics drawer.",
        "P3",
        "`SimulationPanel` creates a read-only code artifact view, Copy code and Export scene.py buttons, writes scene.code without diagnostics into the editor, and sends diagnostics to the collapsible diagnostics drawer. Implementation reference: aetherlab/ui/widgets.py:1571 / aetherlab/ui/widgets.py:1582 / aetherlab/ui/widgets.py:1914 / aetherlab/ui/widgets.py:3343.",
        "If no scene exists or diagnostics are empty, the code surface remains read-only and the diagnostics drawer can stay hidden/empty without corrupting source text.",
        "scripted-ui",
    ),
    "F61": _story_tuple(
        "US-F61: As P1 Student, no AI key, when a rendered MP4 is available, I expect a playable video surface with seek, frame stepping, speed control, and time feedback. Preconditions: SceneBundle.video_path points to an existing file. Steps: 1. Open the Scene video tab. 2. Seek, step previous/next frame, and adjust speed. 3. Confirm time label and playback state update.",
        "P1",
        "`SimulationPanel` builds QMediaPlayer/QVideoWidget controls, previous/next frame buttons using a 33 ms frame step, drag-aware seek slider, speed slider from 25-200%, and media status handling that autoplays once loaded. `set_video()` falls back to code view if the file is missing. Implementation reference: aetherlab/ui/widgets.py:1634 / aetherlab/ui/widgets.py:1681 / aetherlab/ui/widgets.py:1713 / aetherlab/ui/widgets.py:1723 / aetherlab/ui/widgets.py:1929.",
        "If the video path is absent or missing on disk, the user is shown code/diagnostics rather than a broken video widget.",
        "scripted-ui",
    ),
    "F62": _story_tuple(
        "US-F62: As P1 Student, no AI key, when I press Ctrl+Shift+C, I expect the Scene workspace to appear and toggle between canvas and code. Preconditions: main window is open. Steps: 1. Press Ctrl+Shift+C. 2. Observe Scene page. 3. Press again and confirm canvas/code alternates.",
        "P1",
        "`MainWindow._build_shortcuts()` wires Ctrl+Shift+C to `_toggle_code_view()`, which switches the workspace to Scene and toggles `SimulationPanel` stack page 3 code vs page 1 canvas. Implementation reference: aetherlab/ui/main_window.py:779 / aetherlab/ui/main_window.py:1124 / aetherlab/ui/widgets.py:1861 / aetherlab/ui/widgets.py:1867.",
        "If no scene exists yet, the toggle still changes the stack page without starting a run or mutating result data.",
        "scripted-ui",
    ),
    "F63": _story_tuple(
        "US-F63: As P1 Student, no AI key, when the live canvas has curve data, I expect a polished animated parametric view with grid, axes, glow curves, trail, tracer, and coordinate readout. Preconditions: CanvasState contains one or more curves. Steps: 1. Set canvas state. 2. Let the timer tick. 3. Observe paint output and coordinate label.",
        "P1",
        "`LiveCanvas.set_state()` stores CanvasState and starts animation; `paintEvent()` draws background, grid, boxed axes, curves, trail, tracer, hover labels, and legend, with helper `_nice_step()` for grid spacing. Implementation reference: aetherlab/ui/live_canvas.py:393 / aetherlab/ui/live_canvas.py:478 / aetherlab/ui/live_canvas.py:901 / aetherlab/ui/live_canvas.py:1374.",
        "If no curve data exists, paint draws the empty-state hint rather than failing on missing samples.",
        "scripted-ui",
    ),
    "F64": _story_tuple(
        "US-F64: As P1 Student, no AI key, when the solver provides plot payloads, I expect those expressions to drive the canvas, with fallback if validation fails. Preconditions: SolverResult may include `plot`. Steps: 1. Build canvas state with a valid plot. 2. Build with an invalid plot. 3. Confirm fallback domain curves are used on error.",
        "P1",
        "`build_canvas_state()` attempts `compile_plot()` when SolverResult.plot exists, maps compiled curves into canvas specs, logs/continues on expression errors, and otherwise falls back to domain families from variables/keywords. Implementation reference: aetherlab/ui/live_canvas.py:322 / aetherlab/services/plotting.py:269.",
        "Malformed plot payloads do not break the canvas; they degrade to deterministic family curves and leave the solver result intact.",
        "harness",
    ),
    "F65": _story_tuple(
        "US-F65: As P1 Student, no AI key, when no explicit plot is available, I expect AetherLab to choose a sensible curve family from variables. Preconditions: solver variables may include damping/stiffness or gravity/length. Steps: 1. Build canvas state for oscillator variables. 2. Build for pendulum variables. 3. Build generic variables.",
        "P1",
        "`_DOMAIN_MAP` maps variable signatures to domain curve factories; `build_canvas_state()` checks keys and falls back to generic Lissajous-like curves when no known family matches. Implementation reference: aetherlab/ui/live_canvas.py:194 / aetherlab/ui/live_canvas.py:322 / aetherlab/ui/live_canvas.py:342.",
        "Unknown variable sets still produce a generic canvas state instead of an empty or crashed panel.",
        "harness",
    ),
    "F66": _story_tuple(
        "US-F66: As P1 Student, no AI key, when I enable phase portrait, I expect a dashed finite-difference overlay that follows either plot payload or legacy domain curves. Preconditions: canvas state exists and phase toggle is enabled. Steps: 1. Enable phase checkbox. 2. Rebuild canvas state. 3. Confirm an extra dashed/violet phase curve appears.",
        "P1",
        "`_phase_overlay_for()` builds payload-driven finite-difference overlays, `_phase_portrait_curves()` handles legacy variables, and `SimulationPanel` emits phase toggles to rebuild state. Implementation reference: aetherlab/ui/live_canvas.py:133 / aetherlab/ui/live_canvas.py:215 / aetherlab/ui/main_window.py:839.",
        "If the source curve has too few finite points, the overlay is skipped instead of drawing nonsense.",
        "harness",
    ),
    "F67": _story_tuple(
        "US-F67: As P1 Student, no AI key, when I zoom, pan, hover, or reset the canvas, I expect predictable navigation and labels without losing data coordinates. Preconditions: canvas is visible. Steps: 1. Use mouse wheel to zoom. 2. Drag to pan. 3. Hover a curve. 4. Press reset view.",
        "P1",
        "`LiveCanvas.wheelEvent()` zooms within 0.1-50x around cursor, mouse press/move/release handle data-space panning and hover state, `_draw_hover()` shows crosshair/labels, and `reset_view()` restores zoom and pan. Implementation reference: aetherlab/ui/live_canvas.py:509 / aetherlab/ui/live_canvas.py:604 / aetherlab/ui/live_canvas.py:634 / aetherlab/ui/live_canvas.py:683 / aetherlab/ui/live_canvas.py:1324.",
        "Degenerate ranges and empty states are guarded by effective range/default helpers so navigation does not divide by zero.",
        "scripted-ui",
    ),
    "F68": _story_tuple(
        "US-F68: As P1 Student, no AI key, when the canvas has no data, multiple curves, or is hidden, I expect an empty hint, legend when useful, and animation pause offscreen. Preconditions: canvas may be empty, multi-curve, or tab-hidden. Steps: 1. Paint an empty state. 2. Paint multi-curve state. 3. Hide and show the widget.",
        "P1",
        "`paintEvent()` draws a no-curve hint when state has no curves, `_draw_legend()` renders legends for multi-curve states, and show/hide events start/stop the animation timer. Implementation reference: aetherlab/ui/live_canvas.py:760 / aetherlab/ui/live_canvas.py:767 / aetherlab/ui/live_canvas.py:901 / aetherlab/ui/live_canvas.py:1267.",
        "Hidden-tab pause prevents unnecessary timer work; empty states avoid attempting to sample missing curves.",
        "scripted-ui",
    ),
    "F69": _story_tuple(
        "US-F69: As P1 Student, no AI key, when solver variables appear in Params, I expect slider, spinbox, and reset controls that support negative values and update the canvas live. Preconditions: solver variables are available. Steps: 1. Set variables. 2. Move slider and spinbox. 3. Press reset. 4. Observe canvas and analysis updates.",
        "P1",
        "`ParameterDock.set_variables()` creates a 1000-tick slider, QDoubleSpinBox with four decimals and `[-span, span]`, reset button per variable, and emits `parameter_changed`; MainWindow wires that signal to both canvas and analysis panel updates. Implementation reference: aetherlab/ui/widgets.py:800 / aetherlab/ui/widgets.py:855 / aetherlab/ui/widgets.py:862 / aetherlab/ui/widgets.py:870 / aetherlab/ui/main_window.py:827.",
        "Variables outside the initial span are accommodated by dynamic range expansion rather than clamping negative values.",
        "scripted-ui",
    ),
    "F70": _story_tuple(
        "US-F70: As P1 Student, no AI key, when a parameter changes from either UI or canvas, I expect slider and spinbox to mirror without recursive signal storms. Preconditions: ParameterDock has variable controls. Steps: 1. Change slider. 2. Change spinbox. 3. Push an out-of-range value from canvas. 4. Confirm range expands and one signal emits.",
        "P1",
        "`ParameterDock` uses `blockSignals()` while synchronizing slider/spinbox values, expands spinbox range symmetrically when `abs(value) > span`, and mirrors external `update_variable()` calls back into controls. Implementation reference: aetherlab/ui/widgets.py:932 / aetherlab/ui/widgets.py:945 / aetherlab/ui/widgets.py:968 / aetherlab/ui/widgets.py:975.",
        "If a variable name is unknown, update_variable returns without creating orphan controls or emitting misleading changes.",
        "harness",
    ),
    "F71": _story_tuple(
        "US-F71: As P1 Student, no AI key, when I collapse Params or use the Params rail item, I expect the parameter controls to hide and reappear without losing values. Preconditions: parameters exist. Steps: 1. Click the ParameterDock header. 2. Select the Params rail item. 3. Return to Scene and verify values persist.",
        "P1",
        "`ParameterDock._toggle_collapsed()` hides/shows the slider container and updates header affordance; MainWindow sidebar selection handles the Params side panel visibility for the Scene page. Implementation reference: aetherlab/ui/widgets.py:968 / aetherlab/ui/main_window.py:892.",
        "Collapsing only changes visibility; it does not reset variable values or disconnect update signals.",
        "scripted-ui",
    ),
    "F72": _story_tuple(
        "US-F72: As P1 Student, no AI key, when a solve result arrives, I expect the Analysis panel to show a summary banner, cache note, and keyword chips. Preconditions: SolverResult is available. Steps: 1. Call set_solver_result. 2. Inspect banner text. 3. Confirm up to six keyword chips appear.",
        "P1",
        "`AnalysisPanel.set_solver_result()` hides the empty hint, adds `[cache]` when solver.cached is true, fills the cyan summary banner, and renders up to six keyword chips. Implementation reference: aetherlab/ui/widgets.py:1073 / aetherlab/ui/widgets.py:1202 / aetherlab/ui/widgets.py:1203 / aetherlab/ui/widgets.py:1230.",
        "If there are no keywords, the chip row is hidden rather than leaving empty decoration.",
        "scripted-ui",
    ),
    "F73": _story_tuple(
        "US-F73: As P1 Student, no AI key, when I read derivation steps, I expect collapsible sections plus copy affordances for the whole solution or individual steps. Preconditions: SolverResult has derivation_steps. Steps: 1. Expand/collapse steps. 2. Use Expand all. 3. Copy all or one step.",
        "P1",
        "`_CollapsibleStepWidget` toggles body visibility from header clicks, `AnalysisPanel._toggle_all_steps()` expands/collapses all current steps, `_copy_all()` copies summary plus steps, and per-step copy buttons copy individual text. Implementation reference: aetherlab/ui/widgets.py:995 / aetherlab/ui/widgets.py:1188 / aetherlab/ui/widgets.py:1193 / aetherlab/ui/widgets.py:1202.",
        "If no steps are available, the panel can render the summary without creating broken step controls.",
        "scripted-ui",
    ),
    "F74": _story_tuple(
        "US-F74: As P1 Student, no AI key, before any solve completes, I expect Analysis to show an empty hint rather than stale or blank derivation content. Preconditions: fresh app session. Steps: 1. Open Solve/Analysis before running. 2. Observe empty state. 3. Complete a solve and confirm it hides.",
        "P1",
        "`AnalysisPanel` creates an `EmptyHint` label during initialization and `set_solver_result()` hides it when real solver content arrives. Implementation reference: aetherlab/ui/widgets.py:1073 / aetherlab/ui/widgets.py:1149 / aetherlab/ui/widgets.py:1202.",
        "Fresh sessions do not show stale prior derivations unless explicitly loaded from history/cache through a new run.",
        "scripted-ui",
    ),
    "F75": _story_tuple(
        "US-F75: As P1 Student, no AI key, when I choose destinations on the sidebar rail, I expect the main workspace to map to empty/running/solve/scene/library/history appropriately. Preconditions: app window is open. Steps: 1. Select each rail item. 2. Observe emitted index. 3. Confirm pages respect result availability.",
        "P1",
        "`SidebarNav.select()` emits `item_selected`; `MainWindow._on_sidebar_select()` maps rail indexes to workspace pages, using empty/running placeholders until results exist and showing library/history pages directly. Implementation reference: aetherlab/ui/widgets.py:162 / aetherlab/ui/widgets.py:209 / aetherlab/ui/main_window.py:892.",
        "Selecting a gated or unavailable result page falls back to the empty/running page instead of exposing unusable controls.",
        "scripted-ui",
    ),
    "F76": _story_tuple(
        "US-F76: As P1 Student, no AI key, when I use keyboard navigation, I expect Ctrl+1..5 and arrow keys to move through the rail consistently. Preconditions: main window or sidebar has focus. Steps: 1. Press Ctrl+1 through Ctrl+5. 2. Use arrow keys on the rail. 3. Confirm selection changes.",
        "P1",
        "`MainWindow._build_shortcuts()` connects Ctrl+1..5 to `sidebar.select(idx)`, and `SidebarNav.keyPressEvent()` moves selection with Up/Down/Left/Right keys. Implementation reference: aetherlab/ui/main_window.py:774 / aetherlab/ui/widgets.py:212.",
        "Out-of-range arrow movement clamps at the first/last rail item rather than wrapping unexpectedly.",
        "scripted-ui",
    ),
    "F77": _story_tuple(
        "US-F77: As P1 Student, no AI key, when I have not solved a problem yet, I expect the Lab destination to remain available. Preconditions: student workspace is open. Steps: 1. Construct SidebarNav. 2. Mark a result unavailable. 3. Confirm Lab remains enabled. 4. Mark a result available and confirm it stays enabled.",
        "P1",
        "`SidebarNav.set_result_available()` keeps the Lab destination enabled before and after a solve. Implementation reference: aetherlab/ui/navigation.py:96 / aetherlab/ui/main_window.py:1934.",
        "Students can enter the lab before generating a scene; unavailable controls inside the workspace remain guarded by their own state.",
        "harness",
    ),
    "F78": _story_tuple(
        "US-F78: As P1 Student, no AI key, when a scene is ready, I expect the Lab workspace to open automatically. Preconditions: solve worker emits scene_ready. Steps: 1. Start a solve. 2. Wait for scene_ready. 3. Confirm Lab is selected and loading is hidden.",
        "P1",
        "`MainWindow.on_scene_ready()` marks a result available, hides loading, sends the SceneBundle to SimulationPanel, marks the stepper scene stage complete, and calls `sidebar.select(7)`. Implementation reference: aetherlab/ui/main_window.py:1934.",
        "If render is still pending, the user can inspect canvas/code while video completion follows later.",
        "harness",
    ),
    "F79": _story_tuple(
        "US-F79: As P5 Returning user, when runs complete across sessions, I expect recent history to persist and reload with status-coloured entries. Preconditions: history DB path is writable. Steps: 1. Initialize history persistence. 2. Add entries. 3. Reopen panel and confirm recent entries load.",
        "P5",
        "`HistoryPanel.init_persistence()` creates the history table and loads recent rows; `add_entry()` persists and paints each run. If SQLite reports corruption/not-a-database, the DB and sidecars are preserved under `.corrupt-*` and an empty history DB is rebuilt. Implementation reference: aetherlab/ui/widgets.py / aetherlab/core/sqlite_recovery.py.",
        "If persistence is not initialized, add_entry still updates the current-session list; corrupt SQLite is quarantined and rebuilt, while lock/permission errors are not misclassified or moved.",
        "harness",
    ),
    "F80": _story_tuple(
        "US-F80: As P5 Returning user, when I double-click a history item, I expect the original prompt to run again through the normal pipeline path. Preconditions: history item exists. Steps: 1. Double-click a history row. 2. Observe prompt_selected emission. 3. Confirm MainWindow starts a new pipeline for that prompt.",
        "P5",
        "`HistoryPanel` emits `prompt_selected(str)` on item double-click, and `MainWindow._connect_signals()` connects that signal to `start_pipeline()`. Implementation reference: aetherlab/ui/widgets.py:456 / aetherlab/ui/main_window.py:807.",
        "If the current pipeline is already running, start_pipeline's duplicate-run guard prevents history replay from stacking a second run.",
        "harness",
    ),
    "F81": _story_tuple(
        "US-F81: As P5 Returning user, when I clear history, I expect the visible list and persistent SQLite rows to be removed together. Preconditions: history persistence may be initialized. Steps: 1. Add history entries. 2. Click Clear. 3. Reopen the panel/session and confirm entries are gone.",
        "P5",
        "`HistoryPanel._clear()` clears the QListWidget and, when a DB path is attached, opens SQLite and DELETEs from the history table using a bounded connection block. Implementation reference: aetherlab/ui/widgets.py:591.",
        "If persistence is not initialized, clearing still empties the visible list without raising.",
        "harness",
    ),
    "F82": _story_tuple(
        "US-F82: As P1 Student, no AI key, when AetherLab shows a toast, I expect kind-specific colour/icon, optional Details, and a dismiss control. Preconditions: Toast widget exists. Steps: 1. Show info/success/warning/error messages. 2. Toggle details=True. 3. Click Details and dismiss.",
        "P1",
        "`Toast.show_message()` selects visual treatment by kind, updates icon/message, shows the Details button only when requested, and emits `details_requested`; MainWindow connects that signal to the simulation error detail window. Implementation reference: aetherlab/ui/widgets.py:2057 / aetherlab/ui/widgets.py:2105 / aetherlab/ui/main_window.py:824.",
        "Unknown toast kinds fall back to a safe default visual style, and dismiss hides the toast without affecting app state.",
        "scripted-ui",
    ),
    "F83": _story_tuple(
        "US-F83: As P1 Student, no AI key, when a pipeline error happens, I expect an inline banner and a single traceback/details window instead of duplicate popups. Preconditions: SimulationPanel receives an error stage/message/traceback. Steps: 1. Call show_error_banner. 2. Open details twice. 3. Confirm one WA_DeleteOnClose details window is reused/deduped.",
        "P1",
        "`SimulationPanel.show_error_banner()` records stage/message/traceback and shows the banner; `_show_error_details()` opens a traceback QPlainTextEdit window, deduping an existing live details window and using DeleteOnClose. Implementation reference: aetherlab/ui/widgets.py:1985 / aetherlab/ui/widgets.py:1996.",
        "If no traceback is provided, the details window uses the message text; clear_error_banner hides stale error UI before the next run.",
        "scripted-ui",
    ),
    "F84": _story_tuple(
        "US-F84: As P1 Student, no AI key, when a pipeline stage fails, I expect the stepper, status bar, toast, error banner, and workspace to show a recoverable failure state. Preconditions: MainWindow receives PipelineError. Steps: 1. Trigger on_failure. 2. Inspect current stage/error state. 3. Open details and retry from the visible page.",
        "P1",
        "`MainWindow.on_failure()` hides loading, marks the current stepper stage error, disables cancellation, writes `stage failed: message` to the status bar, shows an error toast with Details, shows the simulation error banner, and returns to Solve or Empty depending on whether a prior result exists. Implementation reference: aetherlab/ui/main_window.py:1428.",
        "Failures do not leave the run button permanently busy or the user stranded on a loading-only page.",
        "harness",
    ),
    "F85": _story_tuple(
        "US-F85: As P3 Educator, cloud AI + vision critic, when I export a derivation as LaTeX, I expect a standalone document with escaped user/model content. Preconditions: a solver result exists and output path is chosen. Steps: 1. Click export LaTeX. 2. Save a .tex file. 3. Open it and inspect summary, steps, variables, and escaping.",
        "P3",
        "`export_derivation_to_latex()` writes a standalone amsmath/booktabs document with Summary, Derivation Steps, Variables, and key equations; MainWindow `_export_latex()` routes the current result to the chosen file. Implementation reference: aetherlab/services/pdf.py:72 / aetherlab/ui/main_window.py:944.",
        "If there is no result or the user cancels the save dialog, no file is written and the status bar explains the guard.",
        "harness",
    ),
    "F86": _story_tuple(
        "US-F86: As P3 Educator, cloud AI + vision critic, when I export PDF, I expect AetherLab to compile the LaTeX safely and fall back with a clear message if pdflatex is unavailable. Preconditions: a solver result exists and save path is chosen. Steps: 1. Export PDF. 2. Verify temp .tex directory is created. 3. Confirm PDF copy or fallback status.",
        "P3",
        "`compile_latex_to_pdf()` removes stale PDFs, runs pdflatex with nonstopmode through the cancellable whole-tree runner, then requires returncode 0 plus fresh output. `_export_pdf()` asks for the destination first, runs compilation in `BackgroundTask`, atomically copies the PDF, or saves and names a `.tex` fallback beside the chosen PDF. Status progresses through Preparing PDF to PDF exported or LaTeX saved instead. Implementation reference: aetherlab/services/pdf.py / aetherlab/core/atomic_file.py / aetherlab/ui/main_window.py.",
        "Missing pdflatex, timeout, compile failure, cancellation, or stale outputs do not freeze the window, overwrite a prior good export, or claim an unnamed fallback was saved.",
        "scripted-ui",
    ),
    "F87": _story_tuple(
        "US-F87: As P3 Educator, cloud AI + vision critic, when I export scene code, I expect the exact current Manim code to be written to my chosen path. Preconditions: a scene result exists. Steps: 1. Choose Export scene.py. 2. Pick a path. 3. Confirm file contents match scene.code.",
        "P3",
        "`export_scene_code()` writes the provided code to disk, and MainWindow `_export_scene()` guards missing results then passes `self._last_result.scene.code` to the chosen path. Implementation reference: aetherlab/services/pdf.py:153 / aetherlab/ui/main_window.py:987.",
        "If no scene exists or the user cancels the save dialog, no file is created and the app remains idle.",
        "harness",
    ),
    "F88": _story_tuple(
        "US-F88: As P1 Student, no AI key, when I save the rendered video, I expect AetherLab to copy the current MP4 to my chosen location only if it exists. Preconditions: a rendered scene with video_path exists. Steps: 1. Click Save video. 2. Pick output path. 3. Confirm copy size/path.",
        "P1",
        "`MainWindow._save_video()` guards missing result/video/file, opens a save dialog, then shows Saving video while a `BackgroundTask` calls `atomic_copy_file()`. The copier streams cancellably to a unique sibling staging file, fsyncs, preserves metadata, and `os.replace()`s only after success; choosing the source itself is a no-op. Implementation reference: aetherlab/ui/main_window.py / aetherlab/core/atomic_file.py.",
        "Missing files report status; cancellation/copy failure preserves any prior destination and removes staging without freezing the UI or exposing a partial MP4.",
        "harness",
    ),
    "F89": _story_tuple(
        "US-F89: As P1 Student, no AI key, when I export GIF, I expect ffmpeg to convert the current MP4 with bounded settings and clear errors. Preconditions: rendered video exists and ffmpeg may be installed. Steps: 1. Choose Export GIF. 2. Save output. 3. Inspect ffmpeg command, timeout, and failure messages.",
        "P1",
        "`MainWindow._export_gif()` checks the video and shows Converting video to GIF while a `BackgroundTask` runs `ffmpeg -y -i <mp4> -vf fps=15,scale=480:-1:flags=lanczos -loop 0` through the cancellable whole-tree runner. FFmpeg writes a unique sibling `.gif` staging path that atomically replaces the destination only on success; status reports GIF exported, timeout/failure, or missing ffmpeg. Implementation reference: aetherlab/ui/main_window.py / aetherlab/core/atomic_file.py / aetherlab/core/proc.py.",
        "Missing ffmpeg, timeout, cancellation, or non-zero exit stays actionable, removes staging, preserves an existing destination, and never blocks the Qt event loop.",
        "scripted-ui",
    ),
    "F90": _story_tuple(
        "US-F90: As P1 Student, no AI key, when I use the app, I expect a consistent dark AetherLab theme across dialogs and the main shell. Preconditions: UI initializes. Steps: 1. Construct MainWindow/SettingsDialog. 2. Inspect applied stylesheet. 3. Verify core dark/accent tokens appear.",
        "P1",
        "`AETHERLAB_QSS` defines the shared dark shell stylesheet, and MainWindow plus SettingsDialog apply it during construction. Implementation reference: aetherlab/ui/style.py:52 / aetherlab/ui/main_window.py:93 / aetherlab/ui/main_window.py:640.",
        "If a widget lacks a custom object-name style, Qt falls back to the shared base palette rather than an unreadable system default.",
        "scripted-ui",
    ),
    "F91": _story_tuple(
        "US-F91: As P1 Student, no AI key, when I resize or use a small screen, I expect the shell, Params drawer, canvas, video, and lesson surfaces to remain reachable. Preconditions: screen geometry may be narrow. Steps: 1. Launch on small geometry. 2. Resize. 3. Inspect minimum sizes and Params side width.",
        "P1",
        "`MainWindow` sizes to screen-relative width/height and minimums, `_apply_responsive_layout()` keeps Params side width between 220 and 320 px, and canvas/video widgets use lowered minimums for shrinkability. Implementation reference: aetherlab/ui/main_window.py:638 / aetherlab/ui/main_window.py:840 / aetherlab/ui/live_canvas.py:413 / aetherlab/ui/widgets.py:1648.",
        "At narrow widths, the app constrains panels instead of letting primary controls become unreachable.",
        "scripted-ui",
    ),
    "F92": _story_tuple(
        "US-F92: As P1 Student, no AI key, when I use the title bar gear, I expect Settings to open from the custom chrome. Preconditions: main window is visible. Steps: 1. Click the settings control in TitleBar. 2. Observe settings_requested. 3. Confirm MainWindow opens SettingsDialog.",
        "P1",
        "`TitleBar` is a 44 px custom header with a settings signal, and MainWindow connects `title_bar.settings_requested` to `_open_settings()`. Implementation reference: aetherlab/ui/widgets.py:2022 / aetherlab/ui/main_window.py:798.",
        "If the dialog is cancelled, no settings are persisted; the title bar remains responsive.",
        "scripted-ui",
    ),
    "F93": _story_tuple(
        "US-F93: As P1 Student, no AI key, when I first open AetherLab, I expect a useful empty state with examples and setup status instead of a blank workspace. Preconditions: no result is loaded. Steps: 1. Launch fresh. 2. Inspect empty state headline/chips/status strip. 3. Change API key/library status and refresh.",
        "P1",
        "`EmptyStateView` renders headline copy, three example chips, setup actions, and `set_status()` updates provider/library status from key/model/library count. Implementation reference: aetherlab/ui/widgets.py:2127 / aetherlab/ui/widgets.py:2258.",
        "If no provider or library exists, the empty state communicates that status and offers setup actions rather than a dead Run area.",
        "scripted-ui",
    ),
    "F94": _story_tuple(
        "US-F94: As P1 Student, no AI key, when a run is active, I expect a focused running page with animated blueprint loading and current stage text. Preconditions: solve or lesson is running. Steps: 1. Start a run. 2. Observe RunningView headline/detail. 3. Watch progress update text.",
        "P1",
        "`RunningView` embeds `BlueprintLoadingOverlay` plus headline/detail labels, and `set_stage_text()` updates them from MainWindow progress handlers. Implementation reference: aetherlab/ui/widgets.py:2287 / aetherlab/ui/widgets.py:2321.",
        "When progress detail is empty, the view can still show the headline without stale previous detail.",
        "scripted-ui",
    ),
    "F95": _story_tuple(
        "US-F95: As P1 Student, no AI key, when UI icons render, I expect crisp cached Lucide-style icons and an info fallback for unknown names. Preconditions: Qt icon/pixmap creation is available. Steps: 1. Request known icon/pixmap/label. 2. Request an unknown name. 3. Confirm fallback and cache reuse.",
        "P1",
        "`icon_pixmap()` renders whitelisted SVG path bodies at 2x into a pixmap cache, falls back to the `info` body for unknown names, and `icon()`/`icon_label()` wrap that pixmap for buttons/labels. Implementation reference: aetherlab/ui/icons.py:120 / aetherlab/ui/icons.py:166 / aetherlab/ui/icons.py:190 / aetherlab/ui/icons.py:194.",
        "Unknown icon names do not crash or leave blank controls; they render the standard info glyph.",
        "harness",
    ),
    "F96": _story_tuple(
        "US-F96: As P1 Student, no AI key, when the loading overlay is hidden, I expect its animation timer to stop so the idle app does not burn CPU. Preconditions: BlueprintLoadingOverlay is shown/hidden. Steps: 1. Show overlay. 2. Confirm timer starts. 3. Hide overlay and confirm timer stops.",
        "P1",
        "`BlueprintLoadingOverlay.showEvent()` starts a 33 ms timer and `hideEvent()` stops it; RunningView and SimulationPanel reuse the overlay for active run visuals. Implementation reference: aetherlab/ui/widgets.py:22 / aetherlab/ui/widgets.py:33 / aetherlab/ui/widgets.py:38.",
        "If the overlay is never shown, the timer stays idle.",
        "scripted-ui",
    ),
    "F97": _story_tuple(
        "US-F97: As P5 Returning user, when old or corrupt cache JSON is loaded, I expect model deserializers to coerce safe defaults where possible. Preconditions: cached solver/RAG/scene JSON may be missing new fields or have wrong types. Steps: 1. Call from_json with partial payloads. 2. Inspect defaults and cached flag. 3. Confirm missing plot loads as None.",
        "P5",
        "`SolverResult.from_json()`, `RagResult.from_json()`, and `SceneBundle.from_json()` coerce lists/strings/numbers through safe constructors, preserve cached flags, and accept old rows with missing plot/quality fields. Implementation reference: aetherlab/core/models.py:56 / aetherlab/core/models.py:111 / aetherlab/core/models.py:151.",
        "If optional fields are absent or wrong-shaped, defaults are used instead of KeyError where the model supports compatibility.",
        "harness",
    ),
    "F98": _story_tuple(
        "US-F98: As P1 Student, no AI key, when canvas ranges or samples are degenerate, I expect numeric guards to avoid division by zero and invalid drawing. Preconditions: canvas state may have flat ranges or non-finite samples. Steps: 1. Map degenerate ranges. 2. Call _nice_step with zero/invalid range. 3. Paint non-finite samples.",
        "P1",
        "`LiveCanvas._map_to_plot()` centers points when spans are near zero, `_nice_step()` returns 1.0 for degenerate ranges, and paint/map paths filter non-finite samples before drawing. Implementation reference: aetherlab/ui/live_canvas.py:881 / aetherlab/ui/live_canvas.py:964 / aetherlab/ui/live_canvas.py:1374.",
        "Bad numeric data is skipped or mapped to safe defaults instead of crashing the paint event.",
        "harness",
    ),
    "F99": _story_tuple(
        "US-F99: As P1 Student, no AI key, when headless components need event dispatch, I expect StateBus to call subscribers with Event objects. Preconditions: callback is subscribed for an event name. Steps: 1. Subscribe callback. 2. Emit name/payload. 3. Confirm callback receives Event(name, payload).",
        "P1",
        "`StateBus.subscribe()` stores callbacks by event name and `emit()` constructs Event(name, payload) for each callback currently subscribed to that name. Implementation reference: aetherlab/core/events.py:21 / aetherlab/core/events.py:25 / aetherlab/core/events.py:28.",
        "Emitting an event with no subscribers is a no-op, not an error.",
        "harness",
    ),
    "F100": _story_tuple(
        "US-F100: As P5 Returning user, when scenes render repeatedly, I expect safe scene names and stable code hashes so caches do not collide across different code. Preconditions: class name/title/code are available. Steps: 1. Sanitize scene names with punctuation. 2. Hash identical code twice. 3. Hash different code and confirm name changes.",
        "P5",
        "`sanitize_scene_name()` title-cases alphanumeric runs into a safe identifier, and `_scene_name()` appends a 10-character SHA-256 digest of code so identical code reuses cache paths while different generated code gets distinct render media. Implementation reference: aetherlab/services/manim_runtime.py:915 / aetherlab/services/manim_runtime.py:1066.",
        "Empty or hostile names fall back to a safe scene name; differing code avoids accidental media collisions.",
        "harness",
    ),
    "F101": _story_tuple(
        "US-F101: As P3 Educator, cloud AI + vision critic, when local rendering fails and an API key is available, I expect AetherLab to ask the model for bounded repair, revalidate the code, and re-render. Preconditions: SceneBundle render returns render-error or render-timeout; API key configured. Steps: 1. Render a failing scene. 2. Observe repair prompt/retry. 3. Confirm safety/lint checks and max repair count.",
        "P3",
        "`render_scene_with_repair()` first calls render_scene, then while status is render-error/render-timeout and repairs < max_repairs with an API key, trims error context, adds timeout load-reduction guidance, appends ErrorLearner hints, calls SceneGenerator.repair(), validates safety and scene lint, compiles, records the error, and re-renders. Implementation reference: aetherlab/services/manim_runtime.py:540 / aetherlab/services/manim_runtime.py:579 / aetherlab/services/manim_runtime.py:600 / aetherlab/services/manim_runtime.py:614.",
        "Without an API key, repair is skipped and the original render result/status is returned; unsafe or lint-failing repairs are rejected.",
        "harness",
    ),
    "F102": _story_tuple(
        "US-F102: As P3 Educator, cloud AI + vision critic, when an LLM response is truncated, I expect it to fail into retry/fallback instead of compiling half-written Manim code. Preconditions: remote generation, repair, or revision finish_reason is length. Steps: 1. Simulate length finish_reason. 2. Confirm ValueError. 3. Confirm caller routes to retry/fallback.",
        "P3",
        "`SceneGenerator._generate_remote()`, `repair()`, and `revise()` check `choice.finish_reason == 'length'` and raise ValueError before code extraction/compilation. Implementation reference: aetherlab/services/scene_generator.py:510 / aetherlab/services/scene_generator.py:561 / aetherlab/services/scene_generator.py:592.",
        "Truncated replies are never accepted as renderable code; they are treated as failed attempts.",
        "harness",
    ),
    "F103": _story_tuple(
        "US-F103: As P3 Educator, cloud AI + vision critic, when model-written code enters AetherLab, I expect unsafe imports, builtins, and sandbox-escape patterns to fail closed. Preconditions: generated or repaired code exists. Steps: 1. Validate normal Manim code. 2. Try banned builtins/imports/dunder escapes. 3. Confirm generation/repair rejects unsafe code.",
        "P3",
        "`validate_code_safety()` AST-walks code for import allowlist, banned runtime helpers, banned names/attributes/strings, and unsafe dunders; ManimRuntime calls it for generated candidates and repaired/revised code before render. Implementation reference: aetherlab/services/code_safety.py:89 / aetherlab/services/manim_runtime.py:143 / aetherlab/services/manim_runtime.py:614 / aetherlab/services/manim_runtime.py:710.",
        "Unsafe code counts as a failed generation attempt or aborts repair/revision rather than reaching the Manim subprocess.",
        "harness",
        "FAIL",
        "BUG-28",
        "PASS",
    ),
    "F104": _story_tuple(
        "US-F104: As P3 Educator, cloud AI + vision critic, when render errors recur, I expect AetherLab to learn preventive hints across runs. Preconditions: data_dir is writable and render errors occur. Steps: 1. Trigger known Manim pitfalls. 2. Inspect generation prompt pitfalls. 3. Trigger repair and inspect hints_for output.",
        "P3",
        "`ErrorLearner` provides a curated Manim-CE pitfall knowledge base, persists normalized error signatures with TTL in data_dir/error_patterns.json, appends preventive pitfalls to generation prompts, and provides `hints_for()` repair hints with recurrence warning. Implementation reference: aetherlab/services/error_learner.py:134 / aetherlab/services/error_learner.py:190 / aetherlab/services/scene_generator.py:402 / aetherlab/services/manim_runtime.py:600.",
        "If the pattern store is missing or corrupt, hints fall back to curated rules without blocking generation.",
        "harness",
    ),
    "F105": _story_tuple(
        "US-F105: As P1 Student, no AI key, when fallback scenes are needed, I expect domain-specific Manim visuals rather than one generic plot. Preconditions: keywords/variables indicate pendulum, orbit, wave, oscillator, or unknown. Steps: 1. Build fallback scenes for each domain. 2. Compile them. 3. Confirm Text-only, themed code.",
        "P1",
        "`scene_templates.detect_domain()` maps keywords/variables to domain templates and `build_scene()` emits themed compile-guaranteed Text-only Manim scenes; SceneGenerator and ManimRuntime route fallback scene code through those helpers. Implementation reference: aetherlab/services/scene_templates.py:81 / aetherlab/services/scene_templates.py:122 / aetherlab/services/scene_generator.py:688 / aetherlab/services/manim_runtime.py:896.",
        "Unknown domains fall back to a safe generic/oscillator-style template that still compiles.",
        "harness",
    ),
    "F106": _story_tuple(
        "US-F106: As P3 Educator, cloud AI + vision critic, before a render starts, I expect generated code to pass static validation for obvious Manim, constructor, LaTeX, and duration problems. Preconditions: generated Manim code exists. Steps: 1. Validate unknown names. 2. Validate bad kwargs/LaTeX. 3. Estimate duration. 4. Confirm failures trigger regenerate/repair.",
        "P3",
        "`scene_validation` provides `lint_manim_names()`, `lint_constructor_kwargs()`, `check_latex_strings()`, and `estimate_duration()`; ManimRuntime invokes these during scene generation and repair, using lint failures as failed attempts or repair input. Implementation reference: aetherlab/services/scene_validation.py:95 / aetherlab/services/scene_validation.py:129 / aetherlab/services/scene_validation.py:210 / aetherlab/services/scene_validation.py:386 / aetherlab/services/manim_runtime.py:143.",
        "Static validation is conservative; uncertain code can still render, but provably bad code is rejected before spending render time.",
        "harness",
    ),
    "F107": _story_tuple(
        "US-F107: As P3 Educator, cloud AI + vision critic, when remote generation is available, I expect a creative storyboard pass followed by colder code implementation, with fallback if storyboard fails. Preconditions: API key is configured. Steps: 1. Generate with storyboard path. 2. Inspect SceneBundle.storyboard. 3. Force storyboard failure and confirm single-call fallback.",
        "P3",
        "`SceneGenerator.storyboard()` runs a hot directing pass; `_generate_remote()` implements it cold or falls back to single-call generation; every SceneGenerator request applies `codegen_request_kwargs()`, which disables default-on thinking for hybrid Qwen while Settings gives thinking-only/coder guidance. ManimRuntime stores the storyboard on SceneBundle.",
        "Storyboard failure fails soft; hybrid Qwen scene calls skip lengthy thinking, while thinking-only models keep the bounded configured timeout and never receive an unsupported disable flag.",
        "harness",
    ),
    "F108": _story_tuple(
        "US-F108: As P3 Educator, cloud AI + vision critic, when vision critique is configured, I expect rendered videos to be sampled, scored, and revised only when a revised render succeeds. Preconditions: vision_model configured; rendered video exists. Steps: 1. Render scene. 2. Run critique. 3. If revise requested, render trial and adopt only on success.",
        "P3",
        "`critique_video()` samples frames, tolerantly parses score/verdict/issues, and `render_scene_with_repair()` validates each revision, gives static or render failures one targeted repair, then adopts only a successfully rendered trial.",
        "If no vision model is configured or both bounded revision/repair attempts fail, the original successful render remains the fallback.",
        "harness",
    ),
    "F109": _story_tuple(
        "US-F109: As P1 Student, no AI key, when I zoom the live canvas, I expect the point under my cursor to stay anchored during smooth zoom animation. Preconditions: canvas is visible with curve state. Steps: 1. Wheel over a curve point. 2. Observe smooth OutCubic zoom. 3. Confirm anchor data coordinates stay invariant. 4. Reset with Ctrl+0 or double-click.",
        "P1",
        "`LiveCanvas` owns a 120 ms OutCubic `_zoom_anim`; wheelEvent retargets zoom and `_apply_zoom()` measures data coordinates before/after zoom at the anchor pixel and shifts pan offset to keep that point fixed. Implementation reference: aetherlab/ui/live_canvas.py:447 / aetherlab/ui/live_canvas.py:581 / aetherlab/ui/live_canvas.py:604.",
        "Zoom is clamped to the supported range, and reset stops animation and restores zoom/pan defaults.",
        "scripted-ui",
    ),
    "F110": _story_tuple(
        "US-F110: As P1 Student, no AI key, when the tracer animates, I expect a consistent six-second sweep and trail points that survive zoom/pan because they are stored in data space. Preconditions: canvas has a primary visible curve. Steps: 1. Let animation run. 2. Pause/hide/resume. 3. Zoom/pan and inspect trail alignment.",
        "P1",
        "`LiveCanvas` stores trail points as data coordinates in a 24-point deque, advances tracer time using QElapsedTimer wall-clock dt over SWEEP_SECONDS=6.0 with stall clamp, clears trail on wrap, and maps trail to pixels at paint time. Implementation reference: aetherlab/ui/live_canvas.py:42 / aetherlab/ui/live_canvas.py:417 / aetherlab/ui/live_canvas.py:423 / aetherlab/ui/live_canvas.py:786 / aetherlab/ui/live_canvas.py:1112.",
        "After pause/resume or hidden-tab wake, the first tick restarts the clock so the tracer does not jump.",
        "scripted-ui",
    ),
    "F111": _story_tuple(
        "US-F111: As P1 Student, no AI key, when I hover near a curve, I expect snapping to the nearest visible sample within 24 px and raw coordinates otherwise. Preconditions: visible non-reference curves are painted. Steps: 1. Hover near a curve. 2. Hover far from curves. 3. Inspect crosshair, ring, label, and legend highlight.",
        "P1",
        "`paintEvent()` publishes per-curve pixel caches, `_update_hover()` vectorizes nearest-sample distance across visible non-reference curves with nanargmin, snaps within 24 px, stores t/data coords, and falls back to raw cursor coordinates outside snap range. Implementation reference: aetherlab/ui/live_canvas.py:713 / aetherlab/ui/live_canvas.py:721 / aetherlab/ui/live_canvas.py:728 / aetherlab/ui/live_canvas.py:1324.",
        "Reference/hidden curves are excluded from snapping so guides do not steal the hover target.",
        "scripted-ui",
    ),
    "F112": _story_tuple(
        "US-F112: As P1 Student, no AI key, when canvas visuals render, I expect all colours to come from one palette aligned with app tokens. Preconditions: live_canvas module is loaded. Steps: 1. Inspect CANVAS_PALETTE. 2. Search draw paths for literal colours. 3. Confirm style token alignment.",
        "P1",
        "`CANVAS_PALETTE` centralizes canvas colours and is consumed by curve specs, drawing calls, roles, fills, points, and exports; style.py exposes the matching v2 token system. Implementation reference: aetherlab/ui/live_canvas.py:50 / aetherlab/ui/style.py:31.",
        "Palette changes can be made in one place without missing stray draw-call literals.",
        "harness",
    ),
    "F113": _story_tuple(
        "US-F113: As P1 Student, no AI key, when I zoom or pan complex curves, I expect cached samples to be reused and non-finite or extreme off-screen asymptote gaps to split curves cleanly. Preconditions: canvas has finite and non-finite samples. Steps: 1. Build sample cache. 2. Zoom/pan. 3. Render 1/t and finite-valued tan(t) curves and count branches.",
        "P1",
        "`LiveCanvas` sample cache keys on curve params/range/steps rather than viewport; paint maps arrays to pixels per frame, converts numpy arrays to QPolygonF via vectorized buffer path, and splits non-finite or extreme off-screen gaps into drawable branches. Implementation reference: aetherlab/ui/live_canvas.py:358 / aetherlab/ui/live_canvas.py:379 / aetherlab/ui/live_canvas.py:454 / aetherlab/ui/live_canvas.py:978 / aetherlab/ui/live_canvas.py:1120.",
        "Zoom/pan changes do not resample curve functions, and NaNs/infinities do not draw connecting lines across asymptotes.",
        "scripted-ui",
    ),
    "F114": _story_tuple(
        "US-F114: As P3 Educator, cloud AI + vision critic, when the solver returns rich plot payloads, I expect multiple curve roles, fills, and marked points to compile through the same safety whitelist. Preconditions: plot payload may include curves, fill_between, and points. Steps: 1. Compile multi-curve payload. 2. Inspect role styling/tracer exclusions. 3. Load legacy payload/cache.",
        "P3",
        "`compile_plot()` accepts up to six curves with roles/styles, optional fill_between, and up to eight points; `_state_from_plot()` maps compiled roles to palette colours, fills, marked points, and phase overlays; solver prompt documents the schema and fallback_plot_payload demonstrates envelopes. Implementation reference: aetherlab/services/plotting.py:269 / aetherlab/services/plotting.py:290 / aetherlab/ui/live_canvas.py:249 / aetherlab/services/llm.py:121.",
        "Invalid entries raise ExprError and legacy single-curve payloads continue to load as before.",
        "harness",
    ),
    "F115": _story_tuple(
        "US-F115: As P1 Student, no AI key, when I right-drag or Shift-drag the canvas, I expect to scrub tracer time without a resume jump, and double-click should reset view. Preconditions: primary curve exists. Steps: 1. Right-drag across plot. 2. Release. 3. Double-click. 4. Inspect progress bar and trail.",
        "P1",
        "`LiveCanvas` enters `_scrubbing` on right/Shift drag, maps cursor x to tracer t, clears trail, pauses sweep advance while scrubbing, invalidates the clock on release, draws a bottom progress bar, and double-click/reset paths call reset_view. Implementation reference: aetherlab/ui/live_canvas.py:655 / aetherlab/ui/live_canvas.py:664 / aetherlab/ui/live_canvas.py:686 / aetherlab/ui/live_canvas.py:1179.",
        "Scrubbing does not advance wall-clock animation, so releasing control resumes smoothly rather than jumping ahead.",
        "scripted-ui",
    ),
    "F116": _story_tuple(
        "US-F116: As P1 Student, no AI key, when I export the canvas as PNG, I expect a crisp 2x image and a hover camera button that does not appear in the export. Preconditions: canvas has a visible state. Steps: 1. Hover to reveal camera. 2. Save PNG with path or dialog. 3. Inspect image size and exported signal.",
        "P1",
        "`LiveCanvas.save_png()` renders the widget into a 2x devicePixelRatio pixmap, hides the export button during rendering, saves to a chosen path, and emits `png_exported`; the camera QToolButton is wired to save_png and uses the icon system. Implementation reference: aetherlab/ui/live_canvas.py:401 / aetherlab/ui/live_canvas.py:469 / aetherlab/ui/live_canvas.py:524.",
        "If the user cancels the save dialog, no file is emitted and the export button visibility is restored.",
        "scripted-ui",
    ),
    "F117": _story_tuple(
        "US-F117: As P1 Student, no AI key, when the legend is visible, I expect clicking entries to toggle curves and hovering a snapped curve to highlight its legend entry. Preconditions: state has named curves. Steps: 1. Click legend entries. 2. Hover canvas near a curve. 3. Observe hidden/muted and highlighted states.",
        "P1",
        "`_draw_legend()` registers hit rectangles for named curves, hidden curves render muted/hollow, `_toggle_curve()` flips CurveSpec.visible, mouse movement changes the cursor over legend entries, and hover snapping highlights the matched curve name. Implementation reference: aetherlab/ui/live_canvas.py:519 / aetherlab/ui/live_canvas.py:1270.",
        "Hidden curves are omitted from tracer/snapping but can be restored by clicking their legend entry again.",
        "scripted-ui",
    ),
    "F118": _story_tuple(
        "US-F118: As P1 Student, no AI key, when parameters update, I expect a live mono chip with sorted values and zoom factor, plus a first-paint fade only when curves first appear. Preconditions: CanvasState has params/curves. Steps: 1. Set initial state. 2. Change sliders. 3. Zoom. 4. Inspect fade/chip positioning.",
        "P1",
        "`LiveCanvas.set_state()` starts a 300 ms fade only when transitioning from no curves to curves; `_draw_param_chip()` renders sorted parameter pairs and zoom factor above the legend; subsequent slider rebuilds do not reset the fade. Implementation reference: aetherlab/ui/live_canvas.py:456 / aetherlab/ui/live_canvas.py:478 / aetherlab/ui/live_canvas.py:493 / aetherlab/ui/live_canvas.py:1307.",
        "Large or missing parameter sets degrade to a compact/empty chip without overlapping the legend.",
        "scripted-ui",
    ),
    "F119": _story_tuple(
        "US-F119: As P1 Student, no AI key, when the student UI loads, I expect blue-graphite surfaces, a sky-blue accent, and a labeled navigation rail. Preconditions: styles and widgets import. Steps: 1. Inspect style tokens. 2. Inspect nav rail width and labels. 3. Confirm canvas primary tracks the theme accent.",
        "P1",
        "`style.py` defines CYAN #60A5FA, CYAN_DEEP #3B82F6, and the blue-graphite surface tokens; live_canvas and Theme track CYAN, and SidebarNav uses a labeled 74px rail. Implementation reference: aetherlab/ui/style.py / aetherlab/ui/live_canvas.py / aetherlab/ui/navigation.py.",
        "The QSS, canvas, and Theme defaults use the same semantic accent while success and warning colors keep their separate roles.",
        "harness",
    ),
    "F120": _story_tuple(
        "US-F120: As P3 Educator, cloud AI + vision critic, when formulas appear in the UI, I expect mathtext-rendered transparent pixmaps where possible and safe text fallback on bad input. Preconditions: matplotlib mathtext may parse the expression. Steps: 1. Render valid math. 2. Render malformed math. 3. Render parameter symbols and watermark formulas.",
        "P3",
        "`services.mathtext` cleans unicode/math syntax, maps parameter names to symbols, detects math-like text, renders STIX mathtext to transparent 2x QPixmaps with caching, and returns None on failure so callers can fall back to text. Implementation reference: aetherlab/services/mathtext.py:132 / aetherlab/services/mathtext.py:154 / aetherlab/ui/widgets.py:912 / aetherlab/ui/widgets.py:1208.",
        "Bad math never raises through the UI; it falls back to plain text rendering.",
        "harness",
    ),
    "F121": _story_tuple(
        "US-F121: As a Kazakhstan ENT student, when I start from the empty state, I expect a readable equation-oriented interface and an Open practice entry. Preconditions: a new student session is open. Steps: 1. Show a math summary and parameter rows. 2. Inspect the ENT practice card and setup strip. 3. Confirm math-rendering fallback stays readable.",
        "P3",
        "`AnalysisPanel` prefers math rendering for key equations, `ParameterDock` calls `render_param_symbol()` with text fallback, and `EmptyStateView` includes the ENT Open practice card and setup strip. Implementation reference: aetherlab/ui/analysis_panel.py / aetherlab/ui/parameter_dock.py / aetherlab/ui/shared_widgets.py.",
        "If math rendering fails, text fallback keeps labels visible; the practice action remains available without an API key.",
        "scripted-ui",
    ),
    "F122": _story_tuple(
        "US-F122: As P3 Educator, cloud AI + vision critic, when scene diagnostics, repair, critique, duration, or storyboard data exist, I expect the UI to distill them into stable metadata. Preconditions: SceneBundle may be old, empty, repaired, revised, or critiqued. Steps: 1. Parse scene meta. 2. Normalize storyboard acts. 3. Confirm old bundles return empty/None defaults.",
        "P3",
        "`parse_scene_meta()` distills diagnostics into repaired/revised/critique/duration fields, and `_storyboard_acts()` normalizes storyboard JSON into ordered act dictionaries with duration, beats, hero frame, and narration. Implementation reference: aetherlab/ui/widgets.py:2903 / aetherlab/ui/widgets.py:2949 / aetherlab/core/models.py:121.",
        "Missing storyboard or critique fields degrade to empty acts and None critique instead of KeyError.",
        "harness",
    ),
    "F123": _story_tuple(
        "US-F123: As P3 Educator, cloud AI + vision critic, when a scene is ready, I expect a screening-room UI with code artifact, storyboard seek aids, critique badge, diagnostics drawer, and state chips. Preconditions: SceneBundle is passed to SimulationPanel. Steps: 1. Set scene bundle. 2. Inspect badges/storyboard/code drawer. 3. Click storyboard act to seek.",
        "P3",
        "`SimulationPanel` wires CodeArtifactView, ManimBadge, CritiqueBadge, StoryboardStrip, ActSeekSlider, DiagnosticsDrawer, and `_apply_scene_meta()` populates repaired/revised/critique/storyboard state from the SceneBundle. Implementation reference: aetherlab/ui/widgets.py:1604 / aetherlab/ui/widgets.py:1655 / aetherlab/ui/widgets.py:1666 / aetherlab/ui/widgets.py:1668 / aetherlab/ui/widgets.py:1712 / aetherlab/ui/widgets.py:1873.",
        "Old scene bundles without storyboard/critique still show code/canvas normally and leave optional widgets empty.",
        "scripted-ui",
    ),
    "F124": _story_tuple(
        "US-F124: As P5 Returning user, when I manage research sources and visual critique settings, I expect the library to show indexed chunk freshness and Settings to persist a vision model. Preconditions: library manifest and settings dialog may exist. Steps: 1. Refresh library. 2. Inspect book spines/chunk chips. 3. Save vision model and reload settings.",
        "P5",
        "`LibraryPanel.refresh()` paints `_BookSpine` rows with manifest chunk/freshness state; SettingsDialog includes a VISION CRITIQUE field backed by `vision_model`, and `_open_settings()` persists it through save_app_config into AppSettings. Implementation reference: aetherlab/ui/widgets.py:2661 / aetherlab/ui/widgets.py:3404 / aetherlab/ui/main_window.py:235 / aetherlab/ui/main_window.py:583 / aetherlab/core/settings.py:186.",
        "If the manifest is missing or a file is pending, chips show pending/reindexing state rather than claiming indexed freshness.",
        "scripted-ui",
    ),
    "F125": _story_tuple(
        "US-F125: As P1 Student, no AI key, when local references are thin and web references are enabled, I expect Wikipedia intros to be fetched fail-soft with provenance. Preconditions: internet may or may not be reachable. Steps: 1. Fetch web references for keywords. 2. Simulate offline/malformed response. 3. Deserialize old RagHit rows.",
        "P1",
        "`fetch_web_references()` uses the public MediaWiki API through stdlib urllib, returns RagHit objects with origin web/source_label/source_path, and never raises; RagHit defaults keep old cached rows compatible and `source_name`/`is_web` expose clean labels. Implementation reference: aetherlab/services/web_references.py:98 / aetherlab/core/models.py:96.",
        "Offline, timeout, rate-limit, malformed, or disabled-web cases return an empty list/original RAG result without blocking solve.",
        "harness",
    ),
    "F126": _story_tuple(
        "US-F126: As P1 Student, no AI key, when web references are enabled, I expect local library hits to stay first and web hits to append only within a timeout. Preconditions: RagResult and settings exist. Steps: 1. Merge with web enabled. 2. Disable toggle. 3. Force provider timeout/error.",
        "P1",
        "`_merge_web_references()` runs the provider via asyncio.to_thread under wait_for, appends web hits after local hits, tags backend with +web, and returns the original result if disabled or any error occurs; both pipeline and UI worker use it with settings.web_references/web_ref_timeout. Implementation reference: aetherlab/services/pipeline.py:126 / aetherlab/ui/workers.py:104 / aetherlab/core/settings.py:191.",
        "Web failure never erases local RAG hits or changes a successful local backend into an error state.",
        "harness",
    ),
    "F127": _story_tuple(
        "US-F127: As P1 Student, no AI key, when references and the prompt bar are visible, I expect provenance, blueprint texture, and keyboard focus affordances to be clear. Preconditions: reference hits and command bar exist. Steps: 1. Render local/web cards. 2. Focus prompt. 3. Inspect workspace backdrop and focus rings.",
        "P1",
        "`_RagHitCard` distinguishes web with globe/Wikipedia badge and opens URLs, ReferencePanel counts library/web provenance, BlueprintBackdrop paints the workspace grid, CommandBar toggles a focused property for cyan filament, and QSS defines focus rings. Implementation reference: aetherlab/ui/widgets.py:1258 / aetherlab/ui/widgets.py:1415 / aetherlab/ui/widgets.py:682 / aetherlab/ui/widgets.py:3424 / aetherlab/ui/style.py:551.",
        "Low-score reference cards are dimmed but still readable/clickable; keyboard focus remains visible.",
        "scripted-ui",
    ),
    "F128": _story_tuple(
        "US-F128: As P2 Student, local Ollama, when I choose a provider preset or have Qwen settings nearby, I expect Ollama defaults to fill only when selected and Qwen to remain opt-in. Preconditions: env/app config may contain provider_preset and Qwen settings may exist. Steps: 1. Load settings with ollama preset. 2. Add env overrides. 3. Confirm Qwen ignored unless opted in.",
        "P2",
        "`load_settings()` resolves provider_preset from env then app config; ollama fills base_url/key only when unset and labels provider_source ollama-local, env still wins, and Qwen autoload is gated by AETHERLAB_QWEN_AUTOLOAD=1. Implementation reference: aetherlab/core/settings.py:129 / aetherlab/core/settings.py:131 / aetherlab/core/settings.py:151 / aetherlab/core/settings.py:162.",
        "No AI/offline or unset provider paths do not silently import unrelated developer credentials.",
        "harness",
    ),
    "F129": _story_tuple(
        "US-F129: As P2 Student, local Ollama, when I have Ollama installed, I expect discovery, one-click local AI, and connection tests to be non-crashing and displayable. Preconditions: local Ollama may be running. Steps: 1. Probe installed models. 2. Use empty-state local AI CTA. 3. Test connection in Settings.",
        "P2",
        "`detect_ollama()` GETs /api/tags with short timeout and never raises; `test_connection()` returns displayable ok/message. SettingsDialog exposes provider presets and Test connection, runs the potentially blocking ping in `BackgroundTask`, disables the button while Testing, and cancels result delivery when the dialog closes. MainWindow probes Ollama in a thread and can persist the ollama preset from EmptyStateView. Implementation reference: aetherlab/services/providers.py / aetherlab/ui/background_task.py / aetherlab/ui/main_window.py.",
        "If Ollama is absent or slow, the UI shows no/degraded local-model CTA and no stack trace.",
        "harness",
    ),
    "F130": _story_tuple(
        "US-F130: As P3 Educator, cloud AI + vision critic, when a solver provides governing equations, I expect the first equation to become the hero equation and exports to preserve equations. Preconditions: SolverResult may include key_equations. Steps: 1. Parse remote/fallback solver. 2. Show AnalysisPanel. 3. Export LaTeX/PDF.",
        "P3",
        "`SolverResult.key_equations` round-trips through JSON, the solver prompt requests 1-4 LaTeX equations, fallback equations are domain-selected, AnalysisPanel prefers the first equation via render_math, and LaTeX/PDF export includes a Key Equations section. Implementation reference: aetherlab/core/models.py:50 / aetherlab/services/llm.py:110 / aetherlab/services/llm.py:209 / aetherlab/ui/widgets.py:1211 / aetherlab/services/pdf.py:77.",
        "Old cache rows without key_equations load an empty list and continue rendering prose summaries.",
        "harness",
    ),
    "F131": _story_tuple(
        "US-F131: As P5 Returning user, when I launch or inspect AetherLab, I expect version output, rotating logs, and a correct app icon/taskbar identity. Preconditions: CLI or GUI starts. Steps: 1. Run --version. 2. Launch app. 3. Inspect data_dir/logs and window icon.",
        "P5",
        "`--version` prints AetherLab __version__, `_setup_logging()` adds a rotating data_dir/logs/aetherlab.log handler best-effort, `_icon_path()` finds source/frozen ico assets, and run_app sets the Qt icon plus Windows AppUserModelID. Implementation reference: aetherlab/__main__.py:29 / aetherlab/__main__.py:34 / aetherlab/ui/app.py:12 / aetherlab/ui/app.py:24.",
        "Logging/icon setup failures are best-effort and never block app launch.",
        "harness",
    ),
    "F132": _story_tuple(
        "US-F132: As P5 Returning user, when AetherLab is packaged for Windows, I expect frozen renders to work, LaTeX absence to be handled, and docs/CI to cover the packaging path. Preconditions: packaging scripts and CI files exist. Steps: 1. Inspect PyInstaller/Inno setup. 2. Inspect frozen --manim relay. 3. Check LaTeX detection prompt rule and Windows CI.",
        "P5",
        "`aetherlab --manim` relays to Manim CLI inside frozen bundles, `detect_latex()` gates Text-only scene prompt rules, packaging spec collects Manim/native dependencies, build.py smoke-tests frozen rendering, docs describe setup/troubleshooting, and CI runs on windows-latest. Implementation reference: aetherlab/__main__.py:75 / aetherlab/services/manim_runtime.py:55 / aetherlab/services/scene_generator.py:481 / packaging/aetherlab.spec:17 / .github/workflows/ci.yml:11.",
        "Without LaTeX, scene prompts forbid required MathTex so rendering remains possible.",
        "harness",
    ),
    "F133": _story_tuple(
        "US-F133: As P4 Power user, cloud rendering, when subprocesses run on Windows or Linux, I expect platform-specific flags to stay on the right platform. Preconditions: render/export/frame tools may spawn subprocesses. Steps: 1. Inspect subprocess kwargs on Windows/POSIX. 2. Verify Manim, pdflatex, ffmpeg, and sampling call sites use it.",
        "P4",
        "`subprocess_kwargs()` returns Windows creationflags/no-window/below-normal options or POSIX start_new_session, and render/pdf/GIF/voiceover/scene_critic call sites route subprocesses through it. The long-lived Manim path uses `run_process_tree()`: POSIX kills its isolated process group and Windows invokes documented `taskkill /T` before immediate-process fallback. Implementation reference: aetherlab/core/proc.py / aetherlab/services/manim_runtime.py / aetherlab/services/pdf.py / aetherlab/services/voiceover.py.",
        "Linux cloud runners never receive Windows-only creationflags, avoiding subprocess launch failures.",
        "harness",
    ),
    "F134": _story_tuple(
        "US-F134: As P4 Power user, cloud rendering, when a scene rerenders, I expect isolated per-run media directories and fresh MP4 discovery to prevent frame-cache desync. Preconditions: local render path is used. Steps: 1. Render same scene twice. 2. Inspect run dirs and command flags. 3. Confirm discovery returns this render's fresh MP4.",
        "P4",
        "`render_scene()` creates `_RUNS_DIR/<scene>_<quality>_<uuid>`, passes `--disable_caching`, and `_find_video_in()` returns the class-named MP4 from that render since its start time; old run dirs are pruned. Implementation reference: aetherlab/services/manim_runtime.py:36 / aetherlab/services/manim_runtime.py:457 / aetherlab/services/manim_runtime.py:487 / aetherlab/services/manim_runtime.py:528 / aetherlab/services/manim_runtime.py:950.",
        "If a cached MP4 is later pruned, the pipeline video-validity guard rerenders instead of using the stale path.",
        "harness",
    ),
    "F135": _story_tuple(
        "US-F135: As P3 Educator, cloud AI + vision critic, when a scene is heavy, I expect render budgets and quality promotion to preserve a usable draft if final quality fails. Preconditions: render_scene_with_repair targets non-draft quality. Steps: 1. Estimate render cost. 2. Render draft/repair. 3. Promote final. 4. Force final timeout and confirm draft survives.",
        "P3",
        "`_estimate_render_cost()` scales timeout by duration/updater/play/3D signals, render_scene halves FPS on heavy high-res scenes, and render_scene_with_repair validates/repairs at draft before final promotion, keeping a successful draft when final render fails. Implementation reference: aetherlab/services/manim_runtime.py:466 / aetherlab/services/manim_runtime.py:540 / aetherlab/services/manim_runtime.py:989.",
        "Timeout repair prompts ask for load reduction without stripping the scene to an empty plot.",
        "harness",
    ),
    "F136": _story_tuple(
        "US-F136: As P3 Educator, cloud AI + vision critic, when rendering fails, I expect full evidence dumps and a classified failure kind for repair and cache. Preconditions: render returns error or timeout. Steps: 1. Trigger failure. 2. Inspect data_dir/logs/renders. 3. Inspect SceneBundle.failure_kind.",
        "P3",
        "Render failures retain scene/stderr evidence and a cache-safe failure kind for repair. Exact worker output failures take priority over dependency banners/cleanup: zero MP4s is artifact_missing, multiple is artifact_ambiguous, and invalid downloaded media is artifact_invalid. Missing output includes a timed-animation/retry hint. Implementation reference: aetherlab/services/manim_runtime.py / aetherlab/services/render_backend.py / aetherlab/core/models.py / tests/test_cloud_failure_diagnosis.py.",
        "Unknown failures still get evidence dumps and failure_kind unknown, not silent disappearance.",
        "harness",
    ),
    "F137": _story_tuple(
        "US-F137: As P5 Returning user, when using a frozen build, I expect bundled Manim native dependencies to make text rendering and PyAV encoding work. Preconditions: PyInstaller spec/build is used. Steps: 1. Inspect collected packages/hidden imports. 2. Run frozen smoke. 3. Confirm `--manim render` path works.",
        "P5",
        "`packaging/aetherlab.spec` uses collect_all for Manim, manimpango, skia_pathops, moderngl, moderngl_window, av, cloup and metadata/hidden imports; `__main__.py` handles the `--manim` relay for frozen rendering. Implementation reference: packaging/aetherlab.spec:17 / packaging/aetherlab.spec:48 / aetherlab/__main__.py:75.",
        "Missing native dependencies would fail frozen render smoke; the spec keeps them bundled.",
        "harness",
    ),
    "F138": _story_tuple(
        "US-F138: As P3 Educator, cloud AI + vision critic, when narration is enabled, I expect edge-tts audio to fit the whole video without trimming closing beats. Preconditions: edge-tts/imageio ffmpeg/PyAV may be available. Steps: 1. Add voiceover to a video. 2. Compare durations. 3. Confirm adjusted re-synthesis/merge behaviour.",
        "P3",
        "`voiceover.add_voiceover()` synthesizes audio, measures durations with PyAV, optionally re-synthesizes once at adjusted rate, and merges with imageio-ffmpeg using tpad/no-shortest semantics so full video remains; subprocesses use cross-platform kwargs. Implementation reference: aetherlab/services/voiceover.py:8 / aetherlab/services/voiceover.py:95 / aetherlab/services/voiceover.py:153.",
        "If edge-tts, ffmpeg, or duration measurement fails, voiceover returns None and the silent render is kept.",
        "harness",
    ),
    "F139": _story_tuple(
        "US-F139: As P3 Educator, cloud AI + vision critic, when narration is enabled after final render, I expect a script derived from final scene code and storyboard, then a narrated MP4 while preserving the silent render. Preconditions: successful rendered scene and narration_enabled. Steps: 1. Render scene. 2. Generate narration script. 3. Add voiceover. 4. Inspect video_path and silent_video_path.",
        "P3",
        "`SceneGenerator.narrate()` writes one flowing voiceover from final scene code and storyboard beats; ManimRuntime `_add_narration()` calls voiceover helpers after successful render, swaps video_path to the narrated MP4, and stores the previous silent path on silent_video_path. Implementation reference: aetherlab/services/scene_generator.py:603 / aetherlab/services/manim_runtime.py:738 / aetherlab/services/manim_runtime.py:804 / aetherlab/core/models.py:138.",
        "Any narration failure leaves the original silent video as the active output.",
        "harness",
    ),
    "F140": _story_tuple(
        "US-F140: As P5 Returning user, when I configure narration, I expect env/app-config/manim-bot aliases to resolve and the Settings dialog toggle to persist. Preconditions: settings dialog or env vars are available. Steps: 1. Set narration env/app config. 2. Save Settings narration checkbox/voice. 3. Reload settings and old cache rows.",
        "P5",
        "`AppSettings` includes narration_enabled, tts_voice, and tts_rate; `load_settings()` reads AETHERLAB and manim-bot voiceover aliases plus app config; SettingsDialog renders/persists the narration checkbox and voice field; SceneBundle old cache rows default silent_video_path to empty. Implementation reference: aetherlab/core/settings.py:40 / aetherlab/core/settings.py:194 / aetherlab/ui/main_window.py:273 / aetherlab/ui/main_window.py:585 / aetherlab/core/models.py:160.",
        "Narration defaults off, so older projects and missing TTS dependencies keep silent rendering behaviour.",
        "harness",
    ),
    "F141": _story_tuple(
        "US-F141: As P1 Student, no AI key, when I request a lesson topic, I expect a coherent curriculum plan from either the LLM or deterministic domain template. Preconditions: topic and audience are provided; API key may be absent. Steps: 1. Plan a lesson. 2. Inspect objectives, chapters, equations, questions, and cache-compatible models. 3. Repeat keyless/failure path.",
        "P1",
        "`plan_lesson()` uses a hot LLM strict-JSON planner when possible and falls back to `_template_lesson()`; LessonChapter, LessonQuestion, LessonPlan, and LessonBundle from_json loaders keep old caches compatible. Implementation reference: aetherlab/services/lesson_planner.py:73 / aetherlab/services/lesson_planner.py:156 / aetherlab/core/models.py:191 / aetherlab/core/models.py:257 / aetherlab/core/models.py:314.",
        "Planner/RAG/JSON failure returns a deterministic domain lesson with objectives, chapters, equations, and questions instead of failing lesson mode.",
        "harness",
    ),
    "F142": _story_tuple(
        "US-F142: As P1 Student, no AI key, when lesson chapters are narrated, I expect each clip to get whole-clip narration and a cumulative transcript timeline. Preconditions: chapter clip and narration text may exist. Steps: 1. Narrate a chapter segment. 2. Build SRT from ordered durations. 3. Include blank chapters and confirm timing advances without cues.",
        "P1",
        "`voiceover.narrate_segment()` narrates a single chapter clip and reports spoken duration; `build_srt()` converts ordered text/duration segments into cumulative SRT cues while blank text consumes time without emitting a cue. Implementation reference: aetherlab/services/voiceover.py:225 / aetherlab/services/voiceover.py:254.",
        "Missing clip/TTS/ffmpeg keeps the silent clip and returns usable timeline data where possible.",
        "harness",
    ),
    "F143": _story_tuple(
        "US-F143: As P1 Student, no AI key, when I build a multi-chapter lesson, I expect chapters to render through the normal scene pipeline, assemble to an MP4/SRT, and survive partial failures with alignment intact. Preconditions: topic exists; some chapters may fail. Steps: 1. Run LessonPipeline. 2. Inspect rendered_chapter_indexes, lesson.mp4, and lesson.srt. 3. Simulate a failed middle chapter.",
        "P1",
        "`LessonPipeline.run()` plans, renders renderable chapters with generate/render pipeline and bounded progress, records rendered_chapter_indexes, narrates surviving chapters, assembles with `assemble_lesson()`, and writes SRT with offsets returned by assembly. Implementation reference: aetherlab/services/lesson_pipeline.py:57 / aetherlab/services/lesson_pipeline.py:131 / aetherlab/services/lesson_pipeline.py:153 / aetherlab/services/lesson_pipeline.py:263 / aetherlab/services/assembly.py:53.",
        "Bad chapters are skipped; surviving clips keep their plan indexes so narration, titles, offsets, and subtitles remain attached to the right chapter.",
        "harness",
    ),
    "F144": _story_tuple(
        "US-F144: As P3 Educator, cloud AI + vision critic, when lesson content is grounded, I expect citations/fact-check notes and a study guide export. Preconditions: RAG references and optional API key may exist. Steps: 1. Fact-check lesson. 2. Inspect chapter citations/notes. 3. Export study guide.",
        "P3",
        "`fact_check_lesson()` attaches citations and optionally uses a temp-0 model to check/correct narration before rendering; `export_lesson_study_guide()` writes objectives, prerequisites, misconception, chapters, equations, citations, and self-check. Implementation reference: aetherlab/services/fact_check.py:1 / aetherlab/services/lesson_pipeline.py:73 / aetherlab/services/pdf.py:156.",
        "No key or RAG failure leaves chapters usable with best-effort citations rather than blocking rendering.",
        "harness",
    ),
    "F145": _story_tuple(
        "US-F145: As P1 Student, no AI key, when I press Learn, I expect a cancellable worker, running progress, lesson player, transcript, questions, references, chapter seeking, playground, and study-guide export. Preconditions: command bar has a topic. Steps: 1. Press Learn. 2. Watch progress. 3. Interact with LessonView tabs and chapter outline. 4. Export study guide.",
        "P1",
        "`CommandBar.learn_requested` starts `LessonWorker`; MainWindow shows RunningView and then populates LessonView; LessonView handles inline video, transcript, _QuestionCard MCQs, references, chapter seek using rendered_chapter_indexes, interactive LiveCanvas, regenerate, and export signals. Implementation reference: aetherlab/ui/workers.py:231 / aetherlab/ui/main_window.py:1164 / aetherlab/ui/widgets.py:3523 / aetherlab/ui/widgets.py:3698 / aetherlab/ui/widgets.py:3815.",
        "QtMultimedia absence, cancellation, or partial lesson state shows guarded messages rather than a blank lesson page.",
        "scripted-ui",
    ),
    "F146": _story_tuple(
        "US-F146: As P1 Student, no AI key, when a keyless lesson renders multiple chapters, I expect setup, evolution, math, and recap clips to look distinct while staying Text-only and safe. Preconditions: chapter aspect is passed to scene template. Steps: 1. Render each aspect/domain. 2. Compile and safety-check. 3. Compare visual composition roles.",
        "P1",
        "`scene_templates.build_scene()` accepts aspect values and emits distinct header/composition styles; ManimRuntime passes aspect through `_build_scene_code()` and solve defaults to full. Implementation reference: aetherlab/services/scene_templates.py:122 / aetherlab/services/manim_runtime.py:880.",
        "Unknown or missing aspect falls back to the full/evolution-safe composition.",
        "harness",
    ),
    "F147": _story_tuple(
        "US-F147: As P1 Student, no AI key, when lesson chapters have roles, I expect aspect assignment to follow chapter kind/title/position so the lesson arc is coherent. Preconditions: LessonPlan chapters exist. Steps: 1. Call _chapter_aspect for recap/equation/first/normal chapters. 2. Confirm aspects flow setup, evolution, math, recap.",
        "P1",
        "`_chapter_aspect()` maps recap kind to recap, equation_card and math keywords to math, recap keywords to recap, first renderable chapter to setup, and remaining renderable chapters to evolution. Implementation reference: aetherlab/services/lesson_pipeline.py:316.",
        "Id-less LLM chapters are handled by object/position/role logic rather than comparing empty ids.",
        "harness",
    ),
    "F148": _story_tuple(
        "US-F148: As P1 Student, no AI key, when a produced lesson is assembled, I expect title/chapter/end cards, normalized clips, crossfades, audio handling, and fallback concat if effects fail. Preconditions: rendered chapter clips exist. Steps: 1. Assemble with card metadata. 2. Inspect produced MP4 offsets. 3. Force card/xfade fallback.",
        "P1",
        "`render_card_png()` creates Pillow cards; `assemble_lesson()` builds intro/chapter/end segment plan, normalizes to 1280x720/30fps, adds silence for cards/mixed audio, crossfades with cumulative offsets, and falls back to normalized concat or clips. Implementation reference: aetherlab/services/cards.py:80 / aetherlab/services/assembly.py:53 / aetherlab/services/assembly.py:282.",
        "PIL/ffmpeg/xfade failure degrades to a simpler playable lesson rather than losing all chapter clips.",
        "harness",
        "PASS",
        "None",
        "PASS",
    ),
    "F149": _story_tuple(
        "US-F149: As P5 Returning user, when I reopen the same lesson topic/audience, I expect planning and fact-checking to reuse a disk cache unless I regenerate. Preconditions: data_dir is writable. Steps: 1. Build a lesson. 2. Build same topic/audience again. 3. Build with regenerate=True.",
        "P5",
        "`_PlanCache` stores planned/fact-checked LessonPlan by normalized topic+audience hash, `LessonPipeline.run()` checks it before planning/grounding, and regenerate bypasses plan and chapter caches. Implementation reference: aetherlab/services/lesson_pipeline.py:75 / aetherlab/services/lesson_pipeline.py:100 / aetherlab/services/lesson_pipeline.py:396.",
        "Cache read/write errors miss silently so lesson generation continues.",
        "harness",
    ),
    "F150": _story_tuple(
        "US-F150: As P1 Student, no AI key, when I cancel Learn or press Regenerate, I expect a cooperative stop with partial content or a fresh rebuild. Preconditions: lesson worker is running or a lesson topic exists. Steps: 1. Start Learn. 2. Cancel via Escape/Cancel. 3. Press Regenerate. 4. Confirm cache bypass.",
        "P1",
        "`LessonPipeline.run()` passes cancel_check into every active chapter tournament/render and returns a cancelled LessonBundle with rendered partials; local Manim trees and cloud polling stop promptly instead of waiting for the current chapter's full timeout. `LessonWorker.cancel()` sets an event; MainWindow handles lesson workers; LessonView Regenerate emits regenerate_requested to start_lesson(regenerate=True). Implementation reference: aetherlab/services/lesson_pipeline.py / aetherlab/services/manim_runtime.py / aetherlab/services/render_backend.py / aetherlab/ui/workers.py / aetherlab/ui/main_window.py / aetherlab/ui/widgets.py.",
        "Cancellation never raises into the UI; on_lesson_ready shows finished chapters or a clear cancelled message.",
        "harness",
    ),
    "F151": _story_tuple(
        "US-F151: As P5 Returning user, when an old or partial lesson opens, I expect skipped chapters to be marked and surviving offsets to remain correct. Preconditions: LessonBundle may include rendered_chapter_indexes or legacy data. Steps: 1. Load partial bundle. 2. Inspect chapter outline markers/tooltips. 3. Click surviving chapter.",
        "P5",
        "`LessonView.set_lesson()` reads `rendered_chapter_indexes`, marks skipped renderable chapters as not rendered, and uses true produced-video offsets for surviving rows; LessonBundle.from_json defaults the mapping for old caches. Implementation reference: aetherlab/ui/widgets.py:3698 / aetherlab/ui/widgets.py:3715 / aetherlab/core/models.py:333 / aetherlab/core/models.py:364.",
        "Old bundles without the mapping use the legacy cumulative fallback rather than crashing.",
        "scripted-ui",
    ),
    "F152": _story_tuple(
        "US-F152: As P4 Power user, cloud rendering, when rendering is selected, I expect a backend abstraction that can choose local/cloud/auto without changing the repair pipeline. Preconditions: render settings exist. Steps: 1. Select backend. 2. Render one shot. 3. Confirm render_scene compatibility path remains local.",
        "P4",
        "`render_backend.py` defines RenderBackend, local/cloud implementations, select_backend, cloud_job_id, and timeout/fps helpers; ManimRuntime `_render_once()` routes one-shot renders through selected backend while render_scene remains local compatibility. Implementation reference: aetherlab/services/render_backend.py:166 / aetherlab/services/render_backend.py:410 / aetherlab/services/render_backend.py:480 / aetherlab/services/manim_runtime.py:762.",
        "Missing cloud availability falls back through the local backend without changing scene repair semantics.",
        "harness",
    ),
    "F153": _story_tuple(
        "US-F153: As P4 Power user, cloud rendering, when I configure cloud render settings, I expect env/app-config/legacy manim-bot aliases to resolve with local default preserved. Preconditions: env/app config/legacy `.env` may exist. Steps: 1. Set render mode and GitHub fields. 2. Save Settings. 3. Reload settings with CLOUD_RENDER_ENABLED aliases.",
        "P4",
        "`AppSettings` includes render_mode, provider, GitHub repo/token/workflow/branch/client id, thresholds, poll and timeout; `load_settings()` resolves AetherLab and legacy CLOUD_RENDER aliases and SettingsDialog persists the fields. Implementation reference: aetherlab/core/settings.py:42 / aetherlab/core/settings.py:201 / aetherlab/ui/main_window.py:185 / aetherlab/ui/main_window.py:570.",
        "Default render_mode remains local unless explicit config or legacy enabled flag maps to auto.",
        "harness",
    ),
    "F154": _story_tuple(
        "US-F154: As P4 Power user, cloud rendering, when GitHub Actions cloud render is available, I expect secret scanning, workflow provisioning, dispatch, exact job matching, artifact download, validation, and cache reuse. Preconditions: repo/token or gh auth is available. Steps: 1. Render cloud scene. 2. Poll job. 3. Download artifact. 4. Repeat identical scene.",
        "P4",
        "`CloudRenderBackend` scans payloads, computes content job ids, provisions workflow, commits job code, dispatches workflow_dispatch, polls exact runs, follows signed redirects safely, downloads/validates MP4s into local run dirs, and records a manifest cache; auth can come from settings/env or gh. Implementation reference: aetherlab/services/render_backend.py:211 / aetherlab/services/render_backend.py:244 / aetherlab/services/render_backend.py:256 / aetherlab/services/render_backend.py:492.",
        "Cloud errors return cloud-unavailable diagnostics for local fallback; secrets are masked before surfacing.",
        "live-cloud",
    ),
    "F155": _story_tuple(
        "US-F155: As P4 Power user, cloud rendering, when cloud is unavailable, I expect local fallback and a visible warning, not a failed render. Preconditions: render mode cloud/auto and cloud dispatch unavailable. Steps: 1. Force cloud unavailable. 2. Render. 3. Inspect diagnostics, status bar, and backend chip.",
        "P4",
        "`CloudRenderBackend` returns a cloud-unavailable SceneBundle, `ManimRuntime._render_once()` restores compiled state and invokes LocalRenderBackend, and MainWindow/SimulationPanel surface Local fallback diagnostics/chip/toast. Implementation reference: aetherlab/services/render_backend.py:371 / aetherlab/services/manim_runtime.py:762 / aetherlab/ui/main_window.py:1421 / aetherlab/ui/widgets.py:1885.",
        "Cloud failure does not poison the scene cache as a successful cloud render.",
        "harness",
    ),
    "F156": _story_tuple(
        "US-F156: As P4 Power user, cloud rendering, when sending code to a public or private render repo, I expect obvious secrets to be blocked and diagnostics redacted. Preconditions: generated scene code may contain token-like strings. Steps: 1. Scan payload with token patterns. 2. Trigger cloud diagnostic masking. 3. Read docs privacy warning.",
        "P4",
        "`scan_cloud_payload()` refuses common private-key/API/token patterns before upload, `_mask()` redacts GitHub/OpenAI token shapes in diagnostics, and docs explain privacy/public repo implications. Implementation reference: aetherlab/services/render_backend.py:492 / aetherlab/services/render_backend.py:563 / docs/CLOUD_RENDERING.md:39.",
        "Public repos are allowed for shareable scene code, but token-like payloads are blocked before commit.",
        "harness",
    ),
    "F157": _story_tuple(
        "US-F157: As P4 Power user, cloud rendering, when I configure cloud from the UI, I expect render mode fields, token helpers, test cloud render, streamed backend progress, and Local/Cloud chip feedback. Preconditions: SettingsDialog and SimulationPanel are visible. Steps: 1. Edit cloud fields. 2. Click Get token/Test cloud render. 3. Render and inspect backend chip.",
        "P4",
        "`SettingsDialog` adds render mode, GitHub repo/token/workflow/branch, threshold, Get token, and Test cloud render controls. Both network actions run in cancellable `BackgroundTask`s so the dialog remains responsive; device login opens the verification URL from the GUI thread, respects GitHub's polling interval, adds five seconds after `slow_down`, and cancels result delivery on close. PipelineWorker streams backend progress; SimulationPanel sets Cloud/Local fallback/Local chips from diagnostics. Implementation reference: aetherlab/ui/background_task.py / aetherlab/ui/main_window.py / aetherlab/ui/workers.py / aetherlab/ui/widgets.py.",
        "Failed cloud tests show status/result text and do not expose tokens in messages.",
        "scripted-ui",
    ),
    "F158": _story_tuple(
        "US-F158: As P4 Power user, when setting up cloud rendering, I expect the worker and docs to describe a reproducible render repo that publishes my scene. Preconditions: repository contains workflow/docs. Steps: 1. Inspect pins/setup/permissions. 2. Confirm bundled/shipped workflow parity. 3. Render a named scene. 4. Confirm exactly one final scene output is published, excluding fragments. 5. Try missing and ambiguous outputs.",
        "P4",
        "The pinned workflow renders the committed scene and publishes one exact class-named MP4. Partial fragments and unrelated larger outputs cannot replace it. Workflow version participates in the cache key. Bundled/shipped workflow and setup guide agree. Implementation reference: .github/workflows/render.yml / aetherlab/services/render_backend.py / tests/test_cloud_output_identity.py / docs/CLOUD_RENDERING.md.",
        "Missing or multiple exact outputs fail with an explicit count and produce no renamed job MP4; setup documentation explains repo visibility and permissions. Live worker verification remains required.",
        "harness",
    ),
    "F159": _story_tuple(
        "US-F159: As P1 Student, no AI key, when the redesigned UI loads, I expect blue-graphite styling and a consistent sky-blue accent with stable object names. Preconditions: UI modules and styles import. Steps: 1. Inspect QSS and Theme tokens. 2. Construct widgets. 3. Confirm the canvas and main controls use the same accent.",
        "P1",
        "`style.py`, `theme.py`, shared widgets, simulation widgets, and live_canvas expose blue-graphite/sky-blue styling with stable object names and an export button. Implementation reference: aetherlab/ui/style.py / aetherlab/ui/theme.py / aetherlab/ui/shared_widgets.py / aetherlab/ui/simulation_panel.py / aetherlab/ui/live_canvas.py.",
        "Stable object names let tests and future styling target controls without brittle text scraping.",
        "scripted-ui",
    ),
    "F160": _story_tuple(
        "US-F160: As P3 Educator, cloud AI + vision critic, when visual critique scores exist, I expect them persisted and optionally used to reject low-quality cached scenes. Preconditions: vision critique may run and min_quality_score may be set. Steps: 1. Render with critique. 2. Serialize/cache SceneBundle. 3. Raise min_quality_score and attempt reuse.",
        "P3",
        "`SceneBundle` stores quality_score/verdict/issues; render_scene_with_repair copies critic results; settings min_quality_score defaults 0; pipeline, UI worker, and lesson chapter cache reject below-threshold cached scenes when opted in. Implementation reference: aetherlab/core/models.py:141 / aetherlab/core/settings.py:277 / aetherlab/services/pipeline.py:110 / aetherlab/ui/workers.py:278 / aetherlab/services/lesson_pipeline.py:368.",
        "Default threshold 0 preserves legacy cache reuse; opt-in threshold regenerates low-scoring cached scenes.",
        "harness",
    ),
    "F161": _story_tuple(
        "US-F161: As P3 Educator, cloud AI + vision critic, when I opt into multiple candidates, I expect a bounded tournament that scores draft renders and finalizes only the best surviving scene. Preconditions: scene_candidates > 1, API key, and vision_model. Steps: 1. Generate tournament. 2. Observe safety/lint/draft render/critique. 3. Confirm winner final render.",
        "P3",
        "`generate_render_tournament()` is enabled only with candidates>1 plus key/vision; it builds candidates, gates safety/validation, draft-renders with concurrency, scores via scene_critic, drops failures, chooses by score/issues/duration, and sends winner through existing repair/critique/final path. Implementation reference: aetherlab/core/settings.py:282 / aetherlab/services/manim_runtime.py:219 / aetherlab/services/manim_runtime.py:224 / aetherlab/services/manim_runtime.py:280.",
        "N=1, missing vision config, or tournament errors fall back to the existing single-scene path.",
        "harness",
    ),
    "F162": _story_tuple(
        "US-F162: As P3 Educator, cloud AI + vision critic, when visual regression runs in strict mode, I expect render crashes, hard quality issues, warnings, and baseline regressions to affect the exit code. Preconditions: visual_regression report exists and optional baseline. Steps: 1. Run audit. 2. Compare baseline. 3. Call decide_exit strict/non-strict.",
        "P3",
        "`quality_failures()` flags hard video issues, `compare_report()` computes baseline regressions, and `decide_exit()` fails on render crashes always plus quality/warnings/regressions under --strict while keeping non-strict legacy behavior. Implementation reference: tools/visual_regression.py:524 / tools/visual_regression.py:555 / tools/visual_regression.py:593.",
        "Non-strict mode remains usable for exploratory runs; strict mode is the release gate.",
        "harness",
    ),
    "F163": _story_tuple(
        "US-F163: As P3 Educator, cloud AI + vision critic, when codegen prompts are built, I expect a domain-matched exemplar to be appended fail-soft. Preconditions: solver keywords/variables exist. Steps: 1. Select exemplar for oscillator/pendulum/orbit/wave. 2. Build exemplar block. 3. Inspect SceneGenerator prompt.",
        "P3",
        "`scene_exemplars.exemplar_for()` and `exemplar_block()` choose curated compile/safety/lint-tested Text-only examples by detected domain, and SceneGenerator appends the block to storyboard and single-call codegen prompts. Implementation reference: aetherlab/services/scene_exemplars.py:188 / aetherlab/services/scene_exemplars.py:208 / aetherlab/services/scene_generator.py:472.",
        "If exemplar selection fails, the prompt is unchanged and generation continues.",
        "harness",
    ),
    "F164": _story_tuple(
        "US-F164: As a maintainer, when new visible surfaces are added, I expect an audit to catch untracked flags, settings, buttons, actions, combo items, and Kazakh/Russian/English copy maps. Preconditions: source tree and tracker CSV exist. Steps: 1. Run feature_surface_audit --check. 2. Inspect JSON output. 3. Add an uncovered surface or locale map and confirm failure until a feature story covers its source module and languages.",
        "P3",
        "`tools/feature_surface_audit.py` parses app source for literal controls, CLI flags, settings, and nested multilingual copy dictionaries; it uses Unicode-aware tokenization and requires a tracker row to reference a localized module and its supported languages. It exits non-zero on uncovered items and emits matched feature IDs in JSON mode. Implementation reference: tools/feature_surface_audit.py:1.",
        "Generic controls are filtered; user-facing locale maps and non-Latin labels remain visible to the coverage gate.",
        "harness",
    ),
    "F165": _story_tuple(
        "US-F165: As a maintainer, when tracker artifacts drift, I expect the integrity audit to fail before commits hide the mismatch. Preconditions: generator, CSV, XLSX, result JSON, tests, and error log exist. Steps: 1. Run tracker_integrity_audit --check. 2. Modify one artifact by hand. 3. Confirm non-zero drift report.",
        "P3",
        "`tracker_integrity_audit` imports the generator, applies results, compares CSV/XLSX exactly, checks contiguous IDs, non-empty user story/expected/story columns, valid methods/statuses/personas/phase results, test/result parity, DEFECTS consistency, and documented bug IDs. Implementation reference: tools/tracker_integrity_audit.py:1 / build_feature_tracker.py:1.",
        "Any hand-edited tracker artifact or undocumented defect fails the gate.",
        "harness",
    ),
    "F166": _story_tuple(
        "US-F166: As P5 Returning user, when I export a lesson bundle, I expect a portable ZIP with relative HTML/player media, subtitles, study guide, metadata, and scene source but no secrets or private absolute paths. Preconditions: assembled lesson exists. Steps: 1. Export bundle. 2. Move ZIP/extract folder. 3. Open HTML and inspect metadata.",
        "P5",
        "`export_lesson_bundle()` atomically writes index.html, metadata.json, README, study_guide.tex, media lesson MP4/SRT/VTT, and chapter scene files using share-safe relative asset names; LessonView/MainWindow wire Export bundle to a save dialog and a non-blocking Exporting lesson bundle `BackgroundTask`. Implementation reference: aetherlab/services/share_export.py / aetherlab/ui/widgets.py / aetherlab/ui/main_window.py.",
        "Missing assembled video or asset failures produce status/errors without writing a misleading share bundle.",
        "harness",
        "FAIL",
        "BUG-26; BUG-57",
        "PASS",
    ),
    "F167": _story_tuple(
        "US-F167: As P5 Returning user, when I answer lesson quiz questions, I expect local course progress, scoring, missed concepts, and a next-topic recommendation to persist. Preconditions: lesson plan has questions. Steps: 1. Answer a quiz card. 2. Inspect course_progress.json. 3. Reload and verify summary/recommendation.",
        "P5",
        "`CourseProgressStore.record_quiz_answer()` persists attempts by lesson_key with correctness, choice, concept, and timestamp; LessonView question cards emit graded answers; MainWindow records them and updates the course status strip. Implementation reference: aetherlab/services/course_mode.py:23 / aetherlab/services/course_mode.py:29 / aetherlab/services/course_mode.py:117 / aetherlab/ui/widgets.py:3466 / aetherlab/ui/main_window.py:1259.",
        "If progress cannot be saved, the status bar reports the issue and the lesson remains usable.",
        "harness",
        "FAIL",
        "BUG-27; BUG-44; BUG-45",
        "PASS",
    ),
    "F168": _story_tuple(
        "US-F168: As a maintainer, when prompt or render quality changes, I expect Prompt Quality Lab to render canonical tasks and produce lightweight scored reports for before/after comparison. Preconditions: local pipeline can render; provider mode may be allowed explicitly. Steps: 1. Run prompt_quality_lab. 2. Inspect summary.json, summary.md, scores.csv. 3. Compare against prior report.",
        "P3",
        "`tools/prompt_quality_lab.py` defines canonical prompts, renders via the real local pipeline, reuses visual_regression metrics and quality_failures, records storyboard/critic data, writes summary.md and scores.csv, and compares against previous reports; docs describe safe provider mode. Implementation reference: tools/prompt_quality_lab.py:201 / tools/prompt_quality_lab.py:215 / tools/prompt_quality_lab.py:379 / docs/PROMPT_QUALITY_LAB.md:6.",
        "Reports are written under ignored analysis output and avoid committing raw videos or secrets.",
        "harness",
    ),
    "F169": _story_tuple(
        "US-F169: As P3 Educator/maintainer, when I change generation, prompts, or the critic, I expect a committed golden-set baseline to fail my run if it lowers quality. Preconditions: tools/prompt_quality_baseline.json is committed. Steps: 1. Run `prompt_quality_lab --gate`. 2. Confirm an unchanged/improved run passes. 3. Confirm a mean-score or pass-rate regression exits non-zero.",
        "P3",
        "`load_prompt_set()` returns a >=12-prompt golden set spanning mechanics/waves/fields/orbital plus a lesson, all renderable keyless. `evaluate_gate(baseline, report, score_tolerance)` is a pure ratchet: it reports ok=False with reasons when the mean score falls beyond the tolerance or the render pass rate drops, and main() wires --gate/--baseline/--score-tolerance to exit 2 on regression. Implementation reference: tools/prompt_quality_lab.py:1 / tools/prompt_quality_baseline.json:1 / docs/QUALITY_FLYWHEEL_MISSION.md:1.",
        "If the baseline file is missing the gate exits 3 with an actionable message; render non-determinism within tolerance never trips the gate.",
        "harness",
    ),
    "F170": _story_tuple(
        "US-F170: As P3 Educator, cloud AI + vision critic, when a render is judged, I expect a five-axis 0-2 breakdown I can rank on; and as P1 Student, no AI key, I expect a deterministic static proxy so ranking still works offline. Preconditions: a rendered scene exists. Steps: 1. Parse a critic reply into a breakdown. 2. Feed a malformed breakdown and confirm it is approximated, not zeroed. 3. Estimate a keyless scene statically and confirm a worse scene ranks lower.",
        "P3",
        "`CRITIC_AXES` fixes the five 0-2 axes; `_coerce_breakdown()` validates the model's breakdown against the schema and approximates-and-flags malformed output instead of silent-zeroing; `static_quality_estimate()` maps the static battery to the same axes with verdict skipped; `SceneBundle.critique_breakdown` persists backward-compatibly and all three manim_runtime copy sites propagate it. Implementation reference: aetherlab/services/scene_critic.py:1 / aetherlab/core/models.py:145 / aetherlab/services/manim_runtime.py:266.",
        "Malformed LLM breakdowns are approximated (never silent-zeroed); old caches without the field load cleanly; keyless mode ranks by the static proxy without a vision model; the critic never raises.",
        "harness",
    ),
    "F171": _story_tuple(
        "US-F171: As P4 Power user, cloud rendering, when a tournament renders several candidates at once, I expect each to get its own cloud job and artifact even if two candidates produced identical code. Preconditions: a render repo/token may be configured; the headless test stubs GitHub. Steps: 1. Salt cloud_job_id per candidate. 2. Concurrently render identical-code candidates. 3. Confirm distinct job ids and no shared artifact.",
        "P4",
        "`cloud_job_id(scene, quality, fps, variant)` salts the content-addressed id (and cloud cache key) so concurrent byte-identical candidates cannot collide on jobs/<id>.py or <id>.mp4 (the BUG-15 race); variant='' preserves the legacy id and single-scene cache. `_render_once(variant=...)` threads it and `_render_and_score_candidates` passes cand<index>; keyless candidates are ranked by the static proxy, not dropped. Implementation reference: aetherlab/services/render_backend.py:480 / aetherlab/services/manim_runtime.py:763 / tools/cloud_tournament_smoke.py:1.",
        "A candidate's cloud failure scores it out without aborting the tournament; whole-cloud-unavailable falls back to local; identical-code candidates never share an artifact.",
        "harness",
    ),
    "F172": _story_tuple(
        "US-F172: As P3 Educator/maintainer, when the visual critic repeatedly names the same aesthetic problem, I expect the next scene generation to avoid it. Preconditions: a tournament ran and named issues on losing candidates. Steps: 1. Record losing candidates' issues. 2. Confirm the top pitfalls appear in the generation prompt. 3. Confirm an empty store adds nothing.",
        "P3",
        "`AestheticPitfallStore` tallies normalized critic issue phrases (fail-soft, TTL); `preventive_pitfalls_block(store)` appends the top learned pitfalls to the codegen system prompt while the no-arg form stays the static block; `generate_render_tournament` records losing candidates' issues after winner selection. Implementation reference: aetherlab/services/error_learner.py:119 / aetherlab/services/scene_generator.py:427 / aetherlab/services/manim_runtime.py:250.",
        "A missing/empty/corrupt store contributes nothing and never breaks generation; only losing candidates' issues are learned; the static pitfalls always remain.",
        "harness",
    ),
    "F173": _story_tuple(
        "US-F173: As P3 Educator/maintainer, when a tournament yields a critic-approved high-scoring winner, I expect it captured for review and one-command promotion — but never auto-added to the prompt. Preconditions: a vision critic scored a winner 'ship' >= 8.5. Steps: 1. Record the winner. 2. Confirm skipped/low/revise winners are rejected. 3. List candidates and emit a paste-ready snippet.",
        "P3",
        "`ExemplarCandidateStore.record()` accepts only verdict 'ship' at score >= PROMOTE_MIN_SCORE (rejecting static/skipped, revise, low, empty; dedup by code); `generate_render_tournament` records the winner; `tools/promote_exemplar.py` lists/shows/emits candidates and never writes scene_exemplars.py. Implementation reference: aetherlab/services/scene_exemplars.py:226 / aetherlab/services/manim_runtime.py:250 / tools/promote_exemplar.py:1.",
        "A missing/corrupt store yields no candidates and never breaks a render; only genuine vision winners are stored; the curated exemplar source is only ever changed by a reviewed human edit.",
        "harness",
    ),
    "F174": _story_tuple(
        "US-F174: As P4 Power user, cloud rendering, when I raise the candidate cap, I expect easy or already-good scenes to still cost one render and only hard, weak ones to fan out. Preconditions: the tournament is enabled (cap > 1). Steps: 1. Score a storyboard's difficulty. 2. Render one candidate. 3. Confirm a strong or easy first render does not escalate while a weak+hard one does.",
        "P4",
        "`storyboard_difficulty()` + `candidate_budget()` derive a conservative [1, cap] budget; `generate_render_tournament` renders one candidate, then fans out the remaining budget only when the first score < ESCALATE_BELOW_SCORE and the budget allows. Implementation reference: aetherlab/services/manim_runtime.py:55 / aetherlab/services/manim_runtime.py:264.",
        "A strong first render ships without fan-out; an easy scene never escalates; a first-batch failure still falls back to the single-scene path; keyless static scores usually clear the bar so keyless runs stay single-candidate.",
        "harness",
    ),
    "F175": _story_tuple(
        "US-F175: As P4 Power user, cloud rendering, when renders run in the cloud or a tournament picks a winner, I expect a persisted, secret-free ledger I can inspect. Preconditions: renders/tournaments occur. Steps: 1. Record a job's lifecycle + candidates + winner. 2. Confirm a failure log tail is scrubbed of tokens. 3. Confirm the tournament and cloud paths write the ledger.",
        "P4",
        "`RenderJobLedger` persists per-job status timelines, per-candidate scores, the winner, scrubbed failure log tails, and fallback reason/path (capped, fail-soft); `scrub()` redacts credentials from every free-text field; the tournament, cloud backend, and local-fallback paths all write it. Implementation reference: aetherlab/services/render_ledger.py:1 / aetherlab/services/render_backend.py:262 / aetherlab/services/manim_runtime.py:250.",
        "A missing/corrupt ledger never breaks a render; no token/key/bearer/private-key ever persists; unknown states are never written; the ledger stays bounded.",
        "harness",
    ),
    "F176": _story_tuple(
        "US-F176: As P4 Power user, cloud rendering, when I open the render-farm dashboard, I expect a readable list of jobs with per-candidate scores, the winner, sanitized failures, and fallback reasons. Preconditions: a ledger may exist under the data dir. Steps: 1. Open the dashboard from Settings. 2. Select a tournament job. 3. Confirm candidate scores, winner, and scrubbed failures render.",
        "P4",
        "`RenderLedgerPanel` lists ledger jobs and renders each job's timeline, per-candidate scores (winner highlighted), sanitized failure tail, and fallback reason; it shows an empty state and never crashes on a missing/corrupt ledger. SettingsDialog exposes it via a 'View render ledger' button. Implementation reference: aetherlab/ui/ledger_panel.py:1 / aetherlab/ui/main_window.py:220.",
        "A missing ledger shows an empty state, not an error; only already-scrubbed data is displayed; the panel constructs offscreen without a media backend.",
        "scripted-ui",
    ),
    "F177": _story_tuple(
        "US-F177: As P3 Educator with a vision critic, when I run a solve, I expect the quality tournament to run automatically with no extra clicks; and as P1 Student with no key, I expect exactly one render, exactly as fast. Preconditions: a vision model may or may not be configured. Steps: 1. Resolve the effective cap with/without a critic. 2. Confirm the tournament is on for a critic and off keyless. 3. Toggle it off and confirm single-shot.",
        "P3",
        "`auto_tournament` (default True) + `effective_candidate_cap()` make the tournament default-on for a configured vision critic (cap = AUTO_TOURNAMENT_CAP) while keyless/offline resolves to 1; `scene_tournament_enabled()` gates on a critic AND cap>1; a Settings toggle and env override opt out; explicit scene_candidates>1 still wins. Implementation reference: aetherlab/core/settings.py:60 / aetherlab/services/manim_runtime.py:80 / aetherlab/ui/main_window.py:255.",
        "No vision critic -> single render, never slower; the toggle and env override cleanly disable auto-on; Phase-4 escalation bounds the configured cost.",
        "harness",
    ),
    "F178": _story_tuple(
        "US-F178: As P4 Power user, cloud rendering, when I render a lesson locally with the tournament on, I expect a global cap on simultaneous local renders so my machine does not thrash. Preconditions: multiple renders may be dispatched concurrently. Steps: 1. Dispatch more concurrent local renders than the limit. 2. Confirm no more than the limit run at once. 3. Confirm cloud renders are not bounded by it.",
        "P4",
        "`LOCAL_RENDER_LIMIT` + a threading semaphore acquired inside `LocalRenderBackend.render`'s worker thread cap concurrent local Manim subprocesses globally across lesson-chapter and tournament-candidate nesting; the bound is loop-agnostic and env-overridable, and cloud renders are excluded. Implementation reference: aetherlab/services/render_backend.py:188.",
        "The bound holds across separate event loops; exceeding the limit is impossible; cloud fan-out stays wide (I/O-bound); an env override adjusts it.",
        "harness",
    ),
    "F179": _story_tuple(
        "US-F179: As P3 Educator with a critic, when I ask about a problem similar to one AetherLab rendered well before, I expect that proven scene to guide this generation even if I phrased it differently. Preconditions: the F173 winner store may hold past winners. Steps: 1. Record a winning scene with its problem text. 2. Retrieve it with a semantically-similar (differently-worded) query. 3. Confirm an unrelated query retrieves nothing and no embedder degrades cleanly.",
        "P3",
        "`services/embeddings` (offline all-MiniLM via Chroma, fail-soft) embeds text to unit vectors; `ExemplarCandidateStore.record` stores the winner's embedding and `retrieve()` returns the cosine-nearest winner above RETRIEVE_MIN_SIM; `exemplar_block(data_dir=)` injects it as a second few-shot example. Implementation reference: aetherlab/services/embeddings.py:1 / aetherlab/services/scene_exemplars.py:246.",
        "No embedder / empty store / unrelated query all yield no retrieval and leave generation exactly as before; the deterministic keyless template path never changes; no new hard dependency is added.",
        "harness",
    ),
    "F180": _story_tuple(
        "US-F180: As P3 Educator with a vision critic, when I want to know whether the quality tournament earns its render cost, I expect one command that renders the golden set with the tournament on and off and reports the score lift and the extra renders. Preconditions: a vision critic may be configured (keyless the two arms are identical by design). Steps: 1. Pair two lab reports by prompt id. 2. Confirm the per-prompt deltas, mean lift, win/tie/loss, and extra-render cost. 3. Confirm the verdict is honest across the lift / no-difference / regression regimes.",
        "P3",
        "`prompt_quality_lab --ab` runs the golden set twice (tournament ON vs OFF) in isolated per-arm data dirs so learned state cannot leak between arms; `pair_ab_reports()` is a pure function returning per-prompt deltas, mean lift, win/tie/loss (0.05 noise band), and the ON-arm extra-render cost; `_ab_verdict()` states an honest conclusion and notes keyless arms are identical by construction. Implementation reference: tools/prompt_quality_lab.py:1.",
        "Keyless the two arms are identical (single-shot never enters the tournament) and the verdict says so; only the prompt ids present in both arms are compared; secrets are never persisted; a real lift number needs --allow-provider (Phase D).",
        "harness",
    ),
    "F181": _story_tuple(
        "US-F181: As P3 Educator with a critic, when the tournament has been running, I expect to mine its render ledger to learn whether the fan-out is worth its cost and whether the cheap draft score predicts the shipped HQ quality. Preconditions: a render ledger may hold past tournament jobs. Steps: 1. Aggregate synthetic jobs into escalation rate, winner margin, and the draft-to-HQ correlation. 2. Confirm a missing ledger yields an empty report, not a crash. 3. Confirm a real escalating tournament records difficulty/budget and the winner's HQ score.",
        "P3",
        "`services/render_ledger` gains difficulty/budget/winner_hq_score/winner_hq_verdict; `manim_runtime._record_tournament_hq` logs the winner's final HQ score against the same job as its draft scores; `tools/ledger_report.summarize_ledger()` (pure, stdlib-only, fail-soft) reports escalation rate, winner margin over the runner-up, the draft-to-HQ Pearson correlation and bias, spend by difficulty, the weakest axis, and fallback/failure rates. Implementation reference: tools/ledger_report.py:1 / aetherlab/services/render_ledger.py:1 / aetherlab/services/manim_runtime.py:1.",
        "A missing or corrupt ledger yields an empty report and never raises; keyless renders record no draft-to-HQ pairs and the report says so; the observability is read-only and never blocks a render.",
        "harness",
    ),
    "F182": _story_tuple(
        "US-F182: As P1 Student with no key, when a reviewed model trained on real tournament outcomes is present, I expect my keyless scene ranking to use those learned axis weights; and when none is present, I expect exactly the old behaviour. Preconditions: a trained model file may or may not exist. Steps: 1. Confirm no model leaves the score equal to the equal-weight sum. 2. Confirm the trainer recovers known weights from ledger data. 3. Confirm a present model changes the score and nothing leaks globally.",
        "P1",
        "`tools/train_quality_proxy` mines the ledger's (winner draft axis breakdown -> winner HQ score) pairs and ridge-fits per-axis weights to a reviewable JSON model; `scene_critic._load_quality_proxy()`/`_proxy_score()` apply it when present, else the historical equal-weight sum, so the keyless --gate baseline is unchanged until a reviewed model ships. Implementation reference: aetherlab/services/scene_critic.py:1 / tools/train_quality_proxy.py:1.",
        "No model file -> the keyless score is byte-identical to the equal-weight sum (the --gate floor cannot move); the model is data committed only after human review; the trainer refuses to write from too few samples and never edits source.",
        "harness",
    ),
}


# Phase-2/Phase-4 audit results, applied on top of the story tuples above so a
# whole subsystem can be stamped in one place without editing each _story_tuple.
# Value = (phase2_result, errors_found, phase4_result). Semantics:
#   PASS   — the story was executed/hand-audited and behaves as specified.
#   FAIL   — a defect was found while testing this story in Phase 2 (now fixed,
#            documented in ERRORS_FOUND.md + DEFECTS; Phase-4 re-verifies PASS).
#   BLOCKED— cannot be executed headlessly (needs a real GUI session or live
#            GitHub render credentials); never stamped PASS without evidence.
# "Errors found" lists the associated BUG ids (historical or Phase-2), or None.
PHASE_RESULTS: dict[str, tuple[str, str, str]] = {
    # ── Batch 1: Launch / Settings / Input / Pipeline core (F01-F21) ────────
    # Audited by reading __main__.py, ui/app.py, core/settings.py end-to-end and
    # confirming each t_fNN asserts observable behaviour (real smoke subprocess,
    # settings precedence round-trips, command-bar/stepper widget interaction,
    # a real pipeline run). BUG-4/BUG-5 fixes re-verified in source.
    "F01": ("PASS", "BUG-113", "PASS"),
    "F02": ("PASS", "None", "PASS"),
    "F03": ("PASS", "None", "PASS"),
    "F04": ("PASS", "None", "PASS"),
    "F05": ("PASS", "None", "PASS"),
    "F06": ("PASS", "BUG-5; BUG-34", "PASS"),
    "F07": ("PASS", "BUG-44; BUG-45", "PASS"),
    "F08": ("PASS", "None", "PASS"),
    "F09": ("PASS", "BUG-24", "PASS"),
    "F10": ("PASS", "BUG-4; BUG-42", "PASS"),
    "F11": ("PASS", "None", "PASS"),
    "F12": ("PASS", "None", "PASS"),
    "F13": ("PASS", "None", "PASS"),
    "F14": ("PASS", "None", "PASS"),
    "F15": ("PASS", "BUG-11", "PASS"),
    "F16": ("PASS", "None", "PASS"),
    "F17": ("PASS", "BUG-1", "PASS"),
    "F18": ("PASS", "BUG-49; BUG-56; BUG-114", "PASS"),
    "F19": ("PASS", "None", "PASS"),
    "F20": ("PASS", "None", "PASS"),
    "F21": ("PASS", "BUG-48; BUG-54", "PASS"),
    # ── Batch 2: Solver / Plot / Cache / RAG / Ingestion / Library / Scene ──
    # Audited services/plotting.py end-to-end (probed the safe expression
    # compiler: every sandbox-escape/import/attribute/lambda payload blocked,
    # legit math runs) and confirmed the behavioural tests for cache validity
    # (BUG-23/25), RAG score normalization (BUG-3), and stale-chunk purge
    # (BUG-14). Static-source-assertion features stamped from their documented
    # wiring, consistent with the existing suite.
    "F22": ("PASS", "None", "PASS"),
    "F23": ("PASS", "None", "PASS"),
    "F24": ("PASS", "None", "PASS"),
    "F25": ("PASS", "None", "PASS"),
    "F26": ("PASS", "None", "PASS"),
    "F27": ("PASS", "None", "PASS"),
    "F28": ("PASS", "None", "PASS"),
    "F29": ("PASS", "None", "PASS"),
    "F30": ("PASS", "None", "PASS"),
    "F31": ("PASS", "BUG-50; BUG-51", "PASS"),
    "F32": ("PASS", "None", "PASS"),
    "F33": ("PASS", "BUG-21; BUG-45", "PASS"),
    "F34": ("PASS", "BUG-23; BUG-25", "PASS"),
    "F35": ("PASS", "None", "PASS"),
    "F36": ("PASS", "BUG-3", "PASS"),
    "F37": ("PASS", "None", "PASS"),
    "F38": ("PASS", "BUG-3", "PASS"),
    "F39": ("PASS", "None", "PASS"),
    "F40": ("PASS", "None", "PASS"),
    "F41": ("PASS", "None", "PASS"),
    "F42": ("PASS", "None", "PASS"),
    "F43": ("PASS", "BUG-14", "PASS"),
    "F44": ("PASS", "None", "PASS"),
    "F45": ("PASS", "None", "PASS"),
    "F46": ("PASS", "BUG-54", "PASS"),
    "F47": ("PASS", "BUG-54", "PASS"),
    "F48": ("PASS", "None", "PASS"),
    "F49": ("PASS", "None", "PASS"),
    "F50": ("PASS", "None", "PASS"),
    # ── Batch 3: Scene fallback / Render / SceneUI / Canvas / Params /
    #    Analysis / Navigation / History / Errors / Export / UX (F51-F90) ────
    # Confirmed behavioural widget/interaction tests (stack indices, negative
    # spinbox reset, slider<->spinbox sync, toast/error-banner state, history
    # count round-trips) and the render-wiring/source-assertion tests. F54 is
    # `manual` (render visual quality is judged by the visual-regression harness
    # + human review), so it stays PARTIAL: command wiring confirmed here, full
    # visual verification is out-of-band.
    "F51": ("PASS", "None", "PASS"),
    "F52": ("PASS", "None", "PASS"),
    "F53": ("PASS", "None", "PASS"),
    "F54": ("PARTIAL", "BUG-115", "PASS"),
    "F55": ("PASS", "None", "PASS"),
    "F56": ("PASS", "BUG-55", "PASS"),
    "F57": ("PASS", "BUG-21", "PASS"),
    "F58": ("PASS", "None", "PASS"),
    "F59": ("PASS", "None", "PASS"),
    "F60": ("PASS", "None", "PASS"),
    "F61": ("PASS", "None", "PASS"),
    "F62": ("PASS", "None", "PASS"),
    "F63": ("PASS", "None", "PASS"),
    "F64": ("PASS", "None", "PASS"),
    "F65": ("PASS", "None", "PASS"),
    "F66": ("PASS", "None", "PASS"),
    "F67": ("PASS", "None", "PASS"),
    "F68": ("PASS", "None", "PASS"),
    "F69": ("PASS", "None", "PASS"),
    "F70": ("PASS", "BUG-2", "PASS"),
    "F71": ("PASS", "None", "PASS"),
    "F72": ("PASS", "None", "PASS"),
    "F73": ("PASS", "None", "PASS"),
    "F74": ("PASS", "None", "PASS"),
    "F75": ("PASS", "None", "PASS"),
    "F76": ("PASS", "None", "PASS"),
    "F77": ("PASS", "None", "PASS"),
    "F78": ("PASS", "None", "PASS"),
    "F79": ("PASS", "BUG-52", "PASS"),
    "F80": ("PASS", "None", "PASS"),
    "F81": ("PASS", "None", "PASS"),
    "F82": ("PASS", "None", "PASS"),
    "F83": ("PASS", "None", "PASS"),
    "F84": ("PASS", "None", "PASS"),
    "F85": ("PASS", "None", "PASS"),
    "F86": ("PASS", "BUG-10; BUG-57", "PASS"),
    "F87": ("PASS", "None", "PASS"),
    "F88": ("PASS", "BUG-57", "PASS"),
    "F89": ("PASS", "BUG-57", "PASS"),
    "F90": ("PASS", "None", "PASS"),
    # ── Batch 4: UX / Edge cases / Render+Scene internals / Canvas v2 /
    #    Design v2 / References / Providers / Math (F91-F130) ────────────────
    # Substantive multi-assert behavioural tests throughout: defensive JSON
    # (F97), numeric guards (F98), StateBus (F99), scene-name sanitization
    # (F100), self-heal/repair wiring (F101), truncation guard (F102), critique
    # loop (F108), canvas trail/hover/sample-cache (F110/111/113), multi-curve
    # payloads (F114), provider gating (F128). F103 stays FAIL/BUG-28 (stamped
    # inline). F92 (title bar) is construction-only but low-risk cosmetic.
    "F91": ("PASS", "BUG-22", "PASS"),
    "F92": ("PASS", "None", "PASS"),
    "F93": ("PASS", "None", "PASS"),
    "F94": ("PASS", "None", "PASS"),
    "F95": ("PASS", "None", "PASS"),
    "F96": ("PASS", "None", "PASS"),
    "F97": ("PASS", "None", "PASS"),
    "F98": ("PASS", "None", "PASS"),
    "F99": ("PASS", "None", "PASS"),
    "F100": ("PASS", "None", "PASS"),
    "F101": ("PASS", "None", "PASS"),
    "F102": ("PASS", "None", "PASS"),
    "F104": ("PASS", "None", "PASS"),
    "F105": ("PASS", "None", "PASS"),
    "F106": ("PASS", "BUG-40; BUG-41; BUG-65; BUG-66; BUG-101", "PASS"),
    "F107": ("PASS", "BUG-43", "PASS"),
    "F108": ("PASS", "BUG-35; BUG-38", "PASS"),
    "F109": ("PASS", "None", "PASS"),
    "F110": ("PASS", "None", "PASS"),
    "F111": ("PASS", "None", "PASS"),
    "F112": ("PASS", "None", "PASS"),
    "F113": ("FAIL", "BUG-118", "PASS"),
    "F114": ("PASS", "None", "PASS"),
    "F115": ("PASS", "None", "PASS"),
    "F116": ("PASS", "None", "PASS"),
    "F117": ("PASS", "None", "PASS"),
    "F118": ("PASS", "None", "PASS"),
    "F119": ("PASS", "None", "PASS"),
    "F120": ("PASS", "None", "PASS"),
    "F121": ("PASS", "None", "PASS"),
    "F122": ("PASS", "None", "PASS"),
    "F123": ("PASS", "None", "PASS"),
    "F124": ("PASS", "None", "PASS"),
    "F125": ("PASS", "BUG-47", "PASS"),
    "F126": ("PASS", "None", "PASS"),
    "F127": ("PASS", "None", "PASS"),
    "F128": ("PASS", "None", "PASS"),
    "F129": ("PASS", "BUG-53", "PASS"),
    "F130": ("PASS", "None", "PASS"),
    # ── Batch 5: Product / Render / Narration / Lesson / Security / Cloud /
    #    Docs / Quality (F131-F168) ──────────────────────────────────────────
    # Substantive tests throughout (voiceover rate parsing, SRT timing, lesson
    # planner curriculum, fact-check in-place, quality-score cache, candidate
    # tournament, exemplars, secret-guard scan). The three live-cloud stories
    # (F153/F154/F155) are stub-verified here and were live-smoked historically
    # (see baseline) but not re-run this session -> PARTIAL, never faked PASS.
    # F148/F166/F167 already stamped inline. DEFECTS-linked bugs noted.
    "F131": ("PASS", "None", "PASS"),
    "F132": ("PASS", "None", "PASS"),
    "F133": ("PASS", "BUG-33; BUG-39; BUG-55; BUG-104", "PASS"),
    "F134": ("PASS", "None", "PASS"),
    "F135": ("PASS", "None", "PASS"),
    "F136": ("PASS", "None", "PASS"),
    "F137": ("PASS", "None", "PASS"),
    "F138": ("PASS", "None", "PASS"),
    "F139": ("PASS", "None", "PASS"),
    "F140": ("PASS", "None", "PASS"),
    "F141": ("PASS", "None", "PASS"),
    "F142": ("PASS", "None", "PASS"),
    "F143": ("PASS", "BUG-9; BUG-23; BUG-44; BUG-45", "PASS"),
    "F144": ("PASS", "None", "PASS"),
    "F145": ("PASS", "BUG-8; BUG-9", "PASS"),
    "F146": ("PASS", "None", "PASS"),
    "F147": ("PASS", "BUG-120", "PASS"),
    "F149": ("PASS", "None", "PASS"),
    "F150": ("PASS", "BUG-56", "PASS"),
    "F151": ("PASS", "None", "PASS"),
    "F152": ("PASS", "None", "PASS"),
    "F153": ("PARTIAL", "BUG-19", "PASS"),
    "F154": ("PARTIAL", "BUG-15; BUG-17; BUG-18; BUG-20; BUG-44; BUG-45", "PASS"),
    "F155": ("PASS", "BUG-37", "PASS"),
    "F156": ("PASS", "None", "PASS"),
    "F157": ("PASS", "BUG-53; BUG-58", "PASS"),
      "F158": ("PASS", "BUG-116", "PASS"),
    "F159": ("PASS", "None", "PASS"),
    "F160": ("PASS", "BUG-16", "PASS"),
    "F161": ("PASS", "BUG-29; BUG-30; BUG-46; BUG-117", "PASS"),
    "F162": ("PASS", "None", "PASS"),
    "F163": ("PASS", "None", "PASS"),
    "F164": ("FAIL", "BUG-110", "PASS"),
    "F165": ("PASS", "None", "PASS"),
    "F168": ("PASS", "None", "PASS"),
    # ── Quality Flywheel Phase 0 (F169) ─────────────────────────────────────
    # New feature built + tested this pass: golden-set + gate ratchet. The gate
    # logic is unit-tested deterministically (synthetic + committed baseline);
    # the committed baseline was generated from a real keyless 12-prompt run.
    "F169": ("PASS", "None", "PASS"),
    # ── Quality Flywheel Phase 1 (F170) ─────────────────────────────────────
    # Per-axis rubric + backward-compatible persistence + static no-vision
    # proxy, all deterministically unit-tested (coerce/approx/static/round-trip)
    # without a live vision model or a render.
    "F170": ("PASS", "None", "PASS"),
    # ── Quality Flywheel Phase 2 (F171) ─────────────────────────────────────
    # Distinct candidate ids plus serialized branch commits are exercised
    # deterministically; the manual real-GitHub smoke remains available.
    "F171": ("PASS", "BUG-36", "PASS"),
    # ── Quality Flywheel Phase 3 (F172 losers teach, F173 winners teach) ────
    "F172": ("PASS", "BUG-44", "PASS"),
    "F173": ("PASS", "BUG-31; BUG-44; BUG-45", "PASS"),
    # ── Quality Flywheel Phase 4 (F174 cheap-first escalation) ──────────────
    "F174": ("PASS", "None", "PASS"),
    # ── Quality Flywheel Phase 5 (F175 ledger, F176 dashboard panel) ────────
    "F175": ("PASS", "BUG-44; BUG-45", "PASS"),
    "F176": ("PASS", "BUG-45", "PASS"),
    # ── Quality Flywheel Phase 6 — final: default-on for configured critics ─
    "F177": ("PASS", "None", "PASS"),
    # ── Flywheel efficiency pass (F178 global local-render bound) ───────────
    "F178": ("PASS", "None", "PASS"),
    # ── ML §1: embeddings — semantic exemplar retrieval (F179) ──────────────
    "F179": ("PASS", "None", "PASS"),
    # ── "Prove It" mission — measure the flywheel (F180 A/B, F181 ledger report,
    #    F182 learned keyless proxy) ──────────────────────────────────────────
    "F180": ("PASS", "BUG-32, BUG-109", "PASS"),
    "F181": ("PASS", "None", "PASS"),
    "F182": ("PASS", "None", "PASS"),
    # ── Planner-first / numeric-grounded / self-verifying redesign (F183–F199) ─
    #    Full /goal 4-phase loop run 2026-07-24: hand-audited every story path
    #    against source, then a deterministic 199/199 harness run confirmed each.
    #    No app-code defects surfaced this pass — the implementation was already
    #    correct; the only fix was tracker tooling (generated stories now honour
    #    PHASE_RESULTS). See ERRORS_FOUND.md "F183–F199 audit".
    "F183": ("PASS", "None", "PASS"),  # prompt→modality routing
    "F184": ("PASS", "None", "PASS"),  # conditional pipeline skips unplanned stages
    "F185": ("PASS", "None", "PASS"),  # deterministic offline planner fallback
    "F186": ("PASS", "None", "PASS"),  # view pills gated by plan
    "F187": ("PASS", "None", "PASS"),  # ODE ground truth vs closed-form (<1e-3)
    "F188": ("PASS", "None", "PASS"),  # canvas driven by numeric trajectory
    "F189": ("PASS", "None", "PASS"),  # formal cited research PDF
    "F190": ("PASS", "None", "PASS"),  # pdflatex-free matplotlib PDF fallback
    "F191": ("PASS", "None", "PASS"),  # numeric-driven trajectory component
    "F192": ("PASS", "None", "PASS"),  # 3-D surface component
    "F193": ("PASS", "None", "PASS"),  # curated composition preferred over LLM
    "F194": ("PASS", "None", "PASS"),  # physics self-verification (passes correct)
    "F195": ("PASS", "None", "PASS"),  # catches unphysical results
    "F196": ("PASS", "None", "PASS"),  # solver never silently downgrades
    "F197": ("PASS", "None", "PASS"),  # planner floor — never under-planned
    "F198": ("PASS", "None", "PASS"),  # honest offline verification scope
    "F199": ("PASS", "None", "PASS"),  # text-mode math auto-repair (render-killer)
    # ── Physics-coverage expansion (2026-07-24) — new curated components,
    #    inspired by manim-physics / 3b1b / PhET; render-verified to MP4. ──────
    "F200": ("PASS", "None", "PASS"),  # nonlinear pendulum component
    "F201": ("PASS", "None", "PASS"),  # phase-portrait component
    "F202": ("PASS", "None", "PASS"),  # electric field-line component
    "F203": ("PASS", "None", "PASS"),  # Fourier-epicycle component
    "F204": ("PASS", "None", "PASS"),  # quantum-wavepacket component
    "F205": ("PASS", "None", "PASS"),  # double-slit interference component
    "F206": ("PASS", "None", "PASS"),  # kinetic-theory (ideal-gas) component
    "F207": ("PASS", "None", "PASS"),  # chaotic double-pendulum component
    "F208": ("PASS", "None", "PASS"),  # thin-lens ray-diagram component
    "F209": ("PASS", "None", "PASS"),  # standing-wave (normal-mode) component
    "F210": ("PASS", "None", "PASS"),  # Kepler-orbit component (equal-area law)
    "F211": ("PASS", "None", "PASS"),  # surface3d renders the real field
    "F212": ("PASS", "None", "PASS"),  # components track solver parameters
    "F213": ("PASS", "None", "PASS"),  # coupled-oscillators component
    "F214": ("PASS", "None", "PASS"),  # concave-mirror ray-diagram component
    # The gate itself: found failing (the harness always exited 0), fixed, re-verified.
    "F215": ("FAIL", "BUG-60, BUG-61, BUG-62", "PASS"),
    # Human review (8/10, "missing more details and explanation") drove this one.
    "F216": ("PASS", "None", "PASS"),  # v2 9/10; uniform v3 scaffold rated lower, now opt-in
    "F217": ("PASS", "None", "PASS"),  # per-topic creative scenarios (v4)
    "F218": ("PASS", "None", "PASS"),  # problem-solving videos (v5)
    "F219": ("PASS", "None", "PASS"),  # backup provider (K3 turned off; feature kept)
    "F220": ("PASS", "None", "PASS"),  # study guide / worked-solution PDFs
    "F221": ("PASS", "None", "PASS"),  # harder problem videos (v6)
    "F222": ("PASS", "BUG-96", "PASS"),  # exclusive Manim partial-render upper bound
    "F223": ("PASS", "None", "PASS"),  # study-document numeric-claim review
    "F224": ("PASS", "BUG-108", "PASS"),  # fade-aware visual quality and comparable duration ratios
    # ── ЕНТ student-path audit and locale regressions (2026-10-09) ──────────
    "F225": ("PASS", "None", "PASS"),  # fixed-key bank and partial scoring
    "F226": ("PASS", "None", "PASS"),  # localized practice UI and timer
    "F227": ("FAIL", "BUG-112", "PASS"),  # local goals, countdown, progress and mistakes
    "F228": ("PASS", "None", "PASS"),  # localized searchable practice PDF
    "F229": ("PASS", "None", "PASS"),  # cited, fixed accelerated-motion lesson
    "F230": ("PASS", "None", "PASS"),  # localized student dashboard
    "F231": ("FAIL", "BUG-111", "PASS"),  # source browser follows the selected locale
}


# Follow-up regressions discovered after the first feature sweep. The detailed
# symptoms and fixes live in ERRORS_FOUND.md; this map keeps each logged issue
# attached to the canonical user story that exercises its behavior.
ERROR_FEATURE_LINKS: dict[str, tuple[str, str]] = {
    "BUG-173": ("F233", "mock solutions were empty and completed practice/mock review omitted typeset math; all 40 mock items now have shared equations rendered in review and PDF with per-attempt image resources"),
    "BUG-174": ("F226", "Qt stock Yes/No labels remained English in Kazakh/Russian exam prompts; explicit localized Resume, Start again, Cancel, Finish and Continue labels retain safe defaults"),
    "BUG-175": ("F238", "closing or escaping Resume could act as No and discard saved answers; Cancel now preserves exact saved bytes, and incompatible-bank resume diagnoses rather than replacing the attempt"),
    "BUG-171": ("F226", "timed setup hid only the session-size combo, leaving an orphan label; the entire field now hides and practice selection survives mode/language changes"),
    "BUG-172": ("F230", "pending mock question IDs were ignored by the home recommendation's exercise-only lookup; both banks now supply topic membership, with cleared/unrelated-topic behaviour preserved"),
    "BUG-170": ("F230", "home still asked for mistake review after the queue was cleared; the selected topic's pending IDs now determine review versus new practice while historical accuracy is retained"),
    "BUG-169": ("F228", "native Windows PDF export initialized the system printer and waited for a connection; a PDF-only QPdfWriter now writes the validated atomic stage without discovering printers"),
    "BUG-166": ("F233", "native feedback and result prose exposed raw LaTeX commands; a strict supported-subset formatter preserves grouping and canonical data while retaining typeset solutions"),
    "BUG-167": ("F230", "perfect small samples claimed mistakes and a weak topic; localized success messages now state the sample and invite further practice without asserting mastery"),
    "BUG-168": ("F233", "the study key inherited the code editor's small Cascadia Code font; a scoped PracticeReview style uses the application font at 14px without changing code editors"),
    "BUG-158": ("F228", "early-finish PDF used all selected questions for its denominator/count; shared scoring now matches screen and saved history while keeping the complete study key"),
    "BUG-159": ("F227", "nonfinite numeric fields and malformed aggregate scores crashed progress readers/views; normalized records, safe recovery, preserved file bytes and a visible recovered-values notice"),
    "BUG-160": ("F233", "unattempted practice questions displayed a zero-point penalty although excluded from totals; review now explicitly labels them as not counted"),
    "BUG-161": ("F228", "PDF solutions printed raw LaTeX instead of the shared worked formulas; report-scoped image resources render equations and failures preserve an existing report"),
    "BUG-162": ("F228", "PDF source links orphaned onto a nearly empty page and added formula blocks split worked questions; explicit source and formula-question pagination keeps blocks together"),
    "BUG-163": ("F228", "a process-wide font flag outlived Qt's font database, producing unreadable and unsearchable PDF glyphs after application recreation; bundled fonts now register once per application instance and preserve later font choices"),
    "BUG-164": ("F228", "PDF printing could claim an unchanged old report as new success or corrupt it during a partial write; a fresh sibling stage is parsed and checked for readable report text before atomic replacement, and failures preserve the original"),
    "BUG-165": ("F136", "a real worker's missing-MP4 failure was classified as ffmpeg from dependency noise, while cleanup could hide the error; exact output diagnostics now take priority and missing/ambiguous/invalid artifact kinds stay distinct"),
    "BUG-154": ("F227", "read-only progress errors appeared empty/zero to every consumer; strict readers and a single normalized snapshot now preserve uncertainty"),
    "BUG-155": ("F230", "dashboard/progress/topic screens reset known results or claimed empty data on denied reads; scoped snapshots, unknown/stale states and translated retry"),
    "BUG-156": ("F227", "unreadable setup treated saved goals/mistakes as absent; unknown controls are disabled and retry restores goals without overwriting a loaded draft"),
    "BUG-157": ("F242", "local progress read failure was diagnosed as network failure during sync; trusted local error key, no request and retained ranking"),
    "BUG-149": ("F227", "progress mutations reset an unreadable existing file; strict update reads now preserve bytes and propagate IO failure"),
    "BUG-150": ("F227", "goal/result persistence errors escaped and completion was set before commit; localized draft retention and frozen result retry"),
    "BUG-151": ("F238", "autosave errors escaped and closing omitted the current answer; visible errors and close-time save retry prevent silent loss"),
    "BUG-152": ("F238", "unreadable resume looked absent and stale active snapshots could duplicate history; resume error boundary, pending state and stable attempt identity"),
    "BUG-153": ("F244", "failed companion update replaced stored progress and confirmed choice; preserved choice and localized retry diagnosis"),
    "BUG-145": ("F241", "clearing the endpoint labelled retained remote rows as local; local mode now loads local rows or reports read failure"),
    "BUG-146": ("F242", "environment endpoint override was inconsistent across getter/save/sync; effective URL, explicit diagnosis and preserved preference are now consistent"),
    "BUG-147": ("F236", "unreadable AI allowance was treated as zero usage and could be overwritten; IO errors preserve the counter"),
    "BUG-148": ("F236", "allowance IO failures escaped or showed a false valid limit; unknown badge blocks only AI and restores confirmed usage on refresh"),
    "BUG-144": ("F241", "empty history placeholder spanned both columns and hid a later student's score; selection switches now clear old spans"),
    "BUG-141": ("F240", "teacher review read errors escaped; localized reload retains snapshots, distinguishes unreadable data and clears old spans on recovery"),
    "BUG-142": ("F242", "endpoint save/sync storage errors escaped Qt slots; localized file-storage errors retain the draft and prevent worker launch"),
    "BUG-143": ("F241", "local-ranking read errors escaped or were masked by a local-only notice; retained snapshots and local-file errors avoid false success"),
    "BUG-139": ("F234", "an unreadable registry was treated as empty and could be overwritten; read failures now preserve registry bytes and propagate"),
    "BUG-140": ("F235", "profile reload/selection/discard errors escaped or cleared choices; localized Retry and saved-but-not-reloaded messages retain state"),
    "BUG-135": ("F235", "rejected profile changes overwrote saved photos; immutable copied avatars, rollback and localized photo errors"),
    "BUG-136": ("F234", "new profile creation/activation/avatar used multiple registry commits; complete make_active creation now commits once"),
    "BUG-137": ("F235", "40-character first and surname produced an 81-character name rejected/discarded by persistence; boundary/reload regression"),
    "BUG-138": ("F234", "profile activation let persistence exceptions escape Qt; dialog now retains current profile and reports failure"),
    "BUG-134": ("F234", "Windows profile atomic replacement failed on temporary locks; bounded retries preserve old data on persistent failures"),
    "BUG-132": ("F249", "cloud media passed without PyAV or a decodable frame; decoder-load and metadata-only regressions"),
    "BUG-133": ("F158", "cloud worker substituted unrelated/partial MP4 or chose an ambiguous output; executable exact-scene selection scenarios"),
    "BUG-131": ("F239", "camera downtime was counted toward missing/multiple-face intervals; continuous-observation regression in t_f239"),
    "BUG-130": ("F165", "structural tracker verification rejected a consistent REGRESSED row from the prior run, preventing the audit test from recovering; CLI still rejects failed runs"),
    "BUG-124": ("F164", "new student workflows were omitted from the catalog; 250 stories now cover all detected surfaces"),
    "BUG-125": ("F215", "a recorded fix without a passing supplied result was falsely stamped FIXED; missing-evidence regression in t_f215"),
    "BUG-126": ("F02", "offline feature probes inherited real references and web retrieval; test environment now isolates both"),
    "BUG-127": ("F232", "hydrostatic pressure variants returned a factor-of-ten wrong answer; three-locale independent pressure regression"),
    "BUG-128": ("F249", "MP4 header validation loaded the full video into memory; sparse-file memory regression"),
    "BUG-129": ("F154", "cloud-poll retry fixture used invalid video bytes; regression now uses a real 854x480 MP4"),
    "BUG-6": ("F47", "cancelled starter-book downloads continued into indexing; regression in t_f47"),
    "BUG-7": ("F49", "a brittle test assertion had gone stale and produced a false green; regression in t_f49"),
    "BUG-12": ("F165", "legacy pytest collection and assertions; covered by the canonical test-harness audit"),
    "BUG-121": ("F165", "the tracker audit checked links to the log but not every logged issue's link back to a feature; reverse-link regression in t_f165"),
    "BUG-122": ("F108", "a skipped visual critique could leave an unscored revision selected; regression in tests/test_bugcheck_regressions.py"),
    "BUG-123": ("F106", "cloud cost and play budgets are rechecked after render repair and visual revision; regression in tests/test_bugcheck_regressions.py"),
    "BUG-21": ("F33", "stale rendered-scene cache path; regression is included in the strict render-cache checks"),
    "BUG-22": ("F91", "small-width command-bar input; regression in t_f91"),
    "BUG-59": ("F165", "tracker generation ignored phase results for generated stories; regression in t_f165"),
    "BUG-67": ("F142", "act narration was duplicated across beats; regression in tests/test_bugcheck_regressions.py"),
    "BUG-68": ("F33", "cached fallback scene remained stale after provider recovery; regression in tests/test_bugcheck_regressions.py"),
    "BUG-69": ("F194", "symbolic rearrangement by a variable was rejected; regression in tests/test_bugcheck_regressions.py"),
    "BUG-73": ("F142", "timed-cue instructions malformed the narrator prompt; regression in the voiceover regression suite"),
    "BUG-74": ("F107", "MiniMax scene authoring defaulted to thinking-on; regression in tests/test_bugcheck_regressions.py"),
    "BUG-75": ("F106", "advisory scene findings discarded valid AI output; regression in tests/test_bugcheck_regressions.py"),
    "BUG-76": ("F106", "crash-level lint was omitted from repair instructions; regression in tests/test_bugcheck_regressions.py"),
    "BUG-77": ("F106", "advisory findings blocked a repaired render; regression in tests/test_bugcheck_regressions.py"),
    "BUG-78": ("F106", "zero-duration waits reached Manim; regression in tests/test_bugcheck_regressions.py"),
    "BUG-79": ("F136", "dvisvgm diagnostics were classified as a LaTeX failure; regression in tests/test_bugcheck_regressions.py"),
    "BUG-80": ("F108", "MiniMax vision critique spent its response budget reasoning; regression in tests/test_bugcheck_regressions.py"),
    "BUG-81": ("F106", "updater-controlled readout lost its position; regression in tests/test_bugcheck_regressions.py"),
    "BUG-82": ("F106", "beat timing used absolute boundaries instead of beat duration; regression in tests/test_bugcheck_regressions.py"),
    "BUG-83": ("F108", "unscored revisions could replace a better render; regression in tests/test_bugcheck_regressions.py"),
    "BUG-84": ("F22", "empty analytical-solver replies were accepted; covered by solver and fallback checks"),
    "BUG-85": ("F106", "a crash repair was discarded when advisory findings remained; regression in tests/test_bugcheck_regressions.py"),
    "BUG-86": ("F106", "spelled-out diagonal direction constants crashed generated scenes; regression in tests/test_bugcheck_regressions.py"),
    "BUG-87": ("F106", "repaired template output could be mislabeled as AI generated; regression in tests/test_bugcheck_regressions.py"),
    "BUG-88": ("F106", "cloud render budget findings stopped blocking dispatch; regression in tests/test_bugcheck_regressions.py"),
    "BUG-89": ("F219", "provider failover lost the thinking-off request flag; regression in tests/test_bugcheck_regressions.py"),
    "BUG-90": ("F175", "cloud runner telemetry was overwritten by client timing; regression in tests/test_bugcheck_regressions.py"),
    "BUG-91": ("F154", "cloud repair received cleanup noise instead of the traceback; regression in tests/test_bugcheck_regressions.py"),
    "BUG-92": ("F107", "agent-team code omitted the documented eq() helper; regression in tests/test_bugcheck_regressions.py"),
    "BUG-93": ("F157", "Qt signal lambdas crashed after dialog teardown; regression in tests/test_bugcheck_regressions.py"),
    "BUG-94": ("F220", "PDF fallback overwrote the model-unavailable diagnostic; regression in tests/test_bugcheck_regressions.py"),
    "BUG-95": ("F148", "failed crossfade assembly silently shipped a plain concat; regression in tests/test_bugcheck_regressions.py"),
    "BUG-96": ("F222", "partial preview excluded its final sampled event; regression in t_f222"),
    "BUG-97": ("F165", "generated user stories replaced feature-specific expectations; regression in t_f165"),
    "BUG-98": ("F194", "symbolic scale factors were accepted without proving nonzero; regression in tests/test_bugcheck_regressions.py"),
    "BUG-99": ("F141", "a complete authored lesson was discarded when optional scaffolds were absent; regression in the lesson-planner suite"),
    "BUG-100": ("F194", "unchecked derivation records were omitted from aggregate verification; regression in tests/test_upgrade_missions.py"),
}


def _append_bug_ids(errors: str, bug_id: str) -> str:
    ids = re.findall(r"BUG-\d+", errors)
    if bug_id in ids:
        return errors
    return "; ".join([*ids, bug_id]) if ids else bug_id


for _bug_id, (_feature_id, _evidence) in ERROR_FEATURE_LINKS.items():
    _phase2, _errors, _phase4 = PHASE_RESULTS.get(
        _feature_id, ("PASS", "None", "PASS")
    )
    PHASE_RESULTS[_feature_id] = (
        _phase2,
        _append_bug_ids(_errors, _bug_id),
        _phase4,
    )


def _story_fields(row: tuple[str, ...]) -> tuple[str, ...]:
    fid, category, feature, user_story, expected, source, legacy_method, _status, _notes = row[:9]
    if fid in STORY_OVERRIDES:
        base = list(STORY_OVERRIDES[fid])
        base[2] = _attach_implementation_references(
            base[2],
            source,
            f"{feature}\n{user_story}\n{base[0]}\n{base[2]}",
        )
        if fid in PHASE_RESULTS:
            p2, errs, p4 = PHASE_RESULTS[fid]
            return tuple(base[:5] + [p2, errs, p4])
        return tuple(base)
    persona = _persona_for(category, feature, source)
    legacy_story = user_story.strip()
    if not legacy_story.lower().startswith("as "):
        legacy_story = f"As {PERSONA_LABELS[persona]}, {legacy_story}"
    story = (
        f"US-{fid}: {legacy_story} Persona: {persona}. Preconditions: "
        f"{PERSONA_PRECONDITIONS[persona]} Steps: {_story_steps(feature, legacy_method)}"
    )
    expected_behaviour = _attach_implementation_references(
        expected,
        source,
        f"{feature}\n{user_story}\n{expected}",
    )
    failure = _failure_expectation(category, feature, expected)
    story_method = _story_test_method(category, feature, source, legacy_method)
    # Auto-generated stories carry Phase-2/4 stamps too: without this the
    # generated features (e.g. the F183+ planner/numeric/verifier rework) could
    # never leave PENDING no matter what the /goal loop verified.
    p2, errs, p4 = PHASE_RESULTS.get(fid, ("PENDING", "None", "PENDING"))
    return (story, persona, expected_behaviour, failure, story_method, p2, errs, p4)


FEATURES = [
    row if len(row) > len(BASE_HEADERS) else row + _story_fields(row)
    for row in FEATURES
]
FEATURES = [row + ("Not recorded", "Not verified in this audit", "PENDING", "Run the story and retain evidence") for row in FEATURES]


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

    widths = [7, 13, 30, 46, 66, 30, 12, 12, 40, 58, 12, 72, 58, 16, 16, 24, 16, 23, 44, 18, 48]
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
            FEATURES[i] = row[:7] + (status, note) + row[9:]
            return
    raise KeyError(feature_id)


def set_phase4(feature_id: str, result: str) -> None:
    """Override a feature's Phase-4 column (a live failing run beats the stamp)."""
    column = HEADERS.index("Phase-4 result")
    for i, row in enumerate(FEATURES):
        if row[0] == feature_id:
            if len(row) > column:
                FEATURES[i] = row[:column] + (result,) + row[column + 1:]
            return
    raise KeyError(feature_id)


# Logistical/UX defects found by code review in Phase 2 (see ERRORS_FOUND.md),
# fixed in Phase 3. Keyed by the feature they affect.
DEFECTS: dict[str, str] = {
    "F07": "BUG-44: settings.json used a direct unprotected read/merge/write and could lose concurrent saves or be truncated on interruption; it now shares the path transaction and atomic replace. BUG-45: valid JSON arrays/null caused load_app_config().items() to crash startup/save; wrong shapes now recover as empty config. Regressions in t_f07.",
    "F17": "BUG-1: duplicate reset() shadowed the clearing one; stale elapsed leaked across runs.",
    "F70": "BUG-2: update_variable used setRange(0,span)/`value>span`; dropped negative range.",
    "F38": "BUG-3: filesystem RAG score is a raw count, not 0-1; pill/label semantics broke.",
    "F36": "BUG-3: filesystem RAG score normalization (see F38).",
    "F10": "BUG-4: Settings 'Data path' field never persisted. BUG-42: Settings hid active provider/key source, temporarily bypassed env precedence after Save, and could copy the active env secret into settings.json. AppSettings now tracks exact source/shadow warning, a dedicated panel shows provider/model/source without values, the editable field uses only saved config when env is active, timeout/retry controls are visible, and Save reloads canonical precedence. Regression in t_f10.",
    "F06": "BUG-5: llm_context_window setting was defined but unused (dead config). BUG-34: every asynchronous provider client inherited the OpenAI SDK's two automatic retries and most forced the configured timeout up to 300s, turning one slow request into three long waits. All async clients now share a bounded 5–900s timeout and explicit 0–1 retry policy; both controls honor env/app config. Regression in t_f06.",
    "F148": "BUG-119: xfade chain double-subtracted the overlap (cum += durs[k]-d), drifting every later crossfade early and over-clipping produced-lesson segments. BUG-105: a 0.2 s minimum fade exceeded very short chapter clips, and two-decimal FFmpeg arguments drifted from full-precision seek offsets; fades now stay within the shortest segment and filter parameters retain six decimals. Regression in t_f148.",
    "F147": "BUG-120: _chapter_aspect compared chapter .id (LLM plans default to ''), tagging every id-less chapter 'setup'; now compares by object identity.",
    "F143": "BUG-9: partial lesson renders compacted successful scenes, then zipped them against all renderable chapters; surviving clips could receive the wrong narration/title. Pipeline now carries plan indexes with rendered scenes. BUG-23: lesson chapter cache accepted any existing video path, including zero-byte/corrupt MP4s; cached chapter videos now require a playable video. BUG-44: parallel chapter completions could overwrite each other's cache entries; updates now use a shared path transaction and atomic replace. BUG-45: wrong-shape plan/chapter JSON now becomes a cache miss and the next write repairs the store. BUG-103: multilingual narration referenced an out-of-scope `plan` while narrating chapters, so narration-enabled lessons failed instead of using the lesson's selected voice language. `_narrate_chapters` now receives `plan.language`; t_f143 checks localized voice selection.",
    "F145": "BUG-8/BUG-9: chapter-seek offsets use produced-video starts, and partial lessons map chapter offsets by plan index so skipped middle chapters do not mislabel surviving clips.",
    "F86": "BUG-10: compile_latex_to_pdf could return a stale PDF after a failed pdflatex run; it now removes stale output first and requires returncode 0 plus fresh output. BUG-57: PDF compilation blocked the GUI for up to 60 seconds and failure claimed a LaTeX fallback was saved without a user-selected path. It now runs in BackgroundTask, supports process cancellation, copies atomically, and saves the fallback beside the destination with its exact path in status.",
    "F09": "BUG-24: tracker copy described Qwen settings as automatic autoload, but load_settings gates Qwen reuse behind AETHERLAB_QWEN_AUTOLOAD=1; canonical wording now matches the implemented privacy guard.",
    "F15": "BUG-11: pipeline cancellation did not explicitly clear the scene loading stack; it now calls SimulationPanel.hide_loading() during cancel.",
    "F103": "BUG-13: safety gate allowed string-based runtime escape helpers (`getattr(__builtins__, 'open')`, dunder strings); these handles are now blocked. BUG-28: numpy (an allowed import) exposed raw file-I/O sinks (tofile/fromfile/frombuffer/savetxt/loadtxt/genfromtxt/load/save/memmap/DataSource) giving arbitrary host read/write with no banned name/attribute; these attribute sinks are now rejected while legitimate numpy math stays allowed. BUG-107: NumPy ndarray.dump could pickle to an arbitrary host path; block the method and cover it in t_f103.",
    "F43": "BUG-14: incremental Chroma ingestion left stale chunks when a source file shrank or changed shape; changed files now delete old path chunks before upsert.",
    "F153": "BUG-19: legacy manim-bot .env and existing gh auth sessions were ignored; settings now migrate CLOUD_RENDER_* aliases and GitHub CLI tokens without exposing secrets.",
    "F154": "BUG-15: exact job_id polling prevents attaching to unrelated runs. BUG-17: bundled workflow is provisioned before dispatch/test. BUG-18: removed setup-python cache:pip failure. BUG-20: artifact 302 downloads drop the Bearer header on the signed URL. BUG-44: concurrent artifact completions could lose manifest entries or expose partial JSON; manifest writes are now transactional and atomic. BUG-45: a valid non-object manifest no longer raises through get()/put(); it is treated as empty and rebuilt.",
    "F160": "BUG-16: visual critique score/verdict/issues were not persisted, so cached low-quality renders could be pinned; SceneBundle now stores them and min_quality_score can reject low-score cache.",
    "F34": "BUG-23: solve cache accepted any existing video path, including zero-byte/corrupt MP4s; cached rendered scenes now require a playable video. BUG-25: UI worker now uses the same playable-video guard instead of Path.exists().",
    "F161": "BUG-29: the tournament rendered + critiqued each candidate as a draft, then discarded the winner's rendered draft (built `selected` with status='compiled') and handed it to render_scene_with_repair, which rendered the SAME draft again before promoting to HQ — a wasted render on every tournament solve, multiplied per lesson chapter and made default-on by F177. Now `selected` carries the winner's rendered draft (status/video_path) and render_scene_with_repair skips the draft render when the bundle is already rendered, promoting straight to the requested quality. Regression in t_f135. BUG-30: escalation keyed the second candidate batch off scored (rendered) not built (attempted), so a first candidate that built but failed to render could push total candidates to cap+1; now keyed off first_built so attempts never exceed the budget. Regression in t_f174. BUG-46: the F161 N=1 test forgot that F177 auto-enables tournaments for configured critics, made real api.openai.com calls with sk-test, then passed after fail-soft 401 fallback. It now explicitly opts out and installs an unexpected-candidate sentinel. BUG-117: a second F161 branch stubs `_render_once` but `_render_and_score_candidates` directly uses `render_scene_with_repair` for candidates, so the test still called the configured LLM during crash repair. The test now stubs that full renderer too and asserts each candidate took exactly that stubbed path.",
    "F173": "BUG-31: exemplar promotion (and, through it, the F179 retrieval the flywheel serves) keyed off the winner's 480p DRAFT critic score — the score the tournament uses only to SELECT the winner — recorded before the HQ render. So the flywheel learned from and re-served scenes judged at draft quality, not the 1080p the user sees: a scene great at 480p but weak at HQ could be promoted, and one that improved at HQ rejected. Fixed by recording the exemplar AFTER render_scene_with_repair, from the FINAL bundle whose critique loop re-scored the promoted HQ render (and any aesthetic revision). Selection still uses the cheap draft score; promotion/retrieval now use the HQ score. Regression in t_f173. BUG-44: concurrent promotions now merge under the shared atomic JSON transaction instead of dropping winners. BUG-45: scalar rows in a valid JSON list are ignored instead of breaking dedupe/retrieval.",
    "F166": "BUG-26: export_lesson_bundle wrote the zip straight to the target, so a mid-write failure (disk full, missing asset) truncated it and destroyed any prior good bundle, leaving a plausible-but-incomplete zip that still opened. Now builds into a sibling .part file and os.replace()s onto the target only on full success, unlinking staging on failure. BUG-57: packaging a large lesson still ran synchronously on the GUI thread; MainWindow now dispatches it through the shared export BackgroundTask.",
    "F88": "BUG-57: saving a large MP4 used synchronous shutil.copy2 on the GUI thread, could freeze the app, raised SameFileError if the source was selected, and could expose a truncated destination after copy failure. The cancellable atomic copier streams in the background, no-ops same-file saves, and replaces only after fsync. Regression in t_f88.",
    "F89": "BUG-57: GIF export ran ffmpeg synchronously for up to 120 seconds and wrote `-y` directly to the chosen destination, freezing the app and destroying a prior good GIF on timeout/failure. It now runs in BackgroundTask through whole-tree cancellation and writes to a suffix-correct unique staging GIF before atomic replacement. Regression in t_f89.",
    "F167": "BUG-27: _QuestionCard radios were never locked and re-emitted answer_recorded on every toggle, so switching a selection (or clicking each option until '✓ Correct') recorded multiple quiz attempts and inflated the persisted course score. The card now records only the first answer and disables the group afterward. BUG-44: concurrent answer writes could lose attempts and reused one fixed .tmp filename; progress updates now serialize per path and atomically replace from unique staging files. BUG-45: wrong top-level/nested shapes and invalid counters now recover as empty values instead of crashing quiz interaction. BUG-63: the confidence-selector change re-indented answer_recorded.emit into the button-disabling loop, so one answer on a four-choice question was recorded four times (inflated attempts and spaced-review events); the emit is back outside the loop and t_f167 asserts exactly one recorded answer.",
    "F180": "BUG-32: the A/B verdict said 'did NOT help' whenever more prompts regressed than improved (`or losses > wins`), even with a POSITIVE mean lift — a self-contradicting conclusion (`did NOT help (mean +2.00, 1 win / 2 loss)`) for the flywheel's core measurement. Now the negative verdict requires a negative mean (`mean_lift < -eps and losses >= wins`) and sign/count disagreement routes to an explicit 'Mixed result' verdict. BUG-109: a keyed A/B report could present a numeric lift as a quality result even when most solve critiques were static/skipped, tournament candidates were not vision-ranked, prompt IDs differed, cases failed, the ON arm spent no extra render, or a previous run's ledger/cache contaminated a repeat. Each run now gets fresh isolated state; the report exposes real-vision coverage, marks unsupported measurements INVALID, preserves the raw number as exploratory only, and returns exit 2. Regression in t_f180.",
    "F133": "BUG-33: six external-tool subprocesses decoded text with the host locale and could crash on cp1251; they now use UTF-8/errors=replace. BUG-39: the follow-up found packaging/build.py's frozen smoke capture still locale-decoded and print-producing tools could fail when redirected to a legacy stream. The smoke capture is explicit UTF-8, every CLI configures UTF-8 stdio fail-soft, and t_f133 now AST-audits all production/test Python for text subprocess, text-file, and console encoding assumptions. BUG-55: Manim's timeout killed only its direct process, not FFmpeg/LaTeX descendants; the renderer now owns Popen cleanup and terminates the full Windows tree/POSIX process group. BUG-104: the newly added ENT lesson-route builder and verifier printed localized paths/diagnostics without configuring UTF-8 stdio; both command-line entry points now call configure_utf8_stdio() before printing.",
    "F56": "BUG-55: render_scene used subprocess.run(timeout=...), which Python documents as killing and waiting for the immediate child. Manim can spawn FFmpeg and LaTeX descendants, so timeout could return while orphan work kept consuming resources or locking partial media. `run_process_tree()` now retains Popen control, uses the existing POSIX session as a killable process group, invokes Windows taskkill /T, drains pipes, and only then raises TimeoutExpired. t_f56 starts a parent/grandchild pair and proves the grandchild cannot write a delayed marker after timeout.",
    "F108": "BUG-35: vision critique parsed model text with strict json.loads; a raw LaTeX backslash such as \\omega raised Invalid \\escape and skipped critique, while \\theta silently decoded as a tab. Model responses now use a conservative JSON-object extractor and string-only repair shared by all model-JSON paths. BUG-38: aesthetic revisions were discarded immediately on their first static-gate or render failure; revised code now receives one targeted static repair and one traceback-driven render repair, while the prior cut remains the fallback. Regressions in t_f108.",
    "F171": "BUG-36: tournament variants isolated cloud job/artifact names but every candidate still committed through GitHub's shared render branch concurrently; the Contents API documents concurrent mutations as conflicts, observed as HTTP 409. Writes now serialize per repo/branch and retry 409 with bounded backoff for cross-process races. Regression in t_f171.",
    "F155": "BUG-37: an exhausted cloud poll budget returned terminal render-timeout, so ManimRuntime never entered its cloud-unavailable local fallback and each tournament candidate could wait the full 1800s ceiling. Cloud timeouts are now adaptive under the configured ceiling, cancel the remote run best-effort, return cloud-unavailable, and immediately fall back locally with clear diagnostics. Regression in t_f155 (plus timeout-cap coverage in t_f152).",
    "F106": "BUG-40: codegen invented color constants such as GREEN_SCREEN/BROWN; prompt rules now enumerate the supported Manim palette and SceneGenerator token-repairs unknown loaded color-like names to real constants without touching strings/comments/user definitions. BUG-41: codegen could pass syntax/API lint while producing title cards, reveal-only curves, frozen endings, or omitting requested elements. Remote generation/repair/revision now applies an obvious-motion gate, and prompts require per-act motion, non-identical final sampled frames, and a noun-by-noun requested-element audit. Regressions in t_f106. BUG-65: the beat-timing gate counted LaggedStart/AnimationGroup/Succession without an outer run_time as 1 s and hard-rejected correctly scheduled scenes; such beats are now unmeasurable and declined. BUG-66: the approximate estimate_duration() was a hard +/-20% gate in generation, repair and tournament selection; only an exact estimate (DurationEstimate.exact) can now reject a scene. Regressions in tests/test_bugcheck_regressions.py. BUG-101: static constructor validation now follows visible **kwargs forwarding to a strict Manim base and rejects unsupported TracedPath arguments such as time_traced before render. Regression in tests/test_upgrade_missions.py.",
    "F107": "BUG-43: Qwen3.7-plus and related hybrid models enable thinking by default; using one as llm_model for non-streaming full-scene codegen could spend the whole timeout reasoning and silently fall back to templates. SceneGenerator now sends extra_body enable_thinking=false for hybrid Qwen scene/storyboard/repair/revise/narration calls. Thinking-only models remain bounded by the visible timeout and Settings recommends qwen3-coder-plus. Regression in t_f107.",
    "F172": "BUG-44: concurrent critic results could overwrite learned aesthetic counts or leave partial JSON. The store now reloads and increments under a shared path transaction, then atomically replaces the file.",
    "F33": "BUG-45: SessionCache.get trusted every SQLite JSON field. One valid-but-wrong or malformed nested artifact raised during from_json and killed the whole cache lookup, including independently good fields. Each field now decodes independently; damaged fields become misses while valid solver/RAG/scene data survives. Regression in t_f33.",
    "F175": "BUG-44: render ledger, cloud manifest, chapter cache, course progress, error/aesthetic learning, settings, and exemplar queues performed unprotected read-modify-write operations. Parallel candidates/chapters could silently lose successful entries, and direct writes exposed partial JSON. All mutable stores now share path-scoped re-entrant transactions and same-directory atomic replacement; t_f175 synchronizes fresh instances and proves every update survives. BUG-45: wrong top-level/nested ledger shapes are filtered/defaulted and the next mutation repairs the file.",
    "F176": "BUG-45: the render dashboard assumed every persisted candidate/timeline entry and winner index had the expected type; a syntactically valid but malformed ledger could crash Settings construction. Ledger loading now normalizes rows and the panel skips malformed nested entries with safe numeric coercion. BUG-102: cloud lifecycle events omitted completed/rate-limit recovery and token-scope action-required states, links and job metadata were not recorded/displayed, and several ledger text fields/diagnostics were not consistently scrubbed. Cloud events now record the full lifecycle, retry rate limits visibly, mark scope failures action_required, persist only canonical GitHub Actions links, scrub loaded and new text, and display job id/FPS/clickable links. Regression in t_f154, t_f175 and t_f176.",
    "F125": "BUG-47: WikipediaReferenceProvider wrapped only the HTTP/JSON fetch, then trusted query.pages outside the fail-soft guard. MediaWiki error/warning payloads may arrive with HTTP 200, and wrong JSON shapes raised instead of returning local-only references. The provider now validates each container, filters page objects, and safely ranks malformed indexes. Regression in t_f125.",
    "F21": "BUG-48: closeEvent ignored the boolean result of QThread.wait(5000) and always closed. A provider/render operation lasting beyond five seconds therefore left a live subclassed QThread owned by a closing window; Qt documents that deleting a running QThread can crash. Close now defers, listens for finished, and retries safely without terminate(). BUG-54 extends that barrier to live Library index/download threads, which were previously omitted. Regression in t_f21.",
    "F18": "BUG-49: Cancel immediately called set_busy(False), switched away from Running, and announced 'Run cancelled' even though cooperative work could still be inside a provider call/render. The visible Run button then only produced 'already running'. Cancellation now remains busy, disables repeat Cancel, and restores ready state/toast only from QThread.finished. BUG-56: the cancellation flag was checked only between stages; an active Manim subprocess could continue to the 30-minute ceiling. The callback now reaches queue waits, local process-tree execution, cloud polling, and tournaments. BUG-114: the implementation renamed the internal cancellation sentinel to `_PipelineCancelledError`, but the established `_PipelineCancelled` import used by the F18 cancellation contract disappeared; importing it raised ImportError. Added a backwards-compatible alias and verified the cancelled worker path in t_f18. Regression in t_f18.",
    "F54": "BUG-115: Phase-2 marked the local render story PARTIAL because its original check inspected command flags but did not produce an MP4, leaving successful rendering and artifact discovery unverified. The test is now classified as harness and t_f54 executes a real isolated low-quality Manim render and requires a non-empty MP4; strict visual regression also checks the rendered scenes. The original Phase-2 PARTIAL is retained with this verification-gap id, and Phase-4 is PASS.",
    "F31": "BUG-50: SessionCache construction trusted cache.sqlite3 itself. Invalid bytes or SQLite corruption raised DatabaseError before any pipeline fallback. Initialization now quick-checks under a path lock, quarantines only corruption/not-a-database failures (including WAL/SHM), and rebuilds an empty cache; other operational errors are not misclassified. BUG-51: `with sqlite3.Connection` never closes the handle; all cache operations now use a transaction context that commits/rolls back and closes in finally. The Windows quarantine regression proves the handle is released. Regression in t_f31.",
    "F79": "BUG-52: corrupt history.sqlite3 raised during MainWindow construction and could prevent the app from opening. History now closes the failed connection, uses the shared conservative SQLite corruption classifier, preserves DB/WAL/SHM, rebuilds, and remains usable. Regression in t_f79.",
    "F46": "BUG-54: Library indexing used an independently owned QThread that MainWindow shutdown never cancelled or waited for. Closing during a long Chroma/PDF ingest could destroy a running QThread and crash. LibraryPanel now exposes live workers to the application close barrier; cancellation stays visibly pending until the worker confirms and reports saved progress. Regression in t_f21 and t_f46.",
    "F47": "BUG-54: Starter-book downloads were also absent from the close barrier. In addition, Cancel immediately hid progress/re-enabled controls, then the download completion slot could auto-start indexing despite the cancellation. Downloads now join shutdown, remain visibly pending, preserve completed books, and return without launching ingest when interrupted. Regression in t_f21 and t_f47.",
    "F129": "BUG-53: Settings Test connection called the provider synchronously on the GUI thread, so a slow endpoint could freeze painting and input for the full connection timeout. It now runs through a daemon-backed `BackgroundTask`, disables the button while pending, marshals results through Qt signals, and cancels delivery when Settings closes. Regression in t_f129 blocks the mocked provider and proves the action returns immediately.",
    "F157": "BUG-53: Test cloud render performed several network/provisioning requests synchronously, while Get token ran a polling loop with `processEvents()` plus `sleep()` for up to 180 seconds on the GUI thread. Both now use cancellable background tasks; browser launch and widgets stay on the GUI thread, response shapes are validated, and GitHub's documented `slow_down` response increases the poll interval by five seconds. Regression in t_f157 blocks both mocked network entry points and proves the dialog remains responsive. BUG-58: that BackgroundTask emitted `finished` unconditionally — even after the dialog cancelled it on close — so a worker finishing during teardown re-enabled a button on a torn-down widget, and a PyQt slot touching a deleted C++ object aborts the process (a hard, tracebackless crash the CI Windows runner hit in t_f157, not a fast local machine). Fixed: `finished` is no longer emitted after cancel, `BackgroundTask.wait()` joins the worker, and t_f157 joins deterministically instead of racing a 2s deadline.",
    "F150": "BUG-56: LessonPipeline polled cancellation only before each chapter and before assembly, so cancelling during a heavy chapter still waited for its entire local/cloud render timeout (up to 30 minutes). The lesson cancel callback now propagates through tournament candidates, semaphore queues, local Manim process trees, and cloud polling; ProcessCancelledError becomes a skipped in-flight chapter and the normal cancelled partial bundle. BUG-106: narration/assembly did not receive the cancel callback; cancellation now reaches their FFmpeg process trees and returns a cancelled bundle without replacing a prior good file with a partial. Regression in t_f150 covers active render, narration, assembly, and staged-output preservation.",
    "F215": "BUG-60: test_features.py ended main() with an unconditional `return 0`, so the CI step running the harness could never fail on a feature regression; and tracker_integrity_audit certified a tracker regenerated from failing results, so the documented CI order (harness -> rebuild -> audit) absorbed real failures and went fully green. The harness now returns failure_exit_code(results) and the audit refuses to certify any run containing a FAIL. BUG-61: apply_results() stamped every DEFECTS feature FIXED unconditionally, after the live status was written, so a regression in any of the 48 defect-linked features still read 'FIXED' in the canonical spreadsheet; a failing defect feature is now stamped REGRESSED with its failure note and named by the audit. BUG-62: the Phase-2/Phase-4 columns came from the hand-stamped PHASE_RESULTS dict, so a feature whose test was failing right now still advertised 'Phase-4: PASS'; a failing run now overrides Phase-4 to FAIL. Regression in t_f215 drives a synthetic failing run through all three layers.",
    "F205": "BUG-64: the dispatcher tested quantum stems before interference stems, so a quantum-framed double-slit prompt (keywords 'double-slit interference', 'quantum') rendered a wavepacket sloshing in a harmonic well instead of fringes. Caught in the human review pack. A named two-slit apparatus now skips the quantum branch; t_f205 asserts the quantum-framed case gets the fringe stage.",
    "F204": "BUG-70: the bare stem 'tunnel' routed a wind-tunnel drag problem to the quantum wavepacket; quantum tunnelling now needs quantum language (quantum tunnel/tunneling). Regression in tests/test_bugcheck_regressions.py.",
    "F213": "BUG-70: 'two masses'/'two-mass'/'energy exchange' routed Atwood machines and collisions to coupled spring oscillators, and 'coupled pendulum' went to the chaotic double pendulum; coupling language is now required and spring-coupled pendulums get the coupled-oscillator staging. Regression in tests/test_bugcheck_regressions.py.",
    "F214": "BUG-70: a bare 'mirror' stem routed any summary saying 'mirror image' to the concave-mirror ray diagram; 'mirror' now needs optics cues (focal, image, ray, reflect...). Regression in tests/test_bugcheck_regressions.py.",
    "F218": "BUG-71: orbit_period matched the substring 'iss' (emission, transmission, mission) and took Planck's h as an altitude, so photoelectric/Bohr/sound problems rendered the ISS video; projectile_landing matched 'how far'/'lands' plus any speed, so braking distances rendered a kicked ball, and vertical or cliff launches were drawn as a 40-degree kick. ISS is now a whole word, atomic context is excluded, weak cues need a launch angle, and non-oblique launches do not match. Regression in tests/test_bugcheck_regressions.py.",
    "F220": "BUG-72: Wikibooks references were cited as 'Wikipedia' in the PDF, and relevant_citations only filtered the Wikipedia label; citations are labelled by site and both are filtered. Regression in tests/test_bugcheck_regressions.py.",
    "F224": "BUG-108: strict visual auditing treated expected sub-second fades as broken blank output, and compared normalized blank/static ratios between clips whose durations differed several-fold. Brief fades now pass while sustained gaps and excessive blank ratios fail; ratio deltas are skipped and disclosed when clip duration changes by more than 25%, while duration collapse checks remain active. Regression in t_f224.",
    "F164": "BUG-110: the surface audit recognized literal controls but skipped localized dictionaries such as `_TEXT` and `_COPY`, so a localized student feature could be added without a tracked story. The scanner now records locale maps and requires a feature row to include the source module and supported language names; non-Latin UI labels are tokenized instead of silently discarded. Regression in t_f164.",
    "F231": "BUG-111: ReferenceSourcesDialog hard-coded its labels, guidance, empty states, file details, and errors in Russian even when the student had selected Kazakh or English; standalone opening also skipped registration of the bundled language-safe font. The dialog now localizes its full copy in kk/ru/en, installs the bundled UI font, and both practice/library entry points pass the active language. Regression in t_f231.",
    "F01": "BUG-113: Ruff auto-fix removed imports that were the backwards-compatible widget re-exports after UI modularization, so launching MainWindow raised ImportError for AnalysisPanel (and later widget imports failed similarly). The widgets facade now explicitly re-exports the widget symbols and declares __all__; t_f01 checks the facade contract and constructs MainWindow. Pytest also caught the private _DiagnosticsDrawer import used by the diagnostics test; this legacy compatibility symbol is now re-exported and t_f01 requires it. The prior full run predated Ruff auto-fix; the post-fix rerun caught these breaks.",
    "F227": "BUG-112: saving a future ЕНТ date and opening the practice dialog raised NameError because `_update_dashboard_summary()` called `date.fromisoformat()` and `date.today()` without importing `date`. The saved goal remained on disk, but the practice screen could not load; the existing progress test only inspected JSON and never opened the UI with a date. Fixed by importing `datetime.date`; t_f227 now opens the dialog with a future saved date and checks the localized countdown.",
    "F158": "BUG-116: the canonical feature tracker used fabricated `:1` implementation references, retained stale pre-modularization paths, and omitted a reference for the hidden `.github/workflows/render.yml` path. The source resolver now maps named symbols to Python definitions or relevant YAML lines and preserves leading dots in paths; all 231 stories now have concrete existing source references with in-range, nonblank lines. The integrity audit validates every reference and requires logged bugs for Phase-2 FAIL/PARTIAL rows.",
    "F113": "BUG-118: `LiveCanvas` split only non-finite samples, but tan(pi/2) is a huge finite float. The clipped polyline joined samples across each asymptote and drew a false chord through the graph. A viewport-sized overscan now masks extreme pixel coordinates before run segmentation for both curves and fills; regression in t_f113 requires tan(t) over [-pi, pi] to produce three branches while all singular samples remain finite.",
}


for _bug_id, (_feature_id, _evidence) in ERROR_FEATURE_LINKS.items():
    _existing_note = DEFECTS.get(_feature_id, "")
    if _bug_id not in re.findall(r"BUG-\d+", _existing_note):
        addition = f"{_bug_id}: {_evidence}. Detailed root cause and fix: ERRORS_FOUND.md."
        DEFECTS[_feature_id] = "; ".join(
            part for part in (_existing_note, addition) if part
        )

# Include every mapped historical defect in the spreadsheet's explicit
# "Errors found" cell, even when its detailed fix note is maintained here.
_errors_column = HEADERS.index("Errors found")
for _feature_id, _note in DEFECTS.items():
    _bug_ids = re.findall(r"BUG-\d+", _note)
    for _index, _row in enumerate(FEATURES):
        if _row[0] != _feature_id:
            continue
        _updated_errors = _row[_errors_column]
        for _bug_id in _bug_ids:
            _updated_errors = _append_bug_ids(_updated_errors, _bug_id)
        FEATURES[_index] = (
            _row[:_errors_column] + (_updated_errors,) + _row[_errors_column + 1:]
        )
        break


# Every BUG row in ERRORS_FOUND.md must be represented by at least one story.
# Keep this allowlist empty unless an issue is intentionally outside product and
# test-harness scope, and explain such an exception next to its ID.
NON_FEATURE_DEFECTS: dict[str, str] = {}


def apply_results(results: dict[str, dict] | None = None) -> None:
    """Stamp statuses from feature_test_results.json + Phase-2 defects.

    `results` is injectable so the gate regression (t_f215) can drive a synthetic
    failing run without touching the tracked results file.
    """
    passed = results
    if passed is None:
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
        for index, row in enumerate(FEATURES):
            if row[0] != fid:
                continue
            updated = list(row)
            for key, column in (("phase2_status", "Phase-2 result"), ("phase4_status", "Phase-4 result")):
                if res.get(key) in {"PASS", "FAIL", "PENDING", "PARTIAL", "BLOCKED", "DEFERRED"}:
                    updated[HEADERS.index(column)] = res[key]
            FEATURES[index] = tuple(updated)
            break
    # Defect features become FIXED (Phase 3 applied the fix + Phase 4 re-verified)
    # — but ONLY while their test still passes. BUG-61: this loop used to stamp
    # FIXED unconditionally, so a previously-fixed feature whose test started
    # failing again still read "FIXED" in the canonical spreadsheet. A regression
    # in any of the defect-linked features was structurally invisible.
    for fid, note in DEFECTS.items():
        row = next((r for r in FEATURES if r[0] == fid), None)
        if passed.get(fid, {}).get("status") == "FAIL":
            failure = str(passed.get(fid, {}).get("note", "")).strip()
            # ASCII only: non-ASCII source literals decode to U+FFFD on hosts
            # whose Python resolves source encoding from a legacy locale.
            set_status(fid, "REGRESSED", (f"REGRESSION: {failure} Previously: {note}")[:280])
            continue
        if passed.get(fid, {}).get("status") != "PASS":
            set_status(fid, "PARTIAL", ("Fix recorded; no passing check in the supplied run. " + note)[:280])
            set_phase4(fid, "PENDING")
            continue
        base = ("Verified. " if row and row[7] == "PASS" else "")
        set_status(fid, "FIXED", (base + note)[:280])
    # BUG-62: the Phase-2/Phase-4 columns are hand-stamped from PHASE_RESULTS, so
    # a feature whose test is failing right now still advertised "Phase-4: PASS".
    # A failing run always wins over the stamp.
    for fid, res in passed.items():
        if res.get("status") == "FAIL":
            try:
                set_phase4(fid, "FAIL")
            except KeyError:
                pass
    # A harness pass proves only what that check exercises. Keep end-to-end
    # user behaviour separate from software checks and historical phase stamps.
    for index, row in enumerate(FEATURES):
        res = passed.get(row[0], {})
        checked = str(res.get("checked_at") or "Not recorded (historical result)")
        scope = {
            "static": "Source assertions; no executed user journey",
            "gui": "Offscreen widget and signal checks; no native UI journey",
            "headless": "Automated service/harness checks; see result note",
        }.get(row[6], "Automated harness only")
        live_evidence = res.get("live_cloud_evidence")
        if isinstance(live_evidence, dict) and live_evidence.get("confirmed"):
            scope += "; live GitHub v7: 4s 720p30 fully decoded, cache reuse and missing-output refusal"
        native_evidence = res.get("native_ui_evidence")
        if isinstance(native_evidence, dict) and native_evidence.get("confirmed"):
            scope = scope.replace("; no native UI journey", "")
            scope += "; native UI: " + str(native_evidence.get("scope", "see recorded evidence"))
        behaviour = "FAIL" if res.get("status") == "FAIL" else "PARTIAL" if res.get("status") == "PASS" else "PENDING"
        remaining = "Complete story-level acceptance including failure paths"
        if row[13] == "live-cloud":
            remaining = "Live cloud dispatch, artifact delivery and user playback"
        if row[0] == "F239":
            remaining = "Real camera opt-in, interruption and recovery in native UI"
        elif row[0] == "F235":
            remaining = "Native profile save/cancel, avatar file picker, keyboard and layout acceptance"
        elif row[0] == "F227":
            remaining = "Native goals/result save, unavailable/stale read states and retry; physical file-access failures"
        elif row[0] == "F230":
            remaining = "Native dashboard/progress layout, language changes, profile isolation and file-error recovery"
        elif row[0] == "F228":
            remaining = "Native PDF picker/cancel/error; visual review across all question kinds and long topic sets"
        elif row[0] == "F238":
            remaining = "Native close/reject/resume and pending-result recovery; physical storage interruption"
        elif row[0] == "F244":
            remaining = "Native companion selection, persistence failure/retry and translated dialog layout"
        elif row[0] == "F242":
            remaining = "Deployed HTTPS endpoint, UI sync success/failure and recovery"
        elif row[0] == "F158":
            remaining = "Native cloud setup and permission recovery; ambiguous remote outputs and full lesson playback"
        elif row[0] == "F249":
            remaining = "Live cloud artifact delivery, packaged decoder availability, full playback and visual/audio review"
        elif row[6] == "gui":
            remaining = "Native UI journey, layout, persisted state and failure paths"
        if isinstance(native_evidence, dict) and native_evidence.get("confirmed") and native_evidence.get("remaining"):
            remaining = str(native_evidence["remaining"])
        FEATURES[index] = row[:17] + (checked, scope, behaviour, remaining)


if __name__ == "__main__":
    from aetherlab.core.console import configure_utf8_stdio

    configure_utf8_stdio()
    apply_results()
    write_csv()
    write_xlsx()
    print(f"Wrote {len(FEATURES)} features to:")
    print(f"  {XLSX_PATH}")
    print(f"  {CSV_PATH}")
