from __future__ import annotations


class SQLConnectorError(Exception):
    """Base exception for SQL connector failures."""


class SQLConnectionError(SQLConnectorError):
    """Raised when a SQL connection cannot be established."""


class SQLTimeoutError(SQLConnectorError):
    """Raised when SQL execution exceeds the configured timeout."""
