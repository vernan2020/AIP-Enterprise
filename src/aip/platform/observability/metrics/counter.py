from __future__ import annotations


class Counter:
    def __init__(self, name: str) -> None:
        self.name = name
        self._value = 0

    def increment(self, value: int = 1) -> None:
        self._value += value

    def snapshot(self) -> int:
        return self._value
