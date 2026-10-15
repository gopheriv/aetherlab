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
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

try:  # Windows consoles default to cp1251/cp1252 and choke on arrows in notes.
    # line_buffering=True flushes every line so a HARD crash (native abort, no
    # Python traceback) still records progress in a redirected CI log — otherwise
    # block-buffering loses which test was running when the process died.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
except Exception:  # noqa: BLE001
    pass

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Isolate all state under a throwaway data dir so tests never touch real caches.
_TMP = Path(tempfile.mkdtemp(prefix="aetherlab_test_"))
os.environ["AETHERLAB_DATA_DIR"] = str(_TMP / "data")
os.environ["AETHERLAB_LIBRARY_DIR"] = str(_TMP / "lib")
os.environ["AETHERLAB_CHROMA_PATH"] = str(_TMP / "chroma")
# No real textbook scans or web calls belong in isolated feature probes.
os.environ["AETHERLAB_REFERENCE_SOURCES"] = str(_TMP / "no-references")
os.environ["AETHERLAB_WEB_REFS"] = "0"
os.environ.pop("AETHERLAB_OPENAI_API_KEY", None)
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("AETHERLAB_REVIEW_INTERVALS_DAYS", None)
# Also neutralize the ~/.qwen autoload: without this, subprocess tests (F02
# smoke) pick up a live provider key and make real LLM calls — slow and
# non-deterministic (F02 once timed out at 600s mid-suite because of it).
os.environ["QWEN_SETTINGS_PATH"] = str(_TMP / "no-qwen-settings.json")
os.environ.pop("AETHERLAB_QWEN_AUTOLOAD", None)
os.environ.pop("AETHERLAB_PROVIDER", None)
os.environ.pop("AETHERLAB_VISION_MODEL", None)
os.environ["AETHERLAB_DISABLE_LEGACY_ENV"] = "1"
for _provider_key in (
    "AETHERLAB_LLM_MODEL", "AETHERLAB_OPENAI_BASE_URL", "OPENAI_BASE_URL",
    "DASHSCOPE_API_KEY", "QWEN_API_KEY", "AETHERLAB_KIMI_API_KEY",
    "AETHERLAB_FALLBACK_OPENAI_API_KEY", "AETHERLAB_FALLBACK_OPENAI_BASE_URL",
    "AETHERLAB_FALLBACK_LLM_MODEL", "AETHERLAB_RENDER_MODE",
    "AETHERLAB_RENDER_REPO", "AETHERLAB_GITHUB_TOKEN", "GITHUB_TOKEN",
    "AETHERLAB_GITHUB_WORKFLOW", "AETHERLAB_GITHUB_BRANCH",
    "AETHERLAB_CLOUD_PROVIDER", "AETHERLAB_CLOUD_RENDER_TIMEOUT",
    "AETHERLAB_CLOUD_POLL_SECONDS",
):
    os.environ.pop(_provider_key, None)
for _compat_key in (
    "GPT_API_KEY", "DASHSCOPE_API_KEY", "GPT_BASE_URL", "LLM_BASE_URL",
    "MANIM_MODEL", "GPT_MODEL", "CHAT_MODEL", "LLM_TIMEOUT",
    "VISION_MODEL", "VISUAL_CRITIC_MAX_PASSES", "VISUAL_CRITIC_KEYFRAMES",
    "VOICEOVER_ENABLED", "TTS_ENABLED", "TTS_VOICE", "TTS_RATE",
    "CLOUD_RENDER_ENABLED", "CLOUD_RENDER_REPO", "CLOUD_RENDER_WORKFLOW",
    "CLOUD_RENDER_BRANCH", "CLOUD_RENDER_TIMEOUT", "CLOUD_RENDER_POLL",
    "AETHERLAB_LEGACY_ENV_PATH", "MANIM_BOT_ENV_PATH", "GH_TOKEN",
    "RENDER_TIER", "MANIM_FPS",
):
    os.environ.pop(_compat_key, None)


@contextmanager
def _isolated_app_config_dir(name: str):
    """Keep config-mutating feature probes inside their own temporary folder."""
    key = "AETHERLAB_DATA_DIR"
    previous = os.environ.get(key)
    os.environ[key] = str(_TMP / f"{name}_config")
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


def _assert_test_config_path(path: Path) -> Path:
    """Refuse to let a settings probe read or delete outside its test root."""
    candidate = Path(path).resolve()
    try:
        candidate.relative_to(_TMP.resolve())
    except ValueError as exc:
        raise AssertionError(f"test settings path escaped temporary root: {candidate}") from exc
    return candidate


results: dict[str, dict] = {}
_behaviour_evidence: dict[str, dict] = {}


def check(fid: str, fn) -> None:
    # Flushed pre-run marker: if a test HARD-crashes the process (native abort,
    # no catchable exception), this is the last line in the log — pinpointing it.
    print(f"  [run ] {fid} ...", flush=True)
    _behaviour_evidence.pop(fid, None)
    try:
        note = fn() or ""
        if fid in {"F12", "F13", "F14", "F15", "F17", "F19", "F20", "F84"}:
            note += "; " + _complete_command_bar_acceptance(fid)
        results[fid] = {"status": "PASS", "note": str(note), "checked_at": datetime.now(UTC).isoformat(timespec="seconds")}
        if fid in _behaviour_evidence:
            results[fid]["behaviour_acceptance_evidence"] = _behaviour_evidence.pop(fid)
        print(f"  [PASS] {fid}: {note}", flush=True)
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        results[fid] = {"status": "FAIL", "note": f"{type(exc).__name__}: {exc}"[:300], "checked_at": datetime.now(UTC).isoformat(timespec="seconds")}
        print(f"  [FAIL] {fid}: {type(exc).__name__}: {exc}", flush=True)
        print("\n".join("      " + ln for ln in tb.splitlines()[-4:]), flush=True)


def _ffmpeg_exe():
    """Locate an ffmpeg binary for the assembly tests, or None.

    Prefers a system ffmpeg (GitHub CI runners ship one), then imageio-ffmpeg's
    bundled binary (the app's OPTIONAL ``narration`` extra). Returns None when
    neither is available so callers skip render-driven assertions fail-soft —
    exactly how the app degrades without an ffmpeg (assembly/narration are
    fail-soft), and mirroring how t_f138 already skips when edge-tts is absent.
    """
    import shutil

    system = shutil.which("ffmpeg")
    if system:
        return system
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001 — optional dep; degrade to skip
        return None


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
    from aetherlab.ui import widgets as widget_facade

    assert callable(app.run_app)
    expected_widgets = {
        "AnalysisPanel", "BlueprintBackdrop", "BlueprintLoadingOverlay", "CommandBar",
        "EmptyStateView", "HistoryPanel", "LessonView", "LibraryPanel", "ParameterDock",
        "PipelineStepper", "ReferencePanel", "RunningView", "SidebarNav", "SimulationPanel",
        "TitleBar", "Toast", "EXAMPLE_PROMPTS", "StarterLibraryDialog", "parse_scene_meta",
        "_DiagnosticsDrawer",
    }
    assert expected_widgets <= set(widget_facade.__all__), expected_widgets - set(widget_facade.__all__)
    from aetherlab.ui.main_window import MainWindow
    w = MainWindow(_settings())
    ok = w.windowTitle() == "PhysLab"
    w.close()
    assert ok
    return f"MainWindow constructs; widget facade preserves {len(widget_facade.__all__)} exports"


def t_f02():
    import subprocess
    r = subprocess.run([sys.executable, "-m", "aetherlab", "--smoke", "Solve the simple pendulum"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=600, env={**os.environ})
    assert r.returncode == 0, f"exit {r.returncode}: {r.stderr[-300:]}"
    assert "smoke pipeline complete" in r.stdout.lower(), r.stdout[-300:]
    return "smoke exit 0; scene status line present"


def t_f03():
    # covered structurally: const default vs provided arg
    from aetherlab.__main__ import build_parser
    ns = build_parser().parse_args(["--smoke"])
    ns2 = build_parser().parse_args(["--smoke", "custom"])
    assert ns.smoke and ns2.smoke == "custom"
    return "nargs='?' const + explicit prompt both parse; " + _startup_story_acceptance("F03")


def t_f04():
    import hashlib
    import uuid
    import build_feature_tracker as tracker
    from tools.feature_acceptance import WATCHDOG_CASE_REQUIREMENTS, WATCHDOG_SOURCES, contract_hash

    root = Path(__file__).resolve().parent
    before = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in WATCHDOG_SOURCES}
    checks = []
    for name, requirements in WATCHDOG_CASE_REQUIREMENTS.items():
        _story_checks("test_watchdog_behaviour", (name,))
        checks.append({"id": name, "status": "PASS", "covers": sorted(requirements)})
    after = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in WATCHDOG_SOURCES}
    assert before == after, "Watchdog inputs changed during acceptance"
    tracker.apply_results({})
    row = dict(zip(tracker.HEADERS, next(row for row in tracker.FEATURES if row[0] == "F04")))
    evidence = {"schema": "physlab.story_acceptance.v1", "feature_id": "F04", "status": "PASS",
                "exit_code": 0, "completed_at": datetime.now(UTC).isoformat(),
                "contract_sha256": contract_hash(row), "source_sha256": after, "checks": checks}
    output = root / "tmp" / "feature-acceptance" / f"F04-{uuid.uuid4().hex}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    _behaviour_evidence["F04"] = {"path": output.relative_to(root).as_posix(),
                                "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}
    return "10 executed watchdog recovery checks, including real child and batch launch; source-bound complete contract evidence"


def t_f05():
    src = inspect.getsource(__import__("aetherlab.ui.qt_compat", fromlist=["require_qt"]).require_qt)
    assert "PyQt6" in src and "RuntimeError" in src
    return "require_qt raises RuntimeError w/ install hint; " + _startup_story_acceptance("F05")


def _startup_story_acceptance(feature: str) -> str:
    import uuid
    import build_feature_tracker as tracker
    from tools.accept_startup_stories import CASE_REQUIREMENTS, run_acceptance

    tracker.apply_results({})
    row = dict(zip(tracker.HEADERS, next(row for row in tracker.FEATURES if row[0] == feature)))
    output = Path(__file__).resolve().parent / "tmp" / "feature-acceptance" / f"{feature}-{uuid.uuid4().hex}.json"
    _behaviour_evidence[feature] = run_acceptance(output, row)
    return f"{len(CASE_REQUIREMENTS[feature])} fresh-process cases; complete source-bound contract evidence"


# ══════════════════════════════════════════════════════════════════════════
# Settings
# ══════════════════════════════════════════════════════════════════════════

def t_f06():
    s = _settings()
    assert s.llm_model and s.data_dir and s.cache_path
    import aetherlab.core.settings as settings_module
    keys = (
        "AETHERLAB_LLM_MODEL", "AETHERLAB_OPENAI_API_KEY", "OPENAI_API_KEY",
        "AETHERLAB_OPENAI_BASE_URL", "OPENAI_BASE_URL", "MANIM_MODEL",
        "GPT_API_KEY", "GPT_BASE_URL", "AETHERLAB_LLM_TIMEOUT", "LLM_TIMEOUT",
        "AETHERLAB_LLM_MAX_RETRIES",
        "AETHERLAB_VISUAL_CRITIC_MAX_PASSES", "VISUAL_CRITIC_MAX_PASSES",
        "AETHERLAB_VISUAL_CRITIC_KEYFRAMES", "VISUAL_CRITIC_KEYFRAMES",
        "AETHERLAB_SCENE_CANDIDATES", "AETHERLAB_SCENE_CANDIDATE_CONCURRENCY",
    )
    saved = {k: os.environ.pop(k, None) for k in keys}
    try:
        os.environ["MANIM_MODEL"] = "manim-bot-code-model"
        os.environ["GPT_API_KEY"] = "sk-gpt"
        os.environ["GPT_BASE_URL"] = "https://example.test/v1"
        os.environ["AETHERLAB_LLM_TIMEOUT"] = "17"
        os.environ["LLM_TIMEOUT"] = "77"
        os.environ["AETHERLAB_LLM_MAX_RETRIES"] = "1"
        os.environ["VISUAL_CRITIC_MAX_PASSES"] = "3"
        os.environ["VISUAL_CRITIC_KEYFRAMES"] = "4"
        os.environ["AETHERLAB_SCENE_CANDIDATES"] = "3"
        os.environ["AETHERLAB_SCENE_CANDIDATE_CONCURRENCY"] = "2"
        compat = settings_module.load_settings()
        assert compat.llm_model == "manim-bot-code-model"
        assert compat.openai_api_key == "sk-gpt"
        assert compat.openai_base_url == "https://example.test/v1"
        assert compat.llm_timeout_seconds == 17.0
        assert compat.llm_max_retries == 1
        assert compat.visual_critic_max_passes == 3 and compat.visual_critic_keyframes == 4
        assert compat.scene_candidates == 3 and compat.scene_candidate_concurrency == 2
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v

    # BUG-34: every asynchronous model client must use one bounded timeout /
    # retry policy. The SDK defaults to two retries, multiplying a slow call.
    from dataclasses import replace

    from aetherlab.services.model_policy import openai_client_kwargs

    bounded = replace(s, llm_timeout_seconds=17, llm_max_retries=1)
    assert openai_client_kwargs(bounded)["timeout"] == 17
    assert openai_client_kwargs(bounded)["max_retries"] == 1
    # Every caller gets its client from llm_client.make_client, which builds
    # both the primary and the backup client from the bounded policy.
    factory = Path("aetherlab/services/llm_client.py").read_text(encoding="utf-8")
    assert factory.count("model_policy.openai_client_kwargs(") == 2, "unbounded client in llm_client.py"
    for path in (
        "aetherlab/services/llm.py",
        "aetherlab/services/scene_generator.py",
        "aetherlab/services/scene_critic.py",
        "aetherlab/services/lesson_planner.py",
        "aetherlab/services/fact_check.py",
        "aetherlab/services/planner.py",
        "aetherlab/services/research.py",
    ):
        src = Path(path).read_text(encoding="utf-8")
        assert "make_client(" in src and "AsyncOpenAI(" not in src, f"unbounded model client in {path}"
        assert "timeout=max(" not in src, f"hidden timeout floor remains in {path}"
    return (
        f"model={s.llm_model} data_dir set timeout={s.llm_timeout_seconds}; "
        "bounded async client retries; manim-bot aliases load (BUG-34); "
        + _settings_story_acceptance("F06")
    )


def _settings_story_acceptance(feature: str) -> str:
    from tools.accept_settings_stories import DETAILS, run_acceptance

    pointers = run_acceptance(Path(__file__).resolve().parent / "tmp" / "feature-acceptance")
    _behaviour_evidence.update(pointers)
    return DETAILS[feature]


def t_f07():
    with _isolated_app_config_dir("f07"):
        return _t_f07_body()


def _t_f07_body():
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from aetherlab.core.settings import app_config_path, load_app_config, save_app_config
    save_app_config({"model": "cfg-model", "api_key": None, "base_url": "http://x"})
    cfg = load_app_config()
    assert cfg.get("model") == "cfg-model", cfg
    assert "api_key" not in cfg, "None should be dropped"
    p = _assert_test_config_path(app_config_path())
    assert p.exists()
    # BUG-45: syntactically valid JSON with the wrong top-level shape is a
    # corrupt config, not an AttributeError during application startup/save.
    p.write_text("[]", encoding="utf-8")
    assert load_app_config() == {}
    p.write_text("null", encoding="utf-8")
    save_app_config({"model": "recovered-model"})
    assert load_app_config()["model"] == "recovered-model"

    # BUG-44: fresh callers must merge concurrent settings updates rather than
    # racing direct writes and dropping keys.
    writers = 8
    gate = threading.Barrier(writers)

    def save_one(index: int) -> None:
        gate.wait(timeout=10)
        save_app_config({f"probe_{index}": str(index)})

    with ThreadPoolExecutor(max_workers=writers) as pool:
        list(pool.map(save_one, range(writers)))
    cfg = load_app_config()
    assert all(cfg.get(f"probe_{i}") == str(i) for i in range(writers)), cfg
    assert not list(p.parent.glob(f".{p.name}.*.tmp"))
    # cleanup so it doesn't taint provider-precedence test
    p.unlink()
    return (
        "atomic concurrent settings round-trip; wrong-shape JSON recovers (BUG-44/45); "
        + _story_checks("test_settings_corrupt_encoding") + "; "
        + _settings_story_acceptance("F07")
    )


def t_f08():
    from aetherlab.core.settings import app_config_path, load_settings, save_app_config
    save_app_config({"model": "cfg-model"})
    os.environ["AETHERLAB_LLM_MODEL"] = "env-model"
    s = load_settings()
    del os.environ["AETHERLAB_LLM_MODEL"]
    s2 = load_settings()
    _assert_test_config_path(app_config_path()).unlink(missing_ok=True)
    assert s.llm_model == "env-model", f"env should win, got {s.llm_model}"
    assert s2.llm_model == "cfg-model", f"config should win over default, got {s2.llm_model}"
    return "env > app-config precedence verified; " + _settings_story_acceptance("F08")


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
    return "missing→{}; parsed model/baseUrl/apiKey; " + _story_checks("test_settings_corrupt_encoding", (
        "test_invalid_utf8_opted_in_qwen_uses_defaults_without_rewriting",
    )) + "; " + _startup_story_acceptance("F09")


def t_f10():
    from aetherlab.ui.main_window import SettingsDialog
    d = SettingsDialog(_settings())
    # A standalone dialog defaults to Kazakh. Exercise the English copy
    # explicitly so localization changes cannot look like a provider defect.
    d.set_language("en")
    vals = d.get_settings()
    assert set([
        "model", "api_key", "base_url", "llm_timeout_seconds", "llm_max_retries",
        "library_path", "data_dir", "default_quality",
    ]).issubset(vals)
    assert d._provider_status.active_label.text().startswith("Active:")
    assert "API key source:" in d._provider_status.source_label.text()
    assert isinstance(d._settings_scroll, QtWidgets.QScrollArea)
    assert d._settings_scroll.widgetResizable()
    screen = QtWidgets.QApplication.primaryScreen()
    if screen:
        geo = screen.availableGeometry()
        assert d.height() <= int(geo.height() * 0.90)
        assert d.width() <= min(920, max(520, int(geo.width() * 0.68))) + 8
    d.close()
    # BUG-4 regression: Data path must persist via app-config when no env override.
    # Redirect the default data dir into _TMP so nothing touches the real config.
    import aetherlab.core.settings as settings_module
    saved_env = os.environ.pop("AETHERLAB_DATA_DIR", None)
    key_names = (
        "AETHERLAB_OPENAI_API_KEY", "OPENAI_API_KEY", "GPT_API_KEY", "DASHSCOPE_API_KEY",
    )
    saved_keys = {name: os.environ.pop(name, None) for name in key_names}
    orig_default = settings_module._default_data_dir
    settings_module._default_data_dir = lambda: _TMP / "cfghome"
    try:
        custom = _TMP / "custom_data"
        settings_module.save_app_config({
            "data_dir": str(custom), "api_key": "saved-secret",
            "model": "qwen3-coder-plus", "base_url": "https://dashscope.example/v1",
        })
        assert settings_module.load_settings().data_dir == custom, "data_dir must persist from app-config"
        os.environ["DASHSCOPE_API_KEY"] = "stale-env-secret"
        shadowed = settings_module.load_settings()
        assert shadowed.openai_api_key == "stale-env-secret"
        assert shadowed.api_key_source == "environment: DASHSCOPE_API_KEY"
        assert "DASHSCOPE_API_KEY overrides" in shadowed.provider_warning
        from aetherlab.ui.provider_status import ProviderStatusPanel
        status = ProviderStatusPanel(shadowed)
        visible = " ".join((
            status.active_label.text(), status.source_label.text(), status.warning_label.text(),
        ))
        # This owned example URL is not an actual DashScope hostname. A model
        # name must not make the UI claim a different active endpoint.
        assert "OpenAI-compatible endpoint" in visible and "DASHSCOPE_API_KEY" in visible
        assert "qwen3-coder-plus" in visible
        assert "stale-env-secret" not in visible and "saved-secret" not in visible
        status.close()
        shadow_dialog = SettingsDialog(shadowed)
        assert shadow_dialog._api_key_edit.text() == "saved-secret"
        assert "stale-env-secret" not in shadow_dialog._api_key_edit.text()
        shadow_dialog.close()
    finally:
        settings_module._default_data_dir = orig_default
        (_TMP / "cfghome" / "settings.json").unlink(missing_ok=True)
        for name, value in saved_keys.items():
            os.environ.pop(name, None)
            if value is not None:
                os.environ[name] = value
        if saved_env is not None:
            os.environ["AETHERLAB_DATA_DIR"] = saved_env
    return "settings fits; paths persist; active provider/key source + shadow warning are honest (BUG-42); " + _settings_ui_recovery_checks()


def t_f11():
    import uuid
    import build_feature_tracker as tracker
    from tools.accept_default_paths import run_acceptance

    tracker.apply_results({})
    row = dict(zip(tracker.HEADERS, next(row for row in tracker.FEATURES if row[0] == "F11")))
    output = Path(__file__).parent / "tmp/feature-acceptance" / f"F11-{uuid.uuid4().hex}.json"
    _behaviour_evidence["F11"] = run_acceptance(output, row)
    return "12 fresh-process default-path cases cover valid/invalid LOCALAPPDATA, home fallback, cache/library/Chroma and launch-folder independence; complete source-bound acceptance evidence recorded"


def _settings_ui_recovery_checks():
    import pytest

    count = 0
    for language in ("kk", "ru", "en"):
        cases = [("test_settings_save_failure_keeps_draft_and_retry_commits", {"language": language, "failure": kind})
                 for kind in ("read", "write")]
        cases += [(name, {"language": language}) for name in (
            "test_failed_settings_draft_can_be_cancelled_without_applying_it",
            "test_ollama_save_failure_keeps_provider_unchanged_and_retry_works",
        )]
        for name, arguments in cases:
            with pytest.MonkeyPatch.context() as patch:
                _explicit_practice_checks("test_settings_save_ui_recovery", [(name, {**arguments, "monkeypatch": patch})])
            count += 1
    return f"{count} isolated settings read/write refusal, draft retry/cancel and Ollama activation checks in kk/ru/en"


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
    return "submit trims+emits+clears; empty guarded; " + _command_bar_checks([
        ("test_prompt_input_routes_once_and_preserves_unicode", {"language": language, "route": route})
        for language in ("kk", "ru", "en") for route in ("return", "run", "ctrl-return")
    ] + [
        ("test_quota_storage_failure_keeps_draft_and_retry_starts_once", {"language": language})
        for language in ("kk", "ru", "en")
    ] + [(name, {}) for name in (
        "test_blank_busy_and_exhausted_quota_do_not_submit",
        "test_cancel_restores_question_for_editing",
        "test_failure_restores_question_and_stops_active_timeline",
        "test_recovery_keeps_a_newer_draft_instead_of_replacing_it",
    )])


def t_f13():
    import pytest
    from aetherlab.ui.widgets import EXAMPLE_PROMPTS, CommandBar
    assert len(EXAMPLE_PROMPTS) == 10
    cb = CommandBar()
    cb._pick_example(EXAMPLE_PROMPTS[2])
    assert cb.input.text() == EXAMPLE_PROMPTS[2]
    cb.close()
    for language in ("kk", "ru", "en"):
        with pytest.MonkeyPatch.context() as patch:
            _explicit_practice_checks("test_examples_localization", [
                ("test_examples_follow_selected_language_and_keep_identical_physics_data",
                 {"language": language, "monkeypatch": patch})
            ])
    return f"{len(EXAMPLE_PROMPTS)} examples; kk/ru/en conditions, menu selection and language switch; " + _command_bar_checks([
        ("test_examples_menu_selects_full_prompt_and_escape_preserves_input", {}),
    ])


def t_f14():
    from aetherlab.ui.widgets import CommandBar
    cb = CommandBar()
    cb.set_language("en")
    cb._quality.setCurrentText("High")
    assert cb.get_render_quality() == "h"
    cb.set_quality("m")
    assert cb.get_render_quality() == "m"
    cb.close()
    return "quality maps Draft/Standard/High→l/m/h; set_quality by flag; " + _command_bar_checks([
        ("test_quality_flags_and_missing_selection_reach_actual_worker", {"language": language})
        for language in ("kk", "ru", "en")
    ])


def t_f15():
    from aetherlab.ui.widgets import CommandBar
    cb = CommandBar()
    cb.set_busy(True)
    busy = cb.cancel_button.isVisibleTo(cb) and not cb.run_button.isVisibleTo(cb) and not cb.input.isEnabled()
    cb.set_busy(False)
    idle = cb.run_button.isVisibleTo(cb) and not cb.cancel_button.isVisibleTo(cb)
    cb.close()
    assert busy and idle
    return "Run↔Cancel swap + input disable; " + _command_bar_checks([
        ("test_cancel_remains_busy_until_worker_finished", {}),
    ] + [("test_real_qthread_cancel_waits_for_cleanup_and_preserves_draft", {"language": language, "route": "button"})
         for language in ("kk", "ru", "en")]) + "; " + _lesson_ui_checks([
        "test_real_lesson_qthread_keeps_busy_after_result_until_cleanup_finishes",
        "test_lesson_cancel_is_requested_once_and_controls_wait_for_cleanup",
    ] + [("test_lesson_terminal_keeps_controls_busy_until_finished", {"terminal": terminal})
         for terminal in ("planned", "rendered", "planning_error", "offline_practice_available",
                          "cancelled_empty", "cancelled_video", "failure")])


# ══════════════════════════════════════════════════════════════════════════
# Pipeline
# ══════════════════════════════════════════════════════════════════════════

def t_f16():
    # Run the headless pipeline end-to-end (fallback solver, no key).
    from aetherlab.core.models import ProblemRequest
    from aetherlab.services.pipeline import AetherLabPipeline
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
    return "stage transitions + reset clears timing (BUG-1); " + _command_bar_checks([
        (name, {}) for name in (
            "test_progress_stages_complete_and_next_run_resets_timing",
            "test_finished_cancellation_has_no_active_stage",
            "test_late_progress_does_not_overwrite_cancelling_state",
            "test_terminal_error_ignores_late_worker_events",
        )
    ])


def t_f18():
    import time

    from aetherlab.core.models import ProblemRequest
    from aetherlab.core.proc import ProcessCancelledError, run_process_tree
    from aetherlab.ui.workers import PipelineWorker, _PipelineCancelled
    w = PipelineWorker(ProblemRequest(prompt="x"), _settings())
    w.cancel()
    raised = False
    try:
        w._check_cancelled()
    except _PipelineCancelled:
        raised = True
    assert raised
    from aetherlab.ui.main_window import MainWindow, _PIPELINE_COPY

    cancel_src = inspect.getsource(MainWindow._cancel_pipeline)
    finished_src = inspect.getsource(MainWindow._on_worker_finished)
    assert "set_busy(False)" not in cancel_src
    assert "cancel_button.setEnabled(False)" in cancel_src
    assert "cancel_button.setEnabled(True)" in finished_src
    assert '_pipeline_message("cancelled")' in finished_src
    assert _PIPELINE_COPY["en"]["cancelled"] == "Run cancelled by user."
    assert all(_PIPELINE_COPY[language]["cancelled"] for language in ("kk", "ru", "en"))

    render_src = inspect.getsource(PipelineWorker._run_async)
    assert "cancel_check=lambda: self._cancelled" in render_src
    before = time.monotonic()
    try:
        run_process_tree(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            timeout=10,
            cancel_check=lambda: True,
            capture_output=True,
        )
        raise AssertionError("cancellable process ignored cancel_check")
    except ProcessCancelledError:
        pass
    assert time.monotonic() - before < 2.0
    return "cancel stays honest and stops an owned local process promptly (BUG-49/56); " + _command_bar_checks([
        ("test_real_qthread_cancel_waits_for_cleanup_and_preserves_draft", {"language": language, "route": route})
        for language in ("kk", "ru", "en") for route in ("button", "escape", "stepper")
    ])


def t_f19():
    src = inspect.getsource(__import__("aetherlab.ui.main_window", fromlist=["MainWindow"]).MainWindow.start_pipeline)
    assert "self._is_running()" in src and '_pipeline_message("already_running")' in src
    return "double-run guard present; " + _command_bar_checks([
        ("test_duplicate_start_preserves_worker_and_does_not_charge_again", {"language": language})
        for language in ("kk", "ru", "en")
    ])


def t_f20():
    src = inspect.getsource(__import__("aetherlab.ui.main_window", fromlist=["MainWindow"]).MainWindow.start_pipeline)
    assert "disconnect()" in src and "deleteLater()" in src
    return "old worker disconnected + deleteLater; " + _command_bar_checks([
        (name, {}) for name in (
            "test_cleanup_disconnects_all_signals_after_one_was_already_disconnected",
            "test_deleted_previous_qthread_does_not_block_a_new_run",
            "test_queued_previous_worker_signals_cannot_change_a_new_run",
            "test_all_worker_data_signals_route_once_and_stop_after_cancel",
        )
    ])


def _command_bar_checks(cases):
    """Execute the actual Qt input/lifecycle cases with owned fixture state."""
    import pytest

    for name, arguments in cases:
        with pytest.MonkeyPatch.context() as patch:
            _explicit_practice_checks("test_command_bar_behaviour", [
                (name, {**arguments, "monkeypatch": patch}),
            ])
    return f"{len(cases)} actual Qt command-bar cases (controlled pipeline; no provider/render acceptance)"


def _complete_command_bar_acceptance(feature):
    if os.name != "nt":
        return "Native Windows UI acceptance remains pending on this platform"
    if os.environ.get("PHYSLAB_RUN_NATIVE_UI_ACCEPTANCE") != "1":
        return ("Visible Windows UI acceptance not requested; "
                "set PHYSLAB_RUN_NATIVE_UI_ACCEPTANCE=1 to run it explicitly")
    import build_feature_tracker as tracker
    from tools.accept_command_bar_stories import DETAILS, run_acceptance

    rows = {row[0]: dict(zip(tracker.HEADERS, row)) for row in tracker.FEATURES}
    pointers = run_acceptance(rows)
    _behaviour_evidence[feature] = pointers[feature]
    return DETAILS[feature]


def t_f21():
    from aetherlab.ui.main_window import MainWindow
    from aetherlab.ui.qt_compat import QtGui

    class Signal:
        def __init__(self):
            self.callbacks = []

        def connect(self, callback):
            self.callbacks.append(callback)

    class LingeringWorker:
        def __init__(self):
            self.running = True
            self.cancelled = False
            self.finished = Signal()

        def isRunning(self):  # noqa: N802 - mirrors QThread's public method
            return self.running

        def cancel(self):
            self.cancelled = True

        def requestInterruption(self):  # noqa: N802 - mirrors QThread's public method
            self.cancelled = True

        def wait(self, timeout):
            assert timeout == 5000
            return False

    window = MainWindow(_settings())
    probe = getattr(window, "_ollama_probe", None)
    if probe and probe.isRunning():
        probe.wait(5000)
    window._ollama_probe = None
    lingering = LingeringWorker()
    library_lingering = LingeringWorker()

    class LibraryWorkers:
        def request_background_cancel(self):
            library_lingering.requestInterruption()

        def active_workers(self):
            return (library_lingering,) if library_lingering.running else ()

    window.worker = lingering
    window.library_panel = LibraryWorkers()
    event = QtGui.QCloseEvent()
    window.closeEvent(event)
    assert lingering.cancelled and library_lingering.cancelled and not event.isAccepted()
    assert window._close_pending and lingering.finished.callbacks
    assert library_lingering.finished.callbacks
    # Once the worker reports finished, the callback schedules a safe retry.
    lingering.running = False
    lingering.finished.callbacks[0]()
    assert window._close_pending, "one finished callback must not bypass another live worker"
    library_lingering.running = False
    library_lingering.finished.callbacks[0]()
    QtWidgets.QApplication.processEvents()
    window.worker = None
    window.close()

    src = inspect.getsource(MainWindow.closeEvent)
    assert "event.ignore()" in src and "_close_when_idle" in src and "terminate(" not in src
    return "close defers until pipeline and library QThreads finish (BUG-48/54)"


# ══════════════════════════════════════════════════════════════════════════
# Solver
# ══════════════════════════════════════════════════════════════════════════

def t_f22():
    from aetherlab.services.llm import AsyncLLMCoordinator
    assert hasattr(AsyncLLMCoordinator, "_solve_remote")
    src = inspect.getsource(AsyncLLMCoordinator._solve_remote)
    # The solver asks for 0.2; the model policy may pin it (Kimi accepts only 1).
    assert "request_temperature(self.settings, 0.2)" in src and "plot" in src
    return "remote solve path present (temp 0.2 via model policy, plot key)"


def t_f23():
    from dataclasses import replace

    from aetherlab.core.models import ProblemRequest
    from aetherlab.services.llm import AsyncLLMCoordinator
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
    return "whitelisted expr compiles + vectorizes; " + _plot_story_acceptance("F27")


def _plot_story_acceptance(feature):
    from tools.accept_plot_stories import DETAILS, run_acceptance
    pointers = run_acceptance(Path(__file__).resolve().parent / "tmp/feature-acceptance")
    _behaviour_evidence.update(pointers)
    return DETAILS[feature]


def t_f28():
    from aetherlab.services.plotting import ExprError, compile_expression
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
    return f"all {rejected} unsafe exprs rejected; ^→** works; " + _plot_story_acceptance("F28")


def t_f29():
    from aetherlab.services.plotting import ExprError, compile_plot, fallback_plot_payload
    cp = compile_plot(fallback_plot_payload(), {"damping": 0.2, "stiffness": 1.0, "mass": 1.0})
    assert cp.kind == "explicit"
    try:
        compile_plot({"kind": "bogus", "y": "t", "t_range": [0, 1]}, set())
        raise AssertionError("bad kind not rejected")
    except ExprError:
        pass
    return "fallback payload compiles; bad kind rejected; " + _plot_story_acceptance("F29")


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
    from aetherlab.core.models import ProblemRequest, RagResult, SceneBundle
    c = SessionCache(_settings().cache_path)
    req = ProblemRequest(prompt="incremental-test-xyz")
    key = c.ensure_request(req)
    c.store_solver(key, _solver())
    got = c.get(key)
    assert got.solver and got.solver.cached and got.rag is None
    c.store_rag(key, RagResult(keywords=["k"], hits=[], backend="t"))
    assert c.get(key).rag is not None
    c.store_scene(key, SceneBundle(class_name="S", code="c", engine="e", status="rendered"))
    c.clear_artifacts(key, ("scene",))
    got = c.get(key)
    assert got and got.solver and got.rag and got.scene is None
    c.clear_artifacts(key)
    got = c.get(key)
    assert got and got.solver is None and got.rag is None and got.scene is None
    # SQL-injection guard
    try:
        c._store_json(key, "evil; DROP TABLE sessions;", {})
        raise AssertionError("column not whitelisted")
    except ValueError:
        pass
    # BUG-50: an invalid SQLite file is preserved for diagnosis and replaced by
    # an empty usable cache, rather than aborting every solve at construction.
    corrupt_path = _TMP / "corrupt-session.sqlite3"
    corrupt_bytes = b"this is not a sqlite database\x00\xff"
    corrupt_path.write_bytes(corrupt_bytes)
    recovered_cache = SessionCache(corrupt_path)
    quarantined = list(_TMP.glob("corrupt-session.sqlite3.corrupt-*"))
    assert len(quarantined) == 1 and quarantined[0].read_bytes() == corrupt_bytes
    recovered_key = recovered_cache.ensure_request(ProblemRequest(prompt="after corruption"))
    assert recovered_cache.get(recovered_key) is not None
    return "stage cache independent; corrupt SQLite quarantined and rebuilt (BUG-50/51)"


def t_f32():
    from dataclasses import replace

    from aetherlab.services.pipeline import AetherLabPipeline
    p = AetherLabPipeline(_settings())
    fb = _solver(model_name="deterministic-fallback")
    # with key present, fallback is not usable
    p.settings = replace(p.settings, openai_api_key="sk-x")
    assert p._solver_cache_usable(fb) is False
    other = _solver(model_name="some-other-model")
    assert p._solver_cache_usable(other) is False
    return "fallback+key rejected; wrong model rejected"


def t_f33():
    from aetherlab.core.cache import SessionCache
    from aetherlab.core.models import ProblemRequest

    pipeline_mod = __import__("aetherlab.services.pipeline", fromlist=["AetherLabPipeline"])
    src = inspect.getsource(pipeline_mod.AetherLabPipeline.run)
    assert "engine != current_engine" in src and "compiled" in src
    assert (
        "Cached rendered video missing; re-rendering." in src
        and 'invalidate_rendered_media(scene' in src
    )

    # BUG-45: one malformed JSON artifact in SQLite is a cache miss for that
    # field, not a crash that discards the independently valid solver result.
    cache = SessionCache(_TMP / "malformed_rows.sqlite3")
    key = cache.ensure_request(ProblemRequest(prompt="malformed cache row"))
    with cache._transaction() as connection:
        connection.execute(
            "UPDATE sessions SET parameters_json=?, solver_json=?, rag_json=?, scene_json=? "
            "WHERE key=?",
            (
                "null",
                json.dumps(_solver().to_json()),
                '{"hits":[7]}',
                "[]",
                key,
            ),
        )
    recovered = cache.get(key)
    assert recovered is not None and recovered.solver is not None
    assert recovered.parameters_json == {} and recovered.rag is None and recovered.scene is None
    return "cache reuses valid fields; stale videos and malformed JSON artifacts become misses (BUG-45); " + _render_cache_checks()


def t_f34():
    from aetherlab.core.models import SceneBundle
    from aetherlab.services.pipeline import _video_exists
    from aetherlab.ui.workers import _scene_cache_usable

    assert _video_exists("") is False
    assert _video_exists(str(_TMP / "nope.mp4")) is False
    empty = _TMP / "empty.mp4"
    empty.write_bytes(b"")
    assert _video_exists(str(empty)) is False
    fake = _TMP / "fake.mp4"
    fake.write_text("not a playable video", encoding="utf-8")
    assert _video_exists(str(fake)) is False
    scene = SceneBundle("s", "code", "engine", "rendered", video_path=str(fake))
    assert _scene_cache_usable(scene, _settings()) is False
    return "_video_exists guards empty/missing/unplayable; UI worker rejects bad video cache"


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
    from aetherlab.core.models import RagHit
    from aetherlab.ui.widgets import ReferencePanel
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
    source = lib / "ingest_me.txt"
    source.write_text("kinematics energy momentum. " * 420, encoding="utf-8")
    ing = LibraryIngestor(_settings())
    n1 = ing.ingest(reset=True)
    n2 = ing.ingest()  # nothing new
    assert n1 > 0 and n2 == 0, (n1, n2)
    source.write_text("replacement-only tiny note.", encoding="utf-8")
    n3 = ing.ingest()
    import chromadb
    client = chromadb.PersistentClient(path=str(_settings().chroma_path))
    collection = client.get_collection("textbooks")
    source_chunks = collection.get(where={"path": str(source)}, include=[])
    assert len(source_chunks.get("ids", [])) == 1, "changed file must delete stale old chunks"
    assert n3 == 1, n3
    return f"ingest upserted {n1}; re-run 0; stale chunks purged on change"


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

    class Worker:
        def __init__(self):
            self.interrupted = False

        def isRunning(self):  # noqa: N802 - mirrors QThread's public method
            return True

        def requestInterruption(self):  # noqa: N802 - mirrors QThread's public method
            self.interrupted = True

    panel = LibraryPanel()
    panel._worker = Worker()
    panel._downloader = Worker()
    assert len(panel.active_workers()) == 2
    panel.request_background_cancel()
    assert panel._worker.interrupted and panel._downloader.interrupted
    cancel_src = inspect.getsource(LibraryPanel._cancel_work)
    assert "request_background_cancel(update_ui=True)" in cancel_src
    panel._worker = None
    panel._downloader = None
    panel.close()
    return "index/download workers join app close barrier; cancel remains pending (BUG-54)"


def t_f47():
    from aetherlab.ui.widgets import LibraryPanel, StarterLibraryDialog

    d = StarterLibraryDialog()
    books = d.selected_books()
    assert len(books) >= 1  # defaults checked
    d.close()
    done_src = inspect.getsource(LibraryPanel._on_downloads_done)
    assert "isInterruptionRequested" in done_src
    assert done_src.index("if cancelled:") < done_src.index("_start_ingest(reset=False)")
    return f"starter dialog + cancel-safe completion: {len(books)} defaults (BUG-54)"


def t_f48():
    from aetherlab.services.starter_library import (
        STARTER_BOOKS,
        download_book,
        free_disk_mb,
        resolve_pdf_urls,
    )
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
    return "URL fallback + positive free_disk_mb + skip-existing"


# ══════════════════════════════════════════════════════════════════════════
# Scene generation
# ══════════════════════════════════════════════════════════════════════════

def t_f49():
    from aetherlab.services.scene_generator import SceneGenerator
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
    from aetherlab.core.models import ProblemRequest
    from aetherlab.services.manim_runtime import ManimRuntime
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
    from pathlib import Path

    from aetherlab.core.models import SceneBundle
    from aetherlab.services.manim_runtime import ManimRuntime, _manim_render_command

    src = inspect.getsource(ManimRuntime.render_scene)
    assert "_manim_render_command(" in src
    command = _manim_render_command(
        ["python", "-m", "manim"], quality="l", fps=30, seed=7,
        media_dir=Path("media"), scene_file=Path("scene.py"), class_name="Scene",
    )
    assert "render" in command and "--fps" in command and "--media_dir" in command
    settings = _settings()
    scene = SceneBundle(
        class_name="AetherLabScene",
        code=(
            "from manim import *\n"
            "class AetherLabScene(Scene):\n"
            "    def construct(self):\n"
            "        dot = Dot(color=BLUE)\n"
            "        self.play(FadeIn(dot), run_time=0.25)\n"
            "        self.wait(0.25)\n"
        ),
        engine="manim-community",
        status="compiled",
    )
    rendered = ManimRuntime(settings).render_scene(scene, settings, quality="l")
    assert rendered.status == "rendered", rendered.diagnostics
    assert rendered.video_path and Path(rendered.video_path).is_file(), rendered.video_path
    return f"local Manim command flags verified; real render produced {Path(rendered.video_path).stat().st_size} bytes"


def t_f55():
    return _story_checks("test_render_profile", (
        "test_runtime_tier_refreshes_and_preserves_legacy_constrained_limits",
        "test_runtime_hardware_changes_priority_without_raising_quality",
    ))


def t_f56():
    import subprocess
    import time

    from aetherlab.core.proc import run_process_tree, subprocess_kwargs

    src = inspect.getsource(__import__("aetherlab.services.manim_runtime", fromlist=["ManimRuntime"]).ManimRuntime.render_scene)
    assert '"l": 240' in src and '"h": 600' in src
    assert "render-timeout" in src and "render-error" in src
    assert "run_process_tree" in src

    # BUG-55: a timeout must kill the grandchild too, not just the immediate
    # Python parent. The delayed marker makes an orphan observable cross-platform.
    marker = _TMP / "orphan-grandchild.txt"
    child = (
        "import time; from pathlib import Path; time.sleep(0.8); "
        f"Path({str(marker)!r}).write_text('orphan', encoding='utf-8')"
    )
    parent = (
        "import subprocess, sys, time; "
        f"subprocess.Popen([sys.executable, '-c', {child!r}]); time.sleep(10)"
    )
    try:
        run_process_tree(
            [sys.executable, "-c", parent],
            timeout=0.2,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            **subprocess_kwargs(),
        )
        raise AssertionError("process-tree timeout did not fire")
    except subprocess.TimeoutExpired:
        pass
    time.sleep(1.0)
    assert not marker.exists(), "timed-out grandchild survived and wrote its marker"
    return "quality timeout statuses + whole process-tree termination (BUG-55)"


def t_f57():
    from aetherlab.services.manim_runtime import _clean_old_renders, _find_video
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

    from aetherlab.core.models import SceneBundle
    from aetherlab.services.manim_runtime import ManimRuntime
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
    # string-based escape helpers (getattr + __builtins__/dunder strings) used
    # to bypass the previous gate because they do not appear as ast.Attribute.
    for payload in (
        "getattr(__builtins__, 'open')('x','w')",
        "getattr(type, '__subclasses__')(type)",
        "().__getattribute__('__class__')",
    ):
        ok, bypass_issues = validate_code_safety(payload)
        assert not ok, (payload, bypass_issues)
    # BUG-28: numpy is allowed, but its file-I/O surface is an arbitrary host
    # read/write (RCE via a Startup-folder write). These sinks must be blocked
    # while legitimate numpy math stays allowed.
    for payload in (
        "import numpy as np\nnp.frombuffer(b'x', dtype=np.uint8).tofile('e.bat')\n",
        "import numpy\nnumpy.savetxt('x.bat', numpy.array([1]))\n",
        "import numpy\nnumpy.load('x.npy', allow_pickle=True)\n",
        "import numpy as np\nnp.array([1]).dump('x.pickle')\n",
        "import numpy\nnumpy.lib.npyio.DataSource('.').open('http://evil/x')\n",
    ):
        ok, io_issues = validate_code_safety(payload)
        assert not ok, ("numpy IO not blocked", payload, io_issues)
    assert validate_code_safety("import numpy as np\ny = np.sin(np.array([1.0])) * np.pi\n")[0]
    # wired into generation + repair
    src = inspect.getsource(__import__("aetherlab.services.manim_runtime", fromlist=["ManimRuntime"]).ManimRuntime)
    assert src.count("validate_code_safety") >= 2
    return "safety gate blocks imports/builtins/direct+string dunder escapes; wired twice (F103)"


def t_f104():
    from aetherlab.services.error_learner import (
        ErrorLearner,
        known_pitfall_hints,
        preventive_pitfalls_block,
    )
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
    from aetherlab.services.scene_generator import SceneGenerator
    from aetherlab.services.scene_templates import build_scene, detect_domain
    assert detect_domain(["kepler", "orbit"], {}) == "orbit"
    assert detect_domain(["pendulum"], {}) == "pendulum"
    assert detect_domain(["fourier", "wave"], {}) == "wave"
    assert detect_domain(["electric", "dipole", "field"], {}) == "em_field"
    assert detect_domain(["something"], {"damping": 0.1}) == "oscillator"
    for dom in ("pendulum", "orbit", "em_field", "wave", "oscillator"):
        code = build_scene("AetherLabScene", dom, "T", "S", ["s1"], {"gravity": 9.8})
        compile(code, "<t>", "exec")
        assert "MathTex" not in code, "templates must be LaTeX-free"
        if dom == "em_field":
            assert "field lines" in code and "plus_pos" in code and "minus_pos" in code
    # both fallback paths route through the domain builder now
    sg_src = inspect.getsource(SceneGenerator._fallback_scene)
    assert "detect_domain" in sg_src and "build_scene" in sg_src
    mr_src = inspect.getsource(__import__("aetherlab.services.manim_runtime", fromlist=["ManimRuntime"]).ManimRuntime._build_scene_code)
    assert "detect_domain" in mr_src and "build_scene" in mr_src
    return "5 domains compile LaTeX-free; both fallback paths routed (F105)"


def t_f106():
    from aetherlab.services.scene_validation import (
        _has_cleanup_between,
        check_latex_strings,
        estimate_duration,
        frame_rebuild_issues,
        lint_constructor_kwargs,
        lint_manim_names,
        motion_contract_issues,
        repair_unknown_color_constants,
        scene_hygiene_warnings,
        validate_scene,
    )
    assert _has_cleanup_between(
        ["axes.move_to(ORIGIN)", "self.play(Transform(axes, new_axes))", "new_axes.move_to(ORIGIN)"],
        1, 3, "axes",
    ), "Transform(source, target) replaces the source object during a layout move"
    intentional_transform = '''from manim import *
import numpy as np
class S(Scene):
    def construct(self):
        axes = Axes().move_to(np.array([0.0, 0.0, 0.0]))
        # BEAT A1.B1 | 0.00-2.00 s
        target_axes = Axes().move_to(np.array([0.0, 0.0, 0.0]))
        self.play(Transform(axes, target_axes))
'''
    assert not any(
        issue.startswith("[HYGIENE:OVERLAP]")
        for issue in scene_hygiene_warnings(intentional_transform)
    )
    bad = "from manim import *\nclass S(Scene):\n    def construct(self):\n        self.play(ShowCreation(Circle()))\n"
    issues = lint_manim_names(bad)
    assert any("ShowCreation" in i for i in issues), issues
    # BUG-101: forwarded Manim **kwargs still reach a strict base Mobject
    # constructor; reject invented names but keep real TracedPath styling args.
    bad_traced_path = "trail = TracedPath(lambda: ORIGIN, time_traced=1.2)"
    good_traced_path = (
        "trail = TracedPath(lambda: ORIGIN, dissipating_time=1.2, "
        "stroke_opacity=0.7, color=AMBER)"
    )
    assert any(
        "invalid keyword 'time_traced'" in issue
        for issue in lint_constructor_kwargs(bad_traced_path)
    )
    assert not lint_constructor_kwargs(good_traced_path)
    tex_bad = 'from manim import *\nclass S(Scene):\n    def construct(self):\n        e = MathTex(r"\\frac{a}{b")\n'
    assert check_latex_strings(tex_bad), "unclosed brace must be flagged"
    # BUG-64: Tex-family construction in a per-frame callback can turn a
    # 20-second scene into a 14-minute timeout. Static formulas and live
    # DecimalNumber readouts remain valid.
    tex_redraw = (
        "from manim import *\nclass S(Scene):\n    def construct(self):\n"
        "        t=ValueTracker(0)\n"
        "        x=always_redraw(lambda: MathTex(f'{t.get_value():.1f}'))\n"
        "        self.play(t.animate.set_value(1))\n"
    )
    named_updater = (
        "from manim import *\nclass S(Scene):\n    def construct(self):\n"
        "        x=MathTex('x')\n"
        "        def update(m): m.become(Tex('slow'))\n"
        "        x.add_updater(update)\n        self.play(x.animate.shift(RIGHT))\n"
    )
    assert "TEX_PER_FRAME" in frame_rebuild_issues(tex_redraw)[0]
    assert "TEX_PER_FRAME" in frame_rebuild_issues(named_updater)[0]
    safe_live_number = (
        "from manim import *\nclass S(Scene):\n    def construct(self):\n"
        "        formula=MathTex('x=1')\n        value=DecimalNumber(0)\n"
        "        value.add_updater(lambda m: m.set_value(1))\n"
        "        self.play(value.animate.shift(RIGHT))\n"
    )
    assert not frame_rebuild_issues(safe_live_number)
    assert not validate_scene(tex_redraw, require_motion=True)[0]
    tex_missing_denominator = (
        'from manim import *\nclass S(Scene):\n'
        '    def construct(self):\n        e = MathTex(r"\\dfrac{a}")\n'
    )
    assert any("argument 2" in issue for issue in check_latex_strings(tex_missing_denominator))
    tex_valid_fraction = (
        'from manim import *\nclass S(Scene):\n'
        '    def construct(self):\n        e = MathTex(r"\\dfrac{a}{b}")\n'
    )
    assert not check_latex_strings(tex_valid_fraction)
    messy = """from manim import *
class S(Scene):
    def construct(self):
        a = Text("A").move_to(ORIGIN)
        b = Text("B").move_to(ORIGIN)
        c = a.copy()
        plane = NumberPlane()
        self.play(Write(a), Write(b), FadeIn(c), Create(plane))
        self.clear()
"""
    hygiene = scene_hygiene_warnings(messy)
    assert any("HYGIENE:OVERLAP" in i for i in hygiene), hygiene
    assert any("HYGIENE:STALE_COPY" in i for i in hygiene), hygiene
    assert any("HYGIENE:GRID" in i for i in hygiene), hygiene
    assert any("HYGIENE:CLEAR" in i for i in hygiene), hygiene
    from aetherlab.services.scene_templates import build_scene
    clean = build_scene("S", "wave", "T", "S", ["s1"], {"frequency": 2.0})
    ok, iss = validate_scene(clean)
    assert ok, iss
    # BUG-40: token-aware repair maps invented color-like names without
    # touching string content or identifiers the scene defines itself.
    invented = '''from manim import *
class AetherLabScene(Scene):
    def construct(self):
        label = Text("GREEN_SCREEN / BROWN")
        a = Dot(color=GREEN_SCREEN)
        b = Dot(color=BROWN)
        self.play(a.animate.shift(RIGHT), b.animate.shift(LEFT))
'''
    fixed, replacements = repair_unknown_color_constants(invented)
    assert replacements == {"GREEN_SCREEN": "GREEN", "BROWN": "DARK_BROWN"}, replacements
    assert 'Text("GREEN_SCREEN / BROWN")' in fixed
    assert not lint_manim_names(fixed), lint_manim_names(fixed)
    compile(fixed, "<fixed-colors>", "exec")

    # BUG-41: remote scene gates reject no-motion and reveal-only title cards,
    # while actual object evolution passes.
    no_motion = "from manim import *\nclass S(Scene):\n    def construct(self):\n        self.add(Dot())\n"
    reveal_only = "from manim import *\nclass S(Scene):\n    def construct(self):\n        self.play(FadeIn(Dot()))\n"
    moving = "from manim import *\nclass S(Scene):\n    def construct(self):\n        d=Dot()\n        self.play(d.animate.shift(RIGHT))\n"
    assert motion_contract_issues(no_motion) and motion_contract_issues(reveal_only)
    assert not motion_contract_issues(moving)
    assert not validate_scene(reveal_only, require_motion=True)[0]
    assert validate_scene(moving, require_motion=True)[0]

    from aetherlab.services.scene_generator import (
        SCENE_CODEGEN_SYSTEM_PROMPT,
        SCENE_GENERATION_SYSTEM_PROMPT,
        SceneGenerator,
    )
    extracted = SceneGenerator(_settings())._extract_code(invented, "AetherLabScene")
    assert "GREEN_SCREEN / BROWN" in extracted and "color=GREEN_SCREEN" not in extracted
    prompt = (SCENE_GENERATION_SYSTEM_PROMPT + SCENE_CODEGEN_SYSTEM_PROMPT).lower()
    assert "allowed global colors" in prompt and "final three sampled frames" in prompt
    assert "every requested" in prompt and "noun by noun" in prompt
    assert "five acts" in prompt and "requested total duration" in prompt
    from aetherlab.services.manim_runtime import _duration_contract_delta
    assert _duration_contract_delta(27, 30) == 0
    assert _duration_contract_delta(23, 30) > 0
    assert _duration_contract_delta(37, 30) > 0
    assert _duration_contract_delta(45, 45) == 0
    est = estimate_duration(clean)
    assert est.total_seconds > 0 and est.play_calls >= 1
    # wired into generation and repair paths
    mr_src = inspect.getsource(__import__("aetherlab.services.manim_runtime", fromlist=["ManimRuntime"]).ManimRuntime)
    assert mr_src.count("validate_scene") >= 2 and "estimate_duration" in mr_src
    assert "scene_hygiene_warnings" in mr_src
    return (
        "lint+forwarded-kwargs+LaTeX+per-frame-Tex+color repair+motion contract+hygiene wired "
        "(BUG-40/41/64/101, F106)"
    )


def t_f102():
    # Truncation guard: a finish_reason=='length' reply raises rather than compiling junk.
    from aetherlab.services.scene_generator import SceneGenerator

    class _Msg:
        content = "some truncated code"

    class _Choice:
        finish_reason = "length"
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    class _Completions:
        async def create(self, **_):
            return _Resp()

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

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

    from aetherlab.core.models import ProblemRequest
    from aetherlab.services.scene_generator import (
        SceneGenerator,
        schedule_storyboard_timeline,
    )
    from aetherlab.services.scene_validation import check_timeline_markers

    timed = schedule_storyboard_timeline({
        "acts": [
            {"name": "EVOLVE", "duration_s": 8, "beats": [
                {"detail": "temperature rises", "duration_s": 2,
                 "narration_cue": "hotter", "anchor_cell": "B2"},
                {"detail": "peak shifts", "duration_s": 6,
                 "narration_cue": "shorter wavelength", "anchor_cell": "E3"},
            ]},
            {"name": "REVEAL", "duration_s": 4, "beats": ["quantized steps"]},
        ],
        "narration": ["Heat the object", "Energy comes in quanta"],
    }, 12)
    events = timed["timeline"]
    assert [(e["start_s"], e["end_s"]) for e in events] == [(0.0, 2.0), (2.0, 8.0), (8.0, 12.0)]
    marker_code = "\n".join(
        f"# BEAT {e['id']} | {e['start_s']:.2f}-{e['end_s']:.2f} s" for e in events
    )
    assert not check_timeline_markers(marker_code, events)
    assert check_timeline_markers(marker_code.splitlines()[1], events)

    keyless = replace(_settings(), openai_api_key=None)
    board = asyncio.run(SceneGenerator(keyless).storyboard(
        ProblemRequest(prompt="x"), _solver(), _rag()))
    assert board is None, "storyboard must fail soft without a key"

    class _Msg:
        def __init__(self, c):
            self.content = c

    class _Choice:
        def __init__(self, c):
            self.finish_reason = "stop"
            self.message = _Msg(c)

    class _Resp:
        def __init__(self, c):
            self.choices = [_Choice(c)]

    calls = []
    class _Completions:
        async def create(self, **kw):
            calls.append(kw)
            if len(calls) == 1:
                beats = [{
                    "detail": f"beat {index + 1}", "duration_s": 5,
                    "narration_cue": "Show the next physical state.",
                    "anchor_cell": "C3",
                } for index in range(9)]
                return _Resp(json.dumps({
                    "concept": "c", "staging": "s", "palette": {},
                    "acts": [{"name": "ESTABLISH", "duration_s": 45, "beats": beats}],
                    "hero_frame": "h", "idle_loop": "i", "narration": ["n"],
                }))
            return _Resp("from manim import *\nclass AetherLabScene(Scene):\n"
                         "    def construct(self):\n        self.wait(1)\n")
    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    sg = SceneGenerator(replace(
        _settings(), openai_api_key="sk-test", llm_model="qwen3.7-plus"
    ))
    sg._client = _Client()
    request = ProblemRequest(prompt="pendulum", duration_target_s=45)
    default_request = ProblemRequest(prompt="default duration")
    assert default_request.canonical_payload()["duration_target_s"] == 30
    code = asyncio.run(sg._generate_remote(
        request, _solver(), _rag(), "AetherLabScene"))
    assert len(calls) == 2, "storyboard call + codegen call expected"
    assert calls[0]["temperature"] == 0.9 and calls[1]["temperature"] == 0.15
    assert "45 seconds" in calls[0]["messages"][1]["content"]
    codegen_user = next(
        message["content"] for message in calls[1]["messages"]
        if message["role"] == "user"
    )
    assert "45 seconds" in codegen_user
    assert "five acts" in calls[0]["messages"][0]["content"].lower()
    assert "sum to it within 5%" in calls[0]["messages"][0]["content"].lower()
    assert all(
        call.get("extra_body") == {"enable_thinking": False} for call in calls
    ), calls
    # A valid scene spec supersedes the raw "Locked storyboard" block; it must
    # still carry the director's creative plan and timed beats into codegen.
    assert "Canonical scene specification (aetherlab.scene_spec.v1)" in codegen_user
    assert '"concept": "c"' in codegen_user and '"name": "ESTABLISH"' in codegen_user
    assert "Mandatory beat-boundary comments" in codegen_user
    assert "# BEAT A1.B1 | 0.00-5.00 s" in codegen_user
    assert sg._last_storyboard and "acts" in sg._last_storyboard
    assert sg._last_storyboard["timeline"][0]["end_s"] == 5.0
    assert "TIMED DETAIL + CLEAN FRAME CONTRACT" in calls[1]["messages"][0]["content"]
    assert "A1.B1" in codegen_user
    assert "class AetherLabScene" in code
    from aetherlab.services.model_policy import (
        codegen_request_kwargs,
        is_thinking_only_model,
        model_codegen_warning,
    )
    assert codegen_request_kwargs(sg.settings) == {"extra_body": {"enable_thinking": False}}
    minimax = replace(sg.settings, llm_model="MiniMax-M3")
    assert codegen_request_kwargs(minimax) == {}
    assert codegen_request_kwargs(minimax, minimax_thinking=False) == {
        "extra_body": {"thinking": {"type": "disabled"}}
    }
    assert codegen_request_kwargs(minimax, minimax_thinking=True) == {
        "extra_body": {"thinking": {"type": "enabled"}}
    }
    calls.clear()
    minimax_sg = SceneGenerator(minimax)
    minimax_sg._client = _Client()
    asyncio.run(minimax_sg._generate_remote(
        request, _solver(), _rag(), "AetherLabScene"))
    # Scene calls default to thinking OFF for MiniMax: with it on, M3 spent the
    # whole max_tokens budget reasoning and returned no code (live 2026-09-30).
    assert len(calls) == 2 and all(
        call.get("extra_body") == {"thinking": {"type": "disabled"}} for call in calls
    ), calls
    assert calls[0]["max_tokens"] == 16384, "reasoning storyboard needs room beyond 4096"
    calls.clear()
    opted_in = SceneGenerator(minimax, minimax_thinking=True)
    opted_in._client = _Client()
    asyncio.run(opted_in._generate_remote(request, _solver(), _rag(), "AetherLabScene"))
    assert all(call.get("extra_body") == {"thinking": {"type": "enabled"}} for call in calls), calls
    assert is_thinking_only_model("qwen3.7-max-preview")
    assert "qwen3-coder-plus" in model_codegen_warning("qwen3.7-plus", 60)
    assert inspect.getsource(SceneGenerator).count("codegen_request_kwargs") >= 5
    return "hot storyboard/cold codegen; Qwen + MiniMax thinking toggles; coder guidance (F107)"


def t_f108():
    # Perceptual critique loop: skips cleanly without a vision model; PyAV
    # frame extraction works on a real render when one exists.
    from dataclasses import replace

    from aetherlab.core.models import SceneBundle
    from aetherlab.services.model_json import load_model_json
    from aetherlab.services.model_policy import non_thinking_request_kwargs
    from aetherlab.services.scene_critic import (
        Critique, _sample_indices, critique_video, critique_video_with_retry,
        extract_frames,
    )
    no_vlm = replace(_settings(), vision_model=None)
    crit = asyncio.run(critique_video("missing.mp4", "brief", no_vlm))
    assert crit.verdict == "skipped" and not crit.should_revise
    # BUG-35: raw LaTeX in model JSON must neither raise Invalid \escape nor
    # silently turn \theta into a tab escape.
    raw = r'''preface {"verdict":"revise","score":4,"issues":["Move \omega and \theta away from {edge}"],"strengths":[]} trailing'''
    repaired = load_model_json(raw)
    assert repaired["issues"] == [r"Move \omega and \theta away from {edge}"], repaired
    assert Critique(verdict="revise").should_revise
    # BUG-59: qwen3.7-plus is hybrid-thinking. The bounded, non-streaming
    # structured vision critic must disable thinking just like scene codegen.
    assert non_thinking_request_kwargs("qwen3.7-plus") == {
        "extra_body": {"enable_thinking": False}
    }
    assert non_thinking_request_kwargs("qwen3-coder-plus") == {}

    from types import SimpleNamespace
    from unittest import mock

    from aetherlab.services import scene_critic as critic_module

    frame = _TMP / "critic-thinking-frame.png"
    frame.write_bytes(b"not-decoded-by-fake-client")
    seen_request = {}

    class FakeCompletions:
        async def create(self, **kwargs):
            seen_request.update(kwargs)
            message = SimpleNamespace(
                content='{"verdict":"ship","score":8,"issues":[],"strengths":[]}'
            )
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    class FakeAsyncOpenAI:
        def __init__(self, **_kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    qwen_vision = replace(
        _settings(), openai_api_key="sk-test", vision_model="qwen3.7-plus"
    )
    with (
        mock.patch("openai.AsyncOpenAI", FakeAsyncOpenAI),
        mock.patch.object(critic_module, "extract_frames", return_value=[frame]),
    ):
        qwen_crit = asyncio.run(critique_video("fake.mp4", "brief", qwen_vision))
    assert qwen_crit.verdict == "ship"
    assert seen_request.get("extra_body") == {"enable_thinking": False}
    retry_calls = []

    async def transient_final(*_args, **kwargs):
        retry_calls.append(kwargs["frame_count"])
        if len(retry_calls) == 1:
            return Critique(verdict="skipped")
        return Critique(
            verdict="ship",
            score=7.0,
            breakdown={"legibility": 2.0},
            breakdown_source="vision",
        )

    original_retry_target = critic_module.critique_video
    critic_module.critique_video = transient_final
    try:
        retried_final = asyncio.run(
            critique_video_with_retry("fake.mp4", "brief", qwen_vision, frame_count=6)
        )
    finally:
        critic_module.critique_video = original_retry_target
    assert retry_calls == [6, 3]
    assert retried_final.verdict == "ship" and retried_final.retried
    # storyboard round-trips through the scene cache
    sb = SceneBundle.from_json(SceneBundle(
        class_name="X", code="c", engine="e", status="rendered",
        storyboard={"acts": []}).to_json())
    assert sb.storyboard == {"acts": []}
    assert SceneBundle.from_json({}).storyboard is None
    assert _sample_indices(10, 4) == [0, 3, 6, 9]
    assert _sample_indices(5, 99) == [0, 1, 2, 3, 4]
    # loop is wired into the runtime after successful renders
    src = inspect.getsource(__import__(
        "aetherlab.services.manim_runtime", fromlist=["ManimRuntime"]
    ).ManimRuntime.render_scene_with_repair)
    assert "critique_video_with_retry" in src and ".revise(" in src and "max_revisions" in src
    assert "keeping previous cut" in src, "revisions must never downgrade a shipped render"

    # BUG-38: a weaker reviser may emit code that fails static validation. The
    # revision must get one targeted repair before the previous cut is kept.
    from aetherlab.services.manim_runtime import ManimRuntime
    from aetherlab.services.scene_generator import SceneGenerator

    video = _TMP / "revision-draft.mp4"
    video.write_bytes(b"draft")
    settings = replace(
        _settings(), openai_api_key="sk-test", vision_model="vision-test",
        visual_critic_max_passes=2,
    )
    runtime = ManimRuntime(settings)
    calls = {"critique": 0, "repair": 0, "render": 0}
    original_critique = critic_module.critique_video
    original_revise = SceneGenerator.revise
    original_repair = SceneGenerator.repair

    async def fake_critique(*args, **kwargs):
        calls["critique"] += 1
        # Scores must rise: the best-cut loop keeps the earlier render when a
        # revision does not score above it, so flat scores would stop after
        # round 2 and never reach the final score-only critique (BUG-61).
        if calls["critique"] == 1:
            return Critique(verdict="revise", score=4.0, issues=["fix layout"])
        if calls["critique"] == 2:
            return Critique(verdict="revise", score=6.0, issues=["tighten spacing"])
        return Critique(
            verdict="ship",
            score=8.0,
            breakdown={"legibility": 2.0, "composition": 2.0},
        )

    async def fake_revise(self, code, critique, class_name):
        return (
            "from manim import *\nclass AetherLabScene(Scene):\n"
            "    def construct(self):\n"
            "        dot = Dot(color=GREEN_SCREEN)\n"
            "        self.play(Create(dot))\n"
        )

    async def fake_repair(self, code, error, class_name):
        calls["repair"] += 1
        return (
            "from manim import *\nclass AetherLabScene(Scene):\n"
            "    def construct(self):\n"
            "        dot = Dot(color=GREEN)\n"
            "        self.play(Create(dot))\n"
            "        self.play(dot.animate.shift(RIGHT))\n"
        )

    async def fake_render(scene, settings, quality, progress=None, variant="", **_kwargs):
        calls["render"] += 1
        if calls["render"] == 1:
            return replace(
                scene, status="render-error",
                diagnostics=[*scene.diagnostics, "Manim render failed: bad revised API"],
            )
        return replace(scene, status="rendered", video_path=str(video))

    critic_module.critique_video = fake_critique
    SceneGenerator.revise = fake_revise
    SceneGenerator.repair = fake_repair
    runtime._render_once = fake_render  # type: ignore[assignment]
    try:
        start = SceneBundle(
            "AetherLabScene",
            "from manim import *\nclass AetherLabScene(Scene):\n"
            "    def construct(self):\n        self.play(Create(Dot()))\n",
            "manim-community", "rendered", video_path=str(video),
        )
        from aetherlab.core.render_cache import record_scene_profile
        record_scene_profile(start, settings, "l")
        recovered = asyncio.run(runtime.render_scene_with_repair(start, settings, quality="l"))
    finally:
        critic_module.critique_video = original_critique
        SceneGenerator.revise = original_revise
        SceneGenerator.repair = original_repair
    assert recovered.status == "rendered" and "GREEN_SCREEN" not in recovered.code
    assert calls == {"critique": 3, "repair": 3, "render": 3}, calls
    assert recovered.quality_score == 8.0 and recovered.critique_verdict == "ship"
    assert recovered.critique_breakdown == {"legibility": 2.0, "composition": 2.0}
    assert any("Final visual critique" in d for d in recovered.diagnostics)
    assert any("Applied repaired visual revision" in d for d in recovered.diagnostics)
    import pathlib
    import tempfile
    vids = sorted(
        pathlib.Path(tempfile.gettempdir()).glob("aetherlab/renders/media/videos/**/*.mp4"),
        key=lambda p: p.stat().st_mtime,
    )
    note = "no render available for frame sampling"
    if vids:
        frames = extract_frames(vids[-1], count=3)
        assert len(frames) >= 1, "PyAV should sample frames from a real render"
        note = f"sampled {len(frames)} frames via PyAV"
    return (
        f"critique disables Qwen thinking + scores the final repaired revision; "
        f"{note} (BUG-59/61/65, F108)"
    )


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
    from aetherlab.core.models import SceneBundle
    from aetherlab.ui.widgets import SimulationPanel
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
    from aetherlab.ui.widgets import SimulationPanel, _frame_step_ms_for_video
    sp = SimulationPanel()
    assert hasattr(sp, "_player") and hasattr(sp, "_seek_slider")
    sp._on_duration_changed(65000)  # 1:05
    assert "1:05" in sp._time_label.text()
    assert _frame_step_ms_for_video(_TMP / "missing.mp4") == 33
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
    return "rail select emits index; " + _story_checks("test_ui_layout_regressions", (
        "test_compact_sidebar_fits_short_window_without_overlapping_items",
        "test_nine_sidebar_destinations_reflow_after_growing_and_shrinking",
    ))


def t_f76():
    from aetherlab.ui.qt_compat import QtCore, QtGui
    from aetherlab.ui.widgets import SidebarNav
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
    assert sb._buttons[7].isEnabled()
    sb.set_result_available(True)
    assert sb._buttons[7].isEnabled()
    sb.close()
    return "Lab destination remains available before and after a solve"


def t_f78():
    src = inspect.getsource(__import__("aetherlab.ui.main_window", fromlist=["MainWindow"]).MainWindow.on_scene_ready)
    assert "sidebar.select(7)" in src and "hide_loading" in src
    return "scene ready hides loading and opens the Lab workspace"


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
    corrupt_db = _TMP / "history-corrupt.sqlite3"
    corrupt_bytes = b"not history sqlite\x00\xff"
    corrupt_db.write_bytes(corrupt_bytes)
    hp3 = HistoryPanel()
    hp3.init_persistence(corrupt_db)
    quarantined = list(_TMP.glob("history-corrupt.sqlite3.corrupt-*"))
    assert len(quarantined) == 1 and quarantined[0].read_bytes() == corrupt_bytes
    hp3.add_entry("recovered", "new", "compiled", 0)
    assert hp3._list.count() == 1
    hp.close()
    hp2.close()
    hp3.close()
    return "history persists; corrupt DB quarantined and rebuilt (BUG-52)"


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
    return "failure sets stepper error + status bar; " + _command_bar_checks([
        ("test_failure_context_is_localized_and_preserves_original_diagnostics", {"language": language, "stage": stage})
        for language in ("kk", "ru", "en") for stage in ("pipeline", "solver", "owned-unknown-stage")
    ])


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
    from aetherlab.ui.main_window import MainWindow

    # pdflatex likely absent — must return None, not raise
    r = compile_latex_to_pdf(_TMP / "d.tex")
    assert r is None or r.exists()
    src = inspect.getsource(MainWindow._export_pdf)
    assert "_start_export_task" in src and 'with_suffix(".tex")' in src
    assert "LaTeX saved instead" in src and "cancel_check=cancel.is_set" in src
    return "PDF compiles off-thread; failure saves chosen .tex fallback (BUG-57)"


def t_f87():
    from aetherlab.services.pdf import export_scene_code
    out = _TMP / "s.py"
    export_scene_code("from manim import *\nclass S(Scene):\n    pass", out)
    assert "from manim import *" in out.read_text(encoding="utf-8")
    return "scene code export"


def t_f88():
    from aetherlab.core.atomic_file import atomic_copy_file
    from aetherlab.core.proc import ProcessCancelledError
    from aetherlab.ui.main_window import MainWindow

    source = _TMP / "atomic-video-source.mp4"
    destination = _TMP / "atomic-video-destination.mp4"
    source.write_bytes(b"new-video" * 200_000)
    destination.write_bytes(b"prior-good-video")
    try:
        atomic_copy_file(source, destination, cancel_check=lambda: True)
        raise AssertionError("cancelled copy unexpectedly completed")
    except ProcessCancelledError:
        pass
    assert destination.read_bytes() == b"prior-good-video"
    assert not list(_TMP.glob(".atomic-video-destination.*.tmp.mp4"))
    atomic_copy_file(source, destination)
    assert destination.read_bytes() == source.read_bytes()
    src = inspect.getsource(MainWindow._save_video)
    assert "_start_export_task" in src and "atomic_copy_file" in src
    return "video copy is backgrounded, cancellable, and atomic (BUG-57)"


def t_f89():
    src = inspect.getsource(__import__("aetherlab.ui.main_window", fromlist=["MainWindow"]).MainWindow._export_gif)
    assert "ffmpeg" in src and "FileNotFoundError" in src and "TimeoutExpired" in src
    assert "_start_export_task" in src and "run_process_tree" in src
    assert "unique_staging_path" in src and "os.replace" in src
    assert "subprocess.run" not in src
    return "GIF conversion is backgrounded, cancellable, and atomic (BUG-57)"


# ══════════════════════════════════════════════════════════════════════════
# UX / theme / shell
# ══════════════════════════════════════════════════════════════════════════

def t_f90():
    from aetherlab.ui.style import AETHERLAB_QSS
    from aetherlab.ui.theme import Theme
    assert Theme().accent in AETHERLAB_QSS and len(AETHERLAB_QSS) > 3000
    return f"QSS present ({len(AETHERLAB_QSS)} chars)"


def t_f91():
    from aetherlab.ui.live_canvas import LiveCanvas
    from aetherlab.ui.main_window import MainWindow
    from aetherlab.ui.widgets import CommandBar, LessonView, SimulationPanel

    w = MainWindow(_settings())
    try:
        assert w.minimumWidth() <= 960 and w.minimumHeight() <= 640
        w.resize(760, 520)
        w._apply_responsive_layout()
        assert 220 <= w._param_side.width() <= 320
        assert w._param_side.width() == 220

        sim = SimulationPanel()
        sim_video = getattr(sim, "_video_widget", None)
        if sim_video is not None:
            assert sim_video.minimumWidth() <= 280
            assert sim_video.minimumHeight() <= 158

        canvas = LiveCanvas()
        assert canvas.minimumWidth() <= 260
        assert canvas.minimumHeight() <= 180

        command = CommandBar()
        command.resize(520, 120)
        command.show()
        _app.processEvents()
        assert command.input.width() >= 220, command.input.width()
        command.close()

        lesson = LessonView()
        assert lesson._outline.minimumWidth() <= 160
        assert lesson._outline.maximumWidth() <= 280
        lesson_video = getattr(lesson, "_video_widget", None)
        if lesson_video is not None:
            assert lesson_video.minimumWidth() <= 280
            assert lesson_video.minimumHeight() <= 158
    finally:
        w.close()
        probe = getattr(w, "_ollama_probe", None)
        if probe and probe.isRunning():
            probe.wait(5000)
    return "responsive shell + command bar + media/canvas minimums fit small screens"


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
    assert "gpt-x" in ev._key_label.text() and "3 books" in ev._lib_label.text()
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
    from aetherlab.core.models import RagResult, SceneBundle, SolverResult
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
    from aetherlab.services.manim_runtime import _scene_name, sanitize_scene_name
    assert sanitize_scene_name("my-cool scene 1") == "MyCoolScene1"
    assert sanitize_scene_name("!!!") == "AetherLabScene"
    a = _scene_name("X", "code A")
    b = _scene_name("X", "code B")
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
    from aetherlab.ui.live_canvas import SWEEP_SECONDS
    from aetherlab.ui.qt_compat import QtCore
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
    pm = QtGui.QPixmap(lc.size())
    lc.render(pm)  # populate pixel cache
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
    import inspect
    import re

    import aetherlab.ui.live_canvas as mod
    from aetherlab.ui import style
    from aetherlab.ui.live_canvas import CANVAS_PALETTE
    assert CANVAS_PALETTE["primary"] == style.CYAN
    assert CANVAS_PALETTE["grid"] == style.BORDER_HAIRLINE
    src = inspect.getsource(mod)
    body = src.split("CANVAS_PALETTE: dict[str, str] = {")[1].split("}")[1]
    stray = re.findall(r'"#[0-9A-Fa-f]{6}"', body)
    assert stray == [], f"hardcoded hex outside palette: {stray[:4]}"
    return "one palette dict; zero stray hex in module body"


def t_f113():
    # Sample cache is viewport-independent; NaN gaps split into branches.
    import numpy as np

    from aetherlab.ui.live_canvas import (
        CANVAS_PALETTE,
        CanvasState,
        CurveSpec,
        LiveCanvas,
        _drawable_sample_mask,
        _finite_runs,
    )
    from aetherlab.ui.qt_compat import QtCore, QtGui
    def fx(t, p): return t
    def fy(t, p):
        with np.errstate(all="ignore"):
            return 1.0 / t
    st = CanvasState(title="1/t", x_range=(-3, 3), y_range=(-5, 5),
                     curves=[CurveSpec(name="1/t", x_fn=fx, y_fn=fy,
                                       t_range=(-3.0, 3.0), t_steps=601)])
    lc = LiveCanvas()
    lc.resize(800, 600)
    lc.set_state(st)
    lc._ensure_samples(st)
    key = lc._sample_key
    lc._apply_zoom(5.0, QtCore.QPointF(400, 300))
    lc._ensure_samples(st)
    assert lc._sample_key == key, "zoom must NOT rebuild samples"
    t, xs, ys = lc._samples[0]
    runs = _finite_runs(np.isfinite(xs) & np.isfinite(ys))
    assert len(runs) == 2, f"1/t must render as 2 branches, got {len(runs)}"
    pm = QtGui.QPixmap(lc.size())
    lc.render(pm)
    assert not pm.isNull()
    st.params["k"] = 2.0
    lc._ensure_samples(st)
    assert lc._sample_key != key, "param change must rebuild samples"

    # tan(pi/2) is a huge finite float, not inf/NaN. The old finite-only mask
    # joined samples across each asymptote with a false chord.
    tan_state = CanvasState(
        title="tan(t)", x_range=(-np.pi, np.pi), y_range=(-5, 5),
        curves=[CurveSpec(
            name="tan(t)", x_fn=fx,
            y_fn=lambda value, _params: np.tan(value),
            t_range=(-np.pi, np.pi), t_steps=601,
        )],
    )
    lc.set_state(tan_state)
    lc._ensure_samples(tan_state)
    _tan_t, tan_x, tan_y = lc._samples[0]
    assert np.all(np.isfinite(tan_y)), "test must exercise finite asymptote samples"
    plot_rect = lc._plot_rect()
    px, py = lc._map_arrays(tan_x, tan_y, plot_rect)
    tan_runs = _finite_runs(_drawable_sample_mask(px, py, plot_rect))
    assert len(tan_runs) == 3, f"tan(t) must split into 3 branches, got {tan_runs}"
    tan_pixmap = QtGui.QPixmap(lc.size())
    lc._fade_alpha = 1.0
    lc.render(tan_pixmap)
    assert not tan_pixmap.isNull()
    tan_image = tan_pixmap.toImage().convertToFormat(QtGui.QImage.Format.Format_RGBA8888)
    pixels = tan_image.bits()
    pixels.setsize(tan_image.sizeInBytes())
    pixel_rows = np.frombuffer(pixels, dtype=np.uint8).reshape(
        tan_image.height(), tan_image.bytesPerLine()
    )
    rgba = pixel_rows[:, :tan_image.width() * 4].reshape(
        tan_image.height(), tan_image.width(), 4
    )
    plot = lc._plot_rect()
    x0, x1 = int(plot.left()), int(plot.right())
    y0, y1 = int(plot.top()), int(plot.bottom())
    expected_rgb = np.asarray(QtGui.QColor(CANVAS_PALETTE["primary"]).getRgb()[:3])
    exact_primary = np.all(rgba[y0:y1, x0:x1, :3] == expected_rgb, axis=2).sum()
    assert exact_primary > 100, f"tan(t) render has no visible primary curve ({exact_primary} pixels)"
    return "sample cache stable under zoom; 1/t has 2 branches; finite tan(t) asymptotes split into 3"


def t_f114():
    # Multi-curve payloads: roles, dashed references, fill, points — and full
    # backward compatibility for old single-curve payloads.
    from aetherlab.services.plotting import compile_plot, fallback_plot_payload
    from aetherlab.ui.live_canvas import CANVAS_PALETTE, build_canvas_state
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
    import os
    import tempfile
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
    pm = QtGui.QPixmap(lc.size())
    lc.render(pm)
    assert lc._legend_hits, "legend hidden for a single named curve"
    rect, index = lc._legend_hits[0]
    assert lc._state.curves[index].visible
    hit = lc._legend_hit(rect.center())
    assert hit == index
    lc.toggle_curve_visibility(index)
    assert not lc._state.curves[index].visible
    pm2 = QtGui.QPixmap(lc.size())
    lc.render(pm2)  # muted style paints fine
    lc.toggle_curve_visibility(index)
    assert lc._state.curves[index].visible
    return "legend always shown, hit-testable, toggles visibility"


def t_f118():
    # Param chip renders live values; first paint fades in (later ones don't).
    import inspect

    from aetherlab.ui.live_canvas import FADE_IN_MS, LiveCanvas, build_canvas_state
    src = inspect.getsource(LiveCanvas._draw_param_chip)
    assert "params.items()" in src and "AlignRight" in src
    lc = LiveCanvas()
    lc.resize(800, 600)
    assert lc._fade_alpha == 1.0
    lc.set_state(build_canvas_state("t", {"damping": 0.2}))
    assert lc._fade_alpha < 1.0, "first curves must start faded"
    lc._fade_anim.stop()
    lc._fade_alpha = 1.0
    lc.set_state(build_canvas_state("t", {"damping": 0.4}))
    assert lc._fade_alpha == 1.0, "subsequent updates must not re-fade"
    assert FADE_IN_MS == 300
    return "mono param chip; 300ms fade only on first paint"


# ══════════════════════════════════════════════════════════════════════════
# Design v2 activation (F119-F124)
# ══════════════════════════════════════════════════════════════════════════

def t_f119():
    # Student-app palette tokens stay aligned across QSS, theme, and canvas.
    from aetherlab.ui import style
    from aetherlab.ui.theme import Theme
    assert style.CYAN == Theme().accent
    assert style.CYAN_DEEP == Theme().accent_deep
    for tok in ("STAGE", "ELEV", "HOVER_SURFACE", "LINE_0"):
        assert hasattr(style, tok), tok
    from aetherlab.ui.live_canvas import CANVAS_PALETTE
    assert CANVAS_PALETTE["primary"] == style.CYAN
    assert Theme().accent == style.CYAN and Theme().curve1 == style.CYAN
    from aetherlab.ui.widgets import SidebarNav
    rail = SidebarNav()
    assert rail.width() == 92, f"study navigation rail should be 92px, got {rail.width()}"
    return "study palette tokens; shared canvas/theme accent; 92px navigation rail"


def t_f120():
    # Math-as-brand: mathtext service typesets to pixmaps, never raises.
    from aetherlab.services.mathtext import (
        WATERMARK_FORMULAS,
        latex_for_param,
        looks_like_math,
        render_math,
        render_param_symbol,
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
    # parameter rows show typeset symbols; empty state offers ENT practice.
    from aetherlab.core.models import SolverResult
    from aetherlab.ui.widgets import AnalysisPanel, EmptyStateView, ParameterDock
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
    assert e.findChild(QtWidgets.QFrame, "ENTLaunchCard") is not None
    assert e.findChild(QtWidgets.QFrame, "SetupStrip") is not None
    return "hero banner: math→pixmap, prose→text; param symbols; ENT and setup cards"


def t_f122():
    # Scene-meta parser + storyboard normalizer feed the v2 chrome.
    from aetherlab.core.models import SceneBundle
    from aetherlab.ui.widgets import SimulationPanel, _storyboard_acts, parse_scene_meta
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
        ActSeekSlider,
        CodeArtifactView,
        CritiqueBadge,
        ManimBadge,
        SimulationPanel,
        StoryboardStrip,
        _ManimHighlighter,
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
    assert "_BookSpine" in src and "chunks" in src and '_t("reindexing")' in src
    spine = _BookSpine("#22D3EE")
    from aetherlab.ui.qt_compat import QtGui
    pm = QtGui.QPixmap(spine.size())
    spine.render(pm)  # paints without crash
    from aetherlab.core.settings import load_settings
    from aetherlab.ui.main_window import SettingsDialog
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
    import aetherlab.services.web_references as webrefs
    from aetherlab.core.models import RagHit, RagResult
    from aetherlab.services.web_references import WikipediaReferenceProvider, fetch_web_references
    # A broken endpoint must return [] (never raise) — offline-safety contract.
    broken = WikipediaReferenceProvider(timeout=2)
    broken.api = "https://invalid.aetherlab.example/w/api.php"
    assert broken.search(["oscillator"], 3) == []
    assert WikipediaReferenceProvider().search([], 3) == []  # no keywords → []
    # BUG-47: MediaWiki can return an error/warning object with HTTP 200. Any
    # valid JSON of the wrong shape must remain fail-soft after the fetch.
    original_get = webrefs._http_get_json
    try:
        for malformed in ([], None, {"error": {"code": "ratelimited"}},
                          {"query": []}, {"query": {"pages": []}}):
            webrefs._http_get_json = lambda *_args, value=malformed, **_kwargs: value
            assert WikipediaReferenceProvider().search(["oscillator"], 3) == []
        webrefs._http_get_json = lambda *_args, **_kwargs: {
            "query": {"pages": {
                "bad": 7,
                "ok": {
                    "index": "not-a-number",
                    "title": "Harmonic oscillator",
                    "extract": "A mass oscillates about equilibrium.",
                    "fullurl": "https://en.wikipedia.org/wiki/Harmonic_oscillator",
                },
            }}
        }
        shaped = WikipediaReferenceProvider().search(["oscillator"], 3)
        assert len(shaped) == 1 and shaped[0].source_label == "Harmonic oscillator"
    finally:
        webrefs._http_get_json = original_get
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
    from dataclasses import replace

    from aetherlab.core.settings import load_settings
    assert fetch_web_references(["x"], replace(load_settings(), web_references=False)) == []
    return "web provider transport/schema fail-soft; RagHit back-compat; toggle honored (BUG-47)"


def t_f126():
    # Merge helper appends web hits after library hits, tags backend, fail-soft;
    # settings expose the toggle end to end.
    import asyncio
    from dataclasses import replace

    from aetherlab.core.models import RagHit, RagResult
    from aetherlab.core.settings import _as_bool, load_settings
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
    from aetherlab.core.models import RagHit, RagResult
    from aetherlab.ui.qt_compat import QtGui, QtWidgets
    from aetherlab.ui.widgets import BlueprintBackdrop, CommandBar, ReferencePanel, _RagHitCard

    # web card: opens a URL, not a local file; low score dims the card
    web_card = _RagHitCard("Harmonic oscillator", None, 0.9,
                           "An oscillator…", "https://en.wikipedia.org/wiki/Harmonic_oscillator",
                           is_web=True)
    assert web_card.graphicsEffect() is None  # high score → not dimmed
    dim_card = _RagHitCard("Weak", 12, 0.3, "…", "C:/lib/x.pdf", is_web=False)
    assert dim_card.graphicsEffect() is not None  # < 0.5 → dimmed
    pm = QtGui.QPixmap(320, 120)
    web_card.render(pm)  # paints without crash

    # ReferencePanel provenance line counts library vs web
    rp = ReferencePanel()
    rp.set_rag_result(RagResult(["k"], [
        RagHit("C:/lib/a.pdf", 3, 0.9, "lib", origin="library"),
        RagHit("https://en.wikipedia.org/wiki/X", None, 0.8, "web", source_label="X", origin="web"),
    ], "chromadb+web"))
    assert "1 library" in rp._backend_label.text() and "1 web" in rp._backend_label.text()

    # Blueprint backdrop paints; command-bar filament toggles the shell property
    bd = BlueprintBackdrop(QtWidgets.QLabel("x"))
    bd.resize(400, 300)
    pm2 = QtGui.QPixmap(bd.size())
    bd.render(pm2)
    cb = CommandBar()
    cb._set_shell_focused(True)
    assert cb._shell.property("focused") == "true"
    cb._set_shell_focused(False)
    assert cb._shell.property("focused") == "false"

    # Settings dialog carries the web-references checkbox
    from aetherlab.core.settings import load_settings
    from aetherlab.ui.main_window import SettingsDialog
    d = SettingsDialog(load_settings())
    vals = d.get_settings()
    assert "web_references" in vals and isinstance(vals["web_references"], bool)
    return "web/library card styling + dimming; provenance; backdrop; filament; settings toggle"


def t_f128():
    # Provider independence: ollama preset resolution + qwen autoload gated off.
    import aetherlab.core.settings as settings_module
    saved_env = os.environ.pop("AETHERLAB_DATA_DIR", None)
    provider_keys = (
        "AETHERLAB_PROVIDER", "AETHERLAB_LLM_MODEL", "MANIM_MODEL", "GPT_MODEL",
        "CHAT_MODEL", "AETHERLAB_OPENAI_API_KEY", "OPENAI_API_KEY", "GPT_API_KEY",
        "DASHSCOPE_API_KEY", "AETHERLAB_OPENAI_BASE_URL", "OPENAI_BASE_URL",
        "GPT_BASE_URL", "LLM_BASE_URL",
    )
    saved_provider_env = {key: os.environ.pop(key, None) for key in provider_keys}
    orig_default = settings_module._default_data_dir
    settings_module._default_data_dir = lambda: _TMP / "prov_home"
    try:
        s0 = settings_module.load_settings()
        assert s0.openai_api_key is None, "qwen autoload must be gated off by default"
        settings_module.save_app_config({"provider_preset": "ollama", "model": "qwen2.5:7b"})
        s1 = settings_module.load_settings()
        assert s1.openai_base_url == settings_module.OLLAMA_OPENAI_BASE_URL
        assert s1.openai_api_key == "ollama"
        assert s1.provider_source == str(settings_module.app_config_path())
        assert s1.api_key_source == "Ollama local (no secret)"
        from aetherlab.services.model_policy import active_provider_name
        assert active_provider_name(s1) == "Ollama"
        os.environ["AETHERLAB_OPENAI_API_KEY"] = "sk-env"
        assert settings_module.load_settings().openai_api_key == "sk-env", "env must beat preset"
    finally:
        os.environ.pop("AETHERLAB_OPENAI_API_KEY", None)
        (_TMP / "prov_home" / "settings.json").unlink(missing_ok=True)
        settings_module._default_data_dir = orig_default
        if saved_env is not None:
            os.environ["AETHERLAB_DATA_DIR"] = saved_env
        for key, value in saved_provider_env.items():
            if value is not None:
                os.environ[key] = value
    return "ollama preset resolves; qwen gated; env wins (F128)"


def t_f129():
    # Ollama discovery + Settings preset UI + EmptyState one-click CTA.
    import threading
    import time
    from dataclasses import replace

    import aetherlab.services.providers as providers
    from aetherlab.services.providers import detect_ollama, test_connection

    models = detect_ollama(timeout=1.0)  # absence is a normal state
    assert isinstance(models, list)
    ok, msg = test_connection(replace(_settings(), openai_api_key=None))
    assert not ok and "key" in msg.lower()
    from aetherlab.ui.main_window import SettingsDialog

    d = SettingsDialog(_settings())
    assert d._preset_combo.count() == 3 and hasattr(d, "_test_btn")
    assert d.get_settings()["provider_preset"] in ("custom", "ollama", "none")

    started = threading.Event()
    release = threading.Event()
    original_test_connection = providers.test_connection

    def blocking_test(_probe):
        started.set()
        assert release.wait(2.0)
        return True, "Connected without blocking the GUI"

    providers.test_connection = blocking_test
    try:
        before = time.perf_counter()
        d._test_connection()
        elapsed = time.perf_counter() - before
        assert elapsed < 0.2 and started.wait(0.5)
        assert not d._test_btn.isEnabled()
        release.set()
        deadline = time.monotonic() + 2.0
        while d._provider_task and d._provider_task.is_running and time.monotonic() < deadline:
            _app.processEvents()
            time.sleep(0.01)
        _app.processEvents()
        assert d._provider_task and not d._provider_task.is_running
        assert d._test_btn.isEnabled()
        assert "without blocking" in d._test_result.text()
    finally:
        release.set()
        providers.test_connection = original_test_connection
    d.close()
    from aetherlab.ui.widgets import EmptyStateView
    ev = EmptyStateView()
    ev.offer_ollama(2)
    assert ev._ollama_btn.isVisibleTo(ev) and "2 local models" in ev._key_label.text()
    ev.set_status(True, "m", 0)
    assert not ev._ollama_btn.isVisibleTo(ev)
    ev.close()
    return f"provider test is backgrounded + preset UI + CTA ({len(models)} local models) (BUG-53)"


def t_f130():
    # key_equations contract: model round-trip, fallback domains, hero banner, export.
    from dataclasses import replace

    from aetherlab.core.models import ProblemRequest, SolverResult
    from aetherlab.services.llm import FALLBACK_EQUATIONS, AsyncLLMCoordinator
    sr = SolverResult.from_json(SolverResult(
        summary="s", derivation_steps=[], keywords=[], variables={},
        model_name="t", key_equations=[r"E = mc^2"]).to_json())
    assert sr.key_equations == [r"E = mc^2"]
    assert SolverResult.from_json({}).key_equations == []
    keyless = replace(_settings(), openai_api_key=None)
    r = asyncio.run(AsyncLLMCoordinator(keyless).solve(ProblemRequest(prompt="Solve the simple pendulum")))
    assert r.key_equations == FALLBACK_EQUATIONS["pendulum"]
    em = asyncio.run(AsyncLLMCoordinator(keyless).solve(ProblemRequest(prompt="electric dipole field lines")))
    assert em.key_equations == FALLBACK_EQUATIONS["em_field"]
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
    return "key_equations end-to-end: model→fallback domains→banner→export (F130)"


def t_f131():
    # Product hygiene: version flag, rotating log, icon assets + taskbar wiring.
    import subprocess

    from aetherlab import __version__
    r = subprocess.run([sys.executable, "-m", "aetherlab", "--version"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=60, env={**os.environ})
    assert __version__ in (r.stdout + r.stderr), (r.stdout, r.stderr)
    from aetherlab.__main__ import _setup_logging
    _setup_logging()
    log_file = Path(os.environ["AETHERLAB_DATA_DIR"]) / "logs" / "aetherlab.log"
    assert log_file.exists() and "starting" in log_file.read_text(encoding="utf-8")
    assert Path("assets/aetherlab.ico").exists()
    app_module = __import__("aetherlab.ui.app", fromlist=["_run_owned_app"])
    # App identity and icon setup intentionally live in the private owned-app
    # helper so the profile lock is acquired before QApplication is created.
    src = inspect.getsource(app_module._run_owned_app)
    assert "SetCurrentProcessExplicitAppUserModelID" in src and "setWindowIcon" in src
    assert "PhysLab.Workbench" in src and 'setApplicationName("PhysLab")' in src
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
    # BUG-33/39: audit every Python surface instead of a hand-maintained five-
    # file list. Text subprocess pipes and text files must specify encodings;
    # print-producing entry points must configure redirected legacy streams.
    import ast
    import io

    from aetherlab.core.console import configure_utf8_stdio

    roots = [pathlib.Path("aetherlab"), pathlib.Path("tools"), pathlib.Path("packaging")]
    py_files = sorted({p for root in roots for p in root.rglob("*.py")})
    py_files += [pathlib.Path("build_feature_tracker.py"), pathlib.Path("aetherlab_watchdog.py"), pathlib.Path("test_features.py")]
    undecoded = []
    default_codec = []
    unsafe_console = []
    for path in py_files:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        has_print = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id == "print":
                has_print = True
            if (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "subprocess"
                and node.func.attr in {"run", "Popen", "check_output", "check_call"}
            ):
                kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
                text_mode = any(
                    isinstance(kwargs.get(name), ast.Constant) and kwargs[name].value is True
                    for name in ("text", "universal_newlines")
                )
                if text_mode and not {"encoding", "errors"} <= set(kwargs):
                    undecoded.append(f"{path}:{node.lineno}")
            if isinstance(node.func, ast.Attribute) and node.func.attr in {"read_text", "write_text"}:
                kwargs = {kw.arg for kw in node.keywords if kw.arg}
                if "encoding" not in kwargs:
                    default_codec.append(f"{path}:{node.lineno}")
            if isinstance(node.func, ast.Name) and node.func.id == "open":
                mode = "r"
                if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                    mode = str(node.args[1].value)
                kwargs = {kw.arg for kw in node.keywords if kw.arg}
                if "b" not in mode and "encoding" not in kwargs:
                    default_codec.append(f"{path}:{node.lineno}")
        if has_print and "configure_utf8_stdio" not in source:
            unsafe_console.append(str(path))
    assert not undecoded, f"text subprocess calls missing UTF-8/errors=replace: {undecoded}"
    assert not default_codec, f"text file calls relying on locale codec: {default_codec}"
    assert not unsafe_console, f"print entry points lack UTF-8 stdio policy: {unsafe_console}"

    raw = io.BytesIO()
    cp1251 = io.TextIOWrapper(raw, encoding="cp1251", errors="strict")
    configure_utf8_stdio((cp1251,))
    cp1251.write("revision → θ")
    cp1251.flush()
    assert raw.getvalue().decode("utf-8") == "revision → θ"
    return "xplat subprocesses + whole-tree UTF-8 file/pipe/console audit (BUG-39, F133)"


def t_f134():
    # Bug 1 — the sync fix: isolated dir + disable_caching + this-render discovery.
    from pathlib import Path

    from aetherlab.services.manim_runtime import (
        ManimRuntime,
        _find_video_in,
        _manim_render_command,
    )
    src = inspect.getsource(ManimRuntime.render_scene)
    assert "_RUNS_DIR" in src and "uuid" in src
    assert "subprocess_kwargs" in src and "_find_video_in" in src
    assert "cache_enabled=bool(safe_lineage)" in src
    command = _manim_render_command(
        ["python", "-m", "manim"], quality="l", fps=30, seed=7,
        media_dir=Path("media"), scene_file=Path("scene.py"), class_name="Scene",
    )
    assert "--disable_caching" in command
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
    assert 'scene_bundle.video_path = ""' in rs, "failed renders must not keep stale paths"
    rr = inspect.getsource(ManimRuntime.render_scene_with_repair)
    assert "draft_quality" in rr and "partial success" in rr and "keeping draft" in rr

    # BUG-29: a pre-rendered draft (e.g. the tournament winner) is NOT re-rendered
    # at draft quality — the repair path reuses it and promotes straight to HQ.
    import asyncio as _asyncio
    from dataclasses import replace as _replace

    from aetherlab.core.models import SceneBundle
    rt = ManimRuntime(_settings())
    calls: list[str] = []

    async def _fake_render_once(scene, settings, quality, progress=None, variant="", **_kwargs):
        calls.append(quality)
        return _replace(scene, status="rendered", video_path=str(_TMP / f"r_{quality}.mp4"))

    rt._render_once = _fake_render_once  # type: ignore[assignment]
    drafted = _TMP / "prewinner.mp4"
    drafted.write_bytes(b"\x00" * 64)
    from aetherlab.core.render_cache import record_scene_profile
    pre = record_scene_profile(SceneBundle("S", "code", "manim", "rendered", video_path=str(drafted)), _settings(), "l")

    calls.clear()
    out = _asyncio.run(rt.render_scene_with_repair(_replace(pre), _settings(), quality="l"))
    assert calls == [], f"pre-rendered draft must not re-render at draft quality: {calls}"
    assert out.video_path == str(drafted), "the winner's own draft must be reused as the output"

    calls.clear()
    _asyncio.run(rt.render_scene_with_repair(_replace(pre), _settings(), quality="h"))
    assert calls == ["h"], f"pre-rendered draft must promote straight to HQ (no re-draft): {calls}"

    calls.clear()
    _asyncio.run(rt.render_scene_with_repair(SceneBundle("S", "code", "manim", "compiled"), _settings(), quality="l"))
    assert calls == ["l"], f"a fresh compiled scene must still render its draft: {calls}"
    return f"cost light={light:.1f}<heavy={heavy:.1f}; draft→final partial-success; winner reuse (F135); " + _render_cache_checks()


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
    return "failure classified+dumped; failure_kind round-trips (F136); " + _story_checks("test_cloud_failure_diagnosis", (
        "test_worker_output_failure_overrides_dependency_banners",
        "test_worker_output_excerpt_keeps_the_actual_failure",
    ))


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


def t_f138():
    # Narration sync engine (manim-bot decision): fit-to-video math + merge policy.
    from aetherlab.services import voiceover as vo
    assert vo._parse_rate("+8%") == 8 and vo._parse_rate("-20%") == -20 and vo._parse_rate(None) == 0
    assert vo._format_rate(8) == "+8%" and vo._format_rate(-25) == "-25%"
    # audio 20% too long → speak faster (ratio>1 raises the rate)
    ratio, base = 1.20, 8
    assert vo._format_rate(max(-40, min(80, base + round((ratio - 1) * 100)))) == "+28%"
    # merge policy: audio>video pads (tpad), audio<=video copies without -shortest.
    msrc = inspect.getsource(vo.merge)
    assert "tpad" in msrc and "stop_mode=clone" in msrc, "long-audio path must pad video"
    assert "no -shortest" in msrc, "short-audio path must keep full video (no -shortest)"
    # fail-soft: missing video → None (no network needed)
    got = asyncio.run(vo.add_voiceover(_TMP / "nope.mp4", "hi", _TMP / "narr"))
    assert got is None
    # empty narration → None
    assert asyncio.run(vo.add_voiceover(_TMP / "nope.mp4", "", _TMP / "narr")) is None
    return f"fit-to-video math + merge policy + fail-soft (avail={vo.narration_available()}) (F138)"


def t_f139():
    # Narration derivation from final code + storyboard; pipeline wiring + fail-soft.
    from aetherlab.services import voiceover as vo
    from aetherlab.services.scene_generator import SceneGenerator
    sb = {"narration": ["Beat one.", "Beat two."],
          "acts": [{"duration_s": 6}, {"duration_s": 8}, {"duration_s": 5}]}
    assert vo.storyboard_narration_script(sb) == "Beat one. Beat two."
    assert vo.storyboard_target_seconds(sb) == 19.0
    assert vo.storyboard_narration_script(None) == "" and vo.storyboard_target_seconds({}) is None
    # narrate() derives FROM the final code (references on-screen beats)
    nsrc = inspect.getsource(SceneGenerator.narrate)
    assert "Scene code" in nsrc and "in the order" in nsrc.lower()
    # wired into the render pipeline, fail-soft
    from aetherlab.services.manim_runtime import ManimRuntime
    rr = inspect.getsource(ManimRuntime.render_scene_with_repair)
    assert "_add_narration" in rr and "narration_enabled" in rr
    an = inspect.getsource(ManimRuntime._add_narration)
    assert "narration_available" in an and "silent_video_path" in an and "kept silent" in an
    # disabled → the block is guarded; missing video path → kept silent (fast)
    from dataclasses import replace
    s_on = replace(_settings(), narration_enabled=True)
    out = asyncio.run(ManimRuntime()._add_narration(
        make_scene_bundle(video_path="/no/such.mp4"), s_on, "brief"))
    assert out.video_path == "/no/such.mp4"
    return "narration derived from code+storyboard; wired + fail-soft (F139)"


def make_scene_bundle(**kw):
    from aetherlab.core.models import SceneBundle
    base = dict(class_name="X", code="c", engine="manim-community", status="rendered")
    base.update(kw)
    return SceneBundle(**base)


def t_f140():
    # Narration settings: env + app-config round-trip; silent_video_path persists.
    import aetherlab.core.settings as settings_module
    saved = {k: os.environ.pop(k, None) for k in
             (
                 "AETHERLAB_NARRATION", "AETHERLAB_TTS_VOICE", "AETHERLAB_TTS_RATE",
                 "VOICEOVER_ENABLED", "TTS_ENABLED", "TTS_VOICE", "TTS_RATE",
             )}
    try:
        os.environ["AETHERLAB_NARRATION"] = "1"
        os.environ["AETHERLAB_TTS_VOICE"] = "en-GB-RyanNeural"
        s = settings_module.load_settings()
        assert s.narration_enabled is True and s.tts_voice == "en-GB-RyanNeural" and s.tts_rate == "+8%"
        del os.environ["AETHERLAB_NARRATION"]
        assert settings_module.load_settings().narration_enabled is False
        os.environ.pop("AETHERLAB_TTS_VOICE", None)
        os.environ.pop("AETHERLAB_TTS_RATE", None)
        os.environ["VOICEOVER_ENABLED"] = "true"
        os.environ["TTS_VOICE"] = "en-US-AndrewMultilingualNeural"
        os.environ["TTS_RATE"] = "+10%"
        alias = settings_module.load_settings()
        assert alias.narration_enabled is True and alias.tts_voice.endswith("MultilingualNeural")
        assert alias.tts_rate == "+10%"
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
    from aetherlab.core.models import SceneBundle
    sb = SceneBundle.from_json(SceneBundle(
        class_name="X", code="c", engine="e", status="rendered",
        video_path="narrated.mp4", silent_video_path="silent.mp4").to_json())
    assert sb.silent_video_path == "silent.mp4" and SceneBundle.from_json({}).silent_video_path == ""
    # Settings dialog exposes the toggle
    from aetherlab.ui.main_window import SettingsDialog
    d = SettingsDialog(_settings())
    assert hasattr(d, "_narration_check") and "narration_enabled" in d.get_settings()
    d.close()
    return "narration settings env/config + manim-bot aliases + silent_video_path + dialog toggle (F140)"


def t_f141():
    # Topic-explainer Phase 1: lesson planner + LessonPlan/LessonBundle model.
    from dataclasses import replace
    from unittest.mock import patch

    from aetherlab.core.models import LessonBundle, LessonChapter, LessonPlan, SceneBundle
    from aetherlab.services.lesson_pipeline import _PlanCache
    from aetherlab.services.lesson_planner import _template_lesson, plan_lesson
    from aetherlab.services.scene_templates import detect_domain
    # model round-trip incl. nested chapters/questions; old caches load with defaults
    p = _template_lesson("Solve the simple pendulum", "ap")
    p2 = LessonPlan.from_json(p.to_json())
    assert p2.audience == "ap" and p2.chapters and p2.questions
    assert LessonPlan.from_json({}).title == "Untitled lesson"
    assert LessonPlan.from_json({"audience": "weird"}).audience == "undergrad"
    b2 = LessonBundle.from_json(LessonBundle(
        plan=p, chapter_scenes=[SceneBundle(class_name="X", code="c", engine="e", status="rendered")]
    ).to_json())
    assert b2.plan.title == p.title and len(b2.chapter_scenes) == 1
    # keyless fail-soft → coherent domain templates (per domain)
    keyless = replace(_settings(), openai_api_key=None)
    for topic, need in (("Kepler orbit", "orbit"), ("damped oscillator", "oscillator"),
                        ("simple pendulum", "pendulum"), ("Fourier wave", "wave"),
                        ("electric dipole field", "em_field")):
        lp = asyncio.run(plan_lesson(topic, keyless))
        assert lp.model_name == "deterministic-template" and 4 <= len(lp.chapters) <= 7
        kinds = {c.kind for c in lp.chapters}
        assert "interactive" in kinds and "recap" in kinds and lp.misconception
        assert any(c.key_equations for c in lp.chapters)
        got = detect_domain([lp.topic] + [c.title for c in lp.chapters], {})
        assert got == need, (topic, got)
    # An authored creative plan remains intact when optional chapter checks
    # are null; it must not silently become the generic domain template.
    import aetherlab.services.lesson_planner as lesson_planner
    authored = LessonPlan(
        title="A blackbody's color story", topic="Blackbody radiation",
        chapters=[LessonChapter(
            id="ch1", title="Why does hot metal glow?", goal="Watch the spectrum shift.",
            beats=["Heat a metal rod and reveal its spectrum."], narration="The rod glows.",
            retrieval={"q": "", "choices": ["Only one choice"], "answer": ""},
        )],
    )
    keyed = replace(_settings(), openai_api_key="test-key")
    async def no_context(*_args, **_kwargs):
        return ""
    async def authored_plan(*_args, **_kwargs):
        return authored
    with patch.object(lesson_planner, "_grounding_context", no_context), patch.object(
        lesson_planner, "_plan_remote", authored_plan
    ):
        preserved = asyncio.run(plan_lesson("Blackbody radiation", keyed))
    assert preserved.title == authored.title
    assert preserved.chapters[0].beats == authored.chapters[0].beats
    assert preserved.chapters[0].prediction is None
    assert preserved.chapters[0].retrieval is None
    cache_settings = replace(keyed, data_dir=_TMP / "nullable_lesson_cache")
    cache = _PlanCache(cache_settings)
    cache.put(preserved.topic, preserved.audience, preserved)
    cached_plan = cache.get(preserved.topic, preserved.audience)
    assert cached_plan is not None and cached_plan.title == authored.title and cached_plan.cached
    return "lesson round-trip; keyless templates coherent; nullable checks preserve/cache authored lesson (F141)"


def t_f142():
    # Phase 2: per-chapter narration timeline → .srt + fail-soft narrate_segment.
    from aetherlab.services.voiceover import _fmt_srt_time, build_srt, narrate_segment
    srt = build_srt([("Chapter one.", 4.0), ("", 1.0), ("Chapter two.", 6.5)])
    assert "00:00:00,000 --> 00:00:04,000" in srt and "Chapter two." in srt
    assert srt.count("-->") == 2  # blank consumes time but emits no cue
    assert "00:00:05,000 --> 00:00:11,500" in srt  # ch2 offset by the blank
    assert _fmt_srt_time(11.9996) == "00:00:12,000"
    res, dur = asyncio.run(narrate_segment(_TMP / "nope.mp4", "hi", _TMP))
    assert res is None and dur == 0.0  # missing video → fail-soft
    return "srt timeline (cumulative, blank-skip, ms carry) + narrate_segment fail-soft (F142)"


def t_f143():
    # Phase 3: chapter synthesis + per-chapter cache + orchestration + assembly.
    from dataclasses import replace
    from pathlib import Path

    from aetherlab.core.models import LessonChapter, SceneBundle
    from aetherlab.services.lesson_pipeline import (
        LessonPipeline,
        _chapter_key,
        _chapter_prompt,
        _chapter_solver,
        _ChapterCache,
    )
    from aetherlab.services.lesson_planner import _template_lesson
    plan = _template_lesson("Kepler orbit", "undergrad")
    ch = next(c for c in plan.chapters if c.key_equations)
    solver = _chapter_solver(ch, plan)
    assert solver.key_equations and solver.derivation_steps and solver.keywords
    assert plan.topic in _chapter_prompt(ch, plan)
    assert _chapter_key(ch, plan) != _chapter_key(plan.chapters[0], plan)

    # A tiny real mp4 to drive the chapter-cache playability test. ffmpeg comes
    # from a system binary or the optional 'narration' extra (imageio-ffmpeg); if
    # neither exists, skip the render-driven checks fail-soft (the pure chapter
    # logic above is already verified) — the app treats ffmpeg as optional too.
    import subprocess

    ff = _ffmpeg_exe()
    if not ff:
        return "chapter solver/prompt/key verified; playable-video cache checks skipped (no ffmpeg) (F143)"
    clip = _TMP / "seg.mp4"
    subprocess.run([ff, "-y", "-f", "lavfi", "-i",
                    "testsrc=size=320x240:rate=30:duration=1", "-pix_fmt", "yuv420p", str(clip)],
                   capture_output=True)
    assert clip.exists()

    cache = _ChapterCache(_TMP)
    k = _chapter_key(ch, plan)
    cache.put(k, SceneBundle(class_name="X", code="c", engine="e", status="rendered", video_path=str(clip)))
    assert cache.get(k) is not None and cache.get("missing") is None
    bad_clip = _TMP / "truncated.mp4"
    bad_clip.write_bytes(b"")
    cache.put(
        "bad",
        SceneBundle(class_name="X", code="c", engine="e", status="rendered", video_path=str(bad_clip)),
    )
    assert cache.get("bad") is None, "chapter cache must reject unplayable videos"

    # BUG-45: valid JSON arrays/scalars in cache files degrade to misses and a
    # following write reconstructs a valid object store.
    cache.path.write_text("[]", encoding="utf-8")
    assert cache.get(k) is None
    cache.put(k, SceneBundle(class_name="X", code="c", engine="e", status="rendered", video_path=str(clip)))
    assert cache.get(k) is not None

    from aetherlab.services.lesson_pipeline import _PlanCache

    plan_cache = _PlanCache(_settings())
    plan_path = plan_cache._path(plan.topic, plan.audience)
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text("null", encoding="utf-8")
    assert plan_cache.get(plan.topic, plan.audience) is None

    s = replace(_settings(), openai_api_key=None, narration_enabled=False)
    lp = LessonPipeline(s)
    # BUG-9 regression: a failed middle render must not compact chapter scenes
    # and then narrate/title the surviving next scene with the failed chapter's
    # text. Keep the original plan index with every rendered scene.
    narr_lp = LessonPipeline(replace(s, narration_enabled=True))
    one = LessonChapter(id="1", title="One", kind="scene", narration="narration one")
    three = LessonChapter(id="3", title="Three", kind="scene", narration="narration three")
    calls = []
    import aetherlab.services.voiceover as voiceover
    from aetherlab.core.language import tts_voice_for_language

    async def _fake_narrate(video, narration, out_dir, **kw):
        calls.append((Path(video).name, narration, kw.get("voice")))
        return Path(video), 1.0

    orig_narrate = voiceover.narrate_segment
    voiceover.narrate_segment = _fake_narrate
    try:
        clips, segments, titles = asyncio.run(narr_lp._narrate_chapters([
            (0, one, SceneBundle("S1", "", "e", "rendered", video_path="one.mp4")),
            (2, three, SceneBundle("S3", "", "e", "rendered", video_path="three.mp4")),
        ], _TMP, language="kk"))
    finally:
        voiceover.narrate_segment = orig_narrate
    expected_voice = tts_voice_for_language(s.tts_voice, "kk")
    assert calls == [
        ("one.mp4", "narration one", expected_voice),
        ("three.mp4", "narration three", expected_voice),
    ], calls
    assert titles == ["One", "Three"] and segments[-1][0] == "narration three"
    n = {"i": 0}
    async def _gen(request, solver, rag, settings, aspect="full"):
        return SceneBundle(class_name="AetherLabScene", code="x", engine="manim-community", status="compiled")
    async def _render(scene, settings, quality="l", brief="", **kw):
        n["i"] += 1
        scene.status = "rendered"
        scene.video_path = str(clip)
        return scene
    lp.manim.generate_scene_async = _gen
    lp.manim.render_scene_with_repair = _render
    prog = []
    bundle = asyncio.run(lp.run("Kepler orbit", progress=lambda m, d, t: prog.append(m)))
    assert bundle.status == "assembled" and bundle.video_path and Path(bundle.video_path).exists()
    assert len(bundle.chapter_scenes) >= 3 and any("Assembling" in m for m in prog)
    assert len(bundle.rendered_chapter_indexes) == len(bundle.chapter_scenes)
    return f"lesson pipeline: {len(bundle.chapter_scenes)} chapters → assembled mp4; partial-render narration aligned (F143)"


def t_f144():
    # Phase 4: RAG fact-check (fail-soft) + Phase 5 study-guide export.
    from dataclasses import replace

    from aetherlab.services.fact_check import fact_check_lesson
    from aetherlab.services.lesson_planner import _template_lesson
    from aetherlab.services.pdf import export_lesson_study_guide
    plan = _template_lesson("Kepler orbit", "undergrad")
    # Keep this export fixture explicit so it tests both the localized section
    # heading and a real equation even when the offline curriculum template changes.
    plan.language = "en"
    plan.misconception = "An orbit is not a circle at constant speed."
    plan.chapters[0].key_equations = [r"T^2 = \frac{4\pi^2}{GM}a^3"]
    keyless = replace(_settings(), openai_api_key=None)
    out = asyncio.run(fact_check_lesson(plan, keyless))
    assert out is plan and len(out.chapters) >= 3  # in-place, never raises
    tex = _TMP / "guide.tex"
    export_lesson_study_guide(plan, tex)
    body = tex.read_text(encoding="utf-8")
    assert r"\section*{Learning objectives}" in body and r"\section*{Check yourself}" in body
    assert r"\section*{Keep in mind}" in body and r"\[" in body
    return "fact-check fail-soft; study-guide .tex has objectives/chapters/questions (F144)"


def t_f145():
    # Phase 5: LessonView populates + interactive questions; LessonWorker wiring.
    from aetherlab.core.models import LessonBundle, SceneBundle
    from aetherlab.services.lesson_pipeline import _RENDERED_KINDS
    from aetherlab.services.lesson_planner import _template_lesson
    from aetherlab.ui.qt_compat import QtCore
    from aetherlab.ui.widgets import LessonView, _QuestionCard
    from aetherlab.ui.workers import LessonWorker
    plan = _template_lesson("simple pendulum", "ap")
    lv = LessonView()
    lv.set_lesson(LessonBundle(plan=plan))
    lv.set_language("en")
    assert lv._outline.count() == len(plan.chapters)
    assert lv._questions_layout.count() - 1 == len(plan.questions)
    assert lv._split.isVisibleTo(lv) and not lv._empty.isVisibleTo(lv)
    assert lv._tabs.tabText(0) == "Video"  # inline lesson player is first tab
    tabs = [lv._tabs.tabText(i) for i in range(lv._tabs.count())]
    assert "Explore" in tabs  # interactive exploration embedded
    assert lv._explore_canvas._state is not None  # canvas seeded from the domain
    got = []
    lv.chapter_seek_requested.connect(lambda s: got.append(s))
    # This assertion covers outline seek wiring, not the interactive knowledge
    # check dialog. Keep the headless test non-modal when a chapter has a cue.
    lv._show_chapter_checks = lambda _chapter_index: True
    lv._on_outline_click(lv._outline.item(0))
    assert got == [0.0] and lv._tabs.currentIndex() == 0  # click seeks + shows Video
    # BUG-9 UI regression: if a middle renderable chapter failed, offsets are
    # mapped by plan index, not by compacted rendered-list position.
    renderable_indexes = [i for i, ch in enumerate(plan.chapters) if ch.kind in _RENDERED_KINDS]
    assert len(renderable_indexes) >= 3
    partial = LessonBundle(
        plan=plan,
        chapter_scenes=[
            SceneBundle("S1", "", "e", "rendered", video_path="missing-one.mp4"),
            SceneBundle("S3", "", "e", "rendered", video_path="missing-three.mp4"),
        ],
        chapter_offsets=[4.5, 12.25],
        rendered_chapter_indexes=[renderable_indexes[0], renderable_indexes[2]],
    )
    lv.set_lesson(partial)
    assert lv._outline.item(renderable_indexes[0]).data(QtCore.Qt.ItemDataRole.UserRole) == 4.5
    assert lv._outline.item(renderable_indexes[2]).data(QtCore.Qt.ItemDataRole.UserRole) == 12.25
    mcq = next(q for q in plan.questions if q.choices)
    qc = _QuestionCard(1, mcq)
    qc.set_language("en")
    qc._answer_mcq(mcq.answer)
    assert "Correct" in qc._feedback.text()
    lv.close()
    qc.close()
    w = LessonWorker("simple pendulum", _settings())
    assert hasattr(w, "lesson_ready") and hasattr(w, "progress") and hasattr(w, "failure")
    # Main-window wiring: Learn button + lesson page + on_lesson_ready.
    from aetherlab.core.models import LessonBundle
    from aetherlab.ui.main_window import PAGE_LESSON, MainWindow
    mw = MainWindow(_settings())
    assert mw._workspace.widget(PAGE_LESSON) is mw.lesson_view
    assert hasattr(mw.command_bar, "learn_button") and callable(mw.start_lesson)
    got = []
    mw.command_bar.learn_requested.connect(lambda topic, *_args: got.append(topic))
    mw._on_sidebar_select(4)  # The tutor dock is shown on the AI Tutor destination.
    mw.show()  # child button isVisible() needs the window shown
    _app.processEvents()
    mw.command_bar.input.setText("Kepler orbit")
    mw.command_bar._learn()
    assert got == ["Kepler orbit"]
    mw.on_lesson_ready(LessonBundle(plan=_template_lesson("Kepler orbit", "undergrad")))
    assert mw._workspace.currentIndex() == PAGE_LESSON and mw.lesson_view._outline.count() >= 4
    mw.close()
    return "LessonView + MCQ + worker + main-window Learn wiring (F145); " + _lesson_ui_checks([
        "test_learn_quota_storage_refusal_keeps_exact_topic_and_retry",
        "test_learn_handoff_keeps_language_quality_and_voice",
        "test_lesson_failure_recovers_its_topic_after_a_previous_solve",
        "test_rejected_second_learn_keeps_draft_and_allowance",
        "test_learn_after_deleted_solve_worker_still_starts",
        "test_failed_lesson_rejects_late_progress_and_ready",
        "test_queued_old_lesson_cannot_replace_a_new_lesson",
        "test_deleted_lesson_wrapper_allows_another_lesson",
        "test_solve_during_lesson_cleanup_does_not_charge_or_start",
        "test_real_lesson_qthread_keeps_busy_after_result_until_cleanup_finishes",
        "test_lesson_cancel_is_requested_once_and_controls_wait_for_cleanup",
    ]) + "; " + _lesson_feedback_checks()


def _lesson_ui_checks(names, module="test_lesson_submission_behaviour"):
    import pytest

    count = 0
    for item in names:
        name, arguments = item if isinstance(item, tuple) else (item, {})
        for language in ("kk", "ru", "en"):
            with pytest.MonkeyPatch.context() as patch:
                _explicit_practice_checks(module, [
                    (name, {**arguments, "language": language, "monkeypatch": patch}),
                ])
            count += 1
    return f"{count} actual Learn UI checks; controlled lesson results, no provider/render acceptance"


def _lesson_feedback_checks():
    import pytest

    module = "test_lesson_completion_feedback"
    result = _lesson_ui_checks([
        ("test_lesson_completion_feedback_matches_available_result", {"outcome": outcome})
        for outcome in ("planned", "rendering", "error", "assembled_missing", "assembled_empty",
                        "assembled_file", "planning_error", "offline_practice_available", "unknown")
    ] + ["test_empty_cancel_keeps_previous_lesson_media_and_new_plan_clears_it",
         "test_cancelled_missing_video_keeps_previous_lesson_media",
         "test_incomplete_result_retry_does_not_replace_a_newer_draft"], module=module)
    for path_case in ("blank", "missing", "empty", "directory", "unreadable", "file"):
        with pytest.MonkeyPatch.context() as patch:
            _explicit_practice_checks(module, [
                ("test_lesson_player_replaces_or_clears_its_previous_source",
                 {"path_case": path_case, "monkeypatch": patch}),
            ])
    for status in ("planned", "rendering", "error", "owned-unrecognized-status"):
        with pytest.MonkeyPatch.context() as patch:
            _explicit_practice_checks(module, [
                ("test_nonassembled_bundle_does_not_load_a_video_path", {"status": status, "monkeypatch": patch}),
            ])
    return result + "; 10 media-path/state cases; " + _story_checks(module, (
        "test_new_lesson_clears_the_actual_qmediaplayer_source",
    ))


def t_f146():
    # P1.1: per-chapter template "aspect" makes keyless lesson chapters visually
    # distinct instead of N identical domain templates.
    from aetherlab.services.code_safety import validate_code_safety
    from aetherlab.services.scene_templates import _BUILDERS, ASPECTS, build_scene
    from aetherlab.services.scene_validation import validate_scene
    steps = ["m x'' + c x' + k x = 0", "solution decays", "energy drains away"]
    for domain in _BUILDERS:
        codes = {}
        for asp in ASPECTS:
            code = build_scene("AetherLabScene", domain, "Why does it move?",
                               "a short intuition", steps, {"damping": 0.15}, aspect=asp)
            compile(code, "<t>", "exec")  # every aspect must compile
            safe, _ = validate_code_safety(code)
            lint, _ = validate_scene(code)
            assert safe and lint, f"{domain}/{asp} failed gates"
            codes[asp] = code
        # setup/math/recap must each differ from the plain evolution render.
        assert codes["setup"] != codes["evolution"]
        assert codes["math"] != codes["evolution"]
        assert codes["recap"] != codes["evolution"]
    # "full" (the Solve path default) keeps the classic top-strip header.
    full = build_scene("AetherLabScene", "oscillator", "t", "s", steps, {}, aspect="full")
    assert "self.add(title, summary, rows)" in full
    return "aspect setup/evolution/math/recap → distinct, gate-passing scenes per domain (F146)"


def t_f147():
    # P1.1: the lesson pipeline assigns aspects by chapter role so the four
    # renderable chapters of a keyless lesson get four different compositions.
    from aetherlab.services.lesson_pipeline import _RENDERED_KINDS, _chapter_aspect
    from aetherlab.services.lesson_planner import _template_lesson
    plan = _template_lesson("the simple pendulum", "undergrad")
    aspects = {c.id: _chapter_aspect(c, plan) for c in plan.chapters}
    renderable = [c for c in plan.chapters if c.kind in _RENDERED_KINDS]
    got = [aspects[c.id] for c in renderable]
    assert got[0] == "setup", got
    assert "math" in got and "recap" in got and "evolution" in got, got
    # equation/recap kinds map deterministically regardless of position.
    eq = next(c for c in plan.chapters if c.kind == "equation_card")
    rc = next(c for c in plan.chapters if c.kind == "recap")
    assert _chapter_aspect(eq, plan) == "math" and _chapter_aspect(rc, plan) == "recap"
    return f"chapter→aspect: first={got[0]}, roles={got} (F147)"


def t_f148():
    # P1.2: produced lesson — PIL title cards + crossfaded assembly.
    import subprocess

    from aetherlab.services.assembly import _segment_starts, _xfade_chain
    from aetherlab.services.cards import render_card_png

    # BUG-6 invariant guard: seg k must start at max(sum(durs[0..k-1]) - k*d, 0)
    # exactly — the double-subtraction bug drifted later crossfades early. Check
    # 1/2/3/11-segment and zero-duration cases directly (no render needed).
    for durs, d in (
        ([5.0], 0.5), ([5.0, 4.0], 0.5), ([3.0, 4.0, 5.0], 0.5),
        ([2.2, 6, 2.2, 6, 2.2, 6, 2.2, 6, 2.2, 6, 3.0], 0.5), ([0.0, 0.0, 0.0], 0.2),
    ):
        starts = _segment_starts(durs, d)
        for k in range(len(durs)):
            assert abs(starts[k] - max(sum(durs[:k]) - k * d, 0.0)) < 1e-9, (durs, d, k, starts)
        assert all(starts[i] <= starts[i + 1] + 1e-9 for i in range(len(starts) - 1)), starts

    # BUG-105: the fade must stay shorter than the shortest segment. Keep the
    # values at sub-centisecond precision and assert the emitted FFmpeg graph
    # uses the same precision as the offsets used for chapter seeking.
    short_durations = [3.0, 0.1, 3.0]
    short_fade = min(0.5, min(short_durations) * 0.4)
    assert 0 < short_fade < min(short_durations)
    from unittest.mock import patch

    captured = {}

    async def capture_xfade_command(cmd, _timeout, **_kwargs):
        captured["cmd"] = cmd
        return True

    precise_durations = [1.111111, 1.111111, 1.111111]
    precise_fade = 0.244444
    with patch("aetherlab.services.assembly._run", capture_xfade_command):
        assert asyncio.run(_xfade_chain(
            "ffmpeg", [Path("a.mp4"), Path("b.mp4"), Path("c.mp4")],
            precise_durations, precise_fade, Path("out.mp4"), 10,
        ))
    graph = captured["cmd"][captured["cmd"].index("-filter_complex") + 1]
    starts = _segment_starts(precise_durations, precise_fade)
    assert f"duration={precise_fade:.6f}:offset={starts[1]:.6f}" in graph
    assert f"duration={precise_fade:.6f}:offset={starts[2]:.6f}" in graph
    assert f"acrossfade=d={precise_fade:.6f}" in graph
    from aetherlab.services.assembly import assemble_lesson
    png = render_card_png(_TMP / "card.png", kicker="Chapter 2",
                          title="The idea", subtitle="undergrad")
    assert png and png.exists() and png.stat().st_size > 1000

    # Real crossfade assembly needs an ffmpeg binary (optional 'narration' extra
    # or a system one). Absent both, skip render-driven assembly fail-soft — the
    # BUG-6 segment-start math and PIL cards above are already verified.
    ff = _ffmpeg_exe()
    if not ff:
        return ("produced-lesson BUG-6 segment-start math + PIL cards verified; "
                "assembly render skipped (no ffmpeg) (F148)")
    import av

    clips = []
    for i in range(2):
        c = _TMP / f"clip{i}.mp4"
        subprocess.run([ff, "-y", "-f", "lavfi", "-i",
                        "testsrc=size=480x360:rate=30:duration=2",
                        "-pix_fmt", "yuv420p", str(c)], capture_output=True)
        clips.append(c)
    # return_offsets exposes each chapter clip's readable start in the produced
    # video (BUG-8: plain-concat timing; BUG-16: crossfade-start subtitle drift).
    out, offsets = asyncio.run(assemble_lesson(
        clips, _TMP / "produced.mp4",
        lesson_title="The Pendulum", lesson_subtitle="Undergraduate level",
        chapter_titles=["The question", "The idea"], return_offsets=True))
    assert out and Path(out).exists()
    assert len(offsets) == 2, offsets
    # Chapter 1 must start AFTER the 3s intro card + its chapter card — never 0
    # (a plain concat would have put it at 0), and offsets must be increasing.
    assert offsets[0] > 4.6, f"ch1 offset {offsets[0]} should clear the title-card crossfade"
    assert offsets[1] > offsets[0], offsets
    with av.open(str(out)) as cont:
        vs = cont.streams.video[0]
        dur = float(cont.duration) / 1e6 if cont.duration else 0
        # intro + 2*(card+clip) + end = 6 segments; must exceed the 4s of raw
        # clips, proving the cards were inserted.
        assert vs.width == 1280 and vs.height == 720
        assert dur > 5.0, dur
        # Every chapter offset lands within the real video timeline.
        assert offsets[-1] < dur, (offsets, dur)
    return (f"produced lesson: cards + crossfades → {dur:.1f}s 1280x720; "
            f"chapter offsets {[round(o,1) for o in offsets]} past intro (F148)")


def t_f149():
    # P1.3: LessonPlan cache keyed by topic+audience (re-open is instant) +
    # regenerate bypass; keyed distinctly per audience.
    from dataclasses import replace

    from aetherlab.services.lesson_pipeline import _PlanCache, _topic_id
    from aetherlab.services.lesson_planner import _template_lesson
    s = replace(_settings(), openai_api_key=None)
    pc = _PlanCache(s)
    assert pc.get("the wave equation", "undergrad") is None  # cold
    plan = _template_lesson("the wave equation", "undergrad")
    pc.put("the wave equation", "undergrad", plan)
    hit = pc.get("the wave equation", "undergrad")
    assert hit is not None and hit.cached and len(hit.chapters) == len(plan.chapters)
    # case/space-insensitive key, audience-sensitive.
    assert pc.get("  THE WAVE EQUATION  ", "undergrad") is not None
    assert pc.get("the wave equation", "high_school") is None
    assert _topic_id("X", "ap") != _topic_id("X", "undergrad")
    return "plan cache: warm hit reused, audience-scoped, regenerate-bypassable (F149)"


def t_f150():
    # P2: Learn is cancellable — cancel_check stops the pipeline and returns a
    # "cancelled" bundle; the worker exposes cancel(); the UI stays non-blank.
    from dataclasses import replace

    from aetherlab.core.models import SceneBundle
    from aetherlab.services.lesson_pipeline import LessonPipeline
    from aetherlab.ui.workers import LessonWorker
    s = replace(_settings(), openai_api_key=None, narration_enabled=False)
    lp = LessonPipeline(s)
    calls = {"n": 0}
    async def _gen(request, solver, rag, settings, aspect="full"):
        return SceneBundle(class_name="AetherLabScene", code="x",
                           engine="manim-community", status="compiled")
    async def _render(scene, settings, quality="l", brief="", **kw):
        calls["n"] += 1
        scene.status = "rendered"
        scene.video_path = ""
        return scene
    lp.manim.generate_scene_async = _gen
    lp.manim.render_scene_with_repair = _render
    # Cancel immediately: no chapter should render, bundle is "cancelled".
    bundle = asyncio.run(lp.run("Kepler orbit", regenerate=True,
                                cancel_check=lambda: True))
    assert bundle.status == "cancelled", bundle.status
    assert calls["n"] == 0, calls
    # Worker exposes a cancel() that flips its event.
    w = LessonWorker("x", s, regenerate=True)
    assert hasattr(w, "cancel") and not w._cancel.is_set()
    w.cancel()
    assert w._cancel.is_set()

    # BUG-56: cancellation requested after a chapter starts reaches the active
    # render instead of waiting for the full Manim timeout/current chapter.
    import threading

    from aetherlab.core.proc import ProcessCancelledError

    mid_render_cancel = threading.Event()

    async def _cancel_during_render(scene, settings, quality="l", brief="", **kw):
        calls["n"] += 1
        check_cancel = kw.get("cancel_check")
        assert callable(check_cancel)
        mid_render_cancel.set()
        if check_cancel():
            raise ProcessCancelledError("cancelled active lesson render")
        return scene

    lp.manim.render_scene_with_repair = _cancel_during_render
    bundle2 = asyncio.run(
        lp.run(
            "Kepler orbit",
            regenerate=True,
            max_concurrent=1,
            cancel_check=mid_render_cancel.is_set,
        )
    )
    assert bundle2.status == "cancelled" and calls["n"] >= 1

    # BUG-106: cancellation during lesson narration/assembly must still return
    # a cancelled bundle and must not let the render complete in the background.
    import aetherlab.services.lesson_pipeline as lesson_pipeline
    import aetherlab.services.voiceover as voiceover
    from aetherlab.core.models import LessonChapter, LessonPlan

    cancel_plan = LessonPlan(
        title="Cancel test", topic="cancel test", audience="high_school",
        chapters=[LessonChapter(
            id="only", title="Only chapter", kind="scene", narration="Say this."
        )],
    )
    original_curated = lesson_pipeline.curated_ent_lesson
    original_narrate = voiceover.narrate_segment
    lesson_pipeline.curated_ent_lesson = lambda _topic, _language: cancel_plan
    narration_cancel = threading.Event()
    narration_lp = LessonPipeline(replace(s, narration_enabled=True))

    async def _rendered_chapter(*_args, **_kwargs):
        return SceneBundle("S", "", "e", "rendered", video_path="chapter.mp4")

    async def _cancel_during_narration(*_args, cancel_check=None, **_kwargs):
        assert callable(cancel_check)
        narration_cancel.set()
        raise ProcessCancelledError("cancelled narration subprocess")

    narration_lp._render_chapter = _rendered_chapter
    voiceover.narrate_segment = _cancel_during_narration
    try:
        narration_bundle = asyncio.run(narration_lp.run(
            "cancel test", cancel_check=narration_cancel.is_set,
        ))
    finally:
        lesson_pipeline.curated_ent_lesson = original_curated
        voiceover.narrate_segment = original_narrate
    assert narration_bundle.status == "cancelled", narration_bundle.status

    assembly_cancel = threading.Event()
    assembly_lp = LessonPipeline(s)
    assembly_lp._render_chapter = _rendered_chapter

    async def _narrated(*_args, **_kwargs):
        return [Path("chapter.mp4")], [("Say this.", 1.0)], ["Only chapter"]

    async def _cancel_during_assembly(*_args, cancel_check=None, **_kwargs):
        assert callable(cancel_check)
        assembly_cancel.set()
        raise ProcessCancelledError("cancelled assembly subprocess")

    assembly_lp._narrate_chapters = _narrated
    assembly_lp._assemble = _cancel_during_assembly
    lesson_pipeline.curated_ent_lesson = lambda _topic, _language: cancel_plan
    try:
        assembly_bundle = asyncio.run(assembly_lp.run(
            "cancel test", cancel_check=assembly_cancel.is_set,
        ))
    finally:
        lesson_pipeline.curated_ent_lesson = original_curated
    assert assembly_bundle.status == "cancelled", assembly_bundle.status

    # Cancellation removes staged FFmpeg output without destroying a previous
    # good lesson/narration at the destination path.
    from unittest.mock import patch

    import aetherlab.core.proc as process_helpers
    from aetherlab.services.assembly import _run as run_assembly_ffmpeg
    from aetherlab.services.voiceover import _run_ffmpeg as run_voiceover_ffmpeg

    def cancelled_ffmpeg(argv, **_kwargs):
        Path(argv[-1]).write_bytes(b"partial")
        raise ProcessCancelledError("cancelled after writing staged bytes")

    for runner, filename in (
        (run_assembly_ffmpeg, "prior-lesson.mp4"),
        (run_voiceover_ffmpeg, "prior-narration.mp4"),
    ):
        destination = _TMP / filename
        destination.write_bytes(b"prior-good-output")
        with patch.object(process_helpers, "run_process_tree", cancelled_ffmpeg):
            try:
                asyncio.run(runner(
                    ["ffmpeg", "-y", str(destination)], 10,
                    cancel_check=lambda: False,
                ))
                raise AssertionError("cancelled FFmpeg unexpectedly completed")
            except ProcessCancelledError:
                pass
        assert destination.read_bytes() == b"prior-good-output"
        assert not list(_TMP.glob(f".{destination.stem}.*.tmp{destination.suffix}"))
    return "Learn cancellation reaches active render, narration, and assembly (BUG-56/106); " + _lesson_ui_checks([
        "test_first_cancelled_lesson_returns_to_empty_page_with_topic",
        "test_empty_cancelled_lesson_preserves_previous_completed_lesson",
        "test_cancelled_lesson_with_video_keeps_its_partial_route",
        "test_cancelled_lesson_ignores_late_progress_until_partial_result",
        ("test_lesson_recovery_preserves_a_newer_draft", {"terminal": "failure"}),
        ("test_lesson_recovery_preserves_a_newer_draft", {"terminal": "cancelled"}),
    ])


def t_f151():
    # Innovation: partial lessons make skipped renderable chapters visible in
    # the outline instead of silently mapping them to a surviving clip.
    from aetherlab.core.models import LessonBundle, SceneBundle
    from aetherlab.services.lesson_pipeline import _RENDERED_KINDS
    from aetherlab.services.lesson_planner import _template_lesson
    from aetherlab.ui.qt_compat import QtCore
    from aetherlab.ui.widgets import LessonView

    plan = _template_lesson("Kepler orbit", "undergrad")
    renderable_indexes = [i for i, ch in enumerate(plan.chapters) if ch.kind in _RENDERED_KINDS]
    assert len(renderable_indexes) >= 3
    bundle = LessonBundle(
        plan=plan,
        chapter_scenes=[
            SceneBundle("S1", "", "e", "rendered", video_path="missing-one.mp4"),
            SceneBundle("S3", "", "e", "rendered", video_path="missing-three.mp4"),
        ],
        chapter_offsets=[3.0, 9.0],
        rendered_chapter_indexes=[renderable_indexes[0], renderable_indexes[2]],
    )
    lv = LessonView()
    lv.set_lesson(bundle)
    skipped = lv._outline.item(renderable_indexes[1])
    assert "not rendered" in skipped.text().lower(), skipped.text()
    assert "did not render" in skipped.toolTip().lower()
    assert lv._outline.item(renderable_indexes[2]).data(QtCore.Qt.ItemDataRole.UserRole) == 9.0
    lv.close()
    return "partial lessons mark skipped chapters and keep surviving offsets mapped (F151)"


def t_f152():
    # RenderBackend seam: default local, explicit cloud, auto threshold routing.
    from dataclasses import replace

    from aetherlab.core.models import SceneBundle
    from aetherlab.services.render_backend import (
        CloudRenderBackend,
        LocalRenderBackend,
        cloud_job_id,
        render_fps_for,
        render_timeout_for,
        select_backend,
    )
    s = _settings()
    assert isinstance(select_backend(s, "light", "l"), LocalRenderBackend)
    cloud = replace(s, render_mode="cloud", github_repo="owner/render", github_token="ghp_" + "x" * 24)
    assert isinstance(select_backend(cloud, "light", "l"), CloudRenderBackend)
    auto = replace(cloud, render_mode="auto", cloud_render_threshold=3.0)
    assert isinstance(select_backend(auto, "self.play(FadeIn(x))", "l"), LocalRenderBackend)
    heavy = "self.play(FadeIn(x))\n" * 80
    assert isinstance(select_backend(auto, heavy, "h"), CloudRenderBackend)
    scene = SceneBundle("AetherLabScene", "code", "manim-community", "compiled")
    assert cloud_job_id(scene, quality="l", fps=30) != cloud_job_id(scene, quality="h", fps=30)
    assert render_fps_for(heavy, "h") == 30
    stale_long = replace(cloud, cloud_render_timeout=1800)
    assert render_timeout_for("light", "l", stale_long) == 420
    return "backend selection local/cloud/auto + stable cloud job ids (F152)"


def t_f153():
    with _isolated_app_config_dir("f153"):
        return _t_f153_body()


def _t_f153_body():
    # Settings round-trip for cloud render config; token is config-only and masked elsewhere.
    from aetherlab.core.settings import app_config_path, load_settings, save_app_config
    save_app_config({
        "render_mode": "auto",
        "cloud_provider": "github_actions",
        "github_repo": "owner/render",
        "github_token": "github_pat_TESTTOKEN",
        "github_workflow": "render.yml",
        "github_branch": "renders",
        "cloud_render_threshold": "3.5",
        "cloud_poll_seconds": "4",
        "cloud_render_timeout": "123",
    })
    s = load_settings()
    assert s.render_mode == "auto" and s.github_repo == "owner/render"
    assert s.github_token == "github_pat_TESTTOKEN"
    assert s.cloud_render_threshold == 3.5 and s.cloud_poll_seconds == 4
    assert s.cloud_render_timeout == 123
    _assert_test_config_path(app_config_path()).unlink(missing_ok=True)
    keys = (
        "AETHERLAB_OPENAI_API_KEY", "AETHERLAB_OPENAI_BASE_URL", "AETHERLAB_LLM_MODEL",
        "AETHERLAB_PROVIDER", "OPENAI_API_KEY", "OPENAI_BASE_URL", "GPT_API_KEY",
        "GPT_BASE_URL", "DASHSCOPE_API_KEY", "LLM_BASE_URL", "MANIM_MODEL",
        "GPT_MODEL", "CHAT_MODEL",
        "AETHERLAB_RENDER_MODE", "AETHERLAB_RENDER_REPO", "AETHERLAB_GITHUB_WORKFLOW",
        "AETHERLAB_GITHUB_BRANCH", "AETHERLAB_CLOUD_POLL_SECONDS",
        "AETHERLAB_CLOUD_RENDER_TIMEOUT", "CLOUD_RENDER_ENABLED", "CLOUD_RENDER_REPO",
        "CLOUD_RENDER_WORKFLOW", "CLOUD_RENDER_BRANCH", "CLOUD_RENDER_TIMEOUT",
        "CLOUD_RENDER_POLL", "AETHERLAB_DISABLE_LEGACY_ENV", "AETHERLAB_LEGACY_ENV_PATH",
        "MANIM_BOT_ENV_PATH",
    )
    saved = {k: os.environ.pop(k, None) for k in keys}
    try:
        os.environ["CLOUD_RENDER_ENABLED"] = "true"
        os.environ["CLOUD_RENDER_REPO"] = "owner/worker"
        os.environ["CLOUD_RENDER_WORKFLOW"] = "render.yml"
        os.environ["CLOUD_RENDER_BRANCH"] = "main"
        os.environ["CLOUD_RENDER_TIMEOUT"] = "456"
        os.environ["CLOUD_RENDER_POLL"] = "9"
        alias = load_settings()
        assert alias.render_mode == "auto" and alias.github_repo == "owner/worker"
        assert alias.github_workflow == "render.yml" and alias.github_branch == "main"
        assert alias.cloud_render_timeout == 456 and alias.cloud_poll_seconds == 9
        for k in ("CLOUD_RENDER_ENABLED", "CLOUD_RENDER_REPO", "CLOUD_RENDER_WORKFLOW",
                  "CLOUD_RENDER_BRANCH", "CLOUD_RENDER_TIMEOUT", "CLOUD_RENDER_POLL"):
            os.environ.pop(k, None)
        legacy = _TMP / "manim-bot.env"
        legacy.write_text(
            "\n".join([
                "CLOUD_RENDER_ENABLED=true",
                "CLOUD_RENDER_REPO=owner/legacy-worker",
                "CLOUD_RENDER_WORKFLOW=.github/workflows/render.yml",
                "CLOUD_RENDER_BRANCH=main",
                "CLOUD_RENDER_TIMEOUT=789",
                "CLOUD_RENDER_POLL=11",
                "GPT_BASE_URL=https://legacy.example/v1",
                "GPT_API_KEY=legacy-test-token",
                "MANIM_MODEL=qwen-legacy",
            ]),
            encoding="utf-8",
        )
        os.environ["AETHERLAB_DISABLE_LEGACY_ENV"] = "0"
        os.environ["AETHERLAB_LEGACY_ENV_PATH"] = str(legacy)
        migrated = load_settings()
        assert migrated.render_mode == "auto" and migrated.github_repo == "owner/legacy-worker"
        assert migrated.github_workflow == "render.yml" and migrated.github_branch == "main"
        assert migrated.cloud_render_timeout == 789 and migrated.cloud_poll_seconds == 11
        assert migrated.openai_base_url == "https://legacy.example/v1"
        assert migrated.llm_model == "qwen-legacy" and migrated.openai_api_key
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
    return "cloud settings persist; env + legacy .env CLOUD_RENDER_* aliases load (F153)"


def t_f154():
    # Cloud backend fully stubbed: success downloads MP4; identical scene reuses cache.
    import io
    import subprocess
    import zipfile
    from dataclasses import replace

    import aetherlab.services.render_backend as rb
    from aetherlab.core.models import SceneBundle
    from aetherlab.core.proc import subprocess_kwargs
    from aetherlab.services.render_backend import CloudRenderBackend, GitHubActionsClient

    ffmpeg = _ffmpeg_exe()
    assert ffmpeg, "FFmpeg is needed to verify a real cloud-artifact fixture"
    fixture = _TMP / "f154-cloud-artifact.mp4"
    subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
         "-i", "color=c=blue:s=854x480:r=30:d=0.2", "-pix_fmt", "yuv420p", str(fixture)],
        check=True, capture_output=True, timeout=20, **subprocess_kwargs(),
    )
    fixture_bytes = fixture.read_bytes()

    class FakeClient:
        def __init__(self):
            self.dispatches = 0
            self.provisioned = 0
            self.name = ""
        # BUG-16: the workflow must be installed before dispatch or GitHub 404s.
        def default_branch(self): return "main"
        def ensure_workflow(self, *, workflow, branch):
            self.provisioned += 1
            return False
        def ensure_branch(self, branch): pass
        def put_file(self, path, content, *, branch, message): pass
        def dispatch(self, **kw):
            # Provisioning must have happened before the first dispatch.
            assert self.provisioned >= 1, "workflow not provisioned before dispatch"
            self.dispatches += 1
            return 10
        def get_run(self, run_id, *, job_id, branch):
            return {"id": 10, "status": "completed", "conclusion": "success",
                    "html_url": "https://github.com/owner/render/actions/runs/10"}
        def find_run_artifact(self, run_id, name):
            self.name = name
            return {"id": 77, "name": name,
                    "archive_download_url": "https://api.github.com/zip?token=do-not-persist"}
        def get_artifact(self, artifact_id):
            return {"id": artifact_id, "name": self.name, "expired": False}
        def find_repo_artifact(self, name):
            return None
        def download_artifact_zip(self, artifact_id):
            bio = io.BytesIO()
            with zipfile.ZipFile(bio, "w") as zf:
                zf.writestr(self.name, fixture_bytes)
            return bio.getvalue()
        def download_run_logs(self, run_id):
            return ""

    s = replace(_settings(), render_mode="cloud", github_repo="owner/render",
                github_token="ghp_" + "x" * 24)
    path_workflow = replace(s, github_workflow=".github/workflows/render.yml")
    assert GitHubActionsClient.from_settings(path_workflow).workflow == "render.yml"
    client = FakeClient()
    backend = CloudRenderBackend(s, client=client)
    scene = SceneBundle("AetherLabScene", "from manim import *\nclass AetherLabScene(Scene):\n pass\n",
                        "manim-community", "compiled")
    out = asyncio.run(backend.render(scene, quality="l", settings=s, timeout=30))
    assert out.status == "rendered" and Path(out.video_path).exists(), out.diagnostics
    from aetherlab.services.render_ledger import RenderJobLedger
    success_row = RenderJobLedger(s.data_dir / "render_ledger.json").list()[0]
    statuses = [event["status"] for event in success_row["timeline"]]
    assert all(status in statuses for status in
               ("queued", "in_progress", "completed", "artifact_downloaded", "rendered")), statuses
    assert success_row["fps"] > 0
    assert success_row["run_url"] == "https://github.com/owner/render/actions/runs/10"
    assert success_row["artifact_url"] == "https://github.com/owner/render/actions/runs/10/artifacts/77"
    assert "token=do-not-persist" not in json.dumps(success_row)
    scene2 = SceneBundle("AetherLabScene", scene.code, "manim-community", "compiled")
    out2 = asyncio.run(backend.render(scene2, quality="l", settings=s, timeout=30))
    assert out2.status == "rendered" and client.dispatches == 1

    class RunLookupClient(GitHubActionsClient):
        def __init__(self, runs):
            super().__init__("owner", "render", "token")
            self.runs = runs
        def _request(self, method, path, payload=None, *, raw=False):
            if path.startswith("/repos/owner/render/actions/runs?"):
                return {"workflow_runs": self.runs}
            raise AssertionError(path)

    wrong = RunLookupClient([{"id": 1, "status": "completed", "display_title": "AetherLab render old"}])
    assert wrong.get_run(None, job_id="wanted", branch="renders") == {"status": "queued"}
    right = RunLookupClient([{"id": 2, "status": "completed", "display_title": "AetherLab render wanted"}])
    assert right.get_run(None, job_id="wanted", branch="renders")["id"] == 2
    redirect_src = inspect.getsource(GitHubActionsClient._download_redirecting_raw)
    assert "_NoRedirect" in redirect_src and "urlopen(signed" in redirect_src

    # BUG-16 regression: provision_render_repo installs the dispatchable workflow
    # on BOTH the default branch and the render branch, is idempotent, and gives a
    # clear message when the token lacks the 'workflow' scope (403).
    import urllib.error

    from aetherlab.services.render_backend import (
        RENDER_WORKFLOW_YAML,
        provision_render_repo,
    )

    class ProvisionClient(GitHubActionsClient):
        def __init__(self, existing=None, forbid=False):
            super().__init__("owner", "render", "token")
            self.files = dict(existing or {})   # branch -> {path: content}
            self.branches = {"main"}
            self.writes = []
            self.forbid = forbid
        def default_branch(self): return "main"
        def file_content(self, path, *, branch):
            return self.files.get(branch, {}).get(path)
        def ensure_branch(self, branch): self.branches.add(branch)
        def put_file(self, path, content, *, branch, message):
            if self.forbid:
                raise urllib.error.HTTPError("u", 403, "Forbidden", {}, None)
            self.files.setdefault(branch, {})[path] = content
            self.writes.append((branch, path))

    wf_path = ".github/workflows/render.yml"
    fresh = ProvisionClient()
    provision_render_repo(fresh, branch="renders", workflow="render.yml")
    assert (fresh.files.get("main", {}).get(wf_path) or "").strip() == RENDER_WORKFLOW_YAML.strip()
    assert (fresh.files.get("renders", {}).get(wf_path) or "").strip() == RENDER_WORKFLOW_YAML.strip()
    assert "renders" in fresh.branches
    # Idempotent: a repo that already has the exact workflow writes nothing.
    have = {b: {wf_path: RENDER_WORKFLOW_YAML} for b in ("main", "renders")}
    warm = ProvisionClient(existing=have)
    warm.branches.add("renders")
    provision_render_repo(warm, branch="renders", workflow="render.yml")
    assert warm.writes == [], warm.writes
    # Missing 'workflow' scope surfaces an actionable message, not a raw 403.
    denied = ProvisionClient(forbid=True)
    try:
        provision_render_repo(denied, branch="renders", workflow="render.yml")
        raise AssertionError("expected a scope error")
    except RuntimeError as exc:
        assert "workflow" in str(exc).lower() and "scope" in str(exc).lower()

    # manim-bot used GitHub CLI auth instead of a pasted token. AetherLab should
    # accept that runtime token fallback when Settings has no saved token.
    orig_cli_token = rb._github_cli_token
    rb._github_cli_token = lambda: "ghp_" + "z" * 24
    try:
        cli_auth = replace(s, github_token="")
        assert CloudRenderBackend(cli_auth).available()[0]
        assert GitHubActionsClient.from_settings(cli_auth).token.startswith("ghp_")
    finally:
        rb._github_cli_token = orig_cli_token

    from aetherlab.services.render_backend import CloudRenderManifest

    malformed_manifest_path = _TMP / "cloud_manifest_wrong_shape.json"
    malformed_manifest_path.write_text("[]", encoding="utf-8")
    malformed_manifest = CloudRenderManifest(malformed_manifest_path)
    assert malformed_manifest.get("missing") is None
    malformed_manifest.put("recovered", {"status": "rendered"})
    assert malformed_manifest.get("recovered") == {"status": "rendered"}

    # A missing GitHub workflow scope is visible as an actionable ledger state.
    scope_settings = replace(s, data_dir=_TMP / "cloud_scope")
    class ScopeClient(FakeClient):
        def dispatch(self, **kw):
            raise urllib.error.HTTPError("url", 403, "Forbidden", {}, None)
    scope_scene = SceneBundle("ScopeScene", scene.code, "manim-community", "compiled")
    asyncio.run(CloudRenderBackend(scope_settings, client=ScopeClient()).render(
        scope_scene, quality="l", settings=scope_settings, timeout=30, variant="scope",
    ))
    scope_row = RenderJobLedger(scope_settings.data_dir / "render_ledger.json").list()[0]
    assert scope_row["status"] == "action_required" and "workflow" in scope_row["log_tail"].lower()

    # GitHub 429 is retried and leaves a visible rate-limit/resumed timeline.
    rate_settings = replace(s, data_dir=_TMP / "cloud_rate_limit")
    class RateLimitedClient(FakeClient):
        def __init__(self):
            super().__init__()
            self.polls = 0
        def get_run(self, run_id, *, job_id, branch):
            self.polls += 1
            if self.polls == 1:
                raise urllib.error.HTTPError("url", 429, "Too Many Requests", {"Retry-After": "1"}, None)
            return super().get_run(run_id, job_id=job_id, branch=branch)
    rate_client = RateLimitedClient()
    original_sleep = rb.asyncio.sleep
    async def no_wait(_seconds):
        return None
    rb.asyncio.sleep = no_wait
    try:
        rate_scene = SceneBundle("RateScene", scene.code, "manim-community", "compiled")
        rate_out = asyncio.run(CloudRenderBackend(rate_settings, client=rate_client).render(
            rate_scene, quality="l", settings=rate_settings, timeout=30, variant="rate",
        ))
    finally:
        rb.asyncio.sleep = original_sleep
    rate_row = RenderJobLedger(rate_settings.data_dir / "render_ledger.json").list()[0]
    rate_statuses = [event["status"] for event in rate_row["timeline"]]
    assert rate_out.status == "rendered" and rate_client.polls == 2
    assert "rate_limited" in rate_statuses and rate_statuses.count("in_progress") >= 2

    # Cancellation after dispatch records the terminal state and cancels the run.
    cancel_settings = replace(s, data_dir=_TMP / "cloud_cancel")
    class CancelClient(FakeClient):
        def __init__(self):
            super().__init__()
            self.cancelled = []
        def cancel_run(self, run_id):
            self.cancelled.append(run_id)
    cancel_client = CancelClient()
    cancel_scene = SceneBundle("CancelScene", scene.code, "manim-community", "compiled")
    from aetherlab.core.proc import ProcessCancelledError
    try:
        asyncio.run(CloudRenderBackend(cancel_settings, client=cancel_client).render(
            cancel_scene, quality="l", settings=cancel_settings, timeout=30,
            variant="cancel", cancel_check=lambda: cancel_client.dispatches > 0,
        ))
        raise AssertionError("expected cloud cancellation")
    except ProcessCancelledError:
        pass
    cancel_row = RenderJobLedger(cancel_settings.data_dir / "render_ledger.json").list()[0]
    assert cancel_row["status"] == "cancelled" and cancel_client.cancelled == [10]
    return "cloud success/cache/provisioning + gh auth + signed-artifact download (F154)"


def t_f155():
    # Explicit Cloud mode does not start a heavy local render after cloud failure.
    from dataclasses import replace

    import aetherlab.services.render_backend as rb
    from aetherlab.core.models import SceneBundle
    from aetherlab.services.manim_runtime import ManimRuntime

    calls = {"local": 0}
    class FakeLocal:
        name = "local"
        def available(self): return True, "ok"
        async def render(self, scene, *, quality, settings, timeout, progress=None, **kwargs):
            calls["local"] += 1
            scene.status = "rendered"
            scene.video_path = str(_TMP / "fake.mp4")
            return scene

    orig = rb.LocalRenderBackend
    orig_cli_token = rb._github_cli_token
    rb.LocalRenderBackend = FakeLocal
    rb._github_cli_token = lambda: ""
    try:
        s = replace(_settings(), render_mode="cloud", github_repo="owner/render", github_token="")
        scene = SceneBundle("AetherLabScene", "code", "manim-community", "compiled")
        out = asyncio.run(ManimRuntime(s)._render_once(scene, s, "l"))
    finally:
        rb.LocalRenderBackend = orig
        rb._github_cli_token = orig_cli_token
    assert out.status == rb.CLOUD_UNAVAILABLE and calls["local"] == 0
    assert any("GitHub token" in d for d in out.diagnostics)

    # BUG-37: exhausting the cloud poll budget cancels the remote run. In
    # explicit Cloud mode it remains unavailable rather than rendering locally.
    class TimeoutClient:
        def __init__(self): self.cancelled = []
        def find_repo_artifact(self, name): return None
        def default_branch(self): return "main"
        def ensure_workflow(self, *, workflow, branch): return False
        def ensure_branch(self, branch): pass
        def put_file(self, path, content, *, branch, message): pass
        def dispatch(self, **kw): return 91
        def get_run(self, run_id, *, job_id, branch):
            return {"id": 91, "status": "queued"}
        def cancel_run(self, run_id): self.cancelled.append(run_id)

    timeout_client = TimeoutClient()
    orig_select = rb.select_backend
    orig_timeout = rb.render_timeout_for
    rb.LocalRenderBackend = FakeLocal
    rb.select_backend = lambda settings, code, quality: rb.CloudRenderBackend(
        settings, client=timeout_client
    )
    rb.render_timeout_for = lambda code, quality, settings: 0
    try:
        calls["local"] = 0
        s2 = replace(
            _settings(), render_mode="cloud", github_repo="owner/render",
            github_token="ghp_" + "x" * 24, data_dir=_TMP / "cloud_timeout",
        )
        scene2 = SceneBundle(
            "AetherLabScene",
            "from manim import *\nclass AetherLabScene(Scene):\n    pass\n",
            "manim-community", "compiled",
        )
        out2 = asyncio.run(ManimRuntime(s2)._render_once(scene2, s2, "l"))
    finally:
        rb.LocalRenderBackend = orig
        rb.select_backend = orig_select
        rb.render_timeout_for = orig_timeout
    assert out2.status == rb.CLOUD_UNAVAILABLE and calls["local"] == 0
    assert timeout_client.cancelled == [91]
    assert any("timed out" in d.lower() and "fallback was skipped" in d.lower() for d in out2.diagnostics)

    # Auto mode records the complete cloud-failure -> local-render fallback row.
    class FailingCloudClient:
        def find_repo_artifact(self, name): return None
        def default_branch(self): return "main"
        def ensure_workflow(self, *, workflow, branch): return False
        def ensure_branch(self, branch): pass
        def put_file(self, path, content, *, branch, message): pass
        def dispatch(self, **kw): raise RuntimeError("stub cloud dispatch failure")

    fallback_settings = replace(
        _settings(), render_mode="auto", github_repo="owner/render",
        github_token="test-token", data_dir=_TMP / "cloud_local_fallback",
    )
    fallback_client = FailingCloudClient()
    rb.LocalRenderBackend = FakeLocal
    rb.select_backend = lambda settings, code, quality: rb.CloudRenderBackend(
        settings, client=fallback_client
    )
    try:
        calls["local"] = 0
        fallback_scene = SceneBundle(
            "FallbackScene",
            "from manim import *\nclass FallbackScene(Scene):\n    pass\n",
            "manim-community", "compiled",
        )
        fallback_out = asyncio.run(
            ManimRuntime(fallback_settings)._render_once(fallback_scene, fallback_settings, "l")
        )
    finally:
        rb.LocalRenderBackend = orig
        rb.select_backend = orig_select
    from aetherlab.services.render_ledger import RenderJobLedger
    fallback_row = RenderJobLedger(
        fallback_settings.data_dir / "render_ledger.json"
    ).list()[0]
    assert fallback_out.status == "rendered" and calls["local"] == 1
    assert fallback_row["status"] == "fallback_local"
    assert "dispatch failure" in fallback_row["fallback_reason"]
    assert fallback_row["final_path"] == fallback_out.video_path
    return "explicit Cloud mode stops on unavailable/timeout without local fallback (F155)"


def t_f156():
    # Security guard refuses likely secrets and masks tokens in diagnostics.
    from aetherlab.services.render_backend import _mask, scan_cloud_payload
    assert scan_cloud_payload("OPENAI_API_KEY='sk-secret'") is not None
    assert scan_cloud_payload("from manim import *\nText('Energy')") is None
    masked = _mask("failed with github_pat_ABCDEF1234567890 and sk-abcdef1234567890")
    assert "github_pat_ABC" not in masked and "sk-abcdef" not in masked
    assert "<redacted>" in masked
    return "cloud payload secret scan + token masking (F156)"


def t_f157():
    # Settings dialog exposes cloud controls; Scene panel shows backend chip.
    import threading
    import time
    from dataclasses import replace

    import aetherlab.services.render_backend as render_backend
    from aetherlab.core.models import SceneBundle
    from aetherlab.ui.main_window import SettingsDialog
    from aetherlab.ui.widgets import SimulationPanel

    s = replace(_settings(), render_mode="auto", github_repo="owner/render",
                github_token="ghp_" + "x" * 24,
                github_oauth_client_id="test-device-client")
    d = SettingsDialog(s)
    vals = d.get_settings()
    assert vals["render_mode"] == "auto" and vals["github_repo"] == "owner/render"

    cloud_started = threading.Event()
    cloud_release = threading.Event()
    original_available = render_backend.CloudRenderBackend.available

    def blocking_available(_backend):
        cloud_started.set()
        assert cloud_release.wait(2.0)
        return False, "Cloud unavailable in regression"

    render_backend.CloudRenderBackend.available = blocking_available
    try:
        before = time.perf_counter()
        d._test_cloud_render()
        elapsed = time.perf_counter() - before
        assert elapsed < 0.2 and cloud_started.wait(0.5)
        assert not d._cloud_test_btn.isEnabled()
        cloud_release.set()
        if d._cloud_task:
            d._cloud_task.wait(3.0)  # deterministic join, not a slow-runner deadline
        _app.processEvents()          # deliver the queued finished/result signals
        assert d._cloud_test_btn.isEnabled()
        assert "regression" in d._cloud_result.text()
    finally:
        cloud_release.set()
        render_backend.CloudRenderBackend.available = original_available

    device_started = threading.Event()
    device_release = threading.Event()
    original_device_code = render_backend.request_github_device_code

    def blocking_device_code(_client_id):
        device_started.set()
        assert device_release.wait(2.0)
        return {}

    render_backend.request_github_device_code = blocking_device_code
    try:
        before = time.perf_counter()
        d._get_github_token()
        elapsed = time.perf_counter() - before
        assert elapsed < 0.2 and device_started.wait(0.5)
        assert not d._get_token_btn.isEnabled()
        device_release.set()
        if d._github_task:
            d._github_task.wait(3.0)  # deterministic join, not a slow-runner deadline
        _app.processEvents()
        assert d._get_token_btn.isEnabled()
        assert "failed" in d._cloud_result.text().lower()
    finally:
        device_release.set()
        render_backend.request_github_device_code = original_device_code

    connection_src = inspect.getsource(SettingsDialog._test_connection)
    cloud_src = inspect.getsource(SettingsDialog._test_cloud_render)
    github_src = inspect.getsource(SettingsDialog._get_github_token)
    assert "BackgroundTask" in connection_src and "processEvents" not in connection_src
    assert "BackgroundTask" in cloud_src and "processEvents" not in cloud_src
    assert "cancel.wait(interval)" in github_src and 'error == "slow_down"' in github_src
    assert "interval + 5" in github_src and "time.sleep" not in github_src
    d.close()
    panel = SimulationPanel()
    scene = SceneBundle("AetherLabScene", "code", "manim-community", "rendered",
                        diagnostics=["Rendered via GitHub Actions (abc)."],
                        video_path=str(_TMP / "fake.mp4"))
    panel.set_scene_bundle(scene)
    assert panel._backend_chip.text() == "Cloud"
    panel.close()
    return "provider/cloud/device actions backgrounded + backend chip (BUG-53, F157)"


def t_f158():
    # Workflow and docs ship the concrete GitHub Actions render worker.
    from aetherlab.services.render_backend import RENDER_WORKFLOW_YAML
    wf = Path(".github/workflows/render.yml").read_text(encoding="utf-8")
    doc = Path("docs/CLOUD_RENDERING.md").read_text(encoding="utf-8")
    assert "workflow_dispatch" in wf and "manim==0.21.0" in wf
    assert "jobs/<job_id>.py" in doc and "Cloud" in doc
    # BUG-18 regression: `cache: pip` in setup-python needs a requirements.txt/
    # pyproject.toml, which a render repo has neither of — the step ERRORS and
    # every cloud render fails. It must not reappear in the app-installed workflow.
    assert "cache: pip" not in RENDER_WORKFLOW_YAML, "cache: pip breaks render-repo setup-python"
    assert "cache: pip" not in wf
    # The bundled constant (what the app installs) must match the shipped file so
    # the two can't drift apart.
    assert RENDER_WORKFLOW_YAML.strip() == wf.strip(), "bundled workflow != .github/workflows/render.yml"
    # Scene identity must be proven; a size heuristic cannot establish it.
    assert 'path.name == f"{scene_class}.mp4"' in wf
    assert "partial_movie_files" in wf
    assert "largest MP4" not in wf
    return "cloud workflow + docs; no cache:pip; bundle==file; " + _story_checks("test_cloud_output_identity")


def t_f159():
    # Current student-app QSS hooks + shared study palette.
    from aetherlab.ui import style
    from aetherlab.ui.live_canvas import LiveCanvas
    from aetherlab.ui.theme import Theme
    from aetherlab.ui.widgets import (
        AnalysisPanel,
        EmptyStateView,
        LibraryPanel,
        RunningView,
        SimulationPanel,
    )

    qss = style.AETHERLAB_QSS
    for token in (
        "QFrame#AnalysisCard",
        "QWidget#SceneToolbar",
        "QFrame#SetupStrip",
        "QFrame#LibraryEmptyState",
        "QToolButton#CanvasExportButton",
        "QTabWidget::pane",
        "QRadioButton::indicator:checked",
    ):
        assert token in qss, token
    assert style.CYAN == Theme().accent and style.STAGE == Theme().bg
    assert Theme().accent == style.CYAN and Theme().curve1 == style.CYAN

    ap = AnalysisPanel()
    assert ap.findChild(QtWidgets.QFrame, "AnalysisCard") is not None
    ev = EmptyStateView()
    assert ev._setup_strip.objectName() == "SetupStrip"
    rv = RunningView()
    assert rv.findChild(QtWidgets.QWidget, "RunningStatusStrip") is not None
    panel = SimulationPanel()
    assert panel.findChild(QtWidgets.QWidget, "SceneToolbar") is not None
    lib = LibraryPanel()
    assert lib._empty.objectName() == "LibraryEmptyState"
    canvas = LiveCanvas()
    assert canvas._export_btn.objectName() == "CanvasExportButton"
    doc = Path("docs/UI_GRAPHIC_REDESIGN.md").read_text(encoding="utf-8")
    assert "precision" in doc.lower() and "Qt Mapping" in doc
    for w in (ap, ev, rv, panel, lib, canvas):
        w.close()
    return "precision-instrument graphic redesign hooks + notes (F159)"


def t_f160():
    # Phase 1: persist visual quality metadata and opt into cache rejection for
    # stale/mediocre renders without changing default reuse behavior.
    from dataclasses import replace

    import aetherlab.services.scene_critic as critic_mod
    from aetherlab.core.cache import SessionCache
    from aetherlab.core.models import ProblemRequest, RagResult, SceneBundle
    from aetherlab.services.manim_runtime import ManimRuntime
    from aetherlab.services.pipeline import AetherLabPipeline
    from aetherlab.services.scene_critic import Critique

    scene = SceneBundle(
        class_name="S",
        code="from manim import *\nclass S(Scene):\n    def construct(self): pass\n",
        engine="manim-community",
        status="rendered",
        video_path="v.mp4",
        quality_score=8.25,
        critique_verdict="ship",
        critique_issues=["readable", "well paced"],
    )
    restored = SceneBundle.from_json(scene.to_json(), cached=True)
    assert restored.cached and restored.quality_score == 8.25
    assert restored.critique_verdict == "ship" and restored.critique_issues == ["readable", "well paced"]
    legacy = SceneBundle.from_json({})
    assert legacy.quality_score == 0.0 and legacy.critique_verdict == "" and legacy.critique_issues == []

    cache = SessionCache(_TMP / "quality-cache.sqlite3")
    req = ProblemRequest(prompt="quality cached scene")
    key = cache.ensure_request(req)
    cache.store_scene(key, scene)
    assert cache.get(key).scene.quality_score == 8.25

    import subprocess

    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    video = _TMP / "cached.mp4"
    subprocess.run(
        [ff, "-y", "-f", "lavfi", "-i",
         "testsrc=size=160x90:rate=10:duration=0.5", "-pix_fmt", "yuv420p", str(video)],
        capture_output=True,
    )
    assert video.exists()

    class _LLM:
        async def solve(self, _request):
            return _solver(model_name="deterministic-fallback")

    class _Rag:
        async def search(self, _keywords):
            return RagResult(keywords=["quality"], hits=[], backend="test")

    class _Manim:
        def __init__(self):
            self.generated = 0

        def detect_engine(self):
            return "manim-community", ""

        async def generate_scene_async(self, _request, _solver_result, _rag_result, _settings, **_kwargs):
            self.generated += 1
            from aetherlab.core.render_cache import record_scene_profile
            return record_scene_profile(SceneBundle(
                class_name="Fresh",
                code="fresh",
                engine="manim-community",
                status="rendered",
                video_path=str(video),
                quality_score=9.0,
                critique_verdict="ship",
            ), _settings)

        async def render_scene_with_repair(self, *_args, **_kwargs):
            raise AssertionError("render should be skipped for rendered scene with existing video")

    async def _no_ingest():
        return None

    low = SceneBundle(
        class_name="Old",
        code="old",
        engine="manim-community",
        status="rendered",
        video_path=str(video),
        quality_score=3.0,
    )
    strict_settings = replace(_settings(), cache_path=_TMP / "strict-cache.sqlite3", min_quality_score=7.0)
    from aetherlab.core.render_cache import record_scene_profile
    record_scene_profile(low, strict_settings)
    p = AetherLabPipeline(strict_settings)
    p.cache = SessionCache(strict_settings.cache_path)
    p.llm = _LLM()
    p.rag = _Rag()
    p.manim = _Manim()
    p._ensure_ingested = _no_ingest
    p.cache.ensure_request(req)
    p.cache.store_solver(key, _solver(model_name="deterministic-fallback"))
    p.cache.store_rag(key, RagResult(keywords=["quality"], hits=[], backend="test"))
    p.cache.store_scene(key, low)
    result = asyncio.run(p.run(req))
    assert p.manim.generated == 1 and result.scene.class_name == "Fresh"

    default_settings = replace(_settings(), cache_path=_TMP / "default-quality-cache.sqlite3", min_quality_score=0.0)
    p2 = AetherLabPipeline(default_settings)
    p2.cache = SessionCache(default_settings.cache_path)
    p2.llm = _LLM()
    p2.rag = _Rag()
    p2.manim = _Manim()
    p2._ensure_ingested = _no_ingest
    key2 = p2.cache.ensure_request(req)
    p2.cache.store_solver(key2, _solver(model_name="deterministic-fallback"))
    p2.cache.store_rag(key2, RagResult(keywords=["quality"], hits=[], backend="test"))
    p2.cache.store_scene(key2, low)
    result2 = asyncio.run(p2.run(req))
    assert p2.manim.generated == 0 and result2.scene.class_name == "Old"

    rt_settings = replace(
        _settings(),
        openai_api_key="sk-test",
        vision_model="vision-test",
        visual_critic_max_passes=1,
    )
    rt = ManimRuntime(rt_settings)
    render_video = _TMP / "critic.mp4"
    render_video.write_bytes(b"fake")

    async def fake_render_once(bundle, _settings_arg, _quality, _progress=None, **_kwargs):
        bundle.status = "rendered"
        bundle.video_path = str(render_video)
        return bundle

    async def fake_critique(*_args, **_kwargs):
        return Critique(verdict="ship", score=8.4, issues=["text readable"], strengths=["clear focus"])

    old_critique = critic_mod.critique_video
    critic_mod.critique_video = fake_critique
    rt._render_once = fake_render_once
    try:
        rendered = asyncio.run(rt.render_scene_with_repair(
            SceneBundle(class_name="S", code="code", engine="manim-community", status="compiled"),
            rt_settings,
        ))
    finally:
        critic_mod.critique_video = old_critique
    assert rendered.quality_score == 8.4
    assert rendered.critique_verdict == "ship" and rendered.critique_issues == ["text readable"]
    return "quality score persists; min_quality_score rejects low-score cache; default reuse preserved (F160)"


def t_f161():
    # Phase 2: opt-in candidate tournament. Network/vision work is stubbed; the
    # test proves selection, failed-candidate dropping, and N=1 delegation.
    from dataclasses import replace

    from aetherlab.core.models import ProblemRequest, SceneBundle
    from aetherlab.services.manim_runtime import ManimRuntime, SceneCandidate

    request = ProblemRequest(prompt="candidate tournament")
    solver = _solver()
    rag = _rag()

    single_settings = replace(
        _settings(),
        openai_api_key="sk-test",
        vision_model="vision-test",
        scene_candidates=1,
        auto_tournament=False,
    )
    single = ManimRuntime(single_settings)
    calls: list[str] = []
    compiled = SceneBundle(class_name="S", code="single-code", engine="e", status="compiled")
    rendered = SceneBundle(class_name="S", code="single-code", engine="e", status="rendered")

    async def fake_generate(*_args, **_kwargs):
        calls.append("generate")
        return compiled

    async def fake_render(scene, *_args, **_kwargs):
        calls.append(f"render:{scene.code}")
        return rendered

    async def unexpected_candidate_build(*_args, **_kwargs):
        raise AssertionError("opted-out single path attempted provider-backed candidate generation")

    single.generate_scene_async = fake_generate
    single.render_scene_with_repair = fake_render
    single._build_scene_candidates = unexpected_candidate_build
    assert not single.scene_tournament_enabled(single_settings)
    got = asyncio.run(single.generate_render_tournament(request, solver, rag, single_settings))
    assert got is rendered and calls == ["generate", "render:single-code"]

    tournament_settings = replace(
        _settings(),
        openai_api_key="sk-test",
        vision_model="vision-test",
        scene_candidates=3,
        scene_candidate_concurrency=2,
    )
    rt = ManimRuntime(tournament_settings)
    candidates = [
        SceneCandidate(0, SceneBundle("S", "low", "e", "compiled"), {"id": "low"}),
        SceneCandidate(1, SceneBundle("S", "broken", "e", "compiled"), {"id": "broken"}),
        SceneCandidate(2, SceneBundle("S", "winner", "e", "compiled"), {"id": "winner"}),
    ]

    score_rt = ManimRuntime(tournament_settings)
    score_candidates = [
        SceneCandidate(0, SceneBundle("S", "low", "e", "compiled"), {"id": "low"}),
        SceneCandidate(1, SceneBundle("S", "broken", "e", "compiled"), {"id": "broken"}),
        SceneCandidate(2, SceneBundle("S", "winner", "e", "compiled"), {"id": "winner"}),
    ]
    import aetherlab.services.scene_critic as critic_mod
    from aetherlab.services.scene_critic import Critique

    draft_render_calls: list[str] = []

    async def fake_draft_render(scene, *_args, **_kwargs):
        draft_render_calls.append(scene.code)
        if scene.code == "broken":
            scene.status = "render-error"
            return scene
        scene.status = "rendered"
        scene.video_path = str(_TMP / f"{scene.code}.mp4")
        return scene

    async def fake_critique(video_path, *_args, **_kwargs):
        score = 8.8 if "winner" in str(video_path) else 5.0
        verdict = "ship" if score > 7 else "revise"
        return Critique(verdict=verdict, score=score, issues=[] if verdict == "ship" else ["weak"])

    old_critique = critic_mod.critique_video
    critic_mod.critique_video = fake_critique
    score_rt._render_once = fake_draft_render
    # `_render_and_score_candidates` invokes the full repair renderer directly;
    # stubbing only `_render_once` still let repair call the configured LLM.
    score_rt.render_scene_with_repair = fake_draft_render
    try:
        scored = asyncio.run(score_rt._render_and_score_candidates(
            score_candidates, tournament_settings, None
        ))
    finally:
        critic_mod.critique_video = old_critique
    assert [c.scene.code for c in scored] == ["low", "winner"]
    assert max(scored, key=lambda c: c.score).scene.code == "winner"
    assert sorted(draft_render_calls) == ["broken", "low", "winner"]

    async def fake_build(*_args, **_kwargs):
        return candidates

    async def fake_score(cands, *_args, **_kwargs):
        # Candidate 1 simulates a render/static failure and is dropped.
        cands[0].score = 5.0
        cands[0].verdict = "revise"
        cands[0].issues = ["weak composition", "too static"]
        cands[2].score = 8.8
        cands[2].verdict = "ship"
        cands[2].issues = ["minor label crowding"]
        return [cands[0], cands[2]]

    selected: list[str] = []

    async def fake_final(scene, *_args, **_kwargs):
        selected.append(scene.code)
        assert scene.quality_score == 8.8
        assert scene.critique_verdict == "ship"
        assert scene.critique_issues == ["minor label crowding"]
        assert any("Tournament winner: candidate #3" in d for d in scene.diagnostics)
        scene.status = "rendered"
        return scene

    rt._build_scene_candidates = fake_build
    rt._render_and_score_candidates = fake_score
    rt.render_scene_with_repair = fake_final
    winner = asyncio.run(rt.generate_render_tournament(
        request, solver, rag, tournament_settings, quality="h", brief="brief"
    ))
    assert selected == ["winner"] and winner.code == "winner"

    failed = ManimRuntime(tournament_settings)
    fallback_calls: list[str] = []

    async def fake_empty(*_args, **_kwargs):
        return []

    async def fake_fallback_generate(*_args, **_kwargs):
        fallback_calls.append("fallback-generate")
        return compiled

    async def fake_fallback_render(scene, *_args, **_kwargs):
        fallback_calls.append(f"fallback-render:{scene.code}")
        return rendered

    failed._build_scene_candidates = fake_empty
    failed.generate_scene_async = fake_fallback_generate
    failed.render_scene_with_repair = fake_fallback_render
    fallback = asyncio.run(failed.generate_render_tournament(request, solver, rag, tournament_settings))
    assert fallback is rendered and fallback_calls == ["fallback-generate", "fallback-render:single-code"]
    return "candidate tournament selects highest score, drops failed candidates, N=1 delegates (F161)"


def t_f162():
    # Visual-regression quality GATE: warnings alone never failed the run, and
    # compare_report computed deltas but never flagged regressions. quality_failures,
    # regression flagging, and --strict decide_exit are pure + unit-testable here.
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "visual_regression_mod", str(Path("tools/visual_regression.py").resolve())
    )
    vr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vr)

    healthy = {"kind": "scene", "metrics": {
        "duration": 18.0, "fps": 30.0, "blank_ranges": [], "static_ranges": [],
    }}
    assert vr.quality_failures(healthy) == [], vr.quality_failures(healthy)

    broken = {"kind": "scene", "metrics": {
        "duration": 1.2, "fps": 3.0,
        "blank_ranges": [{"duration": 1.5}],
        "static_ranges": [{"duration": 16.0}],
    }}
    reasons = vr.quality_failures(broken)
    assert any("duration" in r for r in reasons) and any("fps" in r for r in reasons)
    assert any("blank" in r for r in reasons) and any("static" in r for r in reasons), reasons

    lesson_no_subs = {"kind": "lesson", "metrics": {
        "duration": 25.0, "fps": 30.0, "blank_ranges": [], "static_ranges": [],
        "subtitle": {"cue_count": 0},
    }}
    assert any("subtitle" in r for r in vr.quality_failures(lesson_no_subs))

    # A duration collapse remains a regression, but its normalized ratios are
    # not compared because the changed denominator makes them incomparable.
    base_dir = _TMP / "vr_baseline"
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "summary.json").write_text(json.dumps({"cases": [
        {"id": "scene_x", "metrics": {"duration": 18.0, "frame_count": 540,
                                       "blank_ratio": 0.0, "static_ratio": 0.10}},
        {"id": "scene_y", "metrics": {"duration": 12.0, "frame_count": 360,
                                       "blank_ratio": 0.0, "static_ratio": 0.10}},
    ]}), encoding="utf-8")
    now = {"cases": [
        {"id": "scene_x", "metrics": {"duration": 6.0, "frame_count": 180,
                                      "blank_ratio": 0.05, "static_ratio": 0.10}},  # regressed
        {"id": "scene_y", "metrics": {"duration": 12.1, "frame_count": 362,
                                      "blank_ratio": 0.0, "static_ratio": 0.11}},   # stable
    ]}
    cmp = vr.compare_report(base_dir, now)
    assert cmp["regression_count"] == 1, cmp
    by_id = {d["id"]: d for d in cmp["deltas"]}
    assert by_id["scene_x"]["regressions"] == ["duration dropped 18.0s -> 6.0s"], cmp
    assert by_id["scene_x"]["ratio_comparison"] == "skipped_duration_changed"
    assert not by_id["scene_y"]["regressions"] and by_id["scene_y"]["ratio_comparison"] == "compared", cmp

    # decide_exit: render failures always fail; --strict also fails on quality/warn/regress.
    render_fail = {"cases": [{"id": "a", "status": "fail"}]}
    assert vr.decide_exit(render_fail, strict=False) == 1
    warn_only = {"cases": [{"id": "a", "status": "warn", "quality_failures": []}]}
    assert vr.decide_exit(warn_only, strict=False) == 0  # default unchanged
    assert vr.decide_exit(warn_only, strict=True) == 1
    qfail = {"cases": [{"id": "a", "status": "pass", "quality_failures": ["duration low"]}]}
    assert vr.decide_exit(qfail, strict=False) == 0 and vr.decide_exit(qfail, strict=True) == 1
    regressed = {"cases": [{"id": "a", "status": "pass", "quality_failures": []}],
                 "compare": {"regression_count": 3}}
    assert vr.decide_exit(regressed, strict=True) == 1
    clean = {"cases": [{"id": "a", "status": "pass", "quality_failures": []}]}
    assert vr.decide_exit(clean, strict=True) == 0
    return "visual-regression quality gate: quality_failures + regression flags + strict exit (F162)"


def t_f163():
    # Exemplar library: domain-matched few-shot scenes injected into codegen.
    # Every exemplar must pass the SAME gates a generated scene must, and be
    # selected + injected. (All four also render — verified out of band; kept out
    # of the fast suite for speed.)
    from dataclasses import replace

    from aetherlab.core.models import ProblemRequest
    from aetherlab.services.code_safety import validate_code_safety
    from aetherlab.services.scene_exemplars import EXEMPLARS, exemplar_block, exemplar_for
    from aetherlab.services.scene_generator import SceneGenerator
    from aetherlab.services.scene_validation import validate_scene

    assert set(EXEMPLARS) == {"oscillator", "pendulum", "orbit", "wave"}
    for dom, code in EXEMPLARS.items():
        compile(code, "<ex>", "exec")
        assert "MathTex" not in code and "Tex(" not in code, f"{dom} must be LaTeX-free"
        ok, iss = validate_code_safety(code)
        assert ok, (dom, iss)
        lok, liss = validate_scene(code)
        assert lok, (dom, liss)

    # Selection reuses detect_domain and always yields a domain.
    assert exemplar_for(["kepler", "orbit"], {})[0] == "orbit"
    assert exemplar_for(["pendulum"], {})[0] == "pendulum"
    assert exemplar_for(["fourier", "wave"], {})[0] == "wave"
    assert exemplar_for(["thing"], {"damping": 0.1})[0] == "oscillator"
    assert exemplar_block(["orbit"], {}).startswith("## Reference exemplar")
    assert exemplar_block([], {}) != ""

    # Injected into the codegen system prompt (captured via a stub client).
    class _Msg:
        def __init__(self, c):
            self.content = c

    class _Choice:
        def __init__(self, c):
            self.finish_reason = "stop"
            self.message = _Msg(c)

    class _Resp:
        def __init__(self, c):
            self.choices = [_Choice(c)]

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
    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    sg = SceneGenerator(replace(_settings(), openai_api_key="sk-test"))
    sg._client = _Client()
    asyncio.run(sg._generate_remote(
        ProblemRequest(prompt="damped oscillator"), _solver(), _rag(), "AetherLabScene"))
    codegen_system = "\n".join(
        message["content"] for message in calls[1]["messages"]
        if message.get("role") == "system"
    )
    assert "Reference exemplar" in codegen_system, "exemplar not injected into codegen system context"
    assert "oscillator" in codegen_system, "domain-matched exemplar expected"
    return "4 exemplars compile+safety+lint+latex-free; domain-selected; injected into codegen (F163)"


def t_f164():
    from tools.feature_surface_audit import audit

    report = audit()
    assert report["feature_count"] >= 164, report
    assert report["surface_count"] >= 60, report
    assert report["localized_copy_count"] >= 7, report
    assert report["uncovered_count"] == 0, report["uncovered"]
    return (
        f"feature-surface audit covers {report['covered_count']}/"
        f"{report['surface_count']} current surfaces, including "
        f"{report['localized_copy_count']} locale maps (F164)"
    )


def t_f165():
    import build_feature_tracker as tracker
    from tools.tracker_integrity_audit import audit

    # include_run_status=False: this test runs inside the harness and therefore
    # reads the PREVIOUS run's results file. Asserting artifact consistency here;
    # rejecting a failing run is t_f215's job (and the CLI --check gate's).
    new_feature_ids = {f"F{number}" for number in range(225, 251)}
    report = audit(
        allow_pending_result=new_feature_ids | {"F168"},
        include_run_status=False,
    )
    assert report["feature_count"] >= 168, report
    assert report["story_count"] == report["feature_count"], report
    assert report["result_count"] >= report["feature_count"] - len(new_feature_ids), report
    assert report["test_count"] == report["feature_count"], report
    assert report["logged_bug_count"] >= 100, report
    assert report["linked_bug_count"] == report["logged_bug_count"], report
    assert report["unlinked_logged_bug_ids"] == [], report
    assert report["ok"], report["issues"]
    expected_methods = {
        "F54": "harness",
        "F153": "harness",
        "F154": "live-cloud",
        "F155": "harness",
        "F171": "harness",
    }
    actual_methods = {
        fid: tracker.STORY_OVERRIDES[fid][4]
        for fid in expected_methods
    }
    assert actual_methods == expected_methods, actual_methods
    return (
        f"tracker integrity: {report['feature_count']} features/"
        f"{report['story_count']} stories/"
        f"{report['result_count']} results/{report['test_count']} tests aligned (F165)"
    ) + "; " + _story_checks("test_tracker_cli") + "; " + _story_checks("test_tracker_reference_scope") + "; " + _story_checks("test_catalog_network_isolation") + "; " + _story_checks("test_encoder_story_contract") + "; " + _story_checks("test_feature_failure_contracts")


def t_f166():
    import json
    import subprocess
    import zipfile

    import imageio_ffmpeg

    from aetherlab.core.models import LessonBundle, SceneBundle
    from aetherlab.services.lesson_planner import _template_lesson
    from aetherlab.services.share_export import export_lesson_bundle
    from aetherlab.ui.main_window import MainWindow
    from aetherlab.ui.qt_compat import QtWidgets
    from aetherlab.ui.widgets import LessonView

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    video = _TMP / "share_lesson.mp4"
    subprocess.run(
        [ff, "-y", "-f", "lavfi", "-i",
         "testsrc=size=160x90:rate=10:duration=0.5", "-pix_fmt", "yuv420p", str(video)],
        capture_output=True,
    )
    assert video.exists() and video.stat().st_size > 0
    video.with_suffix(".srt").write_text(
        "1\n00:00:00,000 --> 00:00:00,500\nKepler opens the lesson.\n",
        encoding="utf-8",
    )
    plan = _template_lesson("Kepler orbit", "undergrad")
    bundle = LessonBundle(
        plan=plan,
        chapter_scenes=[
            SceneBundle("S1", "class S1(Scene):\n    pass\n", "e", "rendered", video_path=str(video)),
            SceneBundle("S2", "class S2(Scene):\n    pass\n", "e", "rendered", video_path=str(video)),
        ],
        video_path=str(video),
        status="assembled",
        chapter_offsets=[0.0, 3.5],
        rendered_chapter_indexes=[0, 1],
    )
    out = _TMP / "kepler_bundle.zip"
    summary = export_lesson_bundle(bundle, out)
    assert summary.path == out and summary.size_bytes > video.stat().st_size

    # BUG-26 regression: a mid-export failure must not truncate a prior good
    # bundle or leave a plausible-but-incomplete zip in its place (atomic write).
    good_bytes = out.read_bytes()
    from unittest import mock as _mock

    from aetherlab.services import share_export as _se

    _orig_write = _se._write

    def _boom(zf, entries, source, arcname, compress_type=None):
        if arcname.endswith("lesson.mp4"):
            raise OSError("simulated disk-full during export")
        return _orig_write(zf, entries, source, arcname, compress_type)

    with _mock.patch.object(_se, "_write", _boom):
        try:
            export_lesson_bundle(bundle, out)
            raise AssertionError("expected export to fail mid-write")
        except OSError:
            pass
    assert out.read_bytes() == good_bytes, "prior bundle destroyed by failed re-export"
    assert not (out.with_name(out.name + ".part")).exists(), "staging .part leaked"
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert any(n.endswith("/index.html") for n in names)
        assert any(n.endswith("/metadata.json") for n in names)
        assert any(n.endswith("/study_guide.tex") for n in names)
        assert any(n.endswith("/media/lesson.mp4") for n in names)
        assert any(n.endswith("/media/lesson.srt") for n in names)
        assert any(n.endswith("/media/lesson.vtt") for n in names)
        assert any("/scenes/chapter_01_" in n and n.endswith(".py") for n in names)
        html = zf.read(next(n for n in names if n.endswith("/index.html"))).decode("utf-8")
        meta = json.loads(zf.read(next(n for n in names if n.endswith("/metadata.json"))))
    assert "<video" in html and "media/lesson.vtt" in html and "data-time=\"3.500\"" in html
    meta_text = json.dumps(meta)
    assert str(_TMP) not in meta_text and "api_key" not in meta_text.lower()
    assert meta["assets"]["video"] == "media/lesson.mp4"
    assert meta["chapters"][0]["rendered"] is True

    lv = LessonView()
    try:
        lv.set_language("en")
        lv.set_lesson(bundle)
        assert hasattr(lv, "share_bundle_requested")
        labels = [b.text() for b in lv.findChildren(QtWidgets.QPushButton)]
        assert "Export lesson bundle" in labels
    finally:
        lv.close()
    import threading
    import time

    started = threading.Event()
    release = threading.Event()
    mw = MainWindow(_settings())
    try:
        assert hasattr(mw, "_export_lesson_bundle")
        assert "_start_export_task" in inspect.getsource(mw._export_lesson_bundle)

        def blocking_export(_cancel, _progress):
            started.set()
            assert release.wait(2.0)
            return "Export completed in background"

        before = time.perf_counter()
        assert mw._start_export_task("Exporting lesson bundle…", blocking_export)
        assert time.perf_counter() - before < 0.2 and started.wait(0.5)
        release.set()
        deadline = time.monotonic() + 2.0
        while mw._export_task and mw._export_task.is_running and time.monotonic() < deadline:
            _app.processEvents()
            time.sleep(0.01)
        _app.processEvents()
        assert "completed in background" in mw.statusBar().currentMessage()
    finally:
        release.set()
        mw.close()
        probe = getattr(mw, "_ollama_probe", None)
        if probe and probe.isRunning():
            probe.wait(5000)
    return "lesson share bundle zip contains html, mp4, subtitles, study guide, metadata, scene code (F166)"


def t_f167():
    import json
    from datetime import datetime, timedelta, timezone

    from aetherlab.core.models import LessonBundle
    from aetherlab.services.course_mode import CourseProgressStore, lesson_key
    from aetherlab.services.lesson_planner import _template_lesson
    from aetherlab.ui.main_window import MainWindow
    from aetherlab.ui.widgets import LessonView, _QuestionCard

    plan = _template_lesson("Kepler orbit", "undergrad")
    store_path = _TMP / "course_progress.json"
    store = CourseProgressStore(store_path)
    wrong = plan.questions[0].choices[-1]
    summary = store.record_quiz_answer(plan, 0, False, wrong)
    assert store_path.exists()
    assert summary.attempts == 1 and summary.correct == 0
    assert summary.missed_concepts and summary.next_topic.startswith("Review:")
    data = json.loads(store_path.read_text(encoding="utf-8"))
    key = lesson_key(plan)
    assert key in data["lessons"]
    assert data["lessons"][key]["questions"]["0"]["last_choice"] == wrong
    assert "api_key" not in json.dumps(data).lower()
    summary2 = CourseProgressStore(store_path).summary(plan)
    assert summary2.attempts == 1 and summary2.missed_concepts == summary.missed_concepts

    # Due multiple-choice reviews capture correctness before showing feedback,
    # and keep objective accuracy distinct from the open-response self-rating.
    study_store = CourseProgressStore(_TMP / "course_study_events.json")
    started = datetime(2026, 1, 1, tzinfo=timezone.utc)
    study_store.record_quiz_answer(plan, 0, False, wrong, now=started)
    due = study_store.due_reviews(now=started + timedelta(days=1))
    assert len(due) == 1 and due[0]["choices"]
    study_store.record_review_result(
        due[0], False, correct=False, now=started + timedelta(days=1)
    )
    study_event = study_store.evaluation_events()[1]
    assert study_event["recall_mode"] == "objective_mcq"
    assert study_event["correct"] is False and study_event["recalled"] is False
    from tools.learner_study_analysis import analyze_participants

    study_report = analyze_participants(
        [study_store.evaluation_events()],
        as_of=started + timedelta(days=2),
    )
    assert study_report["due_return"]["return_rate"] == 1.0
    assert study_report["delayed_recall"]["day_1"]["objective_mcq"] == {
        "n": 1, "correct": 0, "accuracy": 0.0,
    }

    # BUG-45: valid-but-wrong JSON shapes and malformed nested counters recover
    # as empty progress instead of breaking the lesson's quiz interaction.
    key = lesson_key(plan)
    store_path.write_text(
        json.dumps({"lessons": {key: {"attempts": "bad", "questions": []}}}),
        encoding="utf-8",
    )
    repaired = CourseProgressStore(store_path).record_quiz_answer(plan, 0, True, "A")
    assert repaired.attempts == 1 and repaired.correct == 1
    store_path.write_text("[]", encoding="utf-8")
    assert CourseProgressStore(store_path).summary(plan).attempts == 0

    lv = LessonView()
    try:
        lv.set_lesson(LessonBundle(plan=plan))
        assert "Course progress" in lv._course_status.text()
        got = []
        lv.quiz_answered.connect(lambda i, ok, choice: got.append((i, ok, choice)))
        card = lv.findChildren(_QuestionCard)[0]
        card._answer_mcq(wrong)
        assert got == [(0, False, wrong)]
        # BUG-27 regression: switching the selection after answering must not
        # record a second attempt (the card locks on first answer).
        right = plan.questions[0].answer
        card._answer_mcq(right)
        assert got == [(0, False, wrong)], "quiz card re-recorded after answering"
        assert card._answered and all(
            not b.isEnabled() for b in card._group.buttons()
        ), "quiz card not locked after answering"
        lv.set_course_summary("Quiz score 0/1. Review orbital shape next.")
        assert "Review orbital shape" in lv._course_status.text()
    finally:
        lv.close()

    mw = MainWindow(_settings())
    try:
        mw._last_lesson = LessonBundle(plan=plan)
        mw.course_progress = CourseProgressStore(_TMP / "main_course_progress.json")
        mw._record_lesson_quiz_answer(0, False, wrong)
        assert mw.course_progress.path.exists()
        assert "Review" in mw.lesson_view._course_status.text()
    finally:
        mw.close()
        probe = getattr(mw, "_ollama_probe", None)
        if probe and probe.isRunning():
            probe.wait(5000)
    assert Path("docs/COURSE_MODE.md").read_text(encoding="utf-8")
    return "course progress scores due MCQ recall separately from open-response self-ratings and updates recommendations (F167)"


def t_f168():
    import json

    from tools import prompt_quality_lab as lab

    prompts = lab.load_prompt_set()
    assert len(prompts) >= 6
    assert {p["id"] for p in prompts} >= {"pendulum", "kepler_orbit", "lesson_kepler"}
    assert any(p["mode"] == "lesson" for p in prompts)

    custom = _TMP / "prompt_set.json"
    custom.write_text(
        json.dumps([{"id": "x", "mode": "solve", "prompt": "show x"}]),
        encoding="utf-8",
    )
    assert lab.load_prompt_set(custom)[0]["id"] == "x"
    bom = _TMP / "prompt_bom.json"
    bom.write_text(
        "\ufeff" + json.dumps([{"id": "bom", "mode": "solve", "prompt": "show bom"}]),
        encoding="utf-8",
    )
    assert lab.load_prompt_set(bom)[0]["id"] == "bom"
    dup = _TMP / "prompt_dup.json"
    dup.write_text(
        json.dumps([
            {"id": "x", "mode": "solve", "prompt": "one"},
            {"id": "x", "mode": "solve", "prompt": "two"},
        ]),
        encoding="utf-8",
    )
    try:
        lab.load_prompt_set(dup)
        raise AssertionError("duplicate prompt ids must fail")
    except ValueError:
        pass

    story = lab.storyboard_summary({
        "hero_frame": "orbit reveal",
        "acts": [{"duration_s": 5}, {"duration_s": 7}, {"duration_s": 4}],
    })
    assert story == {
        "present": True,
        "act_count": 3,
        "duration_s": 16.0,
        "has_hero_frame": True,
    }

    good_case = {
        "id": "pendulum",
        "mode": "solve",
        "status": "pass",
        "storyboard": story,
        "critic": {"score": 8.0},
        "metrics": {"duration": 12.0, "fps": 30.0, "blank_ratio": 0.0, "static_ratio": 0.02},
        "quality_failures": [],
    }
    bad_case = {
        **good_case,
        "metrics": {"duration": 1.0, "fps": 4.0, "blank_ratio": 0.4, "static_ratio": 0.5},
        "quality_failures": ["duration below floor"],
        "critic": {"score": 0.0},
    }
    assert lab.score_case(good_case) > lab.score_case(bad_case)
    report = {
        "schema": "aetherlab.prompt_quality_lab.v1",
        "cases": [good_case],
        "summary": lab.summarize_cases([good_case]),
    }
    before = _TMP / "prompt_quality_before"
    before.mkdir()
    (before / "summary.json").write_text(
        json.dumps({"cases": [{**good_case, "score": 8.5}]}),
        encoding="utf-8",
    )
    compare = lab.compare_lab_reports(before, {**report, "cases": [{**good_case, "score": 6.9}]})
    assert compare and compare["regression_count"] == 1
    out = _TMP / "prompt_quality_report"
    lab.write_outputs(out, report)
    assert (out / "summary.json").exists()
    assert "Prompt Quality Lab" in (out / "summary.md").read_text(encoding="utf-8")
    assert "score" in (out / "scores.csv").read_text(encoding="utf-8")
    assert Path("docs/PROMPT_QUALITY_LAB.md").read_text(encoding="utf-8")
    return "prompt quality lab validates prompt sets, scores reports, and flags regressions (F168)"


def t_f169():
    # Quality Flywheel Phase 0: the golden-set + release ratchet (gate).
    from tools import prompt_quality_lab as lab

    # Golden set spans the domains AetherLab serves and is >= 12 prompts.
    prompts = lab.load_prompt_set()
    ids = {p["id"] for p in prompts}
    assert len(prompts) >= 12, len(prompts)
    assert {"pendulum", "projectile", "doppler", "rc_circuit", "escape_velocity"} <= ids, ids
    assert any(p["mode"] == "lesson" for p in prompts), "golden set must exercise a lesson"

    # The gate is a pure function: identical/improved/within-tolerance runs pass;
    # a real mean-score drop or ANY render-pass-rate drop fails. This is the
    # deterministic proof of the ratchet (no rendering needed).
    base = {"summary": {"mean_score": 6.0, "case_count": 12, "pass_count": 12}}
    assert lab.evaluate_gate(base, base)["ok"], "identical run must pass the gate"
    better = {"summary": {"mean_score": 6.8, "case_count": 12, "pass_count": 12}}
    assert lab.evaluate_gate(base, better)["ok"], "improvement must pass"
    noisy = {"summary": {"mean_score": 5.7, "case_count": 12, "pass_count": 12}}
    assert lab.evaluate_gate(base, noisy)["ok"], "within-tolerance noise must pass"
    worse = {"summary": {"mean_score": 5.2, "case_count": 12, "pass_count": 12}}
    g = lab.evaluate_gate(base, worse)
    assert not g["ok"] and any("mean score regressed" in r for r in g["reasons"]), g
    fewer = {"summary": {"mean_score": 6.0, "case_count": 12, "pass_count": 10}}
    g2 = lab.evaluate_gate(base, fewer)
    assert not g2["ok"] and any("pass rate" in r for r in g2["reasons"]), g2

    # A committed baseline exists and gates cleanly against itself (delta 0),
    # proving the wired file path — not just synthetic dicts.
    baseline_path = Path("tools/prompt_quality_baseline.json")
    assert baseline_path.exists(), "committed baseline must ship with the gate"
    committed = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert committed.get("summary", {}).get("case_count", 0) >= 12, committed.get("summary")
    assert lab.evaluate_gate(committed, committed)["ok"], "baseline must gate against itself"

    # The CLI wires --gate/--baseline/--score-tolerance.
    import inspect
    main_src = inspect.getsource(lab.main)
    assert "--gate" in main_src and "evaluate_gate" in main_src, "gate must be wired into the CLI"
    return "quality flywheel gate: 12-prompt golden set + committed baseline ratchet (F169)"


def t_f170():
    # Quality Flywheel Phase 1: the trustworthy per-axis judge.
    import inspect

    from aetherlab.core.models import SceneBundle
    from aetherlab.services import scene_critic as sc
    from aetherlab.services.scene_critic import (
        CRITIC_AXES,
        Critique,
        _coerce_breakdown,
        static_quality_estimate,
    )

    assert set(CRITIC_AXES) == {"legibility", "composition", "palette", "structure", "substance"}

    # A well-formed breakdown validates as "vision" and is clamped 0-2.
    good = {"legibility": 2, "composition": 1.5, "palette": 2, "structure": 1, "substance": 9}
    b, src = _coerce_breakdown(good, 8.0)
    assert src == "vision" and b["substance"] == 2.0 and set(b) == set(CRITIC_AXES), (src, b)
    # BUG-7 lesson: a malformed breakdown with a valid score is NOT silent-zeroed
    # — it is approximated from the score and flagged, not dropped.
    b2, src2 = _coerce_breakdown({"legibility": "oops"}, 6.0)
    assert src2 == "vision-approx" and abs(sum(b2.values()) - 6.0) < 1e-6 and all(v > 0 for v in b2.values()), (src2, b2)

    # The rubric prompt asks for the per-axis breakdown.
    assert '"breakdown"' in sc.CRITIC_SYSTEM_PROMPT and "0-2" in sc.CRITIC_SYSTEM_PROMPT

    # Static no-vision proxy: non-zero, discriminating, verdict stays "skipped".
    good_code = ("from manim import *\nclass S(Scene):\n    def construct(self):\n"
                 "        for i in range(5):\n            self.play(Create(Dot()), run_time=2)\n        self.wait(2)\n")
    bad_code = "from manim import *\nclass S(Scene):\n    def construct(self):\n        self.add(Text('x'))\n"
    eg, eb = static_quality_estimate(good_code), static_quality_estimate(bad_code)
    assert eg.breakdown_source == "static" and eg.verdict == "skipped"
    assert eg.score > 0 and set(eg.breakdown) == set(CRITIC_AXES)
    assert eb.score < eg.score, (eb.score, eg.score)  # a worse scene ranks lower
    # metrics (blank/static frames) push substance down.
    noisy = static_quality_estimate(good_code, {"blank_ratio": 0.5, "static_ratio": 0.5})
    assert noisy.breakdown["substance"] < eg.breakdown["substance"]

    # SceneBundle persists the breakdown and round-trips; OLD payloads still load.
    sb = SceneBundle("S", "c", "manim", "rendered", critique_breakdown={"legibility": 2.0})
    rt = SceneBundle.from_json(sb.to_json())
    assert rt.critique_breakdown == {"legibility": 2.0}
    assert SceneBundle.from_json({"class_name": "S", "code": "c"}).critique_breakdown == {}
    # a malformed persisted breakdown coerces cleanly, never raises.
    assert SceneBundle.from_json({"critique_breakdown": {"legibility": "x", "composition": 1}}).critique_breakdown == {"composition": 1.0}

    # All three manim_runtime critique-copy sites propagate the breakdown, and the
    # tournament uses the static proxy instead of dropping keyless candidates.
    rt_src = inspect.getsource(__import__("aetherlab.services.manim_runtime", fromlist=["ManimRuntime"]))
    assert rt_src.count("critique_breakdown") >= 3, "all three copy sites must carry the breakdown"
    assert "static_quality_estimate" in rt_src, "keyless candidates must be statically scored, not dropped"

    # Critique default is backward-compatible (empty breakdown, no source).
    assert Critique(verdict="skipped").breakdown == {} and Critique(verdict="skipped").breakdown_source == ""
    return "per-axis critic rubric + backward-compatible persistence + static no-vision proxy (F170)"


def t_f171():
    # Quality Flywheel Phase 2: parallel cloud fan-out with per-candidate
    # job-id isolation (the BUG-15 artifact-steal race under concurrency).
    import asyncio as _asyncio
    from dataclasses import replace

    from aetherlab.core.models import SceneBundle
    from aetherlab.services.manim_runtime import ManimRuntime, SceneCandidate
    from aetherlab.services.render_backend import GitHubActionsClient, cloud_job_id

    code = "class AetherLabScene(Scene):\n    def construct(self):\n        self.play(Create(Dot()))\n        self.wait(1)\n"
    sb = SceneBundle("AetherLabScene", code, "manim", "compiled")

    # variant salts the cloud id; "" stays byte-identical to the legacy id so the
    # single-scene path keeps its content-addressed cloud cache.
    base = cloud_job_id(sb, quality="l", fps=30)
    assert cloud_job_id(sb, quality="l", fps=30, variant="") == base, "empty variant must preserve cache id"
    salted = [cloud_job_id(sb, quality="l", fps=30, variant=f"cand{i}") for i in range(4)]
    assert len(set(salted)) == 4 and base not in salted, salted

    # BUG-36: unique paths are insufficient because GitHub's Contents API
    # commits each file to the shared branch. Concurrent PUTs must serialize.
    import concurrent.futures
    import threading
    import time
    import urllib.error

    class ConcurrentPutClient(GitHubActionsClient):
        def __init__(self):
            super().__init__("owner", "render", "token")
            self.guard = threading.Lock()
            self.active = 0
            self.max_active = 0
            self.writes = 0

        def _request(self, method, path, payload=None, *, raw=False):
            if method == "GET" and "/contents/" in path:
                raise urllib.error.HTTPError("u", 404, "missing", {}, None)
            if method == "PUT":
                with self.guard:
                    self.active += 1
                    self.max_active = max(self.max_active, self.active)
                time.sleep(0.03)
                with self.guard:
                    self.active -= 1
                    self.writes += 1
                return {}
            raise AssertionError((method, path))

    put_client = ConcurrentPutClient()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                put_client.put_file, f"jobs/cand{i}.py", code,
                branch="renders", message=f"candidate {i}",
            )
            for i in range(2)
        ]
        for future in futures:
            future.result()
    assert put_client.writes == 2 and put_client.max_active == 1, (
        put_client.writes, put_client.max_active
    )

    # Concurrently render THREE byte-identical candidates through the real
    # tournament scorer with a stubbed render; each must get its own variant and
    # receive its own artifact — never another candidate's.
    s = _settings()
    runtime = ManimRuntime(s)
    seen: list[str] = []

    async def fake_render_once(scene, settings, quality, progress=None, variant=""):
        seen.append(variant)
        await _asyncio.sleep(0)  # yield so the gathered candidates interleave
        return replace(scene, status="rendered", video_path=f"/fake/{variant}.mp4")

    async def fake_candidate_render(scene, settings, quality="l", render_variant="", **_kwargs):
        return await fake_render_once(scene, settings, quality, variant=render_variant)

    # The scorer calls the full repair renderer. Stubbing only _render_once
    # leaves preflight/LLM repair live before it reaches the fake media.
    runtime.render_scene_with_repair = fake_candidate_render  # type: ignore[assignment]
    candidates = [SceneCandidate(index=i, scene=replace(sb), storyboard=None) for i in range(3)]
    scored = _asyncio.run(runtime._render_and_score_candidates(candidates, s, None))

    assert sorted(seen) == ["cand0", "cand1", "cand2"], seen  # distinct isolation keys
    assert scored, "keyless candidates must be scored (static proxy), not dropped"
    for c in scored:
        assert c.scene.video_path == f"/fake/cand{c.index}.mp4", (c.index, c.scene.video_path)
        assert c.score > 0, "static proxy must score keyless candidates for ranking"

    # BUG-63: configured tournaments must not let one transient critic skip turn
    # into a static 10/10 that suppresses escalation. Retry once, bounded to
    # three frames, before the fail-soft proxy is considered.
    from aetherlab.services import scene_critic as critic_module
    from aetherlab.services.scene_critic import Critique

    provider_settings = replace(
        s, openai_api_key="key", vision_model="vision", visual_critic_keyframes=6
    )
    provider_runtime = ManimRuntime(provider_settings)
    provider_runtime.render_scene_with_repair = fake_candidate_render  # type: ignore[assignment]
    original_critique = critic_module.critique_video
    critic_calls = []

    async def transient_critique(*_args, **kwargs):
        critic_calls.append(kwargs["frame_count"])
        if len(critic_calls) == 1:
            return Critique(verdict="skipped")
        return Critique(
            verdict="ship",
            score=7.0,
            breakdown={"legibility": 2.0, "composition": 1.0},
            breakdown_source="vision",
        )

    critic_module.critique_video = transient_critique
    try:
        retried = _asyncio.run(
            provider_runtime._render_and_score_candidates(
                [SceneCandidate(index=0, scene=replace(sb), storyboard=None)],
                provider_settings,
                None,
            )
        )
    finally:
        critic_module.critique_video = original_critique
    assert critic_calls == [6, 3], critic_calls
    assert retried[0].score == 7.0 and retried[0].verdict == "ship"
    assert any("retrying once" in d for d in retried[0].scene.diagnostics)

    # A manual live-smoke script exists for the real GitHub end-to-end path.
    smoke = Path("tools/cloud_tournament_smoke.py").read_text(encoding="utf-8")
    assert "cloud_job_id" in smoke and "variant" in smoke and "asyncio.gather" in smoke
    return (
        "candidate fan-out isolates artifacts, serializes branch PUTs, and retries "
        "transient vision skips (BUG-36/63, F171)"
    )


def t_f172():
    # Quality Flywheel Phase 3a: losers teach — aesthetic pitfall learning.
    import inspect

    from aetherlab.services.error_learner import (
        AestheticPitfallStore,
        learned_aesthetic_block,
        normalize_aesthetic,
        preventive_pitfalls_block,
    )

    # Variants that differ only in numbers/paths/axis-tag collapse to one phrase.
    a = normalize_aesthetic("Legibility: Text overlaps the axis at (3, 4).")
    b = normalize_aesthetic("text overlaps the axis at (1, 2)")
    assert a == b and "text overlaps the axis" in a, (a, b)

    store = AestheticPitfallStore(_TMP / "aesthetic_pitfalls.json")
    store.record(["Text overlaps the axis at (3,4)", "Object leaves the frame", "text overlaps the axis at (9,9)"])
    top = store.top()
    assert top[0][1] == 2 and "overlaps" in top[0][0], top  # the repeated one ranks first
    # Persists across instances.
    assert AestheticPitfallStore(_TMP / "aesthetic_pitfalls.json").top(1) == top[:1]

    # The learned block is empty for an empty store and appears for a full one.
    assert learned_aesthetic_block(AestheticPitfallStore(_TMP / "empty_aes.json")) == ""
    # preventive_pitfalls_block(): static only (backward compatible), no learned section.
    assert "past renders" not in preventive_pitfalls_block()
    withlearn = preventive_pitfalls_block(store)
    assert "past renders" in withlearn and "text overlaps the axis" in withlearn

    # Generation injects the learned pitfalls at both codegen sites.
    gen_src = inspect.getsource(__import__("aetherlab.services.scene_generator", fromlist=["SceneGenerator"]).SceneGenerator._generate_remote)
    assert "AestheticPitfallStore" in gen_src and gen_src.count("preventive_pitfalls_block(_aesthetic)") == 2

    # The tournament records losing candidates' issues (behavioural: the store file appears).
    from aetherlab.services.manim_runtime import ManimRuntime
    rt = ManimRuntime(_settings())
    rt_src = inspect.getsource(ManimRuntime)
    assert "_record_aesthetic_pitfalls" in rt_src and "is not winner" in rt_src
    probe = _settings()
    rt._record_aesthetic_pitfalls(["Text runs off the right edge"], probe)
    recorded = AestheticPitfallStore(probe.data_dir / "aesthetic_pitfalls.json").top()
    assert any("runs off" in p for p, _ in recorded), recorded
    return "aesthetic pitfall learning: critic issues feed the next generation prompt (F172)"


def t_f173():
    # Quality Flywheel Phase 3b: winners teach — exemplar promotion (human-gated).
    import inspect

    from aetherlab.services.scene_exemplars import PROMOTE_MIN_SCORE, ExemplarCandidateStore

    code = "from manim import *\nclass AetherLabScene(Scene):\n    def construct(self):\n        self.wait(1)\n"
    store = ExemplarCandidateStore(_TMP / "exemplar_candidates.json")
    # Only a genuine, high-scoring VISION 'ship' is exemplar-worthy.
    assert store.record(domain="pendulum", code=code, score=9.1, verdict="ship") is True
    assert store.record(domain="wave", code=code, score=9.9, verdict="skipped") is False  # static proxy
    assert store.record(domain="wave", code="x=1", score=6.0, verdict="ship") is False    # below bar
    assert store.record(domain="wave", code="y=2", score=9.0, verdict="revise") is False  # critic unhappy
    assert store.record(domain="wave", code="   ", score=9.0, verdict="ship") is False    # empty code
    assert PROMOTE_MIN_SCORE >= 8.0
    items = ExemplarCandidateStore(_TMP / "exemplar_candidates.json").list()
    assert len(items) == 1 and items[0]["domain"] == "pendulum" and items[0]["verdict"] == "ship"
    # Identical code dedups rather than piling up.
    store.record(domain="pendulum", code=code, score=9.4, verdict="ship")
    assert len(ExemplarCandidateStore(_TMP / "exemplar_candidates.json").list()) == 1
    # BUG-45: malformed-but-valid rows are ignored, and the next good winner
    # reconstructs a usable candidate list instead of failing on scalar .get().
    store.path.write_text('[null, 3, {"code":"old"}]', encoding="utf-8")
    assert store.record(domain="wave", code="new", score=9.0, verdict="ship")
    assert all(isinstance(item, dict) for item in store.list())

    # The tournament records winners; the store never lives in the curated source.
    rt_src = inspect.getsource(__import__("aetherlab.services.manim_runtime", fromlist=["ManimRuntime"]).ManimRuntime)
    assert "_record_exemplar_candidate" in rt_src and "ExemplarCandidateStore" in rt_src

    # The promote tool exists, runs, and NEVER auto-edits scene_exemplars.py
    # (promotion is a reviewed human code change — supply-chain safety).
    from tools import promote_exemplar
    tool_src = Path("tools/promote_exemplar.py").read_text(encoding="utf-8")
    assert 'scene_exemplars.py' in tool_src  # it references the target for humans
    assert ".write_text(" not in tool_src and "open(" not in tool_src, "promote tool must not write files"
    assert promote_exemplar.main(["--list"]) == 0  # runs without crashing

    # BUG-31: promotion keys off the FINAL HQ critique, not the 480p draft score
    # the tournament used only to pick the winner.
    import asyncio as _asyncio
    from dataclasses import replace as _replace

    from aetherlab.core.models import ProblemRequest, RagResult, SceneBundle, SolverResult
    from aetherlab.services.manim_runtime import ManimRuntime, SceneCandidate

    def _promote_count(draft: float, hq_score: float, hq_verdict: str, dd: Path) -> int:
        s = _replace(_settings(), data_dir=dd, scene_candidates=2, openai_api_key="k", vision_model="v")
        rt = ManimRuntime(s)

        async def _fb(request, solver, rag, settings, aspect, progress, count=None, start_index=0, **_kwargs):
            return [SceneCandidate(index=start_index + i,
                                   scene=SceneBundle("AetherLabScene", "winner-code", "e", "rendered", video_path="/x.mp4"),
                                   storyboard={"acts": [{"beats": ["a"]}]}) for i in range(count or 0)]

        async def _fs(cands, settings, progress, **_kwargs):
            for c in cands:
                c.score, c.verdict = draft, ("ship" if draft >= 7 else "revise")
            return cands

        async def _fr(scene, settings=None, quality="l", max_repairs=2, max_revisions=2, brief="", progress=None, **_kwargs):
            return _replace(scene, quality_score=hq_score, critique_verdict=hq_verdict)

        rt._build_scene_candidates = _fb          # type: ignore[assignment]
        rt._render_and_score_candidates = _fs     # type: ignore[assignment]
        rt.render_scene_with_repair = _fr         # type: ignore[assignment]
        solver = SolverResult(summary="", derivation_steps=[], keywords=["orbit"], variables={}, model_name="t")
        _asyncio.run(rt.generate_render_tournament(
            ProblemRequest(prompt="x"), solver, RagResult(keywords=[], hits=[], backend="none"), s))
        return len(ExemplarCandidateStore(dd / "exemplar_candidates.json").list())

    da, db = _TMP / "rekey_a", _TMP / "rekey_b"
    da.mkdir(exist_ok=True)
    db.mkdir(exist_ok=True)
    # A weak draft (7.0) that renders to a strong HQ (9.0 ship) IS promoted.
    assert _promote_count(7.0, 9.0, "ship", da) == 1, "HQ ship must promote even when the draft scored below the bar"
    # A strong draft (9.0 ship) that renders to a weak HQ (6.0) is NOT promoted.
    assert _promote_count(9.0, 6.0, "ship", db) == 0, "a low HQ score must not promote despite a high draft score"
    return "exemplar promotion keys off the final HQ critique, not the draft score (F173)"


def t_f174():
    # Quality Flywheel Phase 4: difficulty-scaled budget + cheap-first escalation.
    import asyncio as _asyncio
    from dataclasses import replace

    from aetherlab.core.models import ProblemRequest, RagResult, SceneBundle, SolverResult
    from aetherlab.services.manim_runtime import (
        ManimRuntime,
        SceneCandidate,
        candidate_budget,
        storyboard_difficulty,
    )

    easy = {"acts": [{"beats": ["a"], "duration_s": 6}]}
    hard = {"acts": [{"beats": ["a", "b", "c", "d"], "duration_s": 8} for _ in range(4)]}
    assert storyboard_difficulty(easy) < storyboard_difficulty(hard)
    assert candidate_budget(easy, 4) == 1, "easy scene must budget a single candidate"
    assert candidate_budget(hard, 4) == 4, "hard scene may use the full cap"
    assert candidate_budget(hard, 1) == 1 and candidate_budget(None, 4) >= 1

    def _tournament(board, scores):
        """Run the tournament with stubbed build/score/render; return build calls."""
        # scene_candidates>1 + key + vision enable the tournament; the stubs mean
        # no real provider/render is ever touched.
        s = replace(_settings(), scene_candidates=4, openai_api_key="test-key", vision_model="test-vision")
        rt = ManimRuntime(s)
        calls = []

        async def fake_build(request, solver, rag, settings, aspect, progress, count=None, start_index=0, **_kwargs):
            calls.append((count, start_index))
            return [
                SceneCandidate(index=start_index + i,
                               scene=SceneBundle("AetherLabScene", "code", "manim", "compiled"),
                               storyboard=board)
                for i in range(count or 0)
            ]

        async def fake_score(cands, settings, progress, **_kwargs):
            for c in cands:
                c.score = scores.get(c.index, 6.0)
                c.verdict = "ship" if c.score >= 7 else "revise"
            return cands

        async def fake_repair(scene, settings=None, quality="l", max_repairs=2,
                              max_revisions=2, brief="", progress=None, **_kwargs):
            return scene

        rt._build_scene_candidates = fake_build          # type: ignore[assignment]
        rt._render_and_score_candidates = fake_score     # type: ignore[assignment]
        rt.render_scene_with_repair = fake_repair        # type: ignore[assignment]

        req = ProblemRequest(prompt="x")
        solver = SolverResult(summary="", derivation_steps=[], keywords=[], variables={}, model_name="t")
        rag = RagResult(keywords=[], hits=[], backend="none")
        _asyncio.run(rt.generate_render_tournament(req, solver, rag, s))
        return calls

    # A good first render ships immediately — no fan-out, even on a hard scene.
    good = _tournament(hard, {0: 9.0})
    assert good == [(1, 0)], f"a strong first render must not escalate: {good}"

    # A weak first render on a HARD scene escalates to the remaining budget.
    weak_hard = _tournament(hard, {0: 5.0})
    assert weak_hard == [(1, 0), (3, 1)], f"weak+hard must fan out the budget: {weak_hard}"

    # A weak first render on an EASY scene does NOT escalate (budget is 1).
    weak_easy = _tournament(easy, {0: 5.0})
    assert weak_easy == [(1, 0)], f"weak+easy must stay single-candidate: {weak_easy}"

    # BUG-30: if the first candidate builds but FAILS to render (scored empty),
    # escalation must not exceed the budget/cap total attempts.
    s = replace(_settings(), scene_candidates=4, openai_api_key="k", vision_model="v")
    rt = ManimRuntime(s)
    built: list[int] = []

    async def _fb(request, solver, rag, settings, aspect, progress, count=None, start_index=0, **_kwargs):
        built.append(count or 0)
        return [SceneCandidate(index=start_index + i, scene=SceneBundle("S", "c", "e", "compiled"), storyboard=hard)
                for i in range(count or 0)]

    async def _fs(cands, settings, progress, **_kwargs):
        if cands and cands[0].index == 0:  # first candidate "fails to render"
            return []
        for c in cands:
            c.score = 5.0
            c.verdict = "revise"
        return cands

    async def _fr(scene, settings=None, quality="l", max_repairs=2, max_revisions=2, brief="", progress=None, **_kwargs):
        return scene

    rt._build_scene_candidates = _fb          # type: ignore[assignment]
    rt._render_and_score_candidates = _fs     # type: ignore[assignment]
    rt.render_scene_with_repair = _fr         # type: ignore[assignment]
    req = ProblemRequest(prompt="x")
    solver = SolverResult(summary="", derivation_steps=[], keywords=[], variables={}, model_name="t")
    _asyncio.run(rt.generate_render_tournament(req, solver, RagResult(keywords=[], hits=[], backend="none"), s))
    assert sum(built) <= 4, f"escalation exceeded the cap of 4: built {sum(built)} ({built})"
    return "cheap-first escalation: difficulty-scaled budget spends fan-out only when needed (F174)"


def t_f175():
    # Quality Flywheel Phase 5a: the render-farm job/candidate event ledger.
    import inspect
    import json as _json
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from dataclasses import replace

    from aetherlab.core.models import SceneBundle
    from aetherlab.services.manim_runtime import ManimRuntime, SceneCandidate
    from aetherlab.services.render_ledger import STATUSES, RenderJobLedger, scrub

    # Secret scrubbing: tokens/keys/bearer are redacted from any free text.
    dirty = "token=ghp_ABCDEFGHIJKLMNOPQRSTUVWX key sk-abcdefghijklmnopqrstuvwx Authorization: Bearer zzzz1234yyyy"
    clean = scrub(dirty)
    assert "ghp_" not in clean and "sk-" not in clean and "Bearer zzzz" not in clean and "redacted" in clean

    led = RenderJobLedger(_TMP / "ledger_unit.json")
    # Success job with per-candidate scores + winner.
    led.start(job_id="j1", scene_class="AetherLabScene", quality="l", fps=30, backend="github-actions", provider="github_actions")
    led.status("j1", "in_progress", "dispatched")
    led.candidates("j1", [
        {"index": 0, "score": 5.0, "verdict": "revise"},
        {"index": 1, "score": 8.8, "verdict": "ship", "breakdown": {"legibility": 2}},
    ])
    led.winner("j1", 1)
    led.status("j1", "artifact_downloaded", "MP4 downloaded")
    led.finish("j1", "rendered", "/x/j1.mp4")
    # Failure with a secret buried in the log tail.
    led.failure("j2", "NameError line 3\nAuthorization: Bearer ghp_SECRETTOKEN1234567890 boom", kind="hallucinated-api")
    # Cancellation, rate-limit, and local fallback.
    led.status("j3", "cancelled", "user cancelled")
    led.status("j4", "rate_limited", "Retry-After 42")
    led.fallback("j5", "cloud unavailable: token lacks workflow scope", "/local/j5.mp4")
    # All persisted user-facing fields are scrubbed, and links accept only
    # credential-free GitHub Actions pages with the expected path shape.
    led.start(job_id="j6", scene_class="token=scene-secret", fps=60)
    led.urls(
        "j6", run_url="https://github.com/owner/repo/actions/runs/12?token=secret",
        artifact_url="https://github.com/owner/repo/actions/runs/12/artifacts/34",
    )
    led.status("j6", "untrusted-state", "api_key=ledger-secret")

    j1 = led.get("j1")
    assert j1["winner_index"] == 1 and j1["status"] == "rendered" and j1["final_path"] == "/x/j1.mp4"
    assert [c["score"] for c in j1["candidates"]] == [5.0, 8.8]
    j2 = led.get("j2")
    assert j2["status"] == "failed" and "ghp_" not in j2["log_tail"] and "redacted" in j2["log_tail"]
    assert led.get("j5")["status"] == "fallback_local" and "workflow scope" in led.get("j5")["fallback_reason"]
    j6 = led.get("j6")
    assert j6["scene_class"] == "<redacted>" and j6["status"] == "failed"
    assert j6["run_url"] == "" and j6["artifact_url"].endswith("/runs/12/artifacts/34")
    assert "ledger-secret" not in _json.dumps(j6)
    # Every recorded timeline status is a known lifecycle state.
    assert all(e["status"] in STATUSES for j in led.list(50) for e in j["timeline"])
    # Cap keeps the ledger bounded.
    capped = RenderJobLedger(_TMP / "ledger_cap.json", max_jobs=3)
    for i in range(6):
        capped.start(job_id=f"k{i}")
    assert len(capped.list(50)) == 3

    # BUG-44: every mutable JSON store reached by parallel candidates/chapters
    # shares one transactional path lock and atomic replace. Fresh instances are
    # intentional: an instance-local lock would still lose these updates.
    workers = 12

    def parallel_json(path: Path, writer) -> object:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)
        gate = threading.Barrier(workers)

        def run_one(index: int) -> None:
            gate.wait(timeout=10)
            writer(index)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(run_one, range(workers)))
        payload = _json.loads(path.read_text(encoding="utf-8"))
        assert not list(path.parent.glob(f".{path.name}.*.tmp"))
        return payload

    ledger_race = _TMP / "ledger_race.json"
    ledger_payload = parallel_json(
        ledger_race,
        lambda i: RenderJobLedger(ledger_race, max_jobs=workers).start(job_id=f"r{i}"),
    )
    assert {row["job_id"] for row in ledger_payload} == {f"r{i}" for i in range(workers)}

    from aetherlab.services.render_backend import CloudRenderManifest

    manifest_race = _TMP / "manifest_race.json"
    manifest_payload = parallel_json(
        manifest_race,
        lambda i: CloudRenderManifest(manifest_race).put(f"m{i}", {"index": i}),
    )
    assert set(manifest_payload) == {f"m{i}" for i in range(workers)}
    manifest_race.write_text("[]", encoding="utf-8")
    malformed_manifest = CloudRenderManifest(manifest_race)
    assert malformed_manifest.get("missing") is None
    malformed_manifest.put("recovered", {"ok": True})
    assert malformed_manifest.get("recovered") == {"ok": True}

    from aetherlab.services.lesson_pipeline import _ChapterCache

    chapter_dir = _TMP / "chapter_race_store"
    chapter_path = chapter_dir / "chapters_cache.json"
    chapter_payload = parallel_json(
        chapter_path,
        lambda i: _ChapterCache(chapter_dir).put(
            f"c{i}", SceneBundle("S", f"code-{i}", "e", "compiled")
        ),
    )
    assert set(chapter_payload) == {f"c{i}" for i in range(workers)}, sorted(chapter_payload)

    from aetherlab.services.course_mode import CourseProgressStore
    from aetherlab.services.lesson_planner import _template_lesson

    course_race = _TMP / "course_race.json"
    plan = _template_lesson("Concurrent pendulum", "undergrad")
    parallel_json(
        course_race,
        lambda i: CourseProgressStore(course_race).record_quiz_answer(
            plan, 0, True, str(i)
        ),
    )
    course_summary = CourseProgressStore(course_race).summary(plan)
    assert course_summary.attempts == workers and course_summary.correct == workers

    from aetherlab.services.error_learner import AestheticPitfallStore, ErrorLearner

    errors_race = _TMP / "errors_race.json"
    parallel_json(
        errors_race,
        lambda _i: ErrorLearner(errors_race).record("NameError: missing_widget"),
    )
    assert ErrorLearner(errors_race).seen_count("NameError: missing_widget") == workers

    aesthetic_race = _TMP / "aesthetic_race.json"
    parallel_json(
        aesthetic_race,
        lambda _i: AestheticPitfallStore(aesthetic_race).record(["label overlaps axis"]),
    )
    assert AestheticPitfallStore(aesthetic_race).top(1)[0][1] == workers

    from aetherlab.services.scene_exemplars import ExemplarCandidateStore

    exemplar_race = _TMP / "exemplar_race.json"
    exemplar_payload = parallel_json(
        exemplar_race,
        lambda i: ExemplarCandidateStore(exemplar_race).record(
            domain="wave", code=f"scene-{i}", score=9.0, verdict="ship"
        ),
    )
    assert len(exemplar_payload) == workers

    # BUG-45: valid JSON with hostile/nested shapes remains fail-soft and can be
    # repaired by the next legitimate mutation.
    ledger_race.write_text(
        '[null, 7, {"job_id":"damaged","timeline":"bad","candidates":[1]}]',
        encoding="utf-8",
    )
    damaged = RenderJobLedger(ledger_race)
    damaged.status("damaged", "in_progress", "recovered")
    assert damaged.get("damaged")["timeline"][-1]["detail"] == "recovered"
    exemplar_race.write_text('[null, 3, {"code":"old"}]', encoding="utf-8")
    assert ExemplarCandidateStore(exemplar_race).record(
        domain="wave", code="new", score=9.0, verdict="ship"
    )
    assert all(isinstance(row, dict) for row in _json.loads(exemplar_race.read_text(encoding="utf-8")))

    # Tournament wiring: per-candidate scores + winner land in the ledger.
    s = replace(_settings(), data_dir=_TMP / "ledger_tourney")
    rt = ManimRuntime(s)
    scored = [
        SceneCandidate(0, SceneBundle("AetherLabScene", "c0", "e", "rendered"), score=5.0, verdict="revise", breakdown={"legibility": 1.0}),
        SceneCandidate(1, SceneBundle("AetherLabScene", "c1", "e", "rendered"), score=8.8, verdict="ship", breakdown={"legibility": 2.0}),
    ]
    rt._record_tournament_ledger(scored, scored[1], s, "l")
    tour = RenderJobLedger(s.data_dir / "render_ledger.json").list()
    assert tour and tour[0]["winner_index"] == 1 and len(tour[0]["candidates"]) == 2

    # The cloud backend and fallback path are wired to the ledger.
    rb_src = inspect.getsource(__import__("aetherlab.services.render_backend", fromlist=["CloudRenderBackend"]).CloudRenderBackend)
    assert "RenderJobLedger" in rb_src and "ledger.failure(" in rb_src and "ledger.finish(" in rb_src
    assert "fallback(" in inspect.getsource(ManimRuntime._render_once)
    return "render-farm ledger + atomic concurrent JSON persistence across stores (F175)"


def t_f176():
    # Quality Flywheel Phase 5b: the render-farm dashboard UI panel.
    from aetherlab.services.render_ledger import RenderJobLedger
    from aetherlab.ui.ledger_panel import RenderLedgerPanel
    from aetherlab.ui.main_window import SettingsDialog
    from aetherlab.ui.qt_compat import QtWidgets

    ledger_path = _TMP / "panel_ledger.json"
    led = RenderJobLedger(ledger_path)
    led.start(job_id="j1", scene_class="AetherLabScene", quality="l", fps=60, backend="github-actions")
    led.urls(job_id="j1", run_url="https://github.com/owner/repo/actions/runs/22",
             artifact_url="https://github.com/owner/repo/actions/runs/22/artifacts/33")
    led.candidates("j1", [{"index": 0, "score": 5.0, "verdict": "revise"},
                          {"index": 1, "score": 8.8, "verdict": "ship"}])
    led.winner("j1", 1)
    led.finish("j1", "rendered", "/x.mp4")
    led.failure("j2", "boom Authorization: Bearer ghp_SECRET1234567890TOKEN", kind="oom")
    led.failure("j3", "GitHub denied access; check workflow scope", kind="token_scope", status="action_required")

    panel = RenderLedgerPanel(ledger_path)
    try:
        assert panel._jobs.count() == 3, panel._jobs.count()
        # Select the tournament job and confirm the winner + candidate scores show.
        win_row = next(i for i, r in enumerate(panel._records) if r.get("winner_index") is not None)
        panel._jobs.setCurrentRow(win_row)
        detail = panel._details.toHtml()
        assert "winner" in detail.lower() and "8.8" in detail, detail[:200]
        assert "Job: j1" in detail and "FPS: 60" in detail
        assert "Open GitHub Actions run" in detail and "Open render artifact" in detail
        # The failure job's log tail was scrubbed at write time — never shows a token.
        fail_row = next(i for i, r in enumerate(panel._records) if r.get("status") == "failed")
        panel._jobs.setCurrentRow(fail_row)
        assert "ghp_" not in panel._details.toHtml()
        action_row = next(i for i, r in enumerate(panel._records) if r.get("status") == "action_required")
        panel._jobs.setCurrentRow(action_row)
        assert "action required" in panel._details.toHtml().lower()
    finally:
        panel.close()

    # An absent ledger shows the empty state, not a crash.
    empty = RenderLedgerPanel(_TMP / "no_such_ledger.json")
    try:
        assert empty._jobs.count() == 0 and empty._empty.isVisibleTo(empty)
    finally:
        empty.close()

    malformed_path = _TMP / "malformed_panel_ledger.json"
    malformed_path.write_text(
        '[null,{"job_id":"x","winner_index":"bad","candidates":[1,{"index":"bad"}],'
        '"timeline":[false,{"status":"queued"}]}]',
        encoding="utf-8",
    )
    malformed = RenderLedgerPanel(malformed_path)
    try:
        assert malformed._jobs.count() == 1
        assert "Candidates" in malformed._details.toPlainText()
    finally:
        malformed.close()

    # The dashboard is reachable from the Settings cloud surface.
    dialog = SettingsDialog(_settings())
    try:
        assert hasattr(dialog, "_open_render_ledger")
        dialog.set_language("en")
        assert "View render ledger" in [b.text() for b in dialog.findChildren(QtWidgets.QPushButton)]
    finally:
        dialog.close()
    return "render-farm dashboard panel lists jobs, candidates, winner, scrubbed failures (F176)"


def t_f177():
    # Quality Flywheel Phase 6: default-on for configured critics, safely.
    import os
    from dataclasses import replace

    from aetherlab.core.settings import AppSettings, load_settings
    from aetherlab.services.manim_runtime import (
        AUTO_TOURNAMENT_CAP,
        ManimRuntime,
        effective_candidate_cap,
    )
    from aetherlab.ui.main_window import SettingsDialog

    assert AppSettings.__dataclass_fields__["auto_tournament"].default is True

    base = _settings()
    keyless = replace(base, openai_api_key=None, vision_model=None, scene_candidates=1, auto_tournament=True)
    critic = replace(base, openai_api_key="k", vision_model="v", scene_candidates=1, auto_tournament=True)
    off = replace(critic, auto_tournament=False)
    power = replace(base, openai_api_key="k", vision_model="v", scene_candidates=5, auto_tournament=False)

    # Keyless/offline: exactly one render, tournament off — unchanged and no slower.
    assert effective_candidate_cap(keyless) == 1
    assert not ManimRuntime(keyless).scene_tournament_enabled(keyless)
    # Configured critic: default-on with the auto cap (Phase-4 escalation keeps it cheap).
    assert effective_candidate_cap(critic) == AUTO_TOURNAMENT_CAP
    assert ManimRuntime(critic).scene_tournament_enabled(critic)
    # Opt-out toggle -> single shot again.
    assert effective_candidate_cap(off) == 1 and not ManimRuntime(off).scene_tournament_enabled(off)
    # Power-user explicit scene_candidates override wins regardless of the toggle.
    assert effective_candidate_cap(power) == 5 and ManimRuntime(power).scene_tournament_enabled(power)

    # load_settings honours the env override.
    old = os.environ.get("AETHERLAB_AUTO_TOURNAMENT")
    try:
        os.environ["AETHERLAB_AUTO_TOURNAMENT"] = "0"
        assert load_settings().auto_tournament is False
    finally:
        if old is None:
            os.environ.pop("AETHERLAB_AUTO_TOURNAMENT", None)
        else:
            os.environ["AETHERLAB_AUTO_TOURNAMENT"] = old

    # The Settings dialog exposes the toggle and round-trips it (BUG-4 class).
    dialog = SettingsDialog(_settings())
    try:
        assert hasattr(dialog, "_auto_tournament_check")
        assert "auto_tournament" in dialog.get_settings()
    finally:
        dialog.close()
    return "tournament default-on for configured critics; keyless stays single-shot; toggle persists (F177)"


def t_f178():
    # Global local-render concurrency bound: lessons x tournaments must not spawn
    # unbounded simultaneous local Manim subprocesses.
    import asyncio as _asyncio
    import threading
    import time as _time
    from dataclasses import replace as _replace

    import aetherlab.services.manim_runtime as mr
    from aetherlab.core.models import SceneBundle
    from aetherlab.services import render_backend as rb

    assert rb.LOCAL_RENDER_LIMIT >= 1
    assert rb._default_local_render_limit() >= 1

    live = {"cur": 0, "max": 0}
    lock = threading.Lock()

    class _FakeRuntime:
        def __init__(self, settings):
            pass

        def render_scene(self, scene, settings, quality, **_kwargs):
            with lock:
                live["cur"] += 1
                live["max"] = max(live["max"], live["cur"])
            _time.sleep(0.08)
            with lock:
                live["cur"] -= 1
            return _replace(scene, status="rendered", video_path="/x.mp4")

    old_sem, real_rt = rb._LOCAL_RENDER_SEM, mr.ManimRuntime
    rb._LOCAL_RENDER_SEM = threading.Semaphore(2)  # bound to 2 for the test
    mr.ManimRuntime = _FakeRuntime
    try:
        async def _run():
            backend = rb.LocalRenderBackend()
            scenes = [SceneBundle("S", "c", "manim", "compiled") for _ in range(6)]
            return await _asyncio.gather(
                *(backend.render(s, quality="l", settings=_settings(), timeout=60) for s in scenes)
            )
        results = _asyncio.run(_run())
    finally:
        rb._LOCAL_RENDER_SEM, mr.ManimRuntime = old_sem, real_rt

    assert all(r.status == "rendered" for r in results), "all six must still render"
    assert live["max"] <= 2, f"local render concurrency exceeded the bound: {live['max']}"
    assert live["max"] >= 2, f"the bound should be saturated (parallelised up to 2), got {live['max']}"
    return "global local-render concurrency bound prevents lesson x tournament thrash (F178)"


def t_f179():
    # ML §1 — embeddings: semantic exemplar retrieval. The flywheel's F173 winner
    # store becomes a live few-shot source: a proven-good past scene is re-served
    # to a semantically-similar future problem (keyword matching can't).
    from unittest import mock

    from aetherlab.services import embeddings as embeddings_module
    from aetherlab.services.scene_exemplars import (
        RETRIEVE_MIN_SIM,
        ExemplarCandidateStore,
        exemplar_block,
    )

    # Fail-soft primitives never raise on missing inputs.
    assert embeddings_module.nearest(None, None) == (-1, -1.0)
    assert embeddings_module.cosine(None, None) == 0.0

    if embeddings_module.available():
        v = embeddings_module.embed(["small-angle pendulum period", "mass on a spring oscillating", "electric dipole field lines"])
        assert v is not None and v.shape[0] == 3 and v.shape[1] >= 128
        assert abs(float((v[0] * v[0]).sum()) - 1.0) < 1e-3, "embeddings must be unit vectors"
        # An SHM pair is closer than SHM vs E&M — real semantic structure.
        assert embeddings_module.cosine(v[0], v[1]) > embeddings_module.cosine(v[0], v[2])

    code = ("from manim import *\nclass AetherLabScene(Scene):\n    def construct(self):\n"
            "        self.play(Create(Ellipse()))\n        self.wait(1)\n")
    data_dir = _TMP / "f179_dir"
    data_dir.mkdir(exist_ok=True)
    store = ExemplarCandidateStore(data_dir / "exemplar_candidates.json")  # canonical name exemplar_block reads
    assert store.record(domain="orbit", code=code, score=9.2, verdict="ship",
                        query_text="kepler elliptical orbit planet sun gravitation")

    if embeddings_module.available():
        entry = store.list()[0]
        assert isinstance(entry.get("embedding"), list) and len(entry["embedding"]) >= 128
        # Semantically-similar problem retrieves the stored winner (keyword miss).
        hit = store.retrieve("escape velocity from a planet's gravity")
        assert hit and hit["domain"] == "orbit" and hit["similarity"] >= RETRIEVE_MIN_SIM
        # An unrelated problem stays below the bar → no injection.
        assert store.retrieve("fourier series of a square wave") is None
        # exemplar_block appends the retrieved winner as a second few-shot example.
        block = exemplar_block(["kepler", "orbit"], {}, data_dir=data_dir)
        assert "Reference exemplar" in block and "Proven exemplar" in block

    # Backward compatible: no data_dir → curated exemplar only, no retrieval.
    assert "Proven exemplar" not in exemplar_block(["kepler", "orbit"], {})

    # Fail-soft: with the embedder disabled, retrieval yields nothing and the
    # curated exemplar path is unchanged — the keyless/no-model path is untouched.
    with mock.patch.object(embeddings_module, "embed_one", return_value=None):
        assert store.retrieve("anything at all") is None
        assert "Proven exemplar" not in exemplar_block(["kepler"], {}, data_dir=data_dir)
    return "semantic exemplar retrieval: past winners re-served to similar problems via embeddings (F179)"


def t_f180():
    # "Prove It" Phase A: the tournament A/B harness. The paired lift math must be
    # exact and deterministic — no renders, no provider key (that is Phase D).
    import inspect

    from tools import prompt_quality_lab as lab

    def _rep(scores, extra=0):
        return {"cases": [{"id": k, "status": "pass", "score": v} for k, v in scores.items()],
                "extra_renders": extra}

    on = _rep({"a": 8.0, "b": 6.0, "c": 5.0}, extra=4)
    off = _rep({"a": 6.0, "b": 6.02, "c": 7.0})
    pairing = lab.pair_ab_reports(on, off)
    assert pairing["n"] == 3
    assert pairing["mean_on"] == round((8.0 + 6.0 + 5.0) / 3, 3)
    assert pairing["mean_off"] == round((6.0 + 6.02 + 7.0) / 3, 3)
    assert pairing["mean_lift"] == round(pairing["mean_on"] - pairing["mean_off"], 3)
    # a: +2 win; b: -0.02 tie (within the noise band); c: -2 loss.
    assert (pairing["wins"], pairing["ties"], pairing["losses"]) == (1, 1, 1), pairing
    assert pairing["extra_renders"] == 4
    by = {p["id"]: p for p in pairing["per_prompt"]}
    assert by["a"]["delta"] == 2.0 and by["a"]["on"] == 8.0 and by["a"]["off"] == 6.0

    # Only the intersection of prompt ids is compared (robust to a dropped case).
    assert lab.pair_ab_reports(_rep({"a": 9.0}), _rep({"b": 1.0}))["n"] == 0

    # The verdict is a readable, honest sentence for each regime.
    lift = lab.pair_ab_reports(_rep({"a": 9.0, "b": 9.0}), _rep({"a": 5.0, "b": 5.0}))
    assert "LIFTS" in lift["verdict"], lift["verdict"]
    same = lab.pair_ab_reports(_rep({"a": 5.0}), _rep({"a": 5.0}))
    assert "identical" in same["verdict"].lower(), same["verdict"]
    worse = lab.pair_ab_reports(_rep({"a": 4.0, "b": 4.0}), _rep({"a": 8.0, "b": 8.0}))
    assert "did NOT help" in worse["verdict"], worse["verdict"]
    # BUG-32: a POSITIVE mean lift where more prompts individually regressed must
    # NOT be labelled "did NOT help" (it once read "did NOT help (mean +2.00)").
    mixed = lab.pair_ab_reports(_rep({"a": 9.0, "b": 5.0, "c": 5.0}), _rep({"a": 1.0, "b": 6.0, "c": 6.0}))
    assert mixed["mean_lift"] > 0 and mixed["losses"] > mixed["wins"], mixed
    assert "did NOT help" not in mixed["verdict"] and "Mixed" in mixed["verdict"], mixed["verdict"]

    # BUG-109: a numeric lift is not provider evidence when the critic silently
    # skipped most scenes, or when the ON arm never rendered a second candidate.
    axes = {axis: 1.0 for axis in lab._AB_VISION_AXES}

    def _vision_case(prompt_id, score=5.0):
        return {
            "id": prompt_id, "mode": "solve", "status": "pass", "score": score,
            "critic": {"score": score, "verdict": "revise", "breakdown_source": "vision", "breakdown": dict(axes)},
        }

    invalid_provider = lab.pair_ab_reports(
        {
            "allow_provider": True,
            "cases": [_vision_case("a"), {"id": "b", "mode": "solve", "status": "pass", "critic": {"score": 0, "breakdown_source": "static", "breakdown": dict(axes)}}],
            "extra_renders": 0,
            "tournament_evidence": {"tournaments": 1, "candidates": 1, "vision_scored": 1, "static_or_skipped": 0},
        },
        {"allow_provider": True, "cases": [_vision_case("a"), _vision_case("b")]},
    )
    assert invalid_provider["measurement_valid"] is False
    assert "1 of 2 solve cases" in invalid_provider["verdict"]
    assert "no multi-candidate choice" in invalid_provider["verdict"]
    assert invalid_provider["raw_verdict"] and "exploratory only" in invalid_provider["verdict"]
    assert "Provider measurement: **INVALID**" in lab.render_ab_markdown(invalid_provider)

    valid_provider = lab.pair_ab_reports(
        {
            "allow_provider": True,
            "cases": [_vision_case("a", 8.0)],
            "extra_renders": 1,
            "tournament_evidence": {"tournaments": 1, "candidates": 2, "vision_scored": 2, "static_or_skipped": 0},
        },
        {"allow_provider": True, "cases": [_vision_case("a", 7.0)]},
    )
    assert valid_provider["measurement_valid"] is True, valid_provider
    assert "Provider evidence passed" in valid_provider["verdict"]

    mismatched_provider = lab.pair_ab_reports(
        {
            "allow_provider": True,
            "cases": [_vision_case("a", 8.0), _vision_case("extra", 8.0)],
            "extra_renders": 1,
            "tournament_evidence": {"tournaments": 1, "candidates": 2, "vision_scored": 2, "static_or_skipped": 0},
        },
        {"allow_provider": True, "cases": [_vision_case("a", 7.0)]},
    )
    assert not mismatched_provider["measurement_valid"]
    assert mismatched_provider["unmatched_on"] == ["extra"]
    assert "prompt IDs" in mismatched_provider["verdict"]

    ledger_evidence = lab._tournament_critic_evidence
    # A candidate needs a complete five-axis critique and an actual critic
    # verdict; a static proxy carries axes too but remains "skipped".
    assert lab._candidate_has_vision_score({"score": 5.0, "verdict": "revise", "breakdown": dict(axes)})
    assert not lab._candidate_has_vision_score({"score": 10.0, "verdict": "skipped", "breakdown": dict(axes)})
    arm_data_dir = _TMP / "f180_provider_arm_data"
    ledger_path = arm_data_dir / "render_ledger.json"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps([{
        "job_id": "tournament-test",
        "candidates": [
            {"score": 5.0, "verdict": "revise", "breakdown": dict(axes)},
            {"score": 10.0, "verdict": "skipped", "breakdown": dict(axes)},
        ],
    }]), encoding="utf-8")
    assert ledger_evidence(arm_data_dir) == {
        "tournaments": 1, "candidates": 2, "vision_scored": 1, "static_or_skipped": 1,
    }
    assert lab._count_extra_renders(arm_data_dir) == 1

    # Markdown renders the comparison table without raising.
    md = lab.render_ab_markdown(lift)
    assert "Tournament A/B" in md and "| a |" in md

    # The CLI wires --ab into main; arms are isolated and toggle the tournament env.
    main_src = inspect.getsource(lab.main)
    assert "--ab" in main_src and "run_ab" in main_src
    ab_src = inspect.getsource(lab.run_ab)
    assert (
        "ab_" in ab_src and "extra_renders" in ab_src and "run_id" in ab_src
        and "measurement_valid" in ab_src and "return 2" in ab_src
    )
    assert "AETHERLAB_AUTO_TOURNAMENT" in inspect.getsource(lab._isolate_arm_env)
    isolate_src = inspect.getsource(lab._isolate_arm_env)
    assert "state_dir" in isolate_src and "arm-private" in isolate_src

    # Isolated state paths differ by invocation; an older ledger can't satisfy
    # the current run's extra-render or vision-coverage checks.
    import os as _os

    state_keys = (
        "AETHERLAB_DATA_DIR", "AETHERLAB_CACHE_PATH", "AETHERLAB_CHROMA_PATH",
        "AETHERLAB_LIBRARY_DIR", "AETHERLAB_AUTO_TOURNAMENT",
    )
    saved_state = {key: _os.environ.get(key) for key in state_keys}
    try:
        run_one = _TMP / "f180_run_one" / "data"
        run_two = _TMP / "f180_run_two" / "data"
        lab._isolate_arm_env(_TMP / "f180_arm", tournament=True, allow_provider=True, state_dir=run_one)
        assert _os.environ["AETHERLAB_DATA_DIR"] == str(run_one)
        lab._isolate_arm_env(_TMP / "f180_arm", tournament=True, allow_provider=True, state_dir=run_two)
        assert _os.environ["AETHERLAB_DATA_DIR"] == str(run_two)
        assert run_one != run_two
    finally:
        for key, value in saved_state.items():
            if value is None:
                _os.environ.pop(key, None)
            else:
                _os.environ[key] = value
    return "tournament A/B: provider evidence gate + fresh arm state + paired lift (BUG-109, F180)"


def t_f181():
    # "Prove It" Phase B: mine the render ledger for offline signal. The aggregation
    # is a pure function tested on synthetic jobs; then the real tournament wiring is
    # exercised end-to-end (difficulty/budget + the winner's HQ score are recorded).
    from tools.ledger_report import _pearson, load_jobs, summarize_ledger

    # Pearson is exact on a clean linear relation and None when undefined.
    assert _pearson([1, 2, 3], [2, 4, 6]) == 1.0
    assert _pearson([1, 2, 3], [6, 4, 2]) == -1.0
    assert _pearson([1, 1, 1], [1, 2, 3]) is None  # zero variance
    assert _pearson([1.0], [2.0]) is None           # n < 2

    def _tourney(jid, diff, cands, winner, hq):
        return {"job_id": f"tournament-{jid}", "status": "rendered", "difficulty": diff,
                "winner_index": winner, "winner_hq_score": hq,
                "candidates": [{"index": i, "score": s, "verdict": ("ship" if s >= 7 else "revise"),
                                "breakdown": {"legibility": 2.0, "composition": 1.0, "palette": 1.5,
                                              "structure": s / 5.0, "substance": 1.0}}
                               for i, s in enumerate(cands)]}

    jobs = [
        _tourney("a", 0.8, [5.0, 8.6], 1, 8.4),   # escalated: margin 3.6; draft 8.6 -> HQ 8.4
        _tourney("b", 0.2, [7.0, 7.1], 1, 6.0),   # escalated near-tie: margin 0.1; 7.1 -> HQ 6.0
        _tourney("c", 0.5, [9.0], 0, 9.2),        # single-candidate; keyed 9.0 -> HQ 9.2
        {"job_id": "cloud-x", "status": "fallback_local", "candidates": []},
        {"job_id": "cloud-y", "status": "failed", "candidates": []},
    ]
    s = summarize_ledger(jobs)

    assert s["totals"]["tournaments"] == 3 and s["totals"]["escalated"] == 2
    assert s["totals"]["fallbacks"] == 1 and s["totals"]["failures"] == 1
    assert s["totals"]["escalation_rate"] == round(2 / 3, 3)

    # Winner margin: two fan-outs (3.6 and 0.1); the 0.1 is a tie (barely moved).
    assert s["winner_margin"]["n"] == 2
    assert s["winner_margin"]["max"] == 3.6 and s["winner_margin"]["min"] == 0.1
    assert s["winner_margin"]["tie_count"] == 1

    # Draft->HQ: three keyed winners; correlation defined, means computed exactly.
    assert s["draft_vs_hq"]["n"] == 3 and s["draft_vs_hq"]["pearson_r"] is not None
    assert s["draft_vs_hq"]["mean_draft"] == round((8.6 + 7.1 + 9.0) / 3, 3)
    assert s["draft_vs_hq"]["mean_hq"] == round((8.4 + 6.0 + 9.2) / 3, 3)

    # Spend by difficulty places 0.8 in 'hard' and 0.2 in 'easy'.
    assert "hard" in s["spend_by_difficulty"] and "easy" in s["spend_by_difficulty"]
    assert s["spend_by_difficulty"]["hard"]["mean_candidates"] == 2.0
    assert s["weakest_axis"] in {"legibility", "composition", "palette", "structure", "substance"}
    assert s["verdict_mix"].get("ship", 0) >= 1

    # Fully fail-soft: a missing/corrupt ledger yields an empty, non-crashing report.
    assert load_jobs(_TMP / "no_ledger.json") == []
    assert summarize_ledger([])["totals"]["jobs"] == 0

    # End-to-end: a weak-draft escalating tournament records difficulty/budget and,
    # after the (stubbed) HQ repair, the winner's HQ score against the same job.
    import asyncio as _asyncio
    from dataclasses import replace as _replace

    from aetherlab.core.models import ProblemRequest, RagResult, SceneBundle, SolverResult
    from aetherlab.services.manim_runtime import ManimRuntime, SceneCandidate
    from aetherlab.services.render_ledger import RenderJobLedger

    dd = _TMP / "f181_led"
    dd.mkdir(exist_ok=True)
    st = _replace(_settings(), data_dir=dd, scene_candidates=2, openai_api_key="k", vision_model="v")
    rt = ManimRuntime(st)

    async def _fb(request, solver, rag, settings, aspect, progress, count=None, start_index=0, **_kwargs):
        return [SceneCandidate(index=start_index + i,
                               scene=SceneBundle("AetherLabScene", f"code{start_index + i}", "e",
                                                 "rendered", video_path="/x.mp4"),
                               storyboard={"acts": [{"beats": ["a", "b", "c"], "duration_s": 8}
                                                    for _ in range(4)]})
                for i in range(count or 0)]

    async def _fs(cands, settings, progress, **_kwargs):
        for c in cands:
            c.score, c.verdict = 5.0, "revise"   # weak draft -> forces escalation
        return cands

    async def _fr(scene, settings=None, quality="l", max_repairs=2, max_revisions=2, brief="", progress=None, **_kwargs):
        return _replace(scene, quality_score=8.7, critique_verdict="ship")

    rt._build_scene_candidates = _fb          # type: ignore[assignment]
    rt._render_and_score_candidates = _fs     # type: ignore[assignment]
    rt.render_scene_with_repair = _fr         # type: ignore[assignment]
    solver = SolverResult(summary="", derivation_steps=[], keywords=["orbit"], variables={}, model_name="t")
    _asyncio.run(rt.generate_render_tournament(
        ProblemRequest(prompt="x"), solver, RagResult(keywords=[], hits=[], backend="none"), st))
    job = RenderJobLedger(dd / "render_ledger.json").list()[0]
    assert job["winner_hq_score"] == 8.7 and job["winner_hq_verdict"] == "ship"
    assert job["budget"] >= 2 and job["difficulty"] > 0.0
    return "ledger report mines spend, winner margin, and the draft->HQ pair (F181)"


def t_f182():
    # "Prove It" Phase C: the learned keyless quality proxy. It must (1) be a no-op
    # when no model ships (so the --gate baseline cannot move), (2) apply learned
    # weights when present, and (3) recover known weights from ledger data.
    from unittest import mock

    from aetherlab.services import scene_critic as sc
    from aetherlab.services.scene_critic import CRITIC_AXES, static_quality_estimate
    from tools.train_quality_proxy import AXES, collect_pairs, fit_quality_proxy

    assert tuple(AXES) == tuple(CRITIC_AXES)

    # 1) No model -> keyless score is exactly the equal-weight sum (gate-safe).
    assert sc._load_quality_proxy(_TMP / "no_model.json") is None
    code = ("from manim import *\nclass S(Scene):\n    def construct(self):\n"
            "        for i in range(5):\n            self.play(Create(Dot()), run_time=2)\n        self.wait(2)\n")
    est = static_quality_estimate(code)
    assert est.breakdown_source == "static"
    assert abs(est.score - round(sum(est.breakdown.values()), 3)) < 1e-6, "no model -> equal-weight sum"

    # 2) _proxy_score applies weights + intercept and clamps to 0-10.
    assert sc._proxy_score({a: 2.0 for a in CRITIC_AXES},
                           {"weights": {a: 1.0 for a in CRITIC_AXES}, "intercept": 0.0}) == 10.0
    assert sc._proxy_score({a: 1.0 for a in CRITIC_AXES},
                           {"weights": {a: 0.0 for a in CRITIC_AXES}, "intercept": 4.2}) == 4.2

    # 3) The trainer recovers known weights from clean synthetic ledger data.
    import random
    rng = random.Random(0)
    true_w = {"legibility": 1.5, "composition": 0.5, "palette": 0.2, "structure": 1.0, "substance": 1.3}
    true_b = 0.4
    jobs = []
    for k in range(60):
        bd = {a: round(rng.uniform(0.0, 2.0), 3) for a in CRITIC_AXES}
        hq = true_b + sum(true_w[a] * bd[a] for a in CRITIC_AXES)
        jobs.append({"job_id": f"tournament-{k}", "winner_index": 0, "winner_hq_score": hq,
                     "candidates": [{"index": 0, "score": hq, "verdict": "ship", "breakdown": bd}]})
    pairs = collect_pairs(jobs)
    assert len(pairs) == 60
    fit = fit_quality_proxy(pairs, lam=1e-8)
    assert fit["r2"] > 0.999, fit["r2"]
    for a in CRITIC_AXES:
        assert abs(fit["weights"][a] - true_w[a]) < 0.02, (a, fit["weights"][a])
    assert abs(fit["intercept"] - true_b) < 0.05
    # collect_pairs ignores keyless/unscored jobs (no HQ score).
    assert collect_pairs([{"winner_index": 0, "winner_hq_score": 0.0,
                           "candidates": [{"index": 0, "breakdown": {a: 1.0 for a in CRITIC_AXES}}]}]) == []

    # 4) With a model present, static_quality_estimate uses it — via a patched loader
    #    so no global cache/env leaks into other tests' keyless path.
    loaded = sc._load_quality_proxy(None)  # default path (absent in repo) -> None
    assert loaded is None
    model = {"weights": {a: 0.0 for a in CRITIC_AXES}, "intercept": 3.0}
    with mock.patch.object(sc, "_load_quality_proxy", return_value=model):
        assert static_quality_estimate(code).score == 3.0

    # The trainer writes only a reviewable JSON model, never source code: its one
    # and only write is the model json (committed after human review).
    tool_src = Path("tools/train_quality_proxy.py").read_text(encoding="utf-8")
    assert "quality_proxy_model.json" in tool_src
    assert tool_src.count(".write_text(") == 1 and ".write_text(json.dumps(model" in tool_src
    return "learned keyless quality proxy: ledger-trained axis weights, gate-safe when absent (F182)"


# ══════════════════════════════════════════════════════════════════════════
# Redesign: planner-first / numeric-grounded / self-verifying pipeline
# ══════════════════════════════════════════════════════════════════════════

def t_f183():
    # Planner routes a prompt to the minimal useful set of output modalities.
    from aetherlab.core.models import OutputPlan, ProblemRequest
    from aetherlab.services.planner import Planner
    p = Planner(_settings())
    concept = p.heuristic_plan(ProblemRequest(prompt="Explain what entropy is conceptually"))
    dyn = p.heuristic_plan(ProblemRequest(prompt="Simulate the damped harmonic oscillator"))
    d3 = p.heuristic_plan(ProblemRequest(prompt="Visualize the electric field of a dipole in 3D"))
    assert concept.enabled() == ["pdf"], concept.enabled()
    assert dyn.needs_numeric and dyn.needs_animation and dyn.needs_2d
    assert d3.needs_3d
    assert OutputPlan.from_json(dyn.to_json()).needs_animation
    return f"planner routes: concept={concept.enabled()} dyn={dyn.enabled()} 3d={d3.enabled()}"


def t_f184():
    # Conditional pipeline: a conceptual prompt skips scene-gen + render.
    import dataclasses

    from aetherlab.core.models import ProblemRequest
    from aetherlab.services.pipeline import AetherLabPipeline
    st = dataclasses.replace(_settings(), openai_api_key=None)
    res = asyncio.run(AetherLabPipeline(st).run(ProblemRequest(prompt="Explain what entropy is conceptually")))
    assert res.plan is not None and not res.plan.needs_animation
    assert res.scene.status == "skipped", res.scene.status
    return f"conditional pipeline: plan={res.plan.enabled()} scene={res.scene.status}"


def t_f185():
    # Planner offline fallback is deterministic and self-labels.
    import dataclasses

    from aetherlab.core.models import ProblemRequest
    from aetherlab.services.planner import Planner
    st = dataclasses.replace(_settings(), openai_api_key=None)
    p = Planner(st)
    a = asyncio.run(p.plan(ProblemRequest(prompt="Simulate a pendulum")))
    b = asyncio.run(p.plan(ProblemRequest(prompt="Simulate a pendulum")))
    assert a.model_name == "heuristic-fallback"
    assert a.to_json() == b.to_json(), "offline plan must be deterministic"
    return f"offline planner deterministic: {a.enabled()}"


def t_f186():
    # UI gates the view pills by plan: pdf-only hides Canvas + Video.
    from aetherlab.core.models import OutputPlan
    from aetherlab.ui.widgets import SimulationPanel
    sp = SimulationPanel()
    byid = {sp._pill_group.id(b): b for b in sp._pill_group.buttons()}
    sp.apply_plan(OutputPlan(needs_2d=False, needs_3d=False, needs_animation=False, needs_pdf=True))
    assert byid[0].isHidden() and byid[1].isHidden() and not byid[2].isHidden(), "pdf-only hides canvas+video"
    sp.apply_plan(OutputPlan(needs_2d=True, needs_animation=True))
    assert not byid[0].isHidden() and not byid[1].isHidden(), "animation plan shows canvas+video"
    sp.close()
    return "view pills gated by plan (canvas/video hidden for pdf-only)"


def t_f187():
    # Numeric ground truth matches the closed-form underdamped solution.
    import math

    import numpy as np

    from aetherlab.services.numeric import fallback_numeric_spec, solve_numeric
    variables = {"damping": 0.15, "stiffness": 1.0, "mass": 1.0}
    sol = solve_numeric(fallback_numeric_spec(), variables, max_points=400)
    assert sol.ok, sol.note
    t = np.array(sol.t)
    x = np.array(sol.series("x"))
    c = variables["damping"]
    w0 = math.sqrt(variables["stiffness"] / variables["mass"])
    wd = math.sqrt(w0 * w0 - c * c)
    analytic = np.exp(-c * t) * (np.cos(wd * t) + (c / wd) * np.sin(wd * t))
    max_err = float(np.max(np.abs(x - analytic)))
    assert max_err < 1e-3, f"numeric vs analytic max_err={max_err}"
    bad = solve_numeric(
        {"state": ["x"], "rhs": ["__import__('os').system('x')"], "initial": [0.0], "t_range": [0, 1]}, {}
    )
    assert not bad.ok
    return f"numeric matches analytic (max_err={max_err:.2e}); unsafe rhs rejected"


def t_f188():
    # Canvas is driven by the exact numeric trajectory when a spec is present.
    import numpy as np

    from aetherlab.services.numeric import fallback_numeric_spec
    from aetherlab.ui.live_canvas import build_canvas_state
    variables = {"damping": 0.15, "stiffness": 1.0, "mass": 1.0}
    state = build_canvas_state("test", variables, plot=None, numeric_spec=fallback_numeric_spec())
    assert state.curves and state.curves[0].name == "x"
    y0 = float(np.asarray(state.curves[0].y_fn(np.array([0.0]), variables)).reshape(-1)[0])
    assert abs(y0 - 1.0) < 1e-6, f"x(0) should equal the initial condition, got {y0}"
    fb = build_canvas_state("test", variables, plot=None, numeric_spec={"bad": 1})
    assert fb.curves
    return f"canvas driven by numeric (x(0)={y0:.3f}); bad spec falls back safely"


def t_f189():
    # Formal research PDF: numeric-driven figure + RAG citations, compiled.
    from aetherlab.core.models import ProblemRequest, RagHit, RagResult
    from aetherlab.services.numeric import fallback_numeric_spec
    from aetherlab.services.research import build_latex, build_research_pdf
    solver = _solver(numeric_spec=fallback_numeric_spec())
    rag = RagResult(keywords=["oscillator"],
                    hits=[RagHit("OpenStax Vol 1.pdf", 213, 0.9, "damped oscillations")],
                    backend="test")
    req = ProblemRequest(prompt="Derive the damped harmonic oscillator")
    res = build_research_pdf(req, solver, rag, _TMP / "research189")
    assert res.tex_path.exists()
    assert res.pdf_path is not None and res.pdf_path.exists(), f"no pdf ({res.backend}): {res.note}"
    assert res.backend in {"pdflatex", "matplotlib"}
    assert res.citations == ["OpenStax Vol 1.pdf, p.213"], res.citations
    assert res.verification, "research PDF should embed physics verification checks"
    tex = build_latex(req, solver, rag, res.figure_path, verification=res.verification)
    assert "OpenStax" in tex and "includegraphics" in tex and "Derivation" in tex and "Verification" in tex
    return f"research pdf via {res.backend}, {len(res.citations)} citation(s), verified"


def t_f190():
    # pdflatex-free fallback: matplotlib renders a PDF + the numeric figure.
    from aetherlab.core.models import ProblemRequest
    from aetherlab.services.numeric import fallback_numeric_spec
    from aetherlab.services.research import _matplotlib_pdf, render_numeric_figure
    solver = _solver(numeric_spec=fallback_numeric_spec())
    out = _TMP / "research190"
    out.mkdir(parents=True, exist_ok=True)
    fig = render_numeric_figure(solver, out / "fig.png")
    assert fig and fig.exists(), "numeric figure should render"
    pdf = _matplotlib_pdf(ProblemRequest(prompt="Derive the oscillator"),
                          solver, ["Ref A, p.1"], fig, out / "fallback.pdf")
    assert pdf and pdf.exists(), "matplotlib fallback PDF should be produced"
    return f"matplotlib fallback pdf ok ({pdf.stat().st_size} bytes)"


def t_f191():
    # Trajectory component composes a compilable, numeric-driven scene.
    from aetherlab.services.numeric import fallback_numeric_spec
    from aetherlab.services.scene_components import compose_scene_code
    sv = _solver(numeric_spec=fallback_numeric_spec())
    code = compose_scene_code("AetherLabScene", sv, None)
    assert code is not None
    compile(code, "<scene>", "exec")
    assert "class AetherLabScene(Scene)" in code and "from manim import *" in code
    assert "point_at_time" in code and "set_points_as_corners" in code
    return f"trajectory component composes a compilable numeric-driven scene ({len(code)} chars)"


def t_f192():
    # 3-D surface is composed for needs_3d; nothing composes without a fit.
    from aetherlab.core.models import OutputPlan
    from aetherlab.services.scene_components import compose_scene_code
    sv = _solver()  # no numeric_spec
    code = compose_scene_code("AetherLabScene", sv, OutputPlan(needs_3d=True, needs_animation=True))
    assert code is not None and "ThreeDScene" in code
    compile(code, "<scene>", "exec")
    assert compose_scene_code("X", sv, OutputPlan(needs_3d=False)) is None
    return "3D surface composed for needs_3d; None otherwise"


def t_f193():
    # ManimRuntime prefers the curated component over LLM/static generation.
    import dataclasses

    from aetherlab.core.models import ProblemRequest
    from aetherlab.services.manim_runtime import ManimRuntime
    from aetherlab.services.numeric import fallback_numeric_spec
    st = dataclasses.replace(_settings(), openai_api_key=None)
    sv = _solver(numeric_spec=fallback_numeric_spec())
    bundle = asyncio.run(
        ManimRuntime(st).generate_scene_async(ProblemRequest(prompt="oscillator"), sv, _rag(), st)
    )
    assert bundle.status == "compiled", bundle.status
    assert any("curated component" in d for d in bundle.diagnostics), bundle.diagnostics
    assert "point_at_time" in bundle.code
    return "ManimRuntime composes from curated library (numeric-driven, no raw LLM code)"


def t_f194():
    # Verifier passes a physically-correct damped oscillator.
    from aetherlab.core.models import SolverResult
    from aetherlab.services.derivation_verify import verify_derivation_records
    from aetherlab.services.numeric import fallback_numeric_spec
    from aetherlab.services.verify import verify_solution
    sv = _solver(numeric_spec=fallback_numeric_spec())
    report = verify_solution(sv)
    assert report.ok, report.summary
    names = {c.name: c.passed for c in report.checks}
    assert names.get("finite") and names.get("boundedness") and names.get("energy"), names
    uncertain = SolverResult.from_json({
        "summary": "symbolic equation",
        "derivation_records": [{"from_expression": "x = y", "to_expression": "x*y = y**2"}],
    })
    assert verify_derivation_records(uncertain)["status"] == "not_checked"
    grounded = SolverResult.from_json({
        "summary": "mass is nonzero in this problem",
        "variables": {"F": 10, "m": 2, "a": 5},
        "derivation_records": [{"from_expression": "F = m*a", "to_expression": "a = F/m"}],
    })
    assert verify_derivation_records(grounded)["status"] == "passed"
    return f"verifier passes physical oscillator ({report.summary})"


def t_f195():
    # Verifier catches an unphysical result (anti-damped: energy grows).
    from aetherlab.core.models import SolverResult
    from aetherlab.services.verify import verify_solution
    anti = {"state": ["x", "v"],
            "rhs": ["v", "-(stiffness/mass)*x + (2*damping)*v"],
            "initial": [1.0, 0.0], "t_range": [0.0, 20.0], "observe": "x"}
    sv = SolverResult(summary="anti-damped", derivation_steps=[], keywords=["oscillator"],
                      variables={"damping": 0.15, "stiffness": 1.0, "mass": 1.0},
                      model_name="t", numeric_spec=anti)
    report = verify_solution(sv)
    failed = {c.name for c in report.checks if not c.passed}
    assert "energy" in failed and "boundedness" in failed, [c.name for c in report.checks]
    return f"verifier flags unphysical growth ({report.summary})"


# ══════════════════════════════════════════════════════════════════════════
# Quality integrity — no silent degradation (found by driving the live app)
# ══════════════════════════════════════════════════════════════════════════

def t_f196():
    # A transient provider error must NOT silently downgrade to canned physics.
    import dataclasses

    from aetherlab.core.models import ProblemRequest, SolverResult
    from aetherlab.services.llm import AsyncLLMCoordinator
    st = dataclasses.replace(_settings(), openai_api_key="fake-key-for-retry-test")
    req = ProblemRequest(prompt="Derive the damped harmonic oscillator")

    c = AsyncLLMCoordinator(st)
    calls = {"n": 0}
    async def flaky(_r):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("503 transient")
        return SolverResult(summary="real", derivation_steps=["s"], keywords=["k"],
                            variables={}, model_name=st.llm_model)
    c._solve_remote = flaky
    r = asyncio.run(c.solve(req))
    assert calls["n"] == 3, calls
    assert r.model_name == st.llm_model, f"must recover, not fall back: {r.model_name}"

    c2 = AsyncLLMCoordinator(st)
    calls2 = {"n": 0}
    async def always_fail(_r):
        calls2["n"] += 1
        raise RuntimeError("provider down")
    c2._solve_remote = always_fail
    r2 = asyncio.run(c2.solve(req))
    assert calls2["n"] == 3 and r2.model_name == "deterministic-fallback"
    # The downgrade must be stated plainly, not buried.
    assert "not solved physics" in r2.raw_response, r2.raw_response
    return "solver retries transient failures; persistent failure is reported loudly"


def t_f197():
    # A stingy/flaky plan must never drop a modality the heuristic requires.
    import dataclasses

    from aetherlab.core.models import OutputPlan, ProblemRequest
    from aetherlab.services.planner import Planner, _union
    stingy = OutputPlan(needs_numeric=False, needs_2d=False, needs_3d=False,
                        needs_animation=False, needs_pdf=True, rationale="pdf only",
                        model_name="qwen")
    floor = OutputPlan(needs_numeric=True, needs_2d=True, needs_3d=False,
                       needs_animation=True, needs_pdf=True)
    u = _union(stingy, floor)
    assert u.enabled() == ["numeric", "2d", "animation", "pdf"], u.enabled()
    assert "Heuristic floor also required" in u.rationale
    assert u.model_name == "qwen"  # keeps provenance

    # All remote attempts failing degrades to the floor, never below it.
    st = dataclasses.replace(_settings(), openai_api_key="fake-key-for-retry-test")
    p = Planner(st)
    calls = {"n": 0}
    async def boom(_r):
        calls["n"] += 1
        raise RuntimeError("planner down")
    p._plan_remote = boom
    got = asyncio.run(p.plan(ProblemRequest(prompt="Simulate the damped harmonic oscillator")))
    assert calls["n"] == 3, calls
    assert got.needs_animation and got.needs_numeric, got.enabled()
    return "planner unions with the heuristic floor and retries before conceding"


def t_f198():
    # The keyless fallback ODE models a damped oscillator: attach it only when
    # the question is one, so verification never claims checks it didn't run.
    import dataclasses

    from aetherlab.core.models import ProblemRequest
    from aetherlab.services.llm import AsyncLLMCoordinator
    from aetherlab.services.verify import verify_solution
    st = dataclasses.replace(_settings(), openai_api_key=None)

    off_topic = ProblemRequest(prompt="Explain what entropy is conceptually")
    sol = asyncio.run(AsyncLLMCoordinator(st).solve(off_topic))
    assert sol.numeric_spec is None, "must not attach an oscillator ODE to an entropy question"
    assert "No numeric model" in verify_solution(sol, off_topic).summary

    on_topic = ProblemRequest(prompt="Derive the damped harmonic oscillator")
    sol2 = asyncio.run(AsyncLLMCoordinator(st).solve(on_topic))
    assert sol2.numeric_spec is not None
    assert verify_solution(sol2, on_topic).ok
    return "fallback ODE only attached on-topic; off-topic verification stays honest"


def t_f199():
    # Text-mode math in Tex() aborts LaTeX ("Missing $ inserted." / "\mathcal
    # allowed only in math mode") and kills a whole render. Observed on real
    # cloud renders: Tex("m_1"), Tex("\theta_1"), Tex("\mathcal{L}").
    from aetherlab.services.scene_validation import (
        _needs_math_mode,
        check_latex_strings,
        repair_text_mode_math,
    )
    for s in ("m_1", r"\theta_1", r"\mathcal{L}", r"\frac{a}{b}", r"\vec{r}_1"):
        assert _needs_math_mode(s), f"{s!r} is math and must require math mode"
    for s in ("Hello world", "Energy (J)", "$m_1$", r"50\% done", r"\textbf{Bold}"):
        assert not _needs_math_mode(s), f"{s!r} is plain text and must stay Tex"

    code = (
        "from manim import *\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        '        a = Tex("m_1")\n'
        '        b = Tex("\\\\mathcal{L}")\n'
        '        c = Tex("Double pendulum")\n'
        '        d = MathTex("m_2")\n'
    )
    assert any("text-mode" in i for i in check_latex_strings(code)), "must be flagged"
    fixed, notes = repair_text_mode_math(code)
    assert len(notes) == 2, notes
    assert 'MathTex("m_1")' in fixed and 'MathTex("\\\\mathcal{L}")' in fixed
    assert 'Tex("Double pendulum")' in fixed and 'MathTex("m_2")' in fixed  # untouched
    assert not [i for i in check_latex_strings(fixed) if "text-mode" in i]
    compile(fixed, "<scene>", "exec")
    return "text-mode math promoted to MathTex (render-killer auto-repaired)"


def t_f200():
    # Pendulum problems get a real rod+bob driven by the *nonlinear* numeric
    # solution, chosen ahead of the generic time-series trajectory. The
    # component integrates its own pendulum ODE (needs no attached spec) and a
    # non-pendulum oscillator must still route to the trajectory curve.
    from aetherlab.services.numeric import fallback_numeric_spec
    from aetherlab.services.scene_components import compose_component_code
    pend = _solver(summary="Simple pendulum swings",
                   keywords=["pendulum"],
                   variables={"gravity": 9.81, "length": 1.0, "damping": 0.1})
    code = compose_component_code("AetherLabScene", pend)
    assert code is not None
    compile(code, "<scene>", "exec")
    assert "class AetherLabScene(Scene)" in code and "from manim import *" in code
    assert "nonlinear pendulum" in code and "TracedPath" in code and "np.interp" in code
    # Built its own spec — no numeric_spec on the solver.
    assert pend.numeric_spec is None
    # Regression: a plain oscillator (no pendulum signal) stays on the trajectory.
    osc = _solver(numeric_spec=fallback_numeric_spec())
    osc_code = compose_component_code("AetherLabScene", osc)
    assert osc_code and "point_at_time" in osc_code and "nonlinear pendulum" not in osc_code
    return f"pendulum component staged from nonlinear solution ({len(code)} chars); oscillator unaffected"


def t_f201():
    # A phase-space framing (v vs x) is composed only when the prompt asks for
    # it, driven by the exact integrated 2-state trajectory; a plain oscillator
    # without that framing keeps the time-series trajectory.
    from aetherlab.services.numeric import fallback_numeric_spec
    from aetherlab.services.scene_components import compose_scene_code
    ph = _solver(summary="Phase portrait of the damped oscillator",
                 keywords=["oscillator", "phase portrait"],
                 numeric_spec=fallback_numeric_spec())
    code = compose_scene_code("AetherLabScene", ph)
    assert code is not None
    compile(code, "<scene>", "exec")
    assert "phase portrait" in code and "MoveAlongPath" in code and "set_points_smoothly" in code
    # Regression: same spec, no phase framing -> the trajectory time series.
    plain = _solver(numeric_spec=fallback_numeric_spec())
    plain_code = compose_scene_code("AetherLabScene", plain)
    assert plain_code and "phase portrait" not in plain_code and "point_at_time" in plain_code
    return f"phase portrait composed on request ({len(code)} chars); default stays time-series"


def t_f202():
    # Electrostatics problems get a curated field-line scene (streamlines of the
    # charge configuration integrated in Python), since no time-ODE component
    # fires for them. A moving test charge guarantees on-screen motion.
    from aetherlab.services.scene_components import compose_component_code
    em = _solver(summary="Electric dipole field",
                 keywords=["electric", "dipole", "charge"],
                 variables={"separation": 2.4})
    code = compose_component_code("AetherLabScene", em)
    assert code is not None
    compile(code, "<scene>", "exec")
    assert "class AetherLabScene(Scene)" in code and "from manim import *" in code
    assert "electric field lines" in code and "MoveAlongPath" in code and "set_points_smoothly" in code
    # Regression: a plain oscillator is not mistaken for a field problem.
    from aetherlab.services.numeric import fallback_numeric_spec
    osc = compose_component_code("AetherLabScene", _solver(numeric_spec=fallback_numeric_spec()))
    assert osc and "electric field lines" not in osc
    return f"dipole field-line component composed ({len(code)} chars); oscillator unaffected"


def t_f203():
    # Fourier / series prompts get the rotating-vector epicycle build; the bare
    # word "harmonic" (harmonic oscillator) must NOT trigger it.
    from aetherlab.services.numeric import fallback_numeric_spec
    from aetherlab.services.scene_components import compose_component_code
    fo = _solver(summary="Fourier series of a square wave",
                 keywords=["fourier", "square wave"], variables={})
    code = compose_component_code("AetherLabScene", fo)
    assert code is not None
    compile(code, "<scene>", "exec")
    assert "Fourier epicycles" in code and "TracedPath" in code and "always_redraw" in code
    # Regression: harmonic *oscillator* stays a trajectory, not a Fourier scene.
    osc = compose_component_code(
        "AetherLabScene",
        _solver(keywords=["harmonic", "oscillator"], numeric_spec=fallback_numeric_spec()),
    )
    assert osc and "Fourier epicycles" not in osc and "point_at_time" in osc
    return f"Fourier epicycle component composed ({len(code)} chars); harmonic-oscillator not stolen"


def t_f204():
    # Quantum prompts get a wavepacket sloshing in a potential well (probability
    # density as a shaded Gaussian), not a bare graph.
    from aetherlab.services.numeric import fallback_numeric_spec
    from aetherlab.services.scene_components import compose_scene_code
    q = _solver(summary="Quantum harmonic oscillator wavefunction",
                keywords=["quantum", "wavefunction"], variables={})
    code = compose_scene_code("AetherLabScene", q)
    assert code is not None
    compile(code, "<scene>", "exec")
    assert "class AetherLabScene(Scene)" in code and "from manim import *" in code
    assert "quantum wavepacket" in code and "Polygon" in code and "always_redraw" in code
    # Regression: a *classical* harmonic oscillator stays a trajectory.
    osc = compose_scene_code("AetherLabScene",
                             _solver(keywords=["oscillator", "harmonic"], numeric_spec=fallback_numeric_spec()))
    assert osc and "quantum wavepacket" not in osc and "point_at_time" in osc
    return f"quantum wavepacket component composed ({len(code)} chars); classical oscillator unaffected"


def t_f205():
    # Interference / double-slit prompts get Young's two-source stage with an
    # intensity pattern; nothing else claims them.
    from aetherlab.services.scene_components import compose_component_code
    d = _solver(summary="Double-slit interference pattern",
                keywords=["double slit", "interference"], variables={})
    code = compose_component_code("AetherLabScene", d)
    assert code is not None
    compile(code, "<scene>", "exec")
    assert "double-slit interference" in code and "Arc" in code and "set_points_smoothly" in code
    # Regression: a plain oscillator is not mistaken for an interference problem.
    from aetherlab.services.numeric import fallback_numeric_spec
    osc = compose_component_code("AetherLabScene", _solver(numeric_spec=fallback_numeric_spec()))
    assert osc and "double-slit interference" not in osc
    # Review-pack regression: a quantum-framed double-slit prompt must still get
    # the fringe stage, not the wavepacket-in-a-well component.
    qd = compose_component_code("AetherLabScene", _solver(
        summary="Quantum double-slit interference of electrons",
        keywords=["double-slit interference", "quantum"], variables={}))
    assert qd and "double-slit interference" in qd and "quantum wavepacket" not in qd
    return f"double-slit interference component composed ({len(code)} chars); oscillator unaffected"


def t_f206():
    # Thermodynamics / kinetic-theory prompts get a gas of bouncing particles
    # (updater-driven, seeded) with a Maxwell-Boltzmann reference.
    from aetherlab.services.numeric import fallback_numeric_spec
    from aetherlab.services.scene_components import compose_scene_code
    g = _solver(summary="Kinetic theory of an ideal gas",
                keywords=["kinetic theory", "ideal gas"], variables={})
    code = compose_scene_code("AetherLabScene", g)
    assert code is not None
    compile(code, "<scene>", "exec")
    assert "kinetic theory" in code and "add_updater" in code and "velocity" in code
    # Deterministic: the same prompt bakes identical particle initial conditions.
    again = compose_scene_code("AetherLabScene", g)
    assert again == code, "kinetic-theory scene must be deterministic (seeded)"
    # Regression: a plain oscillator stays a trajectory.
    osc = compose_scene_code("AetherLabScene", _solver(numeric_spec=fallback_numeric_spec()))
    assert osc and "kinetic theory" not in osc and "point_at_time" in osc
    return f"kinetic-theory component composed + deterministic ({len(code)} chars); oscillator unaffected"


def t_f207():
    # The chaotic double pendulum integrates the full 4-state nonlinear system
    # and is chosen ahead of the single pendulum (whose domain also matches
    # "pendulum"). A single-pendulum prompt must still get the single component.
    from aetherlab.services.scene_components import compose_component_code
    dp = _solver(summary="Chaotic double pendulum",
                 keywords=["double pendulum", "chaos"], variables={"gravity": 9.81})
    code = compose_component_code("AetherLabScene", dp)
    assert code is not None
    compile(code, "<scene>", "exec")
    assert "class AetherLabScene(Scene)" in code and "from manim import *" in code
    assert "double pendulum" in code and "TracedPath" in code
    # Regression: a *single* pendulum is not stolen by the double-pendulum path.
    sp = compose_component_code("AetherLabScene",
                            _solver(keywords=["pendulum"], variables={"gravity": 9.81, "length": 1.0}))
    assert sp and "nonlinear pendulum" in sp and "double pendulum" not in sp
    return f"double-pendulum component integrates 4-state chaos ({len(code)} chars); single pendulum unaffected"


def t_f208():
    # Geometric optics: a thin-lens ray diagram with the image placed by the
    # thin-lens equation (real, inverted for an object beyond f).
    from aetherlab.services.numeric import fallback_numeric_spec
    from aetherlab.services.scene_components import compose_scene_code
    ln = _solver(summary="Thin-lens image formation",
                 keywords=["lens", "focal length"], variables={})
    code = compose_scene_code("AetherLabScene", ln)
    assert code is not None
    compile(code, "<scene>", "exec")
    assert "thin-lens ray diagram" in code and "MoveAlongPath" in code and "Ellipse" in code
    # Regression: a plain oscillator is not mistaken for an optics problem.
    osc = compose_scene_code("AetherLabScene", _solver(numeric_spec=fallback_numeric_spec()))
    assert osc and "thin-lens ray diagram" not in osc
    return f"thin-lens ray-diagram component composed ({len(code)} chars); oscillator unaffected"


def t_f209():
    # Standing wave: a resonant normal mode with fixed nodes and oscillating
    # antinodes; must not steal the plain (traveling) oscillator/wave default.
    from aetherlab.services.numeric import fallback_numeric_spec
    from aetherlab.services.scene_components import compose_component_code
    sw = _solver(summary="Standing wave on a string",
                 keywords=["standing wave", "normal mode"], variables={"mode": 3})
    code = compose_component_code("AetherLabScene", sw)
    assert code is not None
    compile(code, "<scene>", "exec")
    assert "standing wave" in code and "DashedVMobject" in code and "always_redraw" in code
    # Regression: a plain oscillator stays a trajectory.
    osc = compose_component_code("AetherLabScene", _solver(numeric_spec=fallback_numeric_spec()))
    assert osc and "standing wave" not in osc and "point_at_time" in osc
    return f"standing-wave component composed ({len(code)} chars); oscillator unaffected"


def t_f210():
    # Kepler orbit: integrates the real two-body problem and shows two equal-time
    # sectors (equal area by Kepler's 2nd law). Chosen for orbit/gravitation.
    from aetherlab.services.numeric import fallback_numeric_spec
    from aetherlab.services.scene_components import compose_component_code
    o = _solver(summary="Kepler orbit of a planet",
                keywords=["orbit", "kepler", "planet"], variables={})
    code = compose_component_code("AetherLabScene", o)
    assert code is not None
    compile(code, "<scene>", "exec")
    assert "class AetherLabScene(Scene)" in code and "from manim import *" in code
    assert "Kepler orbit" in code and "equal areas in equal times" in code and "TracedPath" in code
    # "hydrogen orbital" must not become a planetary orbit or an inaccurate
    # signed-heightfield probability density; no verified 3-D orbital component
    # is available yet.
    from aetherlab.core.models import OutputPlan
    ho = compose_component_code("AetherLabScene",
                            _solver(keywords=["orbital", "hydrogen", "3d"]),
                            OutputPlan(needs_3d=True))
    assert ho is None
    # Regression: a plain oscillator stays a trajectory.
    osc = compose_component_code("AetherLabScene", _solver(numeric_spec=fallback_numeric_spec()))
    assert osc and "Kepler orbit" not in osc and "point_at_time" in osc
    return f"Kepler-orbit component integrates two-body + equal-area law ({len(code)} chars)"


def t_f211():
    # surface3d renders the problem's ACTUAL field, not one generic bump: a
    # point-charge 1/r peak, a dipole, a saddle, or the Gaussian default — each
    # a real ThreeDScene that compiles. A quantum orbital is explicitly declined.
    from aetherlab.core.models import SolverResult
    from aetherlab.services.scene_components import surface3d
    cases = {
        "1/r potential": ["1/r", "potential of a"],
        "dipole potential": ["dipole"],
        "saddle: unstable": ["saddle", "unstable equilibrium"],
        "p-orbital": ["orbital", "hydrogen"],
        "Gaussian field": ["oscillator"],  # the default (also the F192 shape)
    }
    seen = set()
    for marker, kws in cases.items():
        sv = SolverResult(summary="3D field", derivation_steps=[], keywords=kws,
                          variables={}, model_name="t")
        code = surface3d.build("AetherLabScene", sv)
        if marker == "p-orbital":
            assert code is None
            continue
        assert code and "ThreeDScene" in code and marker in code, (marker, kws)
        compile(code, "<scene>", "exec")
        seen.add(marker)
    assert len(seen) == 4
    return "surface3d builds four supported scalar fields and declines a fake orbital density"


def t_f212():
    # Curated components track the problem's actual numbers: a supplied variable
    # changes the composed scene, while an empty solver still renders the
    # canonical default (so nothing regresses when the solver gives no numbers).
    from aetherlab.core.models import SolverResult
    from aetherlab.services.scene_components import (
        double_slit,
        fourier_epicycles,
        kinetic_theory,
        lens,
        orbit,
        quantum,
        standing_wave,
    )

    def sv(**variables):
        return SolverResult(summary="", derivation_steps=[], keywords=[],
                            variables=variables, model_name="t")

    # (component, marker-in-default, variables-that-must-change-the-output)
    cases = [
        (orbit, "Kepler orbit", {"eccentricity": 0.15}),
        (quantum, "quantum wavepacket", {"stiffness": 4.0, "mass": 1.0}),
        (double_slit, "double-slit interference", {"separation": 1.7, "wavelength": 0.6}),
        (fourier_epicycles, "Fourier epicycles", {"terms": 8}),
        (kinetic_theory, "kinetic theory", {"particles": 12, "temperature": 1500}),
        (lens, "thin-lens ray diagram", {"focal_length": 2.4, "object_distance": 5.0}),
        (standing_wave, "standing wave", {"mode": 5}),
    ]
    changed = []
    for module, marker, variables in cases:
        default = module.build("AetherLabScene", sv())
        assert default and marker in default, marker
        compile(default, "<scene>", "exec")
        tuned = module.build("AetherLabScene", sv(**variables))
        assert tuned and marker in tuned, marker
        compile(tuned, "<scene>", "exec")
        assert tuned != default, f"{marker}: variables {variables} did not change the scene"
        changed.append(marker.split()[0])
    # Fourier explicitly: 8 terms -> 8 odd harmonics baked in.
    assert "[1, 3, 5, 7, 9, 11, 13, 15]" in fourier_epicycles.build("S", sv(terms=8))
    return f"{len(changed)} curated components track solver variables; empty solver keeps canonical default"


def t_f213():
    # Coupled oscillators: integrate the real two-mass coupled ODE so the energy
    # visibly beats between the masses; chosen ahead of the single standing wave.
    from aetherlab.services.numeric import fallback_numeric_spec
    from aetherlab.services.scene_components import compose_component_code
    co = _solver(summary="Two coupled oscillators exchange energy",
                 keywords=["coupled oscillators", "two masses"],
                 variables={"stiffness": 1.0, "mass": 1.0})
    code = compose_component_code("AetherLabScene", co)
    assert code is not None
    compile(code, "<scene>", "exec")
    assert "class AetherLabScene(Scene)" in code and "from manim import *" in code
    assert "coupled oscillators" in code and "np.interp" in code and "set_points_smoothly" in code
    # Regression: a bare "standing wave" prompt still gets the standing wave.
    sw = compose_component_code("AetherLabScene", _solver(keywords=["standing wave"]))
    assert sw and "standing wave" in sw and "coupled oscillators" not in sw
    # Regression: a plain oscillator stays a trajectory.
    osc = compose_component_code("AetherLabScene", _solver(numeric_spec=fallback_numeric_spec()))
    assert osc and "coupled oscillators" not in osc and "point_at_time" in osc
    return f"coupled-oscillator component integrates the two-mass ODE ({len(code)} chars)"


def t_f214():
    # Concave mirror: reflective image formation by the mirror equation; a lens
    # prompt must still get the lens (mirror is excluded from the lens stems).
    from aetherlab.services.numeric import fallback_numeric_spec
    from aetherlab.services.scene_components import compose_scene_code
    mi = _solver(summary="Concave-mirror image formation",
                 keywords=["concave mirror", "mirror equation"], variables={})
    code = compose_scene_code("AetherLabScene", mi)
    assert code is not None
    compile(code, "<scene>", "exec")
    assert "concave mirror ray diagram" in code and "Arc(" in code and "MoveAlongPath" in code
    # Regression: a lens prompt is not stolen by the mirror path.
    ln = compose_scene_code("AetherLabScene", _solver(keywords=["lens", "focal length"]))
    assert ln and "thin-lens ray diagram" in ln and "concave mirror" not in ln
    # Regression: a plain oscillator is not mistaken for an optics problem.
    osc = compose_scene_code("AetherLabScene", _solver(numeric_spec=fallback_numeric_spec()))
    assert osc and "concave mirror ray diagram" not in osc
    return f"concave-mirror ray-diagram component composed ({len(code)} chars); lens unaffected"


def t_f215():
    # The verification gate must be able to go red. Drives a synthetic failing
    # run through all three layers that used to swallow it (BUG-60/61/62).
    import importlib.util
    import json as _json

    # (1) BUG-60: the harness process exit code follows the run.
    assert failure_exit_code({"F01": {"status": "PASS"}}) == 0
    assert failure_exit_code({"F01": {"status": "PASS"}, "F02": {"status": "FAIL"}}) == 1

    # (2) BUG-61/62: the generator refuses to relabel a failing defect feature
    #     FIXED, and a failing run overrides the hand-stamped Phase-4 column.
    root = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location(
        "_f215_tracker", root / "build_feature_tracker.py"
    )
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    defect_fid = next(iter(gen.DEFECTS))
    plain_fid = next(r[0] for r in gen.FEATURES if r[0] not in gen.DEFECTS)
    gen.apply_results({
        defect_fid: {"status": "FAIL", "note": "synthetic gate probe"},
        plain_fid: {"status": "FAIL", "note": "synthetic gate probe"},
    })
    status_col = gen.HEADERS.index("Status")
    phase4_col = gen.HEADERS.index("Phase-4 result")
    rows = {r[0]: r for r in gen.FEATURES}
    assert rows[defect_fid][status_col] == "REGRESSED", rows[defect_fid][status_col]
    assert "REGRESSION" in rows[defect_fid][status_col + 1]
    assert rows[defect_fid][phase4_col] == "FAIL", rows[defect_fid][phase4_col]
    assert rows[plain_fid][status_col] == "FAIL"
    assert rows[plain_fid][phase4_col] == "FAIL"
    unchecked_defect = next(fid for fid in gen.DEFECTS if fid != defect_fid)
    assert rows[unchecked_defect][status_col] == "PARTIAL", rows[unchecked_defect]
    assert rows[unchecked_defect][phase4_col] == "PENDING", rows[unchecked_defect]

    # (3) BUG-60: the integrity audit refuses to certify a run with failures,
    #     instead of absorbing them into a regenerated spreadsheet.
    from tools import tracker_integrity_audit as tia

    doctored = _TMP / "f215_results.json"
    live = _json.loads(tia.RESULTS_JSON.read_text(encoding="utf-8"))
    live[plain_fid] = {"status": "FAIL", "note": "synthetic gate probe"}
    doctored.write_text(_json.dumps(live), encoding="utf-8")
    original = tia.RESULTS_JSON
    try:
        tia.RESULTS_JSON = doctored
        report = tia.audit()
    finally:
        tia.RESULTS_JSON = original
    assert not report["ok"], "audit certified a run containing failures"
    assert any(
        "Feature harness failures recorded" in issue and plain_fid in issue
        for issue in report["issues"]
    ), report["issues"]
    return (
        f"gate fails loudly: exit code follows the run; {defect_fid} REGRESSED not FIXED; "
        f"Phase-4 overridden to FAIL; audit rejects failing results (F215)"
    ) + "; " + _explicit_practice_checks("test_catalog_fixture_paths", [
        (function, {"name": name})
        for function in ("test_fixture_paths_do_not_include_long_test_names", "test_repeated_story_calls_never_reuse_state")
        for name in ("_story_checks", "_explicit_practice_checks", "_practice_display_checks")
    ])


def t_f216():
    # Curated components get intro/closing explanation cards whose numbers come
    # from the component's own params()/numeric solve, stay LaTeX-free and use
    # only glyphs verified to render, and fill the requested duration.
    import re

    from aetherlab.services.code_safety import validate_code_safety
    from aetherlab.services.numeric import fallback_numeric_spec
    from aetherlab.services.scene_components import compose_scene_code, lens, pendulum
    from aetherlab.services.scene_components.explain import (
        _BUILDERS,
        add_explanation,
        explanation_for,
    )
    from aetherlab.services.scene_validation import (
        estimate_duration,
        scene_hygiene_warnings,
        validate_scene,
    )

    osc = fallback_numeric_spec()
    ode_vars = {"damping": 0.2, "stiffness": 1.5, "mass": 1.0}
    cases = [
        (["pendulum"], "Small-angle pendulum", {}, None),
        (["Kepler orbit"], "Kepler equal-area law", {}, None),
        (["standing wave"], "Standing wave on a string", {}, None),
        (["Fourier series"], "Fourier series", {}, None),
        (["electric dipole", "field lines"], "Dipole field lines", {}, None),
        (["double-slit interference", "quantum"], "Double-slit interference", {}, None),
        (["coupled oscillators"], "Coupled oscillators", {}, None),
        (["quantum", "wavefunction"], "Quantum harmonic oscillator", {}, None),
        (["kinetic theory"], "Ideal gas", {"temperature": 600}, None),
        (["lens"], "Thin lens", {}, None),
        (["concave mirror"], "Concave mirror", {}, None),
        (["double pendulum"], "Double pendulum", {}, None),
        (["phase portrait"], "Damped oscillator phase portrait", ode_vars, osc),
        (["oscillator"], "Damped spring", ode_vars, osc),
    ]
    for keywords, summary, variables, spec in cases:
        sv = _solver(summary=summary, keywords=keywords, variables=variables, numeric_spec=spec)
        code = compose_scene_code("AetherLabScene", sv, None, 30.0)
        assert code and "AetherLab explanation layer" in code, summary
        assert "MathTex" not in code and "Tex(" not in code, f"{summary}: explanation must stay LaTeX-free"
        assert validate_code_safety(code)[0], summary
        ok, issues = validate_scene(code, require_motion=True)
        assert ok, (summary, issues)
        assert not any("ACCUMULATION" in w for w in scene_hygiene_warnings(code)), summary
        est = estimate_duration(code).total_seconds
        assert 24.0 <= est <= 36.0, f"{summary}: {est:.1f}s outside 30s ±20%"
        # v4: light v2-style cards only. The v3 scaffold (a prediction card etc.
        # on every topic) was rated below v2, so it must not come back by default.
        assert "What the animation shows" in code and "Predict first" not in code, summary

    # Every explanation string uses only glyphs verified to render in Manim Text
    # (the subscript o/i forms rendered as blank boxes and were removed).
    verified = set("°²·½×ħΔΣγθλπψω₁₂→∂√∝≈")
    for name in _BUILDERS:
        for keywords, summary, variables, spec in cases:
            exp = explanation_for(name, _solver(summary=summary, keywords=keywords,
                                                variables=variables, numeric_spec=spec or osc))
            if not exp:
                continue
            text = " ".join([
                exp["heading"], exp["equation"], exp["watch"], exp["takeaway"], *exp["facts"],
                exp.get("predict", ""), exp.get("answer", ""), *(exp.get("misconception") or ()),
                *[c[0] for c in exp.get("captions", [])],
            ])
            bad = {c for c in text if ord(c) > 127} - verified
            assert not bad, f"{name}: unverified glyphs {bad}"

    # Numbers are the component's own: the lens image distance on screen is the
    # one the ray diagram draws, and the pendulum's first swing (57 degree
    # release) is measured longer than the small-angle formula.
    lens_sv = _solver(keywords=["lens"], variables={"focal_length": 2.2, "object_distance": 4.5})
    di = lens.params(lens_sv)["di"]
    assert any(f"{di:.2f}" in fact for fact in explanation_for("lens", lens_sv)["facts"])
    pend = explanation_for("pendulum", _solver(keywords=["pendulum"], variables={}))
    first = next(f for f in pend["facts"] if f.startswith("First swing"))
    assert float(first.split(":")[1].split()[0]) > 2.05, first
    assert "Wide swings take longer" in pend["takeaway"]
    assert pendulum.params(_solver(variables={}))["theta0"] == 1.0

    # Longer requests get longer holds; fail-soft on anything unusable.
    sv = _solver(keywords=["standing wave"], variables={})
    short = estimate_duration(compose_scene_code("S", sv, None, 20.0)).total_seconds
    long_ = estimate_duration(compose_scene_code("S", sv, None, 45.0)).total_seconds
    assert long_ > short, (short, long_)
    assert explanation_for("no-such-component", sv) is None
    assert add_explanation("not python (", {"heading": "h", "facts": ["f"]}) == "not python ("
    three_d = "from manim import *\nclass S(ThreeDScene):\n    def construct(self):\n        self.wait(1)\n"
    assert add_explanation(three_d, {"heading": "h", "facts": ["f"]}) == three_d

    # The clutter heuristic treats FadeOut(*self.mobjects) as a full cleanup.
    busy = "\n".join("        self.play(FadeIn(Dot()), run_time=0.1)" for _ in range(14))
    head = "from manim import *\nclass S(Scene):\n    def construct(self):\n"
    assert any("ACCUMULATION" in w for w in scene_hygiene_warnings(head + busy))
    cleared = head + busy + "\n        self.play(FadeOut(*self.mobjects))\n        self.play(FadeIn(Dot()))\n"
    assert not any("ACCUMULATION" in w for w in scene_hygiene_warnings(cleared))
    gathered = head + busy + "\n        _stage = Group(*self.mobjects)\n        self.play(FadeIn(Dot()))\n"
    assert not any("ACCUMULATION" in w for w in scene_hygiene_warnings(gathered))

    # The v3 devices stay available as opt-in ingredients. When an explanation
    # asks for them, captions run one at a time, point only at objects the
    # scene really creates, and the misconception is crossed out beside a thumbnail.
    from aetherlab.services.scene_components import compose_component_code

    base = compose_component_code("S", _solver(keywords=["pendulum"], variables={}))
    opted = add_explanation(base, {
        "heading": "h", "equation": "e", "watch": "w", "facts": ["f1", "f2"], "takeaway": "t",
        "predict": "Heavier bob?", "answer": "Same period.", "outro": "beside",
        "misconception": ("Heavier is faster.", "Mass cancels."),
        "captions": [("one", "bob"), ("two", "readout"), ("three", "no_such_name")],
    }, 30.0)
    assert "Predict first" in opted and "to_corner(UL" in opted and "Cross(_mis_wrong" in opted
    windows = [(float(a), float(b)) for a, b in re.findall(
        r"_cap_\d\.add_updater\(lambda m: m\.set_opacity\(_cap_alpha\(_clock\.get_value\(\), "
        r"([\d.]+), ([\d.]+)\)\)\)", opted)]
    assert len(windows) == 3 and all(b1 < a2 for (_, b1), (a2, _) in zip(windows, windows[1:]))
    anchors = set(re.findall(r"_cap_point_update\(m, _cap_\d, lambda: (\w+),", opted))
    assert anchors == {"bob", "readout"}, anchors   # the unknown anchor is dropped
    assert validate_scene(opted, require_motion=True)[0] and validate_code_safety(opted)[0]
    return (
        f"{len(cases)} curated scenes explained with light cards, safe, valid, ~30s; "
        f"glyphs verified; opt-in devices render correctly (F216)"
    )


def t_f217():
    # Each review topic gets its own creative scenario (a race, a stopwatch, a
    # build-up...) restaging the component's physics. Each must be safe, valid
    # and ~30 s, and its on-screen claims must hold numerically. A scenario
    # that breaks falls back to the plain component.
    import math

    import numpy as np

    from aetherlab.services.code_safety import validate_code_safety
    from aetherlab.services.scene_components import compose_scene_code, scenarios
    from aetherlab.services.scene_components.scenarios import (
        energy_buckets,
        field_arrows,
        fourier_buildup,
        kepler_stopwatch,
        pendulum_race,
        photon_buildup,
    )
    from aetherlab.services.scene_validation import estimate_duration, validate_scene

    topics = {
        "the pendulum race": ["pendulum"],
        "Kepler's stopwatch": ["Kepler orbit"],
        "two waves meet": ["standing wave"],
        "a square wave, one circle at a time": ["Fourier series"],
        "follow the arrows": ["electric dipole", "field lines"],
        "photon by photon": ["double-slit interference", "quantum"],
        "energy buckets": ["coupled oscillators"],
    }
    for marker, keywords in topics.items():
        code = compose_scene_code("S", _solver(keywords=keywords, variables={}), None, 30.0)
        assert code and f"scenario: {marker}" in code, (marker, code[:200] if code else code)
        assert "What the animation shows" in code and "MathTex" not in code, marker
        assert validate_code_safety(code)[0], marker
        ok, issues = validate_scene(code, require_motion=True)
        assert ok, (marker, issues)
        est = estimate_duration(code).total_seconds
        assert 24.0 <= est <= 36.0, f"{marker}: {est:.1f}s"
    assert len(set(scenarios.SCENARIOS.values())) == len(topics)

    sv = _solver(variables={})
    race = pendulum_race._race(sv)
    periods = {k: pendulum_race._first_period(race[k][2]) for k in ("short", "long", "small", "big")}
    assert abs(periods["long"] / periods["short"] - math.sqrt(2)) < 0.01, periods
    assert periods["big"] > 1.03 * periods["small"], periods

    orbit = kepler_stopwatch._orbit_samples(_solver(keywords=["Kepler orbit"], variables={}))
    areas, dists = orbit["area"], orbit["dist"]
    assert (max(areas) - min(areas)) / (sum(areas) / len(areas)) < 0.02, areas
    assert max(dists) / min(dists) > 2.0, dists

    over = fourier_buildup._overshoots([1, 3, 5, 7, 9, 11, 13, 15, 17])
    assert over[0] > over[-1] and 8.5 <= over[-1] <= 10.0, over

    k = 1.9
    two = np.array([h[1] for h in photon_buildup._sample(k, True, 520, 2026)])
    one = np.array([h[1] for h in photon_buildup._sample(k, False, 420, 926)])
    dark_two = float(np.mean(np.cos(k * two) ** 2 < 0.1))
    dark_one = float(np.mean(np.cos(k * one) ** 2 < 0.1))
    assert dark_two < 0.03 and dark_one > 0.1, (dark_two, dark_one)   # bands vs no bands

    run = energy_buckets._run(_solver(keywords=["coupled oscillators"], variables={}))
    assert run["peak_share"] > 0.85, run["peak_share"]
    assert abs(run["peak_t"] - run["transfer"]) / run["transfer"] < 0.1, (run["peak_t"], run["transfer"])

    stops = field_arrows._probes(2.4)
    assert stops[3][1] > stops[2][1] > stops[1][1] > stops[0][1] == 1.0, stops

    # Fail-soft: a scenario that raises leaves the plain component in place.
    original = pendulum_race.build
    try:
        def broken(*_a, **_k):
            raise RuntimeError("boom")
        pendulum_race.build = broken
        fallback = compose_scene_code("S", _solver(keywords=["pendulum"], variables={}), None, 30.0)
    finally:
        pendulum_race.build = original
    assert fallback and "nonlinear pendulum" in fallback and "scenario:" not in fallback
    return (
        f"{len(topics)} topic scenarios composed (safe, valid, ~30 s); race √2, equal areas, "
        f"Gibbs {over[-1]:.1f}%, bands vs hump, energy transfer {run['peak_share']:.0%} verified (F217)"
    )


def t_f218():
    # A concrete problem with its givens gets a ~1 minute video that solves it
    # (its own device: two shadows / two clocks / Newton's cannon) and proves
    # the answer with the simulation. Without givens, the topic scenario plays.
    import math
    import re

    from aetherlab.services.code_safety import validate_code_safety
    from aetherlab.services.scene_components import compose_scene_code
    from aetherlab.services.scene_components.problems import (
        moon_clock,
        orbit_period,
        projectile_landing,
    )
    from aetherlab.services.scene_validation import estimate_duration, validate_scene

    problems = {
        "where does the kicked ball land": _solver(
            summary="A ball is kicked at 18 m/s at 40 degrees. How far away does it land?",
            keywords=["projectile", "kicked ball"], variables={"v0": 18.0, "theta": 40.0}),
        "a grandfather clock on another world": _solver(
            summary="A grandfather clock pendulum is taken to the Moon. How long is one swing?",
            keywords=["pendulum", "Moon", "clock"], variables={"length": 0.994, "g": 1.62}),
        "how long is one lap of the ISS": _solver(
            summary="The ISS orbits 420 km above Earth. How long is one orbit?",
            keywords=["ISS", "orbit"], variables={"altitude_km": 420.0}),
    }
    verified = set("°²·½×ħΔΣγθλπψω₁₂→∂√∝≈⁰¹³⁴⁵⁶⁷⁸⁹")
    for marker, sv in problems.items():
        code = compose_scene_code("S", sv, None, 60.0)
        assert code and f"problem: {marker}" in code, marker
        assert "What the animation shows" not in code, f"{marker}: problem videos need no cards"
        assert validate_code_safety(code)[0], marker
        ok, issues = validate_scene(code, require_motion=True)
        assert ok, (marker, issues)
        assert estimate_duration(code).total_seconds >= 45.0, marker   # lower bound (loops count once)
        texts = " ".join(text for _, text in re.findall(r"Text\((['\"])(.*?)\1", code, re.S))
        bad = {c for c in texts if ord(c) > 127} - verified
        assert not bad, f"{marker}: unverified glyphs {bad}"

    # Without the givens the topic's explainer scenario plays instead.
    plain = compose_scene_code("S", _solver(keywords=["pendulum"], variables={}), None, 30.0)
    assert "scenario: the pendulum race" in plain
    kepler = compose_scene_code("S", _solver(keywords=["Kepler orbit"], variables={}), None, 30.0)
    assert "scenario: Kepler's stopwatch" in kepler

    # The numbers each video states hold up numerically.
    p = projectile_landing.params(problems["where does the kicked ball land"])
    sol = projectile_landing._solve(p)
    assert abs(sol["landing_num"] - sol["range"]) < 0.01 * sol["range"]
    assert abs(sol["range"] - 32.5) < 0.1 and abs(sol["t"] - 2.36) < 0.01, (sol["range"], sol["t"])
    assert abs(sol["what_if"][30] - sol["what_if"][60]) < 1e-6 and sol["what_if"][45] > sol["what_if"][30]
    assert projectile_landing.params(_solver(variables={"v0": 18.0, "theta": 0.698}))["angle"] > 39.9

    m = moon_clock._solve(moon_clock.params(problems["a grandfather clock on another world"]))
    assert abs(m["swing_earth"] - 1.0) < 0.01 and abs(m["swing_there"] - 2.46) < 0.01, m["swing_there"]
    assert abs(m["measured"] - m["swing_there"]) < 0.02 * m["swing_there"]
    assert abs(m["sync_length"] - 0.994 * 1.62 / 9.81) < 1e-9

    o = orbit_period._solve(orbit_period.params(problems["how long is one lap of the ISS"]))
    assert o["closure"] < 0.01 and abs(o["period"] / 60 - 92.8) < 0.2, o["period"] / 60
    assert abs((o["geo_r"] - 6.371e6) / 1000 - 35786) < 60, o["geo_r"]
    assert orbit_period._sci(6.791e6) == "6.79 × 10⁶"
    assert math.isclose(orbit_period.params(_solver(variables={"altitude": 420000.0}))["altitude_km"], 420.0)
    return (
        "3 problem videos (kicked ball 32.5 m, Moon clock 2.46 s, ISS 92.8 min) solve, "
        "self-check by simulation, use verified glyphs; plain topics keep scenarios (F218)"
    )


def t_f219():
    # A backup provider takes over any model call the primary fails (cut
    # connection, error status, empty reply), re-deriving model, temperature
    # and thinking flags for the backup's family. Kimi models get temperature 1.
    import asyncio
    import os
    from types import SimpleNamespace

    import httpx
    import openai

    from aetherlab.core.settings import load_settings, save_app_config
    from aetherlab.services import llm_client
    from aetherlab.services.model_policy import (
        fallback_settings,
        request_temperature,
        resolve_pathway,
    )

    assert resolve_pathway("k3-agent").fixed_temperature == 1.0
    assert resolve_pathway("MiniMax-M3").fixed_temperature is None

    saved = {k: os.environ.pop(k, None) for k in (
        "AETHERLAB_FALLBACK_OPENAI_API_KEY", "AETHERLAB_FALLBACK_OPENAI_BASE_URL", "AETHERLAB_FALLBACK_LLM_MODEL")}
    try:
        save_app_config({"fallback_api_key": "mm-key", "fallback_base_url": "https://api.minimax.io/v1",
                         "fallback_model": "MiniMax-M3"})
        s = load_settings()
        assert (s.fallback_llm_model, s.fallback_base_url) == ("MiniMax-M3", "https://api.minimax.io/v1")
        save_app_config({"fallback_api_key": None, "fallback_base_url": None, "fallback_model": None})
        assert fallback_settings(load_settings()) is None
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v

    calls = []

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            self.base_url = kwargs.get("base_url")
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

        async def _create(self, **kwargs):
            calls.append((self.base_url, kwargs))
            if "kimi" in self.base_url:
                raise openai.APIConnectionError(request=httpx.Request("POST", self.base_url))
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))])

    settings = SimpleNamespace(
        openai_api_key="k", openai_base_url="https://agent-gw.kimi.com/coding/v1", llm_model="k3-agent",
        vision_model=None, llm_timeout_seconds=900, llm_max_retries=0,
        fallback_api_key="m", fallback_base_url="https://api.minimax.io/v1", fallback_llm_model="MiniMax-M3")
    real = openai.AsyncOpenAI
    openai.AsyncOpenAI = FakeAsyncOpenAI
    try:
        client = llm_client.make_client(settings)
        reply = asyncio.run(client.chat.completions.create(
            model="k3-agent", temperature=request_temperature(settings, 0.2), messages=[]))
    finally:
        openai.AsyncOpenAI = real
    assert reply.choices[0].message.content == "ok"
    assert calls[0][1]["temperature"] == 1.0 and calls[1][1]["model"] == "MiniMax-M3"
    assert calls[1][1]["temperature"] == 0.2 and client.last_served_by == "MiniMax-M3"
    return "backup provider takes over a failed K3 call as MiniMax-M3 at the wanted temperature (F219)"


def t_f220():
    # Well-explained LaTeX PDFs: a topic gets a study guide, a problem gets
    # theory plus a step-by-step solution, a boxed answer and independent checks.
    # Model LaTeX can only break one equation (the compile heals); with no model
    # a document is still built from the solver.
    import asyncio
    import shutil
    from types import SimpleNamespace

    from aetherlab.__main__ import build_parser
    from aetherlab.core.models import ProblemRequest, RagResult
    from aetherlab.services import study_document as sd

    assert sd.classify("A ball is kicked at 18 m/s at 40 degrees. How far does it land?") == "problem"
    assert sd.classify("Explain Planck's law of blackbody radiation") == "topic"
    parsed = sd._parse_json(r'{"title": "t", "sections": [{"heading": "h", "paragraphs": ["p"],'
                            r' "equations": [{"latex": "\frac{a}{b} + \theta", "note": ""}]}]}')
    assert parsed["sections"][0]["equations"][0]["latex"] == "\\frac{a}{b} + \\theta"

    content = {
        "title": "Kicked ball", "restatement": "r", "given": [{"symbol": "v_0", "value": "18\\,\\mathrm{m/s}",
                                                                 "meaning": "speed"}],
        "find": ["range $R$"], "theory": [{"heading": "Projectiles", "paragraphs": ["two motions"],
                                          "equations": [{"latex": "x = v_x t", "note": ""}]}],
        "plan": ["time of flight", "range"],
        "steps": [{"title": "Time", "explanation": "up and down", "latex": "t = 2 v_y / g"},
                  {"title": "Oops", "explanation": "bad", "latex": "\\frac{1}{"}],
        "final_answer": {"statement": "R = 32.5 m", "latex": "R = 32.5\\,\\mathrm{m}"},
        "checks": ["units"], "common_mistakes": ["using degrees"], "summary": ["done"],
    }
    request = ProblemRequest(prompt="A ball is kicked at 18 m/s at 40 degrees. How far does it land?")
    doc = sd.build_document(content, "problem", request, ["Ref A"], ["simulated: 32.53 m"], None, "test")
    source, _ = doc.render(set())
    for piece in ("\\section{Theory you need}", "\\section{Solution}", "\\begin{answerbox}",
                  "Independent checks by AetherLab", "\\begin{warnbox}", "\\section*{References}"):
        assert piece in source, piece
    have_tex = shutil.which("pdflatex") is not None
    if have_tex:
        (_TMP / "f220").mkdir(exist_ok=True)
        pdf, repaired, error = sd.compile_healing(doc, _TMP / "f220" / "document.tex")
        assert pdf is not None and repaired == 1 and error == "", (repaired, error)

    out = asyncio.run(sd.write_study_document(
        ProblemRequest(prompt="Explain damped oscillations"), _solver(),
        RagResult(keywords=[], hits=[], backend="t"), SimpleNamespace(openai_api_key=None), _TMP / "f220b"))
    assert out.mode == "topic" and out.tex_path.exists() and (out.pdf_path is not None or not have_tex)

    assert build_parser().parse_args(["--pdf", "x"]).pdf == "x"
    src = Path("aetherlab/ui/main_window.py").read_text(encoding="utf-8")
    assert "write_study_document(" in src, "Export PDF uses the study document"
    return (
        f"topic/problem PDFs: parsed LaTeX JSON, theory + solution + answer + checks, "
        f"broken equation healed ({'pdflatex' if have_tex else 'no pdflatex'}), offline fallback, CLI --pdf (F220)"
    )


def t_f221():
    # Harder problem videos (v6): relativity, quantum, chaos and normal modes,
    # each with its own device, typeset math (with a text fallback when LaTeX
    # is missing), 80 s or more of full working, and a numerical proof of the
    # answer. They must not steal plain topics or the v5 problems.
    import ast
    import re

    from aetherlab.services.code_safety import validate_code_safety
    from aetherlab.services.scene_components import compose_scene_code
    from aetherlab.services.scene_components.problems import (
        chaos_horizon,
        coupled_swing,
        muon_paradox,
        quantum_dot,
    )
    from aetherlab.services.scene_components.problems._kit import VERIFIED_GLYPHS, plain_glyphs
    from aetherlab.services.scene_validation import estimate_duration, validate_scene

    cases = {
        "do the muons reach the ground": _solver(
            summary="Muons made 15 km up fly down at 0.995c; half-life 1.52 microseconds. What fraction arrives?",
            keywords=["muon", "time dilation"], variables={"h": 15000.0, "v": 0.995, "t_half": 1.52e-6}),
        "what colour does the trapped electron glow": _solver(
            summary="An electron in a 1.0 nm box (particle in a box) drops from n = 3 to n = 2. What colour?",
            keywords=["particle in a box"], variables={"L": 1.0e-9, "n_i": 3, "n_f": 2}),
        "how far ahead can we predict a double pendulum": _solver(
            summary="Two double pendulums start 1e-6 rad apart. When do they disagree? (chaos)",
            keywords=["double pendulum", "chaos"], variables={"theta1": 120.0, "theta2": -10.0, "delta": 1e-6}),
        "how long until the swing walks across": _solver(
            summary="Two 1 m pendulums coupled by a k = 1 N/m spring; one is pulled 10 degrees aside.",
            keywords=["coupled pendulums"], variables={"L": 1.0, "m": 1.0, "k": 1.0, "theta0": 10.0}),
    }
    for marker, sv in cases.items():
        code = compose_scene_code("S", sv, None, 60.0)
        assert code and f"problem: {marker}" in code, marker
        assert validate_code_safety(code)[0], marker
        ok, issues = validate_scene(code, require_motion=True)
        assert ok, (marker, issues)
        assert estimate_duration(code).total_seconds >= 60.0, marker   # lower bound (loops count once)
        assert "MathTex(tex" in code and "except Exception" in code, f"{marker}: typeset math needs its fallback"
        data = ast.literal_eval(re.search(r"^        D = (\{.*\})$", code, re.M).group(1))
        literals = "".join(t for _, t in re.findall(r"Text\((['\"])(.*?)\1", code, re.S))
        bad = (plain_glyphs(data) | {c for c in literals if ord(c) > 127}) - VERIFIED_GLYPHS
        assert not bad, f"{marker}: unverified glyphs {bad}"

    # The stated numbers hold up against independent calculations.
    m = muon_paradox._solve(muon_paradox.params(cases["do the muons reach the ground"]))
    assert abs(m["gamma"] - 10.01) < 0.01 and abs(m["t_lab"] * 1e6 - 50.28) < 0.05 and abs(m["tau"] * 1e6 - 5.02) < 0.01
    assert abs(m["relativistic"] - 0.1012) < 0.001 and m["classical"] < 1e-9
    assert abs(m["ode_fraction"] - m["relativistic"]) < 1e-6 and abs(m["survivors"] / m["n"] - m["relativistic"]) < 0.05
    q = quantum_dot._solve(quantum_dot.params(cases["what colour does the trapped electron glow"]))
    assert abs(q["e1"] - 0.376) < 0.001 and abs(q["lam"] - 659.4) < 0.5 and abs(q["lam_num"] - q["lam"]) < 0.5
    assert quantum_dot.colour_name(q["lam"]) == "red" and 520 < q["what_if"][0][1] < 540
    c = chaos_horizon._solve(chaos_horizon.params(cases["how far ahead can we predict a double pendulum"]))
    splits = [r["split"] for r in c["runs"]]
    assert abs(splits[0] - 12.85) < 0.3 and 4.0 < splits[1] - splits[0] < 10.0, splits
    assert abs(c["rate"] - 1.0) < 0.1 and c["drift"] < 1e-8
    w = coupled_swing._solve(coupled_swing.params(cases["how long until the swing walks across"]))
    assert abs(w["T"] - 10.32) < 0.05 and abs(w["T_sim"] - w["T"]) < 0.03 * w["T"] and w["left"] < 0.01

    # Plain topics and the v5 problems keep their own videos.
    assert "problem: how far ahead" not in (compose_scene_code("S", _solver(keywords=["double pendulum"]), None, 30.0) or "")
    assert "scenario: the pendulum race" in compose_scene_code("S", _solver(keywords=["pendulum"], variables={}), None, 30.0)
    kicked = _solver(summary="A ball is kicked at 18 m/s at 40 degrees. How far?", keywords=["projectile"],
                     variables={"v0": 18.0, "theta": 40.0})
    assert "problem: where does the kicked ball land" in compose_scene_code("S", kicked, None, 60.0)
    return (
        f"4 harder problem videos: muons (γ {m['gamma']:.1f}, {100 * m['relativistic']:.1f}% arrive), "
        f"quantum dot ({q['lam']:.0f} nm), chaos (split {splits[0]:.1f} s, +{splits[1] - splits[0]:.1f} s per 1000×), "
        f"coupled pendulums ({w['T']:.1f} s); typeset math with fallback, verified glyphs, routing kept (F221)"
    )


def t_f222():
    """Partial critic previews include the full event at their final sample."""
    from aetherlab.services.manim_runtime import _animation_range_for_times

    code = """from manim import *
class AetherLabScene(Scene):
    def construct(self):
        self.wait(2)
        self.play(Write(Text('one')), run_time=3)
        self.wait(5)
"""
    # Manim's -n START,END uses an exclusive end index.
    assert _animation_range_for_times(code, [4.0]) == (0, 2)
    assert _animation_range_for_times(code, [9.9]) == (1, 3)
    assert _animation_range_for_times(code, [4.0, 9.9]) == (0, 3)
    return "partial Manim preview covers all sampled events using exclusive end bound"


def t_f223():
    """A known solar-flux comparison is corrected; missing evidence stays explicit."""
    import asyncio
    from types import SimpleNamespace

    from aetherlab.core.models import ProblemRequest, RagResult
    from aetherlab.services import study_document as sd

    content = {
        "title": "Planck radiation",
        "worked_example": {
            "answer": (
                r"F=3.54\times 10^{7}\,\mathrm{W/m^2}, roughly half of the "
                "solar constant at Earth's orbit."
            )
        },
    }
    corrected, known_checks, citations = sd.audit_known_numeric_claims(content)
    answer = corrected["worked_example"]["answer"]
    assert "about 26,010 times" in answer and "blackbody surface" in answer
    assert known_checks[0]["status"] == "corrected" and known_checks[0]["ratio"] > 26000
    assert any("nssdc.gsfc.nasa.gov" in citation for citation in citations)

    request = ProblemRequest(prompt="Explain Planck radiation")
    rag = RagResult(keywords=[], hits=[], backend="empty")
    reviewed, report = asyncio.run(sd.review_study_claims(
        content, rag, SimpleNamespace(openai_api_key=None)
    ))
    document = sd.build_document(
        reviewed, "topic", request, report["citations"], [], None, "test", report
    )
    source, _ = document.render(set())
    assert report["status"] == "corrected"
    assert report["known_fact_checks"][0]["status"] == "corrected"
    assert report["source_review"]["status"] == "not_checked"
    assert "not certified" in report["note"]
    assert "Prose claim review (advisory)" in source
    assert "NASA Earth Fact Sheet" in source
    return "study PDF corrects solar comparison from NASA value and labels other prose unverified (F223)"


def t_f224():
    """Visual audits tolerate normal fades and compare ratios fairly."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "visual_regression_f224", str(Path("tools/visual_regression.py").resolve())
    )
    vr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vr)

    short_fade = [{"start": 3.1, "end": 3.93, "duration": 0.83}]
    assert vr.blank_span_warning(short_fade) is None
    fade_case = {"kind": "scene", "metrics": {
        "duration": 32.8, "fps": 30.0, "blank_ranges": short_fade,
        "blank_ratio": 0.055, "static_ranges": [],
    }}
    assert vr.quality_failures(fade_case) == []

    sustained_blank = {"kind": "scene", "metrics": {
        "duration": 32.8, "fps": 30.0,
        "blank_ranges": [{"start": 10.0, "end": 11.2, "duration": 1.2}],
        "blank_ratio": 0.11, "static_ranges": [],
    }}
    blank_reasons = vr.quality_failures(sustained_blank)
    assert any("blank span" in reason for reason in blank_reasons), blank_reasons
    assert any("blank ratio" in reason for reason in blank_reasons), blank_reasons
    assert "blank span" in (vr.blank_span_warning(sustained_blank["metrics"]["blank_ranges"]) or "")

    baseline = _TMP / "vr_duration_shift_baseline"
    baseline.mkdir(parents=True, exist_ok=True)
    (baseline / "summary.json").write_text(json.dumps({"cases": [
        {"id": "scene_x", "metrics": {
            "duration": 6.5, "frame_count": 195,
            "blank_ratio": 0.0, "static_ratio": 0.05,
        }},
        {"id": "scene_y", "metrics": {
            "duration": 20.0, "frame_count": 600,
            "blank_ratio": 0.0, "static_ratio": 0.05,
        }},
    ]}), encoding="utf-8")
    current = {"cases": [
        {"id": "scene_x", "metrics": {
            "duration": 32.8, "frame_count": 984,
            "blank_ratio": 0.055, "static_ratio": 0.20,
        }},  # substantially longer format; ratio comparison is not meaningful
        {"id": "scene_y", "metrics": {
            "duration": 20.1, "frame_count": 603,
            "blank_ratio": 0.03, "static_ratio": 0.12,
        }},  # similar length; real normalized regressions remain visible
    ]}
    comparison = vr.compare_report(baseline, current)
    rows = {row["id"]: row for row in comparison["deltas"]}
    assert rows["scene_x"]["ratio_comparison"] == "skipped_duration_changed"
    assert rows["scene_x"]["regressions"] == [], rows["scene_x"]
    assert rows["scene_y"]["ratio_comparison"] == "compared"
    assert rows["scene_y"]["regressions"] == [
        "blank ratio increased", "static ratio increased",
    ], rows["scene_y"]
    return "visual audit tolerates short scene fades and compares normalized deltas only at similar durations (F224)"


def t_f225():
    from collections import Counter

    from aetherlab.services.ent_physics_bank import (
        ENT_MAX_POINTS,
        ENT_TOPIC_IDS,
        ENT_TOTAL_QUESTIONS,
        QUESTIONS,
        canonical_topic,
        question_max_points,
        score_question,
    )

    assert len(QUESTIONS) == ENT_TOTAL_QUESTIONS == 40
    assert sum(question_max_points(question) for question in QUESTIONS) == ENT_MAX_POINTS == 50
    assert Counter("context" if question.context else question.kind for question in QUESTIONS) == {
        "single": 25, "context": 5, "multi": 5, "matching": 5,
    }
    assert {canonical_topic(question.topic) for question in QUESTIONS} == set(ENT_TOPIC_IDS)
    for question in QUESTIONS:
        assert set(question.prompt) == set(question.choices) == set(question.explanation) == {"kk", "ru", "en"}
        assert question.prompt["kk"] and question.prompt["ru"] and question.prompt["en"]
        assert question.explanation["kk"] and question.explanation["ru"] and question.explanation["en"]
        assert question.correct_indices
        assert question.solution_latex
        assert all(0 <= index < len(question.choices["kk"]) for index in question.correct_indices)
        assert question.reviewer == "pending_kazakhstan_physics_teacher"
        assert question.language_review_status == "pending_teacher_review_kk_ru_en"
        assert question.answer_verification_status == "author_checked_teacher_review_pending"
    assert score_question((0,), {"kind": "single", "correct_indices": (0,)}) == 1
    assert score_question((0,), {"kind": "multi", "correct_indices": (0, 1)}) == 1
    assert score_question((0, 0), {"kind": "matching", "correct_indices": (0, 1)}) == 1
    return "40 fixed-key questions span all 25 canonical topics; 50-point format and review-pending labels are explicit (F225)"


def t_f226():
    from aetherlab.services.ent_physics_bank import ENT_TOTAL_QUESTIONS
    from aetherlab.ui.exam_practice import _TEXT, ExamPracticeDialog

    for language in ("kk", "ru", "en"):
        dialog = ExamPracticeDialog(language, progress_path=_TMP / f"f226-{language}.json")
        assert dialog.windowTitle() == _TEXT[language]["title"]
        assert dialog._topic_combo.count() == 26  # all topics plus the unfiltered choice
        dialog._start()
        assert len(dialog._questions) == 10  # a short default practice session, not the full mock
        question = dialog._questions[0]
        correct = question["correct_indices"][0]
        dialog._answer_widgets[correct].click()
        dialog._check_answer()
        assert dialog._index in dialog._checked
        assert question["answer"] in dialog._feedback.text()
        dialog._next_question()
        dialog._previous()
        assert dialog._index == 0 and question["answer"] in dialog._feedback.text()
        dialog.close()
        mock = ExamPracticeDialog(language, progress_path=_TMP / f"f226-mock-{language}.json")
        size_field = mock._session_size.parentWidget()
        mock._session_size.setCurrentIndex(mock._session_size.findData(100))
        mock._mode_combo.setCurrentIndex(mock._mode_combo.findData("timed"))
        assert size_field.isHidden()
        mock._mode_combo.setCurrentIndex(mock._mode_combo.findData("practice"))
        assert not size_field.isHidden() and mock._session_size.currentData() == 100
        mock._mode_combo.setCurrentIndex(mock._mode_combo.findData("timed"))
        mock._start()
        assert len(mock._questions) == ENT_TOTAL_QUESTIONS
        mock.close()
    return "10-question practice and 40-question timed mock start in kk/ru/en; answer feedback and navigation work (F226); " + _explicit_practice_checks("test_exam_confirmation_localization", [
        ("test_timed_finish_is_localized_and_defaults_to_continue", {"language": language})
        for language in ("kk", "ru", "en")
    ]) + "; " + _answer_capture_checks()


def t_f227():
    import json
    from datetime import date, timedelta

    from aetherlab.services.ent_physics_bank import QUESTIONS
    from aetherlab.services.ent_practice_progress import (
        load_goals,
        load_mistake_ids,
        record_attempt,
        save_goals,
    )
    from aetherlab.ui.exam_practice import _TEXT as PRACTICE_TEXT
    from aetherlab.ui.exam_practice import ExamPracticeDialog

    path = _TMP / "f227-ent-progress.json"
    exam_date = (date.today() + timedelta(days=7)).isoformat()
    goals = {
        "target_score": 42,
        "exam_date": exam_date,
        "weekly_question_goal": 80,
        "preparation_level": "intermediate",
    }
    assert save_goals(path, goals) == load_goals(path)
    question = QUESTIONS[0]
    record_attempt(
        path,
        language="kk",
        topic_results={question.topic: {"correct": 0, "total": 1, "points": 0, "max_points": 1}},
        question_results={question.id: False},
        score=0,
        possible_points=1,
    )
    assert load_mistake_ids(path) == (question.id,)
    record_attempt(
        path,
        language="ru",
        topic_results={question.topic: {"correct": 1, "total": 1, "points": 1, "max_points": 1}},
        question_results={question.id: True},
        score=1,
        possible_points=1,
        mode="mistake_review",
    )
    assert load_mistake_ids(path) == ()
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert all("answers" not in attempt for attempt in saved["attempts"])
    assert len(saved["attempts"]) == 2
    dialog = ExamPracticeDialog(language="ru", progress_path=path)
    days_until_exam = (date.fromisoformat(exam_date) - date.today()).days
    countdown = PRACTICE_TEXT["ru"]["dashboard_date"].format(days=days_until_exam)
    assert countdown in dialog._dashboard_summary.text()
    dialog.close()
    recovery = _story_checks("test_progress_storage_recovery", (
        "test_mutations_do_not_replace_unreadable_progress",
        "test_goals_save_failure_keeps_draft_and_never_claims_success",
        "test_result_failure_freezes_answers_and_retry_records_once",
        "test_expired_mock_save_failure_stops_timer_and_retries_without_new_answers",
    ))
    reading = _story_checks("test_progress_read_views", (
        "test_all_progress_readers_propagate_io_without_changing_bytes",
        "test_practice_unavailable_progress_and_retry_preserve_saved_goals",
        "test_missing_and_malformed_progress_still_recover_as_before",
    ))
    numeric = _story_checks("test_practice_result_consistency", (
        "test_progress_nonfinite_numbers_do_not_crash_or_turn_into_scores",
        "test_nonfinite_progress_mutation_recovers_points_from_valid_history",
    ))
    return "goals and attempts persist locally; missed items clear on review and completed history omits selected answers (F227); " + recovery + "; " + reading + "; " + numeric + "; " + _answer_capture_checks()


def t_f228():
    import fitz

    from aetherlab.services.ent_physics_bank import glossary_for_language, questions_for_language
    from aetherlab.services.ent_practice_pdf import export_practice_pdf
    from aetherlab.ui.exam_practice import _TOPIC_NAMES

    for language in ("kk", "ru", "en"):
        question = questions_for_language(language)[0]
        meaning = next(item["meaning"] for item in glossary_for_language(language) if item["term_kk"] == question["kazakh_term"])
        question = {**question, "term_meaning": meaning}
        output = _TMP / f"f228-practice-{language}.pdf"
        export_practice_pdf(
            output,
            language=language,
            questions=(question,),
            user_answers=[question["answer"]],
            topic_names={question["topic"]: _TOPIC_NAMES[language][question["topic"]]},
            topic_progress={},
            score=1,
            possible_points=1,
            question_points=[1],
        )
        with fitz.open(output) as document:
            extracted = "\n".join(page.get_text() for page in document)
        normalized_extracted = " ".join(extracted.split()).translate(str.maketrans({
            "\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl",
            "\ufb03": "ffi", "\ufb04": "ffl",
        }))
        assert " ".join(question["prompt"].split()) in normalized_extracted
        assert " ".join(question["answer"].split()) in normalized_extracted
        assert "NCT" in normalized_extracted
    return "searchable PDF reports preserve prompt, answer key, and NCT attribution in all 3 locales (F228); " + _story_checks("test_practice_result_consistency", (
        "test_early_finish_pdf_totals_equal_screen_and_history",
        "test_empty_practice_pdf_does_not_claim_zero_out_of_selected_set",
        "test_timed_pdf_keeps_unanswered_questions_in_possible_score",
        "test_pdf_contains_rendered_formulas_and_complete_source_block",
        "test_formula_failure_does_not_replace_an_existing_report",
        "test_all_topic_formula_templates_can_be_rendered_for_report",
    )) + "; " + _story_checks("test_ui_fonts") + "; " + _story_checks("test_practice_pdf_transaction") + "; " + _explicit_practice_checks("test_mock_solution_display", [
        ("test_full_mock_pdf_contains_all_shared_equations", {"language": language})
        for language in ("kk", "ru", "en")
    ]) + "; " + _answer_capture_checks()


def t_f229():
    from aetherlab.services.ent_lesson_catalog import route_content

    content = [route_content(language) for language in ("kk", "ru", "en")]
    assert [item["language"] for item in content] == ["kk", "ru", "en"]
    assert all(item["route_id"] == "constant_acceleration" for item in content)
    assert all(item["sources"]["textbook"]["pdf_pages_1based"] == [15, 16, 17, 18, 20] for item in content)
    assert all(item["sources"]["nct_question"]["pdf_question_page_1based"] == 2 for item in content)
    assert all(item["sources"]["nct_question"]["pdf_answer_key_page_1based"] == 37 for item in content)
    assert all(item["review_status"]["kazakh_terms_and_translations"] == "needs_teacher_review" for item in content)
    keys = [item["answer_key"]["choice_id"] for item in content]
    assert keys == ["B", "B", "B"]
    return "fixed route retains textbook/NCT page evidence, one answer key, and honest translation-review status (F229)"


def t_f230():
    from aetherlab.ui.student_views import _COPY, StudentDashboard

    for language in ("kk", "ru", "en"):
        view = StudentDashboard(_TMP / f"f230-{language}.json", language=language)
        assert view.title.text() == _COPY[language]["hello"]
        assert view.topic_button.text() == _COPY[language]["continue"] + "  →"
        assert view.plan_title.text() == _COPY[language]["study_plan"]
        selected = []
        view.practice_topic_requested.connect(selected.append)
        view.topic_button.click()
        assert selected == [view._hero_topic_id]
        view.close()
    return "student home labels and actions follow the selected kk/ru/en locale (F230); " + _story_checks("test_progress_read_views", (
        "test_student_views_retain_snapshot_on_error_and_retry_recovers",
        "test_initial_unavailable_views_do_not_show_zero_or_empty_progress",
        "test_switch_to_unreadable_profile_does_not_show_previous_student_snapshot",
    )) + "; " + _story_checks("test_practice_result_consistency", (
        "test_invalid_aggregate_records_do_not_crash_student_views",
    )) + "; " + _practice_display_checks((
        "test_perfect_small_sample_does_not_claim_mistakes_or_a_weak_topic",
        "test_cleared_mistakes_do_not_remain_a_dashboard_action",
        "test_mock_mistakes_are_recommended_in_their_topic",
    )) + "; " + _story_checks(
        "test_ui_layout_regressions",
        ("test_startup_and_spider_status_follow_selected_language",),
    )


def t_f231():
    import inspect

    from aetherlab.ui.exam_practice import ExamPracticeDialog
    from aetherlab.ui.library_panel import LibraryPanel
    from aetherlab.ui.reference_sources import _COPY, ReferenceSourcesDialog

    empty = _TMP / "f231-empty-reference-root"
    empty.mkdir(exist_ok=True)
    for language in ("kk", "ru", "en"):
        assert set(_COPY[language]) == set(_COPY["kk"]) == set(_COPY["ru"]) == set(_COPY["en"])
        dialog = ReferenceSourcesDialog(source_root=empty, language=language)
        copy = _COPY[language]
        assert dialog.windowTitle() == copy["title"]
        assert dialog._tabs.tabText(0) == copy["books_tab"]
        assert dialog._tabs.tabText(1) == copy["mocks_tab"]
        assert dialog._open_button.text() == copy["open_file"]
        assert dialog._books.item(0).text() == copy["no_books"]
        assert dialog._mocks.item(0).text() == copy["no_mocks"]
        assert dialog._note.text() == copy["books_note"]
        dialog._tabs.setCurrentIndex(1)
        assert dialog._note.text() == copy["mocks_note"]
        dialog.close()

        populated = _TMP / f"f231-populated-{language}"
        populated.mkdir(exist_ok=True)
        (populated / "Физика Закирова 10 ЖМ.pdf").touch()
        (populated / "testcenter_sample.pdf").touch()
        populated_dialog = ReferenceSourcesDialog(source_root=populated, language=language)
        assert populated_dialog._books.count() == 1
        assert copy["scan_pdf"] in populated_dialog._books.item(0).text()
        assert populated_dialog._mocks.count() == 1
        mock_detail = populated_dialog._mocks.item(0).text()
        assert copy["question_set"] in mock_detail and copy["folder_material"] in mock_detail
        populated_dialog.close()
    assert "language=language" in inspect.getsource(LibraryPanel._open_reference_sources)
    assert "language=self._language" in inspect.getsource(ExamPracticeDialog._open_local_mock_sources)
    assert "install_ui_fonts()" in inspect.getsource(ReferenceSourcesDialog.__init__)
    return "source browser labels, guidance and entry-point locale propagation pass for kk/ru/en (F231)"


def _story_checks(module_name: str, names: tuple[str, ...] = ()) -> str:
    """Reuse the focused behavioural regressions as catalog evidence.

    These tests require only tmp_path and monkeypatch. A skipped dependency is
    not converted into a pass, and fixtures are undone between checks.
    """
    import importlib.util
    import uuid

    import pytest

    path = Path(__file__).parent / "tests" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(f"_story_{module_name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    checks = names or tuple(name for name in vars(module) if name.startswith("test_"))
    assert checks, f"No behavioural checks selected for {module_name}"
    invocation = uuid.uuid4().hex
    for index, name in enumerate(checks):
        fn = getattr(module, name)
        folder = _TMP / "s" / invocation / str(index)
        folder.mkdir(parents=True, exist_ok=True)
        with pytest.MonkeyPatch.context() as patch:
            available = {"tmp_path": folder, "monkeypatch": patch}
            parameters = inspect.signature(fn).parameters
            unsupported = set(parameters) - set(available)
            assert not unsupported, f"Unsupported fixtures for {name}: {unsupported}"
            try:
                output = fn(**{key: available[key] for key in parameters})
                if inspect.isawaitable(output):
                    asyncio.run(output)
            except pytest.skip.Exception as exc:
                raise RuntimeError(f"Behaviour not verified: {name}: {exc}") from exc
    return f"{len(checks)} behavioural checks in tests/{module_name}.py: {', '.join(checks)}"


def t_f232():
    from collections import Counter

    from aetherlab.services.ent_topic_bank import build_topic_exercises

    items = build_topic_exercises()
    assert len(items) == 2500
    assert set(Counter(item["topic"] for item in items).values()) == {100}
    assert len({item["id"] for item in items}) == len(items)
    for item in items:
        assert set(item["prompt"]) == {"kk", "ru", "en"}
        for language in ("kk", "ru", "en"):
            assert len(set(item["choices"][language])) == 4, item["id"]
        assert item["solution_latex"]
        assert item["reviewer"] == "pending_kazakhstan_physics_teacher"
    return "2500 stable authored exercise IDs; 100/topic; three locales and unique choices; teacher review pending; " + _practice_bank_acceptance("F232") + "; " + _topic_solution_checks(render=False) + "; " + _story_checks(
        "test_ent_practice_mvp", ("test_hydrostatic_practice_converts_pascals_to_kilopascals",))


def t_f233():
    from aetherlab.services.ent_topic_bank import build_topic_exercises
    assert all(len(item["solution_latex"]) == 3 for item in build_topic_exercises())
    return _story_checks("test_ui_layout_regressions", (
        "test_practice_filters_prevent_empty_sets_and_results_save_once",
        "test_cancelled_timed_practice_stops_without_saving_a_result",
    )) + "; " + _story_checks("test_practice_result_consistency", (
        "test_unattempted_review_label_does_not_imply_deduction",
    )) + "; " + _practice_display_checks() + "; " + _story_checks("test_practice_explanation_display", (
        "test_unsupported_or_incomplete_formula_is_not_guessed",
        "test_all_topic_explanations_are_readable_without_changing_questions",
    )) + "; " + _story_checks("test_mock_solution_display", (
        "test_every_mock_has_shared_renderable_worked_math",
        "test_numerical_mock_keys_and_worked_answers_match_independent_calculation",
        "test_typeset_failure_keeps_readable_math_and_never_shows_raw_latex",
    )) + "; " + _explicit_practice_checks("test_mock_solution_display", [
        ("test_completed_review_contains_typeset_equations_and_clears_previous_resources", {"language": language, "mode": mode})
        for language in ("kk", "ru", "en") for mode in ("practice", "timed")
    ]) + "; " + _answer_capture_checks() + "; " + _topic_solution_checks(render=True)


def _explicit_practice_checks(module_name: str, cases: list[tuple[str, dict]]) -> str:
    """Expand these Qt parametrizations without weakening the fixture adapter."""
    import runpy
    import uuid

    namespace = runpy.run_path(str(Path(__file__).parent / "tests" / f"{module_name}.py"))
    invocation = uuid.uuid4().hex
    for index, (name, arguments) in enumerate(cases):
        folder = _TMP / "s" / invocation / str(index)
        folder.mkdir(parents=True, exist_ok=True)
        namespace[name](tmp_path=folder, **arguments)
    return f"{len(cases)} explicit locale/mode checks in {module_name}"


def _practice_display_checks(names: tuple[str, ...] = ()) -> str:
    """Run the locale regressions with explicit isolated inputs.

    The general story adapter only supplies fixtures; it does not expand pytest
    parametrization. These two tests need one explicit language per case.
    """
    import runpy
    import uuid

    module_name = "test_practice_explanation_display"
    namespace = runpy.run_path(str(Path(__file__).parent / "tests" / f"{module_name}.py"))
    invocation = uuid.uuid4().hex
    checks = names or (
        "test_feedback_and_review_do_not_expose_latex",
        "test_perfect_small_sample_does_not_claim_mistakes_or_a_weak_topic",
    )
    for index, name in enumerate(checks):
        for language in ("kk", "ru", "en"):
            folder = _TMP / "s" / invocation / str(index) / language
            folder.mkdir(parents=True, exist_ok=True)
            namespace[name](language, folder)
    return f"{len(checks) * 3} practice display checks in kk/ru/en: {', '.join(checks)}"


def t_f234():
    return _story_checks("test_student_profiles", (
        "test_profiles_keep_practice_goals_and_review_files_separate",
        "test_dashboard_profile_button_opens_profile_flow_and_can_switch",
        "test_main_window_switches_all_student_views_to_the_selected_profile",
    )) + "; " + _story_checks("test_atomic_json") + "; " + _story_checks("test_profile_read_recovery", (
        "test_unreadable_existing_registry_is_not_reset_on_open",
        "test_unreadable_registry_cannot_be_overwritten_by_create_or_activation",
        "test_missing_and_malformed_registry_keep_legacy_progress_recovery",
        "test_main_window_profile_read_failure_retains_current_views",
    ))


def t_f235():
    return _story_checks("test_student_profiles", (
        "test_profile_names_are_required_unique_and_bounded",
        "test_profile_button_retranslates_without_changing_profile_name",
    )) + "; " + _story_checks("test_profile_editing") + "; " + _story_checks("test_profile_read_recovery", (
        "test_profile_refresh_failure_preserves_choices_and_retries",
        "test_profile_selection_failure_cannot_edit_wrong_learner",
        "test_discard_read_failure_retains_draft_until_retry",
        "test_saved_profile_reports_refresh_failure_without_partial_creation",
        "test_unreadable_dialog_initialization_retries_in_all_languages",
    ))


def t_f236():
    return _story_checks("test_ai_help_quota") + "; " + _story_checks("test_ai_quota_io")


def t_f237():
    return _story_checks("test_ui_layout_regressions", (
        "test_weekly_mock_day_dashboard_reminds_and_offers_timed_shortcut",
        "test_dashboard_weekly_mock_shortcut_opens_timed_practice",
    ))


def t_f238():
    return _story_checks("test_exam_resume_and_proctoring", (
        "test_active_exam_answers_round_trip_and_timer_keeps_running_while_closed",
        "test_full_mock_timer_uses_ninety_minutes_and_resume_keeps_answers",
    )) + "; " + _story_checks("test_progress_storage_recovery", (
        "test_autosave_failure_is_visible_and_close_retries_current_answer",
        "test_unreadable_resume_is_not_treated_as_no_attempt",
        "test_pending_result_resumes_frozen_and_stale_session_cannot_duplicate",
        "test_successful_result_with_failed_cleanup_resumes_completed_snapshot",
    )) + "; " + _explicit_practice_checks("test_exam_confirmation_localization", [
        (name, {"language": language})
        for name in (
            "test_dismissing_resume_preserves_exact_saved_answers_and_localizes_buttons",
            "test_timed_finish_is_localized_and_defaults_to_continue",
        ) for language in ("kk", "ru", "en")
    ] + [
        ("test_explicit_resume_or_start_again_uses_the_chosen_attempt", {"choice": choice})
        for choice in ("Yes", "No")
    ]) + "; " + _story_checks("test_exam_confirmation_localization", (
        "test_unresumable_question_ids_are_not_silently_discarded",
    )) + "; " + _answer_capture_checks()


def t_f239():
    return _story_checks("test_exam_resume_and_proctoring", (
        "test_shadow_camera_flags_are_sparse_and_recover_after_face_returns",
        "test_camera_downtime_does_not_count_as_observed_missing_or_multiple_faces",
        "test_attempt_persists_only_allowlisted_camera_event_metadata",
    ))


def t_f240():
    return _story_checks("test_teacher_review") + "; " + _story_checks("test_school_view_io_recovery", (
        "test_teacher_review_reports_load_failure_and_retry_restores_scores",
    )) + "; " + _story_checks("test_progress_read_views", (
        "test_unreadable_progress_is_not_uploaded_or_hidden_from_school_views",
    ))


def t_f241():
    return _story_checks("test_school_leaderboard", (
        "test_local_ranking_groups_by_school_and_only_counts_full_mocks",
        "test_leaderboard_dialog_shows_local_rank_and_each_mock_score",
    )) + "; " + _story_checks("test_school_view_io_recovery", (
        "test_local_ranking_reports_initial_and_refresh_failure_without_clearing_scores",
        "test_score_history_clears_empty_placeholder_span_when_changing_student",
    )) + "; " + _story_checks("test_leaderboard_mode_switch", (
        "test_clearing_endpoint_restores_local_rows_instead_of_labelling_remote_rows_local",
        "test_clearing_endpoint_with_read_failure_does_not_claim_local_data_loaded",
    ))


def t_f242():
    return _story_checks("test_school_leaderboard", (
        "test_shared_server_merges_scores_across_devices",
        "test_same_username_and_school_id_reuses_remote_student_identity",
        "test_same_username_and_school_id_share_participant_key_on_two_devices",
        "test_school_id_is_not_returned_and_db_stores_only_hmac",
    )) + "; " + _story_checks("test_school_view_io_recovery", (
        "test_leaderboard_endpoint_save_error_keeps_draft_and_reports_storage_error",
    )) + "; " + _story_checks("test_leaderboard_mode_switch", (
        "test_environment_endpoint_override_is_effective_after_save",
        "test_dialog_explains_active_environment_override_in_each_language",
        "test_invalid_environment_override_blocks_sync_with_configuration_diagnosis",
        "test_sync_uses_and_displays_effective_environment_endpoint",
    )) + "; " + _story_checks("test_progress_read_views", (
        "test_sync_progress_error_has_local_diagnosis_and_never_makes_request",
    ))


def t_f243():
    return _story_checks("test_school_leaderboard", (
        "test_server_rejects_invalid_mock_scores_and_remote_http_url",
    ))


def t_f244():
    return _story_checks("test_gamification_progress", (
        "test_companion_picker_selects_one_of_three_and_accepts_choice",
        "test_dashboard_companion_button_persists_the_selected_companion",
        "test_legacy_pet_choice_requires_reselection_without_losing_points",
    )) + "; " + _story_checks("test_progress_storage_recovery", (
        "test_companion_save_failure_retains_confirmed_choice",
    ))


def t_f245():
    return _story_checks("test_gamification_progress", (
        "test_companion_evolves_at_lifetime_point_milestones",
        "test_companion_choice_and_lifetime_points_are_profile_local",
        "test_dashboard_companion_uses_score_not_topic_progress_and_remembers_choice",
    ))


def t_f246():
    return _story_checks("test_ui_layout_regressions", (
        "test_topic_search_filter_and_lesson_route_work_together",
        "test_topic_cards_never_show_as_desktop_windows",
    )) + "; " + _story_checks("test_gamification_progress", (
        "test_topic_confidence_uses_minimum_sample_and_accuracy_threshold",
        "test_topic_catalog_explains_confidence_state_and_keeps_actions",
    )) + "; " + _story_checks("test_progress_read_views", (
        "test_student_views_read_one_consistent_file_per_refresh",
        "test_topic_unknown_state_keeps_learning_actions_and_search",
    ))


def t_f247():
    return _story_checks("test_localized_ui_regressions", (
        "test_library_history_and_settings_follow_the_selected_language",
        "test_command_lab_and_lesson_controls_retranslate_without_losing_values",
    ))


def t_f248():
    return _story_checks("test_settings_startup_sync")


def t_f249():
    return _story_checks("test_cloud_media_check") + "; " + _story_checks(
        "test_cloud_failure_diagnosis") + "; " + _profile_transport_checks()


def t_f250():
    return _story_checks("test_lesson_practice_h")


def t_f251():
    import pytest
    # The reused module's autouse fixture is not run by this function adapter.
    # Clear its exact override inventory before executing the real cases.
    import runpy
    namespace = runpy.run_path(str(Path(__file__).parent / "tests/test_render_profile.py"))
    with pytest.MonkeyPatch.context() as patch:
        for name in namespace["_PROFILE_ENV_VARS"]:
            patch.delenv(name, raising=False)
        return (_story_checks("test_render_profile") + "; " + _profile_transport_checks() + "; "
                + _render_cache_checks() + "; " + _story_checks("test_render_quality_flags", (
                    "test_p_flag_resolves_to_1440p60", "test_p_flag_accepted_from_settings_and_env",
                    "test_p_flag_gets_adaptive_fps_policy")))


_answer_capture_check_cache = {}


def _answer_capture_checks():
    """Execute the real parametrized Qt/storage/scoring matrix without windows."""
    import hashlib
    import subprocess
    import uuid
    import xml.etree.ElementTree as ET
    from collections import Counter
    from aetherlab.core.proc import subprocess_kwargs

    root = Path(__file__).resolve().parent
    sources = ("tests/test_practice_answer_capture.py", "tests/test_practice_session_start.py",
               "aetherlab/ui/exam_practice.py", "aetherlab/services/ent_practice_pdf.py",
               "aetherlab/services/mathtext.py", "aetherlab/ui/fonts.py",
               "aetherlab/services/ent_practice_progress.py", "aetherlab/services/ent_physics_bank.py",
               "aetherlab/services/ent_topic_bank.py",
               "aetherlab/services/ent_mock_solutions.py", "aetherlab/core/atomic_json.py")
    signature = tuple(hashlib.sha256((root / path).read_bytes()).hexdigest() for path in sources)
    if signature in _answer_capture_check_cache:
        return _answer_capture_check_cache[signature]
    folder = _TMP / ("answers-" + uuid.uuid4().hex[:12])
    folder.mkdir()
    report = folder / "tests.xml"
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen",
                       PHYSLAB_RUN_NATIVE_UI_ACCEPTANCE="0", PHYSLAB_REQUIRE_NATIVE_QT="0")
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/test_practice_answer_capture.py",
        "tests/test_practice_session_start.py",
        "-q", "-p", "no:cacheprovider", f"--basetemp={folder / 'cases'}", f"--junitxml={report}"],
        cwd=root, env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=180, **subprocess_kwargs())
    (folder / "pytest.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    assert result.returncode == 0, (result.stdout + result.stderr)[-4000:]
    cases = list(ET.parse(report).iter("testcase"))
    assert all(not any(case.find(tag) is not None for tag in ("failure", "error")) for case in cases)
    expected = {
        "test_cleared_controls_replace_saved_answer": 90,
        "test_check_of_cleared_response_never_keeps_old_points": 12,
        "test_partial_matching_keeps_one_point_and_placeholder": 27,
        "test_checked_answer_remains_committed": 12,
        "test_pending_result_retry_preserves_cleared_response": 18,
        "test_full_mock_clear_is_unanswered_and_scores_48_of_50": 6,
        "test_read_only_snapshot_keeps_old_bytes_and_retry_saves_clear": 6,
        "test_reopen_restores_cleared_answer_in_same_attempt": 12,
        "test_expiry_and_pdf_use_cleared_answer": 6,
        "test_review_mistakes_resolves_saved_attempt_before_replacement": 27,
        "test_restart_refusal_preserves_snapshot_and_retry": 6,
        "test_unreadable_snapshot_blocks_both_entry_points_and_retry_resumes": 6,
        "test_unresumable_snapshot_is_not_replaced_by_review": 6,
        "test_resuming_pending_result_from_setup_records_once": 6,
        "test_resume_uses_saved_language_for_both_setup_actions": 6,
        "test_empty_mistakes_never_replace_a_saved_attempt": 3,
        "test_removal_verification_failure_blocks_start_until_retry": 6,
    }
    assert Counter(case.attrib["name"].split("[")[0] for case in cases) == expected
    skipped = [case for case in cases if case.find("skipped") is not None]
    assert not skipped if os.name == "nt" else all(
        case.attrib["name"].startswith(("test_read_only_snapshot_", "test_restart_refusal_")) for case in skipped)
    assert signature == tuple(hashlib.sha256((root / path).read_bytes()).hexdigest() for path in sources)
    note = (f"{len(cases) - len(skipped)} executed practice persistence/scoring/export cases (BUG-254/255/256): kk/ru/en, "
            "multi/matching clear, navigation, autosave, close/resume, early/timed finish, "
            "partial credit, checked/frozen results, write-failure retry, 48/50 full mocks, "
            "actual expiry/PDFs and guarded Start/Review mistakes replacement; offscreen")
    _answer_capture_check_cache[signature] = note
    return note


_topic_solution_check_cache = {}


def _topic_solution_checks(*, render: bool):
    """Keep the pure generator checks independent of the optional Qt renderer."""
    import hashlib
    import subprocess
    import uuid
    import xml.etree.ElementTree as ET
    from collections import Counter
    from aetherlab.core.proc import subprocess_kwargs

    root = Path(__file__).resolve().parent
    sources = ("tests/test_topic_solution_notation.py", "aetherlab/services/ent_topic_bank.py",
               "aetherlab/services/mathtext.py", "aetherlab/ui/qt_compat.py")
    signature = tuple(hashlib.sha256((root / path).read_bytes()).hexdigest() for path in sources)
    key = (signature, render)
    if key in _topic_solution_check_cache:
        return _topic_solution_check_cache[key]
    folder = _TMP / ("topic-math-" + uuid.uuid4().hex[:12])
    folder.mkdir()
    report = folder / "tests.xml"
    command = [sys.executable, "-m", "pytest", "tests/test_topic_solution_notation.py", "-q",
               "-p", "no:cacheprovider", f"--basetemp={folder / 'cases'}", f"--junitxml={report}"]
    if not render:
        command += ["-k", "not test_first_and_last_worked_steps_typeset_without_fallback"]
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen",
                       PHYSLAB_RUN_NATIVE_UI_ACCEPTANCE="0", PHYSLAB_REQUIRE_NATIVE_QT="0")
    result = subprocess.run(command, cwd=root, env=environment, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=120, **subprocess_kwargs())
    (folder / "pytest.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    assert result.returncode == 0, (result.stdout + result.stderr)[-4000:]
    cases = list(ET.parse(report).iter("testcase"))
    expected = {"test_negative_powers_keep_the_whole_exponent_in_every_substitution": 2,
                "test_nanometre_conversion_uses_the_requested_length_as_unknown": 1,
                "test_all_generated_steps_keep_negative_exponents_grouped": 1,
                "test_keys_and_units_agree_with_independent_physics_in_all_languages": 3}
    if render:
        expected["test_first_and_last_worked_steps_typeset_without_fallback"] = 6
    assert Counter(case.attrib["name"].split("[")[0] for case in cases) == expected
    assert all(not any(case.find(tag) is not None for tag in ("failure", "error", "skipped")) for case in cases)
    assert signature == tuple(hashlib.sha256((root / path).read_bytes()).hexdigest() for path in sources)
    note = (f"{len(cases)} executed topic-math checks (BUG-257/258): grouped negative powers in all 2500 "
            "worked sets, 100 nanometre quantities, 300 independently calculated magnetic/photon/size keys "
            "and units in kk/ru/en" + ("; 18 actual equation images" if render else "; generator checks require no Qt"))
    _topic_solution_check_cache[key] = note
    return note


_render_cache_check_cache = {}


def _render_cache_checks():
    """Run actual saved-session, worker, runtime and nested policy cache cases."""
    import hashlib
    import subprocess
    import uuid
    import xml.etree.ElementTree as ET
    from aetherlab.core.proc import subprocess_kwargs
    root = Path(__file__).resolve().parent
    sources = ("tests/test_render_cache_policy.py", "tests/test_render_cache_reuse.py", "tests/test_cache_compatibility_paths.py",
               "aetherlab/core/models.py", "aetherlab/core/render_cache.py", "aetherlab/core/render_profile.py",
               "aetherlab/core/cache.py", "aetherlab/services/pipeline.py", "aetherlab/ui/workers.py",
               "aetherlab/services/manim_runtime.py", "aetherlab/services/segmented_pipeline.py",
               "aetherlab/services/lesson_pipeline.py", "aetherlab/services/voiceover.py")
    signature = tuple(hashlib.sha256((root / path).read_bytes()).hexdigest() for path in sources)
    if signature in _render_cache_check_cache:
        return _render_cache_check_cache[signature]
    folder = _TMP / ("render-cache-" + uuid.uuid4().hex)
    folder.mkdir()
    report = folder / "tests.xml"
    process = subprocess.run([sys.executable, "-m", "pytest", "tests/test_render_cache_policy.py",
        "tests/test_render_cache_reuse.py", "tests/test_cache_compatibility_paths.py", "-q", "-p", "no:cacheprovider",
        f"--basetemp={folder / 'cases'}", f"--junitxml={report}"], cwd=root,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, **subprocess_kwargs())
    (folder / "pytest.log").write_text(process.stdout + process.stderr, encoding="utf-8")
    assert process.returncode == 0, (process.stdout + process.stderr)[-3000:]
    cases = list(ET.parse(report).iter("testcase"))
    assert cases and all(not any(case.find(tag) is not None for tag in ("failure", "error", "skipped")) for case in cases)
    assert signature == tuple(hashlib.sha256((root / path).read_bytes()).hexdigest() for path in sources)
    note = (f"{len(cases)} executed render-cache cases: SQLite/worker profile changes preserve solver/RAG/code, "
            "invalidate stale media, retain prior files, and guard runtime draft/final reuse; adaptive chapter/segment keys")
    _render_cache_check_cache[signature] = note
    return note


_profile_transport_cache = {}


def _profile_transport_checks():
    """Execute fixture/parameterized profile-to-cloud checks, never a live job."""
    import hashlib
    import subprocess
    import uuid
    import xml.etree.ElementTree as ET
    from aetherlab.core.proc import subprocess_kwargs

    root = Path(__file__).resolve().parent
    sources = ("tests/test_render_profile_transport.py", "aetherlab/core/render_profile.py",
               "aetherlab/core/settings.py", "aetherlab/services/render_backend.py",
               "aetherlab/services/manim_runtime.py", ".github/workflows/render.yml")
    signature = tuple(hashlib.sha256((root / path).read_bytes()).hexdigest() for path in sources)
    if signature in _profile_transport_cache:
        return _profile_transport_cache[signature]
    folder = _TMP / ("profile-transport-" + uuid.uuid4().hex)
    folder.mkdir()
    report = folder / "tests.xml"
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/test_render_profile_transport.py",
        "-q", "-p", "no:cacheprovider", f"--basetemp={folder / 'cases'}", f"--junitxml={report}"],
        cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120, **subprocess_kwargs())
    (folder / "pytest.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    assert result.returncode == 0, (result.stdout + result.stderr)[-3000:]
    cases = list(ET.parse(report).iter("testcase"))
    assert cases and all(not any(case.find(tag) is not None for tag in ("failure", "error", "skipped")) for case in cases)
    assert signature == tuple(hashlib.sha256((root / path).read_bytes()).hexdigest() for path in sources)
    note = (f"{len(cases)} executed profile transport cases: owned GitHub client, actual API payload, "
            "Bash worker canvas guard, encoded custom-size/FPS media, cached-profile refusal and staged download; no live cloud job")
    _profile_transport_cache[signature] = note
    return note


def t_f252():
    return _story_checks("test_dubbing_ru_kk")


def t_f253():
    return _story_checks("test_encoder_budget_contract") + "; " + _story_checks("test_render_quality_flags", (
        "test_command_passes_inflight_encoders_default_4", "test_command_inflight_encoders_env_override_and_clamp")) + "; " + _encoder_budget_acceptance()


def _encoder_budget_acceptance():
    import uuid
    import build_feature_tracker as tracker
    from tools.accept_encoder_budget import DETAIL, run_acceptance
    from tools.feature_acceptance import verify_acceptance
    root = Path(__file__).resolve().parent
    row = dict(zip(tracker.HEADERS, next(item for item in tracker.FEATURES if item[0] == "F253")))
    prior = json.loads((root / "feature_test_results.json").read_text(encoding="utf-8")).get("F253", {})
    valid, _ = verify_acceptance(root, row, prior)
    if valid:
        _behaviour_evidence["F253"] = prior["behaviour_acceptance_evidence"]
        return DETAIL + "; reused current bound execution"
    output = root / "tmp" / "feature-acceptance" / f"F253-{uuid.uuid4().hex}.json"
    _behaviour_evidence["F253"] = run_acceptance(output, row)
    return DETAIL


def _practice_bank_acceptance(feature):
    import uuid

    import build_feature_tracker as tracker
    from tools.accept_practice_bank import DETAILS, run_acceptance
    from tools.feature_acceptance import verify_acceptance

    root = Path(__file__).resolve().parent
    row = dict(zip(tracker.HEADERS, next(item for item in tracker.FEATURES if item[0] == feature)))
    prior = json.loads((root / "feature_test_results.json").read_text(encoding="utf-8")).get(feature, {})
    valid, _detail = verify_acceptance(root, row, prior)
    if valid:
        _behaviour_evidence[feature] = prior["behaviour_acceptance_evidence"]
        return DETAILS[feature] + "; reused current bound execution"
    output = root / "tmp/feature-acceptance" / f"{feature}-{uuid.uuid4().hex}.json"
    _behaviour_evidence[feature] = run_acceptance(output, row)
    return DETAILS[feature]


def t_f254():
    return _practice_bank_acceptance("F254")


def t_f255():
    import subprocess

    result = subprocess.run([sys.executable, "-m", "pytest", "tests/test_gui_instance_guard.py", "-q",
        "-k", "not spider_environment_flag_does_not_open_or_crawl_on_startup and not spider_dock_still_opens_only_after_navigation_action",
        "-p", "no:cacheprovider", f"--basetemp={_TMP / 'gui-instance-cases'}"],
        cwd=Path(__file__).resolve().parent, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=90, env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert result.returncode == 0, (result.stdout + result.stderr)[-3500:]
    assert "17 passed" in result.stdout, result.stdout
    return "17 executed single-profile launch checks: real lock/CLI duplicate, Unicode paths, corrupt-lock/storage diagnosis, release race, owner exit/crash recovery and exception release; no visible window; installed Qt required"


def t_f256():
    import subprocess

    result = subprocess.run([sys.executable, "-m", "pytest", "tests/test_unt_scene_policy.py", "-q",
        "-p", "no:cacheprovider", f"--basetemp={_TMP / 'unt-policy-cases'}"],
        cwd=Path(__file__).resolve().parent, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=90, env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert result.returncode == 0, (result.stdout + result.stderr)[-3500:]
    assert "21 passed" in result.stdout, result.stdout
    return "21 executed UNT policy checks: five-act/eight-beat scheduling, source-neutral scaffold and controlled real directing request, honest provenance, numeric/choice gates, chapter/portrait policy and duration boundaries; no model/cloud/video acceptance"


def _spider_story_checks(expression: str, count: int) -> str:
    import subprocess
    from aetherlab.core.proc import subprocess_kwargs
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/test_spider_contract.py", "-q",
        "-k", expression, "-p", "no:cacheprovider", f"--basetemp={_TMP / ('spider-' + str(count))}"],
        cwd=Path(__file__).resolve().parent, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=90, env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}, **subprocess_kwargs())
    assert result.returncode == 0, (result.stdout + result.stderr)[-3500:]
    assert f"{count} passed" in result.stdout, result.stdout
    return f"{count} owned Spider contract cases; fake providers/PNG, temporary sources/Git, no real screenshot/network/native UI; full behaviour remains partial"


def _spider_startup_opt_in_check() -> str:
    import subprocess
    from aetherlab.core.proc import subprocess_kwargs
    result = subprocess.run(
        [sys.executable, "-m", "pytest",
         "tests/test_gui_instance_guard.py", "-k",
         "spider_environment_flag_does_not_open_or_crawl_on_startup or spider_dock_still_opens_only_after_navigation_action",
         "-q", "-p", "no:cacheprovider",
         f"--basetemp={_TMP / 'spider-startup-opt-in'}"],
        cwd=Path(__file__).resolve().parent, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=90,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "AETHERLAB_SPIDER_CRAWL": "1"},
        **subprocess_kwargs(),
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-3500:]
    assert "2 passed" in result.stdout, result.stdout
    return "legacy Spider startup flag ignored; sidebar action still opens/closes the dock without starting a crawl; offscreen Qt only"


def t_f257():
    return _spider_story_checks("actual_async or invalid_diagnosis or different_vision", 8)


def t_f258():
    return _spider_story_checks("every_patch_section or valid_patch or unsafe_extra", 6)


def t_f259():
    feedback = _spider_story_checks("cancelled_scan or cancel_after or unrepaired_error", 5)
    startup = _spider_startup_opt_in_check()
    return f"{feedback}; {startup}"


def t_f260():
    return _spider_story_checks("test_crawl", 2)


TESTS = {name[2:].upper(): fn for name, fn in sorted(globals().items())
         if name.startswith("t_f") and callable(globals()[name])}


def failure_exit_code(results_map: dict[str, dict]) -> int:
    """Return the process exit code for a finished run (BUG-60).

    The harness used to `return 0` unconditionally, so the CI step that runs it
    could never fail on a feature regression — the whole 'NNN/NNN green' claim
    was unenforced. Kept as a pure function so t_f215 can assert both branches
    without running the suite.
    """
    return 1 if any(r.get("status") == "FAIL" for r in results_map.values()) else 0


def main() -> int:
    from aetherlab.core.console import configure_utf8_stdio

    configure_utf8_stdio()
    print("=" * 72)
    print(f"AETHERLAB FEATURE TESTS  ({len(TESTS)} features)  tmp={_TMP}")
    print("=" * 72)
    for fid in sorted(TESTS, key=lambda x: int(x[1:])):
        check(fid, TESTS[fid])

    prior_path = Path("feature_test_results.json")
    try:
        prior = json.loads(prior_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        prior = {}
    phase = os.environ.get("AETHERLAB_AUDIT_PHASE", "baseline")
    for fid, result in results.items():
        if int(fid[1:]) >= 232:
            result["phase2_status"] = prior.get(fid, {}).get("phase2_status", result["status"])
            result["phase4_status"] = result["status"] if phase == "post_fix" else "PENDING"

    passed = sum(1 for r in results.values() if r["status"] == "PASS")
    failed = [f for f, r in results.items() if r["status"] == "FAIL"]
    print("\n" + "=" * 72)
    print(f"RESULT: {passed}/{len(results)} passed; {len(failed)} failed")
    if failed:
        print("FAILURES: " + ", ".join(sorted(failed, key=lambda x: int(x[1:]))))
    Path("feature_test_results.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8", newline="\n"
    )
    print("Wrote feature_test_results.json")
    return failure_exit_code(results)


if __name__ == "__main__":
    raise SystemExit(main())
