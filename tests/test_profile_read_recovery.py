"""Read failures must not masquerade as an empty learner registry."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aetherlab.services.student_profiles import StudentProfileStore
from aetherlab.ui.profile_dialog import _COPY, StudentProfileDialog
from aetherlab.ui.qt_compat import QtWidgets

_APP = None


def _app():
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


def _store(root: Path):
    store = StudentProfileStore(root)
    second = store.create_profile("Second Learner")
    store.set_active_profile(second.id)
    return store, second


def _refuse_reads(monkeypatch, registry: Path):
    original = Path.read_text

    def read(path, *args, **kwargs):
        if path == registry:
            raise PermissionError("registry temporarily unreadable")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)


def test_unreadable_existing_registry_is_not_reset_on_open(tmp_path, monkeypatch) -> None:
    store, second = _store(tmp_path)
    before = store.registry_path.read_bytes()
    with monkeypatch.context() as patch:
        _refuse_reads(patch, store.registry_path)
        with pytest.raises(PermissionError):
            StudentProfileStore(tmp_path)
    assert store.registry_path.read_bytes() == before
    assert store.active_profile().id == second.id


def test_unreadable_registry_cannot_be_overwritten_by_create_or_activation(tmp_path, monkeypatch) -> None:
    for operation in ("create", "activate", "active"):
        store, second = _store(tmp_path / operation)
        before = store.registry_path.read_bytes()
        with monkeypatch.context() as patch:
            _refuse_reads(patch, store.registry_path)
            with pytest.raises(PermissionError):
                if operation == "create":
                    store.create_profile("New Learner")
                elif operation == "activate":
                    store.set_active_profile("default")
                else:
                    store.active_profile()
        assert store.registry_path.read_bytes() == before
        assert store.active_profile().id == second.id


def test_profile_refresh_failure_preserves_choices_and_retries(tmp_path, monkeypatch) -> None:
    _app()
    store, second = _store(tmp_path)
    dialog = StudentProfileDialog(store, "ru")
    choices = [dialog.profile_combo.itemData(i) for i in range(dialog.profile_combo.count())]
    original = store.list_profiles

    def refused():
        raise PermissionError("registry temporarily unreadable")

    with monkeypatch.context() as patch:
        patch.setattr(store, "list_profiles", refused)
        assert not dialog._refresh_profiles()
    assert [dialog.profile_combo.itemData(i) for i in range(dialog.profile_combo.count())] == choices
    assert not dialog.profile_combo.signalsBlocked()
    assert dialog.message.text() == _COPY["ru"]["load_error"]
    assert not dialog.use_button.isEnabled()
    dialog.retry_button.click()
    assert dialog.profile_combo.currentData() == second.id
    assert not dialog.message.text()
    assert dialog.use_button.isEnabled()
    assert store.list_profiles() == original()
    dialog.close()


def test_profile_selection_failure_cannot_edit_wrong_learner(tmp_path, monkeypatch) -> None:
    _app()
    store, _second = _store(tmp_path)
    dialog = StudentProfileDialog(store, "ru")
    # Block the Qt signal so the original unhandled slot cannot abort the runner.
    dialog.profile_combo.blockSignals(True)
    dialog.profile_combo.setCurrentIndex(dialog.profile_combo.findData("default"))
    dialog.profile_combo.blockSignals(False)

    def refused(_profile_id):
        raise PermissionError("registry temporarily unreadable")

    with monkeypatch.context() as patch:
        patch.setattr(store, "get_profile", refused)
        assert not dialog._load_selected_profile()
    assert not dialog.edit_button.isEnabled() and not dialog.use_button.isEnabled()
    dialog.retry_button.click()
    assert dialog.profile_combo.currentData() == "default"
    assert dialog._current_profile.id == "default"
    assert dialog.edit_button.isEnabled() and dialog.use_button.isEnabled()
    dialog.close()


def test_discard_read_failure_retains_draft_until_retry(tmp_path, monkeypatch) -> None:
    _app()
    store, second = _store(tmp_path)
    dialog = StudentProfileDialog(store, "ru")
    dialog._begin_edit()
    dialog.first_name_edit.setText("Unsaved draft")
    before = store.registry_path.read_bytes()

    def refused(_profile_id):
        raise PermissionError("registry temporarily unreadable")

    with monkeypatch.context() as patch:
        patch.setattr(store, "get_profile", refused)
        dialog._discard_edit()
    assert dialog.first_name_edit.text() == "Unsaved draft"
    assert not dialog.first_name_edit.isReadOnly()
    dialog.retry_button.click()
    assert dialog.first_name_edit.isReadOnly()
    assert dialog._current_profile.id == second.id
    assert store.registry_path.read_bytes() == before
    dialog.close()


def test_saved_profile_reports_refresh_failure_without_partial_creation(tmp_path, monkeypatch) -> None:
    _app()
    store = StudentProfileStore(tmp_path)
    dialog = StudentProfileDialog(store, "ru")
    dialog._begin_new_profile()
    dialog.first_name_edit.setText("Saved")
    dialog.last_name_edit.setText("Learner")
    dialog.username_edit.setText("saved.learner")

    def refused():
        raise PermissionError("registry temporarily unreadable")

    with monkeypatch.context() as patch:
        patch.setattr(store, "list_profiles", refused)
        dialog._save_profile()
    assert dialog.message.text() == _COPY["ru"]["saved_reload_error"]
    assert not dialog._new_profile and dialog.first_name_edit.isReadOnly()
    assert len(store.list_profiles()) == 2
    dialog.retry_button.click()
    assert dialog.profile_combo.currentData() == store.active_profile().id
    assert dialog._current_profile.name == "Saved Learner"
    assert not dialog.message.text()
    dialog.close()


def test_main_window_profile_read_failure_retains_current_views(tmp_path, monkeypatch) -> None:
    _app()
    from aetherlab.core.settings import load_settings
    from aetherlab.ui.main_window import MainWindow

    settings = replace(load_settings(), data_dir=tmp_path, cache_path=tmp_path / "cache.sqlite3", chroma_path=tmp_path / "chroma", library_path=tmp_path / "library", openai_api_key="test-key", reference_sources_path=None)
    window = MainWindow(settings)
    profile = window.active_student_profile

    def refused():
        raise PermissionError("registry temporarily unreadable")

    with monkeypatch.context() as patch:
        patch.setattr(window.student_profile_store, "active_profile", refused)
        window._manage_student_profiles()
    assert window.active_student_profile == profile
    assert window.student_dashboard.progress_path == profile.progress_path
    assert window.topic_catalog.progress_path == profile.progress_path
    assert window.title_bar.profile_button.name == profile.name
    assert window.statusBar().currentMessage() == _COPY[window.command_bar.get_language()]["load_error"]
    window.close()


def test_missing_and_malformed_registry_keep_legacy_progress_recovery(tmp_path) -> None:
    for case in ("missing", "malformed"):
        root = tmp_path / case
        root.mkdir()
        progress = root / "ent_practice_progress.json"
        original = b'{"attempts": [{"score": 42}], "goals": {"target_score": 45}}'
        progress.write_bytes(original)
        if case == "malformed":
            (root / "student_profiles.json").write_text('{"profiles":', encoding="utf-8")
        store = StudentProfileStore(root)
        assert store.active_profile().id == "default"
        assert store.active_profile().progress_path == progress
        assert progress.read_bytes() == original


def test_unreadable_dialog_initialization_retries_in_all_languages(tmp_path, monkeypatch) -> None:
    _app()
    for language in ("kk", "ru", "en"):
        store, second = _store(tmp_path / language)
        before = store.registry_path.read_bytes()
        with monkeypatch.context() as patch:
            _refuse_reads(patch, store.registry_path)
            dialog = StudentProfileDialog(store, language)
            assert dialog.message.text() == _COPY[language]["load_error"]
            assert dialog.retry_button.text() == _COPY[language]["retry"]
            assert not dialog.use_button.isEnabled()
        dialog.retry_button.click()
        assert dialog.profile_combo.currentData() == second.id
        assert dialog.use_button.isEnabled()
        assert not dialog.message.text()
        assert store.registry_path.read_bytes() == before
        dialog.close()
