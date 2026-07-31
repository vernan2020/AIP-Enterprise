from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SQLServerSourceConfig:
    enabled: bool = False
    server: str | None = None
    database: str | None = None
    authentication_mode: str = "integrated"
    username_secret_ref: str | None = None
    password_secret_ref: str | None = None
    query_ref: str | None = None
    connection_timeout_seconds: int = 30
    command_timeout_seconds: int = 30
    retry_count: int = 1


@dataclass(frozen=True, slots=True)
class FolderWatchSourceConfig:
    enabled: bool = False
    portfolio_root: str | None = None
    icl_root: str | None = None
    curves_path: str | None = None
    vector_path: str | None = None
    supported_extensions: tuple[str, ...] = (".csv", ".json")
    recursive: bool = True
    stale_data_threshold_seconds: int = 3600


@dataclass(frozen=True, slots=True)
class BCCRSourceConfig:
    enabled: bool = False
    base_url: str | None = None
    timeout_seconds: float = 10.0
    retries: int = 2
    cache_enabled: bool = True
    indicator_configuration: tuple[str, ...] = ("FX",)


@dataclass(frozen=True, slots=True)
class ConfiguredSourceConfig:
    sql_server: SQLServerSourceConfig = field(default_factory=SQLServerSourceConfig)
    folder_watch: FolderWatchSourceConfig = field(default_factory=FolderWatchSourceConfig)
    bccr: BCCRSourceConfig = field(default_factory=BCCRSourceConfig)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "sql_server": {
                "enabled": self.sql_server.enabled,
                "server": self.sql_server.server,
                "database": self.sql_server.database,
                "authentication_mode": self.sql_server.authentication_mode,
            },
            "folder_watch": {
                "enabled": self.folder_watch.enabled,
                "portfolio_root": self.folder_watch.portfolio_root,
                "icl_root": self.folder_watch.icl_root,
            },
            "bccr": {
                "enabled": self.bccr.enabled,
                "base_url": self.bccr.base_url,
                "timeout_seconds": self.bccr.timeout_seconds,
                "retries": self.bccr.retries,
            },
        }
