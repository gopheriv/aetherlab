from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone

from aetherlab.services.ent_physics_bank import (
    ENT_MAX_POINTS,
    ENT_TOTAL_QUESTIONS,
    QUESTIONS,
    question_max_points,
    score_question,
)
from aetherlab.services.ent_practice_progress import (
    aggregate_topic_progress,
    full_mock_history,
    load_attempts,
    load_goals,
    load_mistake_ids,
    record_attempt,
    save_goals,
    weekly_question_count,
)


def test_practice_bank_matches_current_physics_ent_counts_and_points() -> None:
    assert len(QUESTIONS) == ENT_TOTAL_QUESTIONS == 40
    assert sum(question_max_points(question) for question in QUESTIONS) == ENT_MAX_POINTS == 50
    assert sum(question.kind == "single" and question.context is None for question in QUESTIONS) == 25
    assert sum(question.context is not None for question in QUESTIONS) == 5
    assert sum(question.kind == "multi" for question in QUESTIONS) == 5
    matching = [question for question in QUESTIONS if question.kind == "matching"]
    assert len(matching) == 5
    assert all(len(question.correct_indices) == 2 for question in matching)
    assert all(len(question.matching_left["kk"]) == 2 for question in matching)
    assert Counter(question.difficulty for question in QUESTIONS) == {"A": 20, "B": 12, "C": 8}


def test_hydrostatic_practice_converts_pascals_to_kilopascals() -> None:
    from aetherlab.services.ent_physics_bank import questions_for_language

    for language in ("kk", "ru", "en"):
        question = next(
            item for item in questions_for_language(language)
            if item["id"] == "topic-fluids-011"
        )
        correct_option = question["choices"][question["correct_indices"][0]]
        assert "11" in question["prompt"]
        assert "110" in correct_option
        assert "110" in question["answer"]


def test_single_context_multi_and_matching_use_ent_partial_credit_rules() -> None:
    assert score_question((0,), {"kind": "single", "correct_indices": (0,)}) == 1
    assert score_question((1,), {"kind": "single", "correct_indices": (0,)}) == 0

    one_key = {"kind": "multi", "correct_indices": (0,)}
    assert score_question((0,), one_key) == 2
    assert score_question((0, 1), one_key) == 1
    assert score_question((0, 1, 2), one_key) == 0

    two_key = {"kind": "multi", "correct_indices": (0, 1)}
    assert score_question((0, 1), two_key) == 2
    assert score_question((0,), two_key) == 1
    assert score_question((0, 2), two_key) == 1
    assert score_question((0, 1, 2), two_key) == 1
    assert score_question((0, 2, 3), two_key) == 0

    three_key = {"kind": "multi", "correct_indices": (0, 1, 2)}
    assert score_question((0, 1, 2), three_key) == 2
    assert score_question((0, 1), three_key) == 1
    assert score_question((0, 1, 3), three_key) == 1
    assert score_question((0, 1, 2, 3), three_key) == 1
    assert score_question((0,), three_key) == 0
    assert score_question((0, 1, 3, 4), three_key) == 0

    matching = {"kind": "matching", "correct_indices": (1, 0)}
    assert score_question((1, 0), matching) == 2
    assert score_question((1, 1), matching) == 1
    assert score_question((-1, 0), matching) == 1
    assert score_question((0, 1), matching) == 0


def test_goals_progress_and_mistake_review_persist_only_safe_summary(tmp_path) -> None:
    path = tmp_path / "ent-progress.json"
    saved = save_goals(
        path,
        {
            "target_score": 42,
            "exam_date": "2027-06-20",
            "weekly_question_goal": 80,
            "weekly_mock_day": 0,
            "preparation_level": "intermediate",
        },
    )
    assert saved == load_goals(path)
    assert saved["weekly_mock_day"] == 0
    assert save_goals(path, {"weekly_mock_day": 7})["weekly_mock_day"] is None

    missed_id = QUESTIONS[0].id
    answered_id = QUESTIONS[1].id
    attempts = record_attempt(
        path,
        language="kk",
        topic_results={
            QUESTIONS[0].topic: {
                "correct": 1,
                "total": 2,
                "points": 2,
                "max_points": 3,
            }
        },
        question_results={missed_id: False, answered_id: True},
        score=2,
        possible_points=3,
        mode="timed",
    )
    assert load_mistake_ids(path) == (missed_id,)
    assert attempts[-1]["missed_question_ids"] == [missed_id]
    assert aggregate_topic_progress(attempts)[QUESTIONS[0].topic]["points"] == 2
    assert weekly_question_count(attempts) == 2
    assert full_mock_history(attempts) == []

    record_attempt(
        path,
        language="ru",
        topic_results={QUESTIONS[0].topic: {"correct": 1, "total": 1, "points": 1, "max_points": 1}},
        question_results={missed_id: True},
        score=1,
        possible_points=1,
        mode="mistake_review",
    )
    assert load_mistake_ids(path) == ()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "answers" not in payload["attempts"][-1]
    assert payload["attempts"][-1]["missed_question_ids"] == []

    record_attempt(
        path,
        language="en",
        topic_results={},
        question_results={question.id: True for question in QUESTIONS},
        score=50,
        possible_points=50,
        mode="timed",
        full_mock=True,
    )
    assert len(full_mock_history(load_attempts(path))) == 1


def test_weekly_question_count_ignores_old_or_malformed_history() -> None:
    now = datetime.now(timezone.utc)
    attempts = [
        {"completed_at": now.isoformat(), "question_count": 7},
        {"completed_at": "not a timestamp", "question_count": 99},
    ]
    assert weekly_question_count(attempts, today=now.date()) == 7


def test_practice_dialog_starts_and_reports_a_50_point_mock_in_all_languages(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from aetherlab.ui.exam_practice import ExamPracticeDialog
    from aetherlab.ui.qt_compat import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert app is not None
    progress_path = tmp_path / "dialog-progress.json"

    for language in ("kk", "ru", "en"):
        dialog = ExamPracticeDialog(language, progress_path=progress_path)
        dialog._mode_buttons[1].click()  # explicitly choose the full mock mode
        dialog._start()
        assert len(dialog._questions) == ENT_TOTAL_QUESTIONS
        assert dialog._questions[0]["prompt"]
        dialog._mode = "timed"
        dialog._full_mock = True
        dialog._answers = [tuple(question["correct_indices"]) for question in dialog._questions]
        dialog._show_results()
        assert "50/50" in dialog._score.text()
        assert "40" in dialog._score.text()
        dialog.close()
