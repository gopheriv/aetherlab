"""Worked substitutions must preserve powers, quantities, units and fixed keys."""
import os
import re
from decimal import Decimal

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

from aetherlab.services.ent_topic_bank import build_topic_exercises

_APP = None
TOPICS = ("magnetic_field", "quantum_physics", "nanotechnology")


def examples(topic):
    return tuple(question for question in build_topic_exercises() if question["topic"] == topic)


@pytest.mark.parametrize("topic,exponent", (("magnetic_field", -3), ("quantum_physics", -1)))
def test_negative_powers_keep_the_whole_exponent_in_every_substitution(topic, exponent):
    questions = examples(topic)
    assert len(questions) == 100
    for question in questions:
        substitution = question["solution_latex"][1]
        assert f"10^{{{exponent}}}" in substitution, (question["id"], substitution)
        assert not re.search(r"10\^-\d", substitution)


def test_nanometre_conversion_uses_the_requested_length_as_unknown():
    questions = examples("nanotechnology")
    assert len(questions) == 100
    for question in questions:
        formula, substitution, result = question["solution_latex"]
        assert formula == r"1\,\mathrm{nm}=10^{-9}\,\mathrm{m}"
        assert substitution.startswith("l="), (question["id"], substitution)
        assert result.startswith("l="), (question["id"], result)


def test_all_generated_steps_keep_negative_exponents_grouped():
    questions = build_topic_exercises()
    assert len(questions) == 2500
    for question in questions:
        for expression in question["solution_latex"]:
            assert not re.search(r"\^-\d", expression), (question["id"], expression)


@pytest.mark.parametrize("topic", TOPICS)
def test_keys_and_units_agree_with_independent_physics_in_all_languages(topic):
    units = {"magnetic_field": ("мН", "мН", "mN"),
             "quantum_physics": ("10⁻¹⁹ Дж", "10⁻¹⁹ Дж", "10⁻¹⁹ J"),
             "nanotechnology": ("м", "м", "m")}[topic]
    pattern = {"magnetic_field": r"at ([\d.]+) m/s", "quantum_physics": r"frequency is ([\d.]+)",
               "nanotechnology": r"is ([\d.]+) nm"}[topic]
    questions = examples(topic)
    assert len(questions) == 100
    for question in questions:
        supplied = Decimal(re.search(pattern, question["prompt"]["en"]).group(1))
        if topic == "magnetic_field":
            expected = Decimal("0.001") * supplied * Decimal("0.01") * Decimal("1000")
        elif topic == "quantum_physics":
            expected = Decimal("6.63e-34") * supplied * Decimal("1e14") / Decimal("1e-19")
        else:
            expected = supplied * Decimal("1e-9")
        half_last_digit = Decimal("0.5").scaleb(expected.adjusted() - 3)
        for language, unit in zip(("kk", "ru", "en"), units):
            choice = question["choices"][language][question["correct_indices"][0]]
            value, actual_unit = choice.split(" ", 1)
            assert actual_unit == unit
            assert abs(Decimal(value.replace(",", ".")) - expected) <= half_last_digit, question["id"]
        number = question["solution_latex"][-1].split("=", 1)[1].split(r"\,", 1)[0]
        scientific = re.fullmatch(r"(.+?)\\times 10\^\{(-?\d+)\}", number)
        displayed = Decimal(scientific[1]) * Decimal(10) ** int(scientific[2]) if scientific else Decimal(number)
        assert abs(displayed - expected) <= half_last_digit


@pytest.mark.parametrize("topic", TOPICS)
@pytest.mark.parametrize("index", (0, 99))
def test_first_and_last_worked_steps_typeset_without_fallback(topic, index, tmp_path):
    from aetherlab.services.mathtext import render_math
    from aetherlab.ui.qt_compat import QtWidgets

    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert _APP.platformName() == "offscreen"
    question = examples(topic)[index]
    for number, expression in enumerate(question["solution_latex"]):
        image = render_math(expression, px_size=24, color="#172033")
        assert image is not None and not image.isNull(), (question["id"], expression)
        assert image.save(str(tmp_path / f"step-{number}.png"))
