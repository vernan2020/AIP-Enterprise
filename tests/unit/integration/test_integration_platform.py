from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aip.integration.audit.execution_result import ExecutionResult, ExecutionStatus
from aip.integration.audit.synchronization_log import SynchronizationLog
from aip.integration.contracts.connector import ConnectorProtocol, ConnectorType
from aip.integration.contracts.synchronization import SynchronizationRequest
from aip.integration.events.synchronization_events import SynchronizationEvent, SynchronizationEventType
from aip.integration.hub.integration_hub import IntegrationHub
from aip.integration.monitoring.health_monitor import HealthMonitor
from aip.integration.normalization.normalizer import Normalizer
from aip.integration.scheduler.job_definition import JobDefinition
from aip.integration.scheduler.scheduler_service import SchedulerService
from aip.integration.telemetry.metrics import MetricsCollector
from aip.integration.validation.validator import ValidationIssue, ValidationResult, Validator


class StubConnector(ConnectorProtocol):
    def __init__(self, name: str, *, fail: bool = False) -> None:
        self.name = name
        self.fail = fail
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.health_calls = 0
        self.synchronize_calls = 0
        self.validate_calls = 0
        self.normalize_calls = 0
        self.audit_calls = 0

    def connect(self) -> None:
        self.connect_calls += 1

    def disconnect(self) -> None:
        self.disconnect_calls += 1

    def health(self) -> bool:
        self.health_calls += 1
        return not self.fail

    def synchronize(self, request: SynchronizationRequest) -> int:
        self.synchronize_calls += 1
        if self.fail:
            raise RuntimeError("boom")
        return request.records_expected

    def validate(self, payload: object) -> ValidationResult:
        self.validate_calls += 1
        return ValidationResult(ok=True, issues=[])

    def normalize(self, payload: object) -> object:
        self.normalize_calls += 1
        return payload

    def audit(self, log: SynchronizationLog) -> None:
        self.audit_calls += 1


class FlakyConnector(StubConnector):
    def __init__(self) -> None:
        super().__init__("flaky", fail=False)
        self._attempts = 0

    def synchronize(self, request: SynchronizationRequest) -> int:
        self._attempts += 1
        if self._attempts == 1:
            raise RuntimeError("temporary")
        return request.records_expected


def test_integration_hub_executes_connectors_and_publishes_events() -> None:
    connector = StubConnector("sql", fail=False)
    hub = IntegrationHub(connectors=[connector])
    events: list[SynchronizationEvent] = []
    hub.subscribe(events.append)

    result = hub.run_synchronization(correlation_id="corr-1", user="ops")

    assert result.status == ExecutionStatus.COMPLETED
    assert connector.synchronize_calls == 1
    assert connector.audit_calls == 1
    assert [event.event_type for event in events] == [
        SynchronizationEventType.STARTED,
        SynchronizationEventType.COMPLETED,
    ]
    assert hub.audit_log[-1].correlation_id == "corr-1"
    assert hub.audit_log[-1].user == "ops"


def test_scheduler_supports_manual_scheduled_retry_and_cancellation() -> None:
    connector = FlakyConnector()
    job = JobDefinition(id="job-1", connector=connector, connector_type=ConnectorType.REST_API)
    scheduler = SchedulerService()

    first = scheduler.run_job(job)
    assert first.status == ExecutionStatus.FAILED

    second = scheduler.retry_job("job-1")
    assert second.status == ExecutionStatus.COMPLETED
    assert scheduler.get_status("job-1") == ExecutionStatus.COMPLETED

    scheduled = JobDefinition(id="job-2", connector=StubConnector("folder"), connector_type=ConnectorType.FOLDER_WATCH)
    scheduler.schedule_job(scheduled, scheduled_for=datetime.now(UTC) + timedelta(minutes=5))
    scheduler.cancel_job("job-2")
    assert scheduler.get_status("job-2") == ExecutionStatus.CANCELLED
    assert scheduler.get_history("job-2")[-1].status == ExecutionStatus.CANCELLED


def test_validation_pipeline_collects_issues() -> None:
    validator = Validator()
    result = validator.validate(
        {"id": 1, "name": ""},
        rules=[
            lambda payload: (payload.get("id") is not None, "missing id"),
            lambda payload: (bool(payload.get("name")), "missing name"),
        ],
    )

    assert result.ok is False
    assert any(issue.message == "missing name" for issue in result.issues)


def test_monitoring_tracks_health_and_execution_stats() -> None:
    monitor = HealthMonitor()
    monitor.record_health("sql", healthy=True, availability=0.99, last_synchronization=datetime.now(UTC))
    monitor.record_execution("sql", success=True, records=12)

    snapshot = monitor.get_health("sql")
    assert snapshot.healthy is True
    assert snapshot.availability == 0.99
    assert snapshot.last_synchronization is not None
    assert monitor.get_statistics("sql").completed == 1
    assert monitor.get_statistics("sql").records_processed == 12


def test_telemetry_collects_metrics() -> None:
    collector = MetricsCollector()
    collector.increment("syncs", 2)
    collector.gauge("latency", 7.5)

    snapshot = collector.snapshot()
    assert snapshot["syncs"] == 2
    assert snapshot["latency"] == 7.5


def test_normalizer_applies_transforms() -> None:
    normalizer = Normalizer()
    payload = {"source": "REST", "value": "  ready  "}
    transformed = normalizer.normalize(payload)

    assert transformed["source"] == "REST"
    assert transformed["value"] == "ready"


def test_synchronization_events_are_emitters() -> None:
    bus = SynchronizationEventType
    assert bus.STARTED.value == "started"
    assert bus.FAILED.value == "failed"


def test_hub_registers_and_lists_connectors() -> None:
    hub = IntegrationHub()
    connector = StubConnector("sql")
    hub.register_connector(connector)

    assert hub.list_connectors() == [ConnectorType.FUTURE]


def test_validator_accepts_empty_rules_and_reports_payloads() -> None:
    validator = Validator()
    result = validator.validate({"id": 1})

    assert result.ok is True
    assert result.details["payload"]["id"] == 1


def test_scheduler_status_and_history_helpers() -> None:
    scheduler = SchedulerService()
    job = JobDefinition(id="job-3", connector=StubConnector("rest"), connector_type=ConnectorType.REST_API)
    scheduler.run_job(job)

    assert scheduler.get_status("job-3") == ExecutionStatus.COMPLETED
    assert scheduler.get_history("job-3")[-1].status == ExecutionStatus.COMPLETED


def test_cancel_job_returns_false_for_unknown_job() -> None:
    scheduler = SchedulerService()
    assert scheduler.cancel_job("missing") is False


def test_hub_requires_registered_connector() -> None:
    hub = IntegrationHub()
    try:
        hub.run_synchronization(correlation_id="missing")
    except Exception as exc:
        assert "No connectors registered" in str(exc)


def test_health_monitor_status_and_normalizer_fallback() -> None:
    monitor = HealthMonitor()
    monitor.record_health("rest", healthy=True, availability=0.8, last_synchronization=datetime.now(UTC))
    snapshot = monitor.get_health("rest")
    assert snapshot.healthy is True
    assert snapshot.availability == 0.8
    assert monitor.status("rest")["available"] is True

    normalizer = Normalizer()
    assert normalizer.normalize(17) == {"value": 17}
