"""Searchable, Unicode-safe PDF export for ENT physics practice results."""

from __future__ import annotations

import os
from html import escape
from pathlib import Path

import fitz
from PyQt6 import QtGui
from PyQt6.QtCore import QMarginsF, QUrl
from PyQt6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument

from aetherlab.core.atomic_file import unique_staging_path
from aetherlab.services.ent_physics_bank import (
    FREE_MOCK_URL,
    SOURCE_URL,
    question_max_points,
)
from aetherlab.services.mathtext import render_math
from aetherlab.ui.fonts import install_ui_fonts

_TEXT = {
    "kk": {
        "title": "ҰБТ · Физика бойынша дайындық",
        "set": "PhysLab авторлық оқу жинағы · ресми тест нұсқасы емес",
        "score": "Нәтиже",
        "topics": "Тақырыптар бойынша прогресс",
        "question": "Тапсырма",
        "your": "Сіздің жауабыңыз",
        "correct": "Дұрыс жауап",
        "solution": "Түсіндіру",
        "term": "Қазақша термин",
        "context": "Жағдаят",
        "choices": "Жауап нұсқалары",
        "sources": "Дереккөздер",
        "official_notice": "Бұл оқу материалы. Ресми байқау ҰБТ-ына сілтеме:",
        "items": "Тапсырма саны",
        "all_questions": "Барлық тапсырмалар",
        "not_answered": "Жауап берілмеді",
        "not_counted": "Орындалмады - жаттығу нәтижесіне кірмейді",
        "equations_below": "төмендегі формулаларды қараңыз",
        "score_detail": "{score}/{possible} ұпай · {items} тапсырма",
        "question_score": "Ұпай",
        "topic_accuracy": "Дұрыс / барлығы",
        "topic_points": "Ұпай",
    },
    "ru": {
        "title": "ЕНТ · Подготовка по физике",
        "set": "Авторский учебный набор PhysLab · не официальный вариант",
        "score": "Результат",
        "topics": "Прогресс по темам",
        "question": "Задание",
        "your": "Ваш ответ",
        "correct": "Правильный ответ",
        "solution": "Разбор",
        "term": "Термин на казахском",
        "context": "Контекст",
        "choices": "Варианты ответа",
        "sources": "Источники",
        "official_notice": "Это учебный материал. Ссылка на официальное пробное ЕНТ:",
        "items": "Заданий в наборе",
        "all_questions": "Все задания",
        "not_answered": "Без ответа",
        "not_counted": "Не решено - не входит в результат тренировки",
        "equations_below": "см. формулы ниже",
        "score_detail": "{score}/{possible} баллов · {items} заданий",
        "question_score": "Баллы",
        "topic_accuracy": "Верно / всего",
        "topic_points": "Баллы",
    },
    "en": {
        "title": "UNT · Physics practice",
        "set": "Original PhysLab study set · not an official test variant",
        "score": "Score",
        "topics": "Progress by topic",
        "question": "Question",
        "your": "Your answer",
        "correct": "Correct answer",
        "solution": "Explanation",
        "term": "Kazakh term",
        "context": "Context",
        "choices": "Answer choices",
        "sources": "Sources",
        "official_notice": "This is study material. Official free practice test:",
        "items": "Questions in this set",
        "all_questions": "All questions",
        "not_answered": "Not answered",
        "not_counted": "Not attempted - excluded from the practice result",
        "equations_below": "see the formulas below",
        "score_detail": "{score}/{possible} points · {items} questions",
        "question_score": "Points",
        "topic_accuracy": "Correct / total",
        "topic_points": "Points",
    },
}


