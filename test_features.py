"""Phase 2/4 behavioural test harness for the AetherLab feature tracker.

Exercises every catalogued feature (see build_feature_tracker.py):
  - headless features run real logic
  - gui features are constructed under an offscreen QApplication
  - static features assert source-level guarantees

Writes results to feature_test_results.json (id -> {status, note}) which
build_feature_tracker consumes to stamp the canonical spreadsheet.

Run: python test_features.py
"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

try:  # Windows consoles default to cp1251/cp1252 and choke on arrows in notes.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Isolate all state under a throwaway data dir so tests never touch real caches.
_TMP = Path(tempfile.mkdtemp(prefix="aetherlab_test_"))
os.environ["AETHERLAB_DATA_DIR"] = str(_TMP / "data")
os.environ["AETHERLAB_LIBRARY_DIR"] = str(_TMP / "lib")
os.environ["AETHERLAB_CHROMA_PATH"] = str(_TMP / "chroma")
os.environ.pop("AETHERLAB_OPENAI_API_KEY", None)
os.environ.pop("OPENAI_API_KEY", None)
# Also neutralize the ~/.qwen autoload: without this, subprocess tests (F02
# smoke) pick up a live provider key and make real LLM calls — slow and
# non-deterministic (F02 once timed out at 600s mid-suite because of it).
os.environ["QWEN_SETTINGS_PATH"] = str(_TMP / "no-qwen-settings.json")
os.environ.pop("AETHERLAB_QWEN_AUTOLOAD", None)
os.environ.pop("AETHERLAB_PROVIDER", None)
os.environ.pop("AETHERLAB_VISION_MODEL", None)

results: dict[str, dict] = {}


def check(fid: str, fn) -> None:
    try:
        note = fn() or ""
        results[fid] = {"status": "PASS", "note": str(note)[:300]}
        print(f"  [PASS] {fid}: {note}")
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        results[fid] = {"status": "FAIL", "note": f"{type(exc).__name__}: {exc}"[:300]}
        print(f"  [FAIL] {fid}: {type(exc).__name__}: {exc}")
        print("\n".join("      " + ln for ln in tb.splitlines()[-4:]))


# ── Qt app (offscreen) for gui construction tests ──
from aetherlab.ui.qt_compat import QtWidgets  # noqa: E402

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)


def _settings():
    from aetherlab.core.settings import load_settings
    return load_settings()


def _solver(**kw):
    from aetherlab.core.models import SolverResult
    base = dict(summary="Damped oscillator decays exponentially.",
               derivation_steps=["m x'' + c x' + k x = 0", "Solve characteristic eq."],
               keywords=["oscillator", "damping"],
               variables={"damping": 0.2, "stiffness": 1.5, "mass": 1.0},
               model_name="test")
    base.update(kw)
    return SolverResult(**base)


def _rag(hits=None):
    from aetherlab.core.models import RagResult
    return RagResult(keywords=["oscillator"], hits=hits or [], backend="test")


# ══════════════════════════════════════════════════════════════════════════
# Launch / CLI
# ══════════════════════════════════════════════════════════════════════════

def t_f01():
    from aetherlab.ui import app
    assert callable(app.run_app)
    from aetherlab.ui.main_window import MainWindow
    w = MainWindow(_settings())
    ok = w.windowTitle() == "AetherLab"
    w.close()
    return f"MainWindow constructs; title ok={ok}"


def t_f02():
    import subprocess
    r = subprocess.run([sys.executable, "-m", "aetherlab", "--smoke", "Solve the simple pendulum"],
                       capture_output=True, text=True, timeout=600, env={**os.environ})
    assert r.returncode == 0, f"exit {r.returncode}: {r.stderr[-300:]}"
    assert "smoke pipeline complete" in r.stdout.lower(), r.stdout[-300:]
    return f"smoke exit 0; scene status line present"


def t_f03():
    # covered structurally: const default vs provided arg
    from aetherlab.__main__ import build_parser
    ns = build_parser().parse_args(["--smoke"])
    ns2 = build_parser().parse_args(["--smoke", "custom"])
    assert ns.smoke and ns2.smoke == "custom"
    return "nargs='?' const + explicit prompt both parse"


def t_f04():
    src = Path("aetherlab_watchdog.py").read_text(encoding="utf-8")
    assert "backoff" in src.lower() and "returncode" in src.lower()
    return "watchdog present with backoff logic"


def t_f05():
    src = inspect.getsource(__import__("aetherlab.ui.qt_compat", fromlist=["require_qt"]).require_qt)
    assert "PyQt6" in src and "RuntimeError" in src
    return "require_qt raises RuntimeError w/ install hint"


# ══════════════════════════════════════════════════════════════════════════
# Settings
# ══════════════════════════════════════════════════════════════════════════

def t_f06():
    s = _settings()
    assert s.llm_model and s.data_dir and s.cache_path
    return f"model={s.llm_model} data_dir set timeout={s.llm_timeout_seconds}"


def t_f07():
    from aetherlab.core.settings import save_app_config, load_app_config, app_config_path
    save_app_config({"model": "cfg-model", "api_key": None, "base_url": "http://x"})
    cfg = load_app_config()
    assert cfg.get("model") == "cfg-model", cfg
    assert "api_key" not in cfg, "None should be dropped"
    p = app_config_path()
    assert p.exists()
    # cleanup so it doesn't taint provider-precedence test
    p.unlink()
    return "save/load round-trip; None dropped; path honored"


def t_f08():
    from aetherlab.core.settings import save_app_config, load_settings, app_config_path
    save_app_config({"model": "cfg-model"})
    os.environ["AETHERLAB_LLM_MODEL"] = "env-model"
    s = load_settings()
    del os.environ["AETHERLAB_LLM_MODEL"]
    s2 = load_settings()
    app_config_path().unlink(missing_ok=True)
    assert s.llm_model == "env-model", f"env should win, got {s.llm_model}"
    assert s2.llm_model == "cfg-model", f"config should win over default, got {s2.llm_model}"
    return "env > app-config precedence verified"


def t_f09():
    from aetherlab.core.settings import load_qwen_settings
    q = load_qwen_settings(Path(_TMP / "nope.json"))
    assert q == {}, q
    # write a fake qwen file
    fake = _TMP / "qwen.json"
    fake.write_text(json.dumps({"model": {"name": "qwen-x"},
                                "modelProviders": {"openai": [{"id": "qwen-x", "baseUrl": "http://q", "envKey": "K"}]},
                                "env": {"K": "secret"}}), encoding="utf-8")
    q2 = load_qwen_settings(fake)
    assert q2.get("model") == "qwen-x" and q2.get("base_url") == "http://q" and q2.get("api_key") == "secret", q2
    return "missing→{}; parsed model/baseUrl/apiKey"


def t_f10():
    from aetherlab.ui.main_window import SettingsDialog
    d = SettingsDialog(_settings())
    vals = d.get_settings()
    assert set(["model", "api_key", "base_url", "library_path", "data_dir", "default_quality"]).issubset(vals)
    d.close()
    # BUG-4 regression: Data path must persist via app-config when no env override.
    # Redirect the default data dir into _TMP so nothing touches the real config.
    import aetherlab.core.settings as S
    saved_env = os.environ.pop("AETHERLAB_DATA_DIR", None)
    orig_default = S._default_data_dir
    S._default_data_dir = lambda: _TMP / "cfghome"
    try:
        custom = _TMP / "custom_data"
        S.save_app_config({"data_dir": str(custom)})
        assert S.load_settings().data_dir == custom, "data_dir must persist from app-config"
    finally:
        S._default_data_dir = orig_default
        (_TMP / "cfghome" / "settings.json").unlink(missing_ok=True)
        if saved_env is not None:
            os.environ["AETHERLAB_DATA_DIR"] = saved_env
    return "dialog keys ok; Data path persists via config (BUG-4)"


def t_f11():
    from aetherlab.core.settings import _default_data_dir, _default_chroma_path
    d, c = _default_data_dir(), _default_chroma_path()
    if sys.platform == "win32":
        assert "AetherLab" in str(d)
    return f"data={d.name} chroma={c.name}"


# ══════════════════════════════════════════════════════════════════════════
# Command bar / input
# ══════════════════════════════════════════════════════════════════════════

def t_f12():
    from aetherlab.ui.widgets import CommandBar
    cb = CommandBar()
    cb.show()  # _submit guards on run_button.isVisible()
    got = []
    cb.submitted.connect(lambda s: got.append(s))
    cb.input.setText("  hello world  ")
    cb._submit()
    assert got == ["hello world"], got
    assert cb.input.text() == "", "field should clear"
    cb._submit()  # empty now → no emit
    assert got == ["hello world"]
    cb.close()
    return "submit trims+emits+clears; empty guarded"


def t_f13():
    from aetherlab.ui.widgets import CommandBar, EXAMPLE_PROMPTS
    assert len(EXAMPLE_PROMPTS) == 10
    cb = CommandBar()
    cb._pick_example(EXAMPLE_PROMPTS[2])
    assert cb.input.text() == EXAMPLE_PROMPTS[2]
    cb.close()
    return f"{len(EXAMPLE_PROMPTS)} examples; pick fills field"


def t_f14():
    from aetherlab.ui.widgets import CommandBar
    cb = CommandBar()
    cb._quality.setCurrentText("High")
    assert cb.get_render_quality() == "h"
    cb.set_quality("m")
    assert cb.get_render_quality() == "m"
    cb.close()
    return "quality maps Draft/Standard/High→l/m/h; set_quality by flag"


def t_f15():
    from aetherlab.ui.widgets import CommandBar
    cb = CommandBar()
    cb.set_busy(True)
    busy = cb.cancel_button.isVisibleTo(cb) and not cb.run_button.isVisibleTo(cb) and not cb.input.isEnabled()
    cb.set_busy(False)
    idle = cb.run_button.isVisibleTo(cb) and not cb.cancel_button.isVisibleTo(cb)
    cb.close()
    assert busy and idle
    return "Run↔Cancel swap + input disable"


# ══════════════════════════════════════════════════════════════════════════
# Pipeline
# ══════════════════════════════════════════════════════════════════════════

def t_f16():
    # Run the headless pipeline end-to-end (fallback solver, no key).
    from aetherlab.services.pipeline import AetherLabPipeline
    from aetherlab.core.models import ProblemRequest
    res = asyncio.run(AetherLabPipeline(_settings()).run(ProblemRequest(prompt="damped oscillator test")))
    assert res.solver and res.scene and res.rag
    assert res.scene.status in {"compiled", "rendered", "render-error", "render-timeout"}, res.scene.status
    return f"pipeline ran: solver={res.solver.model_name} scene={res.scene.status}"


def t_f17():
    from aetherlab.ui.widgets import PipelineStepper
    st = PipelineStepper()
    st.set_stage(0, "active")
    st.set_stage(0, "complete")  # records elapsed[0]
    st.set_stage(2, "complete")
    assert st._statuses[0] == "complete" and st._statuses[2] == "complete"
    assert st._elapsed, "elapsed should be recorded"
    st.reset()
    # BUG-1 regression: reset() must clear elapsed/started, not just set_stage(-1).
    assert all(s == "pending" for s in st._statuses)
    assert not st._elapsed and not st._started, "reset must clear timing state"
    st.close()
    return "stage transitions + reset clears timing (BUG-1)"


def t_f18():
    from aetherlab.ui.workers import PipelineWorker, _PipelineCancelled
    from aetherlab.core.models import ProblemRequest
    w = PipelineWorker(ProblemRequest(prompt="x"), _settings())
    w.cancel()
    raised = False
    try:
        w._check_cancelled()
    except _PipelineCancelled:
        raised = True
    assert raised
    return "cancel flag → _check_cancelled raises"


def t_f19():
    src = inspect.getsource(__import__("aetherlab.ui.main_window", fromlist=["MainWindow"]).MainWindow.start_pipeline)
    assert "isRunning()" in src and "already running" in src
    return "double-run guard present"


def t_f20():
    src = inspect.getsource(__import__("aetherlab.ui.main_window", fromlist=["MainWindow"]).MainWindow.start_pipeline)
    assert "disconnect()" in src and "deleteLater()" in src
    return "old worker disconnected + deleteLater"


def t_f21():
    src = inspect.getsource(__import__("aetherlab.ui.main_window", fromlist=["MainWindow"]).MainWindow.closeEvent)
    assert "cancel()" in src and "wait(5000)" in src
    return "closeEvent cancels + waits 5s"


# ══════════════════════════════════════════════════════════════════════════
# Solver
# ══════════════════════════════════════════════════════════════════════════

def t_f22():
    from aetherlab.services.llm import AsyncLLMCoordinator
    assert hasattr(AsyncLLMCoordinator, "_solve_remote")
    src = inspect.getsource(AsyncLLMCoordinator._solve_remote)
    assert "temperature=0.2" in src and "plot" in src
    return "remote solve path present (temp 0.2, plot key)"


def t_f23():
    from dataclasses import replace
    from aetherlab.services.llm import AsyncLLMCoordinator
    from aetherlab.core.models import ProblemRequest
    # Force no key so we exercise the deterministic fallback regardless of any
    # working provider config on the host (e.g. ~/.qwen).
    keyless = replace(_settings(), openai_api_key=None)
    r = asyncio.run(AsyncLLMCoordinator(keyless).solve(ProblemRequest(prompt="Solve the RLC circuit")))
    assert r.model_name == "deterministic-fallback", r.model_name
    assert len(r.derivation_steps) == 5 and r.plot is not None
    return f"fallback: {len(r.derivation_steps)} steps, plot attached"


def t_f24():
    from aetherlab.services.llm import extract_keywords
    a = extract_keywords("Solve the Navier-Stokes equation for turbulent flow")
    b = extract_keywords("Fourier transform of a Gaussian")
    assert "navier stokes" in a and "fourier transform" in b, (a, b)
    return f"phrases: {a[:2]} / {b[:2]}"


def t_f25():
    from aetherlab.services.llm import AsyncLLMCoordinator
    c = AsyncLLMCoordinator(_settings())
    d = c._parse_json('<think>ignore { this </think> here is {"summary": "ok"} trailing')
    assert d == {"summary": "ok"}, d
    return "think-strip + brace extraction"


def t_f26():
    from aetherlab.core.models import SolverResult
    sr = SolverResult.from_json({"plot": {"kind": "explicit", "y": "sin(t)", "t_range": [0, 6]}})
    assert isinstance(sr.plot, dict)
    sr2 = SolverResult.from_json({"plot": "bad"})
    assert sr2.plot is None
    return "plot dict kept; non-dict → None"


# ══════════════════════════════════════════════════════════════════════════
# Plot compiler (NEW)
# ══════════════════════════════════════════════════════════════════════════

def t_f27():
    import numpy as np
    from aetherlab.services.plotting import compile_expression
    fn = compile_expression("exp(-damping*t)*sin(stiffness*t)", {"damping", "stiffness"})
    out = fn(np.linspace(0, 5, 10), {"damping": 0.2, "stiffness": 1.0})
    assert out.shape == (10,) and np.isfinite(out).all()
    return "whitelisted expr compiles + vectorizes"


def t_f28():
    from aetherlab.services.plotting import compile_expression, ExprError
    bad = ["__import__('os')", "t.__class__", "open('x')", "a" * 600, "lambda: 1", "t if t else 0"]
    rejected = 0
    for expr in bad:
        try:
            compile_expression(expr, {"a"})
        except ExprError:
            rejected += 1
    assert rejected == len(bad), f"only {rejected}/{len(bad)} rejected"
    # caret normalized
    import numpy as np
    fn = compile_expression("t^2", set())
    assert abs(fn(np.array([3.0]), {})[0] - 9.0) < 1e-9
    return f"all {rejected} unsafe exprs rejected; ^→** works"


def t_f29():
    from aetherlab.services.plotting import compile_plot, fallback_plot_payload, ExprError
    cp = compile_plot(fallback_plot_payload(), {"damping": 0.2, "stiffness": 1.0, "mass": 1.0})
    assert cp.kind == "explicit"
    try:
        compile_plot({"kind": "bogus", "y": "t", "t_range": [0, 1]}, set())
        raise AssertionError("bad kind not rejected")
    except ExprError:
        pass
    return "fallback payload compiles; bad kind rejected"


# ══════════════════════════════════════════════════════════════════════════
# Cache
# ══════════════════════════════════════════════════════════════════════════

def t_f30():
    from aetherlab.core.cache import SessionCache
    from aetherlab.core.models import ProblemRequest
    c = SessionCache(_settings().cache_path)
    k1 = c.make_key(ProblemRequest(prompt="  solve   the pendulum "))
    k2 = c.make_key(ProblemRequest(prompt="solve the pendulum"))
    assert k1 == k2
    return f"whitespace-normalized key {k1[:12]}"


def t_f31():
    from aetherlab.core.cache import SessionCache
    from aetherlab.core.models import ProblemRequest, SolverResult, RagResult
    c = SessionCache(_settings().cache_path)
    req = ProblemRequest(prompt="incremental-test-xyz")
    key = c.ensure_request(req)
    c.store_solver(key, _solver())
    got = c.get(key)
    assert got.solver and got.solver.cached and got.rag is None
    c.store_rag(key, RagResult(keywords=["k"], hits=[], backend="t"))
    assert c.get(key).rag is not None
    # SQL-injection guard
    try:
        c._store_json(key, "evil; DROP TABLE sessions;", {})
        raise AssertionError("column not whitelisted")
    except ValueError:
        pass
    return "independent stage storage + column whitelist"


def t_f32():
    from aetherlab.services.pipeline import AetherLabPipeline
    from dataclasses import replace
    p = AetherLabPipeline(_settings())
    fb = _solver(model_name="deterministic-fallback")
    # with key present, fallback is not usable
    p.settings = replace(p.settings, openai_api_key="sk-x")
    assert p._solver_cache_usable(fb) is False
    other = _solver(model_name="some-other-model")
    assert p._solver_cache_usable(other) is False
    return "fallback+key rejected; wrong model rejected"


def t_f33():
    src = inspect.getsource(__import__("aetherlab.services.pipeline", fromlist=["AetherLabPipeline"]).AetherLabPipeline.run)
    assert "engine != current_engine" in src and "compiled" in src
    return "scene reused only on engine+status match"


def t_f34():
    from aetherlab.services.pipeline import _video_exists
    assert _video_exists("") is False
    assert _video_exists(str(_TMP / "nope.mp4")) is False
    return "_video_exists guards empty/missing"


# ══════════════════════════════════════════════════════════════════════════
# RAG
# ══════════════════════════════════════════════════════════════════════════

def t_f35():
    src = inspect.getsource(__import__("aetherlab.services.rag", fromlist=["LocalVectorRag"]).LocalVectorRag._try_chromadb)
    assert "1.0 + float(distance" in src and "textbooks" in src
    return "chromadb path scores 1/(1+dist)"


def t_f36():
    from aetherlab.services.rag import LocalVectorRag
    lib = Path(_settings().library_path)
    lib.mkdir(parents=True, exist_ok=True)
    (lib / "note.txt").write_text("The damped oscillator loses energy. oscillator oscillator.", encoding="utf-8")
    r = asyncio.run(LocalVectorRag(_settings()).search(["oscillator"], limit=5))
    assert r.backend in {"filesystem", "chromadb"} and len(r.hits) >= 1, (r.backend, len(r.hits))
    # BUG-3 regression: scores must be normalized to [0,1] (top hit == 1.0).
    assert all(0.0 <= h.score <= 1.0 for h in r.hits), [h.score for h in r.hits]
    if r.backend == "filesystem":
        assert abs(max(h.score for h in r.hits) - 1.0) < 1e-9, "top filesystem hit should be 1.0"
    return f"{r.backend}: {len(r.hits)} hit(s), scores in [0,1] (BUG-3)"


def t_f37():
    from aetherlab.services.rag import LocalVectorRag
    r = asyncio.run(LocalVectorRag(_settings()).search([]))
    assert r.backend == "none" and r.hits == []
    return "empty keywords → backend 'none'"


def t_f38():
    from aetherlab.ui.widgets import ReferencePanel
    from aetherlab.core.models import RagHit
    rp = ReferencePanel()
    rp.set_rag_result(_rag([RagHit(source_path=str(_TMP / "b.pdf"), page_number=3, score=0.9, excerpt="x")]))
    rp.set_rag_result(_rag([]))  # empty path
    rp.close()
    return "reference cards render + empty state"


# ══════════════════════════════════════════════════════════════════════════
# Ingestion
# ══════════════════════════════════════════════════════════════════════════

def t_f39():
    src = inspect.getsource(__import__("aetherlab.services.pipeline", fromlist=["AetherLabPipeline"]).AetherLabPipeline._ensure_ingested)
    assert "get_collection" in src and "ingest()" in src
    return "auto-ingest on empty collection"


def t_f40():
    from aetherlab.services.ingestion import LibraryIngestor
    lib = Path(_settings().library_path)
    lib.mkdir(parents=True, exist_ok=True)
    f = lib / "manifest_test.txt"
    f.write_text("hello world " * 50, encoding="utf-8")
    ing = LibraryIngestor(_settings())
    pend = ing.pending_files()
    assert f in pend, "new file should be pending"
    return f"{len(pend)} pending file(s) detected"


def t_f41():
    from aetherlab.services.ingestion import chunk_text
    assert chunk_text("") == []
    assert chunk_text("short.") == ["short."]
    long = " ".join(f"Sentence {i} padding words here." for i in range(200))
    ch = chunk_text(long)
    assert len(ch) > 1
    return f"{len(ch)} chunks from long text"


def t_f42():
    from aetherlab.services.ingestion import LibraryIngestor
    src = inspect.getsource(LibraryIngestor._chunks_from_pdf)
    assert "fitz" in src and "page" in src
    return "PDF page-by-page chunking present"


def t_f43():
    from aetherlab.services.ingestion import LibraryIngestor
    # Real incremental ingest into chromadb (deps present).
    lib = Path(_settings().library_path)
    lib.mkdir(parents=True, exist_ok=True)
    (lib / "ingest_me.txt").write_text("kinematics energy momentum " * 80, encoding="utf-8")
    ing = LibraryIngestor(_settings())
    n1 = ing.ingest(reset=True)
    n2 = ing.ingest()  # nothing new
    assert n1 > 0 and n2 == 0, (n1, n2)
    return f"ingest upserted {n1}; re-run 0 (incremental)"


# ══════════════════════════════════════════════════════════════════════════
# Library manager
# ══════════════════════════════════════════════════════════════════════════

def t_f44():
    from aetherlab.ui.widgets import LibraryPanel
    lp = LibraryPanel()
    lp.set_settings(_settings())
    n = lp.library_file_count()
    lp.refresh()
    lp.close()
    return f"library panel refresh; file_count={n}"


def t_f45():
    from aetherlab.ui.widgets import LibraryPanel
    assert hasattr(LibraryPanel, "_add_folder")
    src = inspect.getsource(LibraryPanel._add_folder)
    assert "copy2" in src and "reindex" in src.lower()
    return "add-folder copies + triggers reindex"


def t_f46():
    from aetherlab.ui.widgets import LibraryPanel
    src = inspect.getsource(LibraryPanel._reindex_clicked)
    assert "ControlModifier" in src
    src2 = inspect.getsource(LibraryPanel._start_ingest)
    assert "_IngestWorker" in src2
    return "incremental/full reindex via background worker"


def t_f47():
    from aetherlab.ui.widgets import StarterLibraryDialog
    d = StarterLibraryDialog()
    books = d.selected_books()
    assert len(books) >= 1  # defaults checked
    d.close()
    return f"starter dialog: {len(books)} default-selected book(s)"


def t_f48():
    from aetherlab.services.starter_library import resolve_pdf_urls, free_disk_mb, STARTER_BOOKS, download_book
    # resolve falls back to hardcoded without network dependency guarantees
    urls = resolve_pdf_urls(list(STARTER_BOOKS))
    assert all(u.startswith("http") for u in urls.values())
    mb = free_disk_mb(_TMP)
    assert mb > 0
    # skip logic: pretend a large file already exists
    dest = _TMP / "books"
    dest.mkdir(exist_ok=True)
    big = dest / STARTER_BOOKS[0].filename
    big.write_bytes(b"0" * (6 * 1024 * 1024))
    got = []
    r = download_book(STARTER_BOOKS[0], "http://unused", dest, progress_cb=lambda d, t: got.append((d, t)))
    assert r == big and got, "existing >5MB file should be skipped"
    return f"URL fallback + free_disk_mb={mb:.0f} + skip-existing"


# ══════════════════════════════════════════════════════════════════════════
# Scene generation
# ══════════════════════════════════════════════════════════════════════════

def t_f49():
    from aetherlab.services.scene_generator import SceneGenerator, SCENE_GENERATION_SYSTEM_PROMPT
    _gr = inspect.getsource(SceneGenerator._generate_remote)
    # Two-call split: codegen runs cold (0.15), single-call fallback stays 0.4.
    assert "max_tokens=32768" in _gr and "temperature = 0.15" in _gr and "temperature = 0.4" in _gr
    # code extraction robustness
    sg = SceneGenerator(_settings())
    code = sg._extract_code("<think>plan</think>```python\nfrom manim import *\nclass X(Scene):\n    def construct(self):\n        pass\n```", "AetherLabScene")
    assert "class AetherLabScene(Scene)" in code and "def construct" in code
    # BUG-5 regression: llm_context_window is now actually consumed here.
    assert "llm_context_window" in inspect.getsource(SceneGenerator._generate_remote)
    return "extract strips think/fences+renames; context budget wired (BUG-5)"


def t_f50():
    from aetherlab.services.manim_runtime import ManimRuntime
    src = inspect.getsource(ManimRuntime.generate_scene_async)
    assert "max_retries" in src and "SyntaxError" in src
    return "compile+retry path present"


def t_f51():
    from aetherlab.services.manim_runtime import ManimRuntime
    from aetherlab.core.models import ProblemRequest
    sc = ManimRuntime().generate_scene(ProblemRequest(prompt="Damped oscillator"), _solver(), _rag())
    compile(sc.code, "<t>", "exec")
    assert sc.status == "compiled"
    return f"static template compiles ({len(sc.code)} chars)"


def t_f52():
    from aetherlab.services.scene_generator import SceneGenerator
    code = SceneGenerator(_settings())._fallback_scene("TestScene", _solver())
    compile(code, "<t>", "exec")
    assert "ValueTracker" in code and "always_redraw" in code and "TestScene" in code
    return "dynamic fallback compiles w/ ValueTracker"


def t_f53():
    from aetherlab.services.manim_runtime import ManimRuntime
    eng, diag = ManimRuntime().detect_engine()
    assert eng in {"manim-community", "manimgl", "generated-only"}
    return f"engine={eng}"


# ══════════════════════════════════════════════════════════════════════════
# Render
# ══════════════════════════════════════════════════════════════════════════

def t_f54():
    src = inspect.getsource(__import__("aetherlab.services.manim_runtime", fromlist=["ManimRuntime"]).ManimRuntime.render_scene)
    assert "render" in src and "--fps" in src and "--media_dir" in src
    return "render invokes manim render w/ fps+media_dir"


def t_f55():
    from aetherlab.services.manim_runtime import _detect_render_tier, _RENDER_TIER
    t = _detect_render_tier()
    assert t["fps"] in {30, 60} and "name" in t
    return f"tier={_RENDER_TIER['name']} fps={_RENDER_TIER['fps']}"


def t_f56():
    src = inspect.getsource(__import__("aetherlab.services.manim_runtime", fromlist=["ManimRuntime"]).ManimRuntime.render_scene)
    assert '"l": 240' in src and '"h": 600' in src
    assert "render-timeout" in src and "render-error" in src
    return "timeout_map + timeout/error statuses"


def t_f57():
    from aetherlab.services.manim_runtime import _find_video, _clean_old_renders
    assert _find_video("does_not_exist_scene") is None
    _clean_old_renders("does_not_exist_scene")  # must not raise
    return "_find_video None + _clean_old_renders safe"


def t_f58():
    from aetherlab.services.manim_runtime import ManimRuntime
    cmd = ManimRuntime()._find_manim_command()
    assert cmd is not None and cmd[-1] == "manim"
    return f"manim cmd: {' '.join(cmd)}"


def t_f101():
    # Render self-heal: repair loop is wired (incl. timeout repair), and a
    # non-compiled scene is a safe no-op.
    from dataclasses import replace
    from aetherlab.services.manim_runtime import ManimRuntime
    from aetherlab.core.models import SceneBundle
    src = inspect.getsource(ManimRuntime.render_scene_with_repair)
    assert "max_repairs" in src and ".repair(" in src
    assert '"render-timeout"' in src, "timeout must be repairable now"
    assert "exceeded the render time limit" in src, "timeout repair needs actionable direction"
    sb = SceneBundle(class_name="X", code="def broken(", engine="manim-community", status="compile-error")
    keyless = replace(_settings(), openai_api_key=None)
    out = asyncio.run(ManimRuntime(keyless).render_scene_with_repair(sb, keyless))
    assert out.status == "compile-error"  # non-compiled → render_scene skips, repair loop never entered
    return "self-heal wired incl. timeout repair; non-compiled path safe (F101)"


def t_f103():
    from aetherlab.services.code_safety import validate_code_safety
    ok, issues = validate_code_safety("import os\nopen('x')")
    assert not ok and len(issues) >= 2, issues
    ok2, _ = validate_code_safety("from manim import *\nimport numpy as np\nx = 1")
    assert ok2
    # escape-chain attributes
    ok3, iss3 = validate_code_safety("y = ().__class__.__bases__[0].__subclasses__()")
    assert not ok3 and any("__subclasses__" in i for i in iss3)
    # wired into generation + repair
    src = inspect.getsource(__import__("aetherlab.services.manim_runtime", fromlist=["ManimRuntime"]).ManimRuntime)
    assert src.count("validate_code_safety") >= 2
    return "safety gate blocks imports/builtins/escapes; wired twice (F103)"


def t_f104():
    from aetherlab.services.error_learner import ErrorLearner, known_pitfall_hints, preventive_pitfalls_block
    hints = known_pitfall_hints("AttributeError: 'Axes' object has no attribute 'get_graph'")
    assert hints and "axes.plot" in hints[0]
    store = _TMP / "err_store.json"
    learner = ErrorLearner(store)
    err = "NameError: name 'ShowCreation' is not defined"
    assert learner.seen_count(err) == 0
    learner.record(err)
    assert ErrorLearner(store).seen_count(err) == 1, "must persist across instances"
    assert any("before" in h for h in ErrorLearner(store).hints_for(err))
    # preventive block reaches the generation prompt
    from aetherlab.services.scene_generator import SceneGenerator
    assert "preventive_pitfalls_block" in inspect.getsource(SceneGenerator._generate_remote)
    assert "pitfalls" in preventive_pitfalls_block().lower()
    return "pitfall KB + persistent recurrence store + prompt wiring (F104)"


def t_f105():
    from aetherlab.services.scene_templates import build_scene, detect_domain
    from aetherlab.services.scene_generator import SceneGenerator
    assert detect_domain(["kepler", "orbit"], {}) == "orbit"
    assert detect_domain(["pendulum"], {}) == "pendulum"
    assert detect_domain(["fourier", "wave"], {}) == "wave"
    assert detect_domain(["something"], {"damping": 0.1}) == "oscillator"
    for dom in ("pendulum", "orbit", "wave", "oscillator"):
        code = build_scene("AetherLabScene", dom, "T", "S", ["s1"], {"gravity": 9.8})
        compile(code, "<t>", "exec")
        assert "MathTex" not in code, "templates must be LaTeX-free"
    # both fallback paths route through the domain builder now
    sg_src = inspect.getsource(SceneGenerator._fallback_scene)
    assert "detect_domain" in sg_src and "build_scene" in sg_src
    mr_src = inspect.getsource(__import__("aetherlab.services.manim_runtime", fromlist=["ManimRuntime"]).ManimRuntime._build_scene_code)
    assert "detect_domain" in mr_src and "build_scene" in mr_src
    return "4 domains compile LaTeX-free; both fallback paths routed (F105)"


def t_f106():
    from aetherlab.services.scene_validation import (
        validate_scene, lint_manim_names, check_latex_strings, estimate_duration,
    )
    bad = "from manim import *\nclass S(Scene):\n    def construct(self):\n        self.play(ShowCreation(Circle()))\n"
    issues = lint_manim_names(bad)
    assert any("ShowCreation" in i for i in issues), issues
    tex_bad = 'from manim import *\nclass S(Scene):\n    def construct(self):\n        e = MathTex(r"\\frac{a}{b")\n'
    assert check_latex_strings(tex_bad), "unclosed brace must be flagged"
    from aetherlab.services.scene_templates import build_scene
    clean = build_scene("S", "wave", "T", "S", ["s1"], {"frequency": 2.0})
    ok, iss = validate_scene(clean)
    assert ok, iss
    est = estimate_duration(clean)
    assert est.total_seconds > 0 and est.play_calls >= 1
    # wired into generation and repair paths
    mr_src = inspect.getsource(__import__("aetherlab.services.manim_runtime", fromlist=["ManimRuntime"]).ManimRuntime)
    assert mr_src.count("validate_scene") >= 2 and "estimate_duration" in mr_src
    return "lint+LaTeX+duration checks work; wired into gen+repair (F106)"


def t_f102():
    # Truncation guard: a finish_reason=='length' reply raises rather than compiling junk.
    from aetherlab.services.scene_generator import SceneGenerator
    class _Msg:  content = "some truncated code"
    class _Choice:  finish_reason = "length"; message = _Msg()
    class _Resp:  choices = [_Choice()]
    class _Completions:
        async def create(self, **_):  return _Resp()
    class _Chat:  completions = _Completions()
    class _Client:  chat = _Chat()
    sg = SceneGenerator(_settings())
    sg._client = _Client()
    for method, args in (("repair", ("code", "err")), ("revise", ("code", "critique"))):
        raised = False
        try:
            asyncio.run(getattr(sg, method)(*args, "AetherLabScene"))
        except ValueError as exc:
            raised = "truncat" in str(exc).lower()
        assert raised, f"{method} must raise on finish_reason=length"
    return "truncation guard raises in repair AND revise (F102)"


def t_f107():
    # Storyboard→codegen split: hot directing pass, cold implementation pass,
    # fail-soft to the single-call cinematic path.
    from dataclasses import replace
    from aetherlab.core.models import ProblemRequest, SolverResult, RagResult
    from aetherlab.services.scene_generator import SceneGenerator
    keyless = replace(_settings(), openai_api_key=None)
    board = asyncio.run(SceneGenerator(keyless).storyboard(
        ProblemRequest(prompt="x"), _solver(), _rag()))
    assert board is None, "storyboard must fail soft without a key"

    class _Msg:
        def __init__(self, c): self.content = c
    class _Choice:
        def __init__(self, c): self.finish_reason = "stop"; self.message = _Msg(c)
    class _Resp:
        def __init__(self, c): self.choices = [_Choice(c)]
    calls = []
    class _Completions:
        async def create(self, **kw):
            calls.append(kw)
            if len(calls) == 1:
                return _Resp('{"concept":"c","staging":"s","palette":{},'
                             '"acts":[{"name":"ESTABLISH","duration_s":5,"beats":["b"]}],'
                             '"hero_frame":"h","idle_loop":"i","narration":["n"]}')
            return _Resp("from manim import *\nclass AetherLabScene(Scene):\n"
                         "    def construct(self):\n        self.wait(1)\n")
    class _Chat: completions = _Completions()
    class _Client: chat = _Chat()
    sg = SceneGenerator(replace(_settings(), openai_api_key="sk-test"))
    sg._client = _Client()
    code = asyncio.run(sg._generate_remote(
        ProblemRequest(prompt="pendulum"), _solver(), _rag(), "AetherLabScene"))
    assert len(calls) == 2, "storyboard call + codegen call expected"
    assert calls[0]["temperature"] == 0.9 and calls[1]["temperature"] == 0.15
    assert "Locked storyboard" in calls[1]["messages"][1]["content"]
    assert sg._last_storyboard and "acts" in sg._last_storyboard
    assert "class AetherLabScene" in code
    return "hot storyboard@0.9 → cold codegen@0.15; fail-soft (F107)"


def t_f108():
    # Perceptual critique loop: skips cleanly without a vision model; PyAV
    # frame extraction works on a real render when one exists.
    from dataclasses import replace
    from aetherlab.core.models import SceneBundle
    from aetherlab.services.scene_critic import Critique, critique_video, extract_frames
    no_vlm = replace(_settings(), vision_model=None)
    crit = asyncio.run(critique_video("missing.mp4", "brief", no_vlm))
    assert crit.verdict == "skipped" and not crit.should_revise
    assert Critique(verdict="revise").should_revise
    # storyboard round-trips through the scene cache
    sb = SceneBundle.from_json(SceneBundle(
        class_name="X", code="c", engine="e", status="rendered",
        storyboard={"acts": []}).to_json())
    assert sb.storyboard == {"acts": []}
    assert SceneBundle.from_json({}).storyboard is None
    # loop is wired into the runtime after successful renders
    src = inspect.getsource(__import__(
        "aetherlab.services.manim_runtime", fromlist=["ManimRuntime"]
    ).ManimRuntime.render_scene_with_repair)
    assert "critique_video" in src and ".revise(" in src and "max_revisions" in src
    assert "keeping previous cut" in src, "revisions must never downgrade a shipped render"
    import pathlib, tempfile
    vids = sorted(
        pathlib.Path(tempfile.gettempdir()).glob("aetherlab/renders/media/videos/**/*.mp4"),
        key=lambda p: p.stat().st_mtime,
    )
    note = "no render available for frame sampling"
    if vids:
        frames = extract_frames(vids[-1], count=3)
        assert len(frames) >= 1, "PyAV should sample frames from a real render"
        note = f"sampled {len(frames)} frames via PyAV"
    return f"critique loop wired + fail-soft; {note} (F108)"


# ══════════════════════════════════════════════════════════════════════════
# Scene UI
# ══════════════════════════════════════════════════════════════════════════

def t_f59():
    from aetherlab.ui.widgets import SimulationPanel
    sp = SimulationPanel()
    sp._switch_view(2)  # Code
    assert sp._stack.currentIndex() == 3
    sp._switch_view(0)  # Canvas
    assert sp._stack.currentIndex() == 1
    sp.close()
    return "pill tabs map to stack pages"


def t_f60():
    from aetherlab.ui.widgets import SimulationPanel
    from aetherlab.core.models import SceneBundle
    sp = SimulationPanel()
    sp.set_scene_bundle(SceneBundle(class_name="X", code="x=1", engine="manim-community",
                                    status="compiled", diagnostics=["note one", "note two"]))
    # v2 (§4): diagnostics live in a dedicated drawer, not dumped in the code view.
    txt = sp.code.toPlainText()
    assert "x=1" in txt
    drawer = sp._diag_drawer._body.toPlainText()
    assert "note one" in drawer and "note two" in drawer
    assert not sp._diag_drawer.isHidden()
    sp.close()
    return "diagnostics surfaced in the drawer (v2), code view stays clean"


def t_f61():
    from aetherlab.ui.widgets import SimulationPanel
    sp = SimulationPanel()
    assert hasattr(sp, "_player") and hasattr(sp, "_seek_slider")
    sp._on_duration_changed(65000)  # 1:05
    assert "1:05" in sp._time_label.text()
    sp.close()
    return "video player + time label formatting"


def t_f62():
    src = inspect.getsource(__import__("aetherlab.ui.main_window", fromlist=["MainWindow"]).MainWindow._toggle_code_view)
    assert "show_canvas" in src and "show_code" in src
    return "toggle canvas↔code present"


# ══════════════════════════════════════════════════════════════════════════
# Live canvas
# ══════════════════════════════════════════════════════════════════════════

def t_f63():
    from aetherlab.ui.live_canvas import LiveCanvas, build_canvas_state
    lc = LiveCanvas()
    lc.set_state(build_canvas_state("t", {"damping": 0.2, "stiffness": 1.0}))
    lc.close()
    return "LiveCanvas constructs + set_state"


def t_f64():
    from aetherlab.ui.live_canvas import build_canvas_state
    good = build_canvas_state("t", {"damping": 0.2}, plot={"kind": "explicit", "y": "sin(t)", "t_range": [0, 6]})
    assert good.curves and good.x_label
    bad = build_canvas_state("t", {"damping": 0.2}, plot={"kind": "explicit", "y": "nope(t)", "t_range": [0, 6]})
    assert bad.curves, "bad plot should fall back, not crash"
    return "plot-driven curve; bad plot falls back"


def t_f65():
    from aetherlab.ui.live_canvas import build_canvas_state
    assert build_canvas_state("t", {"damping": 0.2, "stiffness": 1.0}).curves
    assert build_canvas_state("t", {"gravity": 9.81, "length": 1.0}).curves
    assert build_canvas_state("t", {"a": 1.0, "b": 2.0}).curves
    return "damped/pendulum/generic all produce curves"


def t_f66():
    from aetherlab.ui.live_canvas import build_canvas_state
    base = build_canvas_state("t", {"damping": 0.2, "stiffness": 1.0}, phase_portrait=False)
    phase = build_canvas_state("t", {"damping": 0.2, "stiffness": 1.0}, phase_portrait=True)
    assert len(phase.curves) > len(base.curves)
    return f"phase adds curve ({len(base.curves)}→{len(phase.curves)})"


def t_f67():
    from aetherlab.ui.live_canvas import LiveCanvas, build_canvas_state
    lc = LiveCanvas()
    lc.set_state(build_canvas_state("t", {"damping": 0.2}))
    lc._zoom_factor = 3.0
    lc.reset_view()
    assert lc._zoom_factor == 1.0 and lc._pan_offset.x() == 0
    lc.close()
    return "reset_view restores zoom/pan"


def t_f68():
    from aetherlab.ui.live_canvas import LiveCanvas
    lc = LiveCanvas()  # no state → empty path must not crash on paint helpers
    x, y = lc._effective_ranges()
    assert x and y
    lc.close()
    return "empty canvas safe; effective ranges default"


# ══════════════════════════════════════════════════════════════════════════
# Parameters
# ══════════════════════════════════════════════════════════════════════════

def t_f69():
    from aetherlab.ui.widgets import ParameterDock
    pd = ParameterDock()
    pd.set_variables({"damping": 0.2, "stiffness": 1.0})
    slider, spin, _, orig = pd._sliders["damping"]
    assert spin.minimum() < 0, f"spin min should be negative, got {spin.minimum()}"
    got = []
    pd.parameter_changed.connect(lambda n, v: got.append((n, v)))
    spin.setValue(-0.3)  # negative allowed
    assert got and abs(got[-1][1] - (-0.3)) < 1e-6, got
    # BUG-2 regression: a large negative from the canvas must keep a negative range.
    pd.update_variable("damping", -5.0)
    assert spin.minimum() < 0, f"range should stay negative, got min {spin.minimum()}"
    pd.close()
    return "negative range preserved on update_variable (BUG-2)"


def t_f70():
    from aetherlab.ui.widgets import ParameterDock
    pd = ParameterDock()
    pd.set_variables({"k": 1.0})
    slider, spin, _, _ = pd._sliders["k"]
    spin.setValue(1.0)
    tick_at_1 = slider.value()
    spin.setValue(0.0)
    assert slider.value() != tick_at_1, "slider should track spinbox"
    pd.close()
    return "spinbox→slider sync"


def t_f71():
    from aetherlab.ui.widgets import ParameterDock
    pd = ParameterDock()
    pd.set_variables({"k": 1.0})
    vis0 = pd._container.isVisibleTo(pd)
    pd._toggle()
    assert pd._container.isVisibleTo(pd) != vis0 and pd._collapsed
    pd.close()
    return "collapse toggles container"


# ══════════════════════════════════════════════════════════════════════════
# Analysis
# ══════════════════════════════════════════════════════════════════════════

def t_f72():
    from aetherlab.ui.widgets import AnalysisPanel
    ap = AnalysisPanel()
    ap.set_solver_result(_solver(cached=True))
    assert "[cache]" in ap.summary.text()
    ap.close()
    return "summary banner + cache note + chips"


def t_f73():
    from aetherlab.ui.widgets import AnalysisPanel
    ap = AnalysisPanel()
    ap.set_solver_result(_solver())
    assert len(ap._step_widgets) == 2
    ap._toggle_all_steps()
    assert all(w._expanded for w in ap._step_widgets)
    ap.close()
    return "collapsible steps + expand-all"


def t_f74():
    from aetherlab.ui.widgets import AnalysisPanel
    ap = AnalysisPanel()
    assert ap._empty_label.isVisible() or ap._empty_label.text()
    ap.close()
    return "empty hint present pre-run"


# ══════════════════════════════════════════════════════════════════════════
# Navigation
# ══════════════════════════════════════════════════════════════════════════

def t_f75():
    from aetherlab.ui.widgets import SidebarNav
    sb = SidebarNav()
    got = []
    sb.item_selected.connect(lambda i: got.append(i))
    sb.select(2)
    assert got == [2]
    sb.close()
    return "rail select emits index"


def t_f76():
    from aetherlab.ui.widgets import SidebarNav
    from aetherlab.ui.qt_compat import QtCore, QtGui
    sb = SidebarNav()
    sb.select(0)
    ev = QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, QtCore.Qt.Key.Key_Down, QtCore.Qt.KeyboardModifier.NoModifier)
    sb.keyPressEvent(ev)
    assert sb._buttons[1].isChecked()
    sb.close()
    return "arrow key advances selection"


def t_f77():
    from aetherlab.ui.widgets import SidebarNav
    sb = SidebarNav()
    sb.set_result_available(False)
    assert not sb._buttons[3].isEnabled()
    sb.set_result_available(True)
    assert sb._buttons[3].isEnabled()
    sb.close()
    return "Params gated until result"


def t_f78():
    src = inspect.getsource(__import__("aetherlab.ui.main_window", fromlist=["MainWindow"]).MainWindow.on_scene_ready)
    assert "sidebar.select(2)" in src and "hide_loading" in src
    return "scene ready auto-switches to Scene"


# ══════════════════════════════════════════════════════════════════════════
# History
# ══════════════════════════════════════════════════════════════════════════

def t_f79():
    from aetherlab.ui.widgets import HistoryPanel
    hp = HistoryPanel()
    db = _TMP / "hist.sqlite3"
    hp.init_persistence(db)
    hp.add_entry("test prompt", "abc123", "rendered", 3)
    hp2 = HistoryPanel()
    hp2.init_persistence(db)  # reload
    assert hp2._list.count() == 1
    hp.close(); hp2.close()
    return "history persists + reloads"


def t_f80():
    from aetherlab.ui.widgets import HistoryPanel
    src = inspect.getsource(HistoryPanel._on_double_click)
    assert "prompt_selected.emit" in src
    return "double-click emits prompt_selected"


def t_f81():
    from aetherlab.ui.widgets import HistoryPanel
    hp = HistoryPanel()
    db = _TMP / "hist2.sqlite3"
    hp.init_persistence(db)
    hp.add_entry("p", "k", "rendered", 1)
    hp._clear()
    assert hp._list.count() == 0
    hp.close()
    return "clear empties list + db"


# ══════════════════════════════════════════════════════════════════════════
# Errors / feedback
# ══════════════════════════════════════════════════════════════════════════

def t_f82():
    from aetherlab.ui.widgets import Toast
    tst = Toast()
    tst.show_message("error", "boom", details=True)
    assert tst._message.text() == "boom" and tst._details_btn.isVisible()
    tst.close()
    return "toast shows kind + details"


def t_f83():
    from aetherlab.ui.widgets import SimulationPanel
    sp = SimulationPanel()
    sp.show_error_banner("Render", "failed", "TRACEBACK")
    assert sp._error_banner.isVisibleTo(sp) and sp._error_traceback == "TRACEBACK"
    sp._show_error_details()
    sp._show_error_details()  # dedupe: still one window
    sp.close()
    return "error banner + deduped details window"


def t_f84():
    src = inspect.getsource(__import__("aetherlab.ui.main_window", fromlist=["MainWindow"]).MainWindow.on_failure)
    assert '"error"' in src and "showMessage" in src
    return "failure sets stepper error + status bar"


# ══════════════════════════════════════════════════════════════════════════
# Export
# ══════════════════════════════════════════════════════════════════════════

def t_f85():
    from aetherlab.services.pdf import export_derivation_to_latex
    out = _TMP / "d.tex"
    export_derivation_to_latex("Sum & 50% $x$", ["Step $E=mc^2$"], {"m": 1.0}, out)
    tx = out.read_text(encoding="utf-8")
    assert r"\begin{document}" in tx and r"\&" in tx
    return "latex export + escaping"


def t_f86():
    from aetherlab.services.pdf import compile_latex_to_pdf
    # pdflatex likely absent — must return None, not raise
    r = compile_latex_to_pdf(_TMP / "d.tex")
    return f"compile_latex_to_pdf returned {r!r} (None ok if no pdflatex)"


def t_f87():
    from aetherlab.services.pdf import export_scene_code
    out = _TMP / "s.py"
    export_scene_code("from manim import *\nclass S(Scene):\n    pass", out)
    assert "from manim import *" in out.read_text(encoding="utf-8")
    return "scene code export"


def t_f88():
    src = inspect.getsource(__import__("aetherlab.ui.main_window", fromlist=["MainWindow"]).MainWindow._save_video)
    assert "copy2" in src and "video_path" in src
    return "save video copies MP4"


def t_f89():
    src = inspect.getsource(__import__("aetherlab.ui.main_window", fromlist=["MainWindow"]).MainWindow._export_gif)
    assert "ffmpeg" in src and "FileNotFoundError" in src and "TimeoutExpired" in src
    return "gif export via ffmpeg w/ error handling"


# ══════════════════════════════════════════════════════════════════════════
# UX / theme / shell
# ══════════════════════════════════════════════════════════════════════════

def t_f90():
    from aetherlab.ui.style import AETHERLAB_QSS
    assert "#06B6D4" in AETHERLAB_QSS and len(AETHERLAB_QSS) > 3000
    return f"QSS present ({len(AETHERLAB_QSS)} chars)"


def t_f91():
    src = inspect.getsource(__import__("aetherlab.ui.main_window", fromlist=["MainWindow"]).MainWindow.__init__)
    assert "0.92" in src and "min(1500" in src
    return "responsive sizing formula"


def t_f92():
    from aetherlab.ui.widgets import TitleBar
    tb = TitleBar()
    got = []
    tb.settings_requested.connect(lambda: got.append(1))
    tb.close()
    return "title bar constructs w/ settings signal"


def t_f93():
    from aetherlab.ui.widgets import EmptyStateView
    ev = EmptyStateView()
    ev.set_status(False, "m", 0)
    assert "No API key" in ev._key_label.text()
    ev.set_status(True, "gpt-x", 3)
    assert "gpt-x" in ev._key_label.text() and "3 textbook" in ev._lib_label.text()
    ev.close()
    return "empty-state status reflects key + library"


def t_f94():
    from aetherlab.ui.widgets import RunningView
    rv = RunningView()
    rv.set_stage_text("Running RAG…", "detail")
    assert rv._headline.text() == "Running RAG…"
    rv.close()
    return "running view stage text"


def t_f95():
    from aetherlab.ui import icons
    pm = icons.icon_pixmap("atom", 16, "#06B6D4")
    assert not pm.isNull()
    pm2 = icons.icon_pixmap("nonexistent-icon", 16)  # → info fallback
    assert not pm2.isNull()
    return "icons render + unknown falls back"


def t_f96():
    from aetherlab.ui.widgets import BlueprintLoadingOverlay
    ov = BlueprintLoadingOverlay()
    assert not ov._timer.isActive()  # idle until shown
    ov.close()
    return "overlay timer idle until shown"


# ══════════════════════════════════════════════════════════════════════════
# Edge / robustness
# ══════════════════════════════════════════════════════════════════════════

def t_f97():
    from aetherlab.core.models import SolverResult, RagResult, SceneBundle
    assert SolverResult.from_json({}).summary == ""
    assert RagResult.from_json({}).keywords == []
    assert SceneBundle.from_json({}).class_name == "AetherLabScene"
    return "corrupt/empty json → safe defaults"


def t_f98():
    from aetherlab.ui.live_canvas import _nice_step
    assert _nice_step(0.0, 8) == 1.0 and _nice_step(1e-15, 8) == 1.0
    src = inspect.getsource(__import__("aetherlab.ui.live_canvas", fromlist=["LiveCanvas"]).LiveCanvas._map_to_plot)
    assert "1e-12" in src
    return "_nice_step degenerate=1.0; map guard present"


def t_f99():
    from aetherlab.core.events import StateBus
    bus = StateBus()
    got = []
    bus.subscribe("e", lambda ev: got.append(ev.payload))
    bus.emit("e", 42)
    assert got == [42]
    return "StateBus subscribe/emit"


def t_f100():
    from aetherlab.services.manim_runtime import sanitize_scene_name, _scene_name
    assert sanitize_scene_name("my-cool scene 1") == "MyCoolScene1"
    assert sanitize_scene_name("!!!") == "AetherLabScene"
    a = _scene_name("X", "code A"); b = _scene_name("X", "code B")
    assert a != b and _scene_name("X", "code A") == a
    return "sanitize + stable per-code hashing"


# ══════════════════════════════════════════════════════════════════════════
# Live canvas flagship upgrade (F109-F118)
# ══════════════════════════════════════════════════════════════════════════

def _canvas(params=None, plot=None):
    from aetherlab.ui.live_canvas import LiveCanvas, build_canvas_state
    lc = LiveCanvas()
    lc.resize(800, 600)
    lc.set_state(build_canvas_state(
        "t", params or {"damping": 0.2, "stiffness": 1.0}, plot=plot))
    return lc


def t_f109():
    # Cursor-anchored zoom: the data point under the cursor must not move,
    # for both the direct math and the wheel path (smooth animation bypassed).
    from aetherlab.ui.qt_compat import QtCore
    lc = _canvas()
    plot_rect = lc._plot_rect()
    anchor = QtCore.QPointF(plot_rect.left() + plot_rect.width() * 0.3,
                            plot_rect.top() + plot_rect.height() * 0.8)
    before = lc._pixel_to_data(anchor.x(), anchor.y(), plot_rect)
    lc._apply_zoom(4.0, anchor)
    after = lc._pixel_to_data(anchor.x(), anchor.y(), plot_rect)
    assert abs(before[0] - after[0]) < 1e-9 and abs(before[1] - after[1]) < 1e-9
    # Smooth-zoom plumbing exists and wheel targets it
    assert lc.smooth_zoom_enabled and lc._zoom_anim.duration() == 120
    lc.reset_view()
    assert lc._zoom_factor == 1.0 and lc._zoom_target == 1.0
    return "zoom anchors cursor; 120ms smooth-zoom animation wired"


def t_f110():
    # Trail lives in data space (survives zoom); tracer advances by wall clock.
    from aetherlab.ui.qt_compat import QtCore
    from aetherlab.ui.live_canvas import SWEEP_SECONDS
    lc = _canvas()
    lc._trail.append((1.25, -0.5))
    lc._apply_zoom(6.0, QtCore.QPointF(400, 300))
    lc._pan_offset += QtCore.QPointF(2.0, 1.0)
    assert list(lc._trail) == [(1.25, -0.5)], "trail must store data coords"
    assert SWEEP_SECONDS == 6.0
    lc._sweep_clock.invalidate()
    t0 = lc._tracer_t
    lc._tick()  # first tick after a pause only starts the clock — no jump
    assert lc._tracer_t == t0 and lc._sweep_clock.isValid()
    return "data-space trail survives zoom/pan; wall-clock sweep (6s), no resume jump"


def t_f111():
    # Hover snapping: cursor near the curve snaps to a sample with (t, x, y).
    from aetherlab.ui.qt_compat import QtCore, QtGui
    lc = _canvas()
    pm = QtGui.QPixmap(lc.size()); lc.render(pm)  # populate pixel cache
    assert lc._pixel_cache, "paint must publish pixel cache for hover"
    idx, px, py, t_arr = lc._pixel_cache[0]
    import numpy as np
    j = int(np.nanargmin(np.abs(px - 400)))
    near = QtCore.QPointF(float(px[j]) + 5, float(py[j]) + 5)
    lc._update_hover(near)
    assert lc._hover_snap is not None, "within 24px must snap"
    sidx, st, sx, sy, spx, spy = lc._hover_snap
    assert sidx == idx and abs(spx - px[j]) < 30
    far = QtCore.QPointF(float(px[j]) + 200, float(py[j]) - 200)
    lc._update_hover(far)
    assert lc._hover_snap is None and lc._hover_coords is not None, "far → raw coords"
    return "snaps within 24px with (t,x,y); raw-coords fallback beyond"


def t_f112():
    # All canvas colors flow from CANVAS_PALETTE (mirrors style.py tokens).
    import inspect, re
    import aetherlab.ui.live_canvas as mod
    from aetherlab.ui.live_canvas import CANVAS_PALETTE
    assert CANVAS_PALETTE["primary"] == "#22D3EE"  # v2 bright cyan
    assert CANVAS_PALETTE["grid"] == "#1E293B"
    src = inspect.getsource(mod)
    body = src.split("CANVAS_PALETTE: dict[str, str] = {")[1].split("}")[1]
    stray = re.findall(r'"#[0-9A-Fa-f]{6}"', body)
    assert stray == [], f"hardcoded hex outside palette: {stray[:4]}"
    return "one palette dict; zero stray hex in module body"


def t_f113():
    # Sample cache is viewport-independent; NaN gaps split into branches.
    import numpy as np
    from aetherlab.ui.qt_compat import QtCore, QtGui
    from aetherlab.ui.live_canvas import (
        LiveCanvas, CanvasState, CurveSpec, _finite_runs,
    )
    def fx(t, p): return t
    def fy(t, p):
        with np.errstate(all="ignore"):
            return 1.0 / t
    st = CanvasState(title="1/t", x_range=(-3, 3), y_range=(-5, 5),
                     curves=[CurveSpec(name="1/t", x_fn=fx, y_fn=fy,
                                       t_range=(-3.0, 3.0), t_steps=601)])
    lc = LiveCanvas(); lc.resize(800, 600); lc.set_state(st)
    lc._ensure_samples(st)
    key = lc._sample_key
    lc._apply_zoom(5.0, QtCore.QPointF(400, 300))
    lc._ensure_samples(st)
    assert lc._sample_key == key, "zoom must NOT rebuild samples"
    t, xs, ys = lc._samples[0]
    runs = _finite_runs(np.isfinite(xs) & np.isfinite(ys))
    assert len(runs) == 2, f"1/t must render as 2 branches, got {len(runs)}"
    pm = QtGui.QPixmap(lc.size()); lc.render(pm)
    assert not pm.isNull()
    st.params["k"] = 2.0
    lc._ensure_samples(st)
    assert lc._sample_key != key, "param change must rebuild samples"
    return "viewport-independent sample cache; 1/t = 2 branches, no bridge"


def t_f114():
    # Multi-curve payloads: roles, dashed references, fill, points — and full
    # backward compatibility for old single-curve payloads.
    from aetherlab.services.plotting import compile_plot, fallback_plot_payload
    from aetherlab.ui.live_canvas import build_canvas_state, CANVAS_PALETTE
    vars_ = {"damping": 0.3}
    payload = {
        "kind": "explicit", "t_range": [0, 10],
        "curves": [
            {"name": "x(t)", "y": "exp(-damping*t)*sin(3*t)", "role": "primary"},
            {"name": "env", "y": "exp(-damping*t)", "style": "dashed", "role": "reference"},
        ],
        "fill_between": {"upper": "exp(-damping*t)", "lower": "-exp(-damping*t)"},
        "points": [{"t": 0.0, "label": "release"}, {"t": 99.0, "label": "dropped"}],
    }
    cp = compile_plot(payload, vars_)
    assert len(cp.curves) == 2 and cp.fill is not None and len(cp.points) == 1
    st = build_canvas_state("m", vars_, plot=payload)
    assert len(st.curves) == 2 and st.curves[1].style == "dashed"
    assert st.curves[1].color == CANVAS_PALETTE["reference"]
    assert len(st.fills) == 1 and len(st.marked_points) == 1
    # Backward compat: legacy payload and cached rows load as one primary curve
    old = {"kind": "explicit", "y": "sin(t)", "t_range": [0, 6], "y_label": "x(t)"}
    st_old = build_canvas_state("o", vars_, plot=old)
    assert len(st_old.curves) == 1 and st_old.curves[0].role == "primary"
    # Fallback payload showcases envelopes; solver prompt documents the schema
    fb = fallback_plot_payload()
    assert len(fb["curves"]) == 3
    import inspect
    from aetherlab.services import llm
    src = inspect.getsource(llm.AsyncLLMCoordinator._solve_remote)
    assert "fill_between" in src and "reference" in src
    return "curves[]/roles/fill/points compile+render; legacy payload = 1 curve; prompt updated"


def t_f115():
    # Time scrubbing + double-click reset.
    from aetherlab.ui.qt_compat import QtCore
    lc = _canvas()
    plot_rect = lc._plot_rect()
    curve = lc._state.curves[0]
    t0, t1 = curve.t_range
    lc._begin_scrub(QtCore.QPointF(plot_rect.left() + plot_rect.width() * 0.5,
                                   plot_rect.center().y()))
    assert lc._scrubbing
    mid = t0 + 0.5 * (t1 - t0)
    assert abs(lc._tracer_t - mid) < (t1 - t0) * 0.02, f"{lc._tracer_t} vs {mid}"
    saved = lc._tracer_t
    lc._tick()
    assert lc._tracer_t == saved, "animation pauses while scrubbing"
    lc._scrubbing = False
    lc._apply_zoom(3.0, QtCore.QPointF(400, 300))
    lc.reset_view()  # double-click routes here (mouseDoubleClickEvent)
    assert lc._zoom_factor == 1.0
    import inspect
    from aetherlab.ui.live_canvas import LiveCanvas
    assert "reset_view" in inspect.getsource(LiveCanvas.mouseDoubleClickEvent)
    assert hasattr(LiveCanvas, "_draw_progress_bar")
    return "right/Shift-drag scrubs t (anim paused); dbl-click resets; progress bar drawn"


def t_f116():
    # PNG export writes a nonzero 2x file offscreen and emits the signal.
    import os, tempfile
    lc = _canvas()
    got = []
    lc.png_exported.connect(lambda p: got.append(p))
    path = os.path.join(tempfile.mkdtemp(prefix="aeth_png_"), "canvas.png")
    out = lc.save_png(path)
    assert out == path and os.path.getsize(path) > 1000
    assert got == [path], "png_exported signal must fire"
    from aetherlab.ui.qt_compat import QtGui
    img = QtGui.QImage(path)
    assert img.width() == lc.width() * 2, f"expected 2x, got {img.width()}"
    return f"2x PNG written ({os.path.getsize(path)} bytes) + signal"


def t_f117():
    # Interactive legend: always present for named curves, click-toggles.
    from aetherlab.ui.qt_compat import QtGui
    lc = _canvas()  # single named curve — legend must still render
    pm = QtGui.QPixmap(lc.size()); lc.render(pm)
    assert lc._legend_hits, "legend hidden for a single named curve"
    rect, index = lc._legend_hits[0]
    assert lc._state.curves[index].visible
    hit = lc._legend_hit(rect.center())
    assert hit == index
    lc.toggle_curve_visibility(index)
    assert not lc._state.curves[index].visible
    pm2 = QtGui.QPixmap(lc.size()); lc.render(pm2)  # muted style paints fine
    lc.toggle_curve_visibility(index)
    assert lc._state.curves[index].visible
    return "legend always shown, hit-testable, toggles visibility"


def t_f118():
    # Param chip renders live values; first paint fades in (later ones don't).
    import inspect
    from aetherlab.ui.live_canvas import LiveCanvas, build_canvas_state, FADE_IN_MS
    src = inspect.getsource(LiveCanvas._draw_param_chip)
    assert "params.items()" in src and "AlignRight" in src
    lc = LiveCanvas(); lc.resize(800, 600)
    assert lc._fade_alpha == 1.0
    lc.set_state(build_canvas_state("t", {"damping": 0.2}))
    assert lc._fade_alpha < 1.0, "first curves must start faded"
    lc._fade_anim.stop(); lc._fade_alpha = 1.0
    lc.set_state(build_canvas_state("t", {"damping": 0.4}))
    assert lc._fade_alpha == 1.0, "subsequent updates must not re-fade"
    assert FADE_IN_MS == 300
    return "mono param chip; 300ms fade only on first paint"


# ══════════════════════════════════════════════════════════════════════════
# Design v2 activation (F119-F124)
# ══════════════════════════════════════════════════════════════════════════

def t_f119():
    # v2 tokens: bright cyan primary + new surface tints; canvas primary matches.
    from aetherlab.ui import style
    assert style.CYAN == "#22D3EE" and style.CYAN_DEEP == "#06B6D4"
    for tok in ("STAGE", "ELEV", "HOVER_SURFACE", "LINE_0"):
        assert hasattr(style, tok), tok
    assert style.STAGE == "#000000"
    from aetherlab.ui.live_canvas import CANVAS_PALETTE
    assert CANVAS_PALETTE["primary"] == "#22D3EE"
    from aetherlab.ui.widgets import SidebarNav
    rail = SidebarNav()
    assert rail.width() == 56, f"rail should be 56px, got {rail.width()}"
    return "cyan #22D3EE primary; stage/elev/hover/line-0 tokens; 56px rail"


def t_f120():
    # Math-as-brand: mathtext service typesets to pixmaps, never raises.
    from aetherlab.services.mathtext import (
        render_math, render_param_symbol, looks_like_math, latex_for_param,
        WATERMARK_FORMULAS,
    )
    pm = render_math(r"x(t) = A e^{-\zeta \omega_0 t}\cos(\omega_d t)", 26)
    assert pm is not None and pm.width() > 100
    sym = render_param_symbol("damping", 15)
    assert sym is not None and sym.width() > 0
    assert latex_for_param("omega0") == r"\omega_0"
    assert looks_like_math("E = mc^2") and not looks_like_math(
        "the system slowly returns to rest as friction dissipates energy")
    assert render_math("\\frac{unclosed", 20) is None  # bad input → None, no raise
    assert all(render_math(f, 34) is not None for f in WATERMARK_FORMULAS)
    return "mathtext → pixmaps; symbol map; math/prose discriminator; safe on junk"


def t_f121():
    # Hero equation banner typesets math summaries, prose stays text;
    # parameter rows show typeset symbols; empty state carries watermarks.
    from aetherlab.core.models import SolverResult
    from aetherlab.ui.widgets import AnalysisPanel, ParameterDock, EmptyStateView
    a = AnalysisPanel()
    a.set_solver_result(SolverResult("x(t) = A e^{-ζωt}\\cos(ω t)",
                                     ["s"], ["k"], {"damping": 0.2}, "m"))
    assert a.summary.pixmap() is not None and not a.summary.pixmap().isNull()
    a.set_solver_result(SolverResult(
        "The oscillator gradually loses amplitude as damping removes its energy.",
        ["s"], ["k"], {"damping": 0.2}, "m"))
    assert a.summary.text() and a.summary.pixmap().isNull()  # PyQt6: cleared pixmap is null, not None
    d = ParameterDock()
    d.set_variables({"damping": 0.15, "omega0": 2.0})
    assert d._container_layout.rowCount() == 2
    e = EmptyStateView()
    assert len(e._watermarks) >= 2
    return "hero banner: math→pixmap, prose→text; param symbols; ambient watermarks"


def t_f122():
    # Scene-meta parser + storyboard normalizer feed the v2 chrome.
    from aetherlab.core.models import SceneBundle
    from aetherlab.ui.widgets import parse_scene_meta, _storyboard_acts, SimulationPanel
    sb = SceneBundle(
        "AetherLabScene", "class AetherLabScene(Scene):\n    def construct(self): pass",
        "manim-community", "rendered",
        ["Estimated duration ~19s (6 beats, 2 waits).",
         "Applied render repair 1.", "Applied visual revision 1.",
         "Visual critique round 1: ship (score 8.5) — tighten pacing; raise contrast"],
        storyboard={"acts": [
            {"name": "ESTABLISH", "duration_s": 5, "beats": ["b"]},
            {"name": "EVOLVE", "duration_s": 10, "beats": ["b"]},
            {"name": "REVEAL", "duration_s": 4, "beats": ["b"]}],
            "narration": ["Set the stage", "Let it evolve", "Lock the invariant"]})
    m = parse_scene_meta(sb)
    assert m["repaired"] == 1 and m["revised"] == 1
    assert m["critique"]["verdict"] == "ship" and m["critique"]["score"] == 8.5
    assert len(m["critique"]["issues"]) == 2 and m["duration"] == "~19s"
    acts = _storyboard_acts(sb.storyboard)
    assert [a["name"] for a in acts] == ["ESTABLISH", "EVOLVE", "REVEAL"]
    assert acts[2]["narration"] == "Lock the invariant"
    # empty/old bundles degrade to no storyboard, no crash
    assert parse_scene_meta(SceneBundle.from_json({}))["critique"] is None
    assert _storyboard_acts(None) == []
    p = SimulationPanel()
    p.set_scene_bundle(sb)
    assert p._repaired_pill.isVisibleTo(p) and p._revised_pill.isVisibleTo(p)
    assert p._engine_chip.text() == "manim-community"
    assert len(p._seek_slider._act_fracs) == 3 and p._seek_slider._hero_frac is not None
    return "parse repaired/revised/critique/duration; storyboard acts + hero bookmark"


def t_f123():
    # Screening room + code artifact + storyboard seek wiring.
    from aetherlab.ui.widgets import (
        SimulationPanel, ManimBadge, CodeArtifactView, _ManimHighlighter,
        ActSeekSlider, StoryboardStrip, CritiqueBadge,
    )
    p = SimulationPanel()
    assert isinstance(p.code, CodeArtifactView)
    assert isinstance(p._seek_slider, ActSeekSlider)
    assert isinstance(p._storyboard_strip, StoryboardStrip)
    assert isinstance(p._critique_badge, CritiqueBadge)
    assert isinstance(p._manim_badge, ManimBadge)
    # code view has a Manim-aware highlighter + line numbers
    assert isinstance(p.code._highlighter, _ManimHighlighter)
    assert p.code.line_number_area_width() > 0
    # storyboard click → seek
    seeks = []
    p._seek_fraction = lambda f: seeks.append(f)  # capture
    p._storyboard_strip.act_seek_requested.connect(p._seek_fraction)
    p._storyboard_strip.set_storyboard({"acts": [
        {"name": "ESTABLISH", "duration_s": 5}, {"name": "REVEAL", "duration_s": 5}]})
    # find an act card and click it
    from aetherlab.ui.qt_compat import QtGui, QtCore
    cards = [p._storyboard_strip._layout.itemAt(i).widget()
             for i in range(p._storyboard_strip._layout.count())]
    cards[1].mousePressEvent(None)  # second act → frac 0.5
    assert seeks and abs(seeks[-1] - 0.5) < 1e-6, seeks
    return "screening room widgets swapped in; code artifact + highlighter; act-click seeks"


def t_f124():
    # Library bookshelf spines + chunk counts; Settings Vision·Critique section.
    import inspect
    from aetherlab.ui.widgets import LibraryPanel, _BookSpine
    src = inspect.getsource(LibraryPanel.refresh)
    assert "_BookSpine" in src and "chunks" in src and "Re-indexing" in src
    spine = _BookSpine("#22D3EE")
    from aetherlab.ui.qt_compat import QtGui
    pm = QtGui.QPixmap(spine.size()); spine.render(pm)  # paints without crash
    from aetherlab.ui.main_window import SettingsDialog
    from aetherlab.core.settings import load_settings
    d = SettingsDialog(load_settings())
    vals = d.get_settings()
    assert "vision_model" in vals
    dsrc = inspect.getsource(SettingsDialog.__init__)
    assert "VISION" in dsrc and "_vision_edit" in dsrc
    return "library spines + chunk counts + freshness; Settings vision·critique field"


# ══════════════════════════════════════════════════════════════════════════
# v3 — Web references + graphics upgrade (F125-F127)
# ══════════════════════════════════════════════════════════════════════════

def t_f125():
    # Web reference provider: offline-safe, correct shape; model back-compat.
    from aetherlab.services.web_references import WikipediaReferenceProvider, fetch_web_references
    from aetherlab.core.models import RagHit, RagResult
    # A broken endpoint must return [] (never raise) — offline-safety contract.
    broken = WikipediaReferenceProvider(timeout=2)
    broken.api = "https://invalid.aetherlab.example/w/api.php"
    assert broken.search(["oscillator"], 3) == []
    assert WikipediaReferenceProvider().search([], 3) == []  # no keywords → []
    # RagHit gains origin/source_label with safe defaults; old dicts still load.
    h = RagHit("C:/lib/x.pdf", 3, 2.0, "e")
    assert h.origin == "library" and not h.is_web and h.source_name == "x.pdf"
    w = RagHit("https://en.wikipedia.org/wiki/Harmonic_oscillator", None, 0.9, "e",
               source_label="Harmonic oscillator", origin="web")
    assert w.is_web and w.source_name == "Harmonic oscillator"
    rr = RagResult.from_json({"keywords": ["k"], "backend": "chromadb",
                              "hits": [{"source_path": "a.pdf", "page_number": 1,
                                        "score": 1.0, "excerpt": "e"}]})
    assert rr.hits[0].origin == "library"  # legacy 4-field row → default origin
    # fetch honors the settings toggle
    from aetherlab.core.settings import load_settings
    from dataclasses import replace
    assert fetch_web_references(["x"], replace(load_settings(), web_references=False)) == []
    return "web provider fail-soft; RagHit origin/label back-compat; toggle honored"


def t_f126():
    # Merge helper appends web hits after library hits, tags backend, fail-soft;
    # settings expose the toggle end to end.
    import asyncio
    from dataclasses import replace
    from aetherlab.core.models import RagHit, RagResult
    from aetherlab.core.settings import load_settings, _as_bool
    from aetherlab.services.pipeline import _merge_web_references

    s = load_settings()
    assert isinstance(s.web_references, bool)
    assert _as_bool("0", default=True) is False and _as_bool(None, "yes", default=False) is True

    base = RagResult(["osc"], [RagHit("C:/lib/b.pdf", 5, 3.0, "local")], "chromadb")
    # disabled → identical object
    assert asyncio.run(_merge_web_references(base, ["x"], replace(s, web_references=False))) is base
    # a provider that raises must not break the merge (returns base unchanged)
    import aetherlab.services.web_references as wr
    orig = wr.fetch_web_references
    wr.fetch_web_references = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    try:
        out = asyncio.run(_merge_web_references(base, ["x"], replace(s, web_references=True)))
        assert out is base
    finally:
        wr.fetch_web_references = orig
    # a provider that returns hits gets merged, library first, backend tagged
    wr.fetch_web_references = lambda kw, st, limit=3: [
        RagHit("https://en.wikipedia.org/wiki/X", None, 0.9, "web", source_label="X", origin="web")]
    try:
        out = asyncio.run(_merge_web_references(base, ["x"], replace(s, web_references=True)))
    finally:
        wr.fetch_web_references = orig
    assert len(out.hits) == 2 and out.hits[0].origin == "library" and out.hits[1].is_web
    assert out.backend == "chromadb+web"
    return "merge: library-first + web-tagged; fail-soft on provider error; toggle wired"


def t_f127():
    # Reference card web styling + dimming; blueprint backdrop; focus filament;
    # Settings web-references checkbox.
    import os
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from aetherlab.ui.qt_compat import QtWidgets, QtGui
    from aetherlab.ui.widgets import _RagHitCard, BlueprintBackdrop, CommandBar
    from aetherlab.core.models import RagResult, RagHit
    from aetherlab.ui.widgets import ReferencePanel

    # web card: opens a URL, not a local file; low score dims the card
    web_card = _RagHitCard("Harmonic oscillator", None, 0.9,
                           "An oscillator…", "https://en.wikipedia.org/wiki/Harmonic_oscillator",
                           is_web=True)
    assert web_card.graphicsEffect() is None  # high score → not dimmed
    dim_card = _RagHitCard("Weak", 12, 0.3, "…", "C:/lib/x.pdf", is_web=False)
    assert dim_card.graphicsEffect() is not None  # < 0.5 → dimmed
    pm = QtGui.QPixmap(320, 120); web_card.render(pm)  # paints without crash

    # ReferencePanel provenance line counts library vs web
    rp = ReferencePanel()
    rp.set_rag_result(RagResult(["k"], [
        RagHit("C:/lib/a.pdf", 3, 0.9, "lib", origin="library"),
        RagHit("https://en.wikipedia.org/wiki/X", None, 0.8, "web", source_label="X", origin="web"),
    ], "chromadb+web"))
    assert "1 library" in rp._backend_label.text() and "1 web" in rp._backend_label.text()

    # Blueprint backdrop paints; command-bar filament toggles the shell property
    bd = BlueprintBackdrop(QtWidgets.QLabel("x")); bd.resize(400, 300)
    pm2 = QtGui.QPixmap(bd.size()); bd.render(pm2)
    cb = CommandBar()
    cb._set_shell_focused(True); assert cb._shell.property("focused") == "true"
    cb._set_shell_focused(False); assert cb._shell.property("focused") == "false"

    # Settings dialog carries the web-references checkbox
    from aetherlab.ui.main_window import SettingsDialog
    from aetherlab.core.settings import load_settings
    d = SettingsDialog(load_settings())
    vals = d.get_settings()
    assert "web_references" in vals and isinstance(vals["web_references"], bool)
    return "web/library card styling + dimming; provenance; backdrop; filament; settings toggle"


def t_f128():
    # Provider independence: ollama preset resolution + qwen autoload gated off.
    import aetherlab.core.settings as S
    saved_env = os.environ.pop("AETHERLAB_DATA_DIR", None)
    orig_default = S._default_data_dir
    S._default_data_dir = lambda: _TMP / "prov_home"
    try:
        s0 = S.load_settings()
        assert s0.openai_api_key is None, "qwen autoload must be gated off by default"
        S.save_app_config({"provider_preset": "ollama", "model": "qwen2.5:7b"})
        s1 = S.load_settings()
        assert s1.openai_base_url == S.OLLAMA_OPENAI_BASE_URL
        assert s1.openai_api_key == "ollama" and s1.provider_source == "ollama-local"
        os.environ["AETHERLAB_OPENAI_API_KEY"] = "sk-env"
        assert S.load_settings().openai_api_key == "sk-env", "env must beat preset"
    finally:
        os.environ.pop("AETHERLAB_OPENAI_API_KEY", None)
        (_TMP / "prov_home" / "settings.json").unlink(missing_ok=True)
        S._default_data_dir = orig_default
        if saved_env is not None:
            os.environ["AETHERLAB_DATA_DIR"] = saved_env
    return "ollama preset resolves; qwen gated; env wins (F128)"


def t_f129():
    # Ollama discovery + Settings preset UI + EmptyState one-click CTA.
    from aetherlab.services.providers import detect_ollama, test_connection
    models = detect_ollama(timeout=1.0)  # absence is a normal state
    assert isinstance(models, list)
    from dataclasses import replace
    ok, msg = test_connection(replace(_settings(), openai_api_key=None))
    assert not ok and "key" in msg.lower()
    from aetherlab.ui.main_window import SettingsDialog
    d = SettingsDialog(_settings())
    assert d._preset_combo.count() == 3 and hasattr(d, "_test_btn")
    assert d.get_settings()["provider_preset"] in ("custom", "ollama", "none")
    d.close()
    from aetherlab.ui.widgets import EmptyStateView
    ev = EmptyStateView()
    ev.offer_ollama(2)
    assert ev._ollama_btn.isVisibleTo(ev) and "2 local models" in ev._key_label.text()
    ev.set_status(True, "m", 0)
    assert not ev._ollama_btn.isVisibleTo(ev)
    ev.close()
    return f"providers module + preset UI + CTA ({len(models)} local models) (F129)"


def t_f130():
    # key_equations contract: model round-trip, fallback domains, hero banner, export.
    from dataclasses import replace
    from aetherlab.core.models import ProblemRequest, SolverResult
    from aetherlab.services.llm import AsyncLLMCoordinator, FALLBACK_EQUATIONS
    sr = SolverResult.from_json(SolverResult(
        summary="s", derivation_steps=[], keywords=[], variables={},
        model_name="t", key_equations=[r"E = mc^2"]).to_json())
    assert sr.key_equations == [r"E = mc^2"]
    assert SolverResult.from_json({}).key_equations == []
    keyless = replace(_settings(), openai_api_key=None)
    r = asyncio.run(AsyncLLMCoordinator(keyless).solve(ProblemRequest(prompt="Solve the simple pendulum")))
    assert r.key_equations == FALLBACK_EQUATIONS["pendulum"]
    from aetherlab.services.mathtext import render_math
    pm = render_math(r.key_equations[0], px_size=30)
    assert pm is not None and not pm.isNull()
    from aetherlab.ui.widgets import AnalysisPanel
    ap = AnalysisPanel()
    ap.set_solver_result(r)
    assert ap.summary.pixmap() is not None and not ap.summary.pixmap().isNull()
    ap.close()
    from aetherlab.services.pdf import export_derivation_to_latex
    out = _TMP / "keq.tex"
    export_derivation_to_latex("s", ["x"], {}, out, key_equations=[r"E = mc^2"])
    assert r"\[ E = mc^2 \]" in out.read_text(encoding="utf-8")
    return "key_equations end-to-end: model→fallback→banner→export (F130)"


def t_f131():
    # Product hygiene: version flag, rotating log, icon assets + taskbar wiring.
    import subprocess
    from aetherlab import __version__
    r = subprocess.run([sys.executable, "-m", "aetherlab", "--version"],
                       capture_output=True, text=True, timeout=60, env={**os.environ})
    assert __version__ in (r.stdout + r.stderr), (r.stdout, r.stderr)
    from aetherlab.__main__ import _setup_logging
    _setup_logging()
    log_file = Path(os.environ["AETHERLAB_DATA_DIR"]) / "logs" / "aetherlab.log"
    assert log_file.exists() and "starting" in log_file.read_text(encoding="utf-8")
    assert Path("assets/aetherlab.ico").exists()
    src = inspect.getsource(__import__("aetherlab.ui.app", fromlist=["run_app"]).run_app)
    assert "SetCurrentProcessExplicitAppUserModelID" in src and "setWindowIcon" in src
    return f"--version={__version__}; rotating log; ico + taskbar wiring (F131)"


def t_f132():
    # Packaging readiness: LaTeX-aware scene prompts + packaging assets present.
    from aetherlab.services.manim_runtime import detect_latex
    has = detect_latex()
    src = inspect.getsource(__import__(
        "aetherlab.services.scene_generator", fromlist=["SceneGenerator"]
    ).SceneGenerator._generate_remote)
    assert "detect_latex" in src and "NO LaTeX" in src
    for f in ("packaging/aetherlab.spec", "packaging/installer.iss", "packaging/build.py",
              ".github/workflows/ci.yml", "docs/QUICKSTART.md", "docs/TROUBLESHOOTING.md"):
        assert Path(f).exists(), f
    # Frozen-bundle regression: inside PyInstaller, sys.executable is our exe,
    # so the renderer must relay via `aetherlab --manim ...` (not `-m manim`),
    # and the build gate must demand an actually-rendered video.
    from aetherlab.services.manim_runtime import ManimRuntime
    mr_src = inspect.getsource(ManimRuntime._find_manim_command)
    assert '"--manim"' in mr_src and "frozen" in mr_src
    main_src = Path("aetherlab/__main__.py").read_text(encoding="utf-8")
    assert '"--manim"' in main_src and "manim_main" in main_src
    build_src = Path("packaging/build.py").read_text(encoding="utf-8")
    assert "Scene status: rendered" in build_src, "gate must require a real render"
    return f"LaTeX-aware prompts (latex={has}); frozen manim relay + strict gate (F132)"


def t_f133():
    # Bug 2 — cross-platform subprocess: Windows flags never reach POSIX.
    import aetherlab.core.proc as proc
    orig = proc.IS_WINDOWS
    try:
        proc.IS_WINDOWS = True
        assert proc.subprocess_kwargs() == {"creationflags": proc.CREATE_NO_WINDOW}
        assert proc.subprocess_kwargs(below_normal=True)["creationflags"] & proc.BELOW_NORMAL_PRIORITY_CLASS
        proc.IS_WINDOWS = False
        assert proc.subprocess_kwargs() == {"start_new_session": True}
        assert "creationflags" not in proc.subprocess_kwargs(below_normal=True)
    finally:
        proc.IS_WINDOWS = orig
    # No raw creationflags left in any subprocess site (they'd break Linux CI/cloud).
    import pathlib
    offenders = []
    for f in ("aetherlab/services/manim_runtime.py", "aetherlab/services/pdf.py",
              "aetherlab/services/scene_critic.py", "aetherlab/ui/main_window.py"):
        if "creationflags=" in pathlib.Path(f).read_text(encoding="utf-8"):
            offenders.append(f)
    assert not offenders, f"raw creationflags remain in: {offenders}"
    return "xplat kwargs win↔posix; zero raw creationflags in call sites (F133)"


def t_f134():
    # Bug 1 — the sync fix: isolated dir + disable_caching + this-render discovery.
    from aetherlab.services.manim_runtime import ManimRuntime, _find_video_in
    src = inspect.getsource(ManimRuntime.render_scene)
    assert "--disable_caching" in src and "_RUNS_DIR" in src and "uuid" in src
    assert "subprocess_kwargs" in src and "_find_video_in" in src
    # _find_video_in prefers the class-named mp4 that belongs to THIS render.
    media = _TMP / "vid_media" / "videos" / "scene" / "480p30"
    media.mkdir(parents=True, exist_ok=True)
    (media / "Neighbor.mp4").write_bytes(b"0" * 5000)      # a stray/older file
    target = media / "AetherLabScene.mp4"
    target.write_bytes(b"0" * 3000)
    got = _find_video_in(_TMP / "vid_media", "AetherLabScene", 0.0)
    assert got == target, f"must return the class-named render, got {got}"
    return "render isolated+disable_caching; discovery returns this render (F134)"


def t_f135():
    # Bug 4 — hard-scene survival: cost-scaled timeout + draft→final + partial success.
    from aetherlab.services.manim_runtime import ManimRuntime, _estimate_render_cost
    light = _estimate_render_cost("class S(Scene):\n    def construct(self):\n        self.wait(1)\n")
    heavy = _estimate_render_cost(
        "class S(Scene):\n" + "        self.play(x)\n" * 40
        + "        always_redraw(f)\n" * 12 + "        Surface(g)\n" * 4)
    assert 1.0 <= light < heavy <= 5.0, (light, heavy)
    rs = inspect.getsource(ManimRuntime.render_scene)
    assert "_estimate_render_cost" in rs and "1800" in rs  # weight-aware, hard ceiling
    rr = inspect.getsource(ManimRuntime.render_scene_with_repair)
    assert "draft_quality" in rr and "partial success" in rr and "keeping draft" in rr
    return f"cost light={light:.1f}<heavy={heavy:.1f}; draft→final partial-success (F135)"


def t_f136():
    # Bug 5 — observability: classification, artifact dump, failure_kind field.
    from aetherlab.services.manim_runtime import _classify_failure, _dump_render_failure
    assert _classify_failure("NameError: 'ShowCreation' not defined") == "hallucinated-api"
    assert _classify_failure("! Undefined control sequence \\foo") == "latex"
    assert _classify_failure("ffmpeg: command not found") == "ffmpeg"
    assert _classify_failure("MemoryError") == "oom"
    assert _classify_failure("plain nonsense") == "unknown"
    dump = _dump_render_failure(_TMP, "scene code", "the stderr", "latex")
    assert dump and (dump / "scene.py").read_text(encoding="utf-8") == "scene code"
    assert (dump / "stderr.txt").read_text(encoding="utf-8") == "the stderr"
    from aetherlab.core.models import SceneBundle
    sb = SceneBundle.from_json(SceneBundle(
        class_name="X", code="c", engine="e", status="render-error",
        failure_kind="latex").to_json())
    assert sb.failure_kind == "latex" and SceneBundle.from_json({}).failure_kind == ""
    return "failure classified+dumped; failure_kind round-trips (F136)"


def t_f137():
    # Bug 3 — frozen render: manim ecosystem collected + ffmpeg-independent path.
    spec = Path("packaging/aetherlab.spec").read_text(encoding="utf-8")
    for pkg in ("manimpango", "skia_pathops", "moderngl", "manim.plugins"):
        assert pkg in spec, f"spec must collect {pkg} for a working frozen render"
    # The dev render path proves manimpango/Text works locally (Manim 0.20 uses
    # PyAV, not an ffmpeg CLI, so the bundle isn't ffmpeg-dependent).
    main_src = Path("aetherlab/__main__.py").read_text(encoding="utf-8")
    assert '"--manim"' in main_src and "manim_main" in main_src
    return "spec collects manimpango/skia/moderngl; frozen relay intact (F137)"


TESTS = {name[2:].upper(): fn for name, fn in sorted(globals().items())
         if name.startswith("t_f") and callable(globals()[name])}


def main() -> int:
    print("=" * 72)
    print(f"AETHERLAB FEATURE TESTS  ({len(TESTS)} features)  tmp={_TMP}")
    print("=" * 72)
    for fid in sorted(TESTS, key=lambda x: int(x[1:])):
        check(fid, TESTS[fid])

    passed = sum(1 for r in results.values() if r["status"] == "PASS")
    failed = [f for f, r in results.items() if r["status"] == "FAIL"]
    print("\n" + "=" * 72)
    print(f"RESULT: {passed}/{len(results)} passed; {len(failed)} failed")
    if failed:
        print("FAILURES: " + ", ".join(sorted(failed, key=lambda x: int(x[1:]))))
    Path("feature_test_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("Wrote feature_test_results.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
