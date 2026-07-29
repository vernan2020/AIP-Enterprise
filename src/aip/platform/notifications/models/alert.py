from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from aip.platform.notifications.severity.severity import Severity


class AlertStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    EXPIRED = "expired"


@dataclass(slots=True)
class Alert:
    alert_id: str
    title: str
    message: str
    severity: Severity
    correlation_id: str | None = None
    execution_id: str | None = None
    status: AlertStatus = AlertStatus.OPEN
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    acknowledged_by: str | None = None
    resolved_by: str | None = None
