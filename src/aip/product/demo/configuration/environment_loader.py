from __future__ import annotations

import ntpath
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

from aip.product.configured.configuration.configured_source_config import BCCRSourceConfig, ConfiguredSourceConfig, CurvesSourceConfig, FolderWatchSourceConfig, SQLServerSourceConfig, VectorSourceConfig
from aip.product.demo.configuration.demo_config import DemoConfig
from aip.product.demo.exceptions import DemoConfigurationError


def _normalize_path_value(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.startswith("\\\\") or len(normalized) >= 2 and normalized[1] == ":":
        return ntpath.normpath(normalized.replace("/", "\\"))
    return os.path.normpath(normalized)


def _first_existing_path(*candidates: Path) -> str | None:
    for candidate in candidates:
        try:
            if candidate.exists():
                return str(candidate)
        except OSError:
            continue
    return None


def _institutional_defaults() -> dict[str, str | None]:
    """Resolve stable non-secret institutional paths from the Windows profile."""
    home = Path.home()
    coopealianza = home / "COOPEALIANZA R.L"
    investment_root = coopealianza / "Seidy Fonseca Hernandez - inversiones"
    analytics_root = (
        coopealianza
        / "Liquidez e Inversiones - Documentos"
        / "General"
        / "Análisis Financiero"
    )
    cutoff_year = os.getenv("AIP_DATA_CUTOFF_DATE", "")[:4]
    if not cutoff_year.isdigit():
        cutoff_year = str(date.today().year)
    vector_root = investment_root / "Inversiones" / cutoff_year / "vector"
    return {
        "portfolio_root": _first_existing_path(investment_root),
        "icl_root": _first_existing_path(analytics_root),
        "vector_path": _first_existing_path(vector_root),
    }


def _infer_latest_master_date(portfolio_root: str | None) -> date | None:
    if not portfolio_root:
        return None
    root = Path(portfolio_root)
    if not root.exists():
        return None
    pattern = re.compile(r"(?P<day>\d{1,2})-(?P<month>\d{1,2})-(?P<year>\d{4})", re.IGNORECASE)
    latest: date | None = None
    try:
        candidates = root.rglob("*.xls*")
        for candidate in candidates:
            if "maestro" not in str(candidate.parent).lower():
                continue
            match = pattern.search(candidate.stem)
            if match is None:
                continue
            try:
                parsed = date(
                    int(match.group("year")),
                    int(match.group("month")),
                    int(match.group("day")),
                )
            except ValueError:
                continue
            if latest is None or parsed > latest:
                latest = parsed
    except OSError:
        return None
    return latest


def _parse_boolean_flag(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off", ""}:
        return False
    return default


class EnvironmentLoader:
    """Loads demo configuration from environment variables."""

    def load(self) -> DemoConfig:
        defaults = _institutional_defaults()
        execution_mode_value = os.getenv("AIP_EXECUTION_MODE") or os.getenv("AIP_DEMO_EXECUTION_MODE")
        if execution_mode_value is None:
            execution_mode = "CONFIGURED" if defaults["portfolio_root"] else "DEMO"
        else:
            execution_mode = execution_mode_value.upper()
        demo_mode_flag = os.getenv(
            "AIP_DEMO_MODE_ENABLED",
            "false" if execution_mode == "CONFIGURED" else "true",
        )
        demo_mode_enabled = demo_mode_flag.lower() == "true"
        configured_source_indicator = _parse_boolean_flag(os.getenv("AIP_CONFIGURED_DIAGNOSTIC_MODE"), default=False)
        configured_source_env_present = any(
            (os.getenv(env_name) or "").strip() not in {"", "false", "False", "FALSE"}
            for env_name in (
                "AIP_PORTFOLIO_ROOT",
                "AIP_VECTOR_PATH",
                "AIP_VECTOR_ROOT",
                "AIP_VECTOR_ENABLED",
                "AIP_FOLDERWATCH_ENABLED",
                "AIP_FOLDER_WATCH_ENABLED",
                "AIP_SQLSERVER_ENABLED",
                "AIP_SQL_CONNECTOR_ENABLED",
                "AIP_CURVES_ENABLED",
            )
        )
        if execution_mode not in {"DEMO", "CONFIGURED"}:
            raise DemoConfigurationError("invalid execution mode")
        if execution_mode == "DEMO" and (configured_source_indicator or configured_source_env_present):
            execution_mode = "CONFIGURED"
        if execution_mode == "DEMO":
            demo_mode_enabled = True
        environment_name = os.getenv("AIP_ENVIRONMENT") or os.getenv("AIP_DEMO_ENVIRONMENT", "demo")
        sql_source = self._read_sql_source_config()
        folder_source = self._read_folder_watch_config()
        inferred_cutoff = _infer_latest_master_date(folder_source["portfolio_root"])
        effective_cutoff = os.getenv("AIP_DATA_CUTOFF_DATE") or (
            inferred_cutoff.isoformat() if inferred_cutoff is not None else "2026-07-29"
        )
        curves_source = self._read_curves_config()
        vector_source = self._read_vector_config()
        bccr_source = self._read_bccr_config()
        configured_source_config = ConfiguredSourceConfig(
            sql_server=SQLServerSourceConfig(
                enabled=sql_source["enabled"],
                server=sql_source["server"],
                database=sql_source["database"],
                authentication_mode=sql_source["authentication_mode"],
                username_secret_ref=sql_source["username_secret_ref"],
                password_secret_ref=sql_source["password_secret_ref"],
                view=sql_source["view"],
                scenario_filters=sql_source["scenario_filters"],
                connection_timeout_seconds=sql_source["connection_timeout_seconds"],
                command_timeout_seconds=sql_source["command_timeout_seconds"],
                retry_count=sql_source["retry_count"],
                additional_query_filters=sql_source["additional_query_filters"],
            ),
            folder_watch=FolderWatchSourceConfig(
                enabled=folder_source["enabled"],
                portfolio_root=folder_source["portfolio_root"],
                icl_root=folder_source["icl_root"],
                curves_path=folder_source["curves_path"],
                vector_path=folder_source["vector_path"],
                portfolio_master_pattern=folder_source["portfolio_master_pattern"],
                icl_file_pattern=folder_source["icl_file_pattern"],
                supported_extensions=folder_source["supported_extensions"],
                recursive=folder_source["recursive"],
                stale_data_threshold_seconds=folder_source["stale_data_threshold_seconds"],
            ),
            curves=CurvesSourceConfig(
                enabled=curves_source["enabled"],
                workbook=curves_source["workbook"],
                sheet_mapping=curves_source["sheet_mapping"],
                stale_data_threshold_seconds=curves_source["stale_data_threshold_seconds"],
            ),
            vector=VectorSourceConfig(
                enabled=vector_source["enabled"],
                path=vector_source["path"],
                root=vector_source["root"],
                directory_aliases=vector_source["directory_aliases"],
                file_pattern=vector_source["file_pattern"],
                supported_extensions=vector_source["supported_extensions"],
                stale_data_threshold_seconds=vector_source["stale_data_threshold_seconds"],
            ),
            bccr=BCCRSourceConfig(
                enabled=bccr_source["enabled"],
                base_url=bccr_source["base_url"],
                timeout_seconds=bccr_source["timeout_seconds"],
                retries=bccr_source["retries"],
                cache_enabled=bccr_source["cache_enabled"],
                indicator_configuration=bccr_source["indicator_configuration"],
                series_config=bccr_source["series_config"],
                name=bccr_source["name"],
                email=bccr_source["email"],
                token=bccr_source["token"],
            ),
            diagnostic_mode=_parse_boolean_flag(os.getenv("AIP_CONFIGURED_DIAGNOSTIC_MODE"), default=False),
            metadata={
                "allow_prior_source_date": _parse_boolean_flag(os.getenv("AIP_ALLOW_PRIOR_SOURCE_DATE"), default=True),
                "data_cutoff_date": effective_cutoff,
            },
        )
        return DemoConfig(
            environment_name=environment_name,
            execution_mode=execution_mode,
            demo_mode_enabled=demo_mode_enabled,
            sql_connector_enabled=sql_source["enabled"],
            folder_watch_enabled=folder_source["enabled"],
            bccr_enabled=bccr_source["enabled"],
            scheduler_enabled=os.getenv("AIP_SCHEDULER_ENABLED", "true").lower() == "true",
            notifications_enabled=os.getenv("AIP_NOTIFICATIONS_ENABLED", "true").lower() == "true",
            startup_timeout_seconds=int(os.getenv("AIP_STARTUP_TIMEOUT_SECONDS", "30")),
            refresh_timeout_seconds=int(os.getenv("AIP_REFRESH_TIMEOUT_SECONDS", "30")),
            default_theme=os.getenv("AIP_DEFAULT_THEME", "light"),
            default_workspace=os.getenv("AIP_DEFAULT_WORKSPACE", "executive"),
            data_cutoff_date=date.fromisoformat(effective_cutoff),
            source_config=configured_source_config.to_safe_dict(),
            observability={"level": os.getenv("AIP_OBSERVABILITY_LEVEL", "INFO")},
            feature_flags={"demo_badge": True},
        )

    def load_source_config(self) -> ConfiguredSourceConfig:
        """Carga la configuración runtime completa de fuentes.

        A diferencia de DemoConfig.source_config, este objeto puede contener
        secretos runtime y no debe serializarse en logs, UI o diagnósticos.
        """
        sql_source = self._read_sql_source_config()
        folder_source = self._read_folder_watch_config()
        inferred_cutoff = _infer_latest_master_date(folder_source["portfolio_root"])
        effective_cutoff = os.getenv("AIP_DATA_CUTOFF_DATE") or (
            inferred_cutoff.isoformat() if inferred_cutoff is not None else "2026-07-29"
        )
        curves_source = self._read_curves_config()
        vector_source = self._read_vector_config()
        bccr_source = self._read_bccr_config()

        return ConfiguredSourceConfig(
            sql_server=SQLServerSourceConfig(
                enabled=sql_source["enabled"],
                server=sql_source["server"],
                database=sql_source["database"],
                authentication_mode=sql_source["authentication_mode"],
                username_secret_ref=sql_source["username_secret_ref"],
                password_secret_ref=sql_source["password_secret_ref"],
                view=sql_source["view"],
                scenario_filters=sql_source["scenario_filters"],
                connection_timeout_seconds=sql_source["connection_timeout_seconds"],
                command_timeout_seconds=sql_source["command_timeout_seconds"],
                retry_count=sql_source["retry_count"],
                additional_query_filters=sql_source["additional_query_filters"],
            ),
            folder_watch=FolderWatchSourceConfig(
                enabled=folder_source["enabled"],
                portfolio_root=folder_source["portfolio_root"],
                icl_root=folder_source["icl_root"],
                curves_path=folder_source["curves_path"],
                vector_path=folder_source["vector_path"],
                portfolio_master_pattern=folder_source["portfolio_master_pattern"],
                icl_file_pattern=folder_source["icl_file_pattern"],
                supported_extensions=folder_source["supported_extensions"],
                recursive=folder_source["recursive"],
                stale_data_threshold_seconds=folder_source["stale_data_threshold_seconds"],
            ),
            curves=CurvesSourceConfig(
                enabled=curves_source["enabled"],
                workbook=curves_source["workbook"],
                sheet_mapping=curves_source["sheet_mapping"],
                stale_data_threshold_seconds=curves_source["stale_data_threshold_seconds"],
            ),
            vector=VectorSourceConfig(
                enabled=vector_source["enabled"],
                path=vector_source["path"],
                root=vector_source["root"],
                directory_aliases=vector_source["directory_aliases"],
                file_pattern=vector_source["file_pattern"],
                supported_extensions=vector_source["supported_extensions"],
                stale_data_threshold_seconds=vector_source["stale_data_threshold_seconds"],
            ),
            bccr=BCCRSourceConfig(
                enabled=bccr_source["enabled"],
                base_url=bccr_source["base_url"],
                timeout_seconds=bccr_source["timeout_seconds"],
                retries=bccr_source["retries"],
                cache_enabled=bccr_source["cache_enabled"],
                indicator_configuration=bccr_source["indicator_configuration"],
                series_config=bccr_source["series_config"],
                name=bccr_source["name"],
                email=bccr_source["email"],
                token=bccr_source["token"],
            ),
            diagnostic_mode=_parse_boolean_flag(
                os.getenv("AIP_CONFIGURED_DIAGNOSTIC_MODE"),
                default=False,
            ),
            metadata={
                "allow_prior_source_date": _parse_boolean_flag(
                    os.getenv("AIP_ALLOW_PRIOR_SOURCE_DATE"),
                    default=True,
                ),
                "data_cutoff_date": effective_cutoff,
            },
        )

    def _read_sql_source_config(self) -> dict[str, Any]:
        enabled_flag = os.getenv("AIP_SQLSERVER_ENABLED") or os.getenv("AIP_SQL_CONNECTOR_ENABLED", "false")
        return {
            "enabled": str(enabled_flag).lower() == "true",
            "server": os.getenv("AIP_SQLSERVER_SERVER"),
            "database": os.getenv("AIP_SQLSERVER_DATABASE"),
            "authentication_mode": os.getenv("AIP_SQLSERVER_AUTH_MODE", "windows"),
            "username_secret_ref": os.getenv("AIP_SQLSERVER_USERNAME_SECRET"),
            "password_secret_ref": os.getenv("AIP_SQLSERVER_PASSWORD_SECRET"),
            "view": os.getenv("AIP_SQLSERVER_VIEW", "VISTA_1514_1515_1516"),
            "scenario_filters": tuple(filter(None, os.getenv("AIP_SQLSERVER_SCENARIOS", "Reales,Presupuesto 2026%").split(","))),
            "connection_timeout_seconds": int(os.getenv("AIP_SQLSERVER_CONNECTION_TIMEOUT", "30")),
            "command_timeout_seconds": int(os.getenv("AIP_SQLSERVER_COMMAND_TIMEOUT", "30")),
            "retry_count": int(os.getenv("AIP_SQLSERVER_RETRIES", "3")),
            "additional_query_filters": tuple(filter(None, os.getenv("AIP_SQLSERVER_QUERY_FILTERS", "").split(","))),
        }

    def _read_folder_watch_config(self) -> dict[str, Any]:
        defaults = _institutional_defaults()
        portfolio_root = os.getenv("AIP_PORTFOLIO_ROOT") or defaults["portfolio_root"]
        icl_root = os.getenv("AIP_ICL_ROOT") or defaults["icl_root"]
        vector_path = os.getenv("AIP_VECTOR_PATH") or defaults["vector_path"]
        enabled_flag = (
            os.getenv("AIP_FOLDERWATCH_ENABLED")
            or os.getenv("AIP_FOLDER_WATCH_ENABLED")
            or ("true" if portfolio_root else "false")
        )
        return {
            "enabled": str(enabled_flag).lower() == "true",
            "portfolio_root": _normalize_path_value(portfolio_root),
            "icl_root": _normalize_path_value(icl_root),
            "curves_path": _normalize_path_value(os.getenv("AIP_CURVES_WORKBOOK")),
            "vector_path": _normalize_path_value(vector_path),
            "portfolio_master_pattern": os.getenv("AIP_PORTFOLIO_MASTER_PATTERN", r"Inversiones\{year}\maestro\{month}\*.xls*"),
            "icl_file_pattern": os.getenv("AIP_ICL_FILE_PATTERN", r"ICL\Reportes ICL\*"),
            "supported_extensions": tuple(filter(None, os.getenv("AIP_PORTFOLIO_SUPPORTED_EXTENSIONS", ".xls,.xlsx").split(","))),
            "recursive": os.getenv("AIP_PORTFOLIO_RECURSIVE", "true").lower() == "true",
            "stale_data_threshold_seconds": int(os.getenv("AIP_PORTFOLIO_STALE_HOURS", "24")) * 3600,
        }

    def _read_curves_config(self) -> dict[str, Any]:
        enabled_flag = os.getenv("AIP_CURVES_ENABLED", "false")
        return {
            "enabled": str(enabled_flag).lower() == "true",
            "workbook": _normalize_path_value(os.getenv("AIP_CURVES_WORKBOOK")),
            "sheet_mapping": tuple(filter(None, os.getenv("AIP_CURVES_SHEET_MAPPING", "Gobierno CRC,Gobierno USD,BCCR CRC").split(","))),
            "stale_data_threshold_seconds": int(os.getenv("AIP_CURVES_STALE_HOURS", "24")) * 3600,
        }

    def _read_vector_config(self) -> dict[str, Any]:
        defaults = _institutional_defaults()
        vector_path = os.getenv("AIP_VECTOR_PATH") or defaults["vector_path"]
        enabled_flag = os.getenv(
            "AIP_VECTOR_ENABLED",
            "true" if vector_path else "false",
        )
        return {
            "enabled": str(enabled_flag).lower() == "true",
            "path": _normalize_path_value(vector_path),
            "root": _normalize_path_value(os.getenv("AIP_VECTOR_ROOT")),
            "directory_aliases": tuple(filter(None, os.getenv("AIP_VECTOR_DIRECTORY_ALIASES", "vector,Vector,Vector Pip,vector pipca").split(","))),
            "file_pattern": os.getenv("AIP_VECTOR_FILE_PATTERNS") or os.getenv("AIP_VECTOR_FILE_PATTERN", "VectorPiPCA_{yyyymmdd}.txt"),
            "supported_extensions": tuple(filter(None, os.getenv("AIP_VECTOR_SUPPORTED_EXTENSIONS", ".txt,.xls,.xlsx").split(","))),
            "stale_data_threshold_seconds": int(os.getenv("AIP_VECTOR_STALE_HOURS", "24")) * 3600,
        }

    def _read_bccr_config(self) -> dict[str, Any]:
        enabled_flag = os.getenv("AIP_BCCR_ENABLED", "true")
        return {
            "enabled": str(enabled_flag).lower() == "true",
            "base_url": os.getenv("AIP_BCCR_BASE_URL", "https://apim.bccr.fi.cr"),
            "timeout_seconds": float(os.getenv("AIP_BCCR_TIMEOUT_SECONDS", "30")),
            "retries": int(os.getenv("AIP_BCCR_RETRIES", "3")),
            "cache_enabled": os.getenv("AIP_BCCR_CACHE_ENABLED", "true").lower() == "true",
            "indicator_configuration": tuple(filter(None, os.getenv("AIP_BCCR_SERIES_CONFIG", "FX").split(","))),
            "series_config": tuple(filter(None, os.getenv("AIP_BCCR_SERIES_CONFIG", "FX").split(","))),
            "name": os.getenv("AIP_BCCR_NAME"),
            "email": os.getenv("AIP_BCCR_EMAIL"),
            "token": os.getenv("AIP_BCCR_TOKEN"),
        }
