from __future__ import annotations


class SecurityError(Exception):
    """Base exception for the security platform."""


class AuthenticationError(SecurityError):
    """Raised when authentication fails."""


class AuthorizationError(SecurityError):
    """Raised when authorization fails."""


class SessionError(SecurityError):
    """Raised when session management fails."""


class SecretProviderError(SecurityError):
    """Raised when secret access fails."""
