"""Unreadable progress is not a new learner, empty history or zero points."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aetherlab.services import ent_practice_progress as progress
from aetherlab.ui.qt_compat import QtWidgets

_APP = None


def _app():
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


def _refuse(monkeypatch, target):
    original = Path.read_text
    def read(path, *args, **kwargs):
        if path == target:
            raise PermissionError("temporarily unreadable progress")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", read)


def _seed(path):
    progress.save_goals(path, {"target_score": 45, "weekly_question_goal": 20})
    progress.save_companion_choice(path, "photon")
    progress.record_attempt(path, language="en", topic_results={"kinematics": {"correct": 4, "total": 5}}, score=40, possible_points=50, full_mock=True)


def test_all_progress_readers_propagate_io_without_changing_bytes(tmp_path, monkeypatch):
    path = tmp_path / "progress.json"
    _seed(path)
    before = path.read_bytes()
    with monkeypatch.context() as patch:
        _refuse(patch, path)
        for reader in (progress.load_attempts, progress.load_goals, progress.load_mistake_ids, progress.load_companion_choice, progress.load_companion_points):
            with pytest.raises(PermissionError):
                reader(path)
    assert path.read_bytes() == before


def test_student_views_retain_snapshot_on_error_and_retry_recovers(tmp_path, monkeypatch):
    _app()
    from aetherlab.ui.student_views import ProgressOverview, StudentDashboard, TopicCatalogView

    for language in ("kk", "ru", "en"):
        path = tmp_path / f"{language}.json"
        _seed(path)
        dashboard = StudentDashboard(path, language=language)
        topics = TopicCatalogView(path, language=language)
        overview = ProgressOverview(path, language=language)
        score = dashboard.metric_labels["best"][0].text()
        summary = overview.summary.text()
        mastery = topics.mastery_summary.text()
        cards = len(topics.cards)
        with monkeypatch.context() as patch:
            _refuse(patch, path)
            for view in (dashboard, topics, overview):
                view.refresh()
                assert view.progress_notice.status.text() == view.progress_notice.copy["stale"]
                assert view.progress_notice.retry.isEnabled()
            assert dashboard.metric_labels["best"][0].text() == score == "40/50"
            assert dashboard.companion_art.companion_id == "photon"
            assert overview.summary.text() == summary
            assert topics.mastery_summary.text() == mastery and len(topics.cards) == cards
        progress.record_attempt(path, language="en", topic_results={}, score=47, possible_points=50, full_mock=True)
        for view in (dashboard, topics, overview):
            view.progress_notice.retry.click()
            assert not view.progress_notice.status.text()
        assert dashboard.metric_labels["best"][0].text() == "47/50"
        assert "47/50" in overview.summary.text()
        for view in (dashboard, topics, overview):
            view.close()


def test_initial_unavailable_views_do_not_show_zero_or_empty_progress(tmp_path, monkeypatch):
    _app()
    from aetherlab.ui.student_views import ProgressOverview, StudentDashboard, TopicCatalogView

    for language in ("kk", "ru", "en"):
        path = tmp_path / f"initial-{language}.json"
        _seed(path)
        with monkeypatch.context() as patch:
            _refuse(patch, path)
            dashboard = StudentDashboard(path, language=language)
            topics = TopicCatalogView(path, language=language)
            overview = ProgressOverview(path, language=language)
            for view in (dashboard, topics, overview):
                assert view.progress_notice.status.text() == view.progress_notice.copy["unavailable"]
            assert all(value.text() == "—" for value, _ in dashboard.metric_labels.values())
            assert not dashboard.companion_panel.isVisibleTo(dashboard)
            assert "—" in topics.mastery_summary.text()
            assert not topics.filter.isEnabled()
            assert not overview.findChildren(QtWidgets.QFrame, "ProgressEmpty")
            assert not overview.review_button.isEnabled()
        for view in (dashboard, topics, overview):
            view.progress_notice.retry.click()
            assert not view.progress_notice.status.text()
            view.close()


def test_switch_to_unreadable_profile_does_not_show_previous_student_snapshot(tmp_path, monkeypatch):
    _app()
    from aetherlab.ui.student_views import ProgressOverview, StudentDashboard, TopicCatalogView

    first, second = tmp_path / "one.json", tmp_path / "two.json"
    _seed(first)
    _seed(second)
    views = [StudentDashboard(first), TopicCatalogView(first), ProgressOverview(first)]
    with monkeypatch.context() as patch:
        _refuse(patch, second)
        for view in views:
            view.progress_path = second
            view.refresh()
            assert view.progress_notice.status.text() == view.progress_notice.copy["unavailable"]
        assert views[0].metric_labels["best"][0].text() == "—"
        assert "40/50" not in views[2].summary.text()
        assert "—" in views[1].mastery_summary.text()
    for view in views:
        view.progress_notice.retry.click()
        view.close()


def test_practice_unavailable_progress_and_retry_preserve_saved_goals(tmp_path, monkeypatch):
    _app()
    from aetherlab.ui.exam_practice import ExamPracticeDialog

    for language in ("kk", "ru", "en"):
        path = tmp_path / f"exam-{language}.json"
        _seed(path)
        with monkeypatch.context() as patch:
            _refuse(patch, path)
            dialog = ExamPracticeDialog(language, progress_path=path)
            assert dialog.progress_notice.status.text() == dialog.progress_notice.copy["unavailable"]
            assert not dialog._save_plan_button.isEnabled()
            assert not dialog._target_score.isEnabled()
            assert not dialog._mistakes_button.isEnabled()
            assert dialog._start_button.isEnabled()
            dialog._start_mistake_review()
            assert dialog._stack.currentIndex() == 0
        dialog.progress_notice.retry.click()
        assert dialog._target_score.value() == 45
        assert dialog._save_plan_button.isEnabled()
        assert not dialog.progress_notice.status.text()
        dialog._target_score.setValue(48)
        with monkeypatch.context() as patch:
            _refuse(patch, path)
            dialog._update_dashboard_summary()
        dialog.progress_notice.retry.click()
        assert dialog._target_score.value() == 48  # retry must preserve an unsaved draft
        dialog.close()


def test_missing_and_malformed_progress_still_recover_as_before(tmp_path):
    path = tmp_path / "missing.json"
    assert progress.load_attempts(path) == []
    assert progress.load_goals(path)["target_score"] is None
    path.write_text("{malformed", encoding="utf-8")
    assert progress.load_attempts(path) == []
    assert progress.load_companion_points(path) == 0


def test_unreadable_progress_is_not_uploaded_or_hidden_from_school_views(tmp_path, monkeypatch):
    _app()
    from aetherlab.services import leaderboard_client
    from aetherlab.services.student_profiles import StudentProfileStore
    from aetherlab.ui.leaderboard_dialog import LeaderboardDialog
    from aetherlab.ui.teacher_review_dialog import TeacherReviewDialog

    store = StudentProfileStore(tmp_path)
    profile = store.update_profile(store.active_profile().id, first_name="Student", last_name="One", username="student", school_id="school")
    _seed(profile.progress_path)
    teacher = TeacherReviewDialog(store, profile)
    ranking = LeaderboardDialog(store, profile)
    entries = list(teacher.entries), list(ranking.entries)
    with monkeypatch.context() as patch:
        _refuse(patch, profile.progress_path)
        patch.setattr(leaderboard_client, "_request_json", lambda *args: pytest.fail("unreadable scores must not be uploaded"))
        with pytest.raises(PermissionError):
            leaderboard_client.sync_school_leaderboard("http://127.0.0.1:8765", profile)
        assert not teacher._reload()
        assert not ranking._show_local_ranking()
        assert teacher.entries == entries[0] and ranking.entries == entries[1]
        assert teacher.status.text() and ranking.status.text()
    teacher.close()
    ranking.close()


def test_student_views_read_one_consistent_file_per_refresh(tmp_path, monkeypatch):
    _app()
    from aetherlab.ui.student_views import ProgressOverview, StudentDashboard, TopicCatalogView

    path = tmp_path / "consistent.json"
    _seed(path)
    views = [StudentDashboard(path), TopicCatalogView(path), ProgressOverview(path)]
    original = Path.read_text
    reads = []
    def read(target, *args, **kwargs):
        if target == path:
            reads.append(target)
        return original(target, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", read)
    for view in views:
        reads.clear()
        view.refresh()
        assert reads == [path]
        view.close()


def test_sync_progress_error_has_local_diagnosis_and_never_makes_request(tmp_path, monkeypatch):
    _app()
    from aetherlab.services import leaderboard_client
    from aetherlab.services.student_profiles import StudentProfileStore
    from aetherlab.ui.leaderboard_dialog import LeaderboardDialog, _SyncWorker

    store = StudentProfileStore(tmp_path)
    profile = store.update_profile("default", first_name="Student", last_name="One", username="student", school_id="school")
    _seed(profile.progress_path)
    for language in ("kk", "ru", "en"):
        dialog = LeaderboardDialog(store, profile, language)
        before = list(dialog.entries)
        worker = _SyncWorker("http://127.0.0.1:8765", profile)
        messages = []
        worker.failed.connect(messages.append)
        worker.failed.connect(dialog._sync_failed)
        with monkeypatch.context() as patch:
            _refuse(patch, profile.progress_path)
            patch.setattr(leaderboard_client, "_request_json", lambda *args: pytest.fail("must not send unreadable history"))
            worker.run()
        assert messages == ["local_read_error"]
        assert dialog.status.text() == dialog.text["local_read_error"]
        assert dialog.entries == before
        dialog.close()


def test_topic_unknown_state_keeps_learning_actions_and_search(tmp_path, monkeypatch):
    _app()
    from aetherlab.ui.student_views import TopicCatalogView

    path = tmp_path / "topic-unknown.json"
    _seed(path)
    with monkeypatch.context() as patch:
        _refuse(patch, path)
        view = TopicCatalogView(path, language="en")
    assert len(view.cards) == 25
    for card, _, _ in view.cards:
        assert card.findChild(QtWidgets.QLabel, "TopicMasteryStatus").text() == view.progress_notice.copy["unknown"]
        assert not any(bar.isVisibleTo(card) for bar in card.findChildren(QtWidgets.QProgressBar))
        assert all(button.isEnabled() for button in card.findChildren(QtWidgets.QPushButton))
    view.search.setText("kinematics")
    assert view.result_count.text() == "1 / 25 topics"
    view.progress_notice.retry.click()
    assert view.filter.isEnabled()
    assert not view.progress_notice.status.text()
    view.close()
