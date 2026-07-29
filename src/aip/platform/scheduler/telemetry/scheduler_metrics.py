from __future__ import annotations

from collections import defaultdict


class SchedulerMetrics:
    def __init__(self) -> None:
        self._values: dict[str, float] = defaultdict(float)

    def increment(self, key: str, value: float = 1.0) -> None:
        self._values[key] += value

    def gauge(self, key: str, value: float) -> None:
        self._values[key] = value

    def snapshot(self) -> dict[str, float]:
        return dict(self._values)
