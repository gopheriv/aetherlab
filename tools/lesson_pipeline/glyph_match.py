"""Blob-split the Q1 key cell and cross-correlate its glyph vs confident
same-row letters (A/B/C/D) to identify the letter without trusting OCR."""

import re
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
TMP = ROOT / ".qwen" / "tmp"
OUT = ROOT / "output" / "stage_d_evidence"

hocr = (TMP / "p37.hocr").read_text(encoding="utf-8")
words = [
    (text, tuple(map(int, box.split())), int(conf))
    for box, conf, text in re.findall(
        r"""title=['"]bbox ([\d ]+);[^'"]*?x_wconf (\d+)[;"'][^>]*>([^<]+)<""", hocr)
]
singles = [(t.strip(), b, c) for t, b, c in words
           if b[1] > 1000 and len(t.strip()) == 1 and t.strip() in "АВСДЕABCD"]
print("single-letter words in row (char, box, conf):")
for s in singles:
    print("  ", s)

im = Image.open(TMP / "tc3_p37_2x.png").convert("L")


def glyph_vector(box, pad=8, size=48):
    crop = im.crop((box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad))
    arr = np.asarray(crop, dtype=float)
    ink = arr < 150
    ys, xs = np.nonzero(ink)
    if len(xs) == 0:
        return None
    tight = ink[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(float)
    img = Image.fromarray((tight * 255).astype("uint8")).resize((size, size))
    v = np.asarray(img, dtype=float).ravel()
    return (v - v.mean()) / (v.std() + 1e-9)


q1 = glyph_vector((113, 1218, 223, 1326))  # same crop as key_cell.py
print("q1 vector:", None if q1 is None else "ok")
for t, b, c in singles:
    v = glyph_vector(b)
    if v is None:
        continue
    sim = float(np.dot(q1, v) / len(v))
    print(f"  q1 vs {t}@{b} conf={c}: corr={sim:.3f}")

# Blob structure of the q1 crop: column ink profile gaps.
crop = np.asarray(im.crop((113, 1218, 223, 1326))) < 150
cols = crop.any(axis=0)
runs, start = [], None
for i, on in enumerate(cols):
    if on and start is None:
        start = i
    elif not on and start is not None:
        runs.append((start, i - 1))
        start = None
if start is not None:
    runs.append((start, len(cols) - 1))
print("ink column runs (crop coords):", runs)
