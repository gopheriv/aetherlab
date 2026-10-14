"""Optional face-presence sampling for the local, non-blocking exam pilot."""

from __future__ import annotations

from aetherlab.ui.qt_compat import QtCore, QtGui


class CameraMonitorThread(QtCore.QThread):
    face_count = QtCore.pyqtSignal(int)
    status = QtCore.pyqtSignal(str)
    preview = QtCore.pyqtSignal(object)

    def run(self) -> None:
        capture = None
        try:
            import cv2

            capture = cv2.VideoCapture(0)
            if not capture.isOpened():
                capture.release()
                self.status.emit("unavailable")
                self.face_count.emit(-1)
                return
            cascade = cv2.CascadeClassifier(
                str(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            )
            if cascade.empty():
                self.status.emit("unavailable")
                self.face_count.emit(-1)
                return
            self.status.emit("active")
            failures = 0
            while not self.isInterruptionRequested():
                ok, frame = capture.read()
                if not ok or frame is None:
                    failures += 1
                    if failures >= 3:
                        self.status.emit("lost")
                        self.face_count.emit(-1)
                        break
                    self.msleep(250)
                    continue
                failures = 0
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.2,
                    minNeighbors=5,
                    minSize=(48, 48),
                )
                self.face_count.emit(int(len(faces)))
                preview = cv2.resize(frame, (320, 180), interpolation=cv2.INTER_AREA)
                preview = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
                image = QtGui.QImage(
                    preview.data,
                    preview.shape[1],
                    preview.shape[0],
                    int(preview.strides[0]),
                    QtGui.QImage.Format.Format_RGB888,
                ).copy()
                self.preview.emit(image)
                del gray, frame
                self.msleep(1000)
        except Exception:
            self.status.emit("unavailable")
            self.face_count.emit(-1)
        finally:
            if capture is not None:
                try:
                    capture.release()
                except Exception:
                    pass

    def stop(self) -> None:
        self.requestInterruption()
        if self.isRunning():
            self.wait(2500)
