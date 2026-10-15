"""Execute the watchdog loop and its user-visible recovery paths."""
import importlib.util
import logging
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(tmp_path):
    spec = importlib.util.spec_from_file_location("watchdog_case_" + uuid.uuid4().hex, ROOT / "aetherlab_watchdog.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.LOG_DIR = tmp_path / "logs"
    module.LOG_FILE = module.LOG_DIR / "watchdog.log"
    return module


def _processes(monkeypatch, module, outcomes):
    calls, sleeps = [], []
    values = iter(outcomes)

    def run(command, **kwargs):
        calls.append((command, kwargs))
        item = next(values)
        if isinstance(item, BaseException):
            raise item
        return subprocess.CompletedProcess(command, item)

    monkeypatch.setattr(module.subprocess, "run", run)
    monkeypatch.setattr(module.time, "sleep", sleeps.append)
    return calls, sleeps


def _messages(monkeypatch, module):
    messages = []
    def record(message, *args):
        messages.append(message % args if args else message)
    monkeypatch.setattr(module.logger, "info", record)
    monkeypatch.setattr(module.logger, "error", record)
    return messages


def test_unwritable_log_directory_does_not_prevent_clean_launch(monkeypatch, tmp_path):
    original = Path.mkdir

    def refuse(path, *args, **kwargs):
        if path.name == "logs":
            raise PermissionError("owned logging refusal")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", refuse)
    module = _load(tmp_path)
    calls, sleeps = _processes(monkeypatch, module, [0])
    module.main()
    assert len(calls) == 1 and sleeps == []


def test_log_file_refusal_does_not_prevent_recovery(monkeypatch, tmp_path):
    def refuse(*args, **kwargs):
        raise PermissionError("owned file logging refusal")

    monkeypatch.setattr(logging, "FileHandler", refuse)
    module = _load(tmp_path)
    calls, sleeps = _processes(monkeypatch, module, [1, 0])
    module.main()
    assert len(calls) == 2 and sleeps == [3]


def test_clean_exit_stops_and_launch_uses_the_expected_command(monkeypatch, tmp_path):
    module = _load(tmp_path)
    calls, sleeps = _processes(monkeypatch, module, [0])
    module.main()
    assert calls == [([sys.executable, "-m", "aetherlab"], {"cwd": str(ROOT)})]
    assert sleeps == []


def test_repeated_crashes_back_off_and_cap_at_sixty_seconds(monkeypatch, tmp_path):
    module = _load(tmp_path)
    calls, sleeps = _processes(monkeypatch, module, [1] * 7 + [0])
    monkeypatch.setattr(module.time, "monotonic", lambda: 0)
    module.main()
    assert len(calls) == 8
    assert sleeps == [3, 6, 12, 24, 48, 60, 60]


def test_healthy_uptime_resets_backoff_at_the_boundary(monkeypatch, tmp_path):
    module = _load(tmp_path)
    calls, sleeps = _processes(monkeypatch, module, [1, 1, 1, 1, 0])
    clock = iter([0, 1, 2, 3, 4, 124, 125, 126, 127, 128])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(clock))
    messages = _messages(monkeypatch, module)
    module.main()
    assert len(calls) == 5 and sleeps == [3, 6, 3, 6]
    assert any("uptime 120s" in message for message in messages)
    assert any("backoff reset" in message for message in messages)


def test_child_start_failure_is_logged_and_retried(monkeypatch, tmp_path):
    module = _load(tmp_path)
    calls, sleeps = _processes(monkeypatch, module, [FileNotFoundError("owned missing child"), 0])
    messages = _messages(monkeypatch, module)
    module.main()
    assert len(calls) == 2 and sleeps == [3]
    assert any("Failed to start AetherLab" in message for message in messages)
    assert any("code -1" in message for message in messages)


def test_interrupt_while_child_runs_stops_without_relaunch(monkeypatch, tmp_path):
    module = _load(tmp_path)
    calls, sleeps = _processes(monkeypatch, module, [KeyboardInterrupt()])
    module.main()
    assert len(calls) == 1 and sleeps == []


def test_interrupt_during_backoff_stops_without_traceback(monkeypatch, tmp_path):
    module = _load(tmp_path)
    calls, _ = _processes(monkeypatch, module, [1])

    def interrupt(delay):
        raise KeyboardInterrupt()

    monkeypatch.setattr(module.time, "sleep", interrupt)
    try:
        module.main()
    except KeyboardInterrupt:
        raise AssertionError("Ctrl+C during backoff escaped the watchdog instead of stopping cleanly") from None
    assert len(calls) == 1


def test_actual_child_process_is_restarted_then_clean_exit_stops(tmp_path, monkeypatch):
    module = _load(tmp_path)
    owned = tmp_path / "child Ә with spaces"
    owned.mkdir()
    package = owned / "aetherlab"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "__main__.py").write_text(
        "from pathlib import Path\nimport sys\n"
        "p=Path('owned-child-count.txt')\n"
        "n=int(p.read_text()) if p.exists() else 0\n"
        "p.write_text(str(n+1))\n"
        "raise SystemExit(7 if n==0 else 0)\n", encoding="utf-8")
    monkeypatch.setattr(module, "SCRIPT_DIR", owned)
    sleeps = []
    monkeypatch.setattr(module.time, "sleep", sleeps.append)
    messages = _messages(monkeypatch, module)
    module.main()
    assert (owned / "owned-child-count.txt").read_text() == "2"
    assert sleeps == [3]
    assert any("code 7" in message for message in messages)
    assert any("code 0" in message for message in messages)


def test_actual_batch_launcher_restarts_child_from_foreign_cwd(tmp_path):
    if sys.platform != "win32":
        import pytest
        pytest.skip("The supplied batch entry point is Windows-specific")
    owned = tmp_path / "launcher Ә with spaces"
    owned.mkdir()
    (owned / "start.bat").write_bytes((ROOT / "start.bat").read_bytes())
    (owned / "aetherlab_watchdog.py").write_bytes((ROOT / "aetherlab_watchdog.py").read_bytes())
    package = owned / "aetherlab"
    core = package / "core"
    core.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (core / "__init__.py").write_text("", encoding="utf-8")
    (core / "console.py").write_bytes((ROOT / "aetherlab/core/console.py").read_bytes())
    (package / "__main__.py").write_text(
        "from pathlib import Path\n"
        "p=Path('owned-batch-count.txt')\n"
        "n=int(p.read_text()) if p.exists() else 0\n"
        "p.write_text(str(n+1))\n"
        "raise SystemExit(7 if n==0 else 0)\n", encoding="utf-8")
    result = subprocess.run(["cmd.exe", "/d", "/c", str(owned / "start.bat")],
        cwd=tmp_path, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert (owned / "owned-batch-count.txt").read_text() == "2"
    assert b"code 7" in result.stderr and b"code 0" in result.stderr
