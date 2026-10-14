"""Mode/endpoint changes must not mislabel a previously loaded ranking."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aetherlab.services.leaderboard_client import LeaderboardSettingsStore
from aetherlab.services.school_leaderboard import MockScore, SchoolLeaderboardEntry
from aetherlab.services.student_profiles import StudentProfileStore
from aetherlab.ui.leaderboard_dialog import LeaderboardDialog
from aetherlab.ui.qt_compat import QtWidgets

_APP = None


def _dialog(root, language="ru"):
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    store = StudentProfileStore(root)
    profile = store.update_profile("default", first_name="Local", last_name="Learner", username="local.learner", school_id="School-77")
    dialog = LeaderboardDialog(store, profile, language)
    return store, dialog


def _remote_snapshot(dialog):
    entry = SchoolLeaderboardEntry(
        rank=1, name="Remote snapshot", class_name="11 B", best_score=49,
        latest_score=49, mock_count=1,
        scores=(MockScore(49, "2026-10-12T12:00:00+00:00"),), is_current_user=False,
    )
    # Exercise the real worker-completion/render path, not a single changed cell.
    dialog._sync_completed([entry])
    assert dialog.entries == [entry]
    assert dialog.table.item(0, 1).text() == entry.name
    return entry


def test_clearing_endpoint_restores_local_rows_instead_of_labelling_remote_rows_local(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("AETHERLAB_LEADERBOARD_URL", raising=False)
    for language in ("kk", "ru", "en"):
        store, dialog = _dialog(tmp_path / language, language)
        dialog.settings.set_server_url("https://school.example.kz")
        _remote_snapshot(dialog)
        dialog.server_edit.clear()
        dialog._save_server_url()
        assert dialog.table.item(0, 1).text() == store.active_profile().name
        assert all(entry.name != "Remote snapshot" for entry in dialog.entries)
        assert dialog.status.text() == dialog.text["local_mode"]
        assert dialog.settings.get_server_url() == ""
        dialog.close()


def test_clearing_endpoint_with_read_failure_does_not_claim_local_data_loaded(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("AETHERLAB_LEADERBOARD_URL", raising=False)
    _store, dialog = _dialog(tmp_path)
    dialog.settings.set_server_url("https://school.example.kz")
    remote = _remote_snapshot(dialog)
    dialog.server_edit.clear()

    def refused():
        raise PermissionError("local registry unavailable")

    monkeypatch.setattr(dialog.profile_store, "list_profiles", refused)
    dialog._save_server_url()
    assert dialog.status.text() == dialog.text["local_read_error"]
    assert dialog.table.item(0, 1).text() == "Remote snapshot"
    assert dialog.entries == [remote]
    assert dialog.settings.get_server_url() == ""
    dialog.close()


def test_environment_endpoint_override_is_effective_after_save(tmp_path, monkeypatch) -> None:
    override = "https://configured-school.example.kz"
    monkeypatch.setenv("AETHERLAB_LEADERBOARD_URL", override)
    settings = LeaderboardSettingsStore(tmp_path)
    assert settings.get_server_url() == override
    effective = settings.set_server_url("https://saved-school.example.kz")
    assert effective == settings.get_server_url() == override
    monkeypatch.delenv("AETHERLAB_LEADERBOARD_URL")
    assert settings.get_server_url() == "https://saved-school.example.kz"


def test_dialog_explains_active_environment_override_in_each_language(tmp_path, monkeypatch) -> None:
    override = "https://configured-school.example.kz"
    monkeypatch.setenv("AETHERLAB_LEADERBOARD_URL", override)
    for language in ("kk", "ru", "en"):
        _store, dialog = _dialog(tmp_path / language, language)
        dialog.server_edit.clear()
        dialog._save_server_url()
        assert dialog.server_edit.text() == override
        assert dialog.status.text() == dialog.text["environment_override"]
        assert "AETHERLAB_LEADERBOARD_URL" in dialog.status.text()
        assert dialog.worker is None
        dialog.close()


def test_invalid_environment_override_blocks_sync_with_configuration_diagnosis(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHERLAB_LEADERBOARD_URL", "https://school.example.kz/?secret=hidden")
    for language in ("kk", "ru", "en"):
        _store, dialog = _dialog(tmp_path / language, language)
        assert dialog.status.text() == dialog.text["invalid_environment_override"]
        dialog.server_edit.setText("https://saved-school.example.kz")
        dialog._sync()
        assert dialog.worker is None
        assert dialog.status.text() == dialog.text["invalid_environment_override"]
        assert "hidden" not in dialog.status.text()
        assert dialog.settings.get_server_url() == ""
        dialog.close()


def test_sync_uses_and_displays_effective_environment_endpoint(tmp_path, monkeypatch) -> None:
    from aetherlab.ui import leaderboard_dialog

    override = "https://configured-school.example.kz"
    monkeypatch.setenv("AETHERLAB_LEADERBOARD_URL", override)
    started = []

    class Signal:
        def connect(self, _callback):
            pass

    class Worker:
        completed = Signal()
        failed = Signal()
        finished = Signal()

        def __init__(self, url, _profile, _parent):
            self.url = url

        def start(self):
            started.append(self.url)

        def isRunning(self):
            return False

        def deleteLater(self):
            pass

    monkeypatch.setattr(leaderboard_dialog, "_SyncWorker", Worker)
    _store, dialog = _dialog(tmp_path)
    dialog.server_edit.setText("https://saved-school.example.kz")
    dialog._sync()
    assert started == [override]
    assert dialog.server_edit.text() == override
    dialog._sync_finished()
    dialog.close()
