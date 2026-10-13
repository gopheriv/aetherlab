from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aetherlab.services.ent_practice_progress import record_attempt
from aetherlab.services.leaderboard_client import (
    _participant_id,
    sync_school_leaderboard,
    validate_server_url,
)
from aetherlab.services.leaderboard_server import (
    LeaderboardRepository,
    LeaderboardRequestHandler,
)
from aetherlab.services.school_leaderboard import school_leaderboard
from aetherlab.services.student_profiles import StudentProfileStore
from aetherlab.ui.qt_compat import QtWidgets

_APP = None


def _app():
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


def _mock(path, score: int, *, full_mock: bool = True, points: int = 50) -> None:
    record_attempt(
        path,
        language="kk",
        topic_results={},
        question_results={},
        score=score,
        possible_points=points,
        full_mock=full_mock,
    )


def test_local_ranking_groups_by_school_and_only_counts_full_mocks(tmp_path):
    store = StudentProfileStore(tmp_path / "profiles", default_name="Aruzhan")
    first = store.update_profile(
        "default", first_name="Aruzhan", last_name="A", username="aruzhan",
        class_name="11 A", school_id="School-77",
    )
    second = store.create_profile(
        "Dias B", username="dias", class_name="11 B", school_id=" school-77 ",
    )
    outsider = store.create_profile(
        "Mira C", username="mira", class_name="11 C", school_id="School-88",
    )
    _mock(first.progress_path, 41)
    _mock(first.progress_path, 48, full_mock=False, points=10)
    _mock(second.progress_path, 48)
    _mock(outsider.progress_path, 50)

    ranking = school_leaderboard(store.list_profiles(), " SCHOOL-77 ", current_profile_id=first.id)

    assert [entry.name for entry in ranking] == ["Dias B", "Aruzhan A"]
    assert [entry.rank for entry in ranking] == [1, 2]
    assert ranking[1].best_score == 41
    assert ranking[1].mock_count == 1
    assert ranking[1].is_current_user


def test_shared_server_merges_scores_across_devices(tmp_path):
    db_path = tmp_path / "shared.sqlite3"
    repository = LeaderboardRepository(db_path, "test-secret-that-is-long-enough-123456")
    server = ThreadingHTTPServer(("127.0.0.1", 0), LeaderboardRequestHandler)
    server.repository = repository
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        first_store = StudentProfileStore(tmp_path / "device-one", default_name="Aruzhan A")
        first = first_store.update_profile(
            "default", first_name="Aruzhan", last_name="A", username="aruzhan",
            class_name="11 A", school_id="School-77",
        )
        _mock(first.progress_path, 42)
        first_result = sync_school_leaderboard(base_url, first)
        assert len(first_result) == 1
        assert first_result[0].best_score == 42

        second_store = StudentProfileStore(tmp_path / "device-two", default_name="Dias B")
        second = second_store.update_profile(
            "default", first_name="Dias", last_name="B", username="dias",
            class_name="11 B", school_id="school-77",
        )
        _mock(second.progress_path, 49)
        second_result = sync_school_leaderboard(base_url, second)
        assert [entry.best_score for entry in second_result] == [49, 42]
        assert [entry.rank for entry in second_result] == [1, 2]
        assert [entry.name for entry in second_result] == ["Dias B", "Aruzhan A"]

        other_store = StudentProfileStore(tmp_path / "device-three", default_name="Mira C")
        outsider = other_store.update_profile(
            "default", first_name="Mira", last_name="C", username="mira",
            class_name="11 C", school_id="School-88",
        )
        _mock(outsider.progress_path, 50)
        other_result = sync_school_leaderboard(base_url, outsider)
        assert len(other_result) == 1
        assert other_result[0].name == "Mira C"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_same_username_and_school_id_reuses_remote_student_identity(tmp_path):
    repository = LeaderboardRepository(
        tmp_path / "identity.sqlite3", "test-secret-that-is-long-enough-123456"
    )
    timestamp_a = datetime(2026, 10, 9, 10, 0, tzinfo=timezone.utc).isoformat()
    timestamp_b = datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc).isoformat()
    payload = {
        "school_id": "School-77",
        "student_id": "a" * 64,
        "name": "Aruzhan A",
        "class_name": "11 A",
        "scores": [{"score": 42, "completed_at": timestamp_a}],
    }
    repository.submit(payload)
    payload["scores"] = [{"score": 47, "completed_at": timestamp_b}]
    result = repository.submit(payload)

    assert len(result["entries"]) == 1
    entry = result["entries"][0]
    assert entry["best_score"] == 47
    assert entry["mock_count"] == 2
    assert entry["scores"][0]["score"] == 47


