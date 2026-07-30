from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class SecurityHealth:
    """Immutable snapshot of security platform health."""

    successful_logins: int = 0
    failed_logins: int = 0
    authorization_failures: int = 0
    active_sessions: int = 0
    expired_sessions: int = 0
    permission_checks: int = 0
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
