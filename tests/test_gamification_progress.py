"""Learning-based progression and its visible student UI."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_APP = None


def _app():
    from aetherlab.ui.fonts import install_ui_fonts
    from aetherlab.ui.qt_compat import QtWidgets

    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    install_ui_fonts()
    return _APP


def test_topic_confidence_uses_minimum_sample_and_accuracy_threshold() -> None:
    from aetherlab.services.gamification import topic_confidence

    assert topic_confidence(0, 0) == "not_started"
    assert topic_confidence(4, 4) == "practicing"  # too few questions
    assert topic_confidence(3, 5) == "practicing"  # below 80%
    assert topic_confidence(4, 5) == "confident"  # threshold is inclusive
    assert topic_confidence(5, 6) == "confident"
    assert topic_confidence(99, 5) == "confident"  # invalid over-count is clamped


def test_companion_evolves_at_lifetime_point_milestones() -> None:
    from aetherlab.services.gamification import companion_progress

    assert (companion_progress(0).stage, companion_progress(0).level) == (0, 1)
    assert companion_progress(25).progress_to_milestone == 0.5
    assert (companion_progress(50).stage, companion_progress(50).level) == (1, 2)
    assert companion_progress(149).next_milestone == 150
    final = companion_progress(150)
    assert (final.stage, final.level, final.next_milestone) == (2, 3, None)


def test_dashboard_companion_uses_score_not_topic_progress_and_remembers_choice(tmp_path) -> None:
    from aetherlab.services.ent_practice_progress import record_attempt, save_companion_choice
    from aetherlab.ui.student_views import StudentDashboard

    app = _app()
    progress_path = tmp_path / "progress.json"
    record_attempt(
        progress_path,
        language="en",
        topic_results={
            "kinematics": {"correct": 4, "total": 5},
            "dynamics": {"correct": 5, "total": 5},
            "statics": {"correct": 4, "total": 5},
        },
        score=40,
        possible_points=15,
    )

    dashboard = StudentDashboard(progress_path, language="en")
    app.processEvents()

    # Topic confidence does not decide which physics companion is selected.
    assert dashboard.companion_art.stage == 0
    assert dashboard.companion_level_label.text() == "Level 1"
    assert dashboard.companion_progress_label.text() == "40 points · 10 to next form"
    assert "#53647A" in dashboard.companion_title.styleSheet()
    save_companion_choice(progress_path, "photon")
    dashboard.refresh()
    assert dashboard.companion_art.companion_id == "photon"
    assert dashboard.companion_stage_label.text() == "Photon"

    record_attempt(progress_path, language="en", topic_results={}, score=10, possible_points=10)
    dashboard.refresh()
    assert dashboard.companion_art.stage == 1
    assert dashboard.companion_stage_label.text() == "Photon"
    assert dashboard.companion_level_label.text() == "Level 2"
    assert dashboard.companion_progress_label.text() == "50 points · 100 to next form"

    dashboard.set_language("kk")
    assert dashboard.companion_stage_label.text() == "Фотон"
    dashboard.close()


def test_companion_picker_selects_one_of_three_and_accepts_choice(tmp_path) -> None:
    from aetherlab.ui.companion_dialog import CompanionPickerDialog
    from aetherlab.ui.qt_compat import QtWidgets
    from aetherlab.ui.study_visuals import CompanionArt

    _app()
    dialog = CompanionPickerDialog(selected_companion=None, points=65, language="ru")
    assert len(dialog._choice_buttons) == 3
    assert len(dialog.findChildren(CompanionArt)) == 3
    assert all(not art._concept_sheet.isNull() for art in dialog.findChildren(CompanionArt))
    assert all(art._concept_sheet.width() == 3840 for art in dialog.findChildren(CompanionArt))
    assert not dialog.confirm_button.isEnabled()

    dialog._choice_buttons["lab_bot"].click()
    assert dialog.confirm_button.isEnabled()
    assert dialog._choice_buttons["lab_bot"].text() == "Выбран"
    dialog.confirm_button.click()

    assert dialog.result() == QtWidgets.QDialog.DialogCode.Accepted
    assert dialog.selected_companion == "lab_bot"


def test_dashboard_companion_button_persists_the_selected_companion(tmp_path, monkeypatch) -> None:
    from aetherlab.services.ent_practice_progress import load_companion_choice
    from aetherlab.ui.companion_dialog import CompanionPickerDialog
    from aetherlab.ui.qt_compat import QtWidgets
    from aetherlab.ui.student_views import StudentDashboard

    _app()
    progress_path = tmp_path / "profile-progress.json"

    def select_photon(dialog):
        dialog._select_companion("photon")
        return QtWidgets.QDialog.DialogCode.Accepted

    monkeypatch.setattr(CompanionPickerDialog, "exec", select_photon)
    dashboard = StudentDashboard(progress_path, language="en")
    dashboard.companion_select_button.click()

    assert load_companion_choice(progress_path) == "photon"
    assert dashboard.companion_art.companion_id == "photon"
    assert dashboard.companion_stage_label.text() == "Photon"
    assert dashboard.companion_select_button.text() == "Change companion"
    dashboard.close()


def test_companion_choice_and_lifetime_points_are_profile_local(tmp_path) -> None:
    from aetherlab.services.ent_practice_progress import (
        load_companion_choice,
        load_companion_points,
        record_attempt,
        save_companion_choice,
    )

    first = tmp_path / "first" / "progress.json"
    second = tmp_path / "second" / "progress.json"
    save_companion_choice(first, "quantum")
    record_attempt(first, language="kk", topic_results={}, score=31, possible_points=40)
    record_attempt(first, language="kk", topic_results={}, score=9, possible_points=10)

    assert load_companion_choice(first) == "quantum"
    assert load_companion_choice(second) is None
    assert load_companion_points(first) == 40
    assert load_companion_points(second) == 0


def test_legacy_pet_choice_requires_reselection_without_losing_points(tmp_path) -> None:
    import json

    from aetherlab.services.ent_practice_progress import (
        load_companion_choice,
        load_companion_points,
    )

    path = tmp_path / "legacy-progress.json"
    path.write_text(
        json.dumps({"companion_choice": "bunny", "companion_total_points": 85}),
        encoding="utf-8",
    )

    assert load_companion_choice(path) is None
    assert load_companion_points(path) == 85


def test_topic_catalog_explains_confidence_state_and_keeps_actions(tmp_path) -> None:
    from aetherlab.services.ent_practice_progress import record_attempt
    from aetherlab.ui.qt_compat import QtWidgets
    from aetherlab.ui.student_views import TopicCatalogView

    app = _app()
    progress_path = tmp_path / "progress.json"
    record_attempt(
        progress_path,
        language="en",
        topic_results={
            "kinematics": {"correct": 4, "total": 5},
            "dynamics": {"correct": 1, "total": 5},
        },
        score=5,
        possible_points=10,
    )
    view = TopicCatalogView(progress_path, language="en")
    view.resize(1080, 680)
    view.show()
    app.processEvents()

    labels = [label.text() for label in view.findChildren(QtWidgets.QLabel, "TopicMasteryStatus")]
    assert labels.count("Confident") == 1
    assert labels.count("In progress") == 1
    assert labels.count("Not started") == 23
    assert view.mastery_summary.text() == "Confident topics: 1/25"
    assert "5+ questions" in view.mastery_rule_label.text()

    practice_destinations = []
    view.practice_topic_requested.connect(practice_destinations.append)
    first_card = view.rows.itemAt(0).widget()
    next(button for button in first_card.findChildren(QtWidgets.QPushButton) if button.text() == "Practice").click()
    assert len(practice_destinations) == 1

    view.set_language("ru")
    assert "Уверенно освоено тем: 1/25" == view.mastery_summary.text()
    assert any(label.text() == "Уверенно" for label in view.findChildren(QtWidgets.QLabel, "TopicMasteryStatus"))
    view.close()
