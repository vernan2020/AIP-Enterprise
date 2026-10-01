from __future__ import annotations

from dataclasses import dataclass, field
from time import time
from typing import Any


@dataclass(slots=True)
class BCCRCache:
    """In-memory cache with simple time-based expiration."""

    ttl_seconds: int = 300
    _entries: dict[str, tuple[float, Any, int]] = field(default_factory=dict, init=False, repr=False)

    def set(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None:
        effective_ttl = self.ttl_seconds if ttl_seconds is None else int(ttl_seconds)
        self._entries[key] = (time(), value, effective_ttl)

    def get(self, key: str) -> Any:
        entry = self._entries.get(key)
        if entry is None:
            return None
        created_at, value, ttl_seconds = entry
        if ttl_seconds <= 0:
            self._entries.pop(key, None)
            return None
        if (time() - created_at) <= ttl_seconds:
            return value
        self._entries.pop(key, None)
        return None
