"""Derivation steps, verification notes, and export controls."""

from __future__ import annotations

from aetherlab.core.models import SolverResult
from aetherlab.ui import icons
from aetherlab.ui.qt_compat import QtCore, QtWidgets, require_qt
from aetherlab.ui.shared_widgets import _copy_to_clipboard

require_qt()

class _CollapsibleStepWidget(QtWidgets.QWidget):
    """Single collapsible derivation step with expand/collapse toggle."""

    def __init__(
        self, index: int, text: str, evidence: dict | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QtWidgets.QWidget()
        header.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(6, 4, 6, 4)
        header_layout.setSpacing(8)

        self._arrow = QtWidgets.QLabel("\u25b6")
        self._arrow.setFixedWidth(14)
        self._arrow.setStyleSheet("color: #65758A; font-size: 10px;")
        header_layout.addWidget(self._arrow)

        step_num = QtWidgets.QLabel(f"Step {index}")
        step_num.setStyleSheet(
            "color: #486A91; font-size: 11px; font-weight: 700; "
            "font-family: 'Cascadia Code', monospace;"
        )
        header_layout.addWidget(step_num)

        status = str((evidence or {}).get("status", "not_checked"))
        status_label = QtWidgets.QLabel({
            "passed": "CHECKED",
            "failed": "REVIEW",
            "not_checked": "NOT CHECKED",
        }.get(status, "NOT CHECKED"))
        status_color = {
            "passed": "#26725C", "failed": "#AC4055", "not_checked": "#65758A",
        }.get(status, "#65758A")
        status_label.setObjectName("DerivationCheckStatus")
        status_label.setStyleSheet(
            f"color: {status_color}; font-size: 9px; font-weight: 700; "
            "letter-spacing: 0.5px; padding: 2px 6px; border-radius: 4px; "
            f"background-color: {status_color}18;"
        )
        status_label.setToolTip(str((evidence or {}).get("detail", "")))
        header_layout.addWidget(status_label)

        preview_label = QtWidgets.QLabel("Try a hint before opening the worked step")
        preview_label.setStyleSheet("color: #65758A; font-size: 11px;")
        header_layout.addWidget(preview_label, 1)

        copy_btn = QtWidgets.QPushButton()
        copy_btn.setIcon(icons.icon("copy", 12, "#65758A"))
        copy_btn.setFixedWidth(28)
        copy_btn.setToolTip("Copy step")
        copy_btn.setStyleSheet(
            "background: transparent; border: none; font-size: 12px; padding: 2px;"
        )
        copy_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(lambda: _copy_to_clipboard(text))
        header_layout.addWidget(copy_btn)

        self._details = QtWidgets.QWidget()
        details_layout = QtWidgets.QVBoxLayout(self._details)
        details_layout.setContentsMargins(28, 4, 6, 6)
        details_layout.setSpacing(6)
        hint = QtWidgets.QLabel(
            "Hint: write the starting law, identify the quantity you need, and name "
            "the assumption that connects them."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #335F92; font-size: 11px; padding: 4px 0;")
        details_layout.addWidget(hint)
        if evidence:
            evidence_detail = str(evidence.get("detail", "")).strip()
            claim = str(evidence.get("claim", "")).strip()
            before = str(evidence.get("from_expression", "")).strip()
            after = str(evidence.get("to_expression", "")).strip()
            source = str(evidence.get("source_ref", "")).strip()
            text_lines = []
            if claim:
                text_lines.append(claim)
            if before or after:
                text_lines.append(f"{before}  →  {after}".strip())
            if evidence_detail:
                text_lines.append(evidence_detail)
            substitution_status = str(evidence.get("substitution_status", "not_checked"))
            substitution_detail = str(evidence.get("substitution_detail", "")).strip()
            if substitution_status != "not_checked" and substitution_detail:
                text_lines.append(
                    f"Numeric substitution ({substitution_status}): {substitution_detail}"
                )
            text_lines.append(f"Source: {source}" if source else "Source: not supplied")
            evidence_label = QtWidgets.QLabel("\r\n".join(text_lines))
            evidence_label.setObjectName("DerivationEvidence")
            evidence_label.setWordWrap(True)
            evidence_label.setTextInteractionFlags(
                QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
            )
            evidence_label.setStyleSheet(
                "color: #53647A; font-size: 10px; padding: 6px 8px; "
                "background-color: #FFFFFF; border-radius: 5px;"
            )
            details_layout.addWidget(evidence_label)
        reveal_btn = QtWidgets.QPushButton("Reveal worked step")
        reveal_btn.setObjectName("GhostButton")
        reveal_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        details_layout.addWidget(reveal_btn, 0, QtCore.Qt.AlignmentFlag.AlignLeft)

        self._body = QtWidgets.QLabel(text)
        self._body.setWordWrap(True)
        self._body.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self._body.setStyleSheet(
            "color: #24364B; font-size: 12px; padding: 8px 8px 8px 28px; "
            "background-color: #FFFFFF; border-radius: 6px; margin-top: 4px;"
        )
        self._body.hide()
        details_layout.addWidget(self._body)
        self._details.hide()
        reveal_btn.clicked.connect(lambda: self._reveal_step(reveal_btn))

        self._expanded = False
        self._full_text = text

        header.mousePressEvent = lambda e: self._toggle()  # type: ignore[assignment]
        layout.addWidget(header)
        layout.addWidget(self._details)

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self._details.setVisible(self._expanded)
        self._arrow.setText("\u25bc" if self._expanded else "\u25b6")
        self._arrow.setStyleSheet(
            f"color: {'#486A91' if self._expanded else '#65758A'}; font-size: 10px;"
        )

    def _reveal_step(self, button: QtWidgets.QPushButton) -> None:
        self._body.show()
        button.setText("Worked step revealed")
        button.setEnabled(False)

class AnalysisPanel(QtWidgets.QWidget):
    """Derivation block (design: components/content/DerivationBlock.jsx).

    Card with a cyan mono summary banner, violet keyword chips, collapsible
    numbered steps, and a Copy / Export footer.
    """

    export_latex_requested = QtCore.pyqtSignal()
    export_pdf_requested = QtCore.pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        card = QtWidgets.QFrame()
        card.setObjectName("AnalysisCard")
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 16)
        card_layout.setSpacing(14)

        # Summary banner (design: summaryEquation — cyan italic mono)
        self.summary = QtWidgets.QLabel("")
        self.summary.setObjectName("EquationBanner")
        self.summary.setWordWrap(True)
        self.summary.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.summary.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        card_layout.addWidget(self.summary)

        self._verification = QtWidgets.QLabel(
            "Numeric model checks are separate from the written derivation."
        )
        self._verification.setWordWrap(True)
        self._verification.setStyleSheet(
            "color: #65758A; font-size: 11px; padding: 2px 6px;"
        )
        card_layout.addWidget(self._verification)

        # Keyword chips (violet pills)
        self._chips_row = QtWidgets.QWidget()
        self._chips_layout = QtWidgets.QHBoxLayout(self._chips_row)
        self._chips_layout.setContentsMargins(0, 0, 0, 0)
        self._chips_layout.setSpacing(6)
        self._chips_layout.addStretch()
        self._chips_row.hide()
        card_layout.addWidget(self._chips_row)

        # Steps header row
        steps_header = QtWidgets.QWidget()
        sth_layout = QtWidgets.QHBoxLayout(steps_header)
        sth_layout.setContentsMargins(0, 0, 0, 0)
        sth_label = QtWidgets.QLabel("DERIVATION STEPS")
        sth_label.setObjectName("SectionTitle")
        sth_layout.addWidget(sth_label)
        sth_layout.addStretch()
        self._expand_all_btn = QtWidgets.QPushButton("Show hints")
        self._expand_all_btn.setObjectName("GhostButton")
        self._expand_all_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._expand_all_btn.clicked.connect(self._toggle_all_steps)
        sth_layout.addWidget(self._expand_all_btn)
        card_layout.addWidget(steps_header)

        # Collapsible steps in a scroll area
        self._steps_scroll = QtWidgets.QScrollArea()
        self._steps_scroll.setWidgetResizable(True)
        self._steps_scroll.setMinimumHeight(120)
        self._steps_scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )
        self._steps_container = QtWidgets.QWidget()
        self._steps_vbox = QtWidgets.QVBoxLayout(self._steps_container)
        self._steps_vbox.setContentsMargins(0, 0, 0, 0)
        self._steps_vbox.setSpacing(4)
        self._steps_vbox.addStretch()
        self._steps_scroll.setWidget(self._steps_container)
        card_layout.addWidget(self._steps_scroll, 1)

        # Empty state
        self._empty_label = QtWidgets.QLabel(
            "Solve a problem to see the analytical derivation and "
            "step-by-step breakdown."
        )
        self._empty_label.setObjectName("EmptyHint")
        self._empty_label.setWordWrap(True)
        self._empty_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self._empty_label)

        # Footer: Copy / Export (design: DerivationBlock footer)
        footer = QtWidgets.QWidget()
        footer_layout = QtWidgets.QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 6, 0, 0)
        footer_layout.setSpacing(8)

        copy_btn = QtWidgets.QPushButton("Copy")
        copy_btn.setObjectName("SecondaryButton")
        copy_btn.setIcon(icons.icon("copy", 13, "#65758A"))
        copy_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(self._copy_all)
        footer_layout.addWidget(copy_btn)

        export_btn = QtWidgets.QPushButton("Export")
        export_btn.setObjectName("SecondaryButton")
        export_btn.setIcon(icons.icon("download", 13, "#65758A"))
        export_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        export_btn.clicked.connect(lambda: self._show_export_menu(export_btn))
        footer_layout.addWidget(export_btn)
        footer_layout.addStretch()
        card_layout.addWidget(footer)

        layout.addWidget(card, 1)

        self._step_widgets: list[_CollapsibleStepWidget] = []
        self._all_expanded = False
        self._steps_text: list[str] = []

    def _show_export_menu(self, anchor: QtWidgets.QWidget) -> None:
        menu = QtWidgets.QMenu(self)
        menu.addAction("Export as LaTeX…", self.export_latex_requested.emit)
        menu.addAction("Export as PDF…", self.export_pdf_requested.emit)
        menu.exec(anchor.mapToGlobal(QtCore.QPoint(0, anchor.height() + 4)))

    def _copy_all(self) -> None:
        parts = [getattr(self, "_summary_text", "") or self.summary.text()]
        parts += [f"{i}. {s}" for i, s in enumerate(self._steps_text, start=1)]
        _copy_to_clipboard("\r\n".join(p for p in parts if p))

    def _toggle_all_steps(self) -> None:
        self._all_expanded = not self._all_expanded
        for w in self._step_widgets:
            if w._expanded != self._all_expanded:
                w._toggle()
        self._expand_all_btn.setText(
            "Hide hints" if self._all_expanded else "Show hints"
        )

    def set_solver_result(
        self, solver: SolverResult, scene_spec: dict | None = None,
    ) -> None:
        cache_note = "  [cache]" if solver.cached else ""
        self._summary_text = f"{solver.summary}{cache_note}"
        # Hero equation banner (design v2 §5.1): the solver's first governing
        # equation, typeset large; else typeset the summary when it reads as
        # math; prose keeps the styled-text banner. Fail-soft at every step.
        from aetherlab.services.mathtext import looks_like_math, render_math

        pixmap = None
        equations = getattr(solver, "key_equations", None) or []
        if equations:
            pixmap = render_math(equations[0], px_size=30, color="#486A91")
        if pixmap is None and looks_like_math(solver.summary):
            pixmap = render_math(solver.summary, px_size=26, color="#486A91")
        if pixmap is not None:
            self.summary.setPixmap(pixmap)
            self.summary.setToolTip(self._summary_text)
        else:
            self.summary.setText(self._summary_text)
            self.summary.setToolTip("")
        self._empty_label.hide()

        derivation = {"items": []}
        spec_records = None
        try:
            from aetherlab.services.scene_specification import validate_scene_spec

            if (
                isinstance(scene_spec, dict)
                and validate_scene_spec(scene_spec)["status"] == "passed"
            ):
                physics = scene_spec.get("physics", {})
                spec_records = physics.get("derivation_records", [])
                verification = scene_spec.get("verification", {})
                derivation = verification.get("derivations", {"items": []})
                units = verification.get("units", {"status": "not_checked", "message": "not checked"})
                numeric = verification.get("numeric_model", {})
                numeric_checks = numeric.get("checks", [])
                has_numeric_model = isinstance(physics.get("numeric_model"), dict)
            else:
                from aetherlab.services.derivation_verify import (
                    verify_derivation_records,
                    verify_ode_units,
                )
                from aetherlab.services.verify import verify_solution

                report = verify_solution(solver)
                derivation = verify_derivation_records(solver)
                units = verify_ode_units(solver)
                numeric_checks = [
                    {"status": "passed" if check.passed else "failed"}
                    for check in report.checks
                ]
                has_numeric_model = bool(getattr(solver, "numeric_spec", None))
            evidence = [
                f"Algebra: {derivation['message']}",
                f"Units: {units['message']}",
            ]
            if has_numeric_model and numeric_checks:
                passed = sum(
                    1 for check in numeric_checks
                    if isinstance(check, dict) and check.get("status") == "passed"
                )
                failed = len(numeric_checks) - passed
                detail = f"Numeric model: {passed}/{len(numeric_checks)} checks passed."
                if failed:
                    detail += f" {failed} need review."
                detail += " " + " ".join(evidence)
                self._verification.setText(detail)
                self._verification.setStyleSheet(
                    f"color: {'#26725C' if not failed and derivation['status'] != 'failed' and units['status'] != 'failed' else '#8A5A24'}; font-size: 11px; padding: 2px 6px;"
                )
            else:
                self._verification.setText(
                    "No deterministic numeric check is available. " + " ".join(evidence)
                )
                self._verification.setStyleSheet(
                    "color: #8A5A24; font-size: 11px; padding: 2px 6px;"
                )
        except Exception:  # noqa: BLE001 - verification status must never block results
            self._verification.setText(
                "Numeric verification is unavailable; the written derivation is unverified."
            )
            self._verification.setStyleSheet(
                "color: #8A5A24; font-size: 11px; padding: 2px 6px;"
            )

        # Keyword chips
        while self._chips_layout.count() > 1:
            item = self._chips_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        keywords = list(solver.keywords)[:6]
        for kw in keywords:
            chip = QtWidgets.QLabel(kw)
            chip.setObjectName("KeywordChip")
            self._chips_layout.insertWidget(self._chips_layout.count() - 1, chip)
        self._chips_row.setVisible(bool(keywords))

        # Steps
        for w in self._step_widgets:
            w.hide()
            w.deleteLater()
        self._step_widgets.clear()
        self._steps_text = list(solver.derivation_steps)
        evidence_by_step = {}
        records_for_steps = (
            spec_records
            if isinstance(spec_records, list)
            else getattr(solver, "derivation_records", []) or []
        )
        for record in records_for_steps:
            if not isinstance(record, dict):
                continue
            try:
                step_index = int(record.get("step_index"))
            except (TypeError, ValueError, OverflowError):
                continue
            evidence_by_step[step_index] = record
        try:
            checks = derivation.get("items", [])
            for check in checks:
                if not isinstance(check, dict):
                    continue
                step_index = int(check.get("step_index", 0) or 0)
                if step_index in evidence_by_step:
                    evidence_by_step[step_index] = {
                        **evidence_by_step[step_index], **check,
                    }
        except (TypeError, ValueError, OverflowError):
            pass

        for index, step in enumerate(solver.derivation_steps, start=1):
            widget = _CollapsibleStepWidget(
                index, step, evidence_by_step.get(index),
            )
            self._steps_vbox.insertWidget(self._steps_vbox.count() - 1, widget)
            self._step_widgets.append(widget)

    def update_variable(self, name: str, value: float) -> None:
        pass  # Parameters live in the parameter panel