def test_server_rejects_invalid_mock_scores_and_remote_http_url(tmp_path):
    repository = LeaderboardRepository(
        tmp_path / "validation.sqlite3", "test-secret-that-is-long-enough-123456"
    )
    with pytest.raises(ValueError, match="https_required"):
        validate_server_url("http://leaderboard.example.com")
    with pytest.raises(ValueError, match="invalid_url"):
        validate_server_url("https://leaderboard.example.com/api")
    with pytest.raises(ValueError, match="between 0 and 50"):
        repository.submit({
            "school_id": "School-77",
            "student_id": "b" * 64,
            "name": "Student B",
            "class_name": "11 B",
            "scores": [{"score": 88, "completed_at": "2026-10-09T10:00:00+00:00"}],
        })


def test_school_id_is_not_returned_and_db_stores_only_hmac(tmp_path):
    db_path = tmp_path / "private.sqlite3"
    repository = LeaderboardRepository(db_path, "test-secret-that-is-long-enough-123456")
    result = repository.submit({
        "school_id": "Private-Id-999",
        "student_id": "c" * 64,
        "name": "Student C",
        "class_name": "11 C",
        "scores": [],
    })

    assert "Private-Id-999" not in json.dumps(result)
    raw_db = db_path.read_bytes()
    assert b"Private-Id-999" not in raw_db


def test_same_username_and_school_id_share_participant_key_on_two_devices(tmp_path):
    first_store = StudentProfileStore(tmp_path / "first", default_name="Student")
    first = first_store.update_profile(
        "default", first_name="Student", last_name="One", username="student.one",
        class_name="11 A", school_id="School-77",
    )
    second_store = StudentProfileStore(tmp_path / "second", default_name="Student")
    second = second_store.update_profile(
        "default", first_name="Student", last_name="One", username="student.one",
        class_name="11 A", school_id=" school-77 ",
    )

    assert _participant_id(first) == _participant_id(second)


def test_leaderboard_dialog_shows_local_rank_and_each_mock_score(tmp_path):
    _app()
    from aetherlab.ui.leaderboard_dialog import LeaderboardDialog
    from aetherlab.ui.student_views import StudentDashboard

    store = StudentProfileStore(tmp_path, default_name="Aruzhan A")
    first = store.update_profile(
        "default", first_name="Aruzhan", last_name="A", username="aruzhan",
        class_name="11 A", school_id="School-77",
    )
    second = store.create_profile(
        "Dias B", username="dias", class_name="11 B", school_id="School-77",
    )
    _mock(first.progress_path, 42)
    _mock(first.progress_path, 46)
    _mock(second.progress_path, 49)

    dialog = LeaderboardDialog(store, first, "ru")

    assert dialog.review_button.isEnabled()
    assert dialog.review_button.text() == "Локальная проверка пробников"
    assert dialog.table.rowCount() == 2
    assert dialog.table.item(0, 1).text() == "Dias B"
    assert dialog.table.item(0, 3).text() == "49/50"
    dialog.table.selectRow(1)
    assert dialog.history_table.rowCount() == 2
    assert {dialog.history_table.item(row, 1).text() for row in range(2)} == {"42/50", "46/50"}
    dialog.close()

    dashboard = StudentDashboard(first.progress_path, "kk", profile_name=first.name)
    requested = []
    dashboard.leaderboard_requested.connect(lambda: requested.append(True))
    dashboard.leaderboard_button.click()
    assert requested == [True]
    dashboard.set_language("en")
    assert dashboard.leaderboard_button.text() == "Top"
    dashboard.close()
