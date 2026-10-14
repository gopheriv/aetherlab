"""Locate the Q1 answer-key cell on Testcenter-3 p.37 via hOCR and OCR it standalone."""

if __package__:
    from ._console import configure_utf8_stdio
else:
    from _console import configure_utf8_stdio

configure_utf8_stdio()


import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
TMP = ROOT / ".qwen" / "tmp"
OUT = ROOT / "output" / "stage_d_evidence"
OUT.mkdir(parents=True, exist_ok=True)
for n in (1, 2, 37):
    shutil.copy(TMP / f"tc3_p{n}.png", OUT / f"tc3_p{n}.png")

subprocess.run(
    ["tesseract", str(TMP / "tc3_p37_2x.png"), str(TMP / "p37"),
     "-l", "kaz", "--psm", "6", "hocr"],
    check=True,
)
hocr = (TMP / "p37.hocr").read_text(encoding="utf-8")
words = [
    (text, tuple(map(int, box.split())))
    for box, text in re.findall(r"""title=['"]bbox ([\d ]+)[;"'][^>]*>([^<]+)<""", hocr)
]
nums = [(t.strip(), box) for t, box in words if t.strip().isdigit()]
print("numbers row:", nums[:8])
ones = [(t, box) for t, box in nums if t == "1"]
print("ones:", ones)
im = Image.open(TMP / "tc3_p37_2x.png")
letters = [(t, box) for t, box in words
           if box[1] > 1000 and t.strip() and not t.strip().isdigit()]
line_y0 = min(box[1] for _, box in letters)
line_y1 = max(box[3] for _, box in letters)
print("letters row y:", line_y0, line_y1)
col_centers = {"Q1": 168}  # x-center of number "1" in 2x coords
pitch = 146  # measured 1->2 column distance in 2x coords
col_centers["Q2"] = col_centers["Q1"] + pitch
col_centers["Q3"] = col_centers["Q1"] + 2 * pitch
for name, cx in col_centers.items():
    cell = im.crop((cx - 55, line_y0 - 12, cx + 55, line_y1 + 12))
    cell = cell.convert("L").resize((cell.width * 4, cell.height * 4))
    cell.save(OUT / f"key_{name.lower()}_cell.png")
    path = TMP / f"key_{name.lower()}_cell.png"
    cell.save(path)
    run = subprocess.run(
        ["tesseract", str(path), "stdout", "-l", "kaz",
         "--psm", "10", "-c", "tessedit_char_whitelist=АВСДЕABCDE"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(name, "key letter:", repr(run.stdout.strip()))
