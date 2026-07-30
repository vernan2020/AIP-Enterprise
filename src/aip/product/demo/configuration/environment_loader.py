from __future__ import annotations

import os
from datetime import date
from typing import Any

from aip.product.demo.configuration.demo_config import DemoConfig
from aip.product.demo.exceptions import DemoConfigurationError


class EnvironmentLoader:
    """Loads demo configuration from environment variables."""

    def load(self) -> DemoConfig:
        execution_mode = os.getenv("AIP_DEMO_EXECUTION_MODE", "DEMO").upper()
        demo_mode_enabled = os.getenv("AIP_DEMO_MODE_ENABLED", "true").lower() == "true"
        if execution_mode not in {"DEMO", "CONFIGURED"}:
            raise DemoConfigurationError("invalid execution mode")
        return DemoConfig(
            environment_name=os.getenv("AIP_DEMO_ENVIRONMENT", "demo"),
            execution_mode=execution_mode,
            demo_mode_enabled=demo_mode_enabled,
            sql_connector_enabled=os.getenv("AIP_SQL_CONNECTOR_ENABLED", "false").lower() == "true",
            folder_watch_enabled=os.getenv("AIP_FOLDER_WATCH_ENABLED", "false").lower() == "true",
            bccr_enabled=os.getenv("AIP_BCCR_ENABLED", "false").lower() == "true",
            scheduler_enabled=os.getenv("AIP_SCHEDULER_ENABLED", "true").lower() == "true",
            notifications_enabled=os.getenv("AIP_NOTIFICATIONS_ENABLED", "true").lower() == "true",
            startup_timeout_seconds=int(os.getenv("AIP_STARTUP_TIMEOUT_SECONDS", "30")),
            refresh_timeout_seconds=int(os.getenv("AIP_REFRESH_TIMEOUT_SECONDS", "30")),
            default_theme=os.getenv("AIP_DEFAULT_THEME", "light"),
            default_workspace=os.getenv("AIP_DEFAULT_WORKSPACE", "executive"),
            data_cutoff_date=date.fromisoformat(os.getenv("AIP_DATA_CUTOFF_DATE", "2026-07-29")),
            source_config={
                "sql_server": os.getenv("AIP_SQL_SERVER", "demo"),
                "folder_watch": os.getenv("AIP_FOLDER_WATCH_PATH", "./demo-data"),
                "bccr": os.getenv("AIP_BCCR_SOURCE", "demo"),
            },
            observability={"level": os.getenv("AIP_OBSERVABILITY_LEVEL", "INFO")},
            feature_flags={"demo_badge": True},
        )
