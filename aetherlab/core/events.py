"""Small headless observer used by services and tests.

The PyQt6 UI exposes the same event boundaries through pyqtSignal. This class is
kept dependency-free so the synchronization model can be exercised without a GUI.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Event:
    name: str
    payload: Any


class StateBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[Event], None]]] = defaultdict(list)

    def subscribe(self, name: str, callback: Callable[[Event], None]) -> None:
        self._subscribers[name].append(callback)

    def emit(self, name: str, payload: Any) -> None:
        event = Event(name=name, payload=payload)
        for callback in list(self._subscribers.get(name, [])):
            callback(event)
