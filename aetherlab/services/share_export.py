"""Portable lesson bundle export.

The share bundle is intentionally static: a zip with the lesson video,
subtitles, study guide, chapter scene sources, metadata, and a local HTML
player. It contains no API keys, settings dumps, or absolute local paths.
"""

from __future__ import annotations

import html
import json
import os
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from aetherlab import __version__
from aetherlab.core.language import LANGUAGE_NAMES, normalize_language
from aetherlab.services.pdf import export_lesson_study_guide
from aetherlab.services.scene_specification import public_scene_spec


@dataclass(frozen=True)
class LessonBundleExport:
    path: Path
    entries: list[str]
    size_bytes: int


def export_lesson_bundle(bundle: Any, output_path: Path) -> LessonBundleExport:
    """Write a portable lesson zip and return a summary.

    A completed lesson needs an assembled MP4. Subtitles are included when the
    pipeline produced `lesson.srt` or `bundle.srt_path`; the exporter also
    writes a WebVTT copy for the offline HTML player.
    """
    video = Path(str(getattr(bundle, "video_path", "") or ""))
    if not video.is_file() or video.stat().st_size <= 0:
        raise FileNotFoundError("Lesson video is missing; build the lesson before exporting.")
    # Prebuilt lessons (v2 5-minute) ship a typeset study-guide PDF; render
    # path lessons only have the generated .tex source.
    study_pdf = Path(str(getattr(bundle, "pdf_path", "") or ""))
    if not study_pdf.is_file() or study_pdf.stat().st_size <= 0:
        study_pdf = None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    root = _slug(getattr(bundle.plan, "title", "") or "aetherlab-lesson")
    entries: list[str] = []

    # Build into a sibling temp file and atomically replace the target only on
    # full success. A mid-write failure (disk full, missing asset, study-guide
    # error) must never truncate the target or leave a plausible-but-incomplete
    # zip in its place -- that would be exactly the "misleading share bundle"
    # the failure contract forbids, and would destroy a prior good export.
    staging = output_path.with_name(output_path.name + ".part")
    try:
        with TemporaryDirectory(prefix="aetherlab_share_") as tmp_name:
            tmp = Path(tmp_name)
            study_guide = export_lesson_study_guide(bundle.plan, tmp / "study_guide.tex")
            srt = _subtitle_path(bundle, video)
            vtt_text = _srt_to_vtt(srt.read_text(encoding="utf-8")) if srt else ""
            metadata = _metadata(bundle, has_srt=bool(srt), has_vtt=bool(vtt_text), has_pdf=study_pdf is not None)
            html_text = _html_player(bundle, metadata, has_track=bool(vtt_text),
                                     has_pdf=study_pdf is not None)
            readme_text = _readme(bundle, bool(srt), has_pdf=study_pdf is not None)

            with zipfile.ZipFile(staging, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                _writestr(zf, entries, f"{root}/README.txt", readme_text)
                _writestr(zf, entries, f"{root}/index.html", html_text)
                _writestr(
                    zf,
                    entries,
                    f"{root}/metadata.json",
                    json.dumps(metadata, indent=2, ensure_ascii=False),
                )
                _write(zf, entries, study_guide, f"{root}/study_guide.tex")
                if study_pdf is not None:
                    _write(zf, entries, study_pdf, f"{root}/study_guide.pdf")
                _write(zf, entries, video, f"{root}/media/lesson.mp4", zipfile.ZIP_STORED)
                if srt:
                    _write(zf, entries, srt, f"{root}/media/lesson.srt")
                if vtt_text:
                    _writestr(zf, entries, f"{root}/media/lesson.vtt", vtt_text)
                for idx, scene in enumerate(getattr(bundle, "chapter_scenes", []) or [], 1):
                    code = str(getattr(scene, "code", "") or "")
                    if code.strip():
                        name = _scene_filename(bundle, idx)
                        _writestr(zf, entries, f"{root}/scenes/{name}", code)
                    spec = public_scene_spec(getattr(scene, "scene_spec", None))
                    if spec is not None:
                        _writestr(
                            zf,
                            entries,
                            f"{root}/evidence/scene_{idx:02d}.json",
                            json.dumps(spec, indent=2, ensure_ascii=False),
                        )

        os.replace(staging, output_path)
    except BaseException:
        try:
            staging.unlink()
        except OSError:
            pass
        raise

    return LessonBundleExport(
        path=output_path,
        entries=entries,
        size_bytes=output_path.stat().st_size,
    )


def _metadata(bundle: Any, *, has_srt: bool = False, has_vtt: bool = False, has_pdf: bool = False) -> dict[str, Any]:
    plan = bundle.plan
    offsets = [float(x) for x in getattr(bundle, "chapter_offsets", []) or []]
    rendered = list(getattr(bundle, "rendered_chapter_indexes", []) or [])
    rendered_map = {
        int(plan_index): render_index
        for render_index, plan_index in enumerate(rendered)
        if isinstance(plan_index, int)
    }
    if not rendered_map:
        rendered_map = {
            i: i
            for i, _scene in enumerate(getattr(bundle, "chapter_scenes", []) or [])
        }
    evidence_specs = [
        f"evidence/scene_{index:02d}.json"
        for index, scene in enumerate(getattr(bundle, "chapter_scenes", []) or [], 1)
        if public_scene_spec(getattr(scene, "scene_spec", None)) is not None
    ]
    chapters = []
    for idx, chapter in enumerate(getattr(plan, "chapters", []) or []):
        render_index = rendered_map.get(idx)
        chapters.append(
            {
                "index": idx + 1,
                "title": str(getattr(chapter, "title", "")),
                "kind": str(getattr(chapter, "kind", "")),
                "goal": str(getattr(chapter, "goal", "")),
                "narration": str(getattr(chapter, "narration", "")),
                "key_equations": [str(x) for x in getattr(chapter, "key_equations", [])],
                "citations": [str(x) for x in getattr(chapter, "citations", [])],
                "rendered": render_index is not None,
                "offset_seconds": (
                    offsets[render_index]
                    if render_index is not None and render_index < len(offsets)
                    else None
                ),
            }
        )
    return {
        "schema": "aetherlab.lesson_bundle.v1",
        "app": "AetherLab",
        "app_version": __version__,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "title": str(getattr(plan, "title", "")),
        "topic": str(getattr(plan, "topic", "")),
        "audience": str(getattr(plan, "audience", "")),
        "language": normalize_language(getattr(plan, "language", "en")),
        "status": str(getattr(bundle, "status", "")),
        "objectives": [str(x) for x in getattr(plan, "objectives", [])],
        "prerequisites": [str(x) for x in getattr(plan, "prerequisites", [])],
        "misconception": str(getattr(plan, "misconception", "")),
        "chapters": chapters,
        "questions": [
            {
                "question": str(getattr(q, "q", "")),
                "choices": [str(x) for x in getattr(q, "choices", [])],
                "answer": str(getattr(q, "answer", "")),
                "why": str(getattr(q, "why", "")),
            }
            for q in getattr(plan, "questions", []) or []
        ],
        "assets": {
            "video": "media/lesson.mp4",
            "subtitles_srt": "media/lesson.srt" if has_srt else None,
            "subtitles_vtt": "media/lesson.vtt" if has_vtt else None,
            "study_guide": "study_guide.tex",
            "study_guide_pdf": "study_guide.pdf" if has_pdf else None,
            "evidence_specs": evidence_specs,
        },
    }


def _subtitle_path(bundle: Any, video: Path) -> Path | None:
    raw_srt_path = str(getattr(bundle, "srt_path", "") or "")
    candidates = []
    if raw_srt_path:
        candidates.append(Path(raw_srt_path))
    candidates.extend([video.with_suffix(".srt"), video.parent / "lesson.srt"])
    for candidate in candidates:
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate
    return None


def _scene_filename(bundle: Any, render_index: int) -> str:
    rendered = list(getattr(bundle, "rendered_chapter_indexes", []) or [])
    plan_index = (
        int(rendered[render_index - 1])
        if render_index - 1 < len(rendered) and isinstance(rendered[render_index - 1], int)
        else render_index - 1
    )
    chapters = list(getattr(bundle.plan, "chapters", []) or [])
    title = (
        getattr(chapters[plan_index], "title", "")
        if 0 <= plan_index < len(chapters)
        else f"chapter-{render_index}"
    )
    return f"chapter_{plan_index + 1:02d}_{_slug(title)}.py"


def _html_player(bundle: Any, metadata: dict[str, Any], *, has_track: bool,
                 has_pdf: bool = False) -> str:
    language = normalize_language(metadata.get("language", getattr(bundle.plan, "language", "en")))
    labels = _portable_labels(language)
    language_label = html.escape(LANGUAGE_NAMES[language])
    title = html.escape(metadata["title"] or labels["lesson"])
    chapters = []
    for chapter in metadata["chapters"]:
        offset = chapter["offset_seconds"]
        disabled = " disabled" if offset is None else ""
        data_time = "" if offset is None else f' data-time="{float(offset):.3f}"'
        chapters.append(
            f"<button{disabled}{data_time}>"
            f"{chapter['index']}. {html.escape(chapter['title'])}</button>"
        )
    track = (
        f'<track default kind="subtitles" src="media/lesson.vtt" srclang="{language}" label="{language_label}">'
        if has_track
        else ""
    )
    objectives = "".join(
        f"<li>{html.escape(item)}</li>"
        for item in metadata.get("objectives", [])
    )
    guide_link = (
        f'<p><a href="study_guide.pdf">{labels["pdf"]}</a> · '
        f'<a href="study_guide.tex">{labels["source"]}</a></p>'
        if has_pdf else
        f'<p><a href="study_guide.tex">{labels["source_only"]}</a></p>'
    )
    audience = metadata.get("audience", "")
    audience_label = labels["school"] if audience == "high_school" else str(audience)
    return f"""<!doctype html>
<html lang="{language}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{ margin: 0; font-family: Inter, system-ui, sans-serif; background: #0A0A0F; color: #E2E8F0; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 28px 18px 40px; }}
    h1 {{ font-size: 28px; margin: 0 0 8px; color: #F8FAFC; }}
    .meta {{ color: #94A3B8; margin-bottom: 18px; }}
    video {{ width: 100%; background: #000; border: 1px solid #1E293B; }}
    .chapters {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0; }}
    button {{ color: #E2E8F0; background: #181822; border: 1px solid #334155; border-radius: 6px; padding: 8px 10px; cursor: pointer; }}
    button:hover {{ border-color: #22D3EE; }}
    button:disabled {{ color: #64748B; cursor: default; }}
    section {{ border-top: 1px solid #1E293B; margin-top: 22px; padding-top: 18px; }}
    a {{ color: #22D3EE; }}
  </style>
</head>
<body>
  <main>
    <h1>{title}</h1>
    <div class="meta">{html.escape(audience_label)} · {labels["exported"]} PhysLab {html.escape(__version__)}</div>
    <video id="lesson" controls preload="metadata" src="media/lesson.mp4">{track}</video>
    <div class="chapters">{''.join(chapters)}</div>
    <section>
      <h2>{labels["objectives"]}</h2>
      <ul>{objectives}</ul>
      {guide_link}
    </section>
  </main>
  <script>
    const video = document.getElementById('lesson');
    document.querySelectorAll('[data-time]').forEach(button => {{
      button.addEventListener('click', () => {{
        video.currentTime = Number(button.dataset.time || 0);
        video.play();
      }});
    }});
  </script>
</body>
</html>
"""


def _readme(bundle: Any, has_srt: bool, *, has_pdf: bool = False) -> str:
    labels = _portable_labels(normalize_language(getattr(bundle.plan, "language", "en")))
    title = getattr(bundle.plan, "title", "") or labels["lesson"]
    subtitle_note = labels["subtitles"] if has_srt else labels["no_subtitles"]
    guide_note = labels["pdf_note"] if has_pdf else labels["tex_note"]
    return (
        f"{title}\n"
        f"{'=' * len(str(title))}\n\n"
        f'{labels["open"]}\n'
        f'{labels["video"]}\n'
        f"{subtitle_note}\n"
        f"{guide_note}\n"
        f'{labels["scenes"]}\n'
    )


def _portable_labels(language: str) -> dict[str, str]:
    return {
        "ru": {
            "lesson": "Урок PhysLab", "objectives": "Цели урока",
            "pdf": "Открыть конспект (PDF)", "source": "Исходник (.tex)",
            "source_only": "Открыть исходник конспекта", "school": "Для школьников",
            "exported": "Экспортировано из",
            "open": "Откройте index.html в браузере для просмотра урока на своём устройстве.",
            "video": "Видео MP4 находится в media/lesson.mp4.",
            "subtitles": "Субтитры находятся в media/lesson.srt и media/lesson.vtt.",
            "no_subtitles": "При экспорте файл субтитров отсутствовал.",
            "pdf_note": "study_guide.pdf — конспект для печати; study_guide.tex — его исходник.",
            "tex_note": "study_guide.tex содержит исходник конспекта для печати.",
            "scenes": "В scenes/ находятся исходники Manim отрендеренных глав.",
        },
        "kk": {
            "lesson": "PhysLab сабағы", "objectives": "Сабақ мақсаттары",
            "pdf": "Конспектіні ашу (PDF)", "source": "Бастапқы файл (.tex)",
            "source_only": "Конспектінің бастапқы файлын ашу", "school": "Оқушыларға арналған",
            "exported": "Экспорт көзі:",
            "open": "Сабақты өз құрылғыңызда көру үшін браузерде index.html файлын ашыңыз.",
            "video": "MP4 бейнесі media/lesson.mp4 файлында орналасқан.",
            "subtitles": "Субтитрлер media/lesson.srt және media/lesson.vtt файлдарында орналасқан.",
            "no_subtitles": "Экспорт кезінде субтитр файлы болмады.",
            "pdf_note": "study_guide.pdf — басып шығарылатын конспект; study_guide.tex — оның бастапқы файлы.",
            "tex_note": "study_guide.tex басып шығарылатын конспектінің бастапқы файлын қамтиды.",
            "scenes": "scenes/ бумасында дайын тараулардың Manim бастапқы коды орналасқан.",
        },
        "en": {
            "lesson": "PhysLab lesson", "objectives": "Objectives",
            "pdf": "Open study guide (PDF)", "source": "source (.tex)",
            "source_only": "Open study guide source", "school": "For school students",
            "exported": "exported by",
            "open": "Open index.html in a browser to watch the lesson locally.",
            "video": "The MP4 is stored at media/lesson.mp4.",
            "subtitles": "Subtitles are included as media/lesson.srt and media/lesson.vtt.",
            "no_subtitles": "No subtitle file was available for this export.",
            "pdf_note": "study_guide.pdf is the printable study guide (study_guide.tex is its source).",
            "tex_note": "study_guide.tex contains the printable study guide source.",
            "scenes": "scenes/ contains generated Manim source for rendered chapters.",
        },
    }[language]


def _srt_to_vtt(text: str) -> str:
    lines = text.replace("\ufeff", "").splitlines()
    out = ["WEBVTT", ""]
    for line in lines:
        if "-->" in line:
            out.append(line.replace(",", "."))
        elif line.strip().isdigit():
            continue
        else:
            out.append(line)
    return "\n".join(out).strip() + "\n"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:64] or "aetherlab-lesson"


def _write(
    zf: zipfile.ZipFile,
    entries: list[str],
    source: Path,
    arcname: str,
    compress_type: int | None = None,
) -> None:
    if compress_type is None:
        zf.write(source, arcname)
    else:
        zf.write(source, arcname, compress_type=compress_type)
    entries.append(arcname)


def _writestr(
    zf: zipfile.ZipFile,
    entries: list[str],
    arcname: str,
    data: str,
) -> None:
    zf.writestr(arcname, data)
    entries.append(arcname)
