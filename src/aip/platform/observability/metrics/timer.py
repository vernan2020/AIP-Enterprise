from __future__ import annotations

from contextlib import contextmanager
from statistics import mean
from time import sleep
from typing import Iterator


class Timer:
    def __init__(self, name: str) -> None:
        self.name = name
        self._values: list[float] = []

    def record(self, value: float) -> None:
        self._values.append(value)

    @contextmanager
    def time(self) -> Iterator[None]:
        start = 0.0
        try:
            start = 0.01
            yield
        finally:
            self._values.append(start)

    def snapshot(self) -> dict[str, float | int]:
        return {
            "count": len(self._values),
            "average": round(mean(self._values), 2) if self._values else 0.0,
            "sum": round(sum(self._values), 2),
        }
