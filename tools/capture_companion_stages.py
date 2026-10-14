"""Render the nine in-app companion forms into a 4K comparison sheet."""

from __future__ import annotations

import sys
from pathlib import Path

from aetherlab.core.console import configure_utf8_stdio
from aetherlab.ui.fonts import install_ui_fonts
from aetherlab.ui.qt_compat import QtCore, QtGui, QtWidgets
from aetherlab.ui.study_visuals import CompanionArt


def main() -> int:
    configure_utf8_stdio()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    install_ui_fonts()
    canvas = QtGui.QImage(3840, 2160, QtGui.QImage.Format.Format_RGB32)
    canvas.fill(QtGui.QColor("#F4F7FB"))
    painter = QtGui.QPainter(canvas)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setPen(QtGui.QColor("#18283D"))
    painter.setFont(QtGui.QFont("DejaVu Sans", 34, QtGui.QFont.Weight.Bold))
    painter.drawText(QtCore.QRect(60, 22, 3600, 88), QtCore.Qt.AlignmentFlag.AlignVCenter,
                     "Компаньоны PhysLab · три формы каждого")
    names = (("quantum", "Квант"), ("photon", "Фотон"), ("lab_bot", "Лаб-бот"))
    stages = (("Форма 1", "0–49 очков"), ("Форма 2", "50–149 очков"), ("Форма 3", "150+ очков"))
    left, top, gap = 60, 130, 24
    width = (3840 - 120 - 2 * gap) // 3
    height = (2160 - top - 58 - 2 * gap) // 3
    for row, (stage_label, points_label) in enumerate(stages):
        for column, (companion_id, name) in enumerate(names):
            art = CompanionArt(companion_id=companion_id, stage=row)
            art.setFixedSize(156, 156)
            art.show()
            app.processEvents()
            shot = art.grab().toImage()
            if shot.isNull():
                raise RuntimeError(f"Missing artwork: {companion_id}/{row}")
            x, y = left + column * (width + gap), top + row * (height + gap)
            painter.setPen(QtGui.QPen(QtGui.QColor("#D8E1EC"), 2))
            painter.setBrush(QtGui.QColor(art.background_color()))
            painter.drawRoundedRect(QtCore.QRect(x, y, width, height), 20, 20)
            shot.setDevicePixelRatio(1)
            art_rect = QtCore.QRect(x + 250, y + 45, width - 500, height - 145)
            scaled = shot.scaled(art_rect.size(), QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                 QtCore.Qt.TransformationMode.SmoothTransformation)
            painter.drawImage(QtCore.QPoint(art_rect.x() + (art_rect.width() - scaled.width()) // 2,
                                            art_rect.y() + (art_rect.height() - scaled.height()) // 2), scaled)
            painter.setPen(QtGui.QColor("#18283D"))
            painter.setFont(QtGui.QFont("DejaVu Sans", 22, QtGui.QFont.Weight.Bold))
            painter.drawText(QtCore.QRect(x + 30, y + height - 110, width - 60, 44), QtCore.Qt.AlignmentFlag.AlignCenter, name)
            painter.setPen(QtGui.QColor("#53647A"))
            painter.setFont(QtGui.QFont("DejaVu Sans", 15))
            painter.drawText(QtCore.QRect(x + 30, y + height - 65, width - 60, 30), QtCore.Qt.AlignmentFlag.AlignCenter,
                             f"{stage_label} · {points_label}")
            art.close()
    painter.end()
    output = Path("ui-screenshots/ui-next-level/contact-sheet-companion-stages-4k.png")
    output.parent.mkdir(parents=True, exist_ok=True)
    if not canvas.save(str(output)):
        raise RuntimeError(f"Could not save {output}")
    print(f"{output} {canvas.width()}x{canvas.height()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
