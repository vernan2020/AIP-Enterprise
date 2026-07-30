from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True, slots=True)
class Token:
    """Immutable bearer token abstraction."""

    value: str
    issued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None

    def is_expired(self, now: datetime | None = None) -> bool:
        current_time = now or datetime.now(timezone.utc)
        return self.expires_at is not None and current_time >= self.expires_at

    def refresh(self, ttl_seconds: int = 300) -> "Token":
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        return Token(value=self.value, issued_at=self.issued_at, expires_at=expires_at)
