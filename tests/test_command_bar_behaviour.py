"""Exercise actual Qt controls and worker-signal ownership on isolated profiles."""
from __future__ import annotations

import os
from dataclasses import replace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6 import QtTest, sip

from aetherlab.ui.qt_compat import QtCore, QtWidgets

_APP = None


def _app():
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    # This host opens/closes many independent windows without app.exec(). A
    # last-window Quit event must not abort a later nested QMenu.exec() loop.
    _APP.setQuitOnLastWindowClosed(False)
    if os.environ.get("PHYSLAB_REQUIRE_NATIVE_QT") == "1":
        assert _APP.platformName() == "windows", "Native acceptance requires the actual Windows Qt platform"
    return _APP


class ControlledWorker(QtCore.QObject):
    plan_ready = QtCore.pyqtSignal(object)
    solver_ready = QtCore.pyqtSignal(object)
    rag_ready = QtCore.pyqtSignal(object)
    scene_ready = QtCore.pyqtSignal(object)
    render_ready = QtCore.pyqtSignal(object)
    pipeline_finished = QtCore.pyqtSignal(object)
    failure = QtCore.pyqtSignal(object)
    status = QtCore.pyqtSignal(str)
    progress = QtCore.pyqtSignal(int, str)
    finished = QtCore.pyqtSignal()

    def __init__(self, request, settings, render_quality="l"):
        super().__init__()
        self.request, self.settings, self.render_quality = request, settings, render_quality
        self.running = self._cancelled = self.deleted_requested = False

    def start(self): self.running = True
    def isRunning(self): return self.running
    def cancel(self): self._cancelled = True
    def wait(self, timeout): return not self.running
    def finish(self):
        self.running = False
        self.finished.emit()
    def deleteLater(self):
        self.deleted_requested = True
        super().deleteLater()


def _window(tmp_path, monkeypatch, language="en", default_quality=None):
    import aetherlab.ui.main_window as module
    from aetherlab.core.settings import load_settings

    for name in tuple(os.environ):
        if name.startswith(("AETHERLAB_", "OPENAI_", "QWEN_", "DASHSCOPE_", "MANIM_", "GPT_", "CHAT_", "LLM_")):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AETHERLAB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AETHERLAB_LIBRARY_DIR", str(tmp_path / "library"))
    monkeypatch.setenv("AETHERLAB_CHROMA_PATH", str(tmp_path / "chroma"))
    monkeypatch.setenv("AETHERLAB_REFERENCE_SOURCES", str(tmp_path / "no-references"))
    monkeypatch.setenv("AETHERLAB_DISABLE_LEGACY_ENV", "1")
    monkeypatch.setenv("AETHERLAB_QWEN_AUTOLOAD", "0")
    monkeypatch.setenv("QWEN_SETTINGS_PATH", str(tmp_path / "no-qwen.json"))
    _app()
    settings = replace(load_settings(), openai_api_key=None, openai_base_url=None, web_references=False)
    # Keep the story's no-key precondition without probing a user's Ollama.
    monkeypatch.setattr(module._OllamaProbe, "run", lambda self: None)
    if default_quality is not None:
        from aetherlab.core.settings import save_app_config
        save_app_config({"default_quality": default_quality})
    created = []
    def factory(**kwargs):
        worker = ControlledWorker(**kwargs)
        created.append(worker)
        return worker
    monkeypatch.setattr(module, "PipelineWorker", factory)
    window = module.MainWindow(settings)
    window.command_bar.set_language(language)
    window.sidebar.select(4)
    window.show()
    window.activateWindow()
    window.command_bar.input.setFocus()
    _app().processEvents()
    return module, window, created


def _close(window, created):
    for worker in created:
        worker.running = False
    window.worker = None
    window.close()
    window.deleteLater()
    _app().processEvents()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("route", ("return", "run", "ctrl-return"))
def test_prompt_input_routes_once_and_preserves_unicode(route, language, tmp_path, monkeypatch):
    _, window, created = _window(tmp_path, monkeypatch, language)
    try:
        draft = "  үдеу: v₀ = 2 м/с, a = 3 м/с²  "
        window.command_bar.input.setText(draft)
        if route == "run": QtTest.QTest.mouseClick(window.command_bar.run_button, QtCore.Qt.MouseButton.LeftButton)
        else: QtTest.QTest.keyClick(window.command_bar.input, QtCore.Qt.Key.Key_Return,
            QtCore.Qt.KeyboardModifier.ControlModifier if route == "ctrl-return" else QtCore.Qt.KeyboardModifier.NoModifier)
        _app().processEvents()
        assert len(created) == 1
        assert created[0].request.prompt == draft.strip()
        assert window.command_bar.input.text() == ""
        assert not window.command_bar.input.isEnabled()
        assert window.command_bar.cancel_button.isVisibleTo(window)
    finally: _close(window, created)


