"""Application launcher."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from aetherlab.core.settings import load_settings
from aetherlab.ui.qt_compat import QtCore, QtGui, QtWidgets, require_qt


def _acquire_gui_lock(data_dir: Path):
    """Own one GUI per profile; a second watchdog exits cleanly.

    Disable age-based expiry: a healthy study session may stay open for days.
    QLockFile still detects dead owning processes and removes their stale locks.
    """
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(f"PhysLab cannot access its data folder: {data_dir}") from exc
    lock_path = data_dir / "physlab-gui.lock"
    lock = QtCore.QLockFile(str(lock_path))
    lock.setStaleLockTime(0)
    if lock.tryLock(0):
        return lock
    if lock.error() == QtCore.QLockFile.LockError.LockFailedError:
        readable, _pid, _host, _application = lock.getLockInfo()
        if not readable:
            # The owner may have released between tryLock and getLockInfo.
            # Retry once; never erase an unreadable lock or claim a live GUI.
            if lock.tryLock(0):
                return lock
            raise RuntimeError(f"PhysLab cannot read its launch lock: {lock_path}. Check the data folder and lock file.")
        logging.getLogger(__name__).info("PhysLab is already running for this data folder: %s", data_dir)
        return None
    raise RuntimeError(f"PhysLab cannot create its launch lock in: {data_dir}")


def _icon_path() -> Path | None:
    """Locate the bundled .ico both in a source checkout and a frozen dist."""
    candidates = [
        Path(__file__).resolve().parents[2] / "assets" / "aetherlab.ico",  # repo
        Path(getattr(sys, "_MEIPASS", ".")) / "assets" / "aetherlab.ico",  # PyInstaller
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def run_app(argv: list[str] | None = None) -> int:
    require_qt()
    settings = load_settings()
    lock = _acquire_gui_lock(settings.data_dir)
    if lock is None:
        return 0
    try:
        return _run_owned_app(settings, argv)
    finally:
        lock.unlock()


def _run_owned_app(settings, argv: list[str] | None = None) -> int:
    from aetherlab.ui.main_window import MainWindow

    # Without an explicit AppUserModelID, the Windows taskbar groups the app
    # under python.exe and shows the Python icon instead of ours.
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "PhysLab.Workbench"
            )
        except Exception:  # noqa: BLE001 — cosmetic only
            pass

    app = QtWidgets.QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("PhysLab")
    app.setApplicationDisplayName("PhysLab")
    icon = _icon_path()
    if icon is not None:
        app.setWindowIcon(QtGui.QIcon(str(icon)))
    window = MainWindow(settings=settings)
    window.show()
    return app.exec()
