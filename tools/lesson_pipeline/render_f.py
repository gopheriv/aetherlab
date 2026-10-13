"""Render output/stage_f_content/lesson_ru.md from canonical.json.

The JSON is the single source of truth; the MD is a derived review copy.
Fails loudly on unknown ID references or non-monotonic block timings.
"""

import json
from pathlib import Path

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
SRC = ROOT / "output" / "stage_f_content" / "canonical.json"
OUTDIR = ROOT / "output" / "stage_f_content"

LANGS = (("ru", "Озвучка", "Подписи", "Визуал"),
         ("kk", "Дыбыстау", "Жазбалар", "Визуал"),
         ("en", "Voiceover", "Captions", "Visual"))

canon = json.loads(SRC.read_text(encoding="utf-8"))
concepts = {c["id"]: c for c in canon["concepts"]}
formulas = {f["id"]: f for f in canon["formulas"]}
data = {d["id"]: d for d in canon["data"]}

CAP_KEY = {"ru": "captions", "kk": "captions_kk", "en": "captions_en"}
VO_KEY = {"ru": "voiceover_ru", "kk": "voiceover_kk", "en": "voiceover_en"}
TITLES = {
    "ru": f"# {canon['lesson']} — канонический ru-контент (v{canon['version']})",
    "kk": f"# {canon['lesson']} — канондық kk-мәтін (v{canon['version']})",
    "en": f"# {canon['lesson']} — canonical en-text (v{canon['version']})",
}

prev_end = 0
for b in canon["blocks"]:
    assert b["start_s"] == prev_end, f"gap/overlap at {b['id']}"
    assert b["end_s"] > b["start_s"], f"bad timing at {b['id']}"
    prev_end = b["end_s"]
    for cid in b["concepts"]:
        assert cid in concepts, f"unknown concept {cid}"
    for fid in b["formulas"]:
        assert fid in formulas, f"unknown formula {fid}"
    for did in b["data"]:
        assert did in data, f"unknown data {did}"

total = canon["blocks"][-1]["end_s"]
for lang, vo_h, cap_h, vis_h in LANGS:
    ll = [
        TITLES[lang],
        "",
        f"Цель: {canon['goal']}",
        "",
        "## Условия применимости",
        "",
        *[f"- {c}" for c in canon["applicability"]],
        "",
        f"Ось: {canon['axis']}",
        "",
        "## Величины (inputs — истина; derived — проверить на этапе G)",
        "",
    ]
    for d in canon["data"]:
        scope = f" [{d['scope']}]" if "scope" in d else ""
        extra = f" ← {d['derived_from']} ({d['verified']})" if d["kind"] == "derived" else ""
        ll.append(
            f"- `{d['id']}`{scope}: {d['symbol']} = {d['value']} {d['unit']}"
            f" — {d.get('name_ru', '')} [{d['kind']}{extra}]"
        )
    ll += ["", "## Формулы", ""]
    for f in canon["formulas"]:
        ll.append(f"- `{f['id']}`: {f['name_ru']}: ${f['latex']}$ (`{f['expr']}`)")
    ll += ["", "## Блоки", ""]
    for b in canon["blocks"]:
        ll += [
            f"### {b['id']} {b['title']} ({b['start_s']}–{b['end_s']} с)",
            "",
            f"{vis_h}: {b['visual']}",
            "",
            f"{vo_h}:",
            "",
            f"> {b[VO_KEY[lang]]}",
            "",
            f"{cap_h}:",
            "",
            *[f"- {c}" for c in b[CAP_KEY[lang]]],
            "",
        ]
    ll += [f"Итого: {total} с (норма 300±15 с).", ""]
    dst = OUTDIR / f"lesson_{lang}.md"
    dst.write_text("\n".join(ll), encoding="utf-8")
    print(f"ok: {dst.name}, {total}s, "
          f"{len(canon['blocks'])} blocks, {len(canon['data'])} data ids")
