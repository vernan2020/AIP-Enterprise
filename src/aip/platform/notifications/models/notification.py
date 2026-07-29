from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from aip.platform.notifications.severity.severity import Severity


@dataclass(slots=True)
class Notification:
    notification_id: str
    alert_id: str
    message: str
    severity: Severity
    correlation_id: str | None = None
    execution_id: str | None = None
    provider: str | None = None
    retries: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
