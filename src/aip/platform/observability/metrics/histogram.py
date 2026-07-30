from __future__ import annotations

from statistics import mean


class Histogram:
    def __init__(self, name: str) -> None:
        self.name = name
        self._values: list[float] = []

    def observe(self, value: float) -> None:
        self._values.append(value)

    def snapshot(self) -> dict[str, float | int]:
        return {
            "count": len(self._values),
            "average": round(mean(self._values), 2) if self._values else 0.0,
            "sum": round(sum(self._values), 2),
        }
