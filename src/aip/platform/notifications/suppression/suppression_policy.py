from __future__ import annotations


class SuppressionPolicy:
    def __init__(self) -> None:
        self._suppressed: set[str] = set()

    def suppress(self, key: str) -> None:
        self._suppressed.add(key)

    def is_suppressed(self, key: str) -> bool:
        return key in self._suppressed
