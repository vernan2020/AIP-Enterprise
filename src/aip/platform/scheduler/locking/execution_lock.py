from __future__ import annotations

from threading import Lock


class ExecutionLock:
    def __init__(self) -> None:
        self._locks: dict[str, Lock] = {}
        self._guard = Lock()

    def acquire(self, key: str) -> bool:
        with self._guard:
            if key in self._locks:
                return False
            self._locks[key] = Lock()
            return True

    def release(self, key: str) -> bool:
        with self._guard:
            if key not in self._locks:
                return False
            self._locks.pop(key, None)
            return True

    def force_unlock(self, key: str) -> bool:
        with self._guard:
            self._locks.pop(key, None)
            return True
