from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True, slots=True)
class SecurityEvent:
    """Base security event."""

    event_type: str = ""
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_type:
            object.__setattr__(self, "event_type", self.__class__.__name__)


@dataclass(frozen=True, slots=True)
class AuthenticationSucceeded(SecurityEvent):
    username: str | None = None


@dataclass(frozen=True, slots=True)
class AuthenticationFailed(SecurityEvent):
    username: str | None = None


@dataclass(frozen=True, slots=True)
class SessionCreated(SecurityEvent):
    session_id: str | None = None


@dataclass(frozen=True, slots=True)
class SessionExpired(SecurityEvent):
    session_id: str | None = None


@dataclass(frozen=True, slots=True)
class SessionClosed(SecurityEvent):
    session_id: str | None = None


@dataclass(frozen=True, slots=True)
class AuthorizationGranted(SecurityEvent):
    principal_id: str | None = None


@dataclass(frozen=True, slots=True)
class AuthorizationDenied(SecurityEvent):
    principal_id: str | None = None


@dataclass(frozen=True, slots=True)
class PermissionEvaluated(SecurityEvent):
    permission_name: str | None = None


class SecurityEventPublisher:
    """Simple event publisher for security events."""

    def __init__(self) -> None:
        self._events: list[SecurityEvent] = []

    def publish(self, event: SecurityEvent) -> None:
        self._events.append(event)

    def get_events(self) -> tuple[SecurityEvent, ...]:
        return tuple(self._events)
