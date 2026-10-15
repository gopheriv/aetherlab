"""Compute keys from the displayed English conditions, independent of Pack.calculate."""
import random
import re
from collections import Counter
from decimal import Decimal, localcontext

import pytest

from aetherlab.services.ent_topic_bank import build_topic_exercises

D = Decimal
NUMBER = r"([0-9]+(?:\.[0-9]+)?(?:e[-+]?[0-9]+)?)"


def n(pattern, prompt):
    found = re.search(pattern, prompt)
    assert found, (pattern, prompt)
    values = tuple(D(value) for value in found.groups())
    return values[0] if len(values) == 1 else values


def kinematics(p):
    speed, acceleration, time = n(r"Initial speed is " + NUMBER + r" m/s, acceleration " + NUMBER + r" m/s², and time " + NUMBER + r" s", p)
    return speed + acceleration * time


def dynamics(p):
    mass, acceleration = n(r"mass " + NUMBER + r" kg accelerates at " + NUMBER + r" m/s²", p)
    return mass * acceleration


def statics(p):
    force, arm = n(r"force of " + NUMBER + r" N acts at a " + NUMBER + r" m lever arm", p)
    return force * arm


def fluids(p):
    density, depth, gravity = n(r"density is " + NUMBER + r" kg/m³ and depth is " + NUMBER + r" m \(g=" + NUMBER + r" m/s²", p)
    return density * gravity * depth / D(1000)


def molecular(p):
    temperature = n(r"temperature is " + NUMBER + r" K", p)
    assert "k=1.38·10⁻²³ J/K" in p
    return D("1.5") * D("1.38e-23") * temperature / D("1e-21")


def gas_laws(p):
    pressure, first, second = n(r"p₁=" + NUMBER + r" kPa, T₁=" + NUMBER + r" K, T₂=" + NUMBER + r" K", p)
    return pressure * second / first


def heat(p):
    mass, change = n(NUMBER + r" kg of water is warmed by " + NUMBER + r"°C", p)
    specific_heat = n(r"c=" + NUMBER + r" kJ/", p)
    return mass * specific_heat * change


def melting(p):
    mass, latent = n(r"Melt " + NUMBER + r" kg of ice; λ=" + NUMBER + r" kJ/kg", p)
    return mass * latent


def electrostatics(p):
    charge, distance = n(r"Two " + NUMBER + r" μC charges are " + NUMBER + r" cm apart", p)
    assert "k=9·10⁹" in p
    return D("9e9") * (charge * D("1e-6")) ** 2 / (distance / D(100)) ** 2


def current(p):
    voltage, resistance = n(r"Voltage is " + NUMBER + r" V and resistance is " + NUMBER + r" Ω", p)
    return voltage / resistance


def electrolysis(p):
    coefficient, amps, time = n(r"k=" + NUMBER + r" g/\(A·s\), current " + NUMBER + r" A, time " + NUMBER + r" s", p)
    return coefficient * amps * time


def magnetic(p):
    charge, speed, induction = n(r"A " + NUMBER + r" mC charge moves at " + NUMBER + r" m/s perpendicular to B=" + NUMBER + r" T", p)
    return charge / D(1000) * speed * induction * D(1000)


def induction(p):
    flux, time, turns = n(r"Flux changes by " + NUMBER + r" Wb in " + NUMBER + r" s through N=" + NUMBER + r" turns", p)
    return turns * flux / time


def oscillation(p):
    mass, spring, pi_squared = n(r"A " + NUMBER + r" kg mass is on a spring with k=" + NUMBER + r" N/m. Use π²≈" + NUMBER, p)
    return D(2) * (pi_squared * mass / spring).sqrt()


def rms(p):
    peak, root_two = n(r"peak of " + NUMBER + r" V. Use √2≈" + NUMBER, p)
    return peak / root_two


def em_wave(p):
    frequency = n(r"frequency " + NUMBER + r" MHz", p)
    assert "c=3·10⁸ m/s" in p
    return D("3e8") / (frequency * D("1e6"))


def fringes(p):
    wavelength, length, slit = n(r"λ=" + NUMBER + r" nm, screen distance L=" + NUMBER + r" m, slit separation d=" + NUMBER + r" mm", p)
    return wavelength * D("1e-9") * length / (slit * D("1e-3")) * D(1000)


def lens(p):
    focus, distance = n(r"focal length f=" + NUMBER + r" cm; an object is at a=" + NUMBER + r" cm", p)
    return D(1) / (D(1) / focus - D(1) / distance)


def relativity(p):
    percent = n(r"moves at " + NUMBER + r"% of light speed", p)
    return D(1) / (D(1) - (percent / D(100)) ** 2).sqrt()


def photon(p):
    frequency = n(r"frequency is " + NUMBER + r"·10¹⁴ Hz", p)
    assert "h=6.63·10⁻³⁴ J·s" in p
    return D("6.63e-34") * frequency * D("1e14") / D("1e-19")


