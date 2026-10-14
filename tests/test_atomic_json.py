"""Persistence recovery must retain atomic replacement and surface real errors."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aetherlab.core import atomic_json
from aetherlab.services.student_profiles import StudentProfileStore


def _windows_lock(code: int = 32) -> PermissionError:
    error = PermissionError("temporarily locked by another Windows file handle")
    error.winerror = code
    return error


def test_profile_save_recovers_from_transient_windows_replace_lock(tmp_path: Path, monkeypatch) -> None:
    real_replace = atomic_json.os.replace
    for code in (5, 32, 33):
        root = tmp_path / str(code)
        store = StudentProfileStore(root, default_name="Student")
        calls = []

        def replace_with_lock(source, target):
            calls.append((source, target))
            if len(calls) == 1:
                raise _windows_lock(code)
            real_replace(source, target)

        with monkeypatch.context() as patch:
            patch.setattr(atomic_json.os, "replace", replace_with_lock)
            saved = store.update_profile("default", first_name="Student", last_name="One", username="student.one")
        assert saved.username == "student.one"
        assert len(calls) == 2
        assert calls[0] == calls[1], "Retry must replace the same durable staged document"
        assert StudentProfileStore(root).get_profile("default").username == "student.one"
        assert not list(root.glob(".student_profiles.json.*.tmp"))


def test_persistent_windows_lock_keeps_original_and_reports_failure(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "progress.json"
    atomic_json.atomic_write_json(path, {"score": 40})
    attempts = []

    def always_locked(*_args):
        attempts.append(True)
        raise _windows_lock()

    monkeypatch.setattr(atomic_json.os, "replace", always_locked)
    with pytest.raises(PermissionError):
        atomic_json.atomic_write_json(path, {"score": 45})
    assert 1 < len(attempts) <= 5, "Recovery must be bounded and must not pretend to save"
    assert json.loads(path.read_text(encoding="utf-8")) == {"score": 40}
    assert not list(tmp_path.glob(".progress.json.*.tmp"))


def test_other_permission_errors_are_not_retried(tmp_path: Path, monkeypatch) -> None:
    attempts = []

    def denied(*_args):
        attempts.append(True)
        raise PermissionError("permanent permission denied")

    monkeypatch.setattr(atomic_json.os, "replace", denied)
    with pytest.raises(PermissionError):
        atomic_json.atomic_write_json(tmp_path / "progress.json", {"score": 45})
    assert len(attempts) == 1
    assert not list(tmp_path.glob(".progress.json.*.tmp"))
