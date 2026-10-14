"""A portable lesson must retain truthful assets, chapter seeking and language."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

from aetherlab.core.models import LessonBundle, LessonPlan
from aetherlab.services.share_export import export_lesson_bundle


def _bundle(tmp_path, language="en"):
    video = tmp_path / f"{language}.mp4"
    video.write_bytes(b"synthetic export fixture, not playback evidence")
    return LessonBundle(plan=LessonPlan(title="Physics", language=language), video_path=str(video), status="assembled")


def _export(bundle, path):
    export_lesson_bundle(bundle, path)
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        metadata_path = next(name for name in names if name.endswith("/metadata.json"))
        prefix = metadata_path.removesuffix("metadata.json")
        metadata = json.loads(archive.read(metadata_path))
        page = archive.read(prefix + "index.html").decode("utf-8")
    return names, prefix, metadata, page


def test_zip_manifest_only_names_included_optional_assets(tmp_path):
    for pdf_state in ("absent", "missing", "empty", "present"):
        folder = tmp_path / pdf_state
        folder.mkdir()
        bundle = _bundle(folder)
        if pdf_state != "absent":
            pdf = folder / "guide.pdf"
            if pdf_state != "missing":
                pdf.write_bytes(b"export PDF fixture" if pdf_state == "present" else b"")
            bundle.pdf_path = str(pdf)
        names, prefix, metadata, page = _export(bundle, folder / "lesson.zip")
        for kind, asset in metadata["assets"].items():
            if kind == "evidence_specs":
                continue
            assert asset is None or prefix + asset in names, (pdf_state, kind, asset)
        assert bool(metadata["assets"]["study_guide_pdf"]) == (pdf_state == "present")
        assert ("href=\"study_guide.pdf\"" in page) == (pdf_state == "present")


def test_prebuilt_export_keeps_all_rendered_chapter_seek_offsets(tmp_path):
    from aetherlab.services.ent_lesson_catalog import accelerated_motion_5min_plan
    from aetherlab.services.lesson_pipeline import _prebuilt_5min_bundle

    for language in ("kk", "ru", "en"):
        bundle = _prebuilt_5min_bundle(accelerated_motion_5min_plan(language))
        names, prefix, metadata, page = _export(bundle, tmp_path / f"{language}.zip")
        assert len(metadata["chapters"]) == 8
        assert all(chapter["rendered"] for chapter in metadata["chapters"])
        assert [chapter["offset_seconds"] for chapter in metadata["chapters"]] == bundle.chapter_offsets
        assert page.count(" data-time=") == 8
        assert "<button disabled" not in page


def test_share_html_and_subtitle_language_match_lesson(tmp_path):
    for language, label in (("kk", "Қазақша"), ("ru", "Русский"), ("en", "English")):
        bundle = _bundle(tmp_path, language)
        srt = Path(bundle.video_path).with_suffix(".srt")
        srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nPhysics\n", encoding="utf-8")
        names, prefix, metadata, page = _export(bundle, tmp_path / f"page-{language}.zip")
        assert f'<html lang="{language}">' in page
        assert f'srclang="{language}"' in page
        assert f'label="{label}"' in page
        assert metadata["language"] == language


def test_portable_page_controls_and_readme_follow_lesson_language(tmp_path):
    labels = {
        "ru": ("Цели урока", "Открыть конспект (PDF)", "Исходник (.tex)", "Открыть исходник конспекта", "Откройте index.html"),
        "kk": ("Сабақ мақсаттары", "Конспектіні ашу (PDF)", "Бастапқы файл (.tex)", "Конспектінің бастапқы файлын ашу", "index.html файлын ашыңыз"),
        "en": ("Objectives", "Open study guide (PDF)", "source (.tex)", "Open study guide source", "Open index.html"),
    }
    for language, expected in labels.items():
        folder = tmp_path / language
        folder.mkdir()
        bundle = _bundle(folder, language)
        bundle.plan.audience = "high_school"
        for has_pdf in (False, True):
            if has_pdf:
                pdf = folder / "guide.pdf"
                pdf.write_bytes(b"synthetic PDF, label check only")
                bundle.pdf_path = str(pdf)
            archive_path = folder / f"{has_pdf}.zip"
            names, prefix, metadata, page = _export(bundle, archive_path)
            assert f"<h2>{expected[0]}</h2>" in page
            assert "high_school" not in page
            if has_pdf:
                assert expected[1] in page and expected[2] in page
            else:
                assert expected[3] in page
            with zipfile.ZipFile(archive_path) as archive:
                readme = archive.read(prefix + "README.txt").decode("utf-8")
            assert expected[4] in readme
