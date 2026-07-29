from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol


class SQLServerDriverAdapter(ABC):
    """Boundary for a production SQL Server driver implementation."""

    @abstractmethod
    def connect(self, connection_string: str) -> Any:
        ...

    @abstractmethod
    def execute(self, connection: Any, query: str, params: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], Any]:
        ...


class DriverProtocol(Protocol):
    def connect(self, connection_string: str) -> Any: ...

    def execute(self, connection: Any, query: str, params: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], Any]: ...


class PyOdbcDriverAdapter(SQLServerDriverAdapter):
    """Adapter that can be backed by pyodbc when available."""

    def __init__(self, module: Any | None = None) -> None:
        self._module = module

    def connect(self, connection_string: str) -> Any:
        if self._module is None:
            raise RuntimeError("pyodbc driver is not available")
        return self._module.connect(connection_string)

    def execute(self, connection: Any, query: str, params: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], Any]:
        if self._module is None:
            raise RuntimeError("pyodbc driver is not available")

        cursor = connection.cursor() if hasattr(connection, "cursor") else None
        if cursor is None:
            raise RuntimeError("driver connection does not expose a cursor")

        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        rows = cursor.fetchall() if hasattr(cursor, "fetchall") else []
        return rows, cursor
