from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class SynchronizationRequest:
    """Request payload passed into a connector during synchronization."""

    connector_name: str
    correlation_id: str
    user: str = "system"
    records_expected: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SynchronizationJob:
    """Definition of a synchronization job."""

    id: str
    connector_name: str
    mode: str = "manual"
    scheduled: bool = False
    enabled: bool = True
    retries: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class SynchronizationScheduler(ABC):
    """Contract for scheduling and executing synchronizations."""

    @abstractmethod
    def execute(self, job: SynchronizationJob) -> Any:
        """Execute a synchronization job."""

    @abstractmethod
    def cancel(self, job_id: str) -> bool:
        """Cancel a queued or running synchronization job."""

    @abstractmethod
    def status(self, job_id: str) -> dict[str, Any]:
        """Return the current status of a job."""

    @abstractmethod
    def history(self, connector_name: str | None = None) -> list[dict[str, Any]]:
        """Return history for the requested connector or all connectors."""
