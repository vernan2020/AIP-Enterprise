from __future__ import annotations

from collections.abc import Callable
from typing import Any


class UIEventBus:
    """Simple publish/subscribe bus for UI-level events."""

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable[[Any], None]]] = {}

    def subscribe(self, topic: str, listener: Callable[[Any], None]) -> None:
        self._listeners.setdefault(topic, []).append(listener)

    def publish(self, topic: str, payload: Any = None) -> None:
        for listener in self._listeners.get(topic, []):
            listener(payload)
