"""Actual lesson callbacks and review controls keep locale, provenance and grade state."""
import asyncio
import runpy
from dataclasses import replace
from pathlib import Path

import pytest

from aetherlab.core.models import LessonBundle, LessonChapter, LessonPlan, SceneBundle
from aetherlab.services.ent_lesson_catalog import accelerated_motion_5min_plan
from aetherlab.services.lesson_pipeline import _prebuilt_5min_bundle
from aetherlab.ui.qt_compat import QtWidgets

_route_helpers = runpy.run_path(str(Path(__file__).with_name("test_prebuilt_student_routes.py")))
_window = _route_helpers["_window"]


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
@pytest.mark.parametrize("partial", (False, True))
def test_cancelled_lesson_messages_follow_the_requested_language(language, partial, tmp_path, monkeypatch):
    window = _window(tmp_path, language, monkeypatch)
    bundle = _prebuilt_5min_bundle(accelerated_motion_5min_plan(language))
    bundle.status = "cancelled"
    if not partial:
        bundle.video_path = ""
    prefix = {"kk": "Сабақ жасау тоқтатылды", "ru": "Создание урока отменено", "en": "Lesson cancelled"}[language]
    try:
        window.on_lesson_ready(bundle)
        assert window.statusBar().currentMessage().startswith(prefix)
        notice_prefix = "Сабақ жасау бірінші бөлім аяқталғанға дейін тоқтатылды." if language == "kk" and not partial else prefix
        assert window.toast._message.text().startswith(notice_prefix)
        assert window.toast._kind == "warning"
    finally:
        window.close()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_saved_answer_and_course_io_notice_are_localized(language, tmp_path, monkeypatch):
    window = _window(tmp_path, language, monkeypatch)
    bundle = _prebuilt_5min_bundle(accelerated_motion_5min_plan(language))
    window.on_lesson_ready(bundle)
    prefix = {"kk": "Курс прогресі сақталды", "ru": "Прогресс курса сохранён", "en": "Course progress saved"}[language]
    unavailable = {"kk": "Курс прогресін", "ru": "Не удалось загрузить прогресс курса", "en": "Course progress is unavailable"}[language]
    try:
        card = window.lesson_view._question_cards[0]
        next(button for button in card._group.buttons() if button.text() == card._q.answer).click()
        assert window.statusBar().currentMessage().startswith(prefix)
        assert "1/1" in window.lesson_view._course_status.text()
        def refused(*_args, **_kwargs):
            raise PermissionError("Controlled history access refusal")
        monkeypatch.setattr(window.course_progress, "summary", refused)
        window._refresh_course_summary(bundle)
        assert window.lesson_view._course_status.text().startswith(unavailable)
    finally:
        window._pending_lesson_answers.clear()
        window.close()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_empty_review_notice_is_localized(language, tmp_path, monkeypatch):
    window = _window(tmp_path, language, monkeypatch)
    expected = {"kk": "Қазір қайталау уақыты келген сұрақтар жоқ.", "ru": "Сейчас нет вопросов для повторения.", "en": "No review questions are due right now."}[language]
    try:
        window._review_due_questions()
        assert window.statusBar().currentMessage() == expected
    finally:
        window.close()


def test_header_language_change_retains_generic_lesson_score_without_regeneration(tmp_path, monkeypatch):
    window = _window(tmp_path, "en", monkeypatch)
    plan = LessonPlan(title="Controlled", topic="Pendulum", language="en", model_name="authored-feedback-test",
                      questions=accelerated_motion_5min_plan("en").questions[:1])
    window.on_lesson_ready(LessonBundle(plan=plan, status="text_only"))
    card = window.lesson_view._question_cards[0]
    next(button for button in card._group.buttons() if button.text() == card._q.answer).click()
    target = window.active_student_profile.course_progress_path
    before = target.read_bytes()
    monkeypatch.setattr(window, "start_lesson", lambda *_args, **_kwargs: pytest.fail("Language controls regenerated a generic lesson"))
    try:
        for language in ("kk", "ru", "en"):
            window.command_bar.set_language(language)
            message = window.lesson_view._course_status.text()
            assert "1/1" in message
            assert target.read_bytes() == before
            if language != "en":
                assert "Quiz score" not in message and "Next:" not in message
    finally:
        window.close()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_open_review_controls_are_localized_and_do_not_self_rate_on_dismissal(language, tmp_path, monkeypatch):
    window = _window(tmp_path, language, monkeypatch)
    item = {"lesson_key": "missing", "question_index": "0", "prompt": "Controlled open recall", "answer": "Fixture answer", "choices": []}
    monkeypatch.setattr(window.course_progress, "due_reviews", lambda **_kwargs: [item])
    invoked = []
    labels = {
        "kk": ("Аралық қайталау", "Жауапты көрсету", "Кейін аяқтау"),
        "ru": ("Повторение по расписанию", "Показать ответ", "Закончить позже"),
        "en": ("Spaced review", "Reveal answer", "Finish later"),
    }[language]
    def dismiss(dialog):
        invoked.append(dialog)
        assert dialog.windowTitle() == labels[0]
        assert {button.text() for button in dialog.buttons()} == set(labels[1:])
        assert dialog.defaultButton().text() == labels[2]
        assert dialog.escapeButton() is dialog.defaultButton()
        dialog.defaultButton().click()
        return dialog.result()
    monkeypatch.setattr(QtWidgets.QMessageBox, "exec", dismiss)
    try:
        window._review_due_questions()
        assert len(invoked) == 1
        assert not window.active_student_profile.course_progress_path.exists()
    finally:
        window.close()


