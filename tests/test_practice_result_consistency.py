"""Practice totals must agree in the UI, local history and exported report."""

from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aetherlab.services import ent_practice_progress as progress
from aetherlab.services.ent_physics_bank import questions_for_language
from aetherlab.ui.exam_practice import ExamPracticeDialog
from aetherlab.ui.qt_compat import QtWidgets

_APP = None


def _app():
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


def test_early_finish_pdf_totals_equal_screen_and_history(tmp_path, monkeypatch):
    _app()
    from aetherlab.services import ent_practice_pdf

    calls = []
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *args: (str(tmp_path / "result.pdf"), ""))
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", lambda *args: None)
    monkeypatch.setattr(ent_practice_pdf, "export_practice_pdf", lambda path, **kwargs: calls.append(kwargs))
    for language in ("kk", "ru", "en"):
        path = tmp_path / f"{language}.json"
        questions = questions_for_language(language, "kinematics")[:10]
        dialog = ExamPracticeDialog(language, progress_path=path)
        dialog._begin_session(questions, "practice")
        dialog._answers[0] = tuple(questions[0]["correct_indices"])
        dialog._answers[4] = tuple(questions[4]["correct_indices"])
        dialog._show_results()
        assert "2/2" in dialog._score.text()
        assert progress.load_attempts(path)[-1]["question_count"] == 2
        dialog._save_pdf()
        exported = calls[-1]
        assert exported["score"] == 2 and exported["possible_points"] == 2
        assert exported["scored_question_count"] == 2
        assert exported["question_counted"] == [True, False, False, False, True] + [False] * 5
        assert len(exported["questions"]) == len(exported["user_answers"]) == 10
        assert dialog._t["not_counted"] in dialog._review.toPlainText()
        dialog.close()


def test_empty_practice_pdf_does_not_claim_zero_out_of_selected_set(tmp_path, monkeypatch):
    _app()
    from aetherlab.services import ent_practice_pdf

    calls = []
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *args: (str(tmp_path / "empty.pdf"), ""))
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", lambda *args: None)
    monkeypatch.setattr(ent_practice_pdf, "export_practice_pdf", lambda path, **kwargs: calls.append(kwargs))
    dialog = ExamPracticeDialog("en", progress_path=tmp_path / "empty.json")
    dialog._begin_session(questions_for_language("en", "kinematics")[:10], "practice")
    dialog._show_results()
    dialog._save_pdf()
    assert calls[-1]["score"] == calls[-1]["possible_points"] == calls[-1]["scored_question_count"] == 0
    assert not any(calls[-1]["question_counted"])
    dialog.close()


def test_timed_pdf_keeps_unanswered_questions_in_possible_score(tmp_path, monkeypatch):
    _app()
    from aetherlab.services import ent_practice_pdf

    calls = []
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *args: (str(tmp_path / "timed.pdf"), ""))
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", lambda *args: None)
    monkeypatch.setattr(ent_practice_pdf, "export_practice_pdf", lambda path, **kwargs: calls.append(kwargs))
    dialog = ExamPracticeDialog("en", progress_path=tmp_path / "timed.json")
    questions = questions_for_language("en", "kinematics")[:10]
    dialog._begin_session(questions, "timed")
    dialog._answers[0] = tuple(questions[0]["correct_indices"])
    dialog._show_results()
    dialog._save_pdf()
    assert calls[-1]["score"] == 1 and calls[-1]["possible_points"] == 10
    assert calls[-1]["scored_question_count"] == 10
    assert all(calls[-1]["question_counted"])
    dialog.close()


def test_progress_nonfinite_numbers_do_not_crash_or_turn_into_scores(tmp_path):
    path = tmp_path / "nonfinite.json"
    payload = {"goals": {"target_score": float("inf"), "weekly_question_goal": float("inf"), "weekly_mock_day": float("inf")},
               "companion_total_points": float("inf"),
               "attempts": [{"score": float("inf"), "possible_points": 50, "full_mock": True}, {"score": 12, "possible_points": 20}]}
    path.write_text(json.dumps(payload), encoding="utf-8")
    before = path.read_bytes()
    snapshot = progress.load_progress_snapshot(path)
    assert snapshot.goals["target_score"] is None
    assert snapshot.goals["weekly_question_goal"] is None
    assert snapshot.goals["weekly_mock_day"] is None
    assert snapshot.companion_points == 12
    assert len(snapshot.attempts) == 1
    assert path.read_bytes() == before


