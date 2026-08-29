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
    name: str | None = None
    email: str | None = None
    token: str | None = None


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

    @classmethod
    def from_safe_dict(cls, payload: dict[str, Any] | None) -> "ConfiguredSourceConfig":
        source_config_payload = payload or {}
        sql_payload = source_config_payload.get("sql_server") or {}
        folder_payload = source_config_payload.get("folder_watch") or {}
        curves_payload = source_config_payload.get("curves") or {}
        vector_payload = source_config_payload.get("vector") or {}
        bccr_payload = source_config_payload.get("bccr") or {}
        return cls(
            sql_server=SQLServerSourceConfig(
                enabled=bool(sql_payload.get("enabled", False)),
                server=sql_payload.get("server"),
                database=sql_payload.get("database"),
                authentication_mode=sql_payload.get("authentication_mode", "windows"),
                view=sql_payload.get("view", "VISTA_1514_1515_1516"),
                scenario_filters=tuple(sql_payload.get("scenario_filters", ())),
            ),
            folder_watch=FolderWatchSourceConfig(
                enabled=bool(folder_payload.get("enabled", False)),
                portfolio_root=folder_payload.get("portfolio_root"),
                icl_root=folder_payload.get("icl_root"),
                curves_path=folder_payload.get("curves_path"),
                vector_path=folder_payload.get("vector_path"),
                portfolio_master_pattern=folder_payload.get(
                    "portfolio_master_pattern", r"Inversiones\{year}\maestro\{month}\*.xls*"
                ),
                icl_file_pattern=folder_payload.get("icl_file_pattern", r"ICL\Reportes ICL\*"),
                supported_extensions=tuple(
                    folder_payload.get("supported_extensions", (".xls", ".xlsx"))
                ),
                recursive=bool(folder_payload.get("recursive", True)),
                stale_data_threshold_seconds=int(
                    folder_payload.get("stale_data_threshold_seconds", 3600)
                ),
            ),
            curves=CurvesSourceConfig(
                enabled=bool(curves_payload.get("enabled", False)),
                workbook=curves_payload.get("workbook"),
                sheet_mapping=tuple(curves_payload.get("sheet_mapping", ())),
                stale_data_threshold_seconds=int(
                    curves_payload.get("stale_data_threshold_seconds", 3600)
                ),
            ),
            vector=VectorSourceConfig(
                enabled=bool(vector_payload.get("enabled", False)),
                path=vector_payload.get("path"),
                root=vector_payload.get("root"),
                directory_aliases=tuple(vector_payload.get("directory_aliases", ())),
                file_pattern=vector_payload.get("file_pattern"),
                supported_extensions=tuple(
                    vector_payload.get("supported_extensions", (".txt", ".xls", ".xlsx"))
                ),
                stale_data_threshold_seconds=int(
                    vector_payload.get("stale_data_threshold_seconds", 3600)
                ),
            ),
            bccr=BCCRSourceConfig(
                enabled=bool(bccr_payload.get("enabled", False)),
                base_url=bccr_payload.get("base_url"),
                timeout_seconds=float(bccr_payload.get("timeout_seconds", 30.0)),
                retries=int(bccr_payload.get("retries", 3)),
                cache_enabled=bool(bccr_payload.get("cache_enabled", True)),
                indicator_configuration=tuple(bccr_payload.get("indicator_configuration", ("FX",))),
                series_config=tuple(bccr_payload.get("series_config", ())),
                name=bccr_payload.get("name"),
                email=bccr_payload.get("email"),
                token=bccr_payload.get("token"),
            ),
            diagnostic_mode=bool(source_config_payload.get("diagnostic_mode", False)),
            metadata={
                "allow_prior_source_date": bool(
                    source_config_payload.get("allow_prior_source_date", False)
                ),
                "data_cutoff_date": source_config_payload.get("data_cutoff_date"),
            },
        )
