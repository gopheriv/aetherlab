"""Render Testcenter-3 p2 at 300dpi and OCR the Q1 graph axes region."""

import subprocess
from pathlib import Path

import fitz
from PIL import Image

REF = Path(r"C:\Users\sunak\Projects\References") / "Testcenter -3.pdf"
TMP = Path(r"C:\Users\sunak\Projects\aetherlab\.qwen\tmp")

doc = fitz.open(REF)
pix = doc[1].get_pixmap(dpi=300)
img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
print("p2 size @300dpi:", img.size)
img.save(TMP / "tc3_p2_300.png")

# Q1 block is the top question; OCR top 55% for axes/ticks.
top = img.crop((0, 0, img.width, int(img.height * 0.55)))
top.save(TMP / "tc3_p2_q1.png")
for lang in ("kaz", "kaz+eng"):
    run = subprocess.run(
        ["tesseract", str(TMP / "tc3_p2_q1.png"), "stdout",
         "-l", lang, "--psm", "6"],
        capture_output=True, text=True)
    print(f"--- lang={lang} ---")
    print(run.stdout[:1500])
