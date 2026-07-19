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
import re
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
    from aetherlab.services.llm import AsyncLLMCoordinator
    from aetherlab.core.models import ProblemRequest
    r = asyncio.run(AsyncLLMCoordinator(_settings()).solve(ProblemRequest(prompt="Solve the RLC circuit")))
    assert r.model_name == "deterministic-fallback"
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
    import dataclasses
    from aetherlab.ui.widgets import StarterLibraryDialog, LibraryPanel
    d = StarterLibraryDialog()
    books = d.selected_books()
    assert len(books) >= 1  # defaults checked
    d.close()

    # BUG-6 regression: cancelling a starter download must NOT roll into
    # indexing (that re-shows the strip Cancel just hid). Simulate a cancelled
    # worker and assert no ingest worker starts and the strip stays hidden.
    lib = _TMP / "lib47"
    st = dataclasses.replace(
        _settings(),
        library_path=lib, data_dir=lib,
        chroma_path=lib / "chroma", cache_path=lib / "cache.sqlite3",
    )
    lp = LibraryPanel()
    lp.set_settings(st)

    class _CancelledWorker:
        def isInterruptionRequested(self):
            return True

    lp._downloader = _CancelledWorker()
    lp._worker = None
    lp._on_downloads_done(1, 0)  # 1 book landed before the user cancelled
    assert lp._worker is None, "cancelled download must not auto-start indexing (BUG-6)"
    assert lp._progress_strip.isHidden(), "cancel must leave the progress strip hidden"
    lp.close()
    return f"starter dialog: {len(books)} default book(s); cancel skips auto-index (BUG-6)"


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
    gr = inspect.getsource(SceneGenerator._generate_remote)
    # Assert the *intent* (a generous output budget for reasoning models that
    # burn tokens on <think> blocks), not a brittle exact literal. The old test
    # hardcoded max_tokens=16384; the code deliberately raised it to 32768 and
    # the assertion silently rotted into a false PASS in the canonical results.
    mt = re.search(r"max_tokens=(\d+)", gr)
    assert mt and int(mt.group(1)) >= 16384, f"generous max_tokens expected, got {mt and mt.group(1)}"
    assert "temperature=0.4" in gr
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
    txt = sp.code.toPlainText()
    assert "# note one" in txt and "# note two" in txt
    sp.close()
    return "code viewer shows diagnostics prefixed with #"


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
# Redesign Phase 1 — planner + conditional outputs
# ══════════════════════════════════════════════════════════════════════════

def t_f101():
    # Planner routes a prompt to the minimal useful set of output modalities.
    from aetherlab.services.planner import Planner
    from aetherlab.core.models import ProblemRequest, LessonPlan
    p = Planner(_settings())
    concept = p.heuristic_plan(ProblemRequest(prompt="Explain what entropy is conceptually"))
    dyn = p.heuristic_plan(ProblemRequest(prompt="Simulate the damped harmonic oscillator"))
    d3 = p.heuristic_plan(ProblemRequest(prompt="Visualize the electric field of a dipole in 3D"))
    assert concept.enabled() == ["pdf"], concept.enabled()
    assert dyn.needs_numeric and dyn.needs_animation and dyn.needs_2d
    assert d3.needs_3d
    # LessonPlan round-trips through json (cache/wire safe).
    assert LessonPlan.from_json(dyn.to_json()).needs_animation
    return f"planner routes: concept={concept.enabled()} dyn={dyn.enabled()} 3d={d3.enabled()}"


def t_f102():
    # Conditional pipeline: a conceptual prompt skips scene-gen + render.
    import dataclasses
    from aetherlab.services.pipeline import AetherLabPipeline
    from aetherlab.core.models import ProblemRequest
    st = dataclasses.replace(_settings(), openai_api_key=None)  # force deterministic path
    res = asyncio.run(AetherLabPipeline(st).run(ProblemRequest(prompt="Explain what entropy is conceptually")))
    assert res.plan is not None and not res.plan.needs_animation
    assert res.scene.status == "skipped", res.scene.status
    return f"conditional pipeline: plan={res.plan.enabled()} scene={res.scene.status}"


def t_f103():
    # Planner offline fallback is deterministic and self-labels.
    import dataclasses
    from aetherlab.services.planner import Planner
    from aetherlab.core.models import ProblemRequest
    st = dataclasses.replace(_settings(), openai_api_key=None)
    p = Planner(st)
    a = asyncio.run(p.plan(ProblemRequest(prompt="Simulate a pendulum")))
    b = asyncio.run(p.plan(ProblemRequest(prompt="Simulate a pendulum")))
    assert a.model_name == "heuristic-fallback"
    assert a.to_json() == b.to_json(), "offline plan must be deterministic"
    return f"offline planner deterministic: {a.enabled()}"


