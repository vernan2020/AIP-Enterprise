from __future__ import annotations

from aip.platform.observability.correlation.correlation_context import CorrelationContext
from aip.platform.observability.health.component_health import HealthStatus
from aip.platform.observability.health.health_service import HealthService
from aip.platform.observability.logging.logger import Logger
from aip.platform.observability.metrics.metrics_registry import MetricsRegistry
from aip.platform.observability.providers.null_provider import NullProvider
from aip.platform.observability.tracing.tracer import Tracer


class TelemetryService:
    def __init__(self, *, logger: Logger | None = None, metrics: MetricsRegistry | None = None, health: HealthService | None = None, tracer: Tracer | None = None) -> None:
        self.logger = logger or Logger(provider=NullProvider())
        self.metrics = metrics or MetricsRegistry()
        self.health = health or HealthService()
        self.tracer = tracer or Tracer()

    def emit_log(self, level: str, message: str) -> None:
        context = CorrelationContext.get_current()
        self.logger.info(message, correlation_id=context.correlation_id if context else None, execution_id=context.execution_id if context else None)

    def record_counter(self, name: str, value: int = 1) -> None:
        self.metrics.counter(name).increment(value)

    def record_gauge(self, name: str, value: float) -> None:
        self.metrics.gauge(name).set(value)

    def observe_histogram(self, name: str, value: float) -> None:
        self.metrics.histogram(name).observe(value)

    def update_component_health(self, name: str, status: HealthStatus) -> None:
        self.health.update_component(name, status)

    def start_span(self, name: str) -> object:
        return self.tracer.start_span(name)

    def snapshot(self) -> dict[str, object]:
        return {"metrics": self.metrics.snapshot(), "health": self.health.snapshot()}