def test_blank_busy_and_exhausted_quota_do_not_submit(tmp_path, monkeypatch):
    _, window, created = _window(tmp_path, monkeypatch)
    try:
        window.command_bar.input.setText("   ")
        window.command_bar._submit()
        assert not created
        window.command_bar.input.setText("keep question")
        window.command_bar.set_busy(True)
        window.command_bar._submit()
        assert not created and window.command_bar.input.text() == "keep question"
        window.command_bar.set_busy(False)
        window.command_bar.set_ai_quota(0)
        window.command_bar._submit()
        assert not created and window.command_bar.input.text() == "keep question"
        window.command_bar.set_ai_quota(None)
        window.command_bar._submit()
        assert not created and window.command_bar.input.text() == "keep question"
    finally: _close(window, created)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_quota_storage_failure_keeps_draft_and_retry_starts_once(language, tmp_path, monkeypatch):
    from aetherlab.services import ai_help_quota

    _, window, created = _window(tmp_path, monkeypatch, language)
    draft = "  Сақталатын сұрақ: v = v₀ + at  "
    try:
        window.command_bar.input.setText(draft)
        with monkeypatch.context() as patch:
            def refused(*args, **kwargs): raise PermissionError("Owned quota read/write refused")
            patch.setattr(ai_help_quota, "consume_ai_help", refused)
            window.command_bar._submit()
        assert not created
        assert window.command_bar.input.text() == draft
        assert window._update_ai_help_quota()
        window.command_bar._submit()
        assert len(created) == 1 and created[0].request.prompt == draft.strip()
        assert window.command_bar.input.text() == ""
    finally: _close(window, created)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_quality_flags_and_missing_selection_reach_actual_worker(language, tmp_path, monkeypatch):
    _, window, created = _window(tmp_path, monkeypatch, language)
    try:
        for flag in ("l", "m", "h"):
            window.command_bar.set_quality(flag)
            window.start_pipeline("quality " + flag)
            assert created[-1].render_quality == flag
            created[-1].finish()
        window.command_bar.set_quality("h")
        window.command_bar._quality.setCurrentText("unknown quality label")
        window.command_bar.set_quality("unknown-flag")
        assert window.command_bar.get_render_quality() == "h"
        window.start_pipeline("preserved quality")
        assert created[-1].render_quality == "h"
        created[-1].finish()
        window.command_bar._quality.setCurrentIndex(-1)
        assert window.command_bar.get_render_quality() == "l"
        window.start_pipeline("unselected quality fallback")
        assert created[-1].render_quality == "l"
    finally: _close(window, created)


@pytest.mark.parametrize("flag", ("l", "m", "h"))
def test_saved_default_quality_reaches_next_window_and_worker(flag, tmp_path, monkeypatch):
    _, window, created = _window(tmp_path, monkeypatch, default_quality=flag)
    try:
        assert window.command_bar.get_render_quality() == flag
        window.start_pipeline("restored quality")
        assert created[-1].render_quality == flag
    finally: _close(window, created)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_quality_labels_fit_the_styled_edit_field(language, tmp_path, monkeypatch):
    _, window, created = _window(tmp_path, monkeypatch, language)
    try:
        combo = window.command_bar._quality
        for index in range(combo.count()):
            combo.setCurrentIndex(index)
            _app().processEvents()
            option = QtWidgets.QStyleOptionComboBox()
            combo.initStyleOption(option)
            rect = combo.style().subControlRect(QtWidgets.QStyle.ComplexControl.CC_ComboBox,
                option, QtWidgets.QStyle.SubControl.SC_ComboBoxEditField, combo)
            assert option.fontMetrics.horizontalAdvance(combo.currentText()) <= rect.width(), combo.currentText()
    finally: _close(window, created)


