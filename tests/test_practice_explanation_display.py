"""Readable practice prose must preserve math and its canonical source."""

from __future__ import annotations

import copy
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from aetherlab.services.ent_physics_bank import questions_for_language
from aetherlab.ui.exam_practice import ExamPracticeDialog
from aetherlab.ui.qt_compat import QtWidgets

_APP = None


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_feedback_and_review_do_not_expose_latex(language, tmp_path):
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    questions = questions_for_language(language, "kinematics")[:2]
    original = copy.deepcopy(questions)
    dialog = ExamPracticeDialog(language, progress_path=tmp_path / f"{language}.json")
    dialog._begin_session(questions, "practice")
    dialog._answers[0] = tuple(questions[0]["correct_indices"])
    dialog._show_feedback(questions[0])
    feedback = dialog._feedback.text()
    assert "\\" not in feedback and "v_0" not in feedback
    assert "v₀" in feedback and "·" in feedback
    assert dialog._solution_math_layout.count() == 3
    dialog._show_results()
    review = dialog._review.toPlainText()
    assert "\\" not in review and "v_0" not in review
    assert "v₀" in review
    _APP.processEvents()
    assert dialog._review.font().family() == _APP.font().family()
    assert dialog._review.font().pixelSize() >= 14 or dialog._review.font().pointSizeF() >= 10.5
    assert questions == original
    dialog.close()


@pytest.mark.parametrize(("source", "expected"), (
    (r"v=v_0+at", "v=v₀+at"),
    (r"\frac{1}{1/5-1/10}", "(1)/(1/5-1/10)"),
    (r"\frac{1}{\sqrt{1-v^2/c^2}}", "(1)/(√(1-v²/c²))"),
    (r"\overline{E}=\frac{3}{2}kT", "Ē=(3)/(2)kT"),
    (r"N=N_0\left(\frac{1}{2}\right)^n", "N=N₀((1)/(2))ⁿ"),
    (r"U=\frac{U_{max}}{\sqrt{2}}", "U=(U_(max))/(√(2))"),
    (r"1\,\mathrm{nm}=10^{-9}\,\mathrm{m}", "1 nm=10⁻⁹ m"),
))
def test_readable_formula_preserves_grouping_and_scripts(source, expected):
    from aetherlab.services.practice_math import readable_formula
    assert readable_formula(source) == expected


def test_unsupported_or_incomplete_formula_is_not_guessed():
    from aetherlab.services.practice_math import readable_formula
    for source in (r"\unknown{x}", r"\frac{1}", r"\sqrt{1", "x}"):
        with pytest.raises(ValueError):
            readable_formula(source)


