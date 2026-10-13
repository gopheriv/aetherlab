"""Build one source-grounded ENT lesson package and its derived media.

The JSON route is the single content source for the 3 PDFs, narrated videos,
and subtitle tracks. Run the PDF path with the bundled workspace Python.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LANGUAGE_NAMES = {"kk": "Қазақша", "ru": "Русский", "en": "English"}
VOICES = {
    "kk": "kk-KZ-AigulNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "en": "en-US-AndrewMultilingualNeural",
}
ROUTE_FILE = ROOT / "content" / "ent" / "constant_acceleration_route.json"
TMP_ROOT = ROOT / "tmp" / "accelerated_motion_route"
VIDEO_DIR = ROOT / "output" / "video"
PDF_DIR = ROOT / "output" / "pdf"
BOOK_NAME = "Физика Закирова 10 ЖМ.pdf"
QUESTION_NAME = "Testcenter -3.pdf"
SPEC_URL = (
    "https://testcenter.kz/wp-content/uploads/2025/10/12_"
    "%D0%A4%D0%B8%D0%B7%D0%B8%D0%BA%D0%B0_%D1%80%D1%83%D1%81.pdf"
)


def write_canonical_route() -> dict:
    from aetherlab.services.ent_lesson_catalog import route_content

    payload = {
        "route_id": "constant_acceleration",
        "version": "physlab-ent-constant-acceleration-v1",
        "source_hash": "cc39b02f972aff31dfca / 966d33a26005cb58b7cb",
        "review_status": {
            "physics_and_source_key": "checked",
            "kk_ru_en_wording": "draft_needs_teacher_review",
            "voice_and_visual_timing": "verified_from_generated_media",
        },
        "verified_question_visual": route_content("ru")["verified_question_visual"],
        "common_mistakes": {
            language: route_content(language)["common_mistakes"]
            for language in ("kk", "ru", "en")
        },
        "lessons": {
            language: route_content(language) for language in ("kk", "ru", "en")
        },
    }
    ROUTE_FILE.parent.mkdir(parents=True, exist_ok=True)
    ROUTE_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return payload


def _load_route() -> dict:
    payload = json.loads(ROUTE_FILE.read_text(encoding="utf-8"))
    if payload.get("version") != "physlab-ent-constant-acceleration-v1":
        raise ValueError("Unexpected lesson route version")
    graph = payload["verified_question_visual"]
    if sum(graph["area_segments_m"]) != graph["answer_m"]:
        raise ValueError("The imported NCT graph areas do not match the checked key")
    if graph["choice_id"] != "B" or graph["answer_m"] != 12:
        raise ValueError("The imported NCT answer no longer matches its reviewed source")
    return payload


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    words = str(text).split()
    lines: list[str] = []
    row = ""
    for word in words:
        candidate = f"{row} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width or not row:
            row = candidate
        else:
            lines.append(row)
            row = word
    if row:
        lines.append(row)
    return lines


def _slide_image(language: str, chapter: dict, question_visual: dict, path: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    width, height = 1280, 720
    image = Image.new("RGB", (width, height), "#081724")
    draw = ImageDraw.Draw(image)
    small = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 18)
    title_font = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 37)
    body_font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 25)
    bold = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 22)
    draw.rounded_rectangle((38, 34, 1242, 686), radius=26, fill="#102638", outline="#25445A", width=2)
    draw.rounded_rectangle((38, 34, 1242, 90), radius=24, fill="#132F42")
    draw.text((66, 50), "PHYSLAB  /  ЕНТ • ҰБТ  /  " + LANGUAGE_NAMES[language], font=small, fill="#9AB3C4")
    draw.text((66, 118), chapter["title"], font=title_font, fill="#F2F6F8")
    draw.rounded_rectangle((66, 179, 1214, 186), radius=3, fill="#2BD6BC")

    graph_chapter = chapter["id"] in {"displacement", "ent-question"}
    text_right = 748 if graph_chapter else 1160
    y = 222
    for index, beat in enumerate(chapter.get("beats", [])):
        draw.ellipse((74, y + 9, 88, y + 23), fill="#2BD6BC")
        lines = _wrap(draw, beat, body_font, text_right - 120)
        for line in lines:
            draw.text((106, y), line, font=body_font, fill="#E1EAF0")
            y += 38
        y += 19

    if chapter["id"] == "worked-example":
        draw.rounded_rectangle((66, 586, 1214, 648), radius=14, fill="#17384A")
        draw.text((88, 602), "v = 8 m/s     •     s = 20 m", font=bold, fill="#A7F3D0")
    elif chapter["id"] == "recap":
        draw.rounded_rectangle((66, 586, 1214, 648), radius=14, fill="#17384A")
        draw.text((88, 602), "v = v₀ + at       |       s = v₀t + at²/2", font=bold, fill="#A7F3D0")
    elif graph_chapter:
        _draw_graph(draw, question_visual, chapter["id"] == "ent-question")
    else:
        _draw_speed_ramp(draw, y)
    footer = "Нұсқаулық: үдеу тұрақты, қозғалыс түзу сызық бойымен қарастырылады." if language == "kk" else (
        "Условия: ускорение постоянно, движение рассматривается вдоль прямой." if language == "ru" else
        "Assumptions: acceleration is constant and motion is along a straight line."
    )
    draw.text((66, 656), footer, font=small, fill="#8EA8B8")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=True)


def _draw_speed_ramp(draw, y: int) -> None:
    from PIL import ImageFont

    left, bottom = 830, 564
    draw.text((left, 226), "0  →  2  →  4  →  6  →  8 m/s", font=ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 25), fill="#A7F3D0")
    draw.line((left, bottom, 1175, bottom), fill="#6D8797", width=3)
    for i, value in enumerate((0, 2, 4, 6, 8)):
        x = left + i * 78
        bar_h = 20 + i * 31
        draw.rounded_rectangle((x, bottom - bar_h, x + 34, bottom), radius=6, fill="#2BD6BC" if i < 4 else "#F0B84A")
        draw.text((x - 2, bottom + 8), f"{i} s", font=ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 14), fill="#A9BAC6")


def _draw_graph(draw, graph: dict, exam_question: bool) -> None:
    from PIL import ImageFont

    x0, y0, gw, gh = 846, 555, 300, 260
    draw.text((x0 - 10, 220), "v (m/s)" if exam_question else "v = v₀ + at", font=ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 24), fill="#A7F3D0")
    sx, sy = gw / 4.0, gh / 4.0
    def xy(x, y):
        return (x0 + x * sx, y0 - y * sy)
    points = graph["graph_points_time_s_velocity_mps"]
    origin = xy(0, 0)
    p1, p2, p3, p4 = [xy(x, y) for x, y in points]
    draw.line((x0, y0, x0 + gw + 15, y0), fill="#9AB3C4", width=2)
    draw.line((x0, y0, x0, y0 - gh - 12), fill="#9AB3C4", width=2)
    for tick in range(5):
        tx = x0 + tick * sx
        ty = y0 - tick * sy
        draw.line((tx, y0 - 4, tx, y0 + 4), fill="#9AB3C4", width=2)
        draw.line((x0 - 4, ty, x0 + 4, ty), fill="#9AB3C4", width=2)
        draw.text((tx - 4, y0 + 7), str(tick), font=ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 14), fill="#A9BAC6")
        draw.text((x0 - 24, ty - 8), str(tick), font=ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 14), fill="#A9BAC6")
    if exam_question:
        areas = graph["area_segments_m"]
        polygons = [
            [xy(0, 0), xy(1, 0), p1],
            [xy(1, 0), p1, p2, xy(3, 0)],
            [xy(3, 0), p2, p3],
        ]
        label_positions = [(0.45, 0.65), (2.0, 2.0), (3.55, 0.65)]
        for polygon, color, label, label_pos in zip(
            polygons, ("#F0B84A", "#2BD6BC", "#A879F8"), areas, label_positions
        ):
            draw.polygon(polygon, fill=color)
            mid_x, mid_y = xy(*label_pos)
            draw.text((mid_x - 18, mid_y - 10), f"{label} m", font=ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 15), fill="#081724")
        draw.line((origin, p1, p2, p3, p4), fill="#F2F6F8", width=4)
        draw.text((x0 + 70, y0 + 45), "s = 2 + 8 + 2 = 12 m", font=ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 17), fill="#F2F6F8")
    else:
        draw.line((xy(0, 0), xy(4, 4)), fill="#2BD6BC", width=4)
    for x, y in points:
        px, py = xy(x, y)
        draw.ellipse((px - 5, py - 5, px + 5, py + 5), fill="#F2F6F8")
    draw.text((x0 + gw - 6, y0 + 8), "t (s)", font=ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 14), fill="#A9BAC6")


def _clock(seconds: float) -> str:
    total_ms = max(0, round(seconds * 1000))
    hours, remain = divmod(total_ms, 3_600_000)
    minutes, remain = divmod(remain, 60_000)
    secs, ms = divmod(remain, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


async def _tts_chapter(text: str, voice: str, mp3_path: Path) -> list[dict]:
    import edge_tts

    communicator = edge_tts.Communicate(text, voice, boundary="WordBoundary")
    audio_parts: list[bytes] = []
    words: list[dict] = []
    async for event in communicator.stream():
        if event.get("type") == "audio":
            audio_parts.append(event["data"])
        elif event.get("type") == "WordBoundary":
            # edge-tts exposes timing metadata at the top level of the event.
            data = event
            words.append(
                {
                    "text": str(data.get("text", "")).strip(),
                    "start": int(data.get("offset", 0)) / 10_000_000,
                    "duration": int(data.get("duration", 0)) / 10_000_000,
                }
            )
    if not audio_parts:
        raise RuntimeError(f"Voice service returned no audio for {voice}")
    mp3_path.parent.mkdir(parents=True, exist_ok=True)
    mp3_path.write_bytes(b"".join(audio_parts))
    return words


def _audio_duration(path: Path) -> float:
    import av

    with av.open(str(path)) as container:
        if container.duration:
            return container.duration / 1_000_000
        stream = container.streams.audio[0]
        return sum(frame.samples / frame.sample_rate for frame in container.decode(stream))


def _write_video_only(slides: list[tuple[Path, float]], path: Path, fps: int = 24) -> None:
    from fractions import Fraction

    import av
    import numpy as np
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    container = av.open(str(path), mode="w", format="mp4")
    stream = container.add_stream("libx264", rate=fps)
    stream.width = 1280
    stream.height = 720
    stream.pix_fmt = "yuv420p"
    stream.options = {"preset": "ultrafast", "crf": "24"}
    frame_no = 0
    try:
        for slide, seconds in slides:
            pixels = np.asarray(Image.open(slide).convert("RGB"))
            for _ in range(max(1, math.ceil(seconds * fps))):
                frame = av.VideoFrame.from_ndarray(pixels, format="rgb24")
                frame.pts = frame_no
                frame.time_base = Fraction(1, fps)
                frame_no += 1
                for packet in stream.encode(frame):
                    container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    finally:
        container.close()


def _write_srt(chapters: list[tuple[list[dict], float, float]], out_path: Path) -> None:
    rows: list[str] = []
    cue = 1
    for words, duration, offset in chapters:
        valid = [w for w in words if w["text"] and 0 <= w["start"] < duration]
        if valid:
            group: list[dict] = []
            for word in valid:
                if group and len(group) >= 7:
                    _append_cue(rows, cue, group, offset, duration)
                    cue += 1
                    group = []
                group.append(word)
            if group:
                _append_cue(rows, cue, group, offset, duration)
                cue += 1
        else:
            raise RuntimeError("TTS did not return word timings; refusing untimed subtitle fallback")
    out_path.write_text("\n".join(rows), encoding="utf-8-sig")


def _append_cue(rows: list[str], number: int, words: list[dict], offset: float, duration: float) -> None:
    start = max(0.0, words[0]["start"])
    end = min(duration, max(start + 0.25, words[-1]["start"] + words[-1]["duration"]))
    text = " ".join(word["text"] for word in words)
    rows.extend([str(number), f"{_clock(offset + start)} --> {_clock(offset + end)}", text, ""])


def _run_video_command(ffmpeg: str, audio_paths: list[Path], video_only: Path, output: Path) -> None:
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
    for path in audio_paths:
        cmd += ["-i", str(path)]
    inputs = "".join(f"[{i}:a]" for i in range(len(audio_paths)))
    cmd += [
        "-filter_complex", f"{inputs}concat=n={len(audio_paths)}:v=0:a=1[aout]",
        "-map", "[aout]", "-vn", "-c:a", "aac", "-b:a", "160k", str(video_only.with_suffix(".m4a")),
    ]
    subprocess.run(cmd, check=True)
    final_tmp = output.with_name(output.stem + ".tmp.mp4")
    subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(video_only),
         "-i", str(video_only.with_suffix(".m4a")), "-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "copy", "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(final_tmp)],
        check=True,
    )
    final_tmp.replace(output)


async def build_videos(payload: dict) -> list[Path]:
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    outputs: list[Path] = []
    for language in ("kk", "ru", "en"):
        lesson = payload["lessons"][language]
        content = lesson["content"]
        source_visual = payload["verified_question_visual"]
        work = TMP_ROOT / payload["version"] / language / uuid.uuid4().hex[:10]
        work.mkdir(parents=True)
        audio_paths: list[Path] = []
        slides: list[tuple[Path, float]] = []
        subtitle_segments: list[tuple[list[dict], float, float]] = []
        clock = 0.0
        for index, chapter in enumerate(content["chapters"]):
            audio = work / f"chapter-{index:02d}.mp3"
            marks = await _tts_chapter(chapter["narration"], VOICES[language], audio)
            duration = _audio_duration(audio)
            if duration <= 0:
                raise RuntimeError(f"Could not read TTS duration for {language} chapter {index}")
            slide = work / f"chapter-{index:02d}.png"
            _slide_image(language, chapter, source_visual, slide)
            audio_paths.append(audio)
            slides.append((slide, duration))
            subtitle_segments.append((marks, duration, clock))
            clock += duration
        video_only = work / "lesson-video-only.mp4"
        _write_video_only(slides, video_only)
        output = VIDEO_DIR / f"physlab_ent_constant_acceleration_v1_{language}.mp4"
        VIDEO_DIR.mkdir(parents=True, exist_ok=True)
        _run_video_command(ffmpeg, audio_paths, video_only, output)
        srt = VIDEO_DIR / f"physlab_ent_constant_acceleration_v1_{language}.srt"
        _write_srt(subtitle_segments, srt)
        _verify_video(ffmpeg, output, audio_paths, language)
        outputs.extend([output, srt])
    outputs.extend(publish_voiceovers(payload))
    return outputs


def publish_voiceovers(payload: dict) -> list[Path]:
    """Publish the exact concatenated AAC voice track embedded in each MP4."""
    import av

    output_dir = ROOT / "output" / "audio"
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for language in ("kk", "ru", "en"):
        candidates = list(
            (TMP_ROOT / payload["version"] / language).glob("*/lesson-video-only.m4a")
        )
        if not candidates:
            raise FileNotFoundError(f"No concatenated {language} voice track found")
        source = max(candidates, key=lambda path: path.stat().st_mtime_ns)
        matching_video = source.with_suffix(".mp4")
        published_video = VIDEO_DIR / f"physlab_ent_constant_acceleration_v1_{language}.mp4"
        if not matching_video.is_file() or not published_video.is_file():
            raise FileNotFoundError(f"Missing paired {language} video for voice track")
        source_duration = _audio_duration(source)
        with av.open(str(published_video)) as container:
            video_duration = container.duration / 1_000_000
            if not container.streams.audio:
                raise RuntimeError(f"Published {language} video has no voice track")
        if abs(source_duration - video_duration) > max(0.4, video_duration * 0.01):
            raise RuntimeError(f"{language} standalone voice track does not match its video")
        target = output_dir / f"physlab_ent_constant_acceleration_v1_{language}.m4a"
        partial = target.with_name(target.stem + f".{uuid.uuid4().hex[:8]}.tmp.m4a")
        shutil.copyfile(source, partial)
        with av.open(str(partial)) as container:
            if not container.streams.audio or not container.duration:
                partial.unlink(missing_ok=True)
                raise RuntimeError(f"Standalone {language} audio failed to reopen")
        partial.replace(target)
        outputs.append(target)
    return outputs


def _verify_video(ffmpeg: str, path: Path, audio_paths: list[Path], language: str) -> None:
    import av

    expected_duration = sum(_audio_duration(item) for item in audio_paths)
    with av.open(str(path)) as container:
        if not container.streams.video or not container.streams.audio:
            raise RuntimeError(f"{language} MP4 is missing video or audio")
        actual = container.duration / 1_000_000 if container.duration else 0
        if actual <= 0 or abs(actual - expected_duration) > max(0.4, expected_duration * 0.01):
            raise RuntimeError(
                f"{language} audiovisual durations diverge: {actual:.2f}s vs {expected_duration:.2f}s"
            )
        if (container.streams.video[0].width, container.streams.video[0].height) != (1280, 720):
            raise RuntimeError(f"Unexpected {language} output dimensions")
    if path.stat().st_size < 25_000:
        raise RuntimeError(f"Suspiciously small {language} MP4: {path.stat().st_size} bytes")


def _pdf_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    regular = Path(r"C:\Windows\Fonts\arial.ttf")
    bold = Path(r"C:\Windows\Fonts\arialbd.ttf")
    if not regular.exists() or not bold.exists():
        raise FileNotFoundError("Arial Unicode fonts are needed for Kazakh PDF text")
    pdfmetrics.registerFont(TTFont("PhysArial", str(regular)))
    pdfmetrics.registerFont(TTFont("PhysArialBold", str(bold)))


def build_pdfs(payload: dict) -> list[Path]:
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        BaseDocTemplate,
        Flowable,
        Frame,
        PageBreak,
        PageTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )

    _pdf_fonts()
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    ink = colors.HexColor("#102638")
    teal = colors.HexColor("#0C9D8C")
    pale = colors.HexColor("#EAF6F3")
    muted = colors.HexColor("#51687A")
    styles = {
        "title": ParagraphStyle("title", fontName="PhysArialBold", fontSize=21, leading=25, textColor=ink, spaceAfter=8),
        "sub": ParagraphStyle("sub", fontName="PhysArial", fontSize=9.5, leading=13, textColor=muted, spaceAfter=12),
        "h": ParagraphStyle("h", fontName="PhysArialBold", fontSize=13.4, leading=17, textColor=teal, spaceBefore=7, spaceAfter=5),
        "body": ParagraphStyle("body", fontName="PhysArial", fontSize=10.2, leading=14.4, textColor=ink, spaceAfter=5),
        "small": ParagraphStyle("small", fontName="PhysArial", fontSize=8.2, leading=11, textColor=muted, spaceAfter=3),
        "cell": ParagraphStyle("cell", fontName="PhysArial", fontSize=9, leading=12, textColor=ink),
        "cell_b": ParagraphStyle("cell_b", fontName="PhysArialBold", fontSize=9, leading=12, textColor=ink),
        "formula": ParagraphStyle("formula", fontName="PhysArialBold", fontSize=12.4, leading=17, textColor=ink, backColor=pale, borderPadding=7, spaceBefore=2, spaceAfter=7),
    }

    class Graph(Flowable):
        def __init__(self, graph: dict, width=500, height=145):
            super().__init__()
            self.graph, self.width, self.height = graph, width, height

        def draw(self):
            c = self.canv
            x0, y0 = 42, 20
            w, h = self.width - 62, self.height - 38
            c.setStrokeColor(colors.HexColor("#7D93A2"))
            c.setLineWidth(0.8)
            c.line(x0, y0, x0 + w, y0)
            c.line(x0, y0, x0, y0 + h)
            sx, sy = w / 4, h / 4
            c.setFont("PhysArial", 7.5)
            for tick in range(5):
                tx, ty = x0 + tick * sx, y0 + tick * sy
                c.line(tx, y0 - 2, tx, y0 + 2)
                c.line(x0 - 2, ty, x0 + 2, ty)
                c.drawCentredString(tx, y0 - 12, str(tick))
                c.drawRightString(x0 - 6, ty - 2.5, str(tick))
            palette = [colors.HexColor("#F0B84A"), colors.HexColor("#0C9D8C"), colors.HexColor("#9572DC")]
            points = self.graph["graph_points_time_s_velocity_mps"]
            polygons = [
                ((0, 0), (1, 0), (1, 4)),
                ((1, 0), (1, 4), (3, 4), (3, 0)),
                ((3, 0), (3, 4), (4, 0)),
            ]
            labels_at = [(0.45, 0.7), (2.0, 2.0), (3.55, 0.7)]
            for idx, polygon_points in enumerate(polygons):
                p = c.beginPath()
                p.moveTo(x0 + polygon_points[0][0] * sx, y0 + polygon_points[0][1] * sy)
                for px, py in polygon_points[1:]:
                    p.lineTo(x0 + px * sx, y0 + py * sy)
                p.close()
                c.setFillColor(palette[idx])
                c.setFillAlpha(0.18)
                c.drawPath(p, stroke=0, fill=1)
                c.setFillAlpha(1)
                c.setFillColor(ink)
                c.setFont("PhysArialBold", 8.2)
                label_t, label_v = labels_at[idx]
                c.drawCentredString(x0 + label_t * sx, y0 + label_v * sy, f"{self.graph['area_segments_m'][idx]} m")
            c.setStrokeColor(ink)
            c.setLineWidth(2)
            prev = None
            for t, v in points:
                point = (x0 + t * sx, y0 + v * sy)
                if prev:
                    c.line(prev[0], prev[1], point[0], point[1])
                c.setFillColor(teal)
                c.circle(point[0], point[1], 2.5, stroke=0, fill=1)
                prev = point
            c.setFont("PhysArial", 8)
            c.setFillColor(muted)
            c.drawRightString(x0 + w, 3, "t, s")
            c.drawString(2, y0 + h - 3, "v, m/s")

    class LessonDoc(BaseDocTemplate):
        def __init__(self, filename, language):
            super().__init__(str(filename), pagesize=A4, leftMargin=17 * mm, rightMargin=17 * mm,
                             topMargin=19 * mm, bottomMargin=15 * mm, title="PhysLab ENT - constant acceleration")
            frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="lesson")
            self.addPageTemplates([PageTemplate(id="physlab", frames=[frame], onPage=self._draw_header)])
            self.language = language

        def _draw_header(self, canvas, doc):
            canvas.saveState()
            canvas.setFillColor(ink)
            canvas.rect(0, A4[1] - 11 * mm, A4[0], 11 * mm, stroke=0, fill=1)
            canvas.setFillColor(colors.white)
            canvas.setFont("PhysArialBold", 8.5)
            canvas.drawString(17 * mm, A4[1] - 7.4 * mm, f"PHYSLAB  /  ЕНТ • ҰБТ  /  {LANGUAGE_NAMES[self.language]}")
            canvas.setStrokeColor(colors.HexColor("#D7E2E8"))
            canvas.line(17 * mm, 11 * mm, A4[0] - 17 * mm, 11 * mm)
            canvas.setFillColor(muted)
            canvas.setFont("PhysArial", 8)
            canvas.drawString(17 * mm, 7 * mm, "Version v1  •  theory + source-based practice")
            canvas.drawRightString(A4[0] - 17 * mm, 7 * mm, str(doc.page))
            canvas.restoreState()

    def para(text, style="body"):
        safe = str(text).replace("–", "-").replace("—", "-").replace("‑", "-")
        return Paragraph(escape(safe).replace("\n", "<br/>"), styles[style])

    outputs = []
    for language in ("kk", "ru", "en"):
        lesson = payload["lessons"][language]
        content = lesson["content"]
        chapters = {chapter["id"]: chapter for chapter in content["chapters"]}
        graph = payload["verified_question_visual"]
        if language == "kk":
            labels = {
                "page1": "Алдымен мағынасын түсінейік", "terms": "Қазақша негізгі терминдер", "page2": "Шамалар, формула және мысал",
                "conditions": "Қолдану шарты", "symbols": "Белгілер мен өлшем бірліктері", "example": "Бірге шығарайық",
                "page3": "ЕНТ-дағы график есебі", "solve": "Шешуі және тексеру", "mistakes": "Жиі кездесетін қателер",
                "review": "Статус: физика мен бастапқы кілт тексерілді; аударма мен терминдерді мұғалім тексеруі керек.",
                "source": "Дереккөздер", "question": "4 секундтағы жүрген жолды табыңыз.",
            }
        elif language == "ru":
            labels = {
                "page1": "Сначала поймём смысл", "terms": "Казахские термины простыми словами", "page2": "Величины, формула и пример",
                "conditions": "Когда применять", "symbols": "Обозначения и единицы", "example": "Решим вместе",
                "page3": "Задача по графику из сборника ЕНТ", "solve": "Решение и проверка", "mistakes": "Частые ошибки",
                "review": "Статус: физика и исходный ключ проверены; перевод и термины требуют проверки учителем.",
                "source": "Источники", "question": "Найдите путь за 4 секунды.",
            }
        else:
            labels = {
                "page1": "Understand the idea first", "terms": "Kazakh terms in plain language", "page2": "Quantities, formula, and example",
                "conditions": "When to use it", "symbols": "Symbols and units", "example": "Worked example",
                "page3": "Graph question from an ENT collection", "solve": "Solution and check", "mistakes": "Common mistakes",
                "review": "Status: physics and original answer key checked; translations and terms need teacher review.",
                "source": "Sources", "question": "Find the distance travelled in 4 seconds.",
            }
        out_path = PDF_DIR / f"physlab_ent_constant_acceleration_v1_{language}.pdf"
        doc = LessonDoc(out_path, language)
        story = [para(content["title"], "title"),
                 para(content["objectives"][0] + "  " + content["objectives"][1], "sub"),
                 para(labels["page1"], "h")]
        for beat in chapters["hook"]["beats"]:
            story.append(para("• " + beat))
        story.extend([para(content["misconception"], "formula"), para(labels["terms"], "h")])
        term_rows = [[para("Қазақша", "cell_b"), para("Тілдегі баламасы", "cell_b"), para("Қарапайым түсінігі", "cell_b")]]
        for term in content["kazakh_terms"]:
            term_rows.append([para(term.get("term_kk", ""), "cell_b"), para(term.get("translation", ""), "cell"), para(term.get("meaning", ""), "cell")])
        table = Table(term_rows, colWidths=[37 * mm, 48 * mm, 91 * mm], repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), pale), ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C8D8E0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.extend([table, Spacer(1, 7), para(labels["review"], "small"), PageBreak()])

        story.extend([para(content["title"], "title"), para(labels["page2"], "h")])
        story.extend([para(formula, "formula") for formula in chapters["velocity"]["key_equations"]])
        story.extend([para(labels["conditions"], "h"), *[para(beat) for beat in chapters["displacement"]["beats"]]])
        story.append(para(labels["symbols"], "h"))
        symbols = chapters["velocity"]["key_symbols"] + chapters["displacement"]["key_symbols"]
        rows = [[para("Шама", "cell_b"), para("Мағынасы", "cell_b")]] + [[para(row.split(":", 1)[0], "cell_b"), para(row.split(":", 1)[1].strip(), "cell")] for row in symbols if ":" in row]
        symbol_table = Table(rows, colWidths=[47 * mm, 129 * mm], repeatRows=1)
        symbol_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), pale), ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C8D8E0")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        story.extend([symbol_table, para(labels["example"], "h"), *[para("• " + beat) for beat in chapters["worked-example"]["beats"]], PageBreak()])

        story.extend([para(labels["page3"], "title"), para(lesson["content"]["questions"][0]["q"], "sub"),
                      para(labels["question"], "h"), Graph(graph), Spacer(1, 4)])
        question = content["questions"][0]
        choices = "     •     ".join(question["choices"])
        story.extend([para(choices, "body"), para(labels["solve"], "h"), para(question["why"], "body"),
                      para(labels["mistakes"], "h")])
        for mistake in payload["common_mistakes"][language]:
            story.append(para("• " + mistake, "small"))
        story.extend([para(labels["source"], "h"),
                      para(f"{BOOK_NAME}, §3, PDF pp. 15–18; textbook exercises: p. 20.", "small"),
                      para(f"{QUESTION_NAME}, task 1: PDF p. 2; original answer table: p. 37. Choice B was checked by graph area.", "small"),
                      Paragraph(f'<link href="{SPEC_URL}" color="#0C9D8C">Current NCT physics specification, applies from 2026</link>', styles["small"]),
                      para(labels["review"], "small")])
        doc.build(story)
        outputs.append(out_path)
    return outputs


def main() -> int:
    from aetherlab.core.console import configure_utf8_stdio

    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--content-only", action="store_true")
    group.add_argument("--video-only", action="store_true")
    group.add_argument("--publish-audio-only", action="store_true")
    group.add_argument("--pdf-only", action="store_true")
    group.add_argument("--all", action="store_true")
    args = parser.parse_args()
    payload = write_canonical_route() if args.content_only or args.all else _load_route()
    if args.content_only:
        print(ROUTE_FILE)
        return 0
    if args.pdf_only or args.all:
        for path in build_pdfs(payload):
            print(path)
    if args.video_only or args.all:
        for path in asyncio.run(build_videos(payload)):
            print(path)
    if args.publish_audio_only:
        for path in publish_voiceovers(payload):
            print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
