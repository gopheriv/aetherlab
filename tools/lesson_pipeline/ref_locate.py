"""Locate the uniformly-accelerated-motion sections in reference PDFs."""

from pathlib import Path

import fitz

REF = Path(r"C:\Users\sunak\Projects\References")
TARGETS = {
    "zak10": "Физика Закирова 10 ЖМ.pdf",
    "zak9": "Физика Закирова 9.pdf",
    "zak11": "Физика Закирова 11 ЖМ.pdf",
    "f369": "369 формула.pdf",
    "fbs": "FBS (1).pdf",
    "tc3": "Testcenter -3.pdf",
}
KEYS = ["теңүдемелі", "тең үдемелі", "равноускорен", "үдеу", "ускорение"]

# UTF-8 stdio for redirected Cyrillic output (F133).
try:
    from aetherlab.core.console import configure_utf8_stdio  # noqa: E402
    configure_utf8_stdio()
except ImportError:
    pass

for key, name in TARGETS.items():
    doc = fitz.open(REF / name)
    print(f"== {key}: {name} ({len(doc)} pages)")
    for i, page in enumerate(doc):
        text = page.get_text()
        hits = [k for k in KEYS if k in text.lower()]
        if hits:
            first = " / ".join(text.splitlines()[:2])[:100]
            print(f"  pdf-p{i + 1}: {hits} :: {first}")
    doc.close()
