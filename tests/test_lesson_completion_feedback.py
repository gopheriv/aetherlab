"""Lesson-result copy and media ownership, with a controlled player offscreen."""
from __future__ import annotations

import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LESSON = runpy.run_path(str(ROOT / "tests/test_lesson_submission_behaviour.py"))
QtCore, QtWidgets = LESSON["QtCore"], LESSON["QtWidgets"]

PREFIXES = {
    "kk": {"ready": "Сабақтың бейнесі дайын", "materials": "Сабақ материалдары дайын",
           "incomplete": "Сабақ аяқталмады", "failed": "Сабақты жасау сәтсіз аяқталды",
           "missing": "Сабақтың бейнефайлы қолжетімсіз", "planning": "Сабақ жоспары жасалмады",
           "offline": "Офлайн жаттығу қолжетімді", "unknown": "Сабақтың күйі расталмады"},
    "ru": {"ready": "Видео урока готово", "materials": "Материалы урока готовы",
           "incomplete": "Урок не завершён", "failed": "Не удалось создать урок",
           "missing": "Видеофайл урока недоступен", "planning": "Не удалось составить план урока",
           "offline": "Доступна офлайн-практика", "unknown": "Состояние урока не подтверждено"},
    "en": {"ready": "Lesson video is ready", "materials": "Lesson materials are ready",
           "incomplete": "Lesson is incomplete", "failed": "Could not create the lesson",
           "missing": "The lesson video file is unavailable", "planning": "Could not plan the lesson",
           "offline": "Offline practice is available", "unknown": "Lesson status is unconfirmed"},
}
OUTCOMES = {
    "planned": ("planned", "info", "materials"),
    "rendering": ("rendering", "warning", "incomplete"),
    "error": ("error", "error", "failed"),
    "assembled_missing": ("assembled", "warning", "missing"),
    "assembled_empty": ("assembled", "warning", "missing"),
    "assembled_file": ("assembled", "success", "ready"),
    "planning_error": ("planning_error", "warning", "planning"),
    "offline_practice_available": ("offline_practice_available", "warning", "offline"),
    "unknown": ("owned-unrecognized-status", "warning", "unknown"),
}


class OwnedPlayer:
    def __init__(self):
        self.current_source = QtCore.QUrl.fromLocalFile(str(ROOT / "tmp/owned-previous.mp4"))
        self.stops = 0
    def stop(self): self.stops += 1
    def setSource(self, source): self.current_source = source
    def source(self): return self.current_source


def _player(view, monkeypatch):
    player = OwnedPlayer()
    monkeypatch.setattr(view, "_player", player)
    if not hasattr(view, "_video_empty_overlay"):
        view._video_empty_overlay = QtWidgets.QLabel(view)
    return player


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("outcome", tuple(OUTCOMES))
def test_lesson_completion_feedback_matches_available_result(language, outcome, tmp_path, monkeypatch):
    _, window, pipelines, lessons = LESSON["_window"](tmp_path, monkeypatch, language)
    player = _player(window.lesson_view, monkeypatch)
    status, kind, prefix = OUTCOMES[outcome]
    video = tmp_path / "owned-result.mp4"
    if outcome == "assembled_file":
        video.write_bytes(b"controlled media routing fixture, not decoder evidence")
    elif outcome == "assembled_empty":
        video.touch()
    bundle = LESSON["_bundle"](status=status, video_path=str(video) if outcome.startswith("assembled") else "")
    bundle.plan.language = language
    bundle.plan.title = "Owned lesson title"
    if outcome in {"planning_error", "offline_practice_available"}:
        bundle.plan.chapters[0].goal = "Owned original diagnostic"
    try:
        draft = "  owned topic  "
        window.command_bar.input.setText(draft)
        window.command_bar._learn()
        lessons[-1].lesson_ready.emit(bundle)
        message = window.toast._message.text()
        assert window.toast._kind == kind
        assert message.startswith(PREFIXES[language][prefix])
        assert window.statusBar().currentMessage() == message
        if outcome in {"planning_error", "offline_practice_available"}:
            assert "Owned original diagnostic" in message
        if outcome == "unknown":
            assert status in message
        if outcome == "assembled_file":
            assert Path(player.source().toLocalFile()).resolve() == video.resolve()
            assert bundle.plan.title in message
        else:
            assert player.source().isEmpty(), "A new result must never retain the previous lesson's video"
            assert not window.lesson_view._video_empty_overlay.isHidden()
        assert window.command_bar._busy
        lessons[-1].finish()
        assert not window.command_bar._busy
        expected_draft = "" if outcome in {"planned", "assembled_file"} else draft
        assert window.command_bar.input.text() == expected_draft
        assert window.lesson_view._tabs.currentIndex() == (0 if outcome == "assembled_file" else 1)
    finally: LESSON["_close"](window, pipelines, lessons)


