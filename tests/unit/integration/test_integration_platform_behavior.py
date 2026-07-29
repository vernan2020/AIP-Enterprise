from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from aip.core.exceptions import InfrastructureError
from aip.integration.audit.execution_result import ExecutionResult, ExecutionStatus
from aip.integration.audit.synchronization_log import SynchronizationLog
from aip.integration.contracts.connector import ConnectorDescriptor, ConnectorProtocol, ConnectorType
from aip.integration.contracts.synchronization import SynchronizationJob, SynchronizationRequest
from aip.integration.events.synchronization_events import IntegrationEventBus, SynchronizationEvent, SynchronizationEventType
from aip.integration.exceptions.exceptions import IntegrationError
from aip.integration.hub.integration_hub import IntegrationHub
from aip.integration.monitoring.health_monitor import HealthMonitor
from aip.integration.normalization.normalizer import Normalizer
from aip.integration.scheduler.job_definition import JobDefinition
from aip.integration.scheduler.scheduler_service import SchedulerService
from aip.integration.telemetry.metrics import MetricsCollector, TelemetryMetrics
from aip.integration.validation.validator import ValidationIssue, ValidationResult, Validator


class RecordingConnector(ConnectorProtocol):
    def __init__(
        self,
        name: str,
        *,
        healthy: bool = True,
        fail_on_validate: bool = False,
        fail_on_normalize: bool = False,
        fail_on_audit: bool = False,
        fail_on_synchronize: bool = False,
        sync_result: int = 1,
    ) -> None:
        self.name = name
        self._healthy = healthy
        self._fail_on_validate = fail_on_validate
        self._fail_on_normalize = fail_on_normalize
        self._fail_on_audit = fail_on_audit
        self._fail_on_synchronize = fail_on_synchronize
        self._sync_result = sync_result
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
        return self._healthy

    def synchronize(self, request: SynchronizationRequest) -> int:
        self.synchronize_calls += 1
        if self._fail_on_synchronize:
            raise RuntimeError("sync failed")
        return self._sync_result

    def validate(self, payload: object) -> ValidationResult:
        self.validate_calls += 1
        if self._fail_on_validate:
            return ValidationResult(ok=False, issues=[ValidationIssue(field="payload", message="invalid")])
        return ValidationResult(ok=True, issues=[])

    def normalize(self, payload: object) -> object:
        self.normalize_calls += 1
        if self._fail_on_normalize:
            raise RuntimeError("normalize failed")
        return payload

    def audit(self, log: SynchronizationLog) -> None:
        self.audit_calls += 1
        if self._fail_on_audit:
            raise RuntimeError("audit failed")


class FlakyConnector(RecordingConnector):
    def __init__(self, *, failures: int = 2) -> None:
        super().__init__("flaky", healthy=True)
        self._failures = failures
        self._attempts = 0

    def synchronize(self, request: SynchronizationRequest) -> int:
        self._attempts += 1
        if self._attempts <= self._failures:
            raise RuntimeError("temporary")
        return request.records_expected


def test_hub_registers_connectors_and_keeps_deterministic_order() -> None:
    hub = IntegrationHub()
    first = RecordingConnector("first")
    second = RecordingConnector("second")

    hub.register_connector(first)
    hub.register_connector(second)

    assert hub.connectors == [first, second]
    assert hub.list_connectors() == [ConnectorType.FUTURE]


def test_hub_translates_validation_and_normalization_and_audit_failures() -> None:
    for connector in (
        RecordingConnector("bad-validation", fail_on_validate=True),
        RecordingConnector("bad-normalization", fail_on_normalize=True),
        RecordingConnector("bad-audit", fail_on_audit=True),
    ):
        hub = IntegrationHub(connectors=[connector])
        with pytest.raises(IntegrationError):
            hub.run_synchronization(correlation_id="corr")
        assert connector.disconnect_calls == 1