def test_missing_review_target_is_not_reported_as_a_saved_response(tmp_path, monkeypatch):
    window = _window(tmp_path, "ru", monkeypatch)
    from aetherlab.ui import widgets
    item = {"lesson_key": "removed", "question_index": "0", "prompt": "Controlled MCQ", "answer": "A", "choices": ["A", "B"]}
    monkeypatch.setattr(window.course_progress, "due_reviews", lambda **_kwargs: [item])
    class Accepted:
        answer_submitted = True
        answer_correct = True
        def __init__(self, *_args, **_kwargs):
            pass
        def exec(self):
            return QtWidgets.QDialog.DialogCode.Accepted
    monkeypatch.setattr(widgets, "_LessonCheckDialog", Accepted)
    try:
        window._review_due_questions()
        assert "изменился" in window.statusBar().currentMessage()
        assert "Сохранено ответов" not in window.statusBar().currentMessage()
        assert not window.active_student_profile.course_progress_path.exists()
    finally:
        window.close()


def test_partial_cancelled_reload_restores_the_original_pending_answer(tmp_path, monkeypatch):
    window = _window(tmp_path, "ru", monkeypatch)
    from aetherlab.services import course_mode
    bundle = _prebuilt_5min_bundle(accelerated_motion_5min_plan("ru"))
    window.on_lesson_ready(bundle)
    original = window.lesson_view._question_cards[0]
    answer = original._q.answer
    def refused(*_args, **_kwargs):
        raise PermissionError("Controlled write refusal")
    with monkeypatch.context() as patch:
        patch.setattr(course_mode, "atomic_write_json", refused)
        next(button for button in original._group.buttons() if button.text() == answer).click()
    bundle.status = "cancelled"
    try:
        window.on_lesson_ready(bundle)
        restored = window.lesson_view._question_cards[0]
        assert restored is not original and restored._answered
        assert restored._group.checkedButton().text() == answer
        assert not restored._save_retry.isHidden()
        restored._save_retry.click()
        assert window.course_progress.summary(bundle.plan).attempts == 1
        assert not window._pending_lesson_answers
    finally:
        window._pending_lesson_answers.clear()
        window.close()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_pipeline_progress_localizes_chapter_lifecycle_without_claiming_a_video(language, tmp_path, monkeypatch):
    from aetherlab.core.settings import load_settings
    from aetherlab.services import lesson_pipeline
    monkeypatch.setenv("AETHERLAB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AETHERLAB_DISABLE_LEGACY_ENV", "1")
    settings = replace(load_settings(), data_dir=tmp_path, openai_api_key="", fallback_api_key="", github_token="")
    plan = LessonPlan(title="Controlled", topic="Controlled", language=language, model_name="controlled-curated",
                      chapters=[LessonChapter(id="fixture", title="Fixture title", kind="scene")])
    monkeypatch.setattr(lesson_pipeline, "curated_ent_lesson", lambda *_args: plan)
    monkeypatch.setattr(lesson_pipeline, "_LESSON_DIR", tmp_path / "lessons")
    pipeline = lesson_pipeline.LessonPipeline(settings)
    async def render(*_args, **_kwargs):
        return SceneBundle(class_name="Fixture", code="", engine="manim", status="compiled")
    async def narrate(*_args, **_kwargs):
        return [], [], []
    async def assemble(*_args, **_kwargs):
        return None, None, []
    monkeypatch.setattr(pipeline, "_render_chapter", render)
    monkeypatch.setattr(pipeline, "_narrate_chapters", narrate)
    monkeypatch.setattr(pipeline, "_assemble", assemble)
    messages = []
    bundle = asyncio.run(pipeline.run("Controlled", language=language, progress=lambda m, d, t: messages.append(m)))
    prefix = {"kk": "Бөлім", "ru": "Раздел", "en": "Chapter"}[language]
    final = {"kk": "Сабақ толық дайын емес", "ru": "Урок ещё не завершён", "en": "Lesson incomplete"}[language]
    assert any(message.startswith(f"{prefix} 1/1:") and "Fixture title" in message for message in messages)
    assert messages[-1] == final and not bundle.video_path
