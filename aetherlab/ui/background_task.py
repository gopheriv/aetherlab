"""Small daemon-thread bridge for bounded Settings network actions."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from aetherlab.ui.qt_compat import QtCore

ProgressCallback = Callable[[object], None]
Operation = Callable[[threading.Event, ProgressCallback], Any]


class BackgroundTask(QtCore.QObject):
    """Run one blocking callable without blocking or owning a QThread."""

    progress = QtCore.pyqtSignal(object)
    succeeded = QtCore.pyqtSignal(object)
    failed = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal()

    def __init__(self, operation: Operation) -> None:
        super().__init__(None)
        self._operation = operation
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.is_running:
            return
        self._thread = threading.Thread(
            target=self._run,
            name="AetherLabSettingsTask",
            daemon=True,
        )
        self._thread.start()

    def cancel(self) -> None:
        self._cancel.set()

    def wait(self, timeout: float | None = None) -> None:
        """Block until the worker thread has fully finished (bounded).

        Teardown-safety: a caller joins before destroying the owning dialog so no
        daemon thread is left to emit a signal into a torn-down widget (a PyQt
        slot touching a deleted C++ object aborts the process — the exact
        CI-only, timing-dependent crash this guards against).
        """
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def _report(self, payload: object) -> None:
        if not self._cancel.is_set():
            self._emit(self.progress, payload)

    def _run(self) -> None:
        try:
            result = self._operation(self._cancel, self._report)
            if not self._cancel.is_set():
                self._emit(self.succeeded, result)
        except Exception as exc:  # noqa: BLE001 - UI task failures are displayable results
            if not self._cancel.is_set():
                self._emit(self.failed, str(exc)[:240])
        finally:
            # Don't emit into a dialog that asked to cancel (it is closing): the
            # re-enable slots would touch widgets under teardown.
            if not self._cancel.is_set():
                self._emit(self.finished)

    @staticmethod
    def _emit(signal, *args: object) -> None:
        try:
            signal.emit(*args)
        except RuntimeError:
            # The dialog may have closed while a bounded socket call finished.
            pass
