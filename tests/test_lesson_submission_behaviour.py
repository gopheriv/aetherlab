"""Actual Learn controls with owned profiles and controlled lesson results."""
from __future__ import annotations

import runpy
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UI = runpy.run_path(str(ROOT / "tests/test_command_bar_behaviour.py"))
QtCore, QtWidgets, QtTest = UI["QtCore"], UI["QtWidgets"], UI["QtTest"]


class ControlledLessonWorker(QtCore.QObject):
    progress = QtCore.pyqtSignal(str, int, int)
    lesson_ready = QtCore.pyqtSignal(object)
    failure = QtCore.pyqtSignal(object)
    finished = QtCore.pyqtSignal()

    def __init__(self, topic, settings, **options):
        super().__init__()
        self.topic, self.settings, self.options = topic, settings, options
        self.running = False
        self.deleted_requested = False
        self._cancel = threading.Event()
        self.cancel_calls = 0

    def start(self): self.running = True
    def isRunning(self): return self.running
    def cancel(self):
        self.cancel_calls += 1
        self._cancel.set()
    def wait(self, timeout): return not self.running
    def finish(self):
        self.running = False
        self.finished.emit()
    def deleteLater(self):
        self.deleted_requested = True
        super().deleteLater()


def _window(tmp_path, monkeypatch, language):
    module, window, pipelines = UI["_window"](tmp_path, monkeypatch, language)
    lessons = []
    def factory(*args, **options):
        worker = ControlledLessonWorker(*args, **options)
        lessons.append(worker)
        return worker
    monkeypatch.setattr(module, "LessonWorker", factory)
    return module, window, pipelines, lessons


def _close(window, pipelines, lessons):
    for worker in lessons:
        worker.running = False
    window.lesson_worker = None
    UI["_close"](window, pipelines)


