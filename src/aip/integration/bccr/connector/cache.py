from __future__ import annotations

from dataclasses import dataclass, field
from time import time
from typing import Any


@dataclass(slots=True)
class BCCRCache:
    """In-memory cache with simple time-based expiration."""

    ttl_seconds: int = 300
    _entries: dict[str, tuple[float, Any]] = field(default_factory=dict, init=False, repr=False)

    def set(self, key: str, value: Any) -> None:
        self._entries[key] = (time(), value)

    def get(self, key: str) -> Any:
        entry = self._entries.get(key)
        if entry is None:
            return None
        created_at, value = entry
        if self.ttl_seconds <= 0:
            self._entries.pop(key, None)
            return None
        if (time() - created_at) <= self.ttl_seconds:
            return value
        self._entries.pop(key, None)
        return None
