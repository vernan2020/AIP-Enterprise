from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SQLServerSourceConfig:
    enabled: bool = False
    server: str | None = None
    database: str | None = None
    authentication_mode: str = "windows"
    username_secret_ref: str | None = None
    password_secret_ref: str | None = None
    view: str = "VISTA_1514_1515_1516"
    scenario_filters: tuple[str, ...] = ("Reales", "Presupuesto 2026%")
    connection_timeout_seconds: int = 30
    command_timeout_seconds: int = 30
    retry_count: int = 3
    additional_query_filters: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FolderWatchSourceConfig:
    enabled: bool = False
    portfolio_root: str | None = None
    icl_root: str | None = None
    curves_path: str | None = None
    vector_path: str | None = None
    portfolio_master_pattern: str = r"Inversiones\{year}\maestro\{month}\*.xls*"
    icl_file_pattern: str = r"ICL\Reportes ICL\*"
    supported_extensions: tuple[str, ...] = (".xls", ".xlsx")
    recursive: bool = True
    stale_data_threshold_seconds: int = 3600


@dataclass(frozen=True, slots=True)
class CurvesSourceConfig:
    enabled: bool = False
    workbook: str | None = None
    sheet_mapping: tuple[str, ...] = ("Gobierno CRC", "Gobierno USD", "BCCR CRC")
    stale_data_threshold_seconds: int = 3600


@dataclass(frozen=True, slots=True)
class VectorSourceConfig:
    enabled: bool = False
    path: str | None = None
    root: str | None = None
    directory_aliases: tuple[str, ...] = ("vector", "Vector", "Vector Pip", "vector pipca")
    file_pattern: str | None = None
    supported_extensions: tuple[str, ...] = (".xls", ".xlsx")
    stale_data_threshold_seconds: int = 3600


@dataclass(frozen=True, slots=True)
class BCCRSourceConfig:
    enabled: bool = False
    base_url: str | None = None
    timeout_seconds: float = 30.0
    retries: int = 3
    cache_enabled: bool = True
    indicator_configuration: tuple[str, ...] = ("FX",)
    series_config: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ConfiguredSourceConfig:
    sql_server: SQLServerSourceConfig = field(default_factory=SQLServerSourceConfig)
    folder_watch: FolderWatchSourceConfig = field(default_factory=FolderWatchSourceConfig)
    curves: CurvesSourceConfig = field(default_factory=CurvesSourceConfig)
    vector: VectorSourceConfig = field(default_factory=VectorSourceConfig)
    bccr: BCCRSourceConfig = field(default_factory=BCCRSourceConfig)
    diagnostic_mode: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def resolve_diagnostic_mode(self) -> bool:
        if "diagnostic_mode" in self.metadata:
            value = self.metadata.get("diagnostic_mode")
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"true", "1", "yes", "on"}:
                    return True
                if normalized in {"false", "0", "no", "off", ""}:
                    return False
            if isinstance(value, (int, float)):
                return bool(value)
            return False
        if self.diagnostic_mode is not None:
            return bool(self.diagnostic_mode)
        return False

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "sql_server": {
                "enabled": self.sql_server.enabled,
                "server": self.sql_server.server,
                "database": self.sql_server.database,
                "authentication_mode": self.sql_server.authentication_mode,
                "view": self.sql_server.view,
                "scenario_filters": list(self.sql_server.scenario_filters),
            },
            "folder_watch": {
                "enabled": self.folder_watch.enabled,
                "portfolio_root": self.folder_watch.portfolio_root,
                "icl_root": self.folder_watch.icl_root,
                "portfolio_master_pattern": self.folder_watch.portfolio_master_pattern,
                "icl_file_pattern": self.folder_watch.icl_file_pattern,
            },
            "curves": {
                "enabled": self.curves.enabled,
                "workbook": self.curves.workbook,
                "sheet_mapping": list(self.curves.sheet_mapping),
            },
            "vector": {
                "enabled": self.vector.enabled,
                "path": self.vector.path,
                "root": self.vector.root,
                "directory_aliases": list(self.vector.directory_aliases),
                "file_pattern": self.vector.file_pattern,
                "supported_extensions": list(self.vector.supported_extensions),
            },
            "bccr": {
                "enabled": self.bccr.enabled,
                "base_url": self.bccr.base_url,
                "timeout_seconds": self.bccr.timeout_seconds,
                "retries": self.bccr.retries,
                "cache_enabled": self.bccr.cache_enabled,
            },
            "diagnostic_mode": self.resolve_diagnostic_mode(),
        }
