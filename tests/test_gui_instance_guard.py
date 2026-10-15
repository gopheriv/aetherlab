"""Single-profile launch ownership, using real locks without visible windows."""
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from aetherlab.core.proc import subprocess_kwargs
from aetherlab.ui import app as launcher
from aetherlab.ui.qt_compat import QtCore

ROOT = Path(__file__).resolve().parents[1]


def test_same_profile_refuses_a_second_lock_and_releases_on_close(tmp_path):
    first = launcher._acquire_gui_lock(tmp_path / "данные Қазақ")
    assert first is not None
    try:
        assert launcher._acquire_gui_lock(tmp_path / "данные Қазақ") is None
    finally:
        first.unlock()
    second = launcher._acquire_gui_lock(tmp_path / "данные Қазақ")
    assert second is not None
    second.unlock()


def test_independent_profiles_can_run_separately(tmp_path):
    first = launcher._acquire_gui_lock(tmp_path / "one")
    second = launcher._acquire_gui_lock(tmp_path / "two")
    assert first is not None and second is not None
    first.unlock()
    second.unlock()


@pytest.mark.parametrize("payload", [b"", b"owned malformed lock"])
def test_corrupt_lock_is_diagnosed_and_preserved(tmp_path, payload):
    path = tmp_path / "physlab-gui.lock"
    path.write_bytes(payload)
    with pytest.raises(RuntimeError, match="PhysLab.*launch lock") as caught:
        launcher._acquire_gui_lock(tmp_path)
    assert str(path) in str(caught.value)
    assert path.read_bytes() == payload


def test_owner_release_during_lock_inspection_retries_once(monkeypatch, tmp_path):
    lock_errors = QtCore.QLockFile.LockError
    class ReleasedLock:
        LockError = lock_errors
        def __init__(self, path):
            self.calls = 0
        def setStaleLockTime(self, value):
            assert value == 0
        def tryLock(self, timeout):
            assert timeout == 0
            self.calls += 1
            return self.calls == 2
        def error(self):
            return self.LockError.LockFailedError
        def getLockInfo(self):
            return False, 0, "", ""
    monkeypatch.setattr(QtCore, "QLockFile", ReleasedLock)
    owner = launcher._acquire_gui_lock(tmp_path)
    assert isinstance(owner, ReleasedLock) and owner.calls == 2


def test_unwritable_profile_is_an_actionable_error(monkeypatch, tmp_path):
    def refuse(*args, **kwargs):
        raise PermissionError("owned profile refusal")
    monkeypatch.setattr(Path, "mkdir", refuse)
    with pytest.raises(RuntimeError, match="PhysLab.*folder") as caught:
        launcher._acquire_gui_lock(tmp_path / "refused")
    assert isinstance(caught.value.__cause__, PermissionError)


@pytest.mark.parametrize("error", [QtCore.QLockFile.LockError.PermissionError,
                                   QtCore.QLockFile.LockError.UnknownError])
def test_lock_storage_errors_are_not_misreported_as_running(monkeypatch, tmp_path, error):
    lock_errors = QtCore.QLockFile.LockError
    class FailedLock:
        LockError = lock_errors
        def __init__(self, path):
            self.path = path
        def setStaleLockTime(self, value):
            assert value == 0
        def tryLock(self, timeout):
            assert timeout == 0
            return False
        def error(self):
            return error
    monkeypatch.setattr(QtCore, "QLockFile", FailedLock)
    with pytest.raises(RuntimeError, match="PhysLab.*lock"):
        launcher._acquire_gui_lock(tmp_path)


def test_duplicate_launch_exits_cleanly_before_window_construction(monkeypatch, tmp_path):
    owner = launcher._acquire_gui_lock(tmp_path)
    assert owner is not None
    monkeypatch.setattr(launcher, "load_settings", lambda: SimpleNamespace(data_dir=tmp_path))
    def forbidden(*args, **kwargs):
        raise AssertionError("Duplicate launch must not construct QApplication or a window")
    monkeypatch.setattr(launcher.QtWidgets, "QApplication", forbidden)
    try:
        assert launcher.run_app([]) == 0
    finally:
        owner.unlock()


def test_real_module_duplicate_exits_without_importing_main_window(tmp_path):
    owner = launcher._acquire_gui_lock(tmp_path)
    assert owner is not None
    script = """import importlib.abc,runpy,sys
class NoWindow(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname=='aetherlab.ui.main_window':
            raise AssertionError('Duplicate launch imported the main window')
sys.meta_path.insert(0,NoWindow())
sys.argv=['aetherlab']
runpy.run_module('aetherlab',run_name='__main__')
"""
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("AETHERLAB_", "OPENAI_", "QWEN_", "DASHSCOPE_"))}
    env.update(AETHERLAB_DATA_DIR=str(tmp_path), AETHERLAB_DISABLE_LEGACY_ENV="1",
               AETHERLAB_QWEN_AUTOLOAD="0", QT_QPA_PLATFORM="offscreen")
    try:
        result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env,
            capture_output=True, text=True, timeout=30, **subprocess_kwargs())
        assert result.returncode == 0, result.stdout + result.stderr
        assert owner.isLocked()
        assert "already running" in (tmp_path / "logs/aetherlab.log").read_text(encoding="utf-8")
    finally:
        owner.unlock()