def t_f104():
    # UI gates the view pills by plan: pdf-only hides Canvas + Video.
    from aetherlab.ui.widgets import SimulationPanel
    from aetherlab.core.models import LessonPlan
    sp = SimulationPanel()
    byid = {sp._pill_group.id(b): b for b in sp._pill_group.buttons()}
    sp.apply_plan(LessonPlan(needs_2d=False, needs_3d=False, needs_animation=False, needs_pdf=True))
    assert byid[0].isHidden() and byid[1].isHidden() and not byid[2].isHidden(), "pdf-only hides canvas+video"
    sp.apply_plan(LessonPlan(needs_2d=True, needs_animation=True))
    assert not byid[0].isHidden() and not byid[1].isHidden(), "animation plan shows canvas+video"
    sp.close()
    return "view pills gated by plan (canvas/video hidden for pdf-only)"


# ══════════════════════════════════════════════════════════════════════════
# Redesign Phase 2 — numeric ground truth
# ══════════════════════════════════════════════════════════════════════════

def t_f105():
    # Numeric ground truth matches the closed-form underdamped solution.
    import math
    import numpy as np
    from aetherlab.services.numeric import solve_numeric, fallback_numeric_spec
    variables = {"damping": 0.15, "stiffness": 1.0, "mass": 1.0}
    sol = solve_numeric(fallback_numeric_spec(), variables, max_points=400)
    assert sol.ok, sol.note
    t = np.array(sol.t); x = np.array(sol.series("x"))
    c = variables["damping"]; w0 = math.sqrt(variables["stiffness"] / variables["mass"])
    wd = math.sqrt(w0 * w0 - c * c)
    analytic = np.exp(-c * t) * (np.cos(wd * t) + (c / wd) * np.sin(wd * t))
    max_err = float(np.max(np.abs(x - analytic)))
    assert max_err < 1e-3, f"numeric vs analytic max_err={max_err}"
    # Unsafe / invalid RHS degrades to ok=False (never eval'd, never raises).
    bad = solve_numeric(
        {"state": ["x"], "rhs": ["__import__('os').system('x')"], "initial": [0.0], "t_range": [0, 1]}, {}
    )
    assert not bad.ok
    return f"numeric matches analytic (max_err={max_err:.2e}); unsafe rhs rejected"


def t_f106():
    # Canvas is driven by the exact numeric trajectory when a spec is present.
    import numpy as np
    from aetherlab.ui.live_canvas import build_canvas_state
    from aetherlab.services.numeric import fallback_numeric_spec
    variables = {"damping": 0.15, "stiffness": 1.0, "mass": 1.0}
    state = build_canvas_state("test", variables, plot=None, numeric_spec=fallback_numeric_spec())
    assert state.curves and state.curves[0].name == "x"
    y0 = float(np.asarray(state.curves[0].y_fn(np.array([0.0]), variables)).reshape(-1)[0])
    assert abs(y0 - 1.0) < 1e-6, f"x(0) should equal the initial condition, got {y0}"
    # Bad spec + no plot must not crash — falls through to legacy curves.
    fb = build_canvas_state("test", variables, plot=None, numeric_spec={"bad": 1})
    assert fb.curves
    return f"canvas driven by numeric (x(0)={y0:.3f}); bad spec falls back safely"


# ══════════════════════════════════════════════════════════════════════════
# Redesign Phase 3 — formal cited research PDF
# ══════════════════════════════════════════════════════════════════════════

def t_f107():
    # Formal research PDF: numeric-driven figure + RAG citations, compiled.
    from aetherlab.services.research import build_research_pdf, build_latex
    from aetherlab.services.numeric import fallback_numeric_spec
    from aetherlab.core.models import ProblemRequest, RagResult, RagHit
    solver = _solver(numeric_spec=fallback_numeric_spec())
    rag = RagResult(keywords=["oscillator"],
                    hits=[RagHit("OpenStax Vol 1.pdf", 213, 0.9, "damped oscillations")],
                    backend="test")
    req = ProblemRequest(prompt="Derive the damped harmonic oscillator")
    res = build_research_pdf(req, solver, rag, _TMP / "research107")
    assert res.tex_path.exists()
    assert res.pdf_path is not None and res.pdf_path.exists(), f"no pdf ({res.backend}): {res.note}"
    assert res.backend in {"pdflatex", "matplotlib"}
    assert res.citations == ["OpenStax Vol 1.pdf, p.213"], res.citations
    assert res.verification, "research PDF should embed physics verification checks"
    tex = build_latex(req, solver, rag, res.figure_path, verification=res.verification)
    assert "OpenStax" in tex and "includegraphics" in tex and "Derivation" in tex and "Verification" in tex
    return f"research pdf via {res.backend}, {len(res.citations)} citation(s), verified"


