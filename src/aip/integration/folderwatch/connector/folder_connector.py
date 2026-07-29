from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aip.integration.audit.execution_result import ExecutionResult, ExecutionStatus
from aip.integration.audit.synchronization_log import SynchronizationLog
from aip.integration.contracts.connector import Connector, ConnectorType
from aip.integration.events.synchronization_events import IntegrationEventBus, SynchronizationEvent, SynchronizationEventType
from aip.integration.exceptions.exceptions import IntegrationError
from aip.integration.folderwatch.configuration.folder_config import FolderWatchConfig
from aip.integration.folderwatch.connector.watcher import FolderWatcher
from aip.integration.folderwatch.contracts.file_request import FileRequest
from aip.integration.folderwatch.monitoring.folder_health import FolderHealthMonitor
from aip.integration.folderwatch.normalization.file_normalizer import FileNormalizer
from aip.integration.folderwatch.providers.filesystem_provider import FileSystemProvider
from aip.integration.folderwatch.providers.local_filesystem_provider import LocalFileSystemProvider
from aip.integration.folderwatch.synchronization.folder_synchronizer import FolderSynchronizer
from aip.integration.folderwatch.telemetry.folder_metrics import FolderMetrics
from aip.integration.folderwatch.validation.file_validator import FileValidator


class FolderWatchConnector(Connector):
    """Adapter exposing folder watch capabilities through the Integration Hub contract."""

    name: str = "folderwatch"
    description: str = "Generic folder watch connector adapter"
    connector_type: ConnectorType = ConnectorType.FOLDER_WATCH

    def __init__(
        self,
        *,
        config: FolderWatchConfig,
        provider: FileSystemProvider | None = None,
        watcher: FolderWatcher | None = None,
        validator: FileValidator | None = None,
        normalizer: FileNormalizer | None = None,
        synchronizer: FolderSynchronizer | None = None,
        health_monitor: FolderHealthMonitor | None = None,
        metrics: FolderMetrics | None = None,
        event_bus: IntegrationEventBus | None = None,
    ) -> None:
        self.config = config
        self.provider = provider or LocalFileSystemProvider()
        self.watcher = watcher or FolderWatcher(provider=self.provider, config=config)
        self.validator = validator or FileValidator()
        self.normalizer = normalizer or FileNormalizer()
        self.synchronizer = synchronizer or FolderSynchronizer(provider=self.provider, validator=self.validator, normalizer=self.normalizer)
        self.health_monitor = health_monitor or FolderHealthMonitor()
        self.metrics = metrics or FolderMetrics()
        self.event_bus = event_bus
        self._connected = False

    def connect(self) -> None:
        self._connected = True
        self.health_monitor.record_state(self.name, "running")
        self._publish(SynchronizationEvent.connected(self.name, self.name, self.name))

    def disconnect(self) -> None:
        self._connected = False
        self.watcher.stop()
        self.health_monitor.record_state(self.name, "stopped")
        self._publish(SynchronizationEvent.disconnected(self.name, self.name, self.name))

    def health(self) -> bool:
        return self._connected

    def synchronize(self, request: Any, correlation_id: str | None = None, user: str = "system", cancellation_token: str | None = None) -> ExecutionResult:
        if not self._connected:
            self.connect()
        if cancellation_token == "cancelled":
            raise IntegrationError("Synchronization cancelled")
        if isinstance(request, FileRequest):
            validation_result = self.validator.validate(request)
            if not validation_result.ok:
                raise IntegrationError("Validation failed")
            normalized = self.normalizer.normalize(request.to_dict())
            self.metrics.increment("files")
            self.health_monitor.record_processed(self.name, 1)
            return ExecutionResult(
                execution_id=f"{self.name}-{datetime.now(UTC).timestamp()}",
                correlation_id=correlation_id or "system",
                connector=self.name,
                duration_seconds=1.0,
                records_processed=1,
                warnings=[],
                errors=[],
                user=user,
                timestamp=datetime.now(UTC),
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
                status=ExecutionStatus.COMPLETED,
            )
        raise IntegrationError("Validation failed")

    def validate(self, payload: object) -> Any:
        if isinstance(payload, FileRequest):
            return self.validator.validate(payload)
        raise IntegrationError("Validation failed")

    def normalize(self, payload: object) -> object:
        if isinstance(payload, FileRequest):
            return self.normalizer.normalize(payload.to_dict())
        return self.normalizer.normalize(payload)

    def audit(self, log: SynchronizationLog) -> None:
        self._publish(SynchronizationEvent.synchronization_started(self.name, self.name, log.execution_id))
        self._publish(SynchronizationEvent.synchronization_completed(self.name, self.name, log.execution_id))

    def _publish(self, event: SynchronizationEvent) -> None:
        if self.event_bus is not None:
            self.event_bus.publish(event)
