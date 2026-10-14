"""Stage H: lesson practice set stays wired, solved, and drift-free.

H1 mirrors bank item kinematics-velocity-01 (display text duplicated for the
lesson view; this test forbids divergence). H2–H5 are original lesson items.
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

from aetherlab.services.ent_lesson_catalog import accelerated_motion_plan
from aetherlab.services.ent_physics_bank import QUESTIONS

PRACTICE = json.loads(
    (Path(__file__).resolve().parent.parent
     / "output" / "stage_h_practice" / "practice.json").read_text(encoding="utf-8")
)
ITEMS = PRACTICE["items"]
LANGS = ("kk", "ru", "en")


def test_practice_kinds_cover_stage_h() -> None:
    assert sorted(i["kind"] for i in ITEMS) == [
        "calculation", "calculation", "comprehension", "comprehension", "graph",
    ]


def test_practice_numbers_recomputed() -> None:
    assert Fraction(2) + Fraction(3) * Fraction(4) == 14  # H1
    assert Fraction(2) * Fraction(4) + Fraction(3) * Fraction(16) / 2 == 32  # H2
    assert (Fraction(2) + Fraction(14)) * Fraction(4) / 2 == 32  # H5 trapezoid
    assert Fraction(14) * Fraction(4) == 56  # E1 decoy
    assert Fraction(3) * Fraction(16) / 2 == 24  # partial-area decoy


def test_practice_options_stable_and_unique() -> None:
    for item in ITEMS:
        assert [o["id"] for o in item["options"]] == ["A", "B", "C", "D"]
        for lang in LANGS:
            labels = [o["label"][lang] for o in item["options"]]
            assert all(label.strip() for label in labels)
            assert len(set(labels)) == 4


def test_h1_mirrors_bank_item() -> None:
    h1 = ITEMS[0]
    assert h1["id"] == "H1"
    bank = next(q for q in QUESTIONS if q.id == h1["bank_ref"])
    for lang in LANGS:
        assert h1["prompt"][lang] == bank.prompt[lang]
        assert tuple(o["label"][lang] for o in h1["options"]) == bank.choices[lang]
        assert h1["explanation"][lang] == bank.explanation[lang]
    assert bank.correct_indices == (0,)


def test_catalog_serves_anchor_then_practice() -> None:
    for lang in LANGS:
        plan = accelerated_motion_plan(lang)
        assert len(plan.questions) == 6
        assert plan.questions[0].answer.startswith("B) ")
        for question, item in zip(plan.questions[1:], ITEMS):
            expected = [f"{o['id']}) {o['label'][lang]}" for o in item["options"]]
            assert question.q == item["prompt"][lang]
            assert question.choices == expected
            assert question.answer == expected[0]
            assert question.why == item["explanation"][lang]
