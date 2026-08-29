from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from aip.platform.security.authentication.token import Token
from aip.platform.security.exceptions.security_exceptions import SessionError
from aip.platform.security.identity.principal import Principal


@dataclass(frozen=True, slots=True)
class Session:
    """Immutable session representation."""

    session_id: str
    principal: Principal
    token: Token
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None

    def is_expired(self, now: datetime | None = None) -> bool:
        current_time = now or datetime.now(timezone.utc)
        return self.expires_at is not None and current_time >= self.expires_at


class SessionManager:
    """Manage authentication sessions and token lifecycle."""

    def __init__(self, ttl_seconds: int = 900) -> None:
        self._ttl_seconds = ttl_seconds
        self._sessions: dict[str, Session] = {}

    def create_session(self, principal: Principal, token: Token | None = None) -> Session:
        session_token = token or Token(
            value=f"token-{principal.identity.subject}",
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=self._ttl_seconds),
        )
        expires_at = session_token.expires_at or datetime.now(timezone.utc) + timedelta(
            seconds=self._ttl_seconds
        )
        session = Session(
            session_id=f"session-{principal.identity.subject}",
            principal=principal,
            token=session_token,
            expires_at=expires_at,
        )
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Session:
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionError(f"Session not found: {session_id}")
        if session.is_expired():
            self._sessions.pop(session_id, None)
            raise SessionError(f"Session expired: {session_id}")
        return session

    def refresh_session(self, session_id: str, token: Token | None = None) -> Session:
        session = self.get_session(session_id)
        refreshed_token = token or session.token.refresh(self._ttl_seconds)
        updated = Session(
            session_id=session.session_id,
            principal=session.principal,
            token=refreshed_token,
            created_at=session.created_at,
            expires_at=refreshed_token.expires_at,
        )
        self._sessions[session_id] = updated
        return updated

    def close_session(self, session_id: str) -> None:
        if session_id not in self._sessions:
            raise SessionError(f"Session not found: {session_id}")
        self._sessions.pop(session_id, None)

    def list_active_sessions(self) -> tuple[Session, ...]:
        return tuple(session for session in self._sessions.values() if not session.is_expired())
