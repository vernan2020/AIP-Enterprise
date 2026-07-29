from __future__ import annotations

from typing import Any


class NotificationService:
    """Stores and exposes UI notifications."""

    def __init__(self) -> None:
        self._items: list[dict[str, Any]] = []

    def add(self, message: str, level: str = "info") -> None:
        self._items.append({"message": message, "level": level})

    def items(self) -> list[dict[str, Any]]:
        return list(self._items)
