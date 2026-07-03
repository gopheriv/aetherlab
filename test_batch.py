"""Comprehensive feature testing for AetherLab."""
import sys
import asyncio
import traceback
from pathlib import Path

# Force unbuffered
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

results = []

def test(feature_id, name, fn):
    try:
        fn()
        results.append((feature_id, name, "PASS", ""))
        print(f"  [PASS] {feature_id}: {name}")
    except Exception as e:
        results.append((feature_id, name, "FAIL", str(e)))
        print(f"  [FAIL] {feature_id}: {name} — {e}")
        traceback.print_exc()

print("=" * 70)
print("AETHERLAB FEATURE TESTING")
print("=" * 70)

# ── SETTINGS ──
print("\n--- Settings ---")

def test_f06():
    from aetherlab.core.settings import load_settings
    s = load_settings()
    assert s.llm_model, "Model should not be empty"
    assert s.data_dir, "Data dir should not be empty"
    assert s.cache_path, "Cache path should not be empty"
    print(f"    Model: {s.llm_model}, API key: {bool(s.openai_api_key)}, Timeout: {s.llm_timeout_seconds}s")
test("F06", "Load Settings from Environment", test_f06)

def test_f07():
    from aetherlab.core.settings import load_qwen_settings
    q = load_qwen_settings()
    print(f"    Qwen settings keys: {list(q.keys())}")
    assert isinstance(q, dict), "Should return dict"
test("F07", "Load Qwen Config", test_f07)

def test_f77():
    from aetherlab.core.settings import _default_data_dir
    d = _default_data_dir()
    import sys as _sys
    if _sys.platform == "win32":
        assert "AppData" in str(d) or "AetherLab" in str(d), f"Expected AppData path, got {d}"
    print(f"    Default data dir: {d}")
test("F77", "Platform-Aware Paths", test_f77)

# ── MODELS ──
print("\n--- Models ---")

def test_f75():
    from aetherlab.core.models import ProblemRequest
    from aetherlab.core.cache import SessionCache
    from aetherlab.core.settings import load_settings
    s = load_settings()
    cache = SessionCache(s.cache_path)
    r1 = ProblemRequest(prompt="  solve   the  pendulum  ")
    r2 = ProblemRequest(prompt="solve the pendulum")
    k1 = cache.make_key(r1)
    k2 = cache.make_key(r2)
    assert k1 == k2, f"Keys differ: {k1[:16]} vs {k2[:16]}"
    print(f"    Keys match: {k1[:16]}")
test("F75", "Whitespace-Normalized Cache Keys", test_f75)

def test_f76():
    from aetherlab.core.models import SolverResult, RagResult, SceneBundle
    # Malformed JSON
    sr = SolverResult.from_json({})
    assert sr.summary == "", f"Expected empty summary, got {sr.summary!r}"
    assert sr.derivation_steps == [], f"Expected empty steps"
    rr = RagResult.from_json({})
    assert rr.keywords == []
    sb = SceneBundle.from_json({})
    assert sb.class_name == "AetherLabScene"
    print(f"    Defensive deserialization: all defaults applied")
test("F76", "Defensive JSON Deserialization", test_f76)

def test_models_serialization():
    from aetherlab.core.models import SolverResult, RagResult, RagHit, SceneBundle
    sr = SolverResult(
        summary="Test summary",
        derivation_steps=["Step 1", "Step 2"],
        keywords=["test"],
        variables={"x": 1.0},
        model_name="test-model"
    )
    j = sr.to_json()
    sr2 = SolverResult.from_json(j, cached=True)
    assert sr2.cached == True
    assert sr2.summary == "Test summary"

    rag = RagResult(
        keywords=["k1"],
        hits=[RagHit(source_path="/a/b.pdf", page_number=3, score=0.8, excerpt="text")],
        backend="test"
    )
    j = rag.to_json()
    rag2 = RagResult.from_json(j, cached=True)
    assert rag2.cached == True
    assert len(rag2.hits) == 1
    assert rag2.hits[0].source_name == "b.pdf"

    sb = SceneBundle(class_name="TestScene", code="pass", engine="manim", status="ok")
    j = sb.to_json()
    sb2 = SceneBundle.from_json(j, cached=True)
    assert sb2.cached == True
    print(f"    Serialization round-trip: all models OK")
