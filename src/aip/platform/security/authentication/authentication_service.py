from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from aip.platform.security.authentication.credential_validator import CredentialValidator
from aip.platform.security.authentication.session_manager import SessionManager
from aip.platform.security.authentication.token import Token
from aip.platform.security.events.security_events import (
    AuthenticationFailed,
    AuthenticationSucceeded,
    SecurityEventPublisher,
)
from aip.platform.security.exceptions.security_exceptions import AuthenticationError
from aip.platform.security.identity.identity import Identity
from aip.platform.security.identity.identity_provider import IdentityProvider
from aip.platform.security.identity.principal import Principal


class AuthenticationService:
    """Service for authenticating principals and managing sessions."""

    def __init__(
        self,
        credential_validator: CredentialValidator,
        identity_provider: IdentityProvider,
        session_manager: SessionManager | None = None,
        event_publisher: SecurityEventPublisher | None = None,
    ) -> None:
        self._credential_validator = credential_validator
        self._identity_provider = identity_provider
        self._session_manager = session_manager or SessionManager()
        self._event_publisher = event_publisher or SecurityEventPublisher()

    def authenticate(self, username: str, password: str) -> tuple[Principal, Token]:
        if not self._credential_validator.validate(username, password):
            self._event_publisher.publish(AuthenticationFailed(username=username, occurred_at=datetime.now(timezone.utc)))
            raise AuthenticationError("Authentication failed")
        identity = self._identity_provider.get_identity(username)
        principal = Principal(identity=identity)
        token = Token(value=f"token-{identity.subject}", expires_at=datetime.now(timezone.utc))
        self._event_publisher.publish(AuthenticationSucceeded(username=username, occurred_at=datetime.now(timezone.utc)))
        return principal, token

    def create_session(self, principal: Principal, token: Token | None = None) -> Any:
        return self._session_manager.create_session(principal, token)
