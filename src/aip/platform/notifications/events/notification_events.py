from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.platform.notifications.severity.severity import Severity


class NotificationEventType(str, Enum):
    ALERT_CREATED = "alert_created"
    ALERT_ACKNOWLEDGED = "alert_acknowledged"
    ALERT_RESOLVED = "alert_resolved"
    ALERT_ESCALATED = "alert_escalated"
    NOTIFICATION_QUEUED = "notification_queued"
    NOTIFICATION_SENT = "notification_sent"
    NOTIFICATION_FAILED = "notification_failed"
    RETRY_STARTED = "retry_started"
    RETRY_COMPLETED = "retry_completed"


@dataclass(slots=True)
class NotificationEvent:
    event_type: NotificationEventType
    message: str
    notification_id: str | None = None
    alert_id: str | None = None
    execution_id: str | None = None
    correlation_id: str | None = None
    provider: str | None = None
    severity: Severity | None = None
    status: str | None = None
    retries: int = 0
    timestamp: object | None = None
