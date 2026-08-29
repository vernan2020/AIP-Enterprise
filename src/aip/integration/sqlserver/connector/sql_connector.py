from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aip.integration.audit.execution_result import ExecutionResult, ExecutionStatus
from aip.integration.audit.synchronization_log import SynchronizationLog
from aip.integration.contracts.connector import Connector, ConnectorType
from aip.integration.events.synchronization_events import (
    IntegrationEventBus,
    SynchronizationEvent,
)
from aip.integration.exceptions.exceptions import IntegrationError
from aip.integration.sqlserver.configuration.sql_config import SQLServerConfig
from aip.integration.sqlserver.connector.connection_factory import (
    DefaultSQLServerConnectionFactory,
    SQLServerConnectionFactory,
)
from aip.integration.sqlserver.connector.connection_pool import ConnectionPool
from aip.integration.sqlserver.contracts.sql_request import SQLRequest
from aip.integration.sqlserver.driver.driver_adapter import SQLServerDriverAdapter
from aip.integration.sqlserver.monitoring.sql_health import SQLHealthMonitor
from aip.integration.sqlserver.synchronization.sql_synchronizer import SQLSynchronizer
from aip.integration.sqlserver.telemetry.sql_metrics import SQLMetrics
from aip.integration.sqlserver.validation.sql_validator import SQLValidator


class SQLServerConnector(Connector):
    """Infrastructure adapter that exposes SQL Server access through the Integration Hub contract."""

    name: str = "sqlserver"
    description: str = "Generic SQL Server connector adapter"
    connector_type: ConnectorType = ConnectorType.SQL_SERVER

    def __init__(
        self,
        *,
        config: SQLServerConfig,
        connection_factory: SQLServerConnectionFactory | None = None,
        pool: ConnectionPool | None = None,
        validator: SQLValidator | None = None,
        synchronizer: SQLSynchronizer | None = None,
        health_monitor: SQLHealthMonitor | None = None,
        metrics: SQLMetrics | None = None,
        event_bus: IntegrationEventBus | None = None,
        driver: SQLServerDriverAdapter | None = None,
    ) -> None:
        self.config = config
        self.connection_factory = connection_factory or DefaultSQLServerConnectionFactory(
            config, driver=driver
        )
        self.pool = pool or ConnectionPool(
            factory=self.connection_factory, max_size=config.pool_size
        )
        self.validator = validator or SQLValidator()
        self.synchronizer = synchronizer or SQLSynchronizer(
            pool=self.pool,
            validator=self.validator,
            max_retries=config.max_retries,
            retry_delay_seconds=config.retry_delay_seconds,
        )
        self.health_monitor = health_monitor or SQLHealthMonitor()
        self.metrics = metrics or SQLMetrics()
        self.event_bus = event_bus
        self._connected = False

    def connect(self) -> None:
        self._connected = True
        self.health_monitor.record_connection(self.name, healthy=True, latency_ms=0.0, retries=0)
        self._publish(SynchronizationEvent.connected(self.name, self.name, self.name))

    def disconnect(self) -> None:
        self._connected = False
        self._publish(SynchronizationEvent.disconnected(self.name, self.name, self.name))

    def health(self) -> bool:
        return self._connected

    def synchronize(
        self, request: Any, correlation_id: str | None = None, user: str = "system"
    ) -> ExecutionResult:
        if not self._connected:
            self.connect()
        validation_result = self.validator.validate(request)
        if not validation_result.ok:
            raise IntegrationError("Validation failed")
        sql_result = self.synchronizer.synchronize(request)
        self.metrics.increment("queries")
        self.health_monitor.record_execution(self.name, rows=sql_result.row_count, elapsed_ms=1.0)
        if sql_result.status != ExecutionStatus.COMPLETED:
            if sql_result.status == ExecutionStatus.CANCELLED:
                raise IntegrationError("Synchronization cancelled")
            raise IntegrationError("Synchronization failed")
        return ExecutionResult(
            execution_id=f"{self.name}-{datetime.now(UTC).timestamp()}",
            correlation_id=correlation_id or "system",
            connector=self.name,
            duration_seconds=1.0,
            records_processed=sql_result.row_count,
            warnings=sql_result.warnings,
            errors=sql_result.errors,
            user=user,
            timestamp=datetime.now(UTC),
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            status=(
                ExecutionStatus.COMPLETED
                if sql_result.status == ExecutionStatus.COMPLETED
                else ExecutionStatus.FAILED
            ),
        )

    def validate(self, payload: object) -> Any:
        if isinstance(payload, SQLRequest):
            validation_result = self.validator.validate(payload)
            if not validation_result.ok:
                raise IntegrationError("Validation failed")
            return validation_result
        validation_result = self.validator.validate(
            SQLRequest(query_name="", query_text="", parameters={})
        )
        if not validation_result.ok:
            raise IntegrationError("Validation failed")
        return validation_result

    def normalize(self, payload: object) -> object:
        return payload

    def audit(self, log: SynchronizationLog) -> None:
        self._publish(
            SynchronizationEvent.synchronization_started(self.name, self.name, log.execution_id)
        )
        self._publish(
            SynchronizationEvent.synchronization_completed(self.name, self.name, log.execution_id)
        )

    def _publish(self, event: SynchronizationEvent) -> None:
        if self.event_bus is not None:
            self.event_bus.publish(event)
