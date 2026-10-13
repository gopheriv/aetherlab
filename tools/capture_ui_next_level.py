"""Capture isolated PhysLab UI screenshots without touching learner data.

Run with QT_QPA_PLATFORM=offscreen and QT_SCALE_FACTOR=2.5 to make a
1536×864 logical window into a 3840×2160 image.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from aetherlab.core.console import configure_utf8_stdio
from aetherlab.core.settings import load_settings
from aetherlab.ui.companion_dialog import CompanionPickerDialog
from aetherlab.ui.exam_practice import ExamPracticeDialog
from aetherlab.ui.leaderboard_dialog import LeaderboardDialog
from aetherlab.ui.main_window import MainWindow
from aetherlab.ui.profile_dialog import StudentProfileDialog
from aetherlab.ui.qt_compat import QtCore, QtGui, QtWidgets
from aetherlab.ui.style import AETHERLAB_QSS


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--route", choices=("home", "topics", "progress", "ai", "library", "history", "lab", "companions", "profile", "leaderboard", "practice", "question", "result"), default="home")
    parser.add_argument("--language", choices=("kk", "ru", "en"), default="kk")
    parser.add_argument("--width", type=int, default=1536)
    parser.add_argument("--height", type=int, default=864)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    app.setStyleSheet(AETHERLAB_QSS)
    demo_dir = Path("tmp/ui-next-level-preview").resolve()
    demo_dir.mkdir(parents=True, exist_ok=True)
    settings = replace(load_settings(), data_dir=demo_dir, openai_api_key="test")
    widget = MainWindow(settings)
    widget.setMinimumSize(640, 480)
    widget.resize(args.width, args.height)
    widget._on_title_language_changed(args.language)
    routes = {"home": 0, "topics": 1, "progress": 3, "ai": 4, "library": 5, "history": 6, "lab": 7}
    if args.route in routes:
        widget.sidebar.select(routes[args.route])
    widget.show()
    for _ in range(6):
        app.processEvents()
    image = widget.grab().toImage()
    if args.route not in routes:
        if args.route == "companions":
            dialog = CompanionPickerDialog(selected_companion="photon", points=80, language=args.language, parent=widget)
        elif args.route == "profile":
            dialog = StudentProfileDialog(widget.student_profile_store, language=args.language, parent=widget)
        elif args.route == "leaderboard":
            dialog = LeaderboardDialog(widget.student_profile_store, widget.active_student_profile, language=args.language, parent=widget)
        else:
            dialog = ExamPracticeDialog(args.language, parent=widget, progress_path=demo_dir / "screenshot-practice-progress.json")
            if args.route == "question":
                dialog._start()
                dialog._timer.stop()
            elif args.route == "result":
                dialog._mode_buttons[1].click()
                dialog._start()
                dialog._timer.stop()
                dialog._mode = "timed"
                dialog._full_mock = True
                dialog._answers = [tuple(question["correct_indices"]) for question in dialog._questions]
                dialog._show_results()
        dialog.show()
        for _ in range(6):
            app.processEvents()
        dialog_image = dialog.grab().toImage()
        image.setDevicePixelRatio(1)
        dialog_image.setDevicePixelRatio(1)
        painter = QtGui.QPainter(image)
        painter.fillRect(image.rect(), QtGui.QColor(24, 40, 61, 70))
        x = (image.width() - dialog_image.width()) // 2
        y = (image.height() - dialog_image.height()) // 2
        painter.drawImage(QtCore.QPoint(x, y), dialog_image)
        painter.end()
        dialog.close()
    if not image.save(str(args.output)):
        raise RuntimeError(f"Could not save {args.output}")
    print(f"{args.output} {image.width()}x{image.height()}")
    widget.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
