"""Real config persistence, storage refusals, restart and crash boundaries."""
import ctypes
import json
import os
import stat
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from aetherlab.core import atomic_json, settings
from aetherlab.core.proc import subprocess_kwargs

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def profile(tmp_path, monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(("AETHERLAB_", "OPENAI_", "QWEN_", "DASHSCOPE_", "MANIM_", "GPT_", "CHAT_", "LLM_")):
            monkeypatch.delenv(name, raising=False)
    data = tmp_path / "данные Қазақ"
    monkeypatch.setenv("AETHERLAB_DATA_DIR", str(data))
    monkeypatch.setenv("AETHERLAB_DISABLE_LEGACY_ENV", "1")
    monkeypatch.setenv("AETHERLAB_QWEN_AUTOLOAD", "0")
    monkeypatch.setenv("AETHERLAB_REFERENCE_SOURCES", str(tmp_path / "no-refs"))
    return data


def seed(data, payload=None):
    data.mkdir(parents=True, exist_ok=True)
    path = data / "settings.json"
    path.write_text(json.dumps(payload or {"keep": "қазақша"}, ensure_ascii=False), encoding="utf-8")
    return path


def test_missing_profile_read_creates_no_files(profile):
    assert settings.app_config_path() == profile / "settings.json"
    assert settings.load_app_config() == {}
    assert settings.load_settings().data_dir == profile
    assert not profile.exists()


@pytest.mark.parametrize("payload", [b"{", b"\xff\xfe", b"[]", b"null", b"4", b"true", b'"text"'],
                         ids=["json", "utf8", "list", "null", "number", "boolean", "string"])
def test_corrupt_config_is_read_without_rewriting(profile, payload):
    path = seed(profile)
    path.write_bytes(payload)
    assert settings.load_app_config() == {}
    assert settings.load_settings().data_dir == profile
    assert path.read_bytes() == payload


def test_scalar_filter_preserves_zero_false_and_unicode(profile):
    seed(profile, {"zero": 0, "false": False, "name": "Қазақша", "empty": "  ",
                   "null": None, "list": [1], "object": {"x": 1}})
    assert settings.load_app_config() == {"zero": "0", "false": "False", "name": "Қазақша"}


def test_save_merges_trims_and_removes_only_requested_empty_fields(profile):
    seed(profile, {"keep": "unchanged", "remove": "old", "blank": "old", "model": "old"})
    result = settings.save_app_config({"model": "  сақталған  ", "remove": None, "blank": " \t",
                                       "zero": "0", "false": "false"})
    assert result == profile / "settings.json"
    assert settings.load_app_config() == {"keep": "unchanged", "model": "сақталған", "zero": "0", "false": "false"}
    assert not list(profile.glob(".settings.json.*.tmp"))


def test_saved_data_and_library_paths_flow_into_settings_without_config_recursion(tmp_path, monkeypatch, profile):
    config_root = tmp_path / "profile"
    monkeypatch.delenv("AETHERLAB_DATA_DIR", raising=False)
    monkeypatch.delenv("AETHERLAB_LIBRARY_DIR", raising=False)
    monkeypatch.setattr(settings, "_default_data_dir", lambda: config_root)
    monkeypatch.setenv("AETHERLAB_DISABLE_LEGACY_ENV", "1")
    monkeypatch.setenv("AETHERLAB_QWEN_AUTOLOAD", "0")
    target, library = tmp_path / "saved data", tmp_path / "saved library"
    settings.save_app_config({"data_dir": str(target), "library_path": str(library), "model": "saved-model"})
    loaded = settings.load_settings()
    assert loaded.data_dir == target and loaded.library_path == library
    assert loaded.cache_path == target / "cache.sqlite3" and loaded.llm_model == "saved-model"
    assert settings.app_config_path() == config_root / "settings.json"
    assert not (target / "settings.json").exists()


def test_read_refusal_uses_startup_defaults_but_cannot_be_overwritten(profile, monkeypatch):
    path = seed(profile)
    before = path.read_bytes()
    original = Path.read_text
    def refuse(target, *args, **kwargs):
        if target == path:
            raise PermissionError("owned config read refusal")
        return original(target, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", refuse)
    assert settings.load_app_config() == {}
    assert settings.load_settings().data_dir == profile
    with pytest.raises(PermissionError):
        settings.save_app_config({"new": "value"})
    assert path.read_bytes() == before


@pytest.mark.parametrize("stage", ["create", "encode", "fsync", "replace"])
def test_write_failure_preserves_committed_bytes_and_cleans_stage(profile, monkeypatch, stage):
    path = seed(profile)
    before = path.read_bytes()
    def refuse(*args, **kwargs):
        if stage == "encode":
            args[1].write('{"partial":')
        raise OSError("owned write refusal")
    target, name = {
        "create": (atomic_json.tempfile, "mkstemp"), "encode": (atomic_json.json, "dump"),
        "fsync": (atomic_json.os, "fsync"), "replace": (atomic_json.os, "replace"),
    }[stage]
    monkeypatch.setattr(target, name, refuse)
    with pytest.raises(OSError):
        settings.save_app_config({"new": "value"})
    assert path.read_bytes() == before
    assert not list(profile.glob(".settings.json.*.tmp"))


@pytest.mark.parametrize("permanent", [False, True], ids=["transient", "permanent"])
def test_windows_sharing_refusal_retries_without_deleting_target(profile, monkeypatch, permanent):
    path = seed(profile)
    before = path.read_bytes()
    original = atomic_json.os.replace
    attempts, waits = [], []
    def replace(source, target):
        attempts.append(1)
        assert path.read_bytes() == before
        if permanent or len(attempts) < 3:
            error = PermissionError("owned Windows sharing refusal")
            error.winerror = 32
            raise error
        return original(source, target)
    monkeypatch.setattr(atomic_json.os, "replace", replace)
    monkeypatch.setattr(atomic_json.time, "sleep", waits.append)
    if permanent:
        with pytest.raises(PermissionError):
            settings.save_app_config({"new": "value"})
        assert len(attempts) == 5 and path.read_bytes() == before
    else:
        assert settings.save_app_config({"new": "value"}) == path
        assert len(attempts) == 3 and settings.load_app_config()["new"] == "value"
    assert waits == [0.025 * 2 ** index for index in range(len(attempts) - 1)]
    assert not list(profile.glob(".settings.json.*.tmp"))


@pytest.mark.skipif(sys.platform != "win32", reason="Real Windows read-only attribute")
def test_real_read_only_config_refuses_then_retries(profile):
    path = seed(profile)
    before = path.read_bytes()
    try:
        path.chmod(stat.S_IREAD)
        with pytest.raises(PermissionError):
            settings.save_app_config({"new": "value"})
        assert path.read_bytes() == before
    finally:
        path.chmod(stat.S_IREAD | stat.S_IWRITE)
    settings.save_app_config({"new": "value"})
    assert settings.load_app_config() == {"keep": "қазақша", "new": "value"}


@pytest.mark.skipif(sys.platform != "win32", reason="Real Windows file-share handle")
def test_real_shared_read_handle_recovers_after_owner_releases_it(profile, monkeypatch):
    path = seed(profile)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p,
                                  ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.CloseHandle.restype = ctypes.c_int
    handle = kernel.CreateFileW(str(path), 0x80000000, 1, None, 3, 0x80, None)
    assert handle not in (None, ctypes.c_void_p(-1).value)
    refused = threading.Event()
    original = atomic_json.os.replace
    def observed(source, target):
        try:
            return original(source, target)
        except PermissionError as exc:
            assert exc.winerror in {5, 32, 33}
            refused.set()
            raise
    monkeypatch.setattr(atomic_json.os, "replace", observed)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(settings.save_app_config, {"new": "value"})
            try:
                assert refused.wait(5), "The owned handle did not produce a sharing refusal"
            finally:
                assert kernel.CloseHandle(handle)
                handle = None
            assert pending.result(timeout=5) == path
    finally:
        if handle is not None:
            kernel.CloseHandle(handle)
    assert settings.load_app_config() == {"keep": "қазақша", "new": "value"}


def test_concurrent_writers_keep_every_field(profile):
    seed(profile)
    barrier = threading.Barrier(8)
    def save(index):
        barrier.wait(timeout=10)
        settings.save_app_config({f"field_{index}": str(index)})
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(save, range(8)))
    result = settings.load_app_config()
    assert result == {"keep": "қазақша", **{f"field_{index}": str(index) for index in range(8)}}
    assert not list(profile.glob(".settings.json.*.tmp"))


def test_real_restart_from_a_foreign_directory_reads_saved_values(profile, tmp_path):
    library = tmp_path / "кітаптар"
    path = settings.save_app_config({"model": "saved-model", "api_key": "owned-unused-key", "library_path": str(library)})
    before = path.read_bytes()
    foreign = tmp_path / "foreign directory"
    foreign.mkdir()
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join((str(ROOT), environment.get("PYTHONPATH", "")))
    code = "from aetherlab.core.settings import load_settings; import sys; s=load_settings(); assert s.llm_model=='saved-model'; assert s.openai_api_key=='owned-unused-key'; assert str(s.library_path)==sys.argv[1]; print('OK')"
    result = subprocess.run([sys.executable, "-c", code, str(library)], cwd=foreign, env=environment,
        capture_output=True, text=True, timeout=20, **subprocess_kwargs())
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK" and path.read_bytes() == before


def test_real_process_crash_cannot_publish_a_partial_configuration(profile):
    path = seed(profile)
    before = path.read_bytes()
    code = '''import os
from aetherlab.core import atomic_json
from aetherlab.core.settings import save_app_config
def crash(payload, stream, **kwargs):
    stream.write('{"partial":')
    stream.flush()
    os.fsync(stream.fileno())
    os._exit(7)
atomic_json.json.dump=crash
save_app_config({'new':'value'})
'''
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True,
        text=True, timeout=20, **subprocess_kwargs())
    assert result.returncode == 7
    assert path.read_bytes() == before and settings.load_app_config() == {"keep": "қазақша"}
    abandoned = list(profile.glob(".settings.json.*.tmp"))
    assert len(abandoned) == 1 and abandoned[0].read_text(encoding="utf-8") == '{"partial":'
    settings.save_app_config({"new": "value"})
    assert settings.load_app_config() == {"keep": "қазақша", "new": "value"}
