from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aip.integration.sqlserver.connector.connection_factory import SQLServerConnectionFactory


@dataclass(slots=True)
class ConnectionPool:
    """Small, testable connection pool that manages a handful of connections."""

    factory: SQLServerConnectionFactory
    max_size: int = 5
    _connections: list[Any] = field(default_factory=list, init=False)
    _closed: bool = field(default=False, init=False)

    def acquire(self) -> Any:
        if self._closed:
            raise RuntimeError("pool is closed")
        if len(self._connections) < self.max_size:
            connection = self.factory.create_connection()
            self._connections.append(connection)
            return connection
        return self._connections[0]

    def release(self, connection: Any) -> None:
        if connection in self._connections:
            return

    def close(self) -> None:
        self._closed = True
        for connection in self._connections:
            close = getattr(connection, "close", None)
            if callable(close):
                close()