def test_cancel_remains_busy_until_worker_finished(tmp_path, monkeypatch):
    _, window, created = _window(tmp_path, monkeypatch)
    try:
        window.start_pipeline("owned cancellation")
        worker = created[-1]
        assert all(not button.isVisibleTo(window) for button in (
            window.command_bar.run_button, window.command_bar.learn_button, window.command_bar.practice_button))
        QtTest.QTest.mouseClick(window.command_bar.cancel_button, QtCore.Qt.MouseButton.LeftButton)
        assert worker._cancelled and worker.running
        assert window.command_bar._busy and not window.command_bar.input.isEnabled()
        assert not window.command_bar.cancel_button.isEnabled()
        worker.finish()
        assert not window.command_bar._busy and window.command_bar.input.isEnabled()
        assert window.command_bar.run_button.isVisibleTo(window)
        assert window.command_bar.learn_button.isVisibleTo(window)
        assert window.command_bar.practice_button.isVisibleTo(window)
        assert not window.command_bar.cancel_button.isVisibleTo(window)
    finally: _close(window, created)


def test_cancel_restores_question_for_editing(tmp_path, monkeypatch):
    _, window, created = _window(tmp_path, monkeypatch)
    try:
        draft = "  revise acceleration question  "
        window.command_bar.input.setText(draft)
        window.command_bar._submit()
        window._cancel_pipeline()
        created[-1].finish()
        assert window.command_bar.input.text() == draft
    finally: _close(window, created)


def test_failure_restores_question_and_stops_active_timeline(tmp_path, monkeypatch):
    from aetherlab.core.models import PipelineError

    _, window, created = _window(tmp_path, monkeypatch)
    try:
        draft = "  retry this complete question  "
        window.command_bar.input.setText(draft)
        window.command_bar._submit()
        created[-1].progress.emit(60, "owned scene")
        created[-1].failure.emit(PipelineError("solver", "Owned failure", "Owned traceback"))
        created[-1].finish()
        assert window.command_bar.input.text() == draft
        assert window.stepper._statuses[window.stepper._current_stage] == "error"
        assert not window.stepper._pulse_timer.isActive()
    finally: _close(window, created)


def test_finished_cancellation_has_no_active_stage(tmp_path, monkeypatch):
    _, window, created = _window(tmp_path, monkeypatch)
    try:
        window.start_pipeline("cancelled timeline")
        created[-1].progress.emit(60, "owned scene")
        window._cancel_pipeline()
        created[-1].finish()
        assert "active" not in window.stepper._statuses
        assert window.stepper._statuses[window.stepper._current_stage] == "cancelled"
        assert not window.stepper._pulse_timer.isActive()
    finally: _close(window, created)


def test_late_progress_does_not_overwrite_cancelling_state(tmp_path, monkeypatch):
    _, window, created = _window(tmp_path, monkeypatch)
    try:
        window.start_pipeline("cancelled progress")
        window._cancel_pipeline()
        previous = window.running_view._headline.text()
        created[-1].progress.emit(90, "late progress")
        created[-1].status.emit("late provider status")
        assert window.running_view._headline.text() == previous
        assert "Cancelling" in window.statusBar().currentMessage()
    finally: _close(window, created)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_duplicate_start_preserves_worker_and_does_not_charge_again(tmp_path, monkeypatch, language):
    from aetherlab.services.ai_help_quota import remaining_ai_help
    from aetherlab.ui.main_window import _PIPELINE_COPY

    _, window, created = _window(tmp_path, monkeypatch, language)
    try:
        window.start_pipeline("first run")
        worker = created[-1]
        worker.progress.emit(60, "current progress")
        before = (window.stepper._statuses[:], window.stepper._started.copy(), window.running_view._detail.text())
        receivers = worker.receivers(worker.progress)
        remaining = remaining_ai_help(window.active_student_profile.ai_help_quota_path)
        window.start_pipeline("duplicate run")
        assert len(created) == 1 and window.worker is worker
        assert not worker._cancelled
        assert not worker.deleted_requested and worker.receivers(worker.progress) == receivers
        assert (window.stepper._statuses, window.stepper._started, window.running_view._detail.text()) == before
        assert window.statusBar().currentMessage() == _PIPELINE_COPY[language]["already_running"]
        assert remaining_ai_help(window.active_student_profile.ai_help_quota_path) == remaining
    finally: _close(window, created)


