from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from aip.integration.audit.execution_result import ExecutionResult, ExecutionStatus
from aip.integration.audit.synchronization_log import SynchronizationLog
from aip.integration.contracts.connector import ConnectorProtocol, ConnectorType
from aip.integration.contracts.synchronization import SynchronizationRequest
from aip.integration.events.synchronization_events import IntegrationEventBus, SynchronizationEvent
from aip.integration.exceptions.exceptions import IntegrationError
from aip.integration.monitoring.health_monitor import HealthMonitor
from aip.integration.normalization.normalizer import Normalizer
from aip.integration.telemetry.metrics import MetricsCollector
from aip.integration.validation.validator import ValidationIssue, ValidationResult, Validator


@dataclass(slots=True)
class IntegrationHub:
    """Single entry point for external integrations with no business logic."""

    connectors: list[ConnectorProtocol] = field(default_factory=list)
    validator: Validator = field(default_factory=Validator)
    normalizer: Normalizer = field(default_factory=Normalizer)
    monitor: HealthMonitor = field(default_factory=HealthMonitor)
    metrics: MetricsCollector = field(default_factory=MetricsCollector)
    event_bus: IntegrationEventBus = field(default_factory=IntegrationEventBus)
    audit_log: list[SynchronizationLog] = field(default_factory=list)

    def register_connector(self, connector: ConnectorProtocol) -> None:
        self.connectors.append(connector)

    def subscribe(self, handler: Callable[[SynchronizationEvent], None]) -> None:
        self.event_bus.subscribe(handler)

    def run_synchronization(self, *, correlation_id: str, user: str = "system") -> ExecutionResult:
        if not self.connectors:
            raise IntegrationError("No connectors registered")

        connector = self.connectors[0]
        execution_id = f"sync-{len(self.audit_log) + 1}"
        started_at = datetime.now(UTC)
        self._publish(SynchronizationEvent.started(correlation_id, connector.name, execution_id))
        self.monitor.record_health(connector.name, healthy=connector.health(), availability=1.0)

        try:
            connector.connect()
            payload = {"connector": connector.name, "correlation_id": correlation_id}
            validation_result = connector.validate(payload)
            if not validation_result.ok:
                raise IntegrationError("Validation failed")
            normalized = connector.normalize(payload)
            request = SynchronizationRequest(
                connector_name=connector.name,
                correlation_id=correlation_id,
                user=user,
                records_expected=1,
                metadata={"normalized": normalized},
            )
            records_processed = connector.synchronize(request)
            duration = 0.0
            log = SynchronizationLog(
                execution_id=execution_id,
                correlation_id=correlation_id,
                connector=connector.name,
                duration_seconds=duration,
                records_processed=records_processed,
                warnings=[],
                errors=[],
                user=user,
                timestamp=datetime.now(UTC),
            )
            connector.audit(log)
            self.audit_log.append(log)
            self.monitor.record_execution(connector.name, success=True, records=records_processed)
            self.metrics.increment("syncs", 1)
            self.monitor.record_sync(connector.name)
            self._publish(SynchronizationEvent.completed(correlation_id, connector.name, execution_id, ExecutionResult(
                execution_id=execution_id,
                correlation_id=correlation_id,
                connector=connector.name,
                duration_seconds=duration,
                records_processed=records_processed,
                warnings=[],
                errors=[],
                user=user,
                started_at=started_at,
                finished_at=datetime.now(UTC),
                status=ExecutionStatus.COMPLETED,
            )))
            return ExecutionResult(
                execution_id=execution_id,
                correlation_id=correlation_id,
                connector=connector.name,
                duration_seconds=duration,
                records_processed=records_processed,
                warnings=[],
                errors=[],
                user=user,
                started_at=started_at,
                finished_at=datetime.now(UTC),
                status=ExecutionStatus.COMPLETED,
            )
        except Exception as exc:  # noqa: BLE001
            self.monitor.record_execution(connector.name, success=False, records=0)
            self.metrics.increment("sync_failures", 1)
            self._publish(SynchronizationEvent.failed(correlation_id, connector.name, execution_id, str(exc)))
            raise IntegrationError(str(exc)) from exc
        finally:
            connector.disconnect()

    def list_connectors(self) -> list[ConnectorType]:
        return [ConnectorType.FUTURE] if not self.connectors else [ConnectorType.FUTURE]

    def _publish(self, event: SynchronizationEvent) -> None:
        self.event_bus.publish(event)
