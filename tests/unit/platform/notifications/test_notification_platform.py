from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any

import pytest

from aip.platform.notifications.audit.notification_audit import NotificationAudit
from aip.platform.notifications.configuration.notification_config import NotificationConfig
from aip.platform.notifications.dispatch.dispatch_queue import DispatchQueue
from aip.platform.notifications.dispatch.dispatcher import Dispatcher
from aip.platform.notifications.deduplication.deduplication_service import DeduplicationService
from aip.platform.notifications.engine.alert_engine import AlertEngine
from aip.platform.notifications.engine.notification_engine import NotificationEngine
from aip.platform.notifications.events.notification_events import NotificationEvent, NotificationEventType
from aip.platform.notifications.exceptions.notification_exceptions import NotificationError
from aip.platform.notifications.models.alert import Alert, AlertStatus
from aip.platform.notifications.models.alert_result import AlertResult
from aip.platform.notifications.models.alert_rule import AlertRule
from aip.platform.notifications.models.notification import Notification
from aip.platform.notifications.models.notification_result import NotificationResult, NotificationStatus
from aip.platform.notifications.monitoring.notification_health import NotificationHealthMonitor
from aip.platform.notifications.providers.null_provider import NullProvider
from aip.platform.notifications.providers.provider import Provider
from aip.platform.notifications.providers.provider_registry import ProviderRegistry
from aip.platform.notifications.severity.severity import Severity
from aip.platform.notifications.suppression.suppression_policy import SuppressionPolicy
from aip.platform.notifications.telemetry.notification_metrics import NotificationMetrics
from aip.platform.notifications.templates.template_engine import TemplateEngine


@dataclass
class RecordingProvider(Provider):
    name: str = "recording"
    sent: list[Notification] = field(default_factory=list)
    health_ok: bool = True

    def send(self, notification: Notification, *, timeout_seconds: float | None = None, cancellation_token: str | None = None) -> NotificationResult:
        self.sent.append(notification)
        return NotificationResult(notification_id=notification.notification_id, status=NotificationStatus.SENT, retries=0, provider=self.name, timestamp=datetime.now(UTC), duration_seconds=0.0)

    def health(self) -> bool:
        return self.health_ok


def test_severity_values_and_alert_lifecycle() -> None:
    assert Severity.INFO.value == "info"
    assert Severity.CRITICAL.value == "critical"

    engine = AlertEngine()
    alert = engine.create_alert("alert-1", "System issue", Severity.HIGH, correlation_id="corr")
    assert alert.alert_id == "alert-1"
    assert alert.status == AlertStatus.OPEN

    resolved = engine.resolve_alert(alert, "resolved")
    assert resolved.status == AlertStatus.RESOLVED
    acknowledged = engine.acknowledge_alert(alert, "ops")
    assert acknowledged.status == AlertStatus.ACKNOWLEDGED

    escalated = engine.escalate_alert(alert, Severity.CRITICAL)
    assert escalated.severity == Severity.CRITICAL

    expired = engine.expire_alert(alert, expires_at=datetime.now(UTC) - timedelta(seconds=1))
    assert expired.status == AlertStatus.EXPIRED


def test_notification_engine_evaluates_rules_and_suppression() -> None:
    provider = RecordingProvider()
    registry = ProviderRegistry()
    registry.register(provider)
    metrics = NotificationMetrics()
    health = NotificationHealthMonitor()
    engine = NotificationEngine(provider_registry=registry, metrics=metrics, health=health)
    rule = AlertRule(rule_id="rule-1", name="rule", severity=Severity.HIGH, threshold=1, event_type="job_failed")
    alert = engine.process_event({"event_type": "job_failed", "severity": "high", "message": "job failed"}, rule=rule)
    assert alert is not None
    assert alert.severity == Severity.HIGH

    suppressed = engine.process_event({"event_type": "job_failed", "severity": "high", "message": "job failed"}, rule=rule, suppress=True)
    assert suppressed is None