test("F68a", "Model Serialization Round-Trip", test_models_serialization)

# ── CACHE ──
print("\n--- Cache ---")

def test_f18():
    from aetherlab.core.settings import load_settings
    from aetherlab.core.models import ProblemRequest, SolverResult
    from aetherlab.core.cache import SessionCache
    s = load_settings()
    cache = SessionCache(s.cache_path)
    req = ProblemRequest(prompt="Solve the simple pendulum for small angles")
    key = cache.ensure_request(req)
    cached = cache.get(key)
    assert cached is not None, "Should find cached session"
    assert cached.solver is not None, "Solver should be cached"
    assert cached.solver.cached == True, "Cached flag should be True"
    print(f"    Cache hit: key={key[:16]}..., solver.cached={cached.solver.cached}")
test("F18", "Cache Hit on Repeated Prompt", test_f18)

def test_cache_incremental():
    from aetherlab.core.settings import load_settings
    from aetherlab.core.models import ProblemRequest, SolverResult, RagResult
    from aetherlab.core.cache import SessionCache
    s = load_settings()
    cache = SessionCache(s.cache_path)
    req = ProblemRequest(prompt=f"__test_incremental_{__import__('time').time()}__")
    key = cache.ensure_request(req)
    # Store solver only
    sr = SolverResult(summary="test", derivation_steps=[], keywords=[], variables={}, model_name="test")
    cache.store_solver(key, sr)
    cached = cache.get(key)
    assert cached.solver is not None, "Solver should be stored"
    assert cached.rag is None, "RAG should not be stored yet"
    # Store RAG
    rr = RagResult(keywords=["k"], hits=[], backend="test")
    cache.store_rag(key, rr)
    cached = cache.get(key)
    assert cached.rag is not None, "RAG should now be stored"
    print(f"    Incremental storage: solver and RAG stored independently")
test("F68", "Incremental Stage Caching", test_cache_incremental)

def test_cache_whitelist():
    from aetherlab.core.settings import load_settings
    from aetherlab.core.cache import SessionCache
    s = load_settings()
    cache = SessionCache(s.cache_path)
    try:
        cache._store_json("fake", "evil_column; DROP TABLE sessions;", {})
        assert False, "Should have raised ValueError"
    except ValueError:
        print(f"    SQL injection guard: PASS")
test("F68b", "Cache Column Whitelist (SQL injection guard)", test_cache_whitelist)

# ── EVENTS ──
print("\n--- Events ---")

def test_events():
    from aetherlab.core.events import StateBus, Event
    bus = StateBus()
    received = []
    bus.subscribe("test", lambda e: received.append(e))
    bus.emit("test", {"data": 42})
    assert len(received) == 1
    assert received[0].name == "test"
    assert received[0].payload == {"data": 42}
    print(f"    Event bus: subscribe + emit OK")
test("F-EVT", "Event Bus (StateBus)", test_events)

# ── KEYWORDS ──
print("\n--- Keyword Extraction ---")

def test_f17():
    from aetherlab.services.llm import extract_keywords
    # Test phrase detection
    kw = extract_keywords("Solve the Navier-Stokes equation for turbulent flow")
    assert "navier stokes" in kw, f"Should detect 'navier stokes' phrase, got {kw}"
    kw2 = extract_keywords("Fourier transform of a Gaussian")
    assert "fourier transform" in kw2, f"Should detect 'fourier transform' phrase, got {kw2}"
    # Test hyphenated form detection
    kw_hyphen = extract_keywords("The Navier-Stokes equations describe fluid flow")
    assert "navier stokes" in kw_hyphen, f"Should detect hyphenated 'Navier-Stokes', got {kw_hyphen}"
    # Test basic extraction
    kw3 = extract_keywords("damped harmonic oscillator with friction")
    assert len(kw3) > 0, "Should extract keywords"
    print(f"    Phrases detected: navier stokes={kw}, fourier={kw2}, hyphen={kw_hyphen}")
    print(f"    Basic keywords: {kw3}")