def test_entrypoint_reports_profile_lock_error_without_traceback(monkeypatch, capsys):
    import aetherlab.__main__ as entry

    monkeypatch.setattr(entry, "_setup_logging", lambda: None)
    def refuse():
        raise RuntimeError("PhysLab cannot create its launch lock in: owned profile")
    monkeypatch.setattr(launcher, "run_app", refuse)
    assert entry.main([]) == 2
    assert "cannot create its launch lock" in capsys.readouterr().err


@pytest.mark.parametrize("failure", ["none", "construct", "show", "event-loop"])
def test_launch_releases_lock_after_exit_or_initialization_failure(monkeypatch, tmp_path, failure):
    import aetherlab.ui.main_window as main_window

    monkeypatch.setattr(launcher, "load_settings", lambda: SimpleNamespace(data_dir=tmp_path))
    monkeypatch.setattr(launcher, "_icon_path", lambda: None)
    events = []
    class Application:
        def __init__(self, argv):
            assert argv == ["owned"]
        def setApplicationName(self, name):
            assert name == "PhysLab"
        def setApplicationDisplayName(self, name):
            assert name == "PhysLab"
        def exec(self):
            events.append("exec")
            assert launcher._acquire_gui_lock(tmp_path) is None
            if failure == "event-loop":
                raise RuntimeError("owned event-loop failure")
            return 17
    class Window:
        def __init__(self, settings):
            events.append("construct")
            assert settings.data_dir == tmp_path
            assert launcher._acquire_gui_lock(tmp_path) is None
            if failure == "construct":
                raise RuntimeError("owned construction failure")
        def show(self):
            events.append("show")
            if failure == "show":
                raise RuntimeError("owned show failure")
    monkeypatch.setattr(launcher.QtWidgets, "QApplication", Application)
    monkeypatch.setattr(main_window, "MainWindow", Window)
    if failure == "none":
        assert launcher.run_app(["owned"]) == 17
        assert events == ["construct", "show", "exec"]
    else:
        with pytest.raises(RuntimeError, match="owned"):
            launcher.run_app(["owned"])
    recovered = launcher._acquire_gui_lock(tmp_path)
    assert recovered is not None
    recovered.unlock()


def test_spider_environment_flag_does_not_open_or_crawl_on_startup(monkeypatch, tmp_path):
    import aetherlab.ui.main_window as main_window
    from aetherlab.ui import qt_compat

    events = []

    class ImmediateTimer:
        @staticmethod
        def singleShot(delay, callback):
            events.append(("timer", delay))
            callback()

    class Application:
        def __init__(self, argv):
            assert argv == ["owned"]
        def setApplicationName(self, name):
            assert name == "PhysLab"
        def setApplicationDisplayName(self, name):
            assert name == "PhysLab"
        def exec(self):
            events.append("exec")
            return 0

    class Window:
        def __init__(self, settings):
            assert settings.data_dir == tmp_path
            events.append("construct")
        def show(self):
            events.append("show")
        def open_spider(self, *, crawl=False):
            events.append(("open_spider", crawl))

    monkeypatch.setattr(launcher, "_icon_path", lambda: None)
    monkeypatch.setattr(launcher.QtWidgets, "QApplication", Application)
    monkeypatch.setattr(qt_compat.QtCore, "QTimer", ImmediateTimer)
    monkeypatch.setattr(main_window, "MainWindow", Window)
    monkeypatch.setenv("AETHERLAB_SPIDER_CRAWL", "1")

    assert launcher._run_owned_app(SimpleNamespace(data_dir=tmp_path), ["owned"]) == 0
    assert events == ["construct", "show", "exec"]


def test_spider_dock_still_opens_only_after_navigation_action(tmp_path):
    from aetherlab.core.settings import AppSettings
    from aetherlab.ui.main_window import MainWindow

    app = launcher.QtWidgets.QApplication.instance() or launcher.QtWidgets.QApplication([])
    settings = AppSettings(
        data_dir=tmp_path,
        cache_path=tmp_path / "cache.sqlite3",
        chroma_path=tmp_path / "chroma",
        library_path=tmp_path / "library",
        openai_api_key=None,
        openai_base_url=None,
        llm_model="owned-test-model",
    )
    window = MainWindow(settings=settings)
    try:
        window.show()
        app.processEvents()
        assert window.spider_dock.isHidden()

        window.sidebar._buttons[8].click()
        app.processEvents()
        assert not window.spider_dock.isHidden()
        assert window.spider_panel._task is None

        window.sidebar._buttons[8].click()
        app.processEvents()
        assert window.spider_dock.isHidden()
    finally:
        window.close()
        app.processEvents()


@pytest.mark.parametrize("crash", [False, True])
def test_actual_process_ownership_and_recovery(tmp_path, crash):
    child = """import os,sys
from pathlib import Path
from aetherlab.ui.app import _acquire_gui_lock
owner=_acquire_gui_lock(Path(sys.argv[1]))
assert owner is not None
print('locked',flush=True)
sys.stdin.readline()
if sys.argv[2]=='crash': os._exit(7)
owner.unlock()
"""
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    process = subprocess.Popen([sys.executable, "-c", child, str(tmp_path), "crash" if crash else "close"],
        cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, **subprocess_kwargs())
    try:
        assert process.stdout.readline().strip() == "locked"
        assert launcher._acquire_gui_lock(tmp_path) is None
        stdout, stderr = process.communicate("finish\n", timeout=20)
        assert process.returncode == (7 if crash else 0), stdout + stderr
        recovered = launcher._acquire_gui_lock(tmp_path)
        assert recovered is not None
        recovered.unlock()
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=20)
