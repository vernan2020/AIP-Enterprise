from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ExecutionStatus(str, Enum):
    """Lifecycle status for an integration execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class ExecutionResult:
    """Structured audit trail entry for integration execution."""

    execution_id: str
    correlation_id: str
    connector: str
    duration_seconds: float = 0.0
    records_processed: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    user: str = "system"
    timestamp: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    status: ExecutionStatus = ExecutionStatus.COMPLETED

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "correlation_id": self.correlation_id,
            "connector": self.connector,
            "duration_seconds": self.duration_seconds,
            "records_processed": self.records_processed,
            "warnings": self.warnings,
            "errors": self.errors,
            "user": self.user,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "status": self.status.value,
        }