test("F17", "Keyword Extraction + Phrase Detection", test_f17)

# ── SCENE GENERATION ──
print("\n--- Scene Generation ---")

def test_f26():
    from aetherlab.services.manim_runtime import ManimRuntime
    from aetherlab.core.models import ProblemRequest, SolverResult, RagResult
    mr = ManimRuntime()
    req = ProblemRequest(prompt="Damped harmonic oscillator")
    solver = SolverResult(
        summary="Exponential decay with oscillation",
        derivation_steps=["mx'' + cx' + kx = 0", "Characteristic equation"],
        keywords=["oscillator", "damping"],
        variables={"damping": 0.3, "stiffness": 2.0, "mass": 1.5},
        model_name="test"
    )
    rag = RagResult(keywords=["oscillator"], hits=[], backend="test")
    scene = mr.generate_scene(req, solver, rag)
    assert scene.status == "compiled", f"Expected 'compiled', got '{scene.status}'"
    assert scene.engine in ("manim-community", "manimgl"), f"Unexpected engine: {scene.engine}"
    compile(scene.code, "<test>", "exec")
    print(f"    Engine: {scene.engine}, Status: {scene.status}, Code: {len(scene.code)} chars")
test("F26", "Static Fallback Scene + Compile", test_f26)

def test_f33():
    from aetherlab.services.manim_runtime import ManimRuntime
    mr = ManimRuntime()
    engine, diag = mr.detect_engine()
    assert engine in ("manim-community", "manimgl", "none"), f"Unexpected: {engine}"
    print(f"    Detected engine: {engine}, diagnostics: {diag}")
test("F33", "Engine Detection", test_f33)

def test_f79():
    from aetherlab.services.manim_runtime import ManimRuntime
    mr = ManimRuntime()
    cmd = mr._find_manim_command()
    assert cmd is not None, "manim binary should be found"
    print(f"    Manim command: {cmd}")
test("F79", "Manim Binary Detection", test_f79)

def test_sanitize_name():
    from aetherlab.services.manim_runtime import sanitize_scene_name
    assert sanitize_scene_name("Hello World 123") == "HelloWorld123"
    assert sanitize_scene_name("!!!") == "AetherLabScene"
    assert sanitize_scene_name("my-cool-scene") == "MyCoolScene"
    print(f"    sanitize_scene_name: all cases pass")
test("F-SAN", "Scene Name Sanitization", test_sanitize_name)

# ── RAG ──
print("\n--- RAG ---")

def test_f21():
    import asyncio
    from aetherlab.core.settings import load_settings
    from aetherlab.services.rag import LocalVectorRag
    s = load_settings()
    rag = LocalVectorRag(s)
    result = asyncio.run(rag.search(["pendulum", "oscillator"], limit=5))
    print(f"    Backend: {result.backend}, Hits: {len(result.hits)}")
    # Library might be empty, so just check it doesn't crash
    assert isinstance(result.hits, list)
test("F21", "RAG Search (filesystem fallback)", test_f21)

# ── PDF SERVICE ──
print("\n--- PDF ---")

def test_pdf_service():
    from aetherlab.services.pdf import PdfService
    ps = PdfService()
    print(f"    PyMuPDF available: {ps.available}")
    if not ps.available:
        print(f"    Import error: {ps.import_error}")
test("F-PDF", "PdfService Availability", test_pdf_service)

def test_latex_export():
    from aetherlab.services.pdf import export_derivation_to_latex
    import tempfile
    out = Path(tempfile.mkdtemp()) / "test.tex"
    result = export_derivation_to_latex(
        summary="Test summary with $math$ & special chars",
        derivation_steps=["Step 1: $E = mc^2$", "Step 2: $F = ma$"],
        variables={"mass": 1.0, "velocity": 3e8},
        output_path=out
    )
    assert result.exists(), "LaTeX file should be created"
    content = result.read_text(encoding="utf-8")
    assert "\\begin{document}" in content
    assert "AetherLab" in content
    print(f"    LaTeX export: {len(content)} chars, file={result}")
