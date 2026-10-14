"""Stage K verification: voice assets exist, measure as tabulated, fit budgets.

Checks:
 1. All 24 block clips + 3 samples + 6 B6-split clips exist and are non-empty.
 2. Re-measured (PyAV) durations match timing.json within 0.15 s.
 3. Per block: slowest language fits budget with >= 1.0 s headroom
    (B6: B6a + gap + B6b + 2x breath == 30.0, gap >= 4.0).
 4. Total speech per language is in [150, 292] s: not empty padding, not cut.
 5. speak.json: block ids match canonical; no Latin in kk/ru; no digits at all.
 6. timing.md exists and names all blocks and voices.
"""

import json
import re
from pathlib import Path

import av

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
CANON = json.loads((ROOT / "output" / "stage_f_content" / "canonical.json").read_text(encoding="utf-8"))
OUT = ROOT / "output" / "stage_k_voice"
TIMING = json.loads((OUT / "timing.json").read_text(encoding="utf-8"))
SPEAK = json.loads((OUT / "speak.json").read_text(encoding="utf-8"))
DOC = (OUT / "timing.md").read_text(encoding="utf-8")

LANGS = ("kk", "ru", "en")


# UTF-8 stdio for redirected Cyrillic output (F133).
try:
    from aetherlab.core.console import configure_utf8_stdio  # noqa: E402
    configure_utf8_stdio()
except ImportError:
    pass

def duration(path: Path) -> float:
    with av.open(str(path)) as container:
        streams = container.streams.audio or container.streams.video
        if streams and streams[0].duration and streams[0].time_base:
            return float(streams[0].duration * streams[0].time_base)
        assert container.duration, f"no duration: {path.name}"
        return container.duration / 1_000_000.0


# 1+2. files + re-measured durations
checked = 0
for key, meta in TIMING["fragments"].items():
    p = OUT / "clips" / meta["file"]
    assert p.is_file() and p.stat().st_size > 0, key
    assert abs(duration(p) - meta["seconds"]) < 0.15, f"{key} drifted"
    checked += 1
assert checked == 24, checked
for lang, meta in TIMING["samples"].items():
    p = OUT / "samples" / meta["file"]
    assert p.is_file() and p.stat().st_size > 0, lang
    assert abs(duration(p) - meta["seconds"]) < 0.15, f"sample {lang} drifted"
for lang in LANGS:
    for tag in ("a", "b"):
        p = OUT / "clips" / f"B6{tag}_{lang}.mp3"
        assert p.is_file() and p.stat().st_size > 0, p.name

# 3. budgets
budgets = {b["id"]: b["end_s"] - b["start_s"] for b in CANON["blocks"]}
for bid, budget in budgets.items():
    if bid == "B6":
        continue
    slowest = max(TIMING["fragments"][f"{bid}_{lang}"]["seconds"] for lang in LANGS)
    assert slowest <= budget - 1.0, f"{bid}: {slowest}s in {budget}s"
split = TIMING["b6_split"]
for lang in LANGS:
    s = split[lang]
    assert s["gap_s"] >= 4.0, f"B6/{lang} gap {s['gap_s']}"
    assert abs(s["B6a_s"] + s["gap_s"] + s["B6b_s"]
               + 2 * s["edge_breath_s"] - 30.0) < 0.02, f"B6/{lang} sum"

# 4. totals per language (B6 counted as a+b speech)
for lang in LANGS:
    total = sum(m["seconds"] for k, m in TIMING["fragments"].items()
                if k.endswith(f"_{lang}"))
    assert 150.0 <= total <= 292.0, f"{lang} total {total}"

# 5. speak text hygiene
assert set(SPEAK) == set(budgets)
for bid, per_lang in SPEAK.items():
    assert set(per_lang) == set(LANGS), bid
    for lang, text in per_lang.items():
        assert not re.search(r"\d", text), f"digit in {bid}/{lang}"
        if lang != "en":
            assert not re.search(r"[A-Za-z]", text), f"latin in {bid}/{lang}"

# 6. doc presence
for bid in budgets:
    assert bid in DOC, f"doc: no {bid}"
for voice in TIMING["voices"].values():
    assert voice in DOC, f"doc: no {voice}"

print(f"STAGE K VERIFIED: 24 clips + 6 B6-split + 3 samples, "
      f"durations match, all blocks fit budgets, totals in [150, 292]s")