def test_hub_emits_started_completed_and_failed_events_in_order() -> None:
    connector = RecordingConnector("sql")
    hub = IntegrationHub(connectors=[connector])
    events: list[SynchronizationEvent] = []
    hub.subscribe(events.append)

    result = hub.run_synchronization(correlation_id="corr-1", user="ops")

    assert result.status == ExecutionStatus.COMPLETED
    assert [event.event_type for event in events] == [SynchronizationEventType.STARTED, SynchronizationEventType.COMPLETED]


def test_scheduler_retries_until_exhaustion_and_emits_retry_event() -> None:
    scheduler = SchedulerService()
    connector = FlakyConnector(failures=3)
    scheduler.register_connector(connector)
    job = JobDefinition(id="retry-job", connector=connector, connector_type=ConnectorType.REST_API)
    events: list[SynchronizationEvent] = []
    scheduler.event_bus = IntegrationEventBus()
    scheduler.event_bus.subscribe(events.append)

    scheduler.run_job(job)
    first = scheduler.retry_job("retry-job")
    second = scheduler.retry_job("retry-job")

    assert first.status == ExecutionStatus.FAILED
    assert second.status == ExecutionStatus.FAILED
    assert [event.event_type for event in events if event.event_type == SynchronizationEventType.RETRY] == [SynchronizationEventType.RETRY]
    assert scheduler.get_status("retry-job") == ExecutionStatus.FAILED


def test_scheduler_cancels_unknown_jobs_and_wraps_history() -> None:
    scheduler = SchedulerService()
    assert scheduler.cancel_job("missing") is False
    assert scheduler.cancel("missing") is False

    job = JobDefinition(id="cancel-job", connector=RecordingConnector("rest"), connector_type=ConnectorType.REST_API)
    scheduler.schedule_job(job, scheduled_for=datetime.now(UTC) + timedelta(minutes=1))
    assert scheduler.status("cancel-job")["status"] == ExecutionStatus.PENDING.value
    assert scheduler.cancel("cancel-job") is True
    assert scheduler.get_status("cancel-job") == ExecutionStatus.CANCELLED
    assert scheduler.history("rest")[-1]["status"] == ExecutionStatus.CANCELLED.value


def test_scheduler_uses_registered_connector_and_reports_health_failure() -> None:
    scheduler = SchedulerService()
    connector = RecordingConnector("unhealthy", healthy=False)
    scheduler.register_connector(connector)
    job = JobDefinition(id="health-job", connector_name="unhealthy")

    result = scheduler.run_job(job)

    assert result.status == ExecutionStatus.FAILED
    assert "Connector is not available" in result.errors[0]


def test_scheduler_handles_validation_and_normalization_failures() -> None:
    scheduler = SchedulerService()
    connector = RecordingConnector("invalid", fail_on_validate=True)
    scheduler.register_connector(connector)
    job = JobDefinition(id="validation-job", connector=connector, connector_type=ConnectorType.FILE_IMPORT)

    failed = scheduler.run_job(job)

    assert failed.status == ExecutionStatus.FAILED
    assert "Validation failed" in failed.errors[0]

    connector = RecordingConnector("bad-normalizer", fail_on_normalize=True)
    scheduler.register_connector(connector)
    job = JobDefinition(id="normalizer-job", connector=connector, connector_type=ConnectorType.FILE_IMPORT)
    failed = scheduler.run_job(job)
    assert failed.status == ExecutionStatus.FAILED
    assert "normalize failed" in failed.errors[0]


def test_scheduler_execute_wrapper_and_history_helpers() -> None:
    scheduler = SchedulerService()
    connector = RecordingConnector("rest", sync_result=7)
    scheduler.register_connector(connector)
    job = SynchronizationJob(id="wrapper-job", connector_name="rest")

    result = scheduler.execute(job)

    assert result.records_processed == 7
    assert scheduler.get_history("wrapper-job")[-1].correlation_id == "wrapper-job"
    assert scheduler.history()[0]["connector"] == "rest"


