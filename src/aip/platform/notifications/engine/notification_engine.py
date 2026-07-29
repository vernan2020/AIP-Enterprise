from __future__ import annotations

from typing import Any

from aip.platform.notifications.deduplication.deduplication_service import DeduplicationService
from aip.platform.notifications.events.notification_events import NotificationEvent, NotificationEventType
from aip.platform.notifications.models.alert import Alert, AlertStatus
from aip.platform.notifications.models.alert_rule import AlertRule
from aip.platform.notifications.models.notification import Notification
from aip.platform.notifications.monitoring.notification_health import NotificationHealthMonitor
from aip.platform.notifications.providers.provider_registry import ProviderRegistry
from aip.platform.notifications.severity.severity import Severity
from aip.platform.notifications.suppression.suppression_policy import SuppressionPolicy
from aip.platform.notifications.telemetry.notification_metrics import NotificationMetrics


class NotificationEngine:
    def __init__(self, *, provider_registry: ProviderRegistry | None = None, metrics: NotificationMetrics | None = None, health: NotificationHealthMonitor | None = None, suppression_policy: SuppressionPolicy | None = None, deduplication_service: DeduplicationService | None = None) -> None:
        self.provider_registry = provider_registry or ProviderRegistry()
        self.metrics = metrics or NotificationMetrics()
        self.health = health or NotificationHealthMonitor()
        self.suppression_policy = suppression_policy or SuppressionPolicy()
        self.deduplication_service = deduplication_service or DeduplicationService()

    def process_event(self, event: dict[str, Any], *, rule: AlertRule | None = None, suppress: bool = False) -> Alert | None:
        severity = Severity(event.get("severity", "info")) if isinstance(event.get("severity"), str) else Severity.INFO
        if suppress or self.suppression_policy.is_suppressed(event.get("event_type", "default")):
            self.health.record_suppressed(1)
            return None
        if self.deduplication_service.is_duplicate(event.get("event_type", "default")):
            self.health.record_deduplicated(1)
            return None
        alert = Alert(alert_id=str(hash(event.get("event_type", "default"))), title=event.get("message", "event"), message=event.get("message", "event"), severity=severity, correlation_id=event.get("correlation_id"))
        if rule is not None:
            alert.severity = rule.severity
        self.health.record_sent(1)
        self.metrics.increment("alerts")
        return alert

    def publish_event(self, event: NotificationEvent) -> None:
        self.metrics.increment("events")