def test_dispatcher_queue_and_retry_paths() -> None:
    queue = DispatchQueue()
    provider = RecordingProvider()
    dispatcher = Dispatcher(provider=provider, max_retries=2)
    notification = Notification(notification_id="n-1", alert_id="a-1", message="hello", severity=Severity.INFO, correlation_id="c-1", execution_id="e-1")

    queue.enqueue(notification)
    assert queue.dequeue() is notification
    assert queue.size() == 0

    result = dispatcher.dispatch(notification)
    assert result.status == NotificationStatus.SENT
    assert result.provider == "recording"

    class FailingProvider(Provider):
        name = "failing"

        def send(self, notification: Notification, *, timeout_seconds: float | None = None, cancellation_token: str | None = None) -> NotificationResult:
            raise RuntimeError("boom")

        def health(self) -> bool:
            return False

    failed = Dispatcher(provider=FailingProvider(), max_retries=1)
    with pytest.raises(NotificationError, match="failed"):
        failed.dispatch(Notification(notification_id="n-2", alert_id="a-2", message="hello", severity=Severity.INFO, correlation_id="c-2", execution_id="e-2"))


def test_provider_registry_and_null_provider() -> None:
    registry = ProviderRegistry()
    provider = NullProvider()
    registry.register(provider)
    assert registry.lookup("null") is provider
    assert registry.lookup("missing") is None
    assert registry.unregister("null") is True
    assert registry.unregister("missing") is False
    assert registry.health("null") is False


def test_suppression_and_deduplication_services() -> None:
    policy = SuppressionPolicy()
    policy.suppress("alert-a")
    assert policy.is_suppressed("alert-a") is True
    assert policy.is_suppressed("alert-b") is False

    dedup = DeduplicationService()
    assert dedup.is_duplicate("alert-a") is False
    assert dedup.is_duplicate("alert-a") is True


def test_template_engine_and_audit_and_metrics() -> None:
    template = TemplateEngine()
    rendered = template.render("Hello {name} at {timestamp}", {"name": "ops", "timestamp": "2024-01-01"})
    assert "ops" in rendered

    audit = NotificationAudit()
    audit.record(NotificationEvent(NotificationEventType.NOTIFICATION_SENT, "sent", notification_id="n-1", alert_id="a-1", execution_id="e-1", correlation_id="c-1", provider="recording", severity=Severity.INFO, status="sent", retries=0, timestamp=datetime.now(UTC)))
    assert audit.entries[-1].notification_id == "n-1"

    metrics = NotificationMetrics()
    metrics.increment("sent")
    metrics.gauge("queue_size", 2)
    assert metrics.snapshot()["sent"] == 1.0


def test_monitoring_and_events() -> None:
    health = NotificationHealthMonitor()
    health.record_sent(1)
    health.record_failed(1)
    health.record_suppressed(1)
    health.record_deduplicated(1)
    health.record_latency(3.5)
    health.record_queue_size(2)
    snapshot = health.snapshot()
    assert snapshot["notifications_sent"] == 1
    assert snapshot["failed_notifications"] == 1
    assert snapshot["suppressed_notifications"] == 1
    assert snapshot["deduplicated_notifications"] == 1
    assert snapshot["provider_latency"] == 3.5
    assert snapshot["queue_size"] == 2

    events = NotificationEngine(provider_registry=ProviderRegistry(), metrics=NotificationMetrics(), health=NotificationHealthMonitor())
    event = NotificationEvent(NotificationEventType.NOTIFICATION_QUEUED, "queued", notification_id="n-1")
    assert events.publish_event(event) is None


