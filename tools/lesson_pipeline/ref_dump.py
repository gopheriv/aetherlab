"""Dump the key reference pages to text files for Stage D term extraction."""

from pathlib import Path

import fitz

REF = Path(r"C:\Users\sunak\Projects\References")
OUT = Path(r"C:\Users\sunak\Projects\aetherlab\.qwen\tmp\ref_text")
OUT.mkdir(parents=True, exist_ok=True)
JOBS = {
    "zak10": ("Физика Закирова 10 ЖМ.pdf", [15, 16, 17, 18, 20]),
    "zak9": ("Физика Закирова 9.pdf", [19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29]),
    "fbs": ("FBS (1).pdf", [6, 7]),
    "f369": ("369 формула.pdf", [6, 7]),
}
for key, (name, pages) in JOBS.items():
    doc = fitz.open(REF / name)
    parts = []
    for n in pages:
        parts.append(f"===== pdf-p{n} =====\n" + doc[n - 1].get_text())
    (OUT / f"{key}.txt").write_text("\n".join(parts), encoding="utf-8")
    print(key, "ok", sum(len(p) for p in parts), "chars")
    doc.close()
