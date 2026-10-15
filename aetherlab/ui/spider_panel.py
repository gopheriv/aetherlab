"""Animated screen-crawler panel for AetherLab."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Callable

from aetherlab.core.settings import AppSettings
from aetherlab.services.spider import (
    SpiderResult,
    inspect_and_repair,
)
from aetherlab.services.spider import (
    crawl_project as crawl_project_sources,
)
from aetherlab.ui.background_task import BackgroundTask
from aetherlab.ui.qt_compat import QtCore, QtGui, QtWidgets


class SpiderMark(QtWidgets.QWidget):
    """A small lively spider tracing a cyan web, drawn without external art."""

    _PALETTE = ("#32E6EE", "#E879F9", "#A3E635", "#FBBF24", "#FB7185")

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._phase = 0.0
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self.setMinimumSize(116, 90)

    def _tick(self) -> None:
        self._phase = (self._phase + 0.075) % (math.tau)
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w * 0.56, h * 0.54
        radius = min(w, h) * 0.38
        web_pen = QtGui.QPen(QtGui.QColor("#1e4450"), 1.0)
        painter.setPen(web_pen)
        for ring in (0.34, 0.60, 0.86):
            painter.drawEllipse(QtCore.QPointF(cx, cy), radius * ring, radius * ring)
        for spoke in range(10):
            angle = math.tau * spoke / 10
            end = QtCore.QPointF(cx + radius * math.cos(angle), cy + radius * math.sin(angle))
            painter.drawLine(QtCore.QPointF(cx, cy), end)

        orbit = self._phase * 0.72
        sx = cx + radius * 0.57 * math.cos(orbit)
        sy = cy + radius * 0.57 * math.sin(orbit)
        accent = QtGui.QColor(self._PALETTE[int(self._phase * 2) % len(self._PALETTE)])
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor(accent.red(), accent.green(), accent.blue(), 28))
        painter.drawEllipse(QtCore.QPointF(sx, sy), 17, 17)
        painter.setPen(QtGui.QPen(accent, 2.0, QtCore.Qt.PenStyle.SolidLine, QtCore.Qt.PenCapStyle.RoundCap))
        body = QtCore.QPointF(sx, sy)
        for side in (-1, 1):
            for leg in range(4):
                dy = (leg - 1.5) * 3.2
                elbow = QtCore.QPointF(sx + side * (8 + leg % 2), sy + dy - 5 * side)
                foot = QtCore.QPointF(sx + side * 16, sy + dy + 6 * side)
                painter.drawLine(body, elbow)
                painter.drawLine(elbow, foot)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(accent)
        painter.drawEllipse(body, 6.2, 6.2)
        painter.drawEllipse(QtCore.QPointF(sx + 4 * math.cos(orbit), sy + 4 * math.sin(orbit)), 3.4, 3.4)
        painter.setBrush(QtGui.QColor("#081018"))
        painter.drawEllipse(QtCore.QPointF(sx + 4.2, sy - 1.2), 1.1, 1.1)
        painter.end()


class SpiderProjectTrail(QtWidgets.QWidget):
    """Animated map showing Spider moving through the active project path."""

    _COLORS = ("#32E6EE", "#E879F9", "#A3E635", "#FBBF24")

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._phase = 0.0
        self._labels = ["PROJECT", "aetherlab", "ui", "waiting.py"]
        self._current_file = "Ready to crawl project"
        self._progress = ""
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self.setMinimumHeight(116)
        self.setMaximumHeight(142)
        self.setAccessibleName("Animated project crawl map")

    def set_progress(self, current: int, total: int, path: str) -> None:
        pieces = [piece for piece in Path(path.replace("\\", "/")).parts if piece not in (".", "")]
        self._labels = ["PROJECT", *(pieces[-3:] if pieces else ["source"])]
        self._labels = (self._labels + [""] * 4)[:4]
        self._current_file = path.replace("\\", "/")
        self._progress = f"{current:,} / {total:,} FILES"
        self.update()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.035) % (math.tau * 3)
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        bounds = QtCore.QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.setPen(QtGui.QPen(QtGui.QColor("#1D3A46"), 1))
        painter.setBrush(QtGui.QColor("#081018"))
        painter.drawRoundedRect(bounds, 11, 11)

        label_font = painter.font()
        label_font.setPointSize(8)
        label_font.setBold(True)
        painter.setFont(label_font)
        painter.setPen(QtGui.QColor("#35E1EA"))
        painter.drawText(QtCore.QRectF(12, 8, self.width() - 24, 15),
                         QtCore.Qt.AlignmentFlag.AlignLeft, "LIVE PROJECT WEB")
        painter.setPen(QtGui.QColor("#91A6B5"))
        painter.drawText(QtCore.QRectF(12, 8, self.width() - 24, 15),
                         QtCore.Qt.AlignmentFlag.AlignRight, self._progress)

        points = [
            QtCore.QPointF(self.width() * x, self.height() * y)
            for x, y in ((0.12, 0.60), (0.37, 0.42), (0.63, 0.60), (0.88, 0.42))
        ]
        web_pen = QtGui.QPen(QtGui.QColor("#28505A"), 1.5)
        painter.setPen(web_pen)
        for first, second in zip(points, points[1:]):
            painter.drawLine(first, second)
        for index, point in enumerate(points):
            color = QtGui.QColor(self._COLORS[index])
            painter.setPen(QtGui.QPen(color, 1.5))
            painter.setBrush(QtGui.QColor(color.red(), color.green(), color.blue(), 36))
            painter.drawEllipse(point, 7, 7)
            painter.setPen(QtGui.QColor("#D6E9EF"))
            painter.drawText(
                QtCore.QRectF(point.x() - 47, point.y() + 10, 94, 15),
                QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop,
                self._labels[index][:16],
            )

        distance = self._phase % 3
        segment = min(2, int(distance))
        fraction = distance - segment
        start, end = points[segment], points[segment + 1]
        sx = start.x() + (end.x() - start.x()) * fraction
        sy = start.y() + (end.y() - start.y()) * fraction
        glow = 8 + 3 * (0.5 + 0.5 * math.sin(self._phase * 2))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor(50, 230, 238, 35))
        painter.drawEllipse(QtCore.QPointF(sx, sy), glow, glow)
        painter.setPen(QtGui.QPen(QtGui.QColor("#32E6EE"), 2,
                                  QtCore.Qt.PenStyle.SolidLine,
                                  QtCore.Qt.PenCapStyle.RoundCap))
        body = QtCore.QPointF(sx, sy)
        for side in (-1, 1):
            for leg in range(4):
                dy = (leg - 1.5) * 2.8
                elbow = QtCore.QPointF(sx + side * 6, sy + dy - side * 3)
                foot = QtCore.QPointF(sx + side * 11, sy + dy + side * 4)
                painter.drawLine(body, elbow)
                painter.drawLine(elbow, foot)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor("#32E6EE"))
        painter.drawEllipse(body, 4.5, 4.5)

        painter.setPen(QtGui.QColor("#77909D"))
        footer = self._current_file
        max_chars = max(12, int((self.width() - 24) / 7))
        if len(footer) > max_chars:
            footer = "…" + footer[-(max_chars - 1):]
        painter.drawText(QtCore.QRectF(12, self.height() - 19, self.width() - 24, 14),
                         QtCore.Qt.AlignmentFlag.AlignLeft, footer)
        painter.end()


class SpiderPanel(QtWidgets.QWidget):
    """Screen-aware helper. A scan sends the visible AetherLab page to its model."""

    _COPY = {
        "en": {
            "eyebrow": "VISUAL PROJECT CRAWLER",
            "title": "Spider sees the whole web.",
            "description": "I trace what is on your workbench back to the code that made it.",
            "target": "CURRENT WORKBENCH VIEW",
            "scan": "Scan screen + auto-fix",
            "crawl": "Crawl project",
            "watch": "Watch this screen",
            "privacy": "A screenshot of the current AetherLab page is sent to your configured AI model when Spider scans.",
            "ready": "Ready to crawl",
            "idle": "Show the page with the error, then scan. I’ll look for the source and patch it.",
            "scanning": "Climbing the web…",
            "done": "No visible bug in this frame. The web is quiet.",
            "fixed": "Source updated and Python syntax checked. Restart AetherLab to load the changes; Watch is paused.",
            "error": "Spider lost the thread",
            "watching": "Watching the workbench",
            "paused": "Watch paused while AetherLab is inactive",
        },
        "ru": {
            "eyebrow": "ВИЗУАЛЬНЫЙ СКАНЕР ПРОЕКТА",
            "title": "Паук видит всю сеть.",
            "description": "Я связываю экран с исходным кодом, который его создал.",
            "target": "ТЕКУЩИЙ ЭКРАН",
            "scan": "Сканировать и исправить",
            "crawl": "Обойти проект",
            "watch": "Следить за экраном",
            "privacy": "При сканировании снимок страницы AetherLab отправляется выбранной AI-модели.",
            "ready": "Готов к поиску",
            "idle": "Покажите экран с ошибкой и запустите сканирование.",
            "scanning": "Паук плетёт сеть…",
            "done": "Ошибок не видно. В сети спокойно.",
            "fixed": "Исходники обновлены, синтаксис проверен. Нужен перезапуск AetherLab; наблюдение остановлено.",
            "error": "Паук потерял нить",
            "watching": "Наблюдаю за экраном",
            "paused": "Наблюдение остановлено: AetherLab неактивен",
        },
        "kk": {
            "eyebrow": "КӨРНЕКІ ЖОБА СКАНЕРІ",
            "title": "Өрмекші бүкіл желіні көреді.",
            "description": "Экрандағы ақауды оны жасаған бастапқы кодпен байланыстырамын.",
            "target": "АҒЫМДАҒЫ ЖҰМЫС ЭКРАНЫ",
            "scan": "Экранды тексеріп, түзету",
            "crawl": "Жобаны шолу",
            "watch": "Экранды бақылау",
            "privacy": "Тексеру кезінде AetherLab бетінің суреті таңдалған AI үлгісіне жіберіледі.",
            "ready": "Іздеуге дайынмын",
            "idle": "Қате көрініп тұрған бетті ашып, тексеруді бастаңыз.",
            "scanning": "Өрмекші желіге өрмелеп барады…",
            "done": "Бұл кадрдан қате көрінбеді. Желі тыныш.",
            "fixed": "Бастапқы код жаңартылып, синтаксисі тексерілді. AetherLab қолданбасын қайта іске қосыңыз; бақылау тоқтады.",
            "error": "Өрмекші жіпті жоғалтты",
            "watching": "Жұмыс экранын бақылаудамын",
            "paused": "AetherLab белсенді емес, бақылау тоқтады",
        },
    }

    def __init__(
        self,
        settings: AppSettings,
        project_root: Path,
        backup_root: Path,
        capture_view: Callable[[], QtGui.QPixmap],
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._project_root = Path(project_root)
        self._backup_root = Path(backup_root)
        self._capture_view = capture_view
        self._language = "en"
        self._task: BackgroundTask | None = None
        self._build()

    def _build(self) -> None:
        self.setObjectName("SpiderPanel")
        self.setMinimumWidth(360)
        self.setStyleSheet("""
            QWidget#SpiderPanel { background:#080D14; color:#E7F3FA; }
            QLabel { color:#DDEAF2; }
            QLabel#SpiderEyebrow { color:#35E1EA; font-size:10px; font-weight:800; letter-spacing:1.2px; }
            QLabel#SpiderTitle { color:#F3FBFF; font-size:21px; font-weight:800; }
            QLabel#SpiderMuted { color:#91A6B5; font-size:12px; }
            QFrame#SpiderCard { background:#101923; border:1px solid #1C3542; border-radius:14px; }
            QFrame#SpiderPreview { background:#060A10; border:1px solid #1D3A46; border-radius:10px; }
            QPushButton#SpiderScan { background:#25C9D7; color:#041016; border:0; border-radius:9px; padding:11px 14px; font-weight:800; }
            QPushButton#SpiderScan:hover { background:#59E5ED; }
            QPushButton#SpiderScan:disabled { background:#31545B; color:#9EB4B8; }
            QPushButton#SpiderWatch { background:#121E28; color:#CDE6EC; border:1px solid #31505A; border-radius:9px; padding:10px 13px; font-weight:700; }
            QPushButton#SpiderWatch:checked { background:#163F45; color:#7EF4EC; border-color:#25C9D7; }
            QPlainTextEdit#SpiderLog { background:#0A1118; color:#B5CED9; border:1px solid #1C3542; border-radius:9px; padding:10px; font-size:12px; }
        """)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 16)
        root.setSpacing(12)

        header = QtWidgets.QHBoxLayout()
        title_block = QtWidgets.QVBoxLayout()
        self.eyebrow = QtWidgets.QLabel()
        self.eyebrow.setObjectName("SpiderEyebrow")
        self.title = QtWidgets.QLabel()
        self.title.setObjectName("SpiderTitle")
        self.title.setWordWrap(True)
        self.description = QtWidgets.QLabel()
        self.description.setObjectName("SpiderMuted")
        self.description.setWordWrap(True)
        title_block.addWidget(self.eyebrow)
        title_block.addWidget(self.title)
        title_block.addWidget(self.description)
        header.addLayout(title_block, 1)
        self.mascot = SpiderMark()
        self.mascot.setFixedSize(116, 90)
        header.addWidget(self.mascot, 0, QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        self.preview_card = QtWidgets.QFrame()
        self.preview_card.setObjectName("SpiderPreview")
        preview_layout = QtWidgets.QVBoxLayout(self.preview_card)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        self.preview = QtWidgets.QLabel("AetherLab workbench preview")
        self.preview.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(170)
        self.preview.setStyleSheet("color:#647B88; font-size:12px; border:0;")
        self.preview.setScaledContents(False)
        preview_layout.addWidget(self.preview)
        root.addWidget(self.preview_card)

        self.project_trail = SpiderProjectTrail()
        root.addWidget(self.project_trail)

        target_card = QtWidgets.QFrame()
        target_card.setObjectName("SpiderCard")
        target_layout = QtWidgets.QHBoxLayout(target_card)
        target_layout.setContentsMargins(13, 10, 13, 10)
        target_layout.addWidget(QtWidgets.QLabel("◉"))
        target_text = QtWidgets.QVBoxLayout()
        self.target_label = QtWidgets.QLabel()
        self.target_label.setObjectName("SpiderEyebrow")
        self.status_label = QtWidgets.QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-size:13px; font-weight:700;")
        target_text.addWidget(self.target_label)
        target_text.addWidget(self.status_label)
        target_layout.addLayout(target_text, 1)
        root.addWidget(target_card)

        self.output = QtWidgets.QPlainTextEdit()
        self.output.setObjectName("SpiderLog")
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(120)
        self.output.setMaximumBlockCount(60)
        root.addWidget(self.output, 1)

        controls = QtWidgets.QHBoxLayout()
        self.scan_button = QtWidgets.QPushButton()
        self.scan_button.setObjectName("SpiderScan")
        self.scan_button.clicked.connect(self.scan)
        self.crawl_button = QtWidgets.QPushButton()
        self.crawl_button.setObjectName("SpiderWatch")
        self.crawl_button.clicked.connect(self.crawl_project)
        self.watch_button = QtWidgets.QPushButton()
        self.watch_button.setObjectName("SpiderWatch")
        self.watch_button.setCheckable(True)
        self.watch_button.toggled.connect(self._watch_changed)
        controls.addWidget(self.scan_button, 1)
        controls.addWidget(self.crawl_button)
        controls.addWidget(self.watch_button)
        root.addLayout(controls)

        self.privacy = QtWidgets.QLabel()
        self.privacy.setObjectName("SpiderMuted")
        self.privacy.setWordWrap(True)
        root.addWidget(self.privacy)
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(20_000)
        self._timer.timeout.connect(self._watch_tick)
        self.set_language("en")

    def set_language(self, language: str) -> None:
        self._language = language if language in self._COPY else "en"
        copy = self._COPY[self._language]
        self.eyebrow.setText(copy["eyebrow"])
        self.title.setText(copy["title"])
        self.description.setText(copy["description"])
        self.target_label.setText(copy["target"])
        self.scan_button.setText(copy["scan"])
        self.crawl_button.setText(copy["crawl"])
        self.watch_button.setText(copy["watch"])
        self.privacy.setText(copy["privacy"])
        if not self._task or not self._task.is_running:
            self.status_label.setText(copy["ready"])
            if not self.output.toPlainText():
                self.output.setPlainText(copy["idle"])

    def set_settings(self, settings: AppSettings) -> None:
        """Keep Spider aligned with provider and storage changes in Settings."""
        self._settings = settings
        self._backup_root = settings.data_dir / "spider" / "backups"

    def scan(self) -> None:
        if self._task and self._task.is_running:
            return
        pixmap = self._capture_view()
        if pixmap.isNull():
            self.status_label.setText(self._COPY[self._language]["error"])
            self.output.setPlainText("AetherLab could not capture its current workbench view.")
            return
        pixmap = pixmap.scaled(
            800,
            520,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        shown = pixmap.scaled(
            max(1, self.preview.width() - 8),
            270,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        self.preview.setPixmap(shown)
        self.preview.setFixedHeight(max(180, shown.height() + 8))
        preview = QtGui.QPixmap(pixmap)
        buffer = QtCore.QBuffer()
        buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
        preview.save(buffer, "PNG")
        image_bytes = bytes(buffer.data())
        self.scan_button.setEnabled(False)
        self.status_label.setText(self._COPY[self._language]["scanning"])
        self.output.setPlainText("Spider is tracing the screen into project source…")
        self._task = BackgroundTask(
            lambda _cancel, _progress: inspect_and_repair(
                self._settings, image_bytes, self._project_root, self._backup_root, cancel_event=_cancel
            )
        )
        self._task.succeeded.connect(self._on_success)
        self._task.failed.connect(self._on_failure)
        self._task.finished.connect(self._set_actions_enabled)
        self.scan_button.setEnabled(False)
        self.crawl_button.setEnabled(False)
        self._task.start()

    def crawl_project(self) -> None:
        if self._task and self._task.is_running:
            return
        self.scan_button.setEnabled(False)
        self.crawl_button.setEnabled(False)
        self.status_label.setText("Starting project crawl…")
        self.output.setPlainText("Spider is crawling Python source files and checking them with Ruff…")
        self._task = BackgroundTask(
            lambda cancel, progress: crawl_project_sources(
                self._project_root, cancel, progress
            )
        )
        self._task.progress.connect(self._on_crawl_progress)
        self._task.succeeded.connect(self._on_crawl_success)
        self._task.failed.connect(self._on_failure)
        self._task.finished.connect(self._set_actions_enabled)
        self._task.start()

    def _on_crawl_progress(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        current = int(payload.get("current", 0))
        total = int(payload.get("total", 0))
        path = str(payload.get("path", ""))
        self.status_label.setText(f"Crawling {current}/{total}")
        self.project_trail.set_progress(current, total, path)
        self.output.setPlainText(f"Spider is tracing the project…\n\n{path}")

    def _on_crawl_success(self, result: object) -> None:
        if not isinstance(result, SpiderResult):
            return
        self.status_label.setText(result.summary)
        self.output.setPlainText(result.details or result.summary)

    def _set_actions_enabled(self) -> None:
        self.scan_button.setEnabled(True)
        self.crawl_button.setEnabled(True)

    def _on_success(self, result: object) -> None:
        if not isinstance(result, SpiderResult):
            return
        copy = self._COPY[self._language]
        if result.repaired:
            # Source edits do not replace already imported Python/Qt objects.
            # Repeated scans of that old view could otherwise propose more
            # patches for a state that only a restart can refresh.
            self.watch_button.setChecked(False)
        self.status_label.setText(copy["fixed"] if result.repaired else result.summary)
        details = result.summary
        if result.details:
            details += "\n\n" + result.details
        if result.changed_files:
            details += "\n\nPatched:\n" + "\n".join(result.changed_files)
        self.output.setPlainText(details)

    def _on_failure(self, message: str) -> None:
        self.status_label.setText(self._COPY[self._language]["error"])
        self.output.setPlainText(str(message)[:1600])

    def _watch_changed(self, enabled: bool) -> None:
        if enabled:
            self._timer.start()
            self.status_label.setText(self._COPY[self._language]["watching"])
            self.scan()
        else:
            self._timer.stop()
            if not (self._task and self._task.is_running):
                self.status_label.setText(self._COPY[self._language]["ready"])

    def _watch_tick(self) -> None:
        window = self.window()
        if window.isActiveWindow() and not window.isMinimized():
            self.scan()
        else:
            self.status_label.setText(self._COPY[self._language]["paused"])

    def stop(self) -> None:
        self._timer.stop()
        if self._task and self._task.is_running:
            self._task.cancel()
            self._task.wait(2.0)
