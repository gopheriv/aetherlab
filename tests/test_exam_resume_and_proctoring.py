from __future__ import annotations

import json
from datetime import datetime, timezone

from aetherlab.services.ent_physics_bank import (
    ENT_FULL_MOCK_DURATION_S,
    mock_questions_for_language,
)
from aetherlab.services.ent_practice_progress import (
    clear_active_session,
    load_active_session,
    record_attempt,
    save_active_session,
)
from aetherlab.services.proctoring import ShadowEventTracker


def test_active_exam_answers_round_trip_and_timer_keeps_running_while_closed(tmp_path) -> None:
    progress = tmp_path / "student-progress.json"
    questions = mock_questions_for_language("ru")[:2]
    state = {
        "question_ids": [item["id"] for item in questions],
        "answers": [(1,), None],
        "index": 1,
        "seconds_left": 4200,
        "mode": "timed",
        "language": "ru",
        "full_mock": False,
        "proctor_enabled": False,
    }

    assert save_active_session(progress, state)
    restored = load_active_session(progress)
    assert restored is not None
    assert restored["answers"] == [(1,), None]
    assert restored["index"] == 1
    assert 0 <= restored["seconds_left"] <= 4200

    clear_active_session(progress)
    assert load_active_session(progress) is None


def test_shadow_camera_flags_are_sparse_and_recover_after_face_returns() -> None:
    tracker = ShadowEventTracker(face_missing_after_s=4, multiple_faces_after_s=2)
    assert tracker.observe_face_count(0, now=10.0) == []
    assert tracker.observe_face_count(0, now=13.9) == []
    missing = tracker.observe_face_count(0, now=14.0)
    assert [event["type"] for event in missing] == ["face_not_visible"]
    assert tracker.observe_face_count(0, now=18.0) == []
    tracker.observe_face_count(1, now=19.0)
    assert tracker.observe_face_count(0, now=20.0) == []

    tracker.observe_face_count(2, now=21.0)
    assert tracker.observe_face_count(2, now=23.0)[0]["type"] == "multiple_faces"
    assert tracker.note_focus_loss()["type"] == "app_focus_lost"
    assert len(tracker.snapshot()) == 3


def test_camera_downtime_does_not_count_as_observed_missing_or_multiple_faces() -> None:
    tracker = ShadowEventTracker(face_missing_after_s=4, multiple_faces_after_s=2)
    assert tracker.observe_face_count(0, now=0) == []
    assert tracker.observe_face_count(-1, now=1)[0]["type"] == "camera_unavailable"
    assert tracker.observe_face_count(0, now=20) == []
    assert tracker.observe_face_count(0, now=23.9) == []
    assert tracker.observe_face_count(0, now=24)[0]["type"] == "face_not_visible"

    tracker.observe_face_count(1, now=25)
    assert tracker.observe_face_count(2, now=26) == []
    assert tracker.note_camera_lost()["type"] == "camera_lost"
    assert tracker.observe_face_count(2, now=50) == []
    assert tracker.observe_face_count(2, now=51.9) == []
    assert tracker.observe_face_count(2, now=52)[0]["type"] == "multiple_faces"


def test_attempt_persists_only_allowlisted_camera_event_metadata(tmp_path) -> None:
    path = tmp_path / "progress.json"
    event_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record_attempt(
        path,
        language="kk",
        topic_results={},
        question_results={},
        integrity_events=[
            {"type": "face_not_visible", "at": event_at},
            {"type": "cheating_detected", "at": event_at},
            {"type": "multiple_faces", "at": "invalid"},
        ],
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["attempts"][0]["integrity_events"] == [
        {"type": "face_not_visible", "at": event_at}
    ]
    assert "video" not in json.dumps(payload).lower()


def test_full_mock_timer_uses_ninety_minutes_and_resume_keeps_answers(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from aetherlab.ui.exam_practice import ExamPracticeDialog
    from aetherlab.ui.qt_compat import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert app is not None
    path = tmp_path / "student-progress.json"
    questions = mock_questions_for_language("kk")
    dialog = ExamPracticeDialog("kk", progress_path=path)
    dialog._full_mock = True
    dialog._begin_session(questions, "timed")
    assert dialog._seconds_left == ENT_FULL_MOCK_DURATION_S == 90 * 60
    dialog.close()  # leaves the active attempt available to resume

    resumed = ExamPracticeDialog("kk", progress_path=path)
    state = load_active_session(path)
    assert state is not None
    state["answers"][0] = (questions[0]["correct_indices"][0],)
    state["index"] = 1
    assert save_active_session(path, state)
    state = load_active_session(path)
    assert state is not None
    assert resumed._resume_active_session(state)
    assert resumed._seconds_left <= ENT_FULL_MOCK_DURATION_S
    assert resumed._answers[0] == (questions[0]["correct_indices"][0],)
    assert resumed._index == 1
    resumed.close()