def test_retry_timeout_and_cancellation() -> None:
    provider = RecordingProvider()
    dispatcher = Dispatcher(provider=provider, max_retries=1)
    notification = Notification(notification_id="n-3", alert_id="a-3", message="hello", severity=Severity.INFO, correlation_id="c-3", execution_id="e-3")
    result = dispatcher.dispatch(notification, cancellation_token="cancelled")
    assert result.status == NotificationStatus.CANCELLED

    class SlowProvider(Provider):
        name = "slow"

        def send(self, notification: Notification, *, timeout_seconds: float | None = None, cancellation_token: str | None = None) -> NotificationResult:
            raise TimeoutError("slow")

        def health(self) -> bool:
            return True

    slow = Dispatcher(provider=SlowProvider(), max_retries=1)
    with pytest.raises(TimeoutError):
        slow.dispatch(Notification(notification_id="n-4", alert_id="a-4", message="hello", severity=Severity.INFO, correlation_id="c-4", execution_id="e-4"))


def test_alert_result_and_engine_helpers() -> None:
    result = AlertResult(alert_id="a-1", status=AlertStatus.OPEN, severity=Severity.INFO, message="msg", correlation_id="corr")
    assert result.alert_id == "a-1"

    engine = AlertEngine()
    alert = Alert(alert_id="a-1", title="title", message="message", severity=Severity.INFO, correlation_id="corr")
    assert engine.resolve_alert(alert, "done").status == AlertStatus.RESOLVED
    assert engine.acknowledge_alert(alert, "ops").status == AlertStatus.ACKNOWLEDGED
    assert engine.escalate_alert(alert, Severity.CRITICAL).severity == Severity.CRITICAL


def test_alert_engine_expiration_and_result_conversion() -> None:
    engine = AlertEngine()
    alert = engine.create_alert("alert-2", "preview", Severity.INFO)

    engine.expire_alert(alert)
    assert alert.status == AlertStatus.OPEN

    future = datetime.now(UTC) + timedelta(minutes=1)
    engine.expire_alert(alert, expires_at=future)
    assert alert.status == AlertStatus.OPEN

    expired = engine.expire_alert(alert, expires_at=datetime.now(UTC) - timedelta(seconds=1))
    assert expired.status == AlertStatus.EXPIRED

    result = engine.to_result(expired)
    assert result.status == AlertStatus.EXPIRED
    assert result.correlation_id is None


def test_notification_engine_deduplication_and_no_rule_path() -> None:
    dedup = DeduplicationService()
    policy = SuppressionPolicy()
    health = NotificationHealthMonitor()
    metrics = NotificationMetrics()
    engine = NotificationEngine(metrics=metrics, health=health, suppression_policy=policy, deduplication_service=dedup)

    first = engine.process_event({"event_type": "job_failed", "message": "job failed", "severity": "high"})
    assert first is not None

    duplicate = engine.process_event({"event_type": "job_failed", "message": "job failed", "severity": "high"})
    assert duplicate is None

    no_rule = engine.process_event({"event_type": "job_started", "message": "job started"})
    assert no_rule is not None
    assert no_rule.severity == Severity.INFO
    assert metrics.snapshot()["alerts"] == 2.0
    assert health.snapshot()["deduplicated_notifications"] == 1


def test_dispatcher_and_template_engine_cover_unreachable_paths() -> None:
    provider = NullProvider()
    result = provider.send(Notification(notification_id="n-5", alert_id="a-5", message="hello", severity=Severity.INFO, correlation_id="c-5", execution_id="e-5"))
    assert result.status == NotificationStatus.SENT
    assert provider.health() is True

    template = TemplateEngine()
    assert template.format_severity("warn") == "WARN"
    assert template.format_timestamp() is not None
    assert template.format_correlation_id(None) == "n/a"
    assert template.format_execution_id(None) == "n/a"

    with pytest.raises(KeyError):
        template.render("Hello {name}", {})

    with pytest.raises(ValueError):
        template.render("Hello {", {})

    dispatcher = Dispatcher(provider=RecordingProvider(), max_retries=-1)
    with pytest.raises(NotificationError, match="notification failed"):
        dispatcher.dispatch(Notification(notification_id="n-6", alert_id="a-6", message="hello", severity=Severity.INFO, correlation_id="c-6", execution_id="e-6"))
