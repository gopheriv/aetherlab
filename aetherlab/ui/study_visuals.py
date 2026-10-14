"""Small vector illustrations for the study studio, drawn at any display scale."""

import math
import sys
from pathlib import Path

from aetherlab.ui.qt_compat import QtCore, QtGui, QtWidgets


class OrbitArt(QtWidgets.QWidget):
    _ORBIT_ANGLES = (-32, 32, 90)

    def __init__(self, parent=None, light=True):
        super().__init__(parent)
        self.light = light
        self.setMinimumSize(130, 130)
        self.setMaximumWidth(240)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self.setAccessibleName("Physics orbit illustration")

    @staticmethod
    def orbit_point(orbit_angle: float, point_angle: float) -> QtCore.QPointF:
        """Return a point on one of the ellipses in the drawing's coordinates."""
        theta = math.radians(point_angle)
        x, y = 91 * math.cos(theta), 37 * math.sin(theta)
        rotation = math.radians(orbit_angle)
        return QtCore.QPointF(
            x * math.cos(rotation) - y * math.sin(rotation),
            x * math.sin(rotation) + y * math.cos(rotation),
        )

    @staticmethod
    def drawing_scale(width: float, height: float) -> float:
        """Fit the orbit art with generous breathing room around the paths."""
        return max(0.01, (min(width, height) - 44) / 220)

    def paintEvent(self, event):  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.translate(self.width() / 2, self.height() / 2)
        # Keep the card background visible and keep dots away from the edges.
        scale = self.drawing_scale(self.width(), self.height())
        p.scale(scale, scale)
        ink = "#CAD5E3" if self.light else "#486A91"
        p.setPen(QtGui.QPen(QtGui.QColor(ink), 1.5))
        p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        for angle in self._ORBIT_ANGLES:
            p.save()
            p.rotate(angle)
            p.drawEllipse(QtCore.QRectF(-91, -37, 182, 74))
            p.restore()

        # Place each electron on its ellipse using the same transform as the
        # orbit. Fixed hand-tuned offsets drifted off the paths when the art
        # was resized or its angles changed.
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        nucleus = "#FFFFFF" if self.light else "#E9EFF7"
        p.setBrush(QtGui.QColor(nucleus))
        p.drawEllipse(QtCore.QPointF(0, 0), 22, 22)

        electrons = (
            (self._ORBIT_ANGLES[0], 0, 10, "#BCE8D6"),
            (self._ORBIT_ANGLES[1], 180, 7, "#FFD8AE"),
            (self._ORBIT_ANGLES[2], 0, 8, "#B7DCE5"),
        )
        for orbit_angle, point_angle, radius, color in electrons:
            point = self.orbit_point(orbit_angle, point_angle)
            p.setBrush(QtGui.QColor(color))
            p.drawEllipse(point, radius, radius)
        p.setPen(QtGui.QPen(QtGui.QColor("#486A91"), 2))
        p.drawLine(-7, 0, 7, 0)
        p.drawLine(0, -7, 0, 7)


