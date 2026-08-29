from __future__ import annotations

import ntpath
import os
import re
from datetime import date
from pathlib import Path

from aip.product.configured.configuration.configured_source_config import (
    BCCRSourceConfig,
    ConfiguredSourceConfig,
    CurvesSourceConfig,
    FolderWatchSourceConfig,
    SQLServerSourceConfig,
    VectorSourceConfig,
)
from aip.product.demo.configuration.demo_config import DemoConfig
from aip.product.demo.exceptions import DemoConfigurationError


def _normalize_path_value(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.startswith("\\\\") or (len(normalized) >= 2 and normalized[1] == ":"):
        return ntpath.normpath(normalized.replace("/", "\\"))
    return os.path.normpath(normalized)


def _parse_boolean_flag(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off", ""}:
        return False
    return default


def _first_existing_path(*candidates: Path) -> str | None:
    for candidate in candidates:
        try:
            if candidate.exists():
                return str(candidate)
        except OSError:
            continue
    return None


def _institutional_defaults() -> dict[str, str | None]:
    """Resolve stable, non-secret institutional locations for the current Windows profile."""
    home = Path.home()
    coopealianza = home / "COOPEALIANZA R.L"
    investment_root = coopealianza / "Seidy Fonseca Hernandez - inversiones"
    analytics_root = (
        coopealianza
        / "Liquidez e Inversiones - Documentos"
        / "General"
        / "Análisis Financiero"
    )
    cutoff_env = (os.getenv("AIP_DATA_CUTOFF_DATE") or "").strip()
    year = cutoff_env[:4] if len(cutoff_env) >= 4 and cutoff_env[:4].isdigit() else str(date.today().year)
    vector_root = investment_root / "Inversiones" / year / "vector"
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
    filename_date = re.compile(r"(?P<day>\d{1,2})-(?P<month>\d{1,2})-(?P<year>\d{4})")
    latest: date | None = None
    try:
        for candidate in root.rglob("*.xls*"):
            if "maestro" not in str(candidate.parent).lower():
                continue
            match = filename_date.search(candidate.stem)
            if match is None:
                continue
            try:
                parsed = date(int(match.group("year")), int(match.group("month")), int(match.group("day")))
            except ValueError:
                continue
            if latest is None or parsed > latest:
                latest = parsed
    except OSError:
        return latest
    return latest


class EnvironmentLoader:
    """Load institutional runtime configuration without persisting secrets."""

    def _effective_cutoff(self, portfolio_root: str | None) -> date:
        explicit = (os.getenv("AIP_DATA_CUTOFF_DATE") or "").strip()
        if explicit:
            try:
                return date.fromisoformat(explicit)
            except ValueError as exc:
                raise DemoConfigurationError("AIP_DATA_CUTOFF_DATE must be YYYY-MM-DD") from exc
        inferred = _infer_latest_master_date(portfolio_root)
        if inferred is not None:
            return inferred
        return date.today()

    def load(self) -> DemoConfig:
        source = self.load_source_config()
        defaults = _institutional_defaults()
        execution_env = os.getenv("AIP_EXECUTION_MODE") or os.getenv("AIP_DEMO_EXECUTION_MODE")
        execution_mode = execution_env.upper() if execution_env else ("CONFIGURED" if defaults["portfolio_root"] else "DEMO")
        if execution_mode not in {"DEMO", "CONFIGURED"}:
            raise DemoConfigurationError("invalid execution mode")
        if execution_mode == "DEMO" and (
            source.folder_watch.enabled or source.vector.enabled or source.sql_server.enabled or source.curves.enabled
        ):
            execution_mode = "CONFIGURED"
        demo_enabled = _parse_boolean_flag(
            os.getenv("AIP_DEMO_MODE_ENABLED"),
            default=execution_mode == "DEMO",
        )
        if execution_mode == "DEMO":
            demo_enabled = True
        cutoff = self._effective_cutoff(source.folder_watch.portfolio_root)
        return DemoConfig(
            environment_name=os.getenv("AIP_ENVIRONMENT") or os.getenv("AIP_DEMO_ENVIRONMENT", "configured" if execution_mode == "CONFIGURED" else "demo"),
            execution_mode=execution_mode,
            demo_mode_enabled=demo_enabled,
            sql_connector_enabled=source.sql_server.enabled,
            folder_watch_enabled=source.folder_watch.enabled,
            bccr_enabled=source.bccr.enabled,
            scheduler_enabled=_parse_boolean_flag(os.getenv("AIP_SCHEDULER_ENABLED"), default=True),
            notifications_enabled=_parse_boolean_flag(os.getenv("AIP_NOTIFICATIONS_ENABLED"), default=True),
            startup_timeout_seconds=int(os.getenv("AIP_STARTUP_TIMEOUT_SECONDS", "30")),
            refresh_timeout_seconds=int(os.getenv("AIP_REFRESH_TIMEOUT_SECONDS", "30")),
            default_theme=os.getenv("AIP_DEFAULT_THEME", "light"),
            default_workspace=os.getenv("AIP_DEFAULT_WORKSPACE", "executive"),
            data_cutoff_date=cutoff,
            source_config=source.to_safe_dict(),
            observability={"level": os.getenv("AIP_OBSERVABILITY_LEVEL", "INFO")},
            feature_flags={"demo_badge": execution_mode == "DEMO"},
        )

    def load_source_config(self) -> ConfiguredSourceConfig:
        defaults = _institutional_defaults()
        portfolio_root = _normalize_path_value(os.getenv("AIP_PORTFOLIO_ROOT") or defaults["portfolio_root"])
        icl_root = _normalize_path_value(os.getenv("AIP_ICL_ROOT") or defaults["icl_root"])
        vector_path = _normalize_path_value(os.getenv("AIP_VECTOR_PATH") or defaults["vector_path"])

        folder_enabled = _parse_boolean_flag(
            os.getenv("AIP_FOLDERWATCH_ENABLED") or os.getenv("AIP_FOLDER_WATCH_ENABLED"),
            default=bool(portfolio_root),
        )
        vector_enabled = _parse_boolean_flag(os.getenv("AIP_VECTOR_ENABLED"), default=bool(vector_path))
        sql_enabled = _parse_boolean_flag(os.getenv("AIP_SQLSERVER_ENABLED") or os.getenv("AIP_SQL_CONNECTOR_ENABLED"), default=False)
        curves_workbook = _normalize_path_value(os.getenv("AIP_CURVES_WORKBOOK"))
        curves_enabled = _parse_boolean_flag(os.getenv("AIP_CURVES_ENABLED"), default=bool(curves_workbook))
        bccr_enabled = _parse_boolean_flag(os.getenv("AIP_BCCR_ENABLED"), default=True)
        cutoff = self._effective_cutoff(portfolio_root)

        return ConfiguredSourceConfig(
            sql_server=SQLServerSourceConfig(
                enabled=sql_enabled,
                server=os.getenv("AIP_SQLSERVER_SERVER"),
                database=os.getenv("AIP_SQLSERVER_DATABASE"),
                authentication_mode=os.getenv("AIP_SQLSERVER_AUTH_MODE", "windows"),
                username_secret_ref=os.getenv("AIP_SQLSERVER_USERNAME_SECRET"),
                password_secret_ref=os.getenv("AIP_SQLSERVER_PASSWORD_SECRET"),
                view=os.getenv("AIP_SQLSERVER_VIEW", "VISTA_1514_1515_1516"),
                scenario_filters=tuple(filter(None, os.getenv("AIP_SQLSERVER_SCENARIOS", "Reales,Presupuesto 2026%").split(","))),
                connection_timeout_seconds=int(os.getenv("AIP_SQLSERVER_CONNECTION_TIMEOUT", "30")),
                command_timeout_seconds=int(os.getenv("AIP_SQLSERVER_COMMAND_TIMEOUT", "30")),
                retry_count=int(os.getenv("AIP_SQLSERVER_RETRIES", "3")),
                additional_query_filters=tuple(filter(None, os.getenv("AIP_SQLSERVER_QUERY_FILTERS", "").split(","))),
            ),
            folder_watch=FolderWatchSourceConfig(
                enabled=folder_enabled,
                portfolio_root=portfolio_root,
                icl_root=icl_root,
                curves_path=curves_workbook,
                vector_path=vector_path,
                portfolio_master_pattern=os.getenv("AIP_PORTFOLIO_MASTER_PATTERN", r"Inversiones\{year}\maestro\{month}\*.xls*"),
                icl_file_pattern=os.getenv("AIP_ICL_FILE_PATTERN", r"ICL\Reportes ICL\*"),
                supported_extensions=tuple(filter(None, os.getenv("AIP_PORTFOLIO_SUPPORTED_EXTENSIONS", ".xls,.xlsx").split(","))),
                recursive=_parse_boolean_flag(os.getenv("AIP_PORTFOLIO_RECURSIVE"), default=True),
                stale_data_threshold_seconds=int(os.getenv("AIP_PORTFOLIO_STALE_HOURS", "24")) * 3600,
            ),
            curves=CurvesSourceConfig(
                enabled=curves_enabled,
                workbook=curves_workbook,
                sheet_mapping=tuple(filter(None, os.getenv("AIP_CURVES_SHEET_MAPPING", "Gobierno CRC,Gobierno USD,BCCR CRC").split(","))),
                stale_data_threshold_seconds=int(os.getenv("AIP_CURVES_STALE_HOURS", "24")) * 3600,
            ),
            vector=VectorSourceConfig(
                enabled=vector_enabled,
                path=vector_path,
                root=_normalize_path_value(os.getenv("AIP_VECTOR_ROOT")),
                directory_aliases=tuple(filter(None, os.getenv("AIP_VECTOR_DIRECTORY_ALIASES", "vector,Vector,Vector Pip,vector pipca").split(","))),
                file_pattern=os.getenv("AIP_VECTOR_FILE_PATTERNS") or os.getenv("AIP_VECTOR_FILE_PATTERN", "VectorPiPCA_{yyyymmdd}.txt"),
                supported_extensions=tuple(filter(None, os.getenv("AIP_VECTOR_SUPPORTED_EXTENSIONS", ".txt,.xls,.xlsx").split(","))),
                stale_data_threshold_seconds=int(os.getenv("AIP_VECTOR_STALE_HOURS", "24")) * 3600,
            ),
            bccr=BCCRSourceConfig(
                enabled=bccr_enabled,
                base_url=os.getenv("AIP_BCCR_BASE_URL", "https://apim.bccr.fi.cr"),
                timeout_seconds=float(os.getenv("AIP_BCCR_TIMEOUT_SECONDS", "30")),
                retries=int(os.getenv("AIP_BCCR_RETRIES", "3")),
                cache_enabled=_parse_boolean_flag(os.getenv("AIP_BCCR_CACHE_ENABLED"), default=True),
                indicator_configuration=tuple(filter(None, os.getenv("AIP_BCCR_SERIES_CONFIG", "FX").split(","))),
                series_config=tuple(filter(None, os.getenv("AIP_BCCR_SERIES_CONFIG", "FX").split(","))),
                name=os.getenv("AIP_BCCR_NAME"),
                email=os.getenv("AIP_BCCR_EMAIL"),
                token=os.getenv("AIP_BCCR_TOKEN"),
            ),
            diagnostic_mode=_parse_boolean_flag(os.getenv("AIP_CONFIGURED_DIAGNOSTIC_MODE"), default=False),
            metadata={
                "allow_prior_source_date": _parse_boolean_flag(os.getenv("AIP_ALLOW_PRIOR_SOURCE_DATE"), default=True),
                "data_cutoff_date": cutoff.isoformat(),
            },
        )