def export_practice_pdf(
    output_path: Path,
    *,
    language: str,
    questions: tuple[dict, ...],
    user_answers: list[str],
    topic_names: dict[str, str],
    topic_progress: dict[str, dict[str, int]],
    score: int,
    possible_points: int | None = None,
    question_points: list[int] | None = None,
    scored_question_count: int | None = None,
    question_counted: list[bool] | None = None,
) -> Path:
    """Write a selectable-text A4 PDF using the app's embedded DejaVu font."""
    language = language if language in _TEXT else "kk"
    t = _TEXT[language]
    if possible_points is None:
        possible_points = sum(question_max_points(question) for question in questions)
    if scored_question_count is None:
        scored_question_count = len(questions)
    install_ui_fonts()
    equation_images = []

    def p(value: object) -> str:
        return escape(str(value or "")).replace("\n", "<br/>")

    fragments = [
        "<!doctype html><html><head><meta charset='utf-8'><style>",
        "body{font-family:'DejaVu Sans';font-size:10pt;color:#172033;line-height:1.35}",
        "h1{font-size:22pt;color:#0E7490;margin:0 0 5pt}",
        "h2{font-size:12pt;color:#0F172A;margin:13pt 0 4pt}",
        ".subtitle{color:#475569;font-size:9pt;margin-bottom:12pt}",
        ".banner{background:#E6F7FA;border-left:3px solid #0891B2;padding:8pt;margin:8pt 0}",
        ".context{background:#F1F5F9;border-left:2px solid #94A3B8;padding:7pt;margin:5pt 0}",
        ".answer{background:#ECFDF5;padding:7pt;margin:5pt 0}",
        ".question{border-bottom:1px solid #CBD5E1;padding-bottom:7pt;margin-bottom:6pt;page-break-inside:avoid}",
        ".meta{font-size:8pt;color:#64748B}",
        "a{color:#0369A1;text-decoration:underline}",
        "table{width:100%;border-collapse:collapse;font-size:8.5pt}",
        "th{background:#E2E8F0;text-align:left}th,td{padding:4pt;border-bottom:1px solid #E2E8F0}",
        "</style></head><body>",
        f"<h1>{p(t['title'])}</h1><div class='subtitle'>{p(t['set'])}</div>",
        f"<div class='banner'><b>{p(t['score'])}:</b> "
        f"{p(t['score_detail'].format(score=score, possible=possible_points, items=scored_question_count))}</div>",
        f"<h2>{p(t['topics'])}</h2><table width='100%' cellpadding='4' cellspacing='0'><thead><tr><th>{p(t['question'])}</th>"
        f"<th>{p(t['topic_accuracy'])}</th><th>{p(t['topic_points'])}</th></tr></thead><tbody>",
    ]
    for topic_id, label in topic_names.items():
        stat = topic_progress.get(topic_id, {"correct": 0, "total": 0})
        total = int(stat.get("total", 0))
        correct = int(stat.get("correct", 0))
        points = int(stat.get("points", 0))
        max_points = int(stat.get("max_points", 0))
        fragments.append(
            f"<tr><td>{p(label)}</td><td>{correct} / {total if total else '—'}</td>"
            f"<td>{points} / {max_points if max_points else '—'}</td></tr>"
        )
    fragments.append("</tbody></table><div style='page-break-before:always'></div><h2>" + p(t["all_questions"]) + "</h2>")

    for index, question in enumerate(questions):
        formulas_on_page = bool(question.get("solution_latex") or (index and questions[index - 1].get("solution_latex")))
        if index and (formulas_on_page or index % 2 == 0):
            fragments.append("<div style='page-break-before:always'></div>")
        user_answer = user_answers[index] if index < len(user_answers) else t["not_answered"]
        earned = question_points[index] if question_points and index < len(question_points) else 0
        maximum = question_max_points(question)
        counted = question_counted is None or index >= len(question_counted) or question_counted[index]
        point_label = f"{earned}/{maximum}" if counted else t["not_counted"]
        fragments.append("<div class='question'>")
        fragments.append(
            f"<h2>{p(t['question'])} {index + 1}</h2>"
            f"<div class='meta'>{p(topic_names.get(question['topic'], question['topic']))}"
            f" · {p(question['difficulty'])} · {p(t['question_score'])}: {p(point_label)}</div>"
        )
        if question.get("context"):
            fragments.append(f"<div class='context'><b>{p(t['context'])}:</b> {p(question['context'])}</div>")
        fragments.append(f"<p>{p(question['prompt'])}</p>")
        fragments.append(f"<p class='meta'><b>{p(t['choices'])}:</b></p><ol type='A'>")
        fragments.extend(f"<li>{p(choice)}</li>" for choice in question["choices"])
        fragments.append("</ol>")
        fragments.append(
            f"<div class='answer'><b>{p(t['your'])}:</b> {p(user_answer)}<br/>"
            f"<b>{p(t['correct'])}:</b> {p(question['answer'])}</div>"
        )
        explanation = question['explanation']
        equations = []
        for equation_index, expression in enumerate(question.get("solution_latex", ())):
            formula = str(expression).strip()
            if not formula:
                continue
            pixmap = render_math(formula, px_size=60, color="#172033")
            if pixmap is None:
                raise RuntimeError("A solution formula could not be rendered.")
            url = QUrl(f"physlab-equation:{index}-{equation_index}")
            equation_images.append((url, pixmap.toImage()))
            size = pixmap.deviceIndependentSize()
            width, height = max(1, round(size.width() / 3)), max(1, round(size.height() / 3))
            equations.append(f"<p><img src='{url.toString()}' width='{width}' height='{height}' /></p>")
            for candidate in (formula, formula.split("=", 1)[-1]):
                if any(symbol in candidate for symbol in ("\\", "_", "^")):
                    explanation = explanation.replace(candidate, t["equations_below"])
        fragments.append(f"<p><b>{p(t['solution'])}:</b> {p(explanation)}</p>")
        fragments.extend(equations)
        fragments.append(
            f"<p class='meta'><b>{p(t['term'])}:</b> {p(question['kazakh_term'])}"
            f" — {p(question.get('term_meaning', ''))}</p></div>"
        )
    fragments.extend([
        f"<h2 style='page-break-before:always'>{p(t['sources'])}</h2>",
        f"<p><a href='{SOURCE_URL}'>NCT physics specification and preparation materials</a></p>",
        f"<p>{p(t['official_notice'])} <a href='{FREE_MOCK_URL}'>NCT free practice portal</a>.</p>",
        "</body></html>",
    ])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    document = QTextDocument()
    document.setDefaultFont(QtGui.QFont("DejaVu Sans", 10))
    document.setDocumentMargin(4)
    document.setMetaInformation(QTextDocument.MetaInformation.DocumentTitle, t["title"])
    for url, image in equation_images:
        document.addResource(QTextDocument.ResourceType.ImageResource, url, image)
    document.setHtml("".join(fragments))
    stage = unique_staging_path(output_path)
    writer = None
    try:
        # A PDF-only paint device avoids QPrinter's default-printer discovery,
        # which can block a native Windows export on an unavailable printer.
        writer = QPdfWriter(str(stage))
        writer.setTitle(t["title"])
        writer.setResolution(300)
        writer.setPageLayout(QPageLayout(
            QPageSize(QPageSize.PageSizeId.A4),
            QPageLayout.Orientation.Portrait,
            QMarginsF(16, 16, 16, 18),
            QPageLayout.Unit.Millimeter,
        ))
        document.print(writer)
        # Finalize and release the output handle before inspection/replacement.
        writer = None
        if not stage.exists() or stage.stat().st_size < 512:
            raise RuntimeError("Qt did not create a complete PDF file.")
        try:
            with fitz.open(stage) as report:
                if not report.is_pdf or not len(report):
                    raise RuntimeError("Qt did not create a readable PDF report.")
                first_page = " ".join(report[0].get_text().split())
                if " ".join(t["title"].split()) not in first_page:
                    raise RuntimeError("The PDF report has missing or unreadable text.")
        except fitz.FileDataError as exc:
            raise RuntimeError("Qt did not create a readable PDF report.") from exc
        with stage.open("r+b") as stream:
            os.fsync(stream.fileno())
        os.replace(stage, output_path)
    finally:
        writer = None
        try:
            stage.unlink(missing_ok=True)
        except OSError:
            pass
    return output_path