class CompanionArt(QtWidgets.QWidget):
    """Render one of the physics companions at its current evolution stage."""

    _COMPANION_COLUMNS = {"quantum": 0, "photon": 1, "lab_bot": 2}
    _EVOLUTION_FILES = {
        "quantum": "quantum-evolution-4k.png",
        "photon": "photon-evolution-4k.png",
        "lab_bot": "lab-bot-evolution-4k.png",
    }
    _EVOLUTION_BOUNDS = {
        "quantum": (0, 1280, 2560, 3840),
        "photon": (0, 1167, 2365, 3840),
        "lab_bot": (0, 1260, 2505, 3840),
    }
    # Fallback bounds for an older package containing only the overview sheet.
    _COLUMN_BOUNDS = ((300, 1378), (1378, 2520), (2520, 3540))
    _ROW_BOUNDS = ((0, 673), (673, 1333), (1333, 2160))
    _ACCESSIBLE_NAMES = {"quantum": "Quantum", "photon": "Photon", "lab_bot": "Lab bot"}

    def __init__(self, parent=None, pet_id=None, stage=0, *, companion_id=None):
        super().__init__(parent)
        requested_id = companion_id or pet_id or "quantum"
        self._companion_id = "quantum"
        self._stage = 0
        roots = (
            Path(__file__).resolve().parents[2] / "assets" / "ui",
            Path(getattr(sys, "_MEIPASS", ".")) / "assets" / "ui",
        )
        self._asset_roots = roots
        self._concept_sheet = QtGui.QImage()
        self._evolution_sheet = False
        self.setMinimumSize(112, 112)
        self.setMaximumSize(156, 156)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet("background:#FBF6ED; border-radius:14px;")
        self.set_companion(requested_id, stage)

    @property
    def stage(self) -> int:
        return self._stage

    @property
    def pet_id(self) -> str:
        """Compatibility alias for saved UI integrations from earlier builds."""
        return self._companion_id

    @property
    def companion_id(self) -> str:
        return self._companion_id

    def set_companion(self, companion_id: str, stage: int) -> None:
        chosen = (
            companion_id if companion_id in self._COMPANION_COLUMNS else "quantum"
        )
        if chosen != self._companion_id or self._concept_sheet.isNull():
            self._concept_sheet = QtGui.QImage()
            self._evolution_sheet = False
            for root in self._asset_roots:
                candidate = root / "companion-contact-sheets" / self._EVOLUTION_FILES[chosen]
                if candidate.is_file():
                    self._concept_sheet = QtGui.QImage(str(candidate))
                    if not self._concept_sheet.isNull():
                        self._evolution_sheet = True
                        break
            if self._concept_sheet.isNull():
                for root in self._asset_roots:
                    candidate = root / "companion-contact-sheets" / "physics-companions-overview-4k.png"
                    if candidate.is_file():
                        self._concept_sheet = QtGui.QImage(str(candidate))
                        if not self._concept_sheet.isNull():
                            break
        self._companion_id = chosen
        self._stage = min(2, max(0, int(stage)))
        self.setAccessibleName(
            f"{self._ACCESSIBLE_NAMES[self._companion_id]}, form {self._stage + 1}"
        )
        self.update()

    def background_color(self) -> str:
        """Return the illustration paper colour for a seamless preview card."""
        if self._concept_sheet.isNull():
            return "#FBF6ED"
        if self._evolution_sheet:
            left = self._EVOLUTION_BOUNDS[self._companion_id][self._stage]
            return self._concept_sheet.pixelColor(left + 80, 160).name().upper()
        left, _ = self._COLUMN_BOUNDS[self._COMPANION_COLUMNS[self._companion_id]]
        top, _ = self._ROW_BOUNDS[self._stage]
        return self._concept_sheet.pixelColor(left + 24, top + 24).name().upper()

    def paintEvent(self, event):  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        if self._concept_sheet.isNull():
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QColor("#EAF0F6"))
            painter.drawEllipse(self.rect().adjusted(8, 8, -8, -8))
            painter.setPen(QtGui.QColor("#486A91"))
            painter.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, "♡")
            return
        if self._evolution_sheet:
            # Each dedicated sheet has three evolution stages side by side.
            # The inset removes the thin dividers without touching the art.
            bounds = self._EVOLUTION_BOUNDS[self._companion_id]
            left, right = bounds[self._stage], bounds[self._stage + 1]
            source = QtCore.QRect(
                left + 18, 180 if self._stage == 2 else 260,
                right - left - 36, 1560 if self._stage == 2 else 1380,
            )
        else:
            column = self._COMPANION_COLUMNS[self._companion_id]
            left, right = self._COLUMN_BOUNDS[column]
            top, bottom = self._ROW_BOUNDS[self._stage]
            source = QtCore.QRect(left + 5, top + 5, right - left - 10, bottom - top - 10)
        # QPainter samples the original 4K pixels into the physical device
        # rectangle. Pre-scaling to logical widget pixels would blur HiDPI UI.
        scale = min(self.width() / source.width(), self.height() / source.height())
        width = source.width() * scale
        height = source.height() * scale
        target = QtCore.QRectF(
            (self.width() - width) / 2,
            (self.height() - height) / 2,
            width,
            height,
        )
        preview = QtGui.QPainterPath()
        preview.addRoundedRect(target, 10, 10)
        painter.setClipPath(preview)
        painter.drawImage(target, self._concept_sheet, QtCore.QRectF(source))
        painter.setClipping(False)
        painter.setPen(QtGui.QPen(QtGui.QColor("#E8DDD0"), 0.7))
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(target, 10, 10)


class GoalRing(QtWidgets.QWidget):
    """An honest weekly-goal ring; no goal is shown as an empty ring."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(96, 96)
        self.value = 0
        self.caption = "—"

    def set_progress(self, completed, goal):
        self.value = min(1, max(0, completed / goal)) if goal else 0
        self.caption = f"{round(self.value * 100)}%" if goal else "—"
        self.setAccessibleName(f"Weekly goal: {self.caption}")
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        ring = QtCore.QRectF(8, 8, 80, 80)
        p.setPen(QtGui.QPen(QtGui.QColor("#EEEBF5"), 7))
        p.drawEllipse(ring)
        pen = QtGui.QPen(QtGui.QColor("#486A91"), 7)
        pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(ring, 90 * 16, -int(self.value * 360 * 16))
        p.setPen(QtGui.QColor("#18283D"))
        font = p.font()
        font.setPixelSize(22)
        font.setBold(True)
        p.setFont(font)
        p.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, self.caption)