@pytest.mark.parametrize("path_case", ("blank", "missing", "empty", "directory", "unreadable", "file"))
def test_lesson_player_replaces_or_clears_its_previous_source(path_case, tmp_path, monkeypatch):
    _, window, pipelines, lessons = LESSON["_window"](tmp_path, monkeypatch, "en")
    player = _player(window.lesson_view, monkeypatch)
    path = tmp_path / "owned-source.mp4"
    if path_case == "empty": path.touch()
    elif path_case == "directory": path.mkdir()
    elif path_case in {"file", "unreadable"}: path.write_bytes(b"owned routing fixture")
    try:
        with monkeypatch.context() as patch:
            if path_case == "unreadable":
                def denied(*args, **kwargs): raise PermissionError("Owned metadata refusal")
                patch.setattr(Path, "stat", denied)
            window.lesson_view.set_video("" if path_case == "blank" else str(path))
        assert player.stops == 1
        if path_case == "file":
            assert Path(player.source().toLocalFile()).resolve() == path.resolve()
            assert window.lesson_view._video_empty_overlay.isHidden()
        else:
            assert player.source().isEmpty()
            assert not window.lesson_view._video_empty_overlay.isHidden()
    finally: LESSON["_close"](window, pipelines, lessons)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_empty_cancel_keeps_previous_lesson_media_and_new_plan_clears_it(language, tmp_path, monkeypatch):
    _, window, pipelines, lessons = LESSON["_window"](tmp_path, monkeypatch, language)
    player = _player(window.lesson_view, monkeypatch)
    video = tmp_path / "owned-previous.mp4"
    video.write_bytes(b"owned previous routing fixture")
    previous = LESSON["_bundle"](status="assembled", video_path=str(video))
    previous.plan.language = language
    try:
        window.on_lesson_ready(previous)
        assert Path(player.source().toLocalFile()).resolve() == video.resolve()
        window.start_lesson("cancelled topic")
        window._cancel_pipeline()
        lessons[-1].lesson_ready.emit(LESSON["_bundle"]())
        lessons[-1].finish()
        assert window._last_lesson is previous
        assert Path(player.source().toLocalFile()).resolve() == video.resolve()
        fresh = LESSON["_bundle"](status="planned", topic="different lesson")
        window.on_lesson_ready(fresh)
        assert player.source().isEmpty()
        assert window._last_lesson is fresh
    finally: LESSON["_close"](window, pipelines, lessons)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_cancelled_missing_video_keeps_previous_lesson_media(language, tmp_path, monkeypatch):
    _, window, pipelines, lessons = LESSON["_window"](tmp_path, monkeypatch, language)
    player = _player(window.lesson_view, monkeypatch)
    video = tmp_path / "owned-previous.mp4"
    video.write_bytes(b"owned previous routing fixture")
    previous = LESSON["_bundle"](status="assembled", video_path=str(video))
    previous.plan.language = language
    try:
        window.on_lesson_ready(previous)
        window.start_lesson("cancelled missing video")
        window._cancel_pipeline()
        lessons[-1].lesson_ready.emit(LESSON["_bundle"](video_path=str(tmp_path / "missing-partial.mp4")))
        lessons[-1].finish()
        assert window._last_lesson is previous
        assert Path(player.source().toLocalFile()).resolve() == video.resolve()
    finally: LESSON["_close"](window, pipelines, lessons)


def test_new_lesson_clears_the_actual_qmediaplayer_source(tmp_path, monkeypatch):
    _, window, pipelines, lessons = LESSON["_window"](tmp_path, monkeypatch, "en")
    try:
        player = window.lesson_view._player
        if player is None:
            pytest.skip("QtMultimedia is unavailable; actual player-source ownership remains unverified")
        # The real Qt URL/source state is exercised, without claiming that this
        # byte fixture is playable or asking the codec to certify a render.
        video = tmp_path / "owned-source-property.mp4"
        video.write_bytes(b"owned URL-state fixture")
        player.setSource(QtCore.QUrl.fromLocalFile(str(video)))
        assert not player.source().isEmpty()
        window.lesson_view.set_lesson(LESSON["_bundle"](status="planned"))
        assert player.source().isEmpty()
        assert player.playbackState() == player.PlaybackState.StoppedState
    finally: LESSON["_close"](window, pipelines, lessons)


@pytest.mark.parametrize("status", ("planned", "rendering", "error", "owned-unrecognized-status"))
def test_nonassembled_bundle_does_not_load_a_video_path(status, tmp_path, monkeypatch):
    _, window, pipelines, lessons = LESSON["_window"](tmp_path, monkeypatch, "en")
    player = _player(window.lesson_view, monkeypatch)
    video = tmp_path / "owned-inconsistent-video.mp4"
    video.write_bytes(b"owned inconsistent-bundle routing fixture")
    try:
        window.on_lesson_ready(LESSON["_bundle"](status=status, video_path=str(video)))
        assert player.source().isEmpty()
        assert window.lesson_view._tabs.currentIndex() == 1
        assert window.toast._kind != "success"
    finally: LESSON["_close"](window, pipelines, lessons)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_incomplete_result_retry_does_not_replace_a_newer_draft(language, tmp_path, monkeypatch):
    _, window, pipelines, lessons = LESSON["_window"](tmp_path, monkeypatch, language)
    _player(window.lesson_view, monkeypatch)
    try:
        for outcome in ("error", "rendering", "planning_error", "offline_practice_available",
                        "assembled_missing", "assembled_empty", "unknown"):
            status = OUTCOMES[outcome][0]
            window.start_lesson("original topic")
            window.command_bar.input.setText("a newer topic")
            bundle = LESSON["_bundle"](status=status)
            bundle.plan.language = language
            lessons[-1].lesson_ready.emit(bundle)
            lessons[-1].finish()
            assert window.command_bar.input.text() == "a newer topic"
    finally: LESSON["_close"](window, pipelines, lessons)
