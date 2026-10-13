"""Read-only checks and contact sheets for the generated ENT lesson package."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTE = ROOT / "content" / "ent" / "constant_acceleration_route.json"


def verify_pdfs() -> Path:
    import fitz
    from PIL import Image, ImageDraw, ImageFont

    payload = json.loads(ROUTE.read_text(encoding="utf-8"))
    languages = ("kk", "ru", "en")
    pages: list[tuple[str, int, Image.Image]] = []
    bad = []
    for language in languages:
        path = ROOT / "output" / "pdf" / f"physlab_ent_constant_acceleration_v1_{language}.pdf"
        if not path.is_file():
            raise FileNotFoundError(path)
        doc = fitz.open(path)
        if not 2 <= len(doc) <= 4:
            bad.append(f"{language}: expected 2-4 pages, got {len(doc)}")
        joined = "\n".join(page.get_text() for page in doc)
        if "12" not in joined or "B" not in joined:
            bad.append(f"{language}: missing checked answer number/choice")
        question = payload["lessons"][language]["content"]["questions"][0]
        normalized_question = " ".join(
            question["q"].replace("–", "-").replace("—", "-").replace("‑", "-").split()
        )
        normalized_text = " ".join(joined.split())
        if normalized_question not in normalized_text:
            bad.append(f"{language}: source question text is not searchable in PDF")
        for dash in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2212"):
            if dash in joined:
                bad.append(f"{language}: non-ASCII dash U+{ord(dash):04X} in PDF text")
        for page_no, page in enumerate(doc, 1):
            pix = page.get_pixmap(matrix=fitz.Matrix(1.0, 1.0), alpha=False)
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            image.thumbnail((430, 610))
            pages.append((language, page_no, image.copy()))
        print(f"PDF {language}: {len(doc)} pages, {path.stat().st_size:,} bytes, searchable text OK")
        doc.close()
    if bad:
        raise AssertionError("; ".join(bad))

    cols, cell_w, cell_h, label_h = 3, 444, 650, 26
    rows = (len(pages) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows * (cell_h + label_h)), "#DDE5E9")
    draw = ImageDraw.Draw(sheet)
    label_font = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 16)
    for index, (language, page_no, page_image) in enumerate(pages):
        x, y = (index % cols) * cell_w, (index // cols) * (cell_h + label_h)
        draw.text((x + 8, y + 4), f"{language} - page {page_no}", font=label_font, fill="#102638")
        sheet.paste(page_image, (x + (cell_w - page_image.width) // 2, y + label_h))
    review_path = ROOT / "tmp" / "accelerated_motion_route" / "pdf-contact-sheet.png"
    review_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(review_path)
    print(f"PDF contact sheet: {review_path}")
    return review_path


def verify_videos() -> None:
    import av
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    subtitles = []
    thumbnails = []
    question_markers = {"kk": "Ұлттық", "ru": "национального", "en": "National"}
    for language in ("kk", "ru", "en"):
        path = ROOT / "output" / "video" / f"physlab_ent_constant_acceleration_v1_{language}.mp4"
        srt = path.with_suffix(".srt")
        if not path.is_file() or not srt.is_file():
            raise FileNotFoundError(path if not path.is_file() else srt)
        with av.open(str(path)) as container:
            if not container.streams.video or not container.streams.audio:
                raise AssertionError(f"{path.name}: expected both video and voice tracks")
            duration = container.duration / 1_000_000
            video_stream = container.streams.video[0]
            if duration <= 0 or (video_stream.width, video_stream.height) != (1280, 720):
                raise AssertionError(f"{path.name}: invalid dimensions/duration")
            video_count = 0
            samples = []
            subtitle_text = srt.read_text(encoding="utf-8-sig")
            question_start = _question_start(subtitle_text, question_markers[language])
            sample_targets = [0.5, min(question_start + 1.0, duration - 1), max(duration - 0.7, 0)]
            next_sample = 0
            for frame in container.decode(video=0):
                seconds = float(frame.time or 0)
                if next_sample < len(sample_targets) and seconds >= sample_targets[next_sample]:
                    samples.append((seconds, frame.to_image().convert("RGB").resize((400, 225))))
                    next_sample += 1
                video_count += 1
            if video_count < int(duration * 10):
                raise AssertionError(f"{path.name}: video is unexpectedly short")
            container.seek(0)
            audio_samples = []
            for frame in container.decode(audio=0):
                audio_samples.append(frame.to_ndarray().astype(np.float32, copy=False))
            if not audio_samples:
                raise AssertionError(f"{path.name}: audio track decoded no samples")
            decoded_audio = np.concatenate(audio_samples)
            rms = float(np.sqrt(np.mean(decoded_audio ** 2)))
            audible_threshold = 0.001 if float(np.max(np.abs(decoded_audio))) <= 2 else 30
            if rms < audible_threshold:
                raise AssertionError(f"{path.name}: voice track is silent or too quiet (RMS={rms:.1f})")
        text = srt.read_text(encoding="utf-8-sig")
        cue_count = len(re.findall(r"\d{2}:\d{2}:\d{2},\d{3} -->", text))
        if cue_count < 5:
            raise AssertionError(f"{srt.name}: missing subtitle timing cues")
        cue_times = re.findall(r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})", text)
        last_end = _subtitle_seconds(cue_times[-1][1])
        if last_end < duration - max(8, duration * 0.08):
            raise AssertionError(f"{srt.name}: subtitles end well before the narration")
        standalone = ROOT / "output" / "audio" / f"physlab_ent_constant_acceleration_v1_{language}.m4a"
        if not standalone.is_file():
            raise FileNotFoundError(standalone)
        with av.open(str(standalone)) as audio_container:
            audio_duration = audio_container.duration / 1_000_000
            if not audio_container.streams.audio or abs(audio_duration - duration) > max(0.4, duration * 0.01):
                raise AssertionError(f"{standalone.name}: voiceover differs from its video timing")
        for sample_no, (_time, image) in enumerate(samples, 1):
            thumbnails.append((language, sample_no, image))
        subtitles.append((language, duration, video_count, cue_count, rms))
    for item in subtitles:
        print(f"MP4 {item[0]}: {item[1]:.1f}s, {item[2]} frames, SRT cues={item[3]}, decoded audio RMS={item[4]:.4f}")
    cols, cell_w, cell_h = 3, 410, 260
    rows = (len(thumbnails) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), "#DDE5E9")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 17)
    for index, (language, sample_no, image) in enumerate(thumbnails):
        x, y = (index % cols) * cell_w, (index // cols) * cell_h
        draw.text((x + 4, y + 3), f"{language} - sample {sample_no}", font=font, fill="#102638")
        sheet.paste(image, (x + 4, y + 29))
    review_path = ROOT / "tmp" / "accelerated_motion_route" / "video-contact-sheet.png"
    review_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(review_path)
    print(f"Video contact sheet: {review_path}")


def _question_start(text: str, marker: str) -> float:
    blocks = text.split("\n\n")
    for index in range(0, len(blocks) - 1, 1):
        lines = blocks[index].strip().splitlines()
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        if marker.casefold() in lines[2].casefold():
            timestamp = lines[1].split("-->", 1)[0].strip()
            return _subtitle_seconds(timestamp)
    raise AssertionError(f"Subtitle track does not contain the expected {marker!r} lesson passage")


def _subtitle_seconds(timestamp: str) -> float:
    hours, minutes, remainder = timestamp.split(":")
    seconds, millis = remainder.split(",")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000


if __name__ == "__main__":
    from aetherlab.core.console import configure_utf8_stdio

    configure_utf8_stdio()
    verify_pdfs()
    if (ROOT / "output" / "video").exists():
        expected = [ROOT / "output" / "video" / f"physlab_ent_constant_acceleration_v1_{lang}.mp4" for lang in ("kk", "ru", "en")]
        if all(path.is_file() for path in expected):
            verify_videos()
