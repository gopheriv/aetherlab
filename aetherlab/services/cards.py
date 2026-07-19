"""Rendered title cards for produced lessons (PIL, no ffmpeg drawtext).

A produced lesson is more than concatenated chapter clips: it opens on a title
card, announces each chapter ("Chapter 2 — The idea"), and closes on an end
card. Those cards are drawn here as PNGs with Pillow and the bundled DejaVu
font, then turned into short clips by services/assembly. PIL is used instead of
ffmpeg's ``drawtext`` filter because filtergraph path/text escaping is fragile
on Windows and in the frozen bundle, whereas PIL text is fully in our control
and works identically everywhere.

Stdlib + Pillow only (no project/UI imports); every function is fail-soft and
returns ``None`` rather than raising into the lesson pipeline.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)

# 720p canvas — matches the lesson assembly's normalization target.
CARD_W, CARD_H = 1280, 720

# Card palette (mirrors scene_templates.DEFAULT_SCENE_PALETTE / "Aether Dark").
_CARD_PALETTE = {
    "background": "#0A0A0F",
    "title": "#F8FAFC",
    "accent": "#F59E0B",
    "muted": "#94A3B8",
    "rule": "#06B6D4",
}


def _font_file(bold: bool) -> Path | None:
    """Locate a bundled DejaVu TTF in both a checkout and a frozen dist."""
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    candidates = [
        Path(__file__).resolve().parents[2] / "assets" / "fonts" / name,  # repo
        Path(getattr(sys, "_MEIPASS", ".")) / "assets" / "fonts" / name,  # frozen
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _load_font(bold: bool, size: int):
    from PIL import ImageFont

    path = _font_file(bold)
    if path is not None:
        try:
            return ImageFont.truetype(str(path), size)
        except Exception:  # noqa: BLE001
            pass
    # Last resort: PIL's built-in bitmap font (fixed size, but never crashes).
    return ImageFont.load_default()


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    """Greedy word-wrap ``text`` to ``max_width`` pixels."""
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    cur = words[0]
    for word in words[1:]:
        trial = f"{cur} {word}"
        if draw.textlength(trial, font=font) <= max_width:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines


def render_card_png(
    out_path: Path | str,
    *,
    kicker: str = "",
    title: str = "",
    subtitle: str = "",
    palette: dict[str, str] | None = None,
) -> Path | None:
    """Draw a centered title card to ``out_path`` (PNG). Returns None on failure.

    ``kicker`` is a small accent line above the title (e.g. "CHAPTER 2" or the
    lesson audience); ``title`` is the hero line; ``subtitle`` is a muted line
    below. Text is word-wrapped to the card width.
    """
    try:
        from PIL import Image, ImageDraw
    except Exception as exc:  # noqa: BLE001 — Pillow always ships, but be safe
        log.info("Pillow unavailable; skipping card render (%s).", exc)
        return None

    pal = dict(_CARD_PALETTE)
    if palette:
        for key, dst in (("background", "background"), ("accent", "accent"),
                         ("text", "title"), ("curve", "rule"), ("muted", "muted")):
            val = palette.get(key)
            if isinstance(val, str) and val.startswith("#") and len(val) == 7:
                pal[dst] = val

    try:
        img = Image.new("RGB", (CARD_W, CARD_H), pal["background"])
        draw = ImageDraw.Draw(img)
        margin = 140
        max_w = CARD_W - 2 * margin

        kicker_font = _load_font(True, 40)
        title_font = _load_font(True, 76)
        sub_font = _load_font(False, 40)

        blocks: list[tuple[list[str], object, str, int]] = []  # (lines, font, color, line_gap)
        if kicker:
            blocks.append(([kicker.upper()], kicker_font, pal["accent"], 12))
        if title:
            blocks.append((_wrap(draw, title, title_font, max_w), title_font, pal["title"], 14))
        if subtitle:
            blocks.append((_wrap(draw, subtitle, sub_font, max_w), sub_font, pal["muted"], 10))

        # Measure total height to vertically center the stack.
        heights: list[int] = []
        total = 0
        for lines, font, _color, gap in blocks:
            h = 0
            for ln in lines:
                bbox = draw.textbbox((0, 0), ln or " ", font=font)
                h += (bbox[3] - bbox[1]) + gap
            heights.append(h)
            total += h
        total += 40 * (len(blocks) - 1) if len(blocks) > 1 else 0

        y = (CARD_H - total) // 2
        rule_y = None
        for (lines, font, color, gap), _h in zip(blocks, heights, strict=False):
            for ln in lines:
                bbox = draw.textbbox((0, 0), ln or " ", font=font)
                w = bbox[2] - bbox[0]
                draw.text(((CARD_W - w) // 2 - bbox[0], y - bbox[1]),
                          ln, font=font, fill=color)
                y += (bbox[3] - bbox[1]) + gap
            if rule_y is None and font is kicker_font:
                rule_y = y + 6
            y += 40
        # A short accent rule under the kicker ties the card to the app.
        if rule_y is not None:
            draw.rectangle([(CARD_W // 2 - 60, rule_y), (CARD_W // 2 + 60, rule_y + 4)],
                           fill=pal["rule"])

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path)
        return out_path
    except Exception as exc:  # noqa: BLE001 — a card must never break a lesson
        log.info("Card render failed (%s); lesson continues without it.", exc)
        return None


def chapter_kicker(index: int, total: int) -> str:
    """'Chapter N' kicker text for a 1-based chapter index."""
    return f"Chapter {index}" if total else "Chapter"
