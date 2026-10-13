"""Stage I verification: trilingual parity of canonical.json v2 + practice.json.

Checks:
 1. Voiceovers contain no ASCII digits (spoken numbers are words), all langs.
 2. Caption digit-sequence parity per block+index across ru/kk/en.
 3. Unit parity: math captions equal across langs modulo unit tokens + the
    descriptive suffix after "—"; text captions stay text in all langs.
 4. Key-phrase sense anchors (constancy, verdicts, terms, negations).
 5. Practice.json: digit parity across langs per field + every visible number
    belongs to the lesson's closed number set (no leaked/rogue figures).
"""

import json
import re
from pathlib import Path

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
CANON = json.loads((ROOT / "output" / "stage_f_content" / "canonical.json").read_text(encoding="utf-8"))
PRACTICE = json.loads((ROOT / "output" / "stage_h_practice" / "practice.json").read_text(encoding="utf-8"))

VO = {"ru": "voiceover_ru", "kk": "voiceover_kk", "en": "voiceover_en"}
CAP = {"ru": "captions", "kk": "captions_kk", "en": "captions_en"}
LANGS = ("ru", "kk", "en")
DIGITS = re.compile(r"\d+")


def norm_unit(s: str) -> str:
    for src, dst in (("м/с²", "U"), ("m/s²", "U"),
                     ("м/с", "U"), ("m/s", "U")):
        s = s.replace(src, dst)
    s = re.sub(r"(?<=\d) (м|m)(?![\w/])", " U", s)
    return s


KAZ_CYR = "ӘәҒғҚқҢңӨөҰұҮүҺһІі"


def math_core(caption: str) -> str:
    """Math skeleton: part before '—', units normalised, all word runs
    (Cyrillic incl. Kazakh-specific, multi-letter Latin) stripped, spaces out.
    Leaves symbols, operators, digits: '=a', 'S=(2+14)/2·4=32U', ..."""
    core = norm_unit(caption.split("—")[0])
    core = re.sub(f"[А-Яа-яЁё{KAZ_CYR}]+", "", core)
    core = re.sub(r"[A-Za-z]{2,}", "", core)
    return re.sub(r"\s+", "", core)


# 1. voiceovers are digit-free
for b in CANON["blocks"]:
    for lang in LANGS:
        assert not DIGITS.search(b[VO[lang]]), f"digit in {b['id']}/{lang}"

# 2+3. caption parity
for b in CANON["blocks"]:
    caps = {lang: b[CAP[lang]] for lang in LANGS}
    assert len(caps["kk"]) == len(caps["en"]) == len(caps["ru"]), b["id"]
    for i, ru_c in enumerate(caps["ru"]):
        d_ru = DIGITS.findall(ru_c)
        for lang in ("kk", "en"):
            assert DIGITS.findall(caps[lang][i]) == d_ru, f"digits {b['id']}[{i}]/{lang}"
        if "=" in ru_c:
            for lang in ("kk", "en"):
                assert math_core(caps[lang][i]) == math_core(ru_c), \
                    f"math {b['id']}[{i}]/{lang}: {caps[lang][i]!r}"
        else:
            for lang in ("kk", "en"):
                assert "=" not in caps[lang][i], f"text->math {b['id']}[{i}]/{lang}"

# 4. key-phrase sense anchors: (block, ru, kk, en) substrings of voiceovers
ANCHORS = [
    ("B1", "растёт одинаково за каждую секунду", "бірдей шамаға өседі", "same amount each second"),
    ("B1", "ускорение равно трём", "үдеудің үшке тең", "acceleration of three"),
    ("B1", "равноускоренным", "теңүдемелі", "uniformly accelerated"),
    ("B1", "скорость не меняется", "жылдамдық өзгермесе", "speed never changes"),
    ("B3", "направление не меняется", "Бағыт өзгермесе", "direction stays the same"),
    ("B3", "Орын ауыстыру" if False else "Перемещение", "Орын ауыстыру", "Displacement"),
    ("B4", "Наклон прямой — это ускорение", "көлбеуі — бұл үдеу", "slope of the line is the acceleration"),
    ("B5", "Площадь под графиком скорости численно равна перемещению",
     "аудан сан жағынан орын ауыстыруға тең",
     "area under the velocity graph numerically equals the displacement"),
    ("B7", "Неверно", "Қате", "Wrong"),
    ("B7", "брать надо среднюю", "орташасын алу керек", "take the average"),
    ("B7", "Наклон — это ускорение, площадь — перемещение",
     "Көлбеу — бұл үдеу, аудан — орын ауыстыру",
     "Slope is acceleration; area is displacement"),
    ("B7", "пробниках ЕНТ", "ҰБТ байқау сынақтарында", "UNT mocks"),
]
by_id = {b["id"]: b for b in CANON["blocks"]}
for bid, ru_f, kk_f, en_f in ANCHORS:
    b = by_id[bid]
    assert ru_f in b["voiceover_ru"], f"{bid}/ru: {ru_f!r}"
    assert kk_f in b["voiceover_kk"], f"{bid}/kk: {kk_f!r}"
    assert en_f in b["voiceover_en"], f"{bid}/en: {en_f!r}"

# 5. practice numbers: parity + closed set
ALLOWED = {"0", "2", "3", "4", "5", "6", "8", "9", "10", "12", "14",
           "16", "20", "24", "25", "32", "48", "56"}


def fields(item):
    yield "prompt", item["prompt"]
    yield "explanation", item["explanation"]
    for o in item["options"]:
        yield f"option-{o['id']}", o["label"]


for item in PRACTICE["items"]:
    for fname, fmap in fields(item):
        d_ru = DIGITS.findall(fmap["ru"])
        for lang in ("kk", "en"):
            assert DIGITS.findall(fmap[lang]) == d_ru, \
                f"{item['id']}/{fname}/{lang}"
        for num in d_ru:
            assert num in ALLOWED, f"rogue number {num} in {item['id']}/{fname}"

print(f"STAGE I VERIFIED: {len(CANON['blocks'])} blocks x3 langs, "
      f"{len(ANCHORS)} anchors, {len(PRACTICE['items'])} H-items, "
      "digits/units/sense parity clean")
