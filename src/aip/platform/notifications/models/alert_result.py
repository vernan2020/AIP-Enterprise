from __future__ import annotations

from dataclasses import dataclass

from aip.platform.notifications.models.alert import AlertStatus
from aip.platform.notifications.severity.severity import Severity


@dataclass(slots=True)
class AlertResult:
    alert_id: str
    status: AlertStatus
    severity: Severity
    message: str
    correlation_id: str | None = None
