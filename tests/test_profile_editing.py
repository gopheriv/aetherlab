"""Profile form failure paths using real Qt images and isolated registries."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aetherlab.services.student_profiles import StudentProfileStore
from aetherlab.ui.profile_dialog import _COPY, StudentProfileDialog
from aetherlab.ui.qt_compat import QtGui, QtWidgets

_APP = None


def _app():
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


def _image(path: Path, color: str) -> Path:
    _app()
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap = QtGui.QPixmap(24, 24)
    pixmap.fill(QtGui.QColor(color))
    assert pixmap.save(str(path), "PNG")
    return path


def _editor(root: Path, language: str = "ru"):
    _app()
    store = StudentProfileStore(root, default_name="Student One")
    old = _image(root / "avatar.png", "red")
    profile = store.update_profile("default", first_name="Student", last_name="One", username="student.one", avatar_path=str(old))
    dialog = StudentProfileDialog(store, language)
    dialog._begin_edit()
    return store, profile, dialog


def test_rejected_identity_change_preserves_saved_avatar(tmp_path) -> None:
    store, profile, dialog = _editor(tmp_path)
    store.create_profile("Other Student", username="other.student")
    before = Path(profile.avatar_path).read_bytes()
    registry = store.registry_path.read_bytes()
    dialog.username_edit.setText("other.student")
    dialog._avatar_source = str(_image(tmp_path / "new.png", "blue"))
    dialog._save_profile()
    assert dialog.message.text() == _COPY["ru"]["duplicate_username"]
    assert store.registry_path.read_bytes() == registry
    assert Path(profile.avatar_path).read_bytes() == before
    dialog.close()


def test_registry_failure_preserves_avatar_and_editable_draft(tmp_path, monkeypatch) -> None:
    store, profile, dialog = _editor(tmp_path)
    before = Path(profile.avatar_path).read_bytes()
    registry = store.registry_path.read_bytes()
    source = _image(tmp_path / "new.png", "blue")
    dialog._avatar_source = str(source)
    dialog.first_name_edit.setText("Changed")

    def refused(_payload):
        raise OSError("registry unavailable")

    monkeypatch.setattr(store, "_write_registry", refused)
    dialog._save_profile()
    assert dialog.message.text() == _COPY["ru"]["save_error"]
    assert store.registry_path.read_bytes() == registry
    assert Path(profile.avatar_path).read_bytes() == before
    assert dialog.first_name_edit.text() == "Changed"
    assert not dialog.first_name_edit.isReadOnly()
    assert not list((tmp_path / "profile_avatars").glob("*.png"))
    dialog.close()


def test_new_profile_and_avatar_are_saved_with_one_registry_commit(tmp_path, monkeypatch) -> None:
    _app()
    store = StudentProfileStore(tmp_path)
    dialog = StudentProfileDialog(store, "ru")
    dialog._begin_new_profile()
    dialog.first_name_edit.setText("New")
    dialog.last_name_edit.setText("Student")
    dialog.username_edit.setText("new.student")
    dialog.school_id_edit.setText("School-77")
    source = _image(tmp_path / "source.png", "blue")
    dialog._avatar_source = str(source)
    real_write = store._write_registry
    commits = []

    def commit(payload):
        commits.append(True)
        if len(commits) > 1:
            raise OSError("a second independent commit is not atomic")
        real_write(payload)

    monkeypatch.setattr(store, "_write_registry", commit)
    dialog._save_profile()
    assert not dialog.message.text()
    assert len(commits) == 1
    reopened = StudentProfileStore(tmp_path).active_profile()
    assert reopened.name == "New Student"
    assert reopened.school_id == "School-77"
    assert reopened.avatar_path != str(source)
    source.unlink()
    assert not QtGui.QPixmap(reopened.avatar_path).isNull()
    dialog.close()


def test_avatar_save_failure_is_localized_and_does_not_save_external_path(tmp_path, monkeypatch) -> None:
    for language in ("kk", "ru", "en"):
        store, profile, dialog = _editor(tmp_path / language, language)
        registry = store.registry_path.read_bytes()
        source = _image(tmp_path / language / "new.png", "blue")
        dialog._avatar_source = str(source)
        with monkeypatch.context() as patch:
            patch.setattr(QtGui.QPixmap, "save", lambda *_args: False)
            dialog._save_profile()
        assert store.registry_path.read_bytes() == registry
        assert dialog.message.text() == _COPY[language]["photo_error"]
        assert store.get_profile(profile.id).avatar_path == profile.avatar_path
        assert not dialog.first_name_edit.isReadOnly()
        dialog.close()


def test_activation_failure_is_reported_without_accepting_dialog(tmp_path, monkeypatch) -> None:
    _app()
    store = StudentProfileStore(tmp_path)
    selected = store.create_profile("Second Learner")
    dialog = StudentProfileDialog(store, "ru")
    dialog.profile_combo.setCurrentIndex(dialog.profile_combo.findData(selected.id))

    def refused(_profile_id):
        raise OSError("registry unavailable")

    monkeypatch.setattr(store, "set_active_profile", refused)
    dialog._activate_selected()
    assert dialog.message.text() == _COPY["ru"]["save_error"]
    assert dialog.selected_profile is None
    assert store.active_profile().id == "default"
    assert dialog.result() != QtWidgets.QDialog.DialogCode.Accepted
    dialog.close()


def test_cancel_edits_and_new_profile_preserves_registry(tmp_path) -> None:
    store, profile, dialog = _editor(tmp_path)
    registry = store.registry_path.read_bytes()
    image_before = Path(profile.avatar_path).read_bytes()
    dialog.first_name_edit.setText("Discarded")
    dialog._avatar_source = str(_image(tmp_path / "new.png", "blue"))
    dialog._discard_edit()
    assert dialog.first_name_edit.text() == "Student"
    assert store.registry_path.read_bytes() == registry
    assert Path(profile.avatar_path).read_bytes() == image_before
    dialog._begin_new_profile()
    dialog.first_name_edit.setText("Unsaved")
    dialog._discard_edit()
    assert dialog.profile_combo.currentData() == "default"
    assert store.registry_path.read_bytes() == registry
    dialog.close()


def test_deleted_photo_source_does_not_clear_existing_avatar(tmp_path) -> None:
    store, profile, dialog = _editor(tmp_path)
    registry = store.registry_path.read_bytes()
    source = _image(tmp_path / "vanishing.png", "blue")
    dialog._avatar_source = str(source)
    source.unlink()
    dialog._save_profile()
    assert store.registry_path.read_bytes() == registry
    assert dialog.message.text() == _COPY["ru"]["photo_error"]
    assert store.get_profile(profile.id).avatar_path == profile.avatar_path
    dialog.close()


def test_maximum_name_fields_survive_create_update_and_reload(tmp_path) -> None:
    _app()
    store = StudentProfileStore(tmp_path)
    dialog = StudentProfileDialog(store, "ru")
    dialog._begin_new_profile()
    dialog.first_name_edit.setText("A" * 40)
    dialog.last_name_edit.setText("B" * 40)
    dialog.username_edit.setText("maximum.name")
    dialog._save_profile()
    assert not dialog.message.text()
    saved = store.active_profile()
    assert saved.first_name == "A" * 40 and saved.last_name == "B" * 40
    saved = store.update_profile(saved.id, first_name="C" * 40, last_name="D" * 40, username=saved.username)
    assert StudentProfileStore(tmp_path).active_profile().name == saved.name
    assert len(saved.name) == 81
    dialog.close()


def test_new_profile_commit_failure_is_retryable_without_partial_profile(tmp_path, monkeypatch) -> None:
    _app()
    store = StudentProfileStore(tmp_path)
    dialog = StudentProfileDialog(store, "ru")
    dialog._begin_new_profile()
    dialog.first_name_edit.setText("Retry")
    dialog.last_name_edit.setText("Student")
    dialog.username_edit.setText("retry.student")
    dialog._avatar_source = str(_image(tmp_path / "source.png", "blue"))
    before = store.registry_path.read_bytes()

    def refused(_payload):
        raise OSError("registry unavailable")

    with monkeypatch.context() as patch:
        patch.setattr(store, "_write_registry", refused)
        dialog._save_profile()
    assert store.registry_path.read_bytes() == before
    assert dialog._new_profile and not dialog.first_name_edit.isReadOnly()
    assert not list((tmp_path / "profile_avatars").glob("*.png"))
    dialog._save_profile()
    assert not dialog.message.text()
    assert len(store.list_profiles()) == 2
    assert store.active_profile().name == "Retry Student"
    assert len(list((tmp_path / "profile_avatars").glob("*.png"))) == 1
    dialog.close()


def test_photo_picker_cancel_and_invalid_selection_preserve_draft(tmp_path, monkeypatch) -> None:
    for language in ("kk", "ru", "en"):
        store, profile, dialog = _editor(tmp_path / language, language)
        before = store.registry_path.read_bytes()
        with monkeypatch.context() as patch:
            patch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *_args: ("", ""))
            dialog._choose_photo()
        assert dialog._avatar_source == profile.avatar_path
        assert not dialog.message.text()
        bad = tmp_path / language / "invalid.png"
        bad.write_bytes(b"not an image")
        with monkeypatch.context() as patch:
            patch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *_args: (str(bad), ""))
            dialog._choose_photo()
        assert dialog.message.text() == _COPY[language]["photo_error"]
        assert dialog._avatar_source == profile.avatar_path
        assert store.registry_path.read_bytes() == before
        dialog.close()


def test_identity_fields_save_in_all_languages_without_rewriting_photo(tmp_path) -> None:
    for language in ("kk", "ru", "en"):
        store, profile, dialog = _editor(tmp_path / language, language)
        photo_bytes = Path(profile.avatar_path).read_bytes()
        dialog.first_name_edit.setText("Edited")
        dialog.last_name_edit.setText("Learner")
        dialog.username_edit.setText("edited.learner")
        dialog.class_edit.setText("11 B")
        dialog.school_id_edit.setText("School-77")
        dialog._save_profile()
        assert not dialog.message.text()
        assert dialog.first_name_edit.isReadOnly()
        saved = StudentProfileStore(tmp_path / language).active_profile()
        assert (saved.name, saved.username, saved.class_name, saved.school_id) == ("Edited Learner", "edited.learner", "11 B", "School-77")
        assert saved.avatar_path == profile.avatar_path
        assert Path(profile.avatar_path).read_bytes() == photo_bytes
        assert not list((tmp_path / language / "profile_avatars").glob("*.png"))
        dialog.close()
