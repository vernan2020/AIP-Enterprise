from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class BCCREventType(str, Enum):
    """Lifecycle event types for BCCR synchronization."""

    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY_STARTED = "retry_started"
    RETRY_COMPLETED = "retry_completed"
    REQUEST_STARTED = "request_started"
    REQUEST_COMPLETED = "request_completed"
    REQUEST_FAILED = "request_failed"
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"


@dataclass(frozen=True, slots=True)
class BCCREvent:
    """Simple BCCR lifecycle event."""

    event_type: BCCREventType
    connector_name: str
    execution_id: str
    details: dict[str, Any] | None = None

    @classmethod
    def started(cls, connector_name: str, execution_id: str) -> "BCCREvent":
        return cls(
            event_type=BCCREventType.STARTED,
            connector_name=connector_name,
            execution_id=execution_id,
        )

    @classmethod
    def completed(cls, connector_name: str, execution_id: str) -> "BCCREvent":
        return cls(
            event_type=BCCREventType.COMPLETED,
            connector_name=connector_name,
            execution_id=execution_id,
        )

    @classmethod
    def failed(cls, connector_name: str, execution_id: str, error: str) -> "BCCREvent":
        return cls(
            event_type=BCCREventType.FAILED,
            connector_name=connector_name,
            execution_id=execution_id,
            details={"error": error},
        )

    @classmethod
    def retry_started(cls, connector_name: str, execution_id: str, attempt: int) -> "BCCREvent":
        return cls(
            event_type=BCCREventType.RETRY_STARTED,
            connector_name=connector_name,
            execution_id=execution_id,
            details={"attempt": attempt},
        )

    @classmethod
    def retry_completed(cls, connector_name: str, execution_id: str, attempt: int) -> "BCCREvent":
        return cls(
            event_type=BCCREventType.RETRY_COMPLETED,
            connector_name=connector_name,
            execution_id=execution_id,
            details={"attempt": attempt},
        )

    @classmethod
    def request_started(cls, connector_name: str, execution_id: str) -> "BCCREvent":
        return cls(
            event_type=BCCREventType.REQUEST_STARTED,
            connector_name=connector_name,
            execution_id=execution_id,
        )

    @classmethod
    def request_completed(cls, connector_name: str, execution_id: str) -> "BCCREvent":
        return cls(
            event_type=BCCREventType.REQUEST_COMPLETED,
            connector_name=connector_name,
            execution_id=execution_id,
        )

    @classmethod
    def request_failed(cls, connector_name: str, execution_id: str, error: str) -> "BCCREvent":
        return cls(
            event_type=BCCREventType.REQUEST_FAILED,
            connector_name=connector_name,
            execution_id=execution_id,
            details={"error": error},
        )

    @classmethod
    def cache_hit(cls, connector_name: str, execution_id: str) -> "BCCREvent":
        return cls(
            event_type=BCCREventType.CACHE_HIT,
            connector_name=connector_name,
            execution_id=execution_id,
            details={"source": "cache"},
        )

    @classmethod
    def cache_miss(cls, connector_name: str, execution_id: str) -> "BCCREvent":
        return cls(
            event_type=BCCREventType.CACHE_MISS,
            connector_name=connector_name,
            execution_id=execution_id,
            details={"source": "network"},
        )
