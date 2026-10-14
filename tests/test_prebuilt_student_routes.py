"""Prepared lessons remain accessible and belong to the selected learner/language."""
from __future__ import annotations

import os
from dataclasses import replace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aetherlab.services.ai_help_quota import consume_ai_help
from aetherlab.services.ent_lesson_catalog import accelerated_motion_5min_plan
from aetherlab.services.lesson_pipeline import _prebuilt_5min_bundle
from aetherlab.ui.qt_compat import QtCore, QtWidgets

_APP = None


class _ReadyWorker(QtCore.QObject):
    progress = QtCore.pyqtSignal(str, int, int)
    lesson_ready = QtCore.pyqtSignal(object)
    failure = QtCore.pyqtSignal(object)
    finished = QtCore.pyqtSignal()
    calls = []

    def __init__(self, topic, settings, *, language, **kwargs):
        super().__init__()
        self.topic, self.language = topic, language
        self.running = False

    def isRunning(self):
        return self.running

    def start(self):
        self.calls.append((self.topic, self.language))
        self.running = True
        self.lesson_ready.emit(_prebuilt_5min_bundle(accelerated_motion_5min_plan(self.language)))
        self.running = False
        self.finished.emit()


def _window(root, language, monkeypatch):
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from aetherlab.core.settings import load_settings
    from aetherlab.ui import main_window

    monkeypatch.setenv("AETHERLAB_DATA_DIR", str(root))
    monkeypatch.setenv("AETHERLAB_DISABLE_LEGACY_ENV", "1")
    monkeypatch.setattr(main_window, "LessonWorker", _ReadyWorker)
    _ReadyWorker.calls = []
    settings = replace(load_settings(), data_dir=root, cache_path=root / "cache.sqlite3",
                       chroma_path=root / "chroma", library_path=root / "library",
                       openai_api_key="", fallback_api_key="", github_token="", reference_sources_path=None)
    window = main_window.MainWindow(settings)
    # This proves signal/content routing, not multimedia playback.
    def record_video(path):
        window._observed_video_path = path
    monkeypatch.setattr(window.lesson_view, "set_video", record_video)
    window.command_bar.set_language(language)
    return window


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("allowance", ("fresh", "exhausted", "unreadable"))
def test_prebuilt_lesson_does_not_consume_or_depend_on_ai_allowance(language, allowance, tmp_path, monkeypatch):
    window = _window(tmp_path, language, monkeypatch)
    target = window.active_student_profile.ai_help_quota_path
    if allowance == "exhausted":
        for _ in range(10):
            consume_ai_help(target)
    before = target.read_bytes() if target.exists() else None
    if allowance == "unreadable":
        monkeypatch.setattr(window, "_try_consume_ai_help", lambda: pytest.fail("Prepared lesson accessed AI allowance"))
    try:
        window._start_ent_topic_lesson("kinematics")
        assert _ReadyWorker.calls == [("constant_acceleration_5min", language)]
        assert window._last_lesson.plan.language == language
        assert window._last_lesson.status == "assembled"
        assert (target.read_bytes() if target.exists() else None) == before
    finally:
        window.close()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_switching_profile_rebuilds_lesson_answers_for_the_new_student(language, tmp_path, monkeypatch):
    from aetherlab.services.course_mode import CourseProgressStore
    from aetherlab.ui.profile_dialog import StudentProfileDialog

    window = _window(tmp_path, language, monkeypatch)
    bundle = _prebuilt_5min_bundle(accelerated_motion_5min_plan(language))
    window.on_lesson_ready(bundle)
    first = window.active_student_profile
    card = window.lesson_view._question_cards[0]
    next(button for button in card._group.buttons() if button.text() == card._q.answer).click()
    before = first.course_progress_path.read_bytes()
    second = window.student_profile_store.create_profile("Audit second learner")

    def select_second(dialog):
        dialog.profile_combo.setCurrentIndex(dialog.profile_combo.findData(second.id))
        dialog.use_button.click()
        return dialog.result()

    monkeypatch.setattr(StudentProfileDialog, "exec", select_second)
    try:
        window._manage_student_profiles()
        fresh = window.lesson_view._question_cards[0]
        assert window.active_student_profile.id == second.id
        assert fresh is not card and not fresh._answered
        assert not fresh._feedback.text() and all(button.isEnabled() for button in fresh._group.buttons())
        next(button for button in fresh._group.buttons() if button.text() == fresh._q.answer).click()
        assert first.course_progress_path.read_bytes() == before
        assert CourseProgressStore(second.course_progress_path).summary(bundle.plan).attempts == 1
    finally:
        window.close()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_cancel_profile_dialog_keeps_current_lesson_selection(language, tmp_path, monkeypatch):
    from aetherlab.ui.profile_dialog import StudentProfileDialog

    window = _window(tmp_path, language, monkeypatch)
    bundle = _prebuilt_5min_bundle(accelerated_motion_5min_plan(language))
    window.on_lesson_ready(bundle)
    card = window.lesson_view._question_cards[0]
    card._group.buttons()[0].click()
    before = window.active_student_profile.course_progress_path.read_bytes()
    monkeypatch.setattr(StudentProfileDialog, "exec", lambda dialog: QtWidgets.QDialog.DialogCode.Rejected)
    try:
        window._manage_student_profiles()
        assert window.lesson_view._question_cards[0] is card and card._answered
        assert window.active_student_profile.course_progress_path.read_bytes() == before
    finally:
        window.close()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_header_language_switch_selects_matching_prebuilt_content_and_media(language, tmp_path, monkeypatch):
    window = _window(tmp_path, language, monkeypatch)
    window.on_lesson_ready(_prebuilt_5min_bundle(accelerated_motion_5min_plan(language)))
    try:
        for target in ("ru", "en", "kk"):
            window._on_title_language_changed(target)
            assert window._last_lesson.plan.language == target
            assert window.lesson_view._bundle.plan.language == target
            assert f"/{target}/" in window._observed_video_path.replace("\\", "/")
    finally:
        window.close()