def nuclei(p):
    initial, periods = n(r"There are " + NUMBER + r" nuclei initially. Let the number of half-lives be n=" + NUMBER, p)
    assert periods == periods.to_integral_value()
    return initial / D(2) ** int(periods)


def nanoscale(p):
    return n(r"nanoparticle is " + NUMBER + r" nm across", p) * D("1e-9")


def redshift(p):
    first, second = n(r"λ₀=" + NUMBER + r" nm to λ=" + NUMBER + r" nm", p)
    return (second - first) / first


def energy(p):
    mass, speed = n(r"mass " + NUMBER + r" kg moves at " + NUMBER + r" m/s", p)
    return mass * speed ** 2 / D(2)


def wave_speed(p):
    wavelength, frequency = n(r"Wavelength is " + NUMBER + r" m and frequency is " + NUMBER + r" Hz", p)
    return wavelength * frequency


ORACLES = {
    "kinematics": (kinematics, "m/s"), "dynamics": (dynamics, "N"), "statics": (statics, "N·m"),
    "fluids": (fluids, "kPa"), "molecular_kinetic_theory": (molecular, "10⁻²¹ J"),
    "gas_laws": (gas_laws, "kPa"), "thermodynamics": (heat, "kJ"), "liquids_solids": (melting, "kJ"),
    "electrostatics": (electrostatics, "N"), "electricity": (current, "A"), "current_media": (electrolysis, "g"),
    "magnetic_field": (magnetic, "mN"), "induction": (induction, "V"),
    "mechanical_oscillations": (oscillation, "s"), "ac_circuits": (rms, "V"),
    "electromagnetic_waves": (em_wave, "m"), "wave_optics": (fringes, "mm"),
    "geometric_optics": (lens, "cm"), "relativity": (relativity, "—"),
    "quantum_physics": (photon, "10⁻¹⁹ J"), "nuclear_physics": (nuclei, ""),
    "nanotechnology": (nanoscale, "m"), "cosmology": (redshift, "—"),
    "conservation": (energy, "J"), "wave_motion": (wave_speed, "m/s"),
}

UNITS = {
    "m/s": ("м/с", "м/с", "m/s"), "N": ("Н", "Н", "N"), "N·m": ("Н·м", "Н·м", "N·m"),
    "kPa": ("кПа", "кПа", "kPa"), "10⁻²¹ J": ("10⁻²¹ Дж", "10⁻²¹ Дж", "10⁻²¹ J"),
    "kJ": ("кДж", "кДж", "kJ"), "A": ("А", "А", "A"), "g": ("г", "г", "g"),
    "mN": ("мН", "мН", "mN"), "V": ("В", "В", "V"), "s": ("с", "с", "s"),
    "m": ("м", "м", "m"), "mm": ("мм", "мм", "mm"), "cm": ("см", "см", "cm"),
    "—": ("—", "—", "—"), "10⁻¹⁹ J": ("10⁻¹⁹ Дж", "10⁻¹⁹ Дж", "10⁻¹⁹ J"),
    "": ("", "", ""), "J": ("Дж", "Дж", "J"),
}


def numeric_tokens(text):
    return Counter(D(value) for value in re.findall(NUMBER, text.replace(",", ".")))


def latex_number(expression):
    number = expression.split("=", 1)[1].split(r"\,", 1)[0]
    match = re.fullmatch(r"(.+?)\\times 10\^\{(-?\d+)\}", number)
    return D(match[1]) * D(10) ** int(match[2]) if match else D(number)


def test_every_generated_topic_has_an_independent_oracle():
    questions = build_topic_exercises()
    assert len(questions) == 2500
    assert {question["topic"] for question in questions} == set(ORACLES)


@pytest.mark.parametrize("topic", tuple(ORACLES))
def test_key_matches_displayed_condition_and_unit(topic):
    from aetherlab.services.ent_physics_bank import questions_for_language

    questions = [question for question in build_topic_exercises() if question["topic"] == topic]
    assert len(questions) == 100
    oracle, expected_unit = ORACLES[topic]
    public = {language: {q["id"]: q for q in questions_for_language(language, topic)}
              for language in ("kk", "ru", "en")}
    assert all(set(bank) == {q["id"] for q in questions} for bank in public.values())
    errors = []
    with localcontext() as context:
        context.prec = 45
        for question in questions:
            expected = oracle(question["prompt"]["en"])
            tolerance = D("0.5").scaleb(expected.adjusted() - 3)
            for language, expected_local_unit in zip(("kk", "ru", "en"), UNITS[expected_unit]):
                keyed = question["choices"][language][question["correct_indices"][0]]
                value, _space, unit = keyed.partition(" ")
                assert unit == expected_local_unit, (question["id"], keyed)
                actual = D(value.replace(",", "."))
                if abs(actual - expected) > tolerance + D("1e-35"):
                    errors.append((question["id"], language, keyed, str(expected)))
                assert numeric_tokens(question["prompt"][language]) == numeric_tokens(question["prompt"]["en"])
                exposed = public[language][question["id"]]
                assert exposed["prompt"] == question["prompt"][language]
                assert exposed["choices"] == question["choices"][language]
                assert exposed["correct_indices"] == question["correct_indices"]
                assert exposed["solution_latex"] == question["solution_latex"]
                assert exposed["answer"] == keyed
            if abs(latex_number(question["solution_latex"][-1]) - expected) > tolerance + D("1e-35"):
                errors.append((question["id"], "LaTeX final value", str(expected)))
    assert not errors, f"{len(errors)}/100 keys disagree with displayed data: {errors[:8]}"