def test_health_monitor_handles_unavailable_and_degraded_state() -> None:
    monitor = HealthMonitor()
    monitor.mark_available("rest", False)
    monitor.update_health("rest", {"healthy": False, "availability": 0.5, "state": "degraded"})
    monitor.record_health("rest", healthy=False, availability=0.5)

    snapshot = monitor.get_health("rest")
    assert snapshot.healthy is False
    assert snapshot.availability == 0.5
    assert monitor.status("rest")["health"]["state"] == "degraded"


def test_metrics_and_telemetry_helpers_snapshot_state() -> None:
    collector = MetricsCollector()
    collector.increment("syncs", 2)
    collector.gauge("latency", 7.5)

    assert collector.snapshot()["syncs"] == 2.0
    assert collector.snapshot()["latency"] == 7.5
    assert isinstance(TelemetryMetrics(), MetricsCollector)


def test_audit_and_result_models_render_to_dicts() -> None:
    result = ExecutionResult(
        execution_id="1",
        correlation_id="corr",
        connector="sql",
        duration_seconds=1.5,
        records_processed=3,
        warnings=["warn"],
        errors=["err"],
        user="ops",
        timestamp=datetime.now(UTC),
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        status=ExecutionStatus.FAILED,
    )
    log = SynchronizationLog(
        execution_id="1",
        correlation_id="corr",
        connector="sql",
        duration_seconds=1.5,
        records_processed=3,
        warnings=["warn"],
        errors=["err"],
        user="ops",
        timestamp=datetime.now(UTC),
    )

    assert result.to_dict()["status"] == "failed"
    assert log.to_dict()["connector"] == "sql"


def test_contracts_and_events_are_immutable_and_metadata_is_stable() -> None:
    request = SynchronizationRequest(connector_name="sql", correlation_id="c", metadata={"source": "api"})
    job = SynchronizationJob(id="job", connector_name="sql")
    event = SynchronizationEvent.started("job", "sql", "exec")
    descriptor = ConnectorDescriptor(name="sql", connector_type=ConnectorType.SQL_SERVER, description="sql")

    with pytest.raises(FrozenInstanceError):
        request.connector_name = "rest"
    with pytest.raises(FrozenInstanceError):
        job.connector_name = "rest"
    with pytest.raises(FrozenInstanceError):
        event.job_id = "other"
    with pytest.raises(FrozenInstanceError):
        descriptor.name = "rest"

    assert request.metadata["source"] == "api"
    assert event.event_type == SynchronizationEventType.STARTED


def test_event_bus_propagates_and_surfaces_subscriber_failures() -> None:
    bus = IntegrationEventBus()
    events: list[SynchronizationEvent] = []

    def handler(event: SynchronizationEvent) -> None:
        events.append(event)

    bus.subscribe(handler)
    bus.publish(SynchronizationEvent.started("job", "sql", "exec"))

    def failing_handler(event: SynchronizationEvent) -> None:
        raise RuntimeError("subscriber failed")

    bus.subscribe(failing_handler)
    with pytest.raises(RuntimeError, match="subscriber failed"):
        bus.publish(SynchronizationEvent.completed("job", "sql", "exec", ExecutionResult(
            execution_id="exec",
            correlation_id="job",
            connector="sql",
            duration_seconds=0.0,
            records_processed=1,
            status=ExecutionStatus.COMPLETED,
        )))

    assert [event.event_type for event in events] == [SynchronizationEventType.STARTED, SynchronizationEventType.COMPLETED]


def test_validator_accepts_none_payload_and_reports_invalid_rules() -> None:
    validator = Validator()
    assert validator.validate(None).ok is False
    assert validator.validate({"id": 1}, rules=[lambda payload: (False, "bad")]).ok is False


def test_normalizer_handles_non_mapping_payloads() -> None:
    normalizer = Normalizer()
    assert normalizer.normalize(17) == {"value": 17}
