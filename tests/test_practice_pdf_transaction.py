"""A failed PDF export must not overwrite or claim an earlier report."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from aetherlab.services import ent_practice_pdf
from aetherlab.services.ent_physics_bank import questions_for_language
from aetherlab.ui.qt_compat import QtWidgets

_APP = None


def test_pdf_export_never_initializes_a_system_printer(tmp_path, monkeypatch):
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    import fitz
    from PyQt6 import QtPrintSupport

    def unavailable_printer(*args, **kwargs):
        raise RuntimeError("system printer is unavailable")

    monkeypatch.setattr(QtPrintSupport, "QPrinter", unavailable_printer)
    if hasattr(ent_practice_pdf, "QPrinter"):
        monkeypatch.setattr(ent_practice_pdf, "QPrinter", unavailable_printer)
    output = tmp_path / "without-printer.pdf"
    ent_practice_pdf.export_practice_pdf(
        output, language="ru", questions=questions_for_language("ru", "kinematics")[:1],
        user_answers=[], topic_names={}, topic_progress={}, score=0,
    )
    with fitz.open(output) as report:
        assert "ЕНТ" in report[0].get_text()


def _failed_printer(tmp_path, monkeypatch, failure):
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    output = tmp_path / "existing.pdf"
    before = b"previous student report\n" * 60
    output.write_bytes(before)
    stage = tmp_path / "failed.tmp.pdf"
    monkeypatch.setattr(ent_practice_pdf, "unique_staging_path", lambda destination: stage)

    def failed_print(document, printer):
        if failure != "no_output":
            stage.write_bytes(
                b"%PDF-1.4\n" if failure == "partial_output" else b"%PDF-1.4\n" + b"broken" * 200
            )

    monkeypatch.setattr(ent_practice_pdf.QTextDocument, "print", failed_print)
    with pytest.raises(RuntimeError, match="PDF"):
        ent_practice_pdf.export_practice_pdf(
            output, language="en", questions=questions_for_language("en", "kinematics")[:1],
            user_answers=[], topic_names={}, topic_progress={}, score=0,
        )
    assert output.read_bytes() == before
    assert list(tmp_path.iterdir()) == [output]


def test_missing_printer_output_does_not_claim_existing_report(tmp_path, monkeypatch):
    _failed_printer(tmp_path, monkeypatch, "no_output")


def test_partial_printer_output_preserves_existing_report(tmp_path, monkeypatch):
    _failed_printer(tmp_path, monkeypatch, "partial_output")


def test_invalid_printer_output_preserves_existing_report(tmp_path, monkeypatch):
    _failed_printer(tmp_path, monkeypatch, "invalid_output")


def test_denied_replacement_preserves_report_and_cleans_stage(tmp_path, monkeypatch):
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    output = tmp_path / "locked.pdf"
    before = b"previous student report\n" * 60
    output.write_bytes(before)

    def denied_replace(stage, destination):
        raise PermissionError("student report is locked")

    monkeypatch.setattr(ent_practice_pdf.os, "replace", denied_replace)
    with pytest.raises(PermissionError, match="locked"):
        ent_practice_pdf.export_practice_pdf(
            output, language="en", questions=questions_for_language("en", "kinematics")[:1],
            user_answers=[], topic_names={}, topic_progress={}, score=0,
        )
    assert output.read_bytes() == before
    assert list(tmp_path.iterdir()) == [output]


def test_textless_pdf_is_rejected_without_replacing_report(tmp_path, monkeypatch):
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    import fitz

    output = tmp_path / "textless.pdf"
    before = b"previous student report\n" * 60
    output.write_bytes(before)

    stage = tmp_path / "textless.tmp.pdf"
    monkeypatch.setattr(ent_practice_pdf, "unique_staging_path", lambda destination: stage)

    def blank_print(document, printer):
        with fitz.open() as report:
            report.new_page()
            report.save(stage)

    monkeypatch.setattr(ent_practice_pdf.QTextDocument, "print", blank_print)
    with pytest.raises(RuntimeError, match="PDF"):
        ent_practice_pdf.export_practice_pdf(
            output, language="en", questions=(), user_answers=[],
            topic_names={}, topic_progress={}, score=0,
        )
    assert output.read_bytes() == before
    assert list(tmp_path.iterdir()) == [output]


def test_export_ui_reports_print_failure_and_retry_saves_new_report(tmp_path, monkeypatch):
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    import fitz

    from aetherlab.ui.exam_practice import ExamPracticeDialog

    warnings, confirmations = [], []
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", lambda *args: warnings.append(args[2]))
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", lambda *args: confirmations.append(args[2]))
    for language in ("kk", "ru", "en"):
        output = tmp_path / f"ui-{language}.pdf"
        before = b"previous student report\n" * 60
        output.write_bytes(before)
        monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *args: (str(output), ""))
        dialog = ExamPracticeDialog(language, progress_path=tmp_path / f"progress-{language}.json")
        questions = questions_for_language(language, "kinematics")[:1]
        dialog._begin_session(questions, "practice")
        dialog._answers[0] = tuple(questions[0]["correct_indices"])
        dialog._show_results()
        saved_history = dialog._progress_path.read_bytes()
        confirmation_count = len(confirmations)
        with monkeypatch.context() as printing:
            printing.setattr(ent_practice_pdf.QTextDocument, "print", lambda *args: None)
            dialog._save_pdf()
        assert len(confirmations) == confirmation_count
        assert dialog._t["pdf_error"].split("{error}")[0] in warnings[-1]
        assert output.read_bytes() == before
        dialog._save_pdf()
        assert len(confirmations) == confirmation_count + 1
        with fitz.open(output) as report:
            text = " ".join(" ".join(page.get_text() for page in report).split())
            assert "1/1" in text and "NCT free practice portal" in text
        assert dialog._progress_path.read_bytes() == saved_history
        assert not list(tmp_path.glob("*.tmp.pdf"))
        dialog.close()