def test_all_topic_explanations_are_readable_without_changing_questions():
    from aetherlab.services.practice_math import readable_explanation
    for language in ("kk", "ru", "en"):
        questions = questions_for_language(language)
        original = copy.deepcopy(questions)
        for question in questions:
            text = readable_explanation(question, language)
            assert "\\" not in text, (language, question["id"], text)
            assert "{" not in text and "}" not in text, (language, question["id"], text)
            assert question["answer"] in text
        assert questions == original


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_perfect_small_sample_does_not_claim_mistakes_or_a_weak_topic(language, tmp_path):
    from aetherlab.services.ent_practice_progress import record_attempt
    from aetherlab.ui.student_views import _COPY, StudentDashboard

    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    path = tmp_path / f"perfect-{language}.json"
    record_attempt(path, language=language, topic_results={"kinematics": {"correct": 2, "total": 2}},
                   score=2, possible_points=2)
    dashboard = StudentDashboard(path, language=language)
    assert dashboard.next_description.text() != _COPY[language]["next_review"].format(accuracy=100)
    assert "2/2" in dashboard.next_description.text()
    questions = questions_for_language(language, "kinematics")[:2]
    dialog = ExamPracticeDialog(language, progress_path=tmp_path / f"dialog-{language}.json")
    dialog._begin_session(questions, "practice")
    dialog._answers[0] = tuple(questions[0]["correct_indices"])
    dialog._show_results()
    assert dialog._recommend_button.text() != dialog._t["practice_weakest"]
    assert "1/1" in dialog._recommendation.text()
    # A later wrong attempt must restore the review action rather than retain
    # the previous congratulatory text; it remains a concrete practice action.
    dialog._begin_session(questions, "practice")
    wrong = next(i for i in range(len(questions[0]["choices"])) if i not in questions[0]["correct_indices"])
    dialog._answers[0] = (wrong,)
    dialog._show_results()
    assert dialog._recommend_button.text() == dialog._t["practice_weakest"]
    record_attempt(path, language=language, topic_results={"kinematics": {"correct": 0, "total": 2}},
                   question_results={questions[0]["id"]: False, questions[1]["id"]: False},
                   score=0, possible_points=2)
    dashboard.refresh()
    assert dashboard.next_description.text() == _COPY[language]["next_review"].format(accuracy=50)
    dialog.close()
    dashboard.close()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_cleared_mistakes_do_not_remain_a_dashboard_action(language, tmp_path):
    from aetherlab.services.ent_practice_progress import record_attempt
    from aetherlab.ui.student_views import _COPY, StudentDashboard

    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    path = tmp_path / f"cleared-{language}.json"
    question = questions_for_language(language, "kinematics")[0]
    record_attempt(path, language=language, topic_results={"kinematics": {"correct": 0, "total": 1}},
                   question_results={question["id"]: False}, score=0, possible_points=1)
    dashboard = StudentDashboard(path, language=language)
    assert dashboard.next_description.text() == _COPY[language]["next_review"].format(accuracy=0)
    record_attempt(path, language=language, topic_results={"kinematics": {"correct": 1, "total": 1}},
                   question_results={question["id"]: True}, score=1, possible_points=1,
                   mode="mistake_review")
    dashboard.refresh()
    assert dashboard.metric_labels["mistakes"][0].text() == "0"
    assert dashboard.next_description.text() != _COPY[language]["next_review"].format(accuracy=50)
    assert "1/2" in dashboard.next_description.text()
    # A pending mistake in a different topic must not revive this topic's action.
    other = questions_for_language(language, "dynamics")[0]
    record_attempt(path, language=language, topic_results={"dynamics": {"correct": 2, "total": 3}},
                   question_results={other["id"]: False}, score=2, possible_points=3)
    dashboard.refresh()
    assert dashboard.metric_labels["mistakes"][0].text() == "1"
    assert dashboard._hero_topic_id == "kinematics"
    assert dashboard.next_description.text() != _COPY[language]["next_review"].format(accuracy=50)
    assert "1/2" in dashboard.next_description.text()
    dashboard.close()


@pytest.mark.parametrize("language", ("kk", "ru", "en"))
def test_mock_mistakes_are_recommended_in_their_topic(language, tmp_path):
    from aetherlab.services.ent_physics_bank import mock_questions_for_language
    from aetherlab.services.ent_practice_progress import record_attempt
    from aetherlab.ui.student_views import _COPY, StudentDashboard

    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    path = tmp_path / f"mock-mistake-{language}.json"
    question = mock_questions_for_language(language, "dynamics")[0]
    record_attempt(path, language=language, topic_results={"dynamics": {"correct": 0, "total": 1}},
                   question_results={question["id"]: False}, score=0, possible_points=50,
                   mode="timed", full_mock=True)
    dashboard = StudentDashboard(path, language=language)
    assert dashboard.metric_labels["mistakes"][0].text() == "1"
    assert dashboard._hero_topic_id == "dynamics"
    assert dashboard.next_description.text() == _COPY[language]["next_review"].format(accuracy=0)
    record_attempt(path, language=language, topic_results={"dynamics": {"correct": 1, "total": 1}},
                   question_results={question["id"]: True}, score=1, possible_points=1,
                   mode="mistake_review")
    dashboard.refresh()
    assert dashboard.metric_labels["mistakes"][0].text() == "0"
    assert dashboard.next_description.text() == _COPY[language]["next_reinforce"].format(correct=1, total=2)
    dashboard.close()