def test_prebuilt_progress_has_one_identity_in_all_languages(tmp_path):
    from aetherlab.services.course_mode import CourseProgressStore, lesson_key

    plans = [accelerated_motion_5min_plan(language) for language in ("kk", "ru", "en")]
    assert len({lesson_key(plan) for plan in plans}) == 1
    store = CourseProgressStore(tmp_path / "progress.json")
    store.record_quiz_answer(plans[0], 0, True, plans[0].questions[0].answer)
    assert all(store.summary(plan).attempts == 1 for plan in plans)


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_command_bar_allows_only_explicit_prebuilt_route_without_ai_quota(language):
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from aetherlab.ui.command_bar import CommandBar

    bar = CommandBar()
    bar.set_language(language)
    try:
        for quota in (0, None):
            bar.input.clear()
            bar.set_ai_quota(quota)
            assert not bar.learn_button.isEnabled()
            bar.input.setText("Constant-Acceleration-5min")
            assert bar.learn_button.isEnabled() and not bar.run_button.isEnabled()
            bar.input.setText("Explain electricity")
            assert not bar.learn_button.isEnabled()
    finally:
        bar.close()


def test_real_prebuilt_worker_never_indexes_references_or_generates_content(tmp_path, monkeypatch):
    from aetherlab.ui import workers

    window = _window(tmp_path, "ru", monkeypatch)
    indexed = []
    def forbidden(*_args, **_kwargs):
        indexed.append(True)
        raise AssertionError("Prepared content must not index references")
    monkeypatch.setattr(workers, "LibraryIngestor", forbidden)
    worker = workers.LessonWorker("constant_acceleration_5min", window.settings, language="ru")
    received = []
    worker.lesson_ready.connect(received.append)
    try:
        worker.run()
        assert not indexed
        assert len(received) == 1 and received[0].status == "assembled"
    finally:
        window.close()


def test_stale_question_card_cannot_record_an_answer_for_another_lesson(tmp_path, monkeypatch):
    window = _window(tmp_path, "ru", monkeypatch)
    bundle = _prebuilt_5min_bundle(accelerated_motion_5min_plan("ru"))
    window.on_lesson_ready(bundle)
    stale = window.lesson_view._question_cards[0]
    window.on_lesson_ready(_prebuilt_5min_bundle(accelerated_motion_5min_plan("en")))
    try:
        stale._group.buttons()[0].click()
        assert window.course_progress.summary(window._last_lesson.plan).attempts == 0
        assert not window.lesson_view._question_cards[0]._answered
    finally:
        window.close()


def test_settings_save_keeps_course_progress_bound_to_the_active_student(tmp_path, monkeypatch):
    from aetherlab.ui.main_window import SettingsDialog
    from aetherlab.ui.profile_dialog import StudentProfileDialog

    window = _window(tmp_path, "ru", monkeypatch)
    second = window.student_profile_store.create_profile("Audit second learner")
    def select_second(dialog):
        dialog.profile_combo.setCurrentIndex(dialog.profile_combo.findData(second.id))
        dialog.use_button.click()
        return dialog.result()
    monkeypatch.setattr(StudentProfileDialog, "exec", select_second)
    window._manage_student_profiles()
    monkeypatch.setattr(SettingsDialog, "exec", lambda dialog: QtWidgets.QDialog.DialogCode.Accepted)
    try:
        window._open_settings()
        assert window.active_student_profile.id == second.id
        assert window.course_progress.path == second.course_progress_path
        assert window.course_progress.path != tmp_path / "course_progress.json"
        window.on_lesson_ready(_prebuilt_5min_bundle(accelerated_motion_5min_plan("ru")))
        card = window.lesson_view._question_cards[0]
        next(button for button in card._group.buttons() if button.text() == card._q.answer).click()
        assert second.course_progress_path.is_file()
        assert not (tmp_path / "course_progress.json").exists()
    finally:
        window.close()


