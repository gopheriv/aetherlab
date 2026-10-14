"""Minimal, local-only event flags for the optional shadow proctoring pilot.

This module never stores image data and never decides whether a student cheated.
The signals below are review hints only; they do not change an exam score.
"""

from __future__ import annotations

from datetime import datetime, timezone


class ShadowEventTracker:
    """Turn consecutive camera observations into sparse, timestamped flags."""

    def __init__(self, *, face_missing_after_s: float = 8.0, multiple_faces_after_s: float = 3.0):
        self.face_missing_after_s = max(1.0, float(face_missing_after_s))
        self.multiple_faces_after_s = max(1.0, float(multiple_faces_after_s))
        self._no_face_since: float | None = None
        self._multiple_since: float | None = None
        self._raised: set[str] = set()
        self.events: list[dict[str, str]] = []

    def _emit(self, kind: str) -> dict[str, str]:
        event = {"type": kind, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        self.events.append(event)
        return event

    def observe_face_count(self, count: int, *, now: float) -> list[dict[str, str]]:
        """Accept a count from an on-device detector; -1 means unavailable."""
        emitted: list[dict[str, str]] = []
        if count < 0:
            # Missing camera observations interrupt a continuous face-count
            # interval. Do not count downtime as observed absence/multiple faces.
            self._no_face_since = None
            self._multiple_since = None
            self._raised.difference_update({"face_not_visible", "multiple_faces"})
            if "camera_unavailable" not in self._raised:
                emitted.append(self._emit("camera_unavailable"))
                self._raised.add("camera_unavailable")
            return emitted
        if "camera_unavailable" in self._raised:
            self._raised.discard("camera_unavailable")
        if count == 0:
            self._no_face_since = self._no_face_since if self._no_face_since is not None else now
            self._multiple_since = None
            self._raised.discard("multiple_faces")
            if now - self._no_face_since >= self.face_missing_after_s and "face_not_visible" not in self._raised:
                emitted.append(self._emit("face_not_visible"))
                self._raised.add("face_not_visible")
        elif count > 1:
            self._multiple_since = self._multiple_since if self._multiple_since is not None else now
            self._no_face_since = None
            self._raised.discard("face_not_visible")
            if now - self._multiple_since >= self.multiple_faces_after_s and "multiple_faces" not in self._raised:
                emitted.append(self._emit("multiple_faces"))
                self._raised.add("multiple_faces")
        else:
            self._no_face_since = None
            self._multiple_since = None
            self._raised.discard("face_not_visible")
            self._raised.discard("multiple_faces")
        return emitted

    def note_focus_loss(self) -> dict[str, str]:
        """Record an app focus change without trying to lock the operating system."""
        return self._emit("app_focus_lost")

    def note_camera_lost(self) -> dict[str, str]:
        """Record a stream interruption and suppress a duplicate unavailable flag."""
        self._no_face_since = None
        self._multiple_since = None
        self._raised.difference_update({"face_not_visible", "multiple_faces"})
        self._raised.add("camera_unavailable")
        return self._emit("camera_lost")

    def snapshot(self) -> list[dict[str, str]]:
        return [dict(event) for event in self.events[-100:]]
