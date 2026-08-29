from __future__ import annotations

from aip.platform.observability.audit.observability_audit import ObservabilityAudit
from aip.platform.observability.events.observability_events import ObservabilityEvent
from aip.platform.observability.health.component_health import HealthStatus
from aip.platform.observability.health.health_service import HealthService
from aip.platform.observability.metrics.metrics_registry import MetricsRegistry


class MonitoringService:
    def __init__(
        self,
        *,
        audit: ObservabilityAudit | None = None,
        health: HealthService | None = None,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self.audit = audit or ObservabilityAudit()
        self.health = health or HealthService()
        self.metrics = metrics or MetricsRegistry()

    def record_event(self, event: ObservabilityEvent) -> None:
        self.audit.record(event)

    def record_health(self, name: str, status: HealthStatus) -> None:
        self.health.update_component(name, status)

    def record_metric(self, name: str, value: float) -> None:
        self.metrics.counter(name).increment(int(value))

    def snapshot(self) -> dict[str, object]:
        return {
            "events": [event.to_dict() for event in self.audit.entries],
            "health": self.health.snapshot(),
            "metrics": self.metrics.snapshot(),
        }