def test_cleanup_disconnects_all_signals_after_one_was_already_disconnected(tmp_path, monkeypatch):
    _, window, created = _window(tmp_path, monkeypatch)
    try:
        window.start_pipeline("old run")
        old = created[-1]
        old.running = False
        old.status.disconnect()
        window.start_pipeline("new run")
        assert old.deleted_requested
        for name in ("status", "progress", "plan_ready", "solver_ready", "rag_ready", "scene_ready",
                     "render_ready", "pipeline_finished", "failure", "finished"):
            signal = getattr(old, name)
            assert old.receivers(signal) == 0, name
    finally: _close(window, created)


def test_deleted_previous_qthread_does_not_block_a_new_run(tmp_path, monkeypatch):
    from aetherlab.core.models import ProblemRequest
    from aetherlab.ui.workers import PipelineWorker

    _, window, created = _window(tmp_path, monkeypatch)
    try:
        old = PipelineWorker(ProblemRequest("deleted previous run"), window.settings)
        window.worker = old
        sip.delete(old)
        window.start_pipeline("new run")
        assert len(created) == 1 and window.worker is created[0]
    finally: _close(window, created)


def test_queued_previous_worker_signals_cannot_change_a_new_run(tmp_path, monkeypatch):
    _, window, created = _window(tmp_path, monkeypatch)
    try:
        window.start_pipeline("old request")
        old = created[-1]
        class QueueOldSignals(QtCore.QThread):
            def run(self):
                old.running = False
                old.progress.emit(90, "old progress")
                old.status.emit("old status")
                old.finished.emit()
        emitter = QueueOldSignals()
        emitter.start()
        assert emitter.wait(3000)
        window.start_pipeline("new request")
        fresh = created[-1]
        assert fresh is not old and fresh.running
        _app().processEvents()
        assert window.worker is fresh
        assert window.command_bar._busy and not window.command_bar.input.isEnabled()
        assert window.stepper._current_stage == 0
        assert window.running_view._detail.text() == "new request"
    finally: _close(window, created)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("route", ("button", "escape", "stepper"))
def test_real_qthread_cancel_waits_for_cleanup_and_preserves_draft(route, language, tmp_path, monkeypatch):
    import threading
    from aetherlab.ui.workers import PipelineWorker
    from aetherlab.ui.main_window import _PIPELINE_COPY

    module, window, created = _window(tmp_path, monkeypatch, language)
    ready, cleaning, finish_cleanup = threading.Event(), threading.Event(), threading.Event()
    class RealControlledWorker(PipelineWorker):
        def run(self):
            ready.set()
            while not self._cancelled and not finish_cleanup.wait(0.005):
                pass
            cleaning.set()
            finish_cleanup.wait(3)
    def factory(**kwargs):
        worker = RealControlledWorker(**kwargs)
        created.append(worker)
        return worker
    monkeypatch.setattr(module, "PipelineWorker", factory)
    try:
        draft = "  үдеу: keep this question  "
        window.command_bar.input.setText(draft)
        window.command_bar._submit()
        worker = created[-1]
        assert ready.wait(1)
        if route == "button":
            QtTest.QTest.mouseClick(window.command_bar.cancel_button, QtCore.Qt.MouseButton.LeftButton)
        elif route == "escape":
            QtTest.QTest.keyClick(window, QtCore.Qt.Key.Key_Escape)
        else:
            window.stepper.repaint()
            _app().processEvents()
            assert window.stepper._cancel_rect is not None
            QtTest.QTest.mouseClick(window.stepper, QtCore.Qt.MouseButton.LeftButton,
                                   pos=window.stepper._cancel_rect.center().toPoint())
        assert cleaning.wait(1)
        assert worker.isRunning() and window.command_bar._busy
        assert window.running_view._headline.text() == _PIPELINE_COPY[language]["cancelling"]
        finish_cleanup.set()
        assert worker.wait(2000)
        _app().processEvents()
        assert not window.command_bar._busy and window.command_bar.input.isEnabled()
        assert window.command_bar.input.text() == draft
        assert window.command_bar.input.hasFocus()
        assert window.statusBar().currentMessage() == _PIPELINE_COPY[language]["cancelled"]
        assert "active" not in window.stepper._statuses
        assert not window.stepper._cancellable
        assert window.simulation_panel._stack.currentWidget() is not window.simulation_panel._loading
        assert window._workspace.currentIndex() == module.PAGE_EMPTY
    finally:
        finish_cleanup.set()
        for worker in created:
            worker.cancel()
            assert worker.wait(2000)
        _close(window, created)