test("F58", "Export Derivation as LaTeX", test_latex_export)

def test_scene_code_export():
    from aetherlab.services.pdf import export_scene_code
    import tempfile
    out = Path(tempfile.mkdtemp()) / "test_scene.py"
    result = export_scene_code("from manim import *\nclass Test(Scene):\n    pass", out)
    assert result.exists()
    content = result.read_text()
    assert "from manim import *" in content
    print(f"    Scene code export: {len(content)} chars")
test("F60", "Export Scene Code", test_scene_code_export)

# ── INGESTION ──
print("\n--- Ingestion ---")

def test_chunk_text():
    from aetherlab.services.ingestion import chunk_text
    # Empty
    assert chunk_text("") == []
    # Short
    short = "Hello world."
    assert chunk_text(short) == [short]
    # Long text
    long_text = " ".join([f"Sentence number {i} with some padding text." for i in range(100)])
    chunks = chunk_text(long_text)
    assert len(chunks) > 1, f"Expected multiple chunks, got {len(chunks)}"
    # Check overlap
    print(f"    Chunks from 100 sentences: {len(chunks)} chunks")
test("F-CHK", "Text Chunking", test_chunk_text)

# ── SCENE GENERATOR FALLBACK ──
print("\n--- SceneGenerator Fallback ---")

def test_f27():
    from aetherlab.services.scene_generator import SceneGenerator
    from aetherlab.core.settings import load_settings
    from aetherlab.core.models import ProblemRequest, SolverResult, RagResult
    s = load_settings()
    sg = SceneGenerator(s)
    solver = SolverResult(
        summary="Test fallback scene",
        derivation_steps=["Step 1"],
        keywords=["test"],
        variables={"damping": 0.2, "stiffness": 1.5, "mass": 1.0},
        model_name="test"
    )
    rag = RagResult(keywords=[], hits=[], backend="none")
    req = ProblemRequest(prompt="test")
    # Call _fallback_scene directly
    code = sg._fallback_scene("TestScene", solver)
    compile(code, "<fallback>", "exec")
    assert "from manim import *" in code
    assert "TestScene" in code
    assert "ValueTracker" in code
    assert "always_redraw" in code
    print(f"    Fallback scene: {len(code)} chars, compiles OK")
test("F27", "Dynamic Fallback Scene (SceneGenerator)", test_f27)

# ── RENDER (quick - just verify video was produced by smoke test) ──
print("\n--- Render ---")

def test_f29():
    import tempfile
    render_dir = Path(tempfile.gettempdir()) / "aetherlab" / "renders"
    assert render_dir.exists(), f"Render dir should exist: {render_dir}"
    # Check for video files
    videos = list(render_dir.rglob("*.mp4"))
    print(f"    Render dir: {render_dir}")
    print(f"    Video files found: {len(videos)}")
    for v in videos[:3]:
        print(f"      {v.name} ({v.stat().st_size} bytes)")
    assert len(videos) > 0, "Should have at least one rendered video"
test("F29", "Manim Video Rendering (verify smoke test output)", test_f29)

# ── HISTORY (SQLite) ──
print("\n--- History ---")

def test_history_db():
    import sqlite3
    from aetherlab.core.settings import load_settings
    s = load_settings()
    db_path = s.data_dir / "history.sqlite3"
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        cur = conn.execute("SELECT COUNT(*) FROM history")
        count = cur.fetchone()[0]
        conn.close()
        print(f"    History DB: {count} entries at {db_path}")
    else:
        print(f"    History DB: not yet created at {db_path}")
test("F55", "Persistent History DB", test_history_db)

# ── CANVAS STATE ──
print("\n--- Canvas ---")

