from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class SynchronizationLog:
    """Audit log entry describing a synchronization execution."""

    execution_id: str
    correlation_id: str
    connector: str
    duration_seconds: float
    records_processed: int
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    user: str = "system"
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

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
            "timestamp": self.timestamp.isoformat(),
        }