def _bundle(status="cancelled", video_path="", topic="owned current lesson"):
    from aetherlab.core.models import LessonBundle
    from aetherlab.services.lesson_planner import _template_lesson

    return LessonBundle(plan=_template_lesson(topic, "high_school"), status=status, video_path=video_path)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_learn_quota_storage_refusal_keeps_exact_topic_and_retry(language, tmp_path, monkeypatch):
    from aetherlab.services import ai_help_quota

    _, window, pipelines, lessons = _window(tmp_path, monkeypatch, language)
    draft = "  Үдеу: keep this exact topic  "
    try:
        window.command_bar.input.setText(draft)
        with monkeypatch.context() as patch:
            def refused(*args, **kwargs): raise PermissionError("Owned allowance storage refusal")
            patch.setattr(ai_help_quota, "consume_ai_help", refused)
            QtTest.QTest.mouseClick(window.command_bar.learn_button, QtCore.Qt.MouseButton.LeftButton)
        assert not lessons
        assert window.command_bar.input.text() == draft
        assert window._update_ai_help_quota()
        QtTest.QTest.mouseClick(window.command_bar.learn_button, QtCore.Qt.MouseButton.LeftButton)
        assert len(lessons) == 1 and lessons[0].topic == draft.strip()
        assert window.command_bar.input.text() == ""
    finally: _close(window, pipelines, lessons)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_learn_handoff_keeps_language_quality_and_voice(language, tmp_path, monkeypatch):
    _, window, pipelines, lessons = _window(tmp_path, monkeypatch, language)
    try:
        window.command_bar.set_quality("h")
        window.command_bar._narration.setChecked(False)
        window.command_bar.input.setText("  own lesson  ")
        QtTest.QTest.mouseClick(window.command_bar.learn_button, QtCore.Qt.MouseButton.LeftButton)
        assert len(lessons) == 1 and lessons[0].topic == "own lesson"
        assert lessons[0].options == {"audience": "high_school", "language": language, "quality": "h", "regenerate": False}
        assert not lessons[0].settings.narration_enabled
        assert window.command_bar._busy and window.command_bar.input.text() == ""
    finally: _close(window, pipelines, lessons)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_lesson_failure_recovers_its_topic_after_a_previous_solve(language, tmp_path, monkeypatch):
    from aetherlab.core.models import PipelineError

    _, window, pipelines, lessons = _window(tmp_path, monkeypatch, language)
    draft = "  current lesson — үдеу  "
    try:
        window.start_pipeline("previous solve question")
        pipelines[-1].finish()
        window.command_bar.input.setText(draft)
        window.command_bar._learn()
        lessons[-1].failure.emit(PipelineError("lesson", "Owned lesson failure", "Owned details"))
        lessons[-1].finish()
        assert window.command_bar.input.text() == draft
        assert window.command_bar.input.isEnabled()
        assert window.focusWidget() is window.command_bar.input
    finally: _close(window, pipelines, lessons)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_first_cancelled_lesson_returns_to_empty_page_with_topic(language, tmp_path, monkeypatch):
    module, window, pipelines, lessons = _window(tmp_path, monkeypatch, language)
    draft = "  retry unfinished lesson  "
    try:
        window.command_bar.input.setText(draft)
        window.command_bar._learn()
        window._cancel_pipeline()
        lessons[-1].lesson_ready.emit(_bundle())
        lessons[-1].finish()
        assert window._workspace.currentIndex() == module.PAGE_EMPTY
        assert getattr(window, "_last_lesson", None) is None
        assert window.command_bar.input.text() == draft
        assert not window.stepper._cancellable
        assert window.simulation_panel._stack.currentWidget() is not window.simulation_panel._loading
        assert window.statusBar().currentMessage() == {
            "kk": "Сабақ тоқтатылды.", "ru": "Создание урока отменено.", "en": "Lesson cancelled."}[language]
    finally: _close(window, pipelines, lessons)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_rejected_second_learn_keeps_draft_and_allowance(language, tmp_path, monkeypatch):
    from aetherlab.services.ai_help_quota import remaining_ai_help

    _, window, pipelines, lessons = _window(tmp_path, monkeypatch, language)
    try:
        window.start_lesson("first lesson")
        lessons[0].lesson_ready.emit(_bundle(status="planned"))
        # The result can arrive before the actual worker's finished signal.
        assert lessons[0].isRunning() and window.command_bar._busy
        before = remaining_ai_help(window.active_student_profile.ai_help_quota_path)
        draft = "  a second lesson topic  "
        window.command_bar.input.setText(draft)
        window.command_bar._learn()
        assert len(lessons) == 1 and window.command_bar.input.text() == draft
        assert remaining_ai_help(window.active_student_profile.ai_help_quota_path) == before
        lessons[0].finish()
        assert window.command_bar.input.text() == draft
    finally: _close(window, pipelines, lessons)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("terminal", (
    "planned", "rendered", "planning_error", "offline_practice_available",
    "cancelled_empty", "cancelled_video", "failure",
))
def test_lesson_terminal_keeps_controls_busy_until_finished(language, terminal, tmp_path, monkeypatch):
    from aetherlab.core.models import PipelineError
    from aetherlab.services.ai_help_quota import remaining_ai_help

    _, window, pipelines, lessons = _window(tmp_path, monkeypatch, language)
    draft = "  own lesson topic  "
    try:
        monkeypatch.setattr(window.lesson_view, "set_video", lambda _path: None)
        window.command_bar.input.setText(draft)
        window.command_bar._learn()
        worker = lessons[-1]
        allowance = remaining_ai_help(window.active_student_profile.ai_help_quota_path)
        if terminal == "failure":
            worker.failure.emit(PipelineError("lesson", "Owned failure"))
        else:
            cancelled = terminal.startswith("cancelled")
            if cancelled:
                window._cancel_pipeline()
            bundle = _bundle(status="cancelled" if cancelled else terminal,
                video_path=str(tmp_path / "owned.mp4") if terminal in {"rendered", "cancelled_video"} else "")
            worker.lesson_ready.emit(bundle)
        assert worker.isRunning()
        assert window.command_bar._busy, "Terminal result must not advertise idle before worker cleanup"
        assert not window.command_bar.input.isEnabled()
        assert window.command_bar.run_button.isHidden() and window.command_bar.learn_button.isHidden()
        assert window.command_bar.practice_button.isHidden()
        assert not window.command_bar.cancel_button.isEnabled()
        assert not window.stepper._cancellable
        before = (window.statusBar().currentMessage(), worker.cancel_calls)
        # Escape/direct cancellation cannot turn a completed result into cancel.
        window._cancel_pipeline()
        assert (window.statusBar().currentMessage(), worker.cancel_calls) == before
        assert remaining_ai_help(window.active_student_profile.ai_help_quota_path) == allowance
        worker.finish()
        assert not window.command_bar._busy and window.command_bar.input.isEnabled()
        assert window.command_bar.cancel_button.isEnabled()
        assert not window.command_bar.run_button.isHidden() and not window.command_bar.learn_button.isHidden()
        if terminal == "failure" or terminal.startswith("cancelled"):
            assert window.command_bar.input.text() == draft
        # A new lesson must get a usable Cancel control, not inherit disabled state.
        window.start_lesson("next lesson")
        assert len(lessons) == 2 and window.command_bar.cancel_button.isEnabled()
    finally: _close(window, pipelines, lessons)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_lesson_cancel_is_requested_once_and_controls_wait_for_cleanup(language, tmp_path, monkeypatch):
    _, window, pipelines, lessons = _window(tmp_path, monkeypatch, language)
    try:
        window.start_lesson("cancel once")
        worker = lessons[-1]
        window._cancel_pipeline()
        assert window.command_bar._busy and not window.command_bar.input.isEnabled()
        assert not window.command_bar.cancel_button.isEnabled()
        assert not window.stepper._cancellable
        assert worker.cancel_calls == 1
        window._cancel_pipeline()
        QtTest.QTest.mouseClick(window.command_bar.cancel_button, QtCore.Qt.MouseButton.LeftButton)
        assert worker.cancel_calls == 1
        worker.lesson_ready.emit(_bundle())
        assert window.command_bar._busy
        worker.finish()
        assert not window.command_bar._busy
    finally: _close(window, pipelines, lessons)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_real_lesson_qthread_keeps_busy_after_result_until_cleanup_finishes(language, tmp_path, monkeypatch):
    module, window, pipelines, lessons = _window(tmp_path, monkeypatch, language)
    produced, release = threading.Event(), threading.Event()
    class GatedLessonWorker(QtCore.QThread):
        progress = QtCore.pyqtSignal(str, int, int)
        lesson_ready = QtCore.pyqtSignal(object)
        failure = QtCore.pyqtSignal(object)
        def __init__(self, *args, **kwargs):
            super().__init__()
            self._cancel = threading.Event()
        def cancel(self): self._cancel.set()
        def run(self):
            self.lesson_ready.emit(_bundle(status="planned"))
            produced.set()
            release.wait(5)
    monkeypatch.setattr(module, "LessonWorker", GatedLessonWorker)
    worker = None
    try:
        window.start_lesson("real cleanup barrier")
        worker = window.lesson_worker
        assert produced.wait(2)
        for _ in range(100):
            UI["_app"]().processEvents()
            if getattr(window, "_last_lesson", None) is not None:
                break
            QtTest.QTest.qWait(5)
        assert getattr(window, "_last_lesson", None) is not None
        assert worker.isRunning() and window.command_bar._busy
        assert not window.command_bar.input.isEnabled()
        release.set()
        assert worker.wait(2000)
        for _ in range(100):
            UI["_app"]().processEvents()
            if not window.command_bar._busy:
                break
            QtTest.QTest.qWait(5)
        assert not window.command_bar._busy and window.command_bar.input.isEnabled()
    finally:
        release.set()
        if worker is not None: worker.wait(2000)
        _close(window, pipelines, lessons)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_learn_after_deleted_solve_worker_still_starts(language, tmp_path, monkeypatch):
    from PyQt6 import sip
    from aetherlab.core.models import ProblemRequest
    from aetherlab.ui.workers import PipelineWorker

    _, window, pipelines, lessons = _window(tmp_path, monkeypatch, language)
    try:
        old = PipelineWorker(ProblemRequest("old deleted solve"), window.settings)
        window.worker = old
        sip.delete(old)
        window.command_bar.input.setText("new lesson after deleted worker")
        window.command_bar._learn()
        assert len(lessons) == 1 and lessons[0].topic == "new lesson after deleted worker"
        assert window.worker is None
    finally: _close(window, pipelines, lessons)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_empty_cancelled_lesson_preserves_previous_completed_lesson(language, tmp_path, monkeypatch):
    module, window, pipelines, lessons = _window(tmp_path, monkeypatch, language)
    previous = _bundle(status="planned", topic="owned previous lesson")
    try:
        window.on_lesson_ready(previous)
        assert window._last_lesson is previous
        window.start_lesson("next topic")
        window._cancel_pipeline()
        lessons[-1].lesson_ready.emit(_bundle())
        lessons[-1].finish()
        assert window._last_lesson is previous
        assert window._workspace.currentIndex() == module.PAGE_LESSON
        assert window.lesson_view._outline.count() == len(previous.plan.chapters)
    finally: _close(window, pipelines, lessons)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("terminal", ("failure", "cancelled"))
