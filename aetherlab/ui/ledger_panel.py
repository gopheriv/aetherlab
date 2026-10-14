"""Render-farm dashboard panel — a read-only view of the render job ledger.

Shows what the Quality Flywheel's cloud backend and tournaments did: each job's
status timeline, per-candidate critic scores with the winner highlighted, any
sanitized failure log tail, and the local-fallback reason. Populated by
``services/render_ledger.RenderJobLedger`` (already secret-scrubbed at write
time), so this widget only ever displays safe data.

Kept as a self-contained widget in its own module (not the large widgets.py) so
it composes cleanly and can be constructed offscreen in tests.
"""

from __future__ import annotations

import html
from pathlib import Path

from aetherlab.ui.qt_compat import QtCore, QtWidgets


class RenderLedgerPanel(QtWidgets.QWidget):
    """A job list plus a details pane, both fed by the render ledger on disk."""

    def __init__(self, ledger_path: Path, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._ledger_path = Path(ledger_path)
        self.setObjectName("RenderLedgerPanel")

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Render farm")
        title.setStyleSheet("color: #18283D; font-size: 16px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch(1)
        self._refresh_btn = QtWidgets.QPushButton("Refresh")
        self._refresh_btn.setObjectName("SecondaryButton")
        self._refresh_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.clicked.connect(self.refresh)
        header.addWidget(self._refresh_btn)
        root.addLayout(header)

        split = QtWidgets.QHBoxLayout()
        split.setSpacing(10)
        self._jobs = QtWidgets.QListWidget()
        self._jobs.setMinimumWidth(220)
        self._jobs.setMaximumWidth(340)
        self._jobs.currentRowChanged.connect(self._show_selected)
        split.addWidget(self._jobs)

        self._details = QtWidgets.QTextBrowser()
        self._details.setOpenExternalLinks(True)
        split.addWidget(self._details, 1)
        root.addLayout(split, 1)

        self._empty = QtWidgets.QLabel(
            "No render jobs yet. Cloud renders and scene tournaments appear here."
        )
        self._empty.setStyleSheet("color: #65758A; font-size: 12px;")
        self._empty.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._empty)

        self._records: list[dict] = []
        self.refresh()

    # -- data -----------------------------------------------------------------
    def _load(self) -> list[dict]:
        try:
            from aetherlab.services.render_ledger import RenderJobLedger

            return RenderJobLedger(self._ledger_path).list(50)
        except Exception:  # noqa: BLE001 — a dashboard must never crash the app
            return []

    def refresh(self) -> None:
        self._records = self._load()
        self._jobs.clear()
        for rec in self._records:
            status = str(rec.get("status", ""))
            backend = str(rec.get("backend", ""))
            winner = rec.get("winner_index")
            label = f"{_status_glyph(status)} {rec.get('scene_class', 'job')} · {backend}"
            if winner is not None:
                try:
                    label += f" · winner #{int(winner) + 1}"
                except (TypeError, ValueError):
                    pass
            self._jobs.addItem(QtWidgets.QListWidgetItem(label))
        has_jobs = bool(self._records)
        self._empty.setVisible(not has_jobs)
        self._jobs.setVisible(has_jobs)
        self._details.setVisible(has_jobs)
        if has_jobs:
            self._jobs.setCurrentRow(0)
        else:
            self._details.setPlainText("")

    def _show_selected(self, row: int) -> None:
        if not (0 <= row < len(self._records)):
            self._details.setPlainText("")
            return
        self._details.setHtml(self._render_details(self._records[row]))

    # -- rendering ------------------------------------------------------------
    def _render_details(self, rec: dict) -> str:
        def esc(value: object) -> str:
            return html.escape(str(value))

        from aetherlab.services.render_ledger import safe_github_url

        run_url = safe_github_url(rec.get("run_url", ""))
        artifact_url = safe_github_url(rec.get("artifact_url", ""))

        parts: list[str] = [
            f"<h3 style='color:#18283D;margin:0 0 6px'>{esc(rec.get('scene_class', 'job'))}</h3>",
            f"<div style='color:#65758A'>Job: {esc(rec.get('job_id', ''))} · FPS: {esc(rec.get('fps', 0))}</div>",
            f"<div style='color:#65758A'>{esc(rec.get('backend', ''))}"
            f" · {esc(rec.get('provider', ''))} · quality {esc(rec.get('quality', ''))}"
            f" · status <b>{esc(str(rec.get('status', '')).replace('_', ' '))}</b></div>",
        ]
        if run_url:
            parts.append(f"<div><a href='{esc(run_url)}'>Open GitHub Actions run</a></div>")
        if artifact_url:
            parts.append(f"<div><a href='{esc(artifact_url)}'>Open render artifact</a></div>")

        candidates = rec.get("candidates") or []
        winner = rec.get("winner_index")
        if candidates:
            parts.append("<h4 style='color:#24364B;margin:12px 0 4px'>Candidates</h4><ul>")
            for cand in candidates:
                if not isinstance(cand, dict):
                    continue
                try:
                    idx = int(cand.get("index", 0))
                except (TypeError, ValueError):
                    idx = 0
                try:
                    is_winner = winner is not None and idx == int(winner)
                except (TypeError, ValueError):
                    is_winner = False
                mark = " ← winner" if is_winner else ""
                colour = "#26725C" if mark else "#24364B"
                parts.append(
                    f"<li style='color:{colour}'>#{idx + 1}: score "
                    f"{esc(cand.get('score', 0))} ({esc(cand.get('verdict', ''))}){esc(mark)}</li>"
                )
            parts.append("</ul>")

        if rec.get("fallback_reason"):
            parts.append(
                f"<div style='color:#8A5A24;margin-top:8px'>Fell back to local: "
                f"{esc(rec['fallback_reason'])}</div>"
            )
        if rec.get("final_path"):
            parts.append(f"<div style='color:#65758A'>Output: {esc(rec['final_path'])}</div>")

        timeline = rec.get("timeline") or []
        if timeline:
            parts.append("<h4 style='color:#24364B;margin:12px 0 4px'>Timeline</h4><ul>")
            for event in timeline:
                if not isinstance(event, dict):
                    continue
                detail = f" — {esc(event.get('detail'))}" if event.get("detail") else ""
                parts.append(
                    f"<li style='color:#65758A'>{esc(event.get('at', ''))}: "
                    f"{esc(str(event.get('status', '')).replace('_', ' '))}{detail}</li>"
                )
            parts.append("</ul>")

        if rec.get("log_tail"):
            parts.append("<h4 style='color:#AC4055;margin:12px 0 4px'>Failure log (sanitized)</h4>")
            parts.append(
                f"<pre style='color:#AC4055;white-space:pre-wrap;font-size:11px'>"
                f"{esc(rec['log_tail'])}</pre>"
            )
        return "".join(parts)


def _status_glyph(status: str) -> str:
    return {
        "rendered": "✓",
        "completed": "✓",
        "artifact_downloaded": "✓",
        "failed": "✗",
        "action_required": "⚠",
        "cancelled": "⊘",
        "rate_limited": "⏳",
        "fallback_local": "↩",
        "in_progress": "…",
        "queued": "•",
    }.get(status, "•")
