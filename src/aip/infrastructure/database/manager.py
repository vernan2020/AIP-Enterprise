from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from aip.infrastructure.configuration.models import DatabaseSettings


class DatabaseManager:
    def __init__(self, settings: DatabaseSettings, project_root: Path) -> None:
        self._settings = settings
        self._path = settings.path if settings.path.is_absolute() else project_root / settings.path
        self._connection: duckdb.DuckDBPyConnection | None = None

    @property
    def path(self) -> Path:
        return self._path

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        if self._connection is None:
            raise RuntimeError("La base de datos no está inicializada.")
        return self._connection

    def initialize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = duckdb.connect(database=str(self._path), read_only=self._settings.read_only)
        self._create_schema()

    def _create_schema(self) -> None:
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS system_metadata (
                key VARCHAR PRIMARY KEY,
                value VARCHAR NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.connection.execute("""
            INSERT INTO system_metadata(key, value)
            VALUES ('schema_version', '0.1.0')
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = now()
        """)

    def scalar(self, query: str, parameters: list[Any] | None = None) -> Any:
        row = self.connection.execute(query, parameters or []).fetchone()
        return None if row is None else row[0]

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None