def test_lesson_recovery_preserves_a_newer_draft(language, terminal, tmp_path, monkeypatch):
    from aetherlab.core.models import PipelineError

    _, window, pipelines, lessons = _window(tmp_path, monkeypatch, language)
    try:
        window.command_bar.input.setText("original lesson topic")
        window.command_bar._learn()
        window.command_bar.input.setText("a newer question")
        if terminal == "failure":
            lessons[-1].failure.emit(PipelineError("lesson", "Owned failure"))
        else:
            window._cancel_pipeline()
            lessons[-1].lesson_ready.emit(_bundle())
        lessons[-1].finish()
        assert window.command_bar.input.text() == "a newer question"
    finally: _close(window, pipelines, lessons)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_cancelled_lesson_with_video_keeps_its_partial_route(language, tmp_path, monkeypatch):
    module, window, pipelines, lessons = _window(tmp_path, monkeypatch, language)
    displayed = []
    try:
        monkeypatch.setattr(window.lesson_view, "set_video", displayed.append)
        video = tmp_path / "owned-partial.mp4"
        video.write_bytes(b"owned routing fixture, not decoder evidence")
        partial = _bundle(video_path=str(video))
        window.start_lesson("partial lesson")
        window._cancel_pipeline()
        lessons[-1].lesson_ready.emit(partial)
        lessons[-1].finish()
        assert window._last_lesson is partial
        assert displayed == [partial.video_path]
        assert window._workspace.currentIndex() == module.PAGE_LESSON
    finally: _close(window, pipelines, lessons)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_failed_lesson_rejects_late_progress_and_ready(language, tmp_path, monkeypatch):
    from aetherlab.core.models import PipelineError

    _, window, pipelines, lessons = _window(tmp_path, monkeypatch, language)
    try:
        window.start_lesson("failed lesson")
        worker = lessons[-1]
        worker.failure.emit(PipelineError("lesson", "Owned terminal failure"))
        assert window.stepper._current_stage >= 0
        assert window.stepper._statuses[window.stepper._current_stage] == "error"
        assert not window.stepper._pulse_timer.isActive()
        before = (window.statusBar().currentMessage(), window._workspace.currentIndex(), window.toast._message.text())
        worker.progress.emit("late lesson progress", 1, 4)
        worker.lesson_ready.emit(_bundle(status="planned"))
        worker.finish()
        assert (window.statusBar().currentMessage(), window._workspace.currentIndex(), window.toast._message.text()) == before
    finally: _close(window, pipelines, lessons)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_cancelled_lesson_ignores_late_progress_until_partial_result(language, tmp_path, monkeypatch):
    _, window, pipelines, lessons = _window(tmp_path, monkeypatch, language)
    try:
        window.start_lesson("cancelled lesson")
        window._cancel_pipeline()
        before = window.statusBar().currentMessage()
        lessons[-1].progress.emit("late progress", 2, 4)
        assert window.statusBar().currentMessage() == before
        lessons[-1].lesson_ready.emit(_bundle())
        lessons[-1].finish()
    finally: _close(window, pipelines, lessons)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_queued_old_lesson_cannot_replace_a_new_lesson(language, tmp_path, monkeypatch):
    _, window, pipelines, lessons = _window(tmp_path, monkeypatch, language)
    try:
        window.start_lesson("old lesson")
        old = lessons[-1]
        class Emitter(QtCore.QThread):
            def run(self):
                old.running = False
                old.progress.emit("old progress", 1, 4)
                old.lesson_ready.emit(_bundle(status="planned"))
                old.finished.emit()
        emitter = Emitter()
        emitter.start()
        assert emitter.wait(2000)
        window.start_lesson("new lesson")
        fresh = lessons[-1]
        UI["_app"]().processEvents()
        assert window.lesson_worker is fresh and fresh is not old
        assert window.command_bar._busy and window.running_view._detail.text() == "new lesson"
        assert old.deleted_requested
    finally: _close(window, pipelines, lessons)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_deleted_lesson_wrapper_allows_another_lesson(language, tmp_path, monkeypatch):
    from PyQt6 import sip
    from aetherlab.ui.workers import LessonWorker

    _, window, pipelines, lessons = _window(tmp_path, monkeypatch, language)
    try:
        old = LessonWorker("old lesson", window.settings)
        window.lesson_worker = old
        sip.delete(old)
        window.start_lesson("new lesson")
        assert len(lessons) == 1 and window.lesson_worker is lessons[0]
    finally: _close(window, pipelines, lessons)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_solve_during_lesson_cleanup_does_not_charge_or_start(language, tmp_path, monkeypatch):
    from aetherlab.services.ai_help_quota import remaining_ai_help

    _, window, pipelines, lessons = _window(tmp_path, monkeypatch, language)
    try:
        window.start_lesson("running lesson")
        lessons[-1].lesson_ready.emit(_bundle(status="planned"))
        before = remaining_ai_help(window.active_student_profile.ai_help_quota_path)
        window.start_pipeline("overlapping solve")
        assert not pipelines and len(lessons) == 1
        assert remaining_ai_help(window.active_student_profile.ai_help_quota_path) == before
    finally: _close(window, pipelines, lessons)
