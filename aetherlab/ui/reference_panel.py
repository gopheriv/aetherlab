"""Reference cards and source evidence shown beside a physics result."""

from __future__ import annotations

from aetherlab.core.models import RagResult
from aetherlab.ui import icons
from aetherlab.ui.qt_compat import QtCore, QtGui, QtWidgets, require_qt
from aetherlab.ui.shared_widgets import _copy_to_clipboard

require_qt()

class _RagHitCard(QtWidgets.QFrame):
    """Reference card (design: components/content/ReferenceCard.jsx).

    Book icon + source + page, threshold-colored score pill, excerpt,
    and an Open link that opens the source file.
    """

    def __init__(self, source: str, page: int | None, score: float, excerpt: str,
                 source_path: str = "", is_web: bool = False,
                 parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CardFrame")
        # Low-relevance cards read dimmer (design v2: reference card "dimmed" state).
        if score < 0.5:
            eff = QtWidgets.QGraphicsOpacityEffect(self)
            eff.setOpacity(0.6)
            self.setGraphicsEffect(eff)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Header row: icon + source + page + origin badge + score pill + copy
        header = QtWidgets.QWidget()
        h_layout = QtWidgets.QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(8)

        # Web references get a globe + violet accent; library keeps the book/cyan.
        icon_name = "globe" if is_web else "book-open"
        icon_color = "#536F90" if is_web else "#486A91"
        h_layout.addWidget(icons.icon_label(icon_name, 14, icon_color))

        src_label = QtWidgets.QLabel(source)
        src_label.setStyleSheet("color: #18283D; font-size: 13px; font-weight: 600;")
        h_layout.addWidget(src_label)

        if is_web:
            web_badge = QtWidgets.QLabel("Wikipedia")
            web_badge.setStyleSheet(
                "color: #536F90; border: 1px solid #536F90; border-radius: 8px; "
                "padding: 0px 7px; font-size: 9.5px; font-weight: 600;"
            )
            h_layout.addWidget(web_badge)
        elif page:
            page_label = QtWidgets.QLabel(f"p.{page}")
            page_label.setStyleSheet("color: #65758A; font-size: 11px;")
            h_layout.addWidget(page_label)
        h_layout.addStretch()

        # Score pill — emerald >= 0.8, amber >= 0.5, else tertiary (design thresholds)
        score_color = "#26725C" if score >= 0.8 else "#8A5A24" if score >= 0.5 else "#65758A"
        score_label = QtWidgets.QLabel(f"{score:.2f}")
        score_label.setStyleSheet(
            f"color: {score_color}; border: 1px solid {score_color}; "
            "border-radius: 9px; padding: 1px 8px; font-size: 11px; "
            "font-family: 'Cascadia Code', monospace;"
        )
        h_layout.addWidget(score_label)

        copy_btn = QtWidgets.QPushButton()
        copy_btn.setIcon(icons.icon("copy", 13, "#65758A"))
        copy_btn.setFixedSize(24, 24)
        copy_btn.setToolTip("Copy excerpt")
        copy_btn.setStyleSheet("background: transparent; border: none;")
        copy_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(lambda: _copy_to_clipboard(excerpt))
        h_layout.addWidget(copy_btn)

        layout.addWidget(header)

        # Excerpt
        excerpt_label = QtWidgets.QLabel(excerpt)
        excerpt_label.setWordWrap(True)
        excerpt_label.setStyleSheet("color: #65758A; font-size: 12px;")
        layout.addWidget(excerpt_label)

        # Open link — a local file opens in the OS viewer, a URL in the browser.
        if source_path:
            open_btn = QtWidgets.QPushButton("Open article" if is_web else "Open")
            open_btn.setObjectName("LinkButton")
            open_btn.setIcon(icons.icon("arrow-up-right", 12, icon_color))
            open_btn.setLayoutDirection(QtCore.Qt.LayoutDirection.RightToLeft)
            open_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            is_url = source_path.startswith(("http://", "https://"))
            url = QtCore.QUrl(source_path) if is_url else QtCore.QUrl.fromLocalFile(source_path)
            open_btn.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(url))
            row = QtWidgets.QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(open_btn)
            row.addStretch()
            layout.addLayout(row)

class ReferencePanel(QtWidgets.QWidget):
    """References column (design: DerivationView right column)."""

    def __init__(self) -> None:
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QtWidgets.QLabel("REFERENCES")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        self._backend_label = QtWidgets.QLabel("")
        self._backend_label.setStyleSheet(
            "color: #65758A; font-size: 11px; font-family: 'Cascadia Code', monospace;"
        )
        layout.addWidget(self._backend_label)

        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._card_container = QtWidgets.QWidget()
        self._card_layout = QtWidgets.QVBoxLayout(self._card_container)
        self._card_layout.setContentsMargins(0, 0, 0, 0)
        self._card_layout.setSpacing(10)
        self._card_layout.addStretch()
        self._scroll.setWidget(self._card_container)
        layout.addWidget(self._scroll, 1)

        # Empty state (design copy: name the missing thing, one action)
        self._empty_label = QtWidgets.QLabel(
            "Textbook references will appear here after a run.\r\n"
            "Add PDFs or text files to the library to enable retrieval."
        )
        self._empty_label.setObjectName("EmptyHint")
        self._empty_label.setWordWrap(True)
        self._empty_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty_label)

    def set_rag_result(self, rag: RagResult) -> None:
        # Clear old cards
        while self._card_layout.count() > 1:
            item = self._card_layout.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                w.deleteLater()

        if not rag.hits:
            self._empty_label.setText(
                f"No local references found via {rag.backend}.\r\n"
                "Add PDFs or text files to the library directory."
            )
            self._empty_label.show()
            self._backend_label.setText("")
            return

        self._empty_label.hide()
        n_web = sum(1 for h in rag.hits if getattr(h, "is_web", False))
        n_lib = len(rag.hits) - n_web
        provenance = f"{n_lib} library"
        if n_web:
            provenance += f" · {n_web} web"
        self._backend_label.setText(f"{rag.backend} · {provenance}")

        for hit in rag.hits:
            card = _RagHitCard(
                source=hit.source_name,
                page=hit.page_number,
                score=hit.score,
                excerpt=hit.excerpt,
                source_path=hit.source_path,
                is_web=getattr(hit, "is_web", False),
            )
            self._card_layout.insertWidget(self._card_layout.count() - 1, card)
