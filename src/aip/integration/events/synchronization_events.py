from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from aip.integration.audit.execution_result import ExecutionResult


class SynchronizationEventType(str, Enum):
    """Lifecycle event types for synchronization."""

    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRY = "retry"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


@dataclass(frozen=True, slots=True)
class SynchronizationEvent:
    """Domain event used to announce integration lifecycle changes."""

    event_type: SynchronizationEventType
    job_id: str
    connector_name: str
    execution_id: str
    details: dict[str, Any] | None = None

    @classmethod
    def started(cls, job_id: str, connector_name: str, execution_id: str) -> "SynchronizationEvent":
        return cls(
            event_type=SynchronizationEventType.STARTED,
            job_id=job_id,
            connector_name=connector_name,
            execution_id=execution_id,
        )

    @classmethod
    def completed(
        cls, job_id: str, connector_name: str, execution_id: str, result: ExecutionResult
    ) -> "SynchronizationEvent":
        return cls(
            event_type=SynchronizationEventType.COMPLETED,
            job_id=job_id,
            connector_name=connector_name,
            execution_id=execution_id,
            details={"result": result.to_dict()},
        )

    @classmethod
    def failed(
        cls, job_id: str, connector_name: str, execution_id: str, error: str
    ) -> "SynchronizationEvent":
        return cls(
            event_type=SynchronizationEventType.FAILED,
            job_id=job_id,
            connector_name=connector_name,
            execution_id=execution_id,
            details={"error": error},
        )

    @classmethod
    def cancelled(
        cls, job_id: str, connector_name: str, execution_id: str
    ) -> "SynchronizationEvent":
        return cls(
            event_type=SynchronizationEventType.CANCELLED,
            job_id=job_id,
            connector_name=connector_name,
            execution_id=execution_id,
        )

    @classmethod
    def retry(
        cls, job_id: str, connector_name: str, execution_id: str, attempt: int
    ) -> "SynchronizationEvent":
        return cls(
            event_type=SynchronizationEventType.RETRY,
            job_id=job_id,
            connector_name=connector_name,
            execution_id=execution_id,
            details={"attempt": attempt},
        )

    @classmethod
    def connected(
        cls, job_id: str, connector_name: str, execution_id: str
    ) -> "SynchronizationEvent":
        return cls(
            event_type=SynchronizationEventType.CONNECTED,
            job_id=job_id,
            connector_name=connector_name,
            execution_id=execution_id,
            details={"phase": "connected"},
        )

    @classmethod
    def disconnected(
        cls, job_id: str, connector_name: str, execution_id: str
    ) -> "SynchronizationEvent":
        return cls(
            event_type=SynchronizationEventType.DISCONNECTED,
            job_id=job_id,
            connector_name=connector_name,
            execution_id=execution_id,
            details={"phase": "disconnected"},
        )

    @classmethod
    def synchronization_started(
        cls, job_id: str, connector_name: str, execution_id: str
    ) -> "SynchronizationEvent":
        return cls(
            event_type=SynchronizationEventType.STARTED,
            job_id=job_id,
            connector_name=connector_name,
            execution_id=execution_id,
            details={"phase": "synchronization_started"},
        )

    @classmethod
    def synchronization_completed(
        cls, job_id: str, connector_name: str, execution_id: str
    ) -> "SynchronizationEvent":
        return cls(
            event_type=SynchronizationEventType.COMPLETED,
            job_id=job_id,
            connector_name=connector_name,
            execution_id=execution_id,
            details={"phase": "synchronization_completed"},
        )


class SyncEvent(SynchronizationEvent):
    """Backward-compatible alias for lifecycle events."""

    pass


class IntegrationEventBus:
    """Simple event bus for synchronization lifecycle events."""

    def __init__(self) -> None:
        self._handlers: list[Callable[[SynchronizationEvent], None]] = []

    def subscribe(self, handler: Callable[[SynchronizationEvent], None]) -> None:
        self._handlers.append(handler)

    def publish(self, event: SynchronizationEvent) -> None:
        for handler in self._handlers:
            handler(event)
