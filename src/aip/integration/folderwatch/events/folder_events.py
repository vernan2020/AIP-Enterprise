from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class FolderWatchEventType(str, Enum):
    """Lifecycle event types for folder watch operations."""

    STARTED = "started"
    STOPPED = "stopped"
    DETECTED = "detected"
    PROCESSING_STARTED = "processing_started"
    PROCESSING_COMPLETED = "processing_completed"
    PROCESSING_FAILED = "processing_failed"
    RETRY_STARTED = "retry_started"
    RETRY_COMPLETED = "retry_completed"


@dataclass(frozen=True, slots=True)
class FolderWatchEvent:
    """Event emitted by the folder watch connector."""

    event_type: FolderWatchEventType
    job_id: str
    connector_name: str
    execution_id: str
    details: dict[str, Any] | None = None

    @classmethod
    def started(cls, job_id: str, connector_name: str, execution_id: str) -> "FolderWatchEvent":
        return cls(
            event_type=FolderWatchEventType.STARTED,
            job_id=job_id,
            connector_name=connector_name,
            execution_id=execution_id,
        )

    @classmethod
    def stopped(cls, job_id: str, connector_name: str, execution_id: str) -> "FolderWatchEvent":
        return cls(
            event_type=FolderWatchEventType.STOPPED,
            job_id=job_id,
            connector_name=connector_name,
            execution_id=execution_id,
        )

    @classmethod
    def detected(
        cls, job_id: str, connector_name: str, execution_id: str, filename: str
    ) -> "FolderWatchEvent":
        return cls(
            event_type=FolderWatchEventType.DETECTED,
            job_id=job_id,
            connector_name=connector_name,
            execution_id=execution_id,
            details={"filename": filename},
        )

    @classmethod
    def processing_started(
        cls, job_id: str, connector_name: str, execution_id: str, filename: str
    ) -> "FolderWatchEvent":
        return cls(
            event_type=FolderWatchEventType.PROCESSING_STARTED,
            job_id=job_id,
            connector_name=connector_name,
            execution_id=execution_id,
            details={"filename": filename},
        )

    @classmethod
    def processing_completed(
        cls, job_id: str, connector_name: str, execution_id: str, filename: str
    ) -> "FolderWatchEvent":
        return cls(
            event_type=FolderWatchEventType.PROCESSING_COMPLETED,
            job_id=job_id,
            connector_name=connector_name,
            execution_id=execution_id,
            details={"filename": filename},
        )

    @classmethod
    def processing_failed(
        cls, job_id: str, connector_name: str, execution_id: str, filename: str, error: str
    ) -> "FolderWatchEvent":
        return cls(
            event_type=FolderWatchEventType.PROCESSING_FAILED,
            job_id=job_id,
            connector_name=connector_name,
            execution_id=execution_id,
            details={"filename": filename, "error": error},
        )

    @classmethod
    def retry_started(
        cls, job_id: str, connector_name: str, execution_id: str, attempt: int
    ) -> "FolderWatchEvent":
        return cls(
            event_type=FolderWatchEventType.RETRY_STARTED,
            job_id=job_id,
            connector_name=connector_name,
            execution_id=execution_id,
            details={"attempt": attempt},
        )

    @classmethod
    def retry_completed(
        cls, job_id: str, connector_name: str, execution_id: str, attempt: int
    ) -> "FolderWatchEvent":
        return cls(
            event_type=FolderWatchEventType.RETRY_COMPLETED,
            job_id=job_id,
            connector_name=connector_name,
            execution_id=execution_id,
            details={"attempt": attempt},
        )
