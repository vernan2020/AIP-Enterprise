from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SQLAuthentication:
    """Authentication settings for SQL Server connections."""

    mode: str = "integrated"
    username: str | None = None
    password: str | None = None

    def __repr__(self) -> str:
        return f"SQLAuthentication(mode={self.mode!r}, username={self.username!r}, password='***')"


@dataclass(frozen=True, slots=True)
class SQLServerConfig:
    """Configuration for the SQL Server connector."""

    connection_string: str = ""
    server: str = ""
    database: str = ""
    authentication: SQLAuthentication | None = None
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: float = 0.1
    pool_size: int = 5
    enable_streaming: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.connection_string.strip() and not (
            self.server.strip() and self.database.strip()
        ):
            raise ValueError("connection_string is required")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if self.pool_size <= 0:
            raise ValueError("pool_size must be positive")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def build_connection_string(self) -> str:
        if self.connection_string.strip():
            return self.connection_string
        return f"Server={self.server};Database={self.database};"

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "server": self.server,
            "database": self.database,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds,
            "pool_size": self.pool_size,
            "enable_streaming": self.enable_streaming,
            "metadata": dict(self.metadata),
            "authentication": self.authentication,
        }

    def __repr__(self) -> str:
        safe = self.to_safe_dict()
        safe["authentication"] = (
            repr(self.authentication) if self.authentication is not None else None
        )
        return f"SQLServerConfig({safe})"
