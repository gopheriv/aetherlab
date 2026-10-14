"""Stage O: the prebuilt v2 5-minute lesson is wired into the app.

Covers: catalog resolution + plan content (8 chapters, H1-H5, citations) in
all three languages, measured chapter offsets, prebuilt bundle assembly
(ready + explicit error states), progress-key separation from v1, share
export with PDF, and the LessonView surface (PDF button, review badge,
quiz -> progress) offscreen.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _content() -> dict:
    from aetherlab.services.ent_lesson_catalog import _load_5min_content

    return _load_5min_content()


def test_v2_plan_all_languages() -> None:
    from aetherlab.services.ent_lesson_catalog import (
        ACCELERATED_MOTION_5MIN_VERSION,
        accelerated_motion_5min_plan,
        curated_ent_lesson,
    )

    for lang in ("kk", "ru", "en"):
        plan = accelerated_motion_5min_plan(lang)
        assert plan.language == lang
        assert plan.model_name == ACCELERATED_MOTION_5MIN_VERSION
        assert len(plan.chapters) == 8
        assert [c.id for c in plan.chapters] == [f"b{i}" for i in range(8)]
        assert all(c.narration.strip() for c in plan.chapters)
        assert all(c.title.strip() and c.goal.strip() for c in plan.chapters)
        assert len(plan.questions) == 5
        assert all(q.choices for q in plan.questions)
        assert all(q.answer in q.choices for q in plan.questions)
        assert any(c.citations for c in plan.chapters)
        resolved = curated_ent_lesson("constant_acceleration_5min", lang)
        assert resolved is not None and resolved.topic == plan.topic
        # v1 aliases still resolve to the v1 plan, not v2.
        v1 = curated_ent_lesson("constant_acceleration", lang)
        assert v1 is not None and v1.model_name != ACCELERATED_MOTION_5MIN_VERSION


def test_v2_questions_match_practice_key() -> None:
    from aetherlab.services.ent_lesson_catalog import accelerated_motion_5min_plan

    practice = json.loads(
        (ROOT / "output/stage_h_practice/practice.json").read_text(encoding="utf-8")
    )
    for lang in ("kk", "ru", "en"):
        plan = accelerated_motion_5min_plan(lang)
        for item, question in zip(practice["items"], plan.questions):
            correct = next(
                o for o in item["options"] if o["id"] == item["correct_option_id"]
            )
            assert question.answer == f"{correct['id']}) {correct['label'][lang]}"
            assert question.q == item["prompt"][lang]
            assert question.why == item["explanation"][lang]


def test_v2_narrations_match_canonical_voiceovers() -> None:
    from aetherlab.services.ent_lesson_catalog import accelerated_motion_5min_plan

    canonical = json.loads(
        (ROOT / "output/stage_f_content/canonical.json").read_text(encoding="utf-8")
    )
    assert canonical["version"] == 2
    for lang in ("kk", "ru", "en"):
        plan = accelerated_motion_5min_plan(lang)
        for block, chapter in zip(canonical["blocks"], plan.chapters):
            assert chapter.narration == block[f"voiceover_{lang}"]


def test_v2_offsets_are_measured_cumsum() -> None:
    from aetherlab.services.ent_lesson_catalog import prebuilt_5min_media

    params = json.loads(
        (ROOT / "output/stage_m_final/params.json").read_text(encoding="utf-8")
    )
    expected, t = [], 0.0
    for i in range(8):
        expected.append(t)
        t += float(params["ru"][f"BlockB{i}"]["duration_s"])
    for lang in ("kk", "ru", "en"):
        media = prebuilt_5min_media(lang)
        assert media["missing"] == []
        assert media["offsets"] == expected
        assert Path(media["video"]).is_file()
        assert Path(media["srt"]).is_file()
        assert Path(media["pdf"]).is_file()


def test_v2_progress_keys_do_not_collide_with_v1() -> None:
    from aetherlab.services.course_mode import lesson_key
    from aetherlab.services.ent_lesson_catalog import (
        accelerated_motion_5min_plan,
        accelerated_motion_plan,
    )

    for lang in ("kk", "ru", "en"):
        v1_key = lesson_key(accelerated_motion_plan(lang))
        v2_key = lesson_key(accelerated_motion_5min_plan(lang))
        assert v2_key != v1_key, lang


def test_prebuilt_bundle_ready_and_error_states(tmp_path, monkeypatch) -> None:
    import asyncio

    from aetherlab.core.settings import load_settings
    from aetherlab.services.ent_lesson_catalog import accelerated_motion_5min_plan
    from aetherlab.services.lesson_pipeline import LessonPipeline, _prebuilt_5min_bundle

    monkeypatch.setenv("AETHERLAB_DATA_DIR", str(tmp_path / "data"))
    settings = load_settings()
    for lang in ("kk", "ru", "en"):
        bundle = asyncio.run(
            LessonPipeline(settings).run(
                "constant_acceleration_5min", audience="high_school", language=lang
            )
        )
        assert bundle.status == "assembled", lang
        assert Path(bundle.video_path).is_file()
        assert Path(bundle.srt_path).is_file()
        assert Path(bundle.pdf_path).is_file()
        assert bundle.chapter_offsets == _content()["chapter_offsets"]
        assert "needs_teacher_review" in str(bundle.review_status)

    # Missing media degrades to an explicit error bundle, never a blank page.
    plan = accelerated_motion_5min_plan("ru")
    real = dict(plan.__dict__)
    _ = real
    import aetherlab.services.lesson_pipeline as pipeline_mod

    def _missing_media(language: str = "ru", *, expected_content_hash: str | None = None) -> dict:
        return {
            "video": "", "srt": "", "pdf": "",
            "offsets": [0.0] * 8, "review_status": {},
            "missing": ["video", "srt", "pdf"],
        }

    original = pipeline_mod.prebuilt_5min_media
    pipeline_mod.prebuilt_5min_media = _missing_media  # type: ignore[assignment]
    try:
        error_bundle = _prebuilt_5min_bundle(plan)
    finally:
        pipeline_mod.prebuilt_5min_media = original
    assert error_bundle.status == "error"
    assert error_bundle.missing_media == ["video", "srt", "pdf"]
    assert len(error_bundle.plan.chapters) == 8  # transcript/questions still work


def test_share_export_includes_pdf_and_subtitles(tmp_path) -> None:
    from aetherlab.services.ent_lesson_catalog import accelerated_motion_5min_plan
    from aetherlab.services.lesson_pipeline import _prebuilt_5min_bundle
    from aetherlab.services.share_export import export_lesson_bundle

    bundle = _prebuilt_5min_bundle(accelerated_motion_5min_plan("ru"))
    assert bundle.status == "assembled"
    summary = export_lesson_bundle(bundle, tmp_path / "lesson_5min.zip")
    assert "study_guide.pdf" in "\n".join(summary.entries)
    assert any(e.endswith("media/lesson.srt") for e in summary.entries)
    assert any(e.endswith("media/lesson.vtt") for e in summary.entries)


def _app():
    from aetherlab.ui.qt_compat import QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_lesson_view_v2_surface_and_quiz_progress(tmp_path) -> None:
    from aetherlab.services.course_mode import CourseProgressStore, lesson_key
    from aetherlab.services.ent_lesson_catalog import accelerated_motion_5min_plan
    from aetherlab.services.lesson_pipeline import _prebuilt_5min_bundle
    from aetherlab.ui.lesson_view import LessonView

    app = _app()
    for lang in ("kk", "ru", "en"):
        bundle = _prebuilt_5min_bundle(accelerated_motion_5min_plan(lang))
        view = LessonView()
        view.show()
        app.processEvents()
        view.set_lesson(bundle)
        view.set_video(bundle.video_path)
        app.processEvents()
        try:
            assert view._outline.count() == 8
            assert view._pdf_btn.isVisible(), lang
            assert view._review_badge.isVisible(), lang
            assert len(view._question_cards) == 5
            # The chapter outline seeks the measured block starts.
            expected = _content()["chapter_offsets"]
            for row in range(8):
                from aetherlab.ui.qt_compat import QtCore

                seek = view._outline.item(row).data(QtCore.Qt.ItemDataRole.UserRole)
                assert seek == expected[row], (lang, row)
            # Answering a question records course progress (restart-persistent).
            progress = CourseProgressStore(tmp_path / f"course_{lang}.json")
            card = view._question_cards[0]
            recorded: list[tuple[bool, str]] = []
            card.answer_recorded.connect(lambda c, ch: recorded.append((c, ch)))
            correct = next(
                b for b in card._group.buttons() if b.text() == card._q.answer
            )
            correct.click()
            app.processEvents()
            assert recorded and recorded[0][0] is True
            summary = progress.record_quiz_answer(
                bundle.plan, 0, True, recorded[0][1]
            )
            assert summary.correct == 1
            reread = CourseProgressStore(tmp_path / f"course_{lang}.json").summary(bundle.plan)
            assert reread.correct == 1 and reread.attempts == 1
            assert lesson_key(bundle.plan) in json.loads(
                (tmp_path / f"course_{lang}.json").read_text(encoding="utf-8")
            )["lessons"]
        finally:
            # Unload the real media before closing: an abandoned FFmpeg load
            # crashes later MainWindow construction in the same session.
            try:
                if view._player is not None:
                    from PyQt6.QtCore import QUrl

                    view._player.stop()
                    view._player.setSource(QUrl())
            finally:
                app.processEvents()
                view.close()
                app.processEvents()


def test_v1_plan_untouched() -> None:
    """The v1 render-on-demand route keeps its content and version."""
    from aetherlab.services.ent_lesson_catalog import (
        ACCELERATED_MOTION_VERSION,
        accelerated_motion_plan,
        route_content,
    )

    assert ACCELERATED_MOTION_VERSION == "physlab-ent-constant-acceleration-v1"
    plan = accelerated_motion_plan("ru")
    assert plan.model_name == ACCELERATED_MOTION_VERSION
    assert route_content("ru")["route_id"] == "constant_acceleration"
