from __future__ import annotations

from datetime import UTC, datetime

from aip.platform.notifications.models.alert import Alert, AlertStatus
from aip.platform.notifications.models.alert_result import AlertResult
from aip.platform.notifications.severity.severity import Severity


class AlertEngine:
    def create_alert(self, alert_id: str, message: str, severity: Severity, *, correlation_id: str | None = None, execution_id: str | None = None) -> Alert:
        return Alert(alert_id=alert_id, title=message, message=message, severity=severity, correlation_id=correlation_id, execution_id=execution_id)

    def resolve_alert(self, alert: Alert, resolved_by: str) -> Alert:
        alert.status = AlertStatus.RESOLVED
        alert.resolved_by = resolved_by
        return alert

    def acknowledge_alert(self, alert: Alert, acknowledged_by: str) -> Alert:
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_by = acknowledged_by
        return alert

    def escalate_alert(self, alert: Alert, severity: Severity) -> Alert:
        alert.severity = severity
        return alert

    def expire_alert(self, alert: Alert, *, expires_at: datetime | None = None) -> Alert:
        if expires_at is not None and expires_at <= datetime.now(UTC):
            alert.status = AlertStatus.EXPIRED
        return alert

    def to_result(self, alert: Alert) -> AlertResult:
        return AlertResult(alert_id=alert.alert_id, status=alert.status, severity=alert.severity, message=alert.message, correlation_id=alert.correlation_id)