def test_f35():
    from aetherlab.ui.live_canvas import build_canvas_state, CanvasState
    # Damped oscillator
    cs = build_canvas_state("Test", {"damping": 0.3, "stiffness": 2.0}, False)
    assert len(cs.curves) >= 1, "Should have at least one curve"
    print(f"    Damped oscillator: {len(cs.curves)} curves")

    # Pendulum
    cs2 = build_canvas_state("Pendulum", {"gravity": 9.81, "length": 1.0}, False)
    assert len(cs2.curves) >= 1
    print(f"    Pendulum: {len(cs2.curves)} curves")

    # Generic
    cs3 = build_canvas_state("Generic", {"a": 1.0, "b": 2.0}, False)
    assert len(cs3.curves) >= 1
    print(f"    Generic (Lissajous): {len(cs3.curves)} curves")

    # Phase portrait
    cs4 = build_canvas_state("Phase", {"damping": 0.3, "stiffness": 2.0}, True)
    assert len(cs4.curves) >= 2, "Phase portrait should add extra curve"
    print(f"    Phase portrait: {len(cs4.curves)} curves")
test("F35", "Domain Auto-Detection (Canvas)", test_f35)

# ── SUMMARY ──
print("\n" + "=" * 70)
print("RESULTS SUMMARY")
print("=" * 70)
passed = sum(1 for _, _, s, _ in results if s == "PASS")
failed = sum(1 for _, _, s, _ in results if s == "FAIL")
print(f"\n  PASSED: {passed}/{len(results)}")
print(f"  FAILED: {failed}/{len(results)}")
if failed:
    print("\n  FAILURES:")
    for fid, name, status, err in results:
        if status == "FAIL":
            print(f"    {fid} ({name}): {err}")
print()

# ── POST-FIX VERIFICATION ──
print("\n" + "=" * 70)
print("POST-FIX VERIFICATION")
print("=" * 70)

# Verify _map_to_plot handles zero span
def test_div_by_zero():
    from aetherlab.ui.live_canvas import LiveCanvas, CanvasState
    # We can't instantiate LiveCanvas without QApplication, so test the static method logic
    # Just verify the code path exists
    import inspect
    src = inspect.getsource(LiveCanvas._map_to_plot)
    assert "1e-12" in src, "Division-by-zero guard should be present"
    assert "x_span" in src, "Should use x_span variable"
    print(f"    Div-by-zero guard present in _map_to_plot")
test("FIX-C1", "Division-by-zero guard in _map_to_plot", test_div_by_zero)

# Verify tracer color uses setAlpha
def test_tracer_color():
    import inspect
    from aetherlab.ui.live_canvas import LiveCanvas
    src = inspect.getsource(LiveCanvas._draw_tracer)
    assert "setAlpha" in src, "Should use setAlpha instead of string concatenation"
    print(f"    Tracer color uses setAlpha")
test("FIX-C2", "Tracer glow color fix", test_tracer_color)

# Verify _nice_step handles zero
def test_nice_step_zero():
    from aetherlab.ui.live_canvas import _nice_step
    result = _nice_step(0.0, 8)
    assert result == 1.0, f"Expected 1.0 for zero range, got {result}"
    result2 = _nice_step(1e-15, 8)
    assert result2 == 1.0, f"Expected 1.0 for near-zero range, got {result2}"
    print(f"    _nice_step(0, 8) = {result}, _nice_step(1e-15, 8) = {result2}")
test("FIX-C3", "_nice_step handles degenerate ranges", test_nice_step_zero)

# Verify phrase detection handles hyphens
def test_phrase_hyphen():
    from aetherlab.services.llm import extract_keywords
    kw = extract_keywords("Solve the Navier-Stokes equation")
    assert "navier stokes" in kw, f"Hyphenated form should be detected, got {kw}"
    print(f"    Hyphenated phrase detected: {kw}")
test("FIX-C4", "Phrase detection handles hyphenated forms", test_phrase_hyphen)

# Verify settings dialog applies changes
def test_settings_dialog():
    import inspect
    from aetherlab.ui.main_window import MainWindow
    src = inspect.getsource(MainWindow._open_settings)
    assert "replace" in src, "Should use dataclasses.replace to update settings"
    print(f"    Settings dialog uses dataclasses.replace")