def test_invalid_aggregate_records_do_not_crash_student_views(tmp_path):
    _app()
    from aetherlab.ui.student_views import ProgressOverview, StudentDashboard, TopicCatalogView

    path = tmp_path / "bad-history.json"
    path.write_text(json.dumps({"attempts": [{"score": "broken", "possible_points": 50, "full_mock": True},
        {"score": 42, "possible_points": 50, "full_mock": True, "question_count": 40,
         "topics": {"kinematics": {"correct": 4, "total": 5}}}]}), encoding="utf-8")
    before = path.read_bytes()
    views = [StudentDashboard(path, language="en"), ProgressOverview(path, language="en"), TopicCatalogView(path, language="en")]
    assert views[0].metric_labels["best"][0].text() == "42/50"
    assert views[0].metric_labels["attempts"][0].text() == "1"
    assert views[0].progress_notice.status.text() == views[0].progress_notice.copy["recovered"]
    assert len(progress.full_mock_history(progress.load_attempts(path))) == 1
    assert path.read_bytes() == before
    for view in views:
        view.close()


def test_nonfinite_progress_mutation_recovers_points_from_valid_history(tmp_path):
    path = tmp_path / "points.json"
    path.write_text(json.dumps({"companion_total_points": float("inf"), "attempts": [{"score": 12}, {"score": float("inf")}]}), encoding="utf-8")
    progress.record_attempt(path, language="en", topic_results={}, score=5, possible_points=5)
    assert progress.load_companion_points(path) == 17
    assert len(progress.load_attempts(path)) == 2


def test_pdf_contains_rendered_formulas_and_complete_source_block(tmp_path):
    _app()
    import fitz

    from aetherlab.services.ent_practice_pdf import export_practice_pdf

    questions = questions_for_language("ru", "kinematics")[:2]
    output = tmp_path / "formulas.pdf"
    export_practice_pdf(output, language="ru", questions=questions, user_answers=[], topic_names={"kinematics": "Кинематика"}, topic_progress={}, score=0)
    with fitz.open(output) as document:
        assert len(document) == 4  # summary, two complete worked questions, sources
        text = "".join(page.get_text() for page in document)
        assert "\\cdot" not in text
        assert sum(len(page.get_images()) for page in document) >= 6
        last = document[-1].get_text()
        assert "Источники" in last and "NCT free practice portal" in " ".join(last.split())
        assert "Разбор" in document[2].get_text()
        assert len(document[2].get_images()) >= 3


def test_formula_failure_does_not_replace_an_existing_report(tmp_path, monkeypatch):
    _app()
    import pytest

    from aetherlab.services import ent_practice_pdf

    output = tmp_path / "existing.pdf"
    output.write_bytes(b"existing user report")
    monkeypatch.setattr(ent_practice_pdf, "render_math", lambda *args, **kwargs: None)
    with pytest.raises(RuntimeError, match="formula"):
        ent_practice_pdf.export_practice_pdf(output, language="en", questions=questions_for_language("en", "kinematics")[:1], user_answers=[], topic_names={}, topic_progress={}, score=0)
    assert output.read_bytes() == b"existing user report"


def test_unattempted_review_label_does_not_imply_deduction(tmp_path):
    _app()
    for language in ("kk", "ru", "en"):
        dialog = ExamPracticeDialog(language, progress_path=tmp_path / f"review-{language}.json")
        questions = questions_for_language(language, "kinematics")[:2]
        dialog._begin_session(questions, "practice")
        dialog._answers[0] = tuple(questions[0]["correct_indices"])
        dialog._show_results()
        text = dialog._review.toPlainText()
        assert text.count(dialog._t["not_counted"]) == 1
        assert "1/1" in dialog._score.text()
        assert dialog._t["points_feedback"].format(score=0, possible=1) not in text
        dialog.close()


def test_all_topic_formula_templates_can_be_rendered_for_report():
    _app()
    from aetherlab.services.ent_physics_bank import ENT_TOPIC_IDS
    from aetherlab.services.mathtext import render_math

    for topic in ENT_TOPIC_IDS:
        question = questions_for_language("en", topic)[0]
        assert question["solution_latex"]
        for expression in question["solution_latex"]:
            assert render_math(expression, px_size=60, color="#172033") is not None, (topic, expression)