@pytest.mark.parametrize("topic,pattern", (
    ("electrostatics", r"charges are " + NUMBER + r" cm apart"),
    ("relativity", r"moves at " + NUMBER + r"%"),
), ids=("electrostatics", "relativity"))
def test_substitution_uses_the_displayed_input_without_hidden_precision(topic, pattern):
    for question in build_topic_exercises():
        if question["topic"] == topic:
            visible = n(pattern, question["prompt"]["en"])
            substituted = n(r"\(" + NUMBER + r"/100\)", question["solution_latex"][1])
            assert substituted == visible, question["id"]


def test_ac_substitution_uses_the_approximation_given_in_the_condition():
    for question in build_topic_exercises():
        if question["topic"] == "ac_circuits":
            assert "}{1.414}" in question["solution_latex"][1]
            assert "√2≈1.414" in question["prompt"]["en"]


def test_bank_generation_is_deterministic_without_consuming_global_random_state():
    before = random.getstate()
    first = build_topic_exercises()
    second = build_topic_exercises()
    assert first == second
    assert random.getstate() == before


def test_structure_difficulty_bands_and_review_status_are_explicit():
    questions = build_topic_exercises()
    assert len({q["id"] for q in questions}) == 2500
    for topic in ORACLES:
        selected = [q for q in questions if q["topic"] == topic]
        assert Counter(q["difficulty"] for q in selected) == {"A": 50, "B": 30, "C": 20}
        for language in ("kk", "ru", "en"):
            assert len({q["prompt"][language] for q in selected}) == 100
        for question in selected:
            assert question["kind"] == "single" and len(question["correct_indices"]) == 1
            assert 0 <= question["correct_indices"][0] < 4
            assert set(question["prompt"]) == set(question["choices"]) == set(question["explanation"]) == {"kk", "ru", "en"}
            assert all(len(set(choices)) == 4 for choices in question["choices"].values())
            assert question["reviewer"] == "pending_kazakhstan_physics_teacher"
            assert question["language_review_status"] == "pending_teacher_review_kk_ru_en"
            assert question["answer_verification_status"] == "author_checked_teacher_review_pending"
            assert "not an official UNT question" in question["source_note"]


@pytest.mark.parametrize("alias,canonical", (("energy", "conservation"), ("mechanics", "dynamics")))
def test_public_topic_aliases_select_the_same_hundred_questions(alias, canonical):
    from aetherlab.services.ent_physics_bank import questions_for_language

    assert questions_for_language("en", alias) == questions_for_language("en", canonical)
    assert len(questions_for_language("en", alias)) == 100


def test_unknown_topic_is_an_empty_selection():
    from aetherlab.services.ent_physics_bank import questions_for_language

    assert questions_for_language("en", "not-a-topic") == ()


@pytest.mark.parametrize("locale,language", (("kk-KZ", "kk"), ("ru_RU", "ru"), ("en-US", "en"), ("unknown", "en")))
def test_public_locale_normalization_preserves_question_identity(locale, language):
    from aetherlab.services.ent_physics_bank import questions_for_language

    assert questions_for_language(locale) == questions_for_language(language)


def test_mutating_a_public_result_cannot_change_the_shared_bank():
    from aetherlab.services.ent_physics_bank import questions_for_language

    first = questions_for_language("en")[0]
    original = dict(first)
    first.update(prompt="changed", choices=("changed",), correct_indices=(99,), solution_latex=("changed",))
    assert questions_for_language("en")[0] == original


def test_internal_generation_error_propagates_instead_of_returning_a_partial_bank(monkeypatch):
    from dataclasses import replace

    from aetherlab.services import ent_topic_bank

    def unavailable(*values):
        raise ValueError("owned malformed template")

    original = ent_topic_bank.PACKS
    monkeypatch.setattr(ent_topic_bank, "PACKS", (original[0], replace(original[1], calculate=unavailable)))
    with pytest.raises(ValueError, match="owned malformed template"):
        ent_topic_bank.build_topic_exercises()
