from __future__ import annotations


class DeduplicationService:
    def __init__(self) -> None:
        self._seen: set[str] = set()

    def is_duplicate(self, key: str) -> bool:
        if key in self._seen:
            return True
        self._seen.add(key)
        return False
