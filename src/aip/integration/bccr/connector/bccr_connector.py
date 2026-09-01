from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aip.integration.audit.execution_result import ExecutionResult, ExecutionStatus
from aip.integration.audit.synchronization_log import SynchronizationLog
from aip.integration.bccr.configuration.bccr_config import BCCRConfig
from aip.integration.bccr.connector.cache import BCCRCache
from aip.integration.bccr.connector.http_client import HTTPClient
from aip.integration.bccr.contracts.request import BCCRRequest
from aip.integration.bccr.monitoring.bccr_health import BCCRHealthMonitor
from aip.integration.bccr.normalization.response_normalizer import ResponseNormalizer
from aip.integration.bccr.providers.http_provider import HTTPProvider
from aip.integration.bccr.synchronization.bccr_synchronizer import BCCRSynchronizer
from aip.integration.bccr.telemetry.bccr_metrics import BCCRMetrics
from aip.integration.bccr.validation.response_validator import ResponseValidator
from aip.integration.contracts.connector import Connector, ConnectorType
from aip.integration.events.synchronization_events import IntegrationEventBus, SynchronizationEvent
from aip.integration.exceptions.exceptions import IntegrationError


class BCCRConnector(Connector):
    """Adapter exposing BCCR public indicator retrieval through the integration hub."""

    name: str = "bccr"
    description: str = "Banco Central de Costa Rica public indicator connector"
    connector_type: ConnectorType = ConnectorType.REST_API

    def __init__(
        self,
        *,
        config: BCCRConfig,
        provider: HTTPProvider | None = None,
        validator: ResponseValidator | None = None,
        normalizer: ResponseNormalizer | None = None,
        synchronizer: BCCRSynchronizer | None = None,
        health_monitor: BCCRHealthMonitor | None = None,
        metrics: BCCRMetrics | None = None,
        event_bus: IntegrationEventBus | None = None,
        cache: BCCRCache | None = None,
    ) -> None:
        self.config = config
        self.provider = provider
        self.validator = validator or ResponseValidator()
        self.normalizer = normalizer or ResponseNormalizer()
        self.health_monitor = health_monitor or BCCRHealthMonitor()
        self.metrics = metrics or BCCRMetrics()
        self.event_bus = event_bus
        self.cache = cache or BCCRCache(ttl_seconds=config.cache_ttl_seconds)
        self._connected = False
        self.synchronizer = synchronizer or BCCRSynchronizer(
            client=HTTPClient(
                provider=provider or self._default_provider(),
                timeout_seconds=config.timeout_seconds,
            ),
            validator=self.validator,
            normalizer=self.normalizer,
        )

    def connect(self) -> None:
        self._connected = True
        self.health_monitor.record_state(self.name, "running")
        self._publish(SynchronizationEvent.connected(self.name, self.name, self.name))

    def disconnect(self) -> None:
        self._connected = False
        self.health_monitor.record_state(self.name, "stopped")
        self._publish(SynchronizationEvent.disconnected(self.name, self.name, self.name))

    def health(self) -> bool:
        return self._connected

    def synchronize(
        self,
        request: Any,
        correlation_id: str | None = None,
        user: str = "system",
        cancellation_token: str | None = None,
    ) -> ExecutionResult:
        if not self._connected:
            self.connect()
        if cancellation_token == "cancelled":
            raise IntegrationError("Synchronization cancelled")
        if isinstance(request, BCCRRequest):
            validation_result = self.validator.validate(request)
            if not validation_result.ok:
                raise IntegrationError("Validation failed")
            cache_key = request.indicator_codes[0] if request.indicator_codes else "default"
            payload = self.cache.get(cache_key)
            if payload is None:
                try:
                    result = self.synchronizer.synchronize(
                        request, cancellation_token=cancellation_token
                    )
                except (TimeoutError, ConnectionError) as exc:
                    self.health_monitor.record_failure(self.name)
                    raise IntegrationError(str(exc)) from exc
                self.cache.set(cache_key, {"status": result.status.value})
                self.metrics.increment("requests")
                self.health_monitor.record_success(self.name, 1)
                return ExecutionResult(
                    execution_id=f"{self.name}-{datetime.now(UTC).timestamp()}",
                    correlation_id=correlation_id or "system",
                    connector=self.name,
                    duration_seconds=1.0,
                    records_processed=1 if result.status == ExecutionStatus.COMPLETED else 0,
                    warnings=[],
                    errors=[],
                    user=user,
                    timestamp=datetime.now(UTC),
                    started_at=datetime.now(UTC),
                    finished_at=datetime.now(UTC),
                    status=result.status,
                )
            self.metrics.increment("requests")
            self.health_monitor.record_success(self.name, 1)
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
        if isinstance(payload, BCCRRequest):
            return self.validator.validate(payload)
        raise IntegrationError("Validation failed")

    def normalize(self, payload: object) -> object:
        if isinstance(payload, BCCRRequest):
            return self.normalizer.normalize(payload.to_dict())
        return self.normalizer.normalize(payload)

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

    def _default_provider(self) -> HTTPProvider:
        class DefaultProvider(HTTPProvider):
            def get(
                self, url: str, *, timeout: float, headers: dict[str, str] | None = None
            ) -> dict[str, Any]:
                return {"indicators": []}

        return DefaultProvider()
