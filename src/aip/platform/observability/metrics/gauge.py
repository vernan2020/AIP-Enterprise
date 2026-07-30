from __future__ import annotations


class Gauge:
    def __init__(self, name: str) -> None:
        self.name = name
        self._value = 0.0

    def set(self, value: float) -> None:
        self._value = value

    def snapshot(self) -> float:
        return self._value