def test_language_changes_during_loading_use_only_the_latest_choice(tmp_path, monkeypatch):
    import threading

    from aetherlab.ui import main_window

    class HeldWorker(_ReadyWorker):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._cancel = threading.Event()
        def start(self):
            self.calls.append((self.topic, self.language))
            self.running = True
        def complete(self):
            self.lesson_ready.emit(_prebuilt_5min_bundle(accelerated_motion_5min_plan(self.language)))
            self.running = False
            self.finished.emit()

    window = _window(tmp_path, "kk", monkeypatch)
    monkeypatch.setattr(main_window, "LessonWorker", HeldWorker)
    window.on_lesson_ready(_prebuilt_5min_bundle(accelerated_motion_5min_plan("kk")))
    try:
        window._on_title_language_changed("ru")
        first = window.lesson_worker
        window._on_title_language_changed("en")
        assert window.lesson_worker is first and first.language == "ru"
        first.complete()
        latest = window.lesson_worker
        assert latest is not first and latest.language == "en"
        latest.complete()
        assert window._last_lesson.plan.language == "en"
        assert _ReadyWorker.calls == [("constant_acceleration_5min", "ru"), ("constant_acceleration_5min", "en")]
    finally:
        window.close()


def test_empty_cancelled_load_preserves_the_previous_lesson_and_its_answers(tmp_path, monkeypatch):
    from aetherlab.core.models import LessonBundle, LessonPlan

    window = _window(tmp_path, "ru", monkeypatch)
    previous = _prebuilt_5min_bundle(accelerated_motion_5min_plan("ru"))
    window.on_lesson_ready(previous)
    try:
        window.on_lesson_ready(LessonBundle(plan=LessonPlan(title="Cancelled", topic="cancelled"), status="cancelled"))
        assert window._last_lesson is previous
        card = window.lesson_view._question_cards[0]
        next(button for button in card._group.buttons() if button.text() == card._q.answer).click()
        assert window.course_progress.summary(previous.plan).attempts == 1
    finally:
        window.close()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("entry", ("dashboard", "catalog"))
@pytest.mark.parametrize("allowance", ("fresh", "exhausted"))
def test_visible_kinematics_buttons_select_the_prepared_package(language, entry, allowance, tmp_path, monkeypatch):
    window = _window(tmp_path, language, monkeypatch)
    target = window.active_student_profile.ai_help_quota_path
    if allowance == "exhausted":
        for _ in range(10):
            consume_ai_help(target)
    before = target.read_bytes() if target.exists() else None
    try:
        if entry == "dashboard":
            assert window.student_dashboard._hero_topic_id == "kinematics"
            window.student_dashboard.hero_learn_button.click()
        else:
            buttons = window.topic_catalog.cards[0][0].findChildren(QtWidgets.QPushButton)
            assert len(buttons) == 2
            buttons[0].click()
        assert _ReadyWorker.calls == [("constant_acceleration_5min", language)]
        assert window._last_lesson.status == "assembled"
        assert len(window._last_lesson.plan.chapters) == 8
        assert window._last_lesson.plan.language == language
        assert (target.read_bytes() if target.exists() else None) == before
    finally:
        window.close()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_prepared_lesson_success_and_audience_are_localized(language, tmp_path, monkeypatch):
    window = _window(tmp_path, language, monkeypatch)
    ready = {"kk": "Сабақ дайын", "ru": "Урок готов", "en": "Lesson ready"}[language]
    audience = {"kk": "Мектеп оқушысына", "ru": "Для школьника", "en": "For school students"}[language]
    try:
        window.on_lesson_ready(_prebuilt_5min_bundle(accelerated_motion_5min_plan(language)))
        assert window.statusBar().currentMessage().startswith(ready)
        assert window.toast._message.text().startswith(ready)
        assert window.lesson_view._audience.text().startswith(audience)
        assert "assembled" not in window.toast._message.text()
    finally:
        window.close()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("status", ("rendering", "text_only"))
def test_incomplete_video_is_not_announced_as_a_completed_lesson(language, status, tmp_path, monkeypatch):
    window = _window(tmp_path, language, monkeypatch)
    prefix = {"kk": "Сабақ мәтіні дайын", "ru": "Текст урока готов", "en": "Lesson text ready"}[language]
    bundle = _prebuilt_5min_bundle(accelerated_motion_5min_plan(language))
    bundle.status = status
    bundle.video_path = ""
    try:
        window.on_lesson_ready(bundle)
        assert window.toast._kind != "success"
        assert window.statusBar().currentMessage().startswith(prefix)
        assert window.toast._message.text().startswith(prefix)
        assert status not in window.toast._message.text()
    finally:
        window.close()
