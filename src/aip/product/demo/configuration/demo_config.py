from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from aip.product.demo.exceptions import DemoConfigurationError


@dataclass(frozen=True, slots=True)
class DemoConfig:
    """Typed configuration for the demo product slice."""

    environment_name: str = "demo"
    execution_mode: str = "DEMO"
    demo_mode_enabled: bool = True
    sql_connector_enabled: bool = False
    folder_watch_enabled: bool = False
    bccr_enabled: bool = False
    scheduler_enabled: bool = True
    notifications_enabled: bool = True
    startup_timeout_seconds: int = 30
    refresh_timeout_seconds: int = 30
    default_theme: str = "light"
    default_workspace: str = "executive"
    data_cutoff_date: date = field(default_factory=lambda: date(2026, 7, 29))
    source_config: dict[str, Any] = field(default_factory=dict)
    observability: dict[str, Any] = field(default_factory=lambda: {"level": "INFO"})
    feature_flags: dict[str, bool] = field(default_factory=lambda: {"demo_badge": True})

    def __post_init__(self) -> None:
        if self.execution_mode not in {"DEMO", "CONFIGURED"}:
            raise DemoConfigurationError("execution_mode must be DEMO or CONFIGURED")
        if not self.environment_name.strip():
            raise DemoConfigurationError("environment_name is required")

    def safe_representation(self) -> dict[str, Any]:
        return {
            "environment_name": self.environment_name,
            "execution_mode": self.execution_mode,
            "demo_mode_enabled": self.demo_mode_enabled,
            "sql_connector_enabled": self.sql_connector_enabled,
            "folder_watch_enabled": self.folder_watch_enabled,
            "bccr_enabled": self.bccr_enabled,
            "scheduler_enabled": self.scheduler_enabled,
            "notifications_enabled": self.notifications_enabled,
            "startup_timeout_seconds": self.startup_timeout_seconds,
            "refresh_timeout_seconds": self.refresh_timeout_seconds,
            "default_theme": self.default_theme,
            "default_workspace": self.default_workspace,
            "data_cutoff_date": self.data_cutoff_date.isoformat(),
            "source_config": dict(self.source_config),
            "observability": dict(self.observability),
            "feature_flags": dict(self.feature_flags),
        }