def test_terminal_error_ignores_late_worker_events(tmp_path, monkeypatch):
    from aetherlab.core.models import PipelineError

    _, window, created = _window(tmp_path, monkeypatch)
    try:
        window.start_pipeline("keep failed result stable")
        worker = created[-1]
        worker.failure.emit(PipelineError("solver", "Owned failure"))
        before = (window.stepper._statuses[:], window.statusBar().currentMessage())
        worker.progress.emit(90, "late progress")
        worker.status.emit("late status")
        assert (window.stepper._statuses, window.statusBar().currentMessage()) == before
        worker.finish()
        worker.progress.emit(100, "after finished")
        assert (window.stepper._statuses, window.statusBar().currentMessage()) == before
    finally: _close(window, created)


def test_recovery_keeps_a_newer_draft_instead_of_replacing_it(tmp_path, monkeypatch):
    _, window, created = _window(tmp_path, monkeypatch)
    try:
        window.command_bar.input.setText("original question")
        window.command_bar._submit()
        window.command_bar.input.setText("a newer draft")
        window._cancel_pipeline()
        created[-1].finish()
        assert window.command_bar.input.text() == "a newer draft"
    finally: _close(window, created)


def test_examples_menu_selects_full_prompt_and_escape_preserves_input(tmp_path, monkeypatch):
    # A fresh Qt host isolates this nested popup loop from modal/quit events
    # left by other test modules. The child runs every assertion below against
    # the real MainWindow, real QMenu.exec() and real key events.
    if os.environ.get("PHYSLAB_OWNED_MENU_CHILD") != "1":
        import subprocess
        import sys
        from pathlib import Path
        from aetherlab.core.proc import subprocess_kwargs

        env = {**os.environ, "PHYSLAB_OWNED_MENU_CHILD": "1"}
        program = """
import runpy,sys
from pathlib import Path
import pytest
scope=runpy.run_path(sys.argv[1])
with pytest.MonkeyPatch.context() as patch:
    scope['test_examples_menu_selects_full_prompt_and_escape_preserves_input'](Path(sys.argv[2]),patch)
"""
        completed = subprocess.run([sys.executable, "-c", program, str(Path(__file__).resolve()), str(tmp_path)],
                                   env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   timeout=45, **subprocess_kwargs())
        (tmp_path / "owned-menu-child.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
        assert completed.returncode == 0, completed.stdout + completed.stderr
        return
    from aetherlab.ui.command_bar import EXAMPLE_PROMPTS

    _, window, created = _window(tmp_path, monkeypatch)
    events = []
    real_exec = QtWidgets.QMenu.exec
    actions = iter((*range(len(EXAMPLE_PROMPTS)), None))
    def execute_owned_menu(menu, *args):
        mode = next(actions)
        assert len(EXAMPLE_PROMPTS) == 10
        assert [action.text() for action in menu.actions()] == [
            prompt[:64] + "…" if len(prompt) > 64 else prompt for prompt in EXAMPLE_PROMPTS]
        assert args[0] == window.command_bar._examples_btn.mapToGlobal(
            QtCore.QPoint(0, -menu.sizeHint().height() - 6))
        action_timer, safety_timer = QtCore.QTimer(menu), QtCore.QTimer(menu)
        action_timer.setSingleShot(True)
        safety_timer.setSingleShot(True)
        def interact():
            if not menu.isVisible():
                events.append("not visible")
                menu.close()
                return
            if mode is not None:
                events.append(len(menu.actions()))
                menu.setActiveAction(menu.actions()[mode])
                QtTest.QTest.keyClick(menu, QtCore.Qt.Key.Key_Return)
            else:
                QtTest.QTest.keyClick(menu, QtCore.Qt.Key.Key_Escape)
        action_timer.timeout.connect(interact)
        safety_timer.timeout.connect(menu.close)
        action_timer.start(20)
        safety_timer.start(1500)
        try:
            return real_exec(menu, *args)
        finally:
            action_timer.stop()
            safety_timer.stop()
    # Retain the real nested menu event loop. Target that exact owned menu,
    # rather than racing QApplication.activePopupWidget() in a shared suite.
    monkeypatch.setattr(QtWidgets.QMenu, "exec", execute_owned_menu)
    try:
        for prompt in EXAMPLE_PROMPTS:
            window.command_bar._examples_btn.click()
            _app().processEvents()
            assert window.command_bar.input.text() == prompt and not created
        assert events == [len(EXAMPLE_PROMPTS)] * len(EXAMPLE_PROMPTS)
        # The offscreen popup can leave the whole window inactive. Its owned
        # focus target still proves where typing returns on reactivation;
        # the Windows-platform repeat also checks actual keyboard focus.
        assert window.focusWidget() is window.command_bar.input and not created
        if _app().platformName() == "windows":
            assert window.command_bar.input.hasFocus()
        window.command_bar._examples_btn.click()
        assert window.command_bar.input.text() == EXAMPLE_PROMPTS[-1] and not created
    finally: _close(window, created)


def test_progress_stages_complete_and_next_run_resets_timing(tmp_path, monkeypatch):
    _, window, created = _window(tmp_path, monkeypatch)
    try:
        window.command_bar.input.setText("first progress question")
        window.command_bar._submit()
        for percent, expected_stage in ((10, 0), (40, 1), (60, 2), (80, 3), (99, 3)):
            created[-1].progress.emit(percent, str(percent))
            assert window.stepper._current_stage == expected_stage
            assert window.stepper._statuses[expected_stage] == "active"
            assert all(status == "complete" for status in window.stepper._statuses[:expected_stage])
        created[-1].progress.emit(100, "complete")
        assert all(status == "complete" for status in window.stepper._statuses)
        assert not window.stepper._pulse_timer.isActive()
        created[-1].finish()
        assert not window.command_bar._busy and window.command_bar.input.isEnabled()
        assert window.command_bar.input.text() == ""
        window.command_bar.input.setText("second progress question")
        window.command_bar._submit()
        assert window.stepper._statuses == ["active", "pending", "pending", "pending"]
        assert not window.stepper._elapsed
        assert set(window.stepper._started) == {0}
    finally: _close(window, created)


def test_all_worker_data_signals_route_once_and_stop_after_cancel(tmp_path, monkeypatch):
    _, window, created = _window(tmp_path, monkeypatch)
    deliveries = []
    names = ("plan", "solver", "rag", "scene", "render", "pipeline_finished")
    handlers = ("on_plan_ready", "on_solver_ready", "on_rag_ready", "on_scene_ready", "on_render_ready", "on_pipeline_finished")
    for name, handler in zip(names, handlers):
        monkeypatch.setattr(window, handler, lambda value, name=name: deliveries.append((name, value)))
    try:
        window.start_pipeline("signal owner")
        worker = created[-1]
        values = [object() for _ in names]
        signals = (worker.plan_ready, worker.solver_ready, worker.rag_ready,
                   worker.scene_ready, worker.render_ready, worker.pipeline_finished)
        for signal, value in zip(signals, values):
            signal.emit(value)
        assert deliveries == list(zip(names, values))
        window._cancel_pipeline()
        for signal, value in zip(signals, values):
            signal.emit(value)
        assert deliveries == list(zip(names, values))
        worker.finish()
        for signal, value in zip(signals, values):
            signal.emit(value)
        assert deliveries == list(zip(names, values))
    finally: _close(window, created)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("stage", ("pipeline", "solver", "rag", "scene", "render", "planner", "lesson", "owned-unknown-stage"))
def test_failure_context_is_localized_and_preserves_original_diagnostics(stage, language, tmp_path, monkeypatch):
    from aetherlab.core.models import PipelineError

    _, window, created = _window(tmp_path, monkeypatch, language)
    labels = {
        "kk": {"pipeline": "Өңдеу", "solver": "Шешу", "rag": "Іздеу", "scene": "Сахна", "render": "Рендер", "planner": "Жоспарлау", "lesson": "Сабақ"},
        "ru": {"pipeline": "Обработка", "solver": "Решение", "rag": "Поиск", "scene": "Сцена", "render": "Рендер", "planner": "Планирование", "lesson": "Урок"},
        "en": {"pipeline": "Processing", "solver": "Solve", "rag": "Search", "scene": "Scene", "render": "Render", "planner": "Planning", "lesson": "Lesson"},
    }
    label = labels[language].get(stage, stage)
    expected = {
        "kk": f"«{label}» кезеңіндегі қате: Owned diagnostic",
        "ru": f"Ошибка на этапе «{label}»: Owned diagnostic",
        "en": f"{label} failed: Owned diagnostic",
    }[language]
    try:
        window.start_pipeline("recoverable question")
        created[-1].failure.emit(PipelineError(stage, "Owned diagnostic", "Original owned traceback"))
        assert window.statusBar().currentMessage() == expected
        assert window.toast._message.text() == expected
        assert window.simulation_panel._error_traceback == "Original owned traceback"
        assert label in window.simulation_panel._error_text.text()
        assert "Owned diagnostic" in window.simulation_panel._error_text.text()
        assert window.command_bar.input.text() == "recoverable question"
        created[-1].finish()
        assert not window.command_bar._busy
    finally: _close(window, created)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("has_result", (False, True))
def test_failure_details_and_retry_use_recoverable_page(language, has_result, tmp_path, monkeypatch):
    from aetherlab.core.models import PipelineError

    module, window, created = _window(tmp_path, monkeypatch, language)
    detail = None
    try:
        window._has_result = has_result
        window.command_bar.input.setText("  retry exact question  ")
        window.command_bar._submit()
        worker = created[-1]
        worker.failure.emit(PipelineError("solver", "Owned failure", "Owned original traceback"))
        assert window._workspace.currentIndex() == (module.PAGE_SOLVE if has_result else module.PAGE_EMPTY)
        assert window.simulation_panel._stack.currentWidget() is not window.simulation_panel._loading
        assert not window.stepper._cancellable and not window.stepper._pulse_timer.isActive()
        assert window.toast._details_btn.isVisibleTo(window)
        QtTest.QTest.mouseClick(window.toast._details_btn, QtCore.Qt.MouseButton.LeftButton)
        _app().processEvents()
        detail = window.simulation_panel._detail_window
        assert detail.isVisible() and detail.isReadOnly()
        assert detail.toPlainText() == "Owned original traceback"
        detail.close()
        _app().processEvents()
        worker.finish()
        assert window.command_bar.input.text() == "  retry exact question  "
        QtTest.QTest.mouseClick(window.command_bar.run_button, QtCore.Qt.MouseButton.LeftButton)
        assert len(created) == 2 and created[-1].request.prompt == "retry exact question"
        assert window.simulation_panel._error_traceback == ""
        assert not window.simulation_panel._error_banner.isVisibleTo(window)
    finally:
        if detail is not None and not sip.isdeleted(detail):
            detail.close()
        _close(window, created)


@pytest.mark.parametrize("terminal", ("complete", "error", "cancelled"))
def test_terminal_stepper_freezes_elapsed_and_reset_clears_it(terminal, tmp_path, monkeypatch):
    import time

    _, window, created = _window(tmp_path, monkeypatch)
    clock = [100.0]
    try:
        with monkeypatch.context() as patch:
            patch.setattr(time, "monotonic", lambda: clock[0])
            window.stepper.reset()
            window.stepper.set_stage(0)
            clock[0] = 103.25
            window.stepper.set_stage(0, terminal)
            assert window.stepper._elapsed == {0: 3.25}
            assert not window.stepper._pulse_timer.isActive()
            clock[0] = 500.0
            window.stepper.repaint()
            assert window.stepper._elapsed == {0: 3.25}
            window.stepper.reset()
            assert not window.stepper._elapsed and not window.stepper._started
    finally: _close(window, created)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_cancel_returns_to_existing_result_page(language, tmp_path, monkeypatch):
    module, window, created = _window(tmp_path, monkeypatch, language)
    try:
        window._has_result = True  # Owned pre-existing-result state, not a solver/render claim.
        window.start_pipeline("return to previous result")
        window._cancel_pipeline()
        created[-1].finish()
        assert window._workspace.currentIndex() == module.PAGE_SOLVE
        assert window.simulation_panel._stack.currentWidget() is not window.simulation_panel._loading
        assert window.command_bar.input.text() == "return to previous result"
    finally: _close(window, created)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_running_progress_labels_follow_selected_language(language, tmp_path, monkeypatch):
    _, window, created = _window(tmp_path, monkeypatch, language)
    labels = {"kk": ("Шешу", "Іздеу", "Сахна", "Рендер"),
              "ru": ("Решение", "Поиск", "Сцена", "Рендер"),
              "en": ("Solve", "RAG", "Scene", "Render")}[language]
    try:
        window.start_pipeline("localized progress")
        for index, percent in enumerate((10, 40, 60, 80)):
            created[-1].progress.emit(percent, "owned current detail")
            assert window.stepper._stage_labels[index] == labels[index]
            assert labels[index] in window.running_view._headline.text()
            assert window.running_view._detail.text() == "owned current detail"
    finally: _close(window, created)
