"""Stage O: the v2 5-minute lesson inside the app.

Unit coverage: plan shape (8 blocks, H1-H5 only), narration/content pins,
media resolution, prebuilt bundle assembly, missing-media error bundle, and
progress-key separation from the v1 route.

E2E coverage (offscreen): real MainWindow + LessonWorker + LessonView per
language — ready state, video source, 8 outline rows with measured seeks,
PDF button, review badge, subtitle count, chapter seek, quiz answer through
a real card click, persisted progress; then the error state and a restart
persistence re-read.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aetherlab.services.ent_lesson_catalog import (  # noqa: E402
    ACCELERATED_MOTION_5MIN_ID,
    ACCELERATED_MOTION_5MIN_VERSION,
    accelerated_motion_5min_plan,
    accelerated_motion_plan,
    curated_ent_lesson,
)

ROOT = Path(__file__).resolve().parent.parent
LANGS = ("kk", "ru", "en")
CANONICAL = json.loads(
    (ROOT / "output" / "stage_f_content" / "canonical.json").read_text(encoding="utf-8")
)
PRACTICE_ITEMS = json.loads(
    (ROOT / "output" / "stage_h_practice" / "practice.json").read_text(encoding="utf-8")
)["items"]


def _manifest_offsets(lang: str) -> list[float]:
    manifest = json.loads(
        (ROOT / "output" / "stage_m_final" / lang / f"assembly_manifest_{lang}.json")
        .read_text(encoding="utf-8")
    )
    return [float(manifest["blocks"][f"BlockB{i}"]["start_s"]) for i in range(8)]


def test_5min_plan_shape() -> None:
    for lang in LANGS:
        plan = accelerated_motion_5min_plan(lang)
        assert plan.language == lang
        assert plan.topic == ACCELERATED_MOTION_5MIN_ID
        assert plan.model_name == ACCELERATED_MOTION_5MIN_VERSION
        assert plan.audience == "high_school"
        assert [c.id for c in plan.chapters] == [f"B{i}" for i in range(8)]
        assert [c.kind for c in plan.chapters] == ["scene"] * 7 + ["recap"]
        assert all(c.title.strip() and c.narration.strip() for c in plan.chapters)
        assert len(plan.questions) == 5
        assert all(q.answer.startswith("A) ") for q in plan.questions)


def test_5min_narrations_match_canonical_voiceovers() -> None:
    blocks = {b["id"]: b for b in CANONICAL["blocks"]}
    for lang in LANGS:
        plan = accelerated_motion_5min_plan(lang)
        for chapter in plan.chapters:
            assert chapter.narration == blocks[chapter.id][f"voiceover_{lang}"]


def test_5min_numbers_do_not_drift() -> None:
    plan = accelerated_motion_5min_plan("ru")
    text = " ".join(
        " ".join(c.beats) + " ".join(c.key_equations) + " ".join(c.key_symbols)
        for c in plan.chapters
    )
    for token in ("14", "32", "25", "56"):
        assert token in text
    assert plan.chapters[2].key_equations[0] == r"v = v_0 + at"
    assert plan.chapters[3].key_equations[0] == r"s = v_0t + at^2/2"


def test_5min_practice_mirrors_practice_json() -> None:
    for lang in LANGS:
        plan = accelerated_motion_5min_plan(lang)
        for question, item in zip(plan.questions, PRACTICE_ITEMS):
            expected = [f"{o['id']}) {o['label'][lang]}" for o in item["options"]]
            assert question.q == item["prompt"][lang]
            assert question.choices == expected
            assert question.answer == expected[0]
            assert question.why == item["explanation"][lang]


def test_curated_resolver_routes_aliases_to_v2_and_keeps_legacy_id() -> None:
    for lang in LANGS:
        new = curated_ent_lesson("constant_acceleration_5min", lang)
        assert new is not None
        assert new.model_name == ACCELERATED_MOTION_5MIN_VERSION
        assert len(new.chapters) == 8
        old = curated_ent_lesson("constant_acceleration", lang)
        assert old is not None
        assert old.model_name == "physlab-ent-constant-acceleration-v1"
        assert old.questions[0].answer.startswith("B) ")
    assert curated_ent_lesson("constant acceleration 5min", "ru") is not None
    # Free-text aliases resolve to the v2 lesson in every language.
    for alias, lang in (("равноускоренное движение", "ru"),
                        ("теңүдемелі қозғалыс", "kk"),
                        ("uniformly accelerated motion", "en")):
        routed = curated_ent_lesson(alias, lang)
        assert routed is not None
        assert routed.model_name == ACCELERATED_MOTION_5MIN_VERSION
        assert len(routed.chapters) == 8
    assert curated_ent_lesson("кинематика", "ru") is None


def test_5min_progress_key_separate_from_v1() -> None:
    from aetherlab.services.course_mode import lesson_key

    new_keys = {lesson_key(accelerated_motion_5min_plan(lang)) for lang in LANGS}
    assert new_keys == {"high_school:constant-acceleration-5min"}
    for lang in LANGS:
        assert lesson_key(accelerated_motion_plan(lang)) not in new_keys


def test_prebuilt_media_resolves_all_languages() -> None:
    from aetherlab.services.lesson_pipeline import prebuilt_5min_media

    for lang in LANGS:
        media = prebuilt_5min_media(lang)
        assert media["missing"] == []
        assert media["video"].endswith(f"lesson_{lang}.mp4")
        assert media["srt"].endswith(f"lesson_{lang}.srt")
        assert media["pdf"].endswith(f"lesson_{lang}.pdf")
        assert media["offsets"] == _manifest_offsets(lang)
        assert media["review_status"]["teacher_translation_review"] == "pending"


def test_prebuilt_bundle_assembled_without_rendering(tmp_path) -> None:
    from aetherlab.core.settings import load_settings
    from aetherlab.services.lesson_pipeline import LessonPipeline

    settings = replace(load_settings(), data_dir=tmp_path, openai_api_key="test")
    pipeline = LessonPipeline(settings)
    bundle = asyncio.run(
        pipeline.run("constant_acceleration_5min", audience="high_school", language="ru")
    )
    assert bundle.status == "assembled"
    assert bundle.plan.language == "ru"
    assert bundle.chapter_scenes == []
    assert bundle.chapter_offsets == _manifest_offsets("ru")
    assert bundle.rendered_chapter_indexes == list(range(8))
    assert Path(bundle.video_path).is_file()
    assert Path(bundle.srt_path).read_text(encoding="utf-8").count("-->") == 45
    assert Path(bundle.pdf_path).is_file()


def test_prebuilt_bundle_missing_media_is_error_with_plan_intact(tmp_path, monkeypatch) -> None:
    import aetherlab.services.lesson_pipeline as pipeline_mod

    monkeypatch.setattr(pipeline_mod, "_stage_output_root", lambda: tmp_path / "empty")
    media = pipeline_mod.prebuilt_5min_media("ru")
    assert media["missing"] == ["video", "srt", "pdf", "offsets"]
    bundle = pipeline_mod._prebuilt_5min_bundle(accelerated_motion_5min_plan("ru"))
    assert bundle.status == "error"
    assert bundle.video_path == ""
    assert len(bundle.plan.chapters) == 8
    assert len(bundle.plan.questions) == 5


def test_bundle_json_roundtrip_carries_media_links() -> None:
    from aetherlab.core.models import LessonBundle
    from aetherlab.services.ent_lesson_catalog import ACCELERATED_MOTION_5MIN_REVIEW

    bundle = LessonBundle(
        plan=accelerated_motion_5min_plan("en"),
        video_path="v.mp4",
        status="assembled",
        chapter_offsets=[1.0, 2.0],
        rendered_chapter_indexes=[0, 1],
        srt_path="v.srt",
        pdf_path="v.pdf",
        review_status=dict(ACCELERATED_MOTION_5MIN_REVIEW),
    )
    clone = LessonBundle.from_json(bundle.to_json())
    assert clone.video_path == "v.mp4"
    assert clone.srt_path == "v.srt"
    assert clone.pdf_path == "v.pdf"
    assert clone.review_status["teacher_translation_review"] == "pending"
    # Old caches without the new keys still load.
    legacy = LessonBundle.from_json({"plan": bundle.plan.to_json()})
    assert legacy.srt_path == "" and legacy.pdf_path == "" and legacy.review_status == {}


_TEST_APP = None


def _app():
    from aetherlab.ui.fonts import install_ui_fonts
    from aetherlab.ui.qt_compat import QtWidgets

    global _TEST_APP
    _TEST_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    install_ui_fonts()
    return _TEST_APP


def test_stage_o_e2e_offscreen(tmp_path, monkeypatch) -> None:
    """Real MainWindow + LessonWorker + LessonView across ru/kk/en, then the
    error state and a restart persistence re-read."""
    import aetherlab.services.lesson_pipeline as pipeline_mod
    from aetherlab.core.settings import load_settings
    from aetherlab.services.course_mode import CourseProgressStore
    from aetherlab.ui.main_window import MainWindow
    from aetherlab.ui.qt_compat import QtCore, QtGui, QtWidgets

    app = _app()
    data_dir = tmp_path / "appdata"
    settings = replace(
        load_settings(), data_dir=data_dir, openai_api_key="test",
        cache_path=data_dir / "cache.sqlite3",
        library_path=data_dir / "library",
        chroma_path=data_dir / "chroma",
        reference_sources_path=data_dir / "references",
    )
    opened_urls: list[str] = []
    monkeypatch.setattr(
        QtGui.QDesktopServices, "openUrl", lambda url: opened_urls.append(url.toString()) or True
    )
    window = MainWindow(settings)
    window.resize(1280, 800)
    window.show()
    app.processEvents()
    try:
        shots_dir = tmp_path / "shots"
        shots_dir.mkdir()
        for lang in ("ru", "kk", "en"):
            expected = _manifest_offsets(lang)
            window.command_bar.set_language(lang)
            window.start_lesson("constant_acceleration_5min", language=lang)
            deadline = time.time() + 120
            while time.time() < deadline:
                app.processEvents()
                time.sleep(0.05)
                worker = window.lesson_worker
                if worker is not None and not worker.isRunning():
                    break
            app.processEvents()
            bundle = getattr(window, "_last_lesson", None)
            view = window.lesson_view
            assert bundle is not None and bundle.status == "assembled", lang
            assert bundle.plan.language == lang
            assert view._player is not None, lang
            actual = Path(view._player.source().toLocalFile())
            assert actual == Path(bundle.video_path), lang
            assert view._outline.count() == 8, lang
            seeks = [
                view._outline.item(r).data(QtCore.Qt.ItemDataRole.UserRole)
                for r in range(8)
            ]
            assert seeks == expected, lang
            assert view._pdf_btn.isVisible(), lang
            assert view._review_badge.isVisible(), lang
            assert view._cc_label is not None and view._cc_label.isVisible(), lang
            assert "45" in view._cc_label.text(), lang
            # Chapter seek through the real outline click.
            seeked: list[float] = []
            view.chapter_seek_requested.connect(seeked.append)
            try:
                view._on_outline_click(view._outline.item(4))
            finally:
                view.chapter_seek_requested.disconnect(seeked.append)
            assert seeked == [expected[4]], lang
            # PDF button opens the bundled PDF through the real window handler.
            before = len(opened_urls)
            view._pdf_btn.click()
            app.processEvents()
            assert len(opened_urls) == before + 1, lang
            assert opened_urls[-1].replace("/", "\\").endswith(
                str(Path(bundle.pdf_path)).replace("/", "\\")[-len(f"lesson_{lang}.pdf"):]), lang
            # Quiz answer through a real card click -> window progress path.
            card = view._question_cards[1]
            correct = next(
                b for b in card._group.buttons() if b.text() == card._q.answer
            )
            correct.click()
            app.processEvents()
            summary = window.course_progress.summary(bundle.plan)
            assert summary.correct >= 1, lang
            # Layout evidence: video tab + questions tab.
            view._tabs.setCurrentIndex(0)
            app.processEvents()
            view.grab().save(str(shots_dir / f"lesson_{lang}_video.png"))
            view._tabs.setCurrentIndex(3)
            app.processEvents()
            view.grab().save(str(shots_dir / f"lesson_{lang}_questions.png"))
            view._tabs.setCurrentIndex(0)

        # Restart persistence: a fresh store over the same file keeps answers.
        last_bundle = getattr(window, "_last_lesson", None)
        progress_file = Path(window.course_progress.path)
        assert progress_file.is_file()
        reread = CourseProgressStore(progress_file).summary(last_bundle.plan)
        assert reread.correct >= 1

        # Error state: missing media bundle through the real on_lesson_ready.
        def _missing_media(language: str = "ru"):
            from aetherlab.services.ent_lesson_catalog import (
                ACCELERATED_MOTION_5MIN_REVIEW,
            )

            return {"video": "", "srt": "", "pdf": "", "offsets": [],
                    "review_status": dict(ACCELERATED_MOTION_5MIN_REVIEW),
                    "missing": ["video", "srt", "pdf", "offsets"]}

        monkeypatch.setattr(pipeline_mod, "prebuilt_5min_media", _missing_media)
        error_bundle = pipeline_mod._prebuilt_5min_bundle(
            accelerated_motion_5min_plan("ru")
        )
        window.on_lesson_ready(error_bundle)
        app.processEvents()
        assert error_bundle.status == "error"
        assert not window.lesson_view._video_empty_overlay.isHidden()
        assert window.lesson_view._transcript.toPlainText().strip()
        assert window.lesson_view._outline.count() == 8
        # The user-visible state: Video tab shows the empty-video message.
        window.lesson_view._tabs.setCurrentIndex(0)
        app.processEvents()
        assert window.lesson_view._video_empty_overlay.isVisible()
        window.lesson_view.grab().save(str(shots_dir / "lesson_error_state.png"))

        print(f"\nshots={[p.name for p in sorted(shots_dir.glob('*.png'))]}")
    finally:
        window.close()
        app.processEvents()
