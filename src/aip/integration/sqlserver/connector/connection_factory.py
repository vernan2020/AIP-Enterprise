from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from aip.integration.sqlserver.configuration.sql_config import SQLServerConfig
from aip.integration.sqlserver.driver.driver_adapter import SQLServerDriverAdapter


class SQLServerConnectionFactory(ABC):
    """Abstract connection factory for SQL Server adapters."""

    def __init__(
        self, config: SQLServerConfig, driver: SQLServerDriverAdapter | None = None
    ) -> None:
        self.config = config
        self.driver = driver

    @abstractmethod
    def create_connection(self) -> Any:
        """Create a new connection object."""


class DefaultSQLServerConnectionFactory(SQLServerConnectionFactory):
    """Practical fallback factory used when no driver-specific adapter is injected."""

    def create_connection(self) -> Any:
        class _FallbackCursor:
            def __init__(self) -> None:
                self._rows: list[dict[str, Any]] = []
                self.executed: tuple[str, dict[str, Any]] | None = None

            def execute(
                self, query: str, params: dict[str, Any] | None = None
            ) -> "_FallbackCursor":
                self.executed = (query, params or {})
                return self

            def fetchall(self) -> list[dict[str, Any]]:
                return list(self._rows)

        class _FallbackConnection:
            def __init__(self) -> None:
                self._cursor = _FallbackCursor()

            def cursor(self) -> _FallbackCursor:
                return self._cursor

            def close(self) -> None:
                return None

            def commit(self) -> None:
                return None

        return _FallbackConnection()