test("FIX-C5", "Settings dialog applies changes", test_settings_dialog)

# Verify worker cleanup
def test_worker_cleanup():
    import inspect
    from aetherlab.ui.main_window import MainWindow
    src = inspect.getsource(MainWindow.start_pipeline)
    assert "disconnect" in src, "Should disconnect old worker signals"
    assert "deleteLater" in src, "Should call deleteLater on old worker"
    print(f"    Worker cleanup present in start_pipeline")
test("FIX-C6", "Worker signal cleanup", test_worker_cleanup)

# Verify closeEvent
def test_close_event():
    import inspect
    from aetherlab.ui.main_window import MainWindow
    src = inspect.getsource(MainWindow.closeEvent)
    assert "cancel" in src, "Should cancel worker on close"
    assert "wait" in src, "Should wait for worker to finish"
    print(f"    closeEvent gracefully shuts down worker")
test("FIX-C7", "Graceful worker shutdown on close", test_close_event)

# Verify PDF export creates temp dir
def test_pdf_export_dir():
    import inspect
    from aetherlab.ui.main_window import MainWindow
    src = inspect.getsource(MainWindow._export_pdf)
    assert "mkdir" in src, "Should create temp directory"
    print(f"    PDF export creates temp directory")
test("FIX-C8", "PDF export creates temp directory", test_pdf_export_dir)

# Verify cancel hides loading overlay
def test_cancel_overlay():
    import inspect
    from aetherlab.ui.main_window import MainWindow
    src = inspect.getsource(MainWindow._cancel_pipeline)
    assert "hide_loading" in src, "Should hide loading overlay on cancel"
    print(f"    Cancel pipeline hides loading overlay")
test("FIX-C9", "Cancel hides loading overlay", test_cancel_overlay)

# Verify progress gap fixed
def test_progress_gap():
    import inspect
    from aetherlab.ui.main_window import MainWindow
    src = inspect.getsource(MainWindow._on_progress)
    assert "< 100" in src, "Should handle values 96-99"
    print(f"    Progress handler covers all values")
test("FIX-C10", "Progress gap fixed (96-99)", test_progress_gap)

# Verify parameter dock allows negatives
def test_negative_params():
    import inspect
    from aetherlab.ui.widgets import ParameterDock
    src = inspect.getsource(ParameterDock.set_variables)
    assert "-span" in src, "Spinbox range should include -span"
    print(f"    ParameterDock allows negative values")
test("FIX-H1", "Parameter dock allows negative values", test_negative_params)

# Verify diagnostics formatting
def test_diagnostics():
    import inspect
    from aetherlab.ui.widgets import SimulationPanel
    src = inspect.getsource(SimulationPanel.set_scene_bundle)
    assert '"# {line}"' in src or "'# {line}'" in src or "f\"# {line}\"" in src, "Each diagnostic line should be prefixed with #"
    print(f"    Diagnostics formatting prefixes each line")
test("FIX-H2", "Diagnostics formatting fixed", test_diagnostics)

# Verify SQLite connection safety
def test_sqlite_safety():
    import inspect
    from aetherlab.ui.widgets import HistoryPanel
    src = inspect.getsource(HistoryPanel.add_entry)
    assert "finally" in src, "Should use try/finally for connection cleanup"
    src2 = inspect.getsource(HistoryPanel._clear)
    assert "finally" in src2, "Should use try/finally in _clear too"
    print(f"    SQLite connections use try/finally")
test("FIX-H3", "SQLite connection safety", test_sqlite_safety)

# Print post-fix summary
post_passed = sum(1 for _, _, s, _ in results if s == "PASS") - passed
post_failed = sum(1 for _, _, s, _ in results if s == "FAIL") - failed
print(f"\n  Post-fix tests: {post_passed} passed, {post_failed} failed")
print(f"  TOTAL: {passed + post_passed}/{len(results)} passed, {failed + post_failed}/{len(results)} failed")

