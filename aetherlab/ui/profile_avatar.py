"""Circular student avatar widgets shared by the dashboard and profile editor."""

from __future__ import annotations

from aetherlab.ui.qt_compat import QtCore, QtGui, QtWidgets, require_qt

require_qt()


def _initials(name: str) -> str:
    parts = [part for part in str(name or "").split() if part]
    return "".join(part[0] for part in parts[:2]).upper() or "?"


def _draw_avatar(
    painter: QtGui.QPainter,
    rect: QtCore.QRectF,
    name: str,
    pixmap: QtGui.QPixmap,
    *,
    background: str,
) -> None:
    path = QtGui.QPainterPath()
    path.addEllipse(rect)
    painter.save()
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
    painter.setClipPath(path)
    if not pixmap.isNull():
        size = rect.size().toSize()
        scaled = pixmap.scaled(
            size,
            QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        source = QtCore.QRectF(
            (scaled.width() - rect.width()) / 2,
            (scaled.height() - rect.height()) / 2,
            rect.width(),
            rect.height(),
        )
        painter.drawPixmap(rect, scaled, source)
    else:
        painter.fillPath(path, QtGui.QColor(background))
        painter.setPen(QtGui.QColor("#FFFFFF"))
        font = painter.font()
        font.setPixelSize(max(15, int(rect.width() * 0.34)))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, _initials(name))
    painter.restore()
    painter.setPen(QtGui.QPen(QtGui.QColor("#FFFFFF"), 2))
    painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
    painter.drawEllipse(rect)


class ProfileAvatarWidget(QtWidgets.QWidget):
    def __init__(self, name: str = "", avatar_path: str = "", size: int = 144, parent=None) -> None:
        super().__init__(parent)
        self.name = name
        self.avatar_path = avatar_path
        self._pixmap = QtGui.QPixmap(avatar_path) if avatar_path else QtGui.QPixmap()
        self.setFixedSize(size, size)
        self.setAccessibleName(f"Profile photo for {name}" if name else "Profile photo")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_profile(self, name: str, avatar_path: str = "") -> None:
        self.name = name
        self.avatar_path = avatar_path
        self._pixmap = QtGui.QPixmap(avatar_path) if avatar_path else QtGui.QPixmap()
        self.setAccessibleName(f"Profile photo for {name}" if name else "Profile photo")
        self.update()

    def paintEvent(self, event):  # noqa: N802
        painter = QtGui.QPainter(self)
        _draw_avatar(
            painter,
            QtCore.QRectF(self.rect()).adjusted(2, 2, -2, -2),
            self.name,
            self._pixmap,
            background="#486A91",
        )


class ProfileAvatarButton(QtWidgets.QPushButton):
    def __init__(self, name: str = "", avatar_path: str = "", size: int = 52, parent=None) -> None:
        super().__init__(parent)
        self.name = name
        self.avatar_path = avatar_path
        self._pixmap = QtGui.QPixmap(avatar_path) if avatar_path else QtGui.QPixmap()
        self.setFixedSize(size, size)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet("QPushButton { background:transparent; border:none; padding:0; }")
        self.setAccessibleName("Open student profile")
        self.setToolTip("Open student profile")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_profile(self, name: str, avatar_path: str = "", tooltip: str | None = None) -> None:
        self.name = name
        self.avatar_path = avatar_path
        self._pixmap = QtGui.QPixmap(avatar_path) if avatar_path else QtGui.QPixmap()
        if tooltip:
            self.setToolTip(tooltip)
        action = self.toolTip() or "Open student profile"
        self.setAccessibleName(f"{action}: {name}" if name else action)
        self.update()

    def paintEvent(self, event):  # noqa: N802
        painter = QtGui.QPainter(self)
        rect = QtCore.QRectF(self.rect()).adjusted(2, 2, -2, -2)
        _draw_avatar(
            painter,
            rect,
            self.name,
            self._pixmap,
            background="#58759A" if self.underMouse() else "#486A91",
        )
        if self.hasFocus():
            painter.setPen(QtGui.QPen(QtGui.QColor("#486A91"), 2))
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.drawEllipse(rect.adjusted(-1, -1, 1, 1))
