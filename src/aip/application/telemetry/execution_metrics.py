from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from aip.application.exceptions import TelemetryError


@dataclass(slots=True)
class ExecutionMetrics:
    """Collects telemetry for workflow execution."""

    workflow_id: str
    correlation_id: str
    step_durations: dict[str, Decimal] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    engine_sequence: tuple[str, ...] = ()
    execution_time: Decimal | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    start_timestamp: datetime | None = None
    end_timestamp: datetime | None = None
    total_duration: Decimal | None = None
    step_order: tuple[str, ...] = ()
    final_status: str = "RUNNING"

    def record_step(self, engine_name: str, duration: Decimal) -> None:
        if duration < 0:
            raise TelemetryError("step duration cannot be negative")
        self.step_durations[engine_name] = duration
        self.engine_sequence = self.engine_sequence + (engine_name,)
        self.step_order = self.step_order + (engine_name,)

    def record_warning(self, warning: str) -> None:
        self.warnings = self.warnings + (warning,)

    def record_error(self, error: str) -> None:
        self.errors = self.errors + (error,)

    def record_execution_time(self, execution_time: Decimal) -> None:
        if execution_time < 0:
            raise TelemetryError("execution_time cannot be negative")
        self.execution_time = execution_time
        self.total_duration = execution_time

    def record_start_timestamp(self, timestamp: datetime) -> None:
        if timestamp.tzinfo is None:
            raise TelemetryError("timestamps must be timezone-aware")
        self.start_timestamp = timestamp.astimezone(UTC)

    def record_end_timestamp(self, timestamp: datetime) -> None:
        if timestamp.tzinfo is None:
            raise TelemetryError("timestamps must be timezone-aware")
        self.end_timestamp = timestamp.astimezone(UTC)

    def mark_completed(self, status: str = "COMPLETED") -> None:
        self.final_status = status
