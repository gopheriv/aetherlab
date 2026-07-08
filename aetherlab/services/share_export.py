"""Portable lesson bundle export.

The share bundle is intentionally static: a zip with the lesson video,
subtitles, study guide, chapter scene sources, metadata, and a local HTML
player. It contains no API keys, settings dumps, or absolute local paths.
"""

from __future__ import annotations

import html
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from aetherlab import __version__
from aetherlab.services.pdf import export_lesson_study_guide


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

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    root = _slug(getattr(bundle.plan, "title", "") or "aetherlab-lesson")
    entries: list[str] = []

    with TemporaryDirectory(prefix="aetherlab_share_") as tmp_name:
        tmp = Path(tmp_name)
        study_guide = export_lesson_study_guide(bundle.plan, tmp / "study_guide.tex")
        metadata = _metadata(bundle)
        srt = _subtitle_path(bundle, video)
        vtt_text = _srt_to_vtt(srt.read_text(encoding="utf-8")) if srt else ""
        html_text = _html_player(bundle, metadata, has_track=bool(vtt_text))
        readme_text = _readme(bundle, bool(srt))

        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            _writestr(zf, entries, f"{root}/README.txt", readme_text)
            _writestr(zf, entries, f"{root}/index.html", html_text)
            _writestr(
                zf,
                entries,
                f"{root}/metadata.json",
                json.dumps(metadata, indent=2, ensure_ascii=False),
            )
            _write(zf, entries, study_guide, f"{root}/study_guide.tex")
            _write(zf, entries, video, f"{root}/media/lesson.mp4", zipfile.ZIP_STORED)
            if srt:
                _write(zf, entries, srt, f"{root}/media/lesson.srt")
            if vtt_text:
                _writestr(zf, entries, f"{root}/media/lesson.vtt", vtt_text)
            for idx, scene in enumerate(getattr(bundle, "chapter_scenes", []) or [], 1):
                code = str(getattr(scene, "code", "") or "")
                if not code.strip():
                    continue
                name = _scene_filename(bundle, idx)
                _writestr(zf, entries, f"{root}/scenes/{name}", code)

    return LessonBundleExport(
        path=output_path,
        entries=entries,
        size_bytes=output_path.stat().st_size,
    )


def _metadata(bundle: Any) -> dict[str, Any]:
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
            "subtitles_srt": "media/lesson.srt",
            "subtitles_vtt": "media/lesson.vtt",
            "study_guide": "study_guide.tex",
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


def _html_player(bundle: Any, metadata: dict[str, Any], *, has_track: bool) -> str:
    title = html.escape(metadata["title"] or "AetherLab lesson")
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
        '<track default kind="subtitles" src="media/lesson.vtt" srclang="en" label="English">'
        if has_track
        else ""
    )
    objectives = "".join(
        f"<li>{html.escape(item)}</li>"
        for item in metadata.get("objectives", [])
    )
    return f"""<!doctype html>
<html lang="en">
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
    <div class="meta">{html.escape(metadata.get("audience", ""))} · exported by AetherLab {html.escape(__version__)}</div>
    <video id="lesson" controls preload="metadata" src="media/lesson.mp4">{track}</video>
    <div class="chapters">{''.join(chapters)}</div>
    <section>
      <h2>Objectives</h2>
      <ul>{objectives}</ul>
      <p><a href="study_guide.tex">Open study guide source</a></p>
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


def _readme(bundle: Any, has_srt: bool) -> str:
    title = getattr(bundle.plan, "title", "AetherLab lesson")
    subtitle_note = "Subtitles are included as media/lesson.srt and media/lesson.vtt." if has_srt else "No subtitle file was available for this export."
    return (
        f"{title}\n"
        f"{'=' * len(str(title))}\n\n"
        "Open index.html in a browser to watch the lesson locally.\n"
        "The MP4 is stored at media/lesson.mp4.\n"
        f"{subtitle_note}\n"
        "study_guide.tex contains the printable study guide source.\n"
        "scenes/ contains generated Manim source for rendered chapters.\n"
    )


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
