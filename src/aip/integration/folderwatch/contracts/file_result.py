from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class FileExecutionStatus(str, Enum):
    """Lifecycle status for a file processing execution."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class FileExecutionResult:
    """Structured execution result for a processed file."""

    filename: str
    status: FileExecutionStatus = FileExecutionStatus.COMPLETED
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    timestamp: datetime | None = None
    records_processed: int = 0
