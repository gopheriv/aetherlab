"""Place four full-resolution UI captures on a labeled 4K contact sheet."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aetherlab.core.console import configure_utf8_stdio
from aetherlab.ui.fonts import install_ui_fonts
from aetherlab.ui.qt_compat import QtCore, QtGui, QtWidgets


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("captures", nargs=4, help="label=path")
    args = parser.parse_args()
    _app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    install_ui_fonts()
    canvas = QtGui.QImage(3840, 2160, QtGui.QImage.Format.Format_RGB32)
    canvas.fill(QtGui.QColor("#F4F7FB"))
    painter = QtGui.QPainter(canvas)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setPen(QtGui.QColor("#18283D"))
    painter.setFont(QtGui.QFont("DejaVu Sans", 35, QtGui.QFont.Weight.Bold))
    painter.drawText(QtCore.QRect(64, 30, 3700, 80), QtCore.Qt.AlignmentFlag.AlignVCenter, args.title)
    gap = 28
    left, top = 64, 132
    width = (3840 - 128 - gap) // 2
    height = (2160 - top - 64 - gap) // 2
    for index, value in enumerate(args.captures):
        label, file_name = value.split("=", 1)
        source = QtGui.QImage(str(Path(file_name)))
        if source.isNull():
            raise FileNotFoundError(file_name)
        column, row = index % 2, index // 2
        x = left + column * (width + gap)
        y = top + row * (height + gap)
        painter.setPen(QtGui.QPen(QtGui.QColor("#D8E1EC"), 2))
        painter.setBrush(QtGui.QColor("#FFFFFF"))
        painter.drawRoundedRect(QtCore.QRect(x, y, width, height), 18, 18)
        painter.setPen(QtGui.QColor("#18283D"))
        painter.setFont(QtGui.QFont("DejaVu Sans", 19, QtGui.QFont.Weight.DemiBold))
        painter.drawText(QtCore.QRect(x + 24, y + 14, width - 48, 42), QtCore.Qt.AlignmentFlag.AlignVCenter, label)
        image_rect = QtCore.QRect(x + 16, y + 66, width - 32, height - 82)
        scaled = source.scaled(image_rect.size(), QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                               QtCore.Qt.TransformationMode.SmoothTransformation)
        target = QtCore.QPoint(image_rect.x() + (image_rect.width() - scaled.width()) // 2,
                               image_rect.y() + (image_rect.height() - scaled.height()) // 2)
        painter.drawImage(target, scaled)
    painter.end()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not canvas.save(str(args.output)):
        raise RuntimeError(f"Could not save {args.output}")
    print(f"{args.output} {canvas.width()}x{canvas.height()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
