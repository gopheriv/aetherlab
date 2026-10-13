from __future__ import annotations

import os
from datetime import datetime, timezone

from aetherlab.services.ent_practice_progress import record_attempt
from aetherlab.services.student_profiles import StudentProfileStore
from aetherlab.services.teacher_review import local_school_mock_review
from aetherlab.ui.qt_compat import QtWidgets

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_APP = None


def _app():
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


def _mock(path, *, score: int, proctor_enabled: bool, events=None, full_mock=True):
    return record_attempt(
        path,
        language="ru",
        topic_results={},
        score=score,
        possible_points=50 if full_mock else 10,
        full_mock=full_mock,
        proctor_enabled=proctor_enabled,
        integrity_events=events,
    )[-1]


def test_local_review_shows_only_school_full_mocks_and_allowlisted_signals(tmp_path):
    store = StudentProfileStore(tmp_path / "profiles", default_name="Learner")
    teacher_group = store.create_profile(
        "Aruzhan", username="aruzhan", school_id="school-77", class_name="11 A",
    )
    peer = store.create_profile("Dias", school_id=" SCHOOL-77 ", class_name="11 B")
    outsider = store.create_profile("Mira", school_id="school-88")
    event_at = "2020-01-02T03:04:05+00:00"
    _mock(
        teacher_group.progress_path,
        score=43,
        proctor_enabled=True,
        events=[
            {"type": "face_not_visible", "at": event_at},
            {"type": "cheating_detected", "at": event_at},
        ],
    )
    _mock(peer.progress_path, score=47, proctor_enabled=False)
    _mock(outsider.progress_path, score=50, proctor_enabled=True)
    _mock(peer.progress_path, score=6, proctor_enabled=True, full_mock=False)

    entries = local_school_mock_review(store.list_profiles(), " School-77 ")

    assert [entry.student_name for entry in entries] == ["Aruzhan", "Dias"]
    assert entries[0].score == 43
    assert entries[0].proctor_enabled is True
    assert entries[0].integrity_events == (("face_not_visible", event_at),)
    assert entries[1].proctor_enabled is False
    assert entries[1].integrity_events == ()
    assert local_school_mock_review(store.list_profiles(), " ") == []


def test_camera_event_time_does_not_replace_attempt_completion_time(tmp_path):
    path = tmp_path / "progress.json"
    event_at = "2020-01-02T03:04:05+00:00"

    attempt = _mock(
        path,
        score=42,
        proctor_enabled=True,
        events=[{"type": "face_not_visible", "at": event_at}],
    )

    completed_at = datetime.fromisoformat(attempt["completed_at"])
    assert completed_at > datetime(2020, 1, 2, tzinfo=timezone.utc)
    assert attempt["integrity_events"][0]["at"] == event_at


def test_teacher_review_dialog_discloses_local_access_and_camera_flags_are_not_verdicts(tmp_path):
    _app()
    from aetherlab.ui.teacher_review_dialog import TeacherReviewDialog

    store = StudentProfileStore(tmp_path / "profiles", default_name="Learner")
    profile = store.create_profile("Aruzhan", username="aruzhan", school_id="school-77")
    _mock(profile.progress_path, score=42, proctor_enabled=True)

    dialog = TeacherReviewDialog(store, profile, language="ru")

    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 1).text() == "Aruzhan"
    assert dialog.table.item(0, 3).text() == "42/50"
    assert dialog.table.item(0, 4).text() == "Включена"
    assert any(
        "не доказательство списывания" in label.text()
        for label in dialog.findChildren(QtWidgets.QLabel)
    )
    assert dialog.events_table.item(0, 0).text() == "Нет сигналов"
    dialog.close()
