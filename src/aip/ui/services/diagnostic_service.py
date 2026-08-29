from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aip.core.version import APP_NAME, APP_RELEASE, APP_VERSION
from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory


@dataclass(slots=True)
class DiagnosticMetricsStore:
    startup_time_ms: float = 0.0
    initial_load_time_ms: float = 0.0
    refresh_all_duration_ms: float = 0.0
    workspace_switch_time_ms: float = 0.0
    memory_after_startup_mb: float = 0.0
    memory_after_refresh_mb: float = 0.0
    last_refresh_duration_ms: float = 0.0
    diagnostic_mode: bool = False

    def record_refresh_all_duration(self, duration_ms: float) -> None:
        self.refresh_all_duration_ms = duration_ms
        self.last_refresh_duration_ms = duration_ms

    def snapshot(self) -> dict[str, Any]:
        return {
            "startup_time_ms": self.startup_time_ms,
            "initial_load_time_ms": self.initial_load_time_ms,
            "refresh_all_duration_ms": self.refresh_all_duration_ms,
            "workspace_switch_time_ms": self.workspace_switch_time_ms,
            "memory_after_startup_mb": self.memory_after_startup_mb,
            "memory_after_refresh_mb": self.memory_after_refresh_mb,
            "last_refresh_duration_ms": self.last_refresh_duration_ms,
            "diagnostic_mode": self.diagnostic_mode,
        }


@dataclass(slots=True)
class DiagnosticContext:
    execution_id: str = field(default_factory=lambda: f"exec-{uuid.uuid4().hex[:8]}")
    correlation_id: str = field(default_factory=lambda: f"corr-{uuid.uuid4().hex[:8]}")
    valuation_date: str = field(default_factory=lambda: datetime.now(timezone.utc).date().isoformat())
    environment: str = field(default_factory=lambda: (os.getenv("AIP_ENVIRONMENT") or os.getenv("AIP_DEMO_ENVIRONMENT") or "demo"))
    execution_mode: str = field(default_factory=lambda: ((os.getenv("AIP_EXECUTION_MODE") or os.getenv("AIP_DEMO_EXECUTION_MODE") or "DEMO")).upper())
    connector_status: dict[str, str] = field(default_factory=lambda: {"sql": "HEALTHY", "folder_watch": "HEALTHY", "bccr": "HEALTHY"})
    scheduler_jobs: list[str] = field(default_factory=lambda: ["refresh-all", "executive-sync"])
    last_refresh_duration: float = 0.0
    application_version: str = field(default_factory=lambda: APP_VERSION)


class ProductionReadinessService:
    def __init__(
        self,
        *,
        iterations: int = 100,
        application_factory: DemoApplicationFactory | None = None,
    ) -> None:
        self._iterations = iterations
        self._factory = application_factory or DemoApplicationFactory()
        self._metrics = DiagnosticMetricsStore()

    def run_stability_check(self) -> dict[str, Any]:
        failures = 0
        warnings = 0
        execution_times: list[float] = []
        for _ in range(self._iterations):
            started = time.perf_counter()
            try:
                self._factory.refresh_all_workflow().execute("corr-stability")
                self._factory.initial_load_workflow().execute("corr-stability")
            except Exception:
                failures += 1
                continue
            execution_times.append((time.perf_counter() - started) * 1000.0)
        average_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0.0
        return {
            "iterations": self._iterations,
            "failures": failures,
            "warnings": warnings,
            "average_execution_time_ms": average_execution_time,
            "memory_growth_mb": 0.0,
        }

    def diagnostic_snapshot(self) -> dict[str, Any]:
        status = self._factory.build_system_status()
        context = DiagnosticContext()
        config = self._factory.config
        return {
            "application_name": APP_NAME,
            "version": APP_VERSION,
            "release": APP_RELEASE,
            "diagnostic_mode": self._metrics.diagnostic_mode,
            "environment": config.environment_name,
            "execution_mode": config.execution_mode,
            "execution_id": context.execution_id,
            "correlation_id": context.correlation_id,
            "valuation_date": config.data_cutoff_date.isoformat(),
            "connector_status": context.connector_status,
            "scheduler_jobs": context.scheduler_jobs,
            "last_refresh_duration": self._metrics.last_refresh_duration_ms,
            "application_version": context.application_version,
            "system_status": status.as_dict(),
            "metrics": self._metrics.snapshot(),
        }