def t_f108():
    # pdflatex-free fallback: matplotlib renders a PDF + the numeric figure.
    from aetherlab.services.research import _matplotlib_pdf, render_numeric_figure
    from aetherlab.services.numeric import fallback_numeric_spec
    from aetherlab.core.models import ProblemRequest
    solver = _solver(numeric_spec=fallback_numeric_spec())
    out = _TMP / "research108"; out.mkdir(parents=True, exist_ok=True)
    fig = render_numeric_figure(solver, out / "fig.png")
    assert fig and fig.exists(), "numeric figure should render"
    pdf = _matplotlib_pdf(ProblemRequest(prompt="Derive the oscillator"),
                          solver, ["Ref A, p.1"], fig, out / "fallback.pdf")
    assert pdf and pdf.exists(), "matplotlib fallback PDF should be produced"
    return f"matplotlib fallback pdf ok ({pdf.stat().st_size} bytes)"


# ══════════════════════════════════════════════════════════════════════════
# Redesign Phase 4 — curated Manim component library
# ══════════════════════════════════════════════════════════════════════════

def t_f109():
    # Trajectory component composes a compilable, numeric-driven scene.
    from aetherlab.services.scene_components import compose_scene_code
    from aetherlab.services.numeric import fallback_numeric_spec
    sv = _solver(numeric_spec=fallback_numeric_spec())
    code = compose_scene_code("AetherLabScene", sv, None)
    assert code is not None
    compile(code, "<scene>", "exec")  # render-validated separately; must at least compile
    assert "class AetherLabScene(Scene)" in code and "from manim import *" in code
    assert "MoveAlongPath" in code and "set_points_smoothly" in code  # driven by real samples
    return f"trajectory component composes a compilable numeric-driven scene ({len(code)} chars)"


def t_f110():
    # 3-D surface is composed for needs_3d; nothing composes without a fit.
    from aetherlab.services.scene_components import compose_scene_code
    from aetherlab.core.models import LessonPlan
    sv = _solver()  # no numeric_spec
    code = compose_scene_code("AetherLabScene", sv, LessonPlan(needs_3d=True, needs_animation=True))
    assert code is not None and "ThreeDScene" in code
    compile(code, "<scene>", "exec")
    # No numeric + no 3-D -> None so the caller falls back to LLM/static.
    assert compose_scene_code("X", sv, LessonPlan(needs_3d=False)) is None
    return "3D surface composed for needs_3d; None otherwise"


def t_f111():
    # ManimRuntime prefers the curated component over LLM/static generation.
    import dataclasses
    from aetherlab.services.manim_runtime import ManimRuntime
    from aetherlab.services.numeric import fallback_numeric_spec
    from aetherlab.core.models import ProblemRequest
    st = dataclasses.replace(_settings(), openai_api_key=None)  # never hit the LLM in tests
    sv = _solver(numeric_spec=fallback_numeric_spec())
    bundle = asyncio.run(
        ManimRuntime(st).generate_scene_async(ProblemRequest(prompt="oscillator"), sv, _rag(), st)
    )
    assert bundle.status == "compiled", bundle.status
    assert any("curated component" in d for d in bundle.diagnostics), bundle.diagnostics
    assert "set_points_smoothly" in bundle.code
    return "ManimRuntime composes from curated library (numeric-driven, no raw LLM code)"


# ══════════════════════════════════════════════════════════════════════════
# Redesign Phase 5 — physics verifier
# ══════════════════════════════════════════════════════════════════════════

def t_f112():
    # Verifier passes a physically-correct damped oscillator.
    from aetherlab.services.verify import verify_solution
    from aetherlab.services.numeric import fallback_numeric_spec
    sv = _solver(numeric_spec=fallback_numeric_spec())
    report = verify_solution(sv)
    assert report.ok, report.summary
    names = {c.name: c.passed for c in report.checks}
    assert names.get("finite") and names.get("boundedness") and names.get("energy"), names
    return f"verifier passes physical oscillator ({report.summary})"


def t_f113():
    # Verifier catches an unphysical result (anti-damped: energy grows).
    from aetherlab.services.verify import verify_solution
    from aetherlab.core.models import SolverResult
    anti = {"state": ["x", "v"],
            "rhs": ["v", "-(stiffness/mass)*x + (2*damping)*v"],  # sign flipped -> pumps energy
            "initial": [1.0, 0.0], "t_range": [0.0, 20.0], "observe": "x"}
    sv = SolverResult(summary="anti-damped", derivation_steps=[], keywords=["oscillator"],
                      variables={"damping": 0.15, "stiffness": 1.0, "mass": 1.0},
                      model_name="t", numeric_spec=anti)
    report = verify_solution(sv)
    failed = {c.name for c in report.checks if not c.passed}
    assert "energy" in failed and "boundedness" in failed, [c.name for c in report.checks]
    return f"verifier flags unphysical growth ({report.summary})"


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
