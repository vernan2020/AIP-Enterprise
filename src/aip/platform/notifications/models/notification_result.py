from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class NotificationStatus(str, Enum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class NotificationResult:
    notification_id: str
    status: NotificationStatus
    retries: int
    provider: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    duration_seconds: float = 0.0
