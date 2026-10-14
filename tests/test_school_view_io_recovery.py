"""Shared profile-read errors must remain usable in ranking/review screens."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aetherlab.services.ent_practice_progress import record_attempt
from aetherlab.services.student_profiles import StudentProfileStore
from aetherlab.ui.qt_compat import QtWidgets

_APP = None


def _setup(root):
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    store = StudentProfileStore(root)
    profile = store.update_profile("default", first_name="Student", last_name="One", username="student.one", school_id="School-77")
    record_attempt(profile.progress_path, language="ru", topic_results={}, score=42, possible_points=50, full_mock=True)
    return store, profile


def _refused(*_args):
    raise PermissionError("local profile file is temporarily unreadable")


def test_teacher_review_reports_load_failure_and_retry_restores_scores(tmp_path, monkeypatch) -> None:
    from aetherlab.ui.teacher_review_dialog import TeacherReviewDialog

    for language in ("kk", "ru", "en"):
        store, profile = _setup(tmp_path / language)
        with monkeypatch.context() as patch:
            patch.setattr(store, "list_profiles", _refused)
            dialog = TeacherReviewDialog(store, profile, language)
        assert dialog.status.text() == dialog.text["load_error"]
        assert dialog.table.item(0, 0).text() == dialog.text["load_error"]
        dialog.reload_button.click()
        assert dialog.table.item(0, 3).text() == "42/50"
        assert dialog.table.columnSpan(0, 0) == 1
        assert not dialog.status.text()
        before = list(dialog.entries)
        with monkeypatch.context() as patch:
            patch.setattr(store, "list_profiles", _refused)
            assert not dialog._reload()
        assert dialog.entries == before
        assert dialog.table.item(0, 3).text() == "42/50"
        assert dialog.status.text() == dialog.text["load_error"]
        dialog.close()


def test_local_ranking_reports_initial_and_refresh_failure_without_clearing_scores(tmp_path, monkeypatch) -> None:
    from aetherlab.ui.leaderboard_dialog import LeaderboardDialog

    for language in ("kk", "ru", "en"):
        store, profile = _setup(tmp_path / language)
        with monkeypatch.context() as patch:
            patch.setattr(store, "list_profiles", _refused)
            dialog = LeaderboardDialog(store, profile, language)
        assert dialog.status.text() == dialog.text["local_read_error"]
        dialog._sync()
        assert dialog.table.item(0, 3).text() == "42/50"
        before = list(dialog.entries)
        with monkeypatch.context() as patch:
            patch.setattr(store, "list_profiles", _refused)
            dialog._sync()
        assert dialog.entries == before
        assert dialog.table.item(0, 3).text() == "42/50"
        assert dialog.status.text() == dialog.text["local_read_error"]
        assert dialog.worker is None
        dialog.close()


def test_leaderboard_endpoint_save_error_keeps_draft_and_reports_storage_error(tmp_path, monkeypatch) -> None:
    from aetherlab.ui.leaderboard_dialog import LeaderboardDialog

    for language in ("kk", "ru", "en"):
        store, profile = _setup(tmp_path / language)
        dialog = LeaderboardDialog(store, profile, language)
        dialog.server_edit.setText("https://school.example.kz")
        with monkeypatch.context() as patch:
            patch.setattr(dialog.settings, "set_server_url", _refused)
            dialog._save_server_url()
        assert dialog.status.text() == dialog.text["settings_error"]
        assert dialog.server_edit.text() == "https://school.example.kz"
        assert dialog.settings.get_server_url() == ""
        with monkeypatch.context() as patch:
            patch.setattr(dialog.settings, "set_server_url", _refused)
            dialog._sync()
        assert dialog.status.text() == dialog.text["settings_error"]
        assert dialog.worker is None
        dialog.close()


def test_score_history_clears_empty_placeholder_span_when_changing_student(tmp_path) -> None:
    from aetherlab.ui.leaderboard_dialog import LeaderboardDialog

    store, profile = _setup(tmp_path)
    store.create_profile("No Mock", school_id=profile.school_id)
    dialog = LeaderboardDialog(store, profile, "ru")
    empty_row = next(i for i, entry in enumerate(dialog.entries) if entry.name == "No Mock")
    scored_row = next(i for i, entry in enumerate(dialog.entries) if entry.name == profile.name)
    dialog.table.selectRow(empty_row)
    assert dialog.history_table.columnSpan(0, 0) == 2
    dialog.table.selectRow(scored_row)
    assert dialog.history_table.columnSpan(0, 0) == 1, "A date placeholder must not cover the score column"
    assert dialog.history_table.item(0, 1).text() == "42/50"
    dialog.close()
