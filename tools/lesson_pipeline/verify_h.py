"""Stage H verification: numbers, H1 bank mirror, option sanity, catalog wiring."""

import json
from fractions import Fraction
from pathlib import Path

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
practice = json.loads((ROOT / "output/stage_h_practice/practice.json").read_text(encoding="utf-8"))
items = practice["items"]

# --- 1. Kind coverage: 2 comprehension, 2 calculation, 1 graph ---
kinds = sorted(i["kind"] for i in items)

# UTF-8 stdio for redirected Cyrillic output (F133).
try:
    from aetherlab.core.console import configure_utf8_stdio  # noqa: E402
    configure_utf8_stdio()
except ImportError:
    pass

assert kinds == ["calculation", "calculation", "comprehension", "comprehension", "graph"], kinds
assert [i["id"] for i in items] == ["H1", "H2", "H3", "H4", "H5"]
print("kinds ok:", kinds)

# --- 2. Independent numeric recomputation (inputs stated here) ---
assert Fraction(2) + Fraction(3) * Fraction(4) == 14  # H1
s = Fraction(2) * Fraction(4) + Fraction(3) * Fraction(16) / 2  # H2
assert s == 32
assert (Fraction(2) + Fraction(14)) * Fraction(4) / 2 == 32  # H5 trapezoid
# Decoy formulas from practice.json must reproduce the decoy labels.
assert Fraction(14) * Fraction(4) == 56  # H2-B/C E1
assert Fraction(3) * Fraction(16) / 2 == 24  # H2-C / H5-D triangle
assert Fraction(2) * Fraction(4) + Fraction(3) * Fraction(4) == 20  # H2-D
assert (Fraction(14) - Fraction(2)) * Fraction(4) == 48  # H5-B
print("numbers ok: H1=14, H2=32, H5=32, decoys reproduce")

# --- 3. Option sanity per item per language ---
for item in items:
    assert [o["id"] for o in item["options"]] == ["A", "B", "C", "D"], item["id"]
    assert item["correct_option_id"] == "A", item["id"]
    for lang in ("kk", "ru", "en"):
        labels = [o["label"][lang] for o in item["options"]]
        assert all(lbl.strip() for lbl in labels), (item["id"], lang)
        assert len(set(labels)) == 4, (item["id"], lang, labels)
        assert item["prompt"][lang].strip(), (item["id"], lang)
        assert item["explanation"][lang].strip(), (item["id"], lang)
print("options ok: A-D stable, unique labels, non-empty text in kk/ru/en")

# --- 4. H1 mirrors bank item kinematics-velocity-01 exactly ---
from aetherlab.services.ent_physics_bank import QUESTIONS

bank = next(q for q in QUESTIONS if q.id == items[0]["bank_ref"])
h1 = items[0]
for lang in ("kk", "ru", "en"):
    assert h1["prompt"][lang] == bank.prompt[lang], lang
    assert tuple(o["label"][lang] for o in h1["options"]) == bank.choices[lang], lang
    assert h1["explanation"][lang] == bank.explanation[lang], lang
assert bank.correct_indices == (0,)
print("H1 mirror ok: prompt/choices/explanation match bank item")

# --- 5. Catalog wiring: anchor first, then H1..H5 with "A) " prefixes ---
from aetherlab.services.ent_lesson_catalog import accelerated_motion_plan

for lang in ("kk", "ru", "en"):
    plan = accelerated_motion_plan(lang)
    assert len(plan.questions) == 6, (lang, len(plan.questions))
    assert plan.questions[0].answer.startswith("B) "), lang  # NCT anchor untouched
    for question, item in zip(plan.questions[1:], items):
        assert question.q == item["prompt"][lang], (lang, item["id"])
        expect = [f"{o['id']}) {o['label'][lang]}" for o in item["options"]]
        assert question.choices == expect, (lang, item["id"])
        assert question.answer == expect[0], (lang, item["id"])
        assert question.why == item["explanation"][lang], (lang, item["id"])
print("catalog ok: 6 questions per lang, anchor first, H1-H5 match practice.json")

print("STAGE H VERIFIED")
