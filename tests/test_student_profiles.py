from __future__ import annotations

import os
from dataclasses import replace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aetherlab.services.ent_physics_bank import ENT_TOPIC_IDS
from aetherlab.services.ent_practice_progress import (
    load_attempts,
    load_goals,
    record_attempt,
    save_goals,
)
from aetherlab.services.student_profiles import StudentProfileStore
from aetherlab.ui.qt_compat import QtCore, QtWidgets

_APP = None


def _app() -> QtWidgets.QApplication:
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


def test_profiles_keep_practice_goals_and_review_files_separate(tmp_path) -> None:
    legacy_progress = tmp_path / "ent_practice_progress.json"
    save_goals(legacy_progress, {"target_score": 42, "weekly_question_goal": 30})
    store = StudentProfileStore(tmp_path, default_name="Оқушы 1")
    first = store.active_profile()
    assert first.progress_path == legacy_progress
    assert load_goals(first.progress_path)["target_score"] == 42
    record_attempt(
        first.progress_path,
        language="kk",
        topic_results={ENT_TOPIC_IDS[0]: {"correct": 1, "total": 1}},
        question_results={},
    )

    second = store.create_profile("Аружан")
    assert second.progress_path != first.progress_path
    assert second.course_progress_path != first.course_progress_path
    assert load_goals(second.progress_path)["target_score"] is None
    assert load_attempts(second.progress_path) == []

    save_goals(second.progress_path, {"target_score": 28, "weekly_question_goal": 12})
    assert load_goals(first.progress_path)["target_score"] == 42
    assert load_goals(second.progress_path)["target_score"] == 28
    assert len(load_attempts(first.progress_path)) == 1
    assert load_attempts(second.progress_path) == []

    store.set_active_profile(second.id)
    reopened = StudentProfileStore(tmp_path)
    assert reopened.active_profile().id == second.id
    assert reopened.active_profile().name == "Аружан"


def test_profile_names_are_required_unique_and_bounded(tmp_path) -> None:
    store = StudentProfileStore(tmp_path)
    for name, error in ((" ", "empty"), ("Learner 1", "duplicate"), ("x" * 81, "too_long")):
        try:
            store.create_profile(name)
        except ValueError as exc:
            assert str(exc) == error
        else:
            raise AssertionError(f"Expected profile validation error: {error}")


def test_dashboard_profile_button_opens_profile_flow_and_can_switch(tmp_path) -> None:
    _app()
    from aetherlab.ui.profile_dialog import StudentProfileDialog
    from aetherlab.ui.student_views import StudentDashboard

    store = StudentProfileStore(tmp_path, default_name="Оқушы 1")
    dashboard = StudentDashboard(
        store.active_profile().progress_path,
        language="kk",
        profile_name=store.active_profile().name,
    )
    requested = []
    dashboard.profile_requested.connect(lambda: requested.append(True))
    dashboard.profile_button.click()
    assert requested == [True]
    assert dashboard.profile_button.name == "Оқушы 1"

    dialog = StudentProfileDialog(store, "kk")
    dialog.new_button.click()
    dialog.first_name_edit.setText("Аружан")
    dialog.last_name_edit.setText("Серік")
    dialog.username_edit.setText("aruzhan")
    dialog.class_edit.setText("11 A")
    dialog.school_id_edit.setText("UNT-2026-001")
    assert dialog.login_edit.text() == "aruzhan@gmail.com"
    dialog.save_button.click()
    assert dialog.profile_combo.currentText() == "Аружан Серік"
    created_profile = store.get_profile(str(dialog.profile_combo.currentData()))
    assert created_profile is not None
    assert created_profile.email == "aruzhan@gmail.com"
    assert created_profile.class_name == "11 A"
    assert created_profile.school_id == "UNT-2026-001"
    assert store.active_profile().name == "Аружан Серік"
    dialog.use_button.click()
    assert store.active_profile().name == "Аружан Серік"
    assert dialog.result() == QtWidgets.QDialog.DialogCode.Accepted

    dashboard.set_profile("Аружан Серік")
    assert dashboard.profile_button.name == "Аружан Серік"
    dashboard.close()
    dialog.close()


def test_profile_button_retranslates_without_changing_profile_name(tmp_path) -> None:
    _app()
    from aetherlab.ui.student_views import StudentDashboard

    dashboard = StudentDashboard(tmp_path / "progress.json", "kk", profile_name="Аружан")
    dashboard.set_language("en")
    assert dashboard.profile_button.name == "Аружан"
    assert "profile" in dashboard.profile_button.toolTip().lower()
    dashboard.close()


def test_main_window_switches_all_student_views_to_the_selected_profile(tmp_path) -> None:
    _app()
    from aetherlab.core.settings import load_settings
    from aetherlab.ui.main_window import MainWindow
    from aetherlab.ui.profile_dialog import StudentProfileDialog

    settings = replace(
        load_settings(),
        data_dir=tmp_path,
        cache_path=tmp_path / "cache.sqlite3",
        chroma_path=tmp_path / "chroma",
        library_path=tmp_path / "library",
        openai_api_key="test-key",
        reference_sources_path=None,
    )
    window = MainWindow(settings)
    expected = {}

    def create_and_switch() -> None:
        dialog = window.findChild(StudentProfileDialog, "StudentProfileDialog")
        assert dialog is not None
        dialog.new_button.click()
        dialog.first_name_edit.setText("Аружан")
        dialog.last_name_edit.setText("Серік")
        dialog.username_edit.setText("aruzhan")
        dialog.class_edit.setText("11 A")
        dialog.school_id_edit.setText("UNT-2026-001")
        dialog.save_button.click()
        expected["profile"] = window.student_profile_store.get_profile(
            str(dialog.profile_combo.currentData())
        )
        dialog.use_button.click()

    QtCore.QTimer.singleShot(0, create_and_switch)
    window.title_bar.profile_button.click()
    profile = expected["profile"]
    assert profile is not None
    assert window.active_student_profile.id == profile.id
    assert window.student_dashboard.progress_path == profile.progress_path
    assert window.topic_catalog.progress_path == profile.progress_path
    assert window.progress_overview.progress_path == profile.progress_path
    assert window.course_progress.path == profile.course_progress_path
    assert window.title_bar.profile_button.name == profile.name
    assert not window.student_dashboard.profile_button.isVisible()
    window.close()
