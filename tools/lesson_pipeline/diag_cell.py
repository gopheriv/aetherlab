"""Diagnose the Q1 key-cell crop: stats plus several tesseract configs."""

import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
TMP = ROOT / ".qwen" / "tmp"
OUT = ROOT / "output" / "stage_d_evidence"

cell = Image.open(TMP / "key_q1_cell.png").convert("L")
arr = np.asarray(cell)
print("size:", cell.size, "dark_frac@128:", float((arr < 128).mean()))
print("col range with ink:",
      [int(i) for i in (np.nonzero((arr < 128).any(axis=0))[0][[0, -1]])])
print("row range with ink:",
      [int(i) for i in (np.nonzero((arr < 128).any(axis=1))[0][[0, -1]])])

thr = cell.point(lambda v: 255 if v > 150 else 0)
thr.save(TMP / "key_q1_thr.png")

for src, psm, lang, extra in [
    ("key_q1_cell.png", "10", "kaz", ["-c", "tessedit_char_whitelist=АВСДЕABCDE"]),
    ("key_q1_cell.png", "8", "kaz", []),
    ("key_q1_thr.png", "8", "kaz", []),
    ("key_q1_thr.png", "8", "rus", []),
    ("key_q1_thr.png", "10", "rus", []),
]:
    run = subprocess.run(
        ["tesseract", str(TMP / src), "stdout", "-l", lang, "--psm", psm, *extra],
        capture_output=True, text=True)
    print(f"{src} psm={psm} lang={lang}: {run.stdout.strip()!r} err={run.stderr.strip()[-120:]}")
