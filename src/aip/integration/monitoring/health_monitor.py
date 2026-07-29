from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class HealthSnapshot:
    """Observed health information for a connector."""

    connector_name: str
    healthy: bool
    availability: float
    last_synchronization: datetime | None = None


@dataclass(slots=True)
class ExecutionStatistics:
    """Aggregated execution statistics for a connector."""

    completed: int = 0
    failed: int = 0
    records_processed: int = 0
    last_execution: datetime | None = None


@dataclass(slots=True)
class HealthMonitor:
    """Tracks connector health, availability, and synchronization state."""

    availability: dict[str, bool] = field(default_factory=dict)
    health_status: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_sync: dict[str, datetime] = field(default_factory=dict)
    execution_stats: dict[str, ExecutionStatistics] = field(default_factory=dict)

    def mark_available(self, connector_name: str, available: bool) -> None:
        self.availability[connector_name] = available

    def update_health(self, connector_name: str, snapshot: dict[str, Any]) -> None:
        self.health_status[connector_name] = snapshot

    def record_sync(self, connector_name: str) -> None:
        self.last_sync[connector_name] = datetime.now(UTC)
        stats = self.execution_stats.setdefault(connector_name, ExecutionStatistics())
        self.execution_stats[connector_name] = ExecutionStatistics(
            completed=stats.completed + 1,
            failed=stats.failed,
            records_processed=stats.records_processed,
            last_execution=datetime.now(UTC),
        )

    def record_health(
        self,
        connector_name: str,
        *,
        healthy: bool,
        availability: float,
        last_synchronization: datetime | None = None,
    ) -> None:
        self.availability[connector_name] = healthy
        snapshot = dict(self.health_status.get(connector_name, {}))
        snapshot.update({
            "healthy": healthy,
            "availability": availability,
        })
        self.health_status[connector_name] = snapshot
        if last_synchronization is not None:
            self.last_sync[connector_name] = last_synchronization

    def record_execution(self, connector_name: str, *, success: bool, records: int = 0) -> None:
        stats = self.execution_stats.setdefault(connector_name, ExecutionStatistics())
        self.execution_stats[connector_name] = ExecutionStatistics(
            completed=stats.completed + (1 if success else 0),
            failed=stats.failed + (1 if not success else 0),
            records_processed=stats.records_processed + records,
            last_execution=datetime.now(UTC),
        )

    def get_health(self, connector_name: str) -> HealthSnapshot:
        return HealthSnapshot(
            connector_name=connector_name,
            healthy=self.availability.get(connector_name, False),
            availability=self.health_status.get(connector_name, {}).get("availability", 0.0),
            last_synchronization=self.last_sync.get(connector_name),
        )

    def get_statistics(self, connector_name: str) -> ExecutionStatistics:
        return self.execution_stats.get(connector_name, ExecutionStatistics())

    def status(self, connector_name: str) -> dict[str, Any]:
        stats = self.get_statistics(connector_name)
        return {
            "available": self.availability.get(connector_name, False),
            "health": self.health_status.get(connector_name, {}),
            "last_sync": self.last_sync.get(connector_name),
            "execution_stats": stats,
        }
