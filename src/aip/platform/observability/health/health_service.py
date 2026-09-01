from __future__ import annotations

from aip.platform.observability.health.component_health import ComponentHealth, HealthStatus


class HealthService:
    def __init__(self) -> None:
        self._components: dict[str, ComponentHealth] = {}

    def update_component(
        self, name: str, status: HealthStatus, details: dict[str, object] | None = None
    ) -> None:
        self._components[name] = ComponentHealth(name=name, status=status, details=details or {})

    def snapshot(self) -> dict[str, dict[str, object]]:
        return {name: component.to_dict() for name, component in self._components.items()}

    def aggregate_status(self) -> HealthStatus:
        if not self._components:
            return HealthStatus.UNKNOWN
        statuses = {component.status for component in self._components.values()}
        if HealthStatus.UNAVAILABLE in statuses:
            return HealthStatus.UNAVAILABLE
        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        if HealthStatus.UNKNOWN in statuses:
            return HealthStatus.UNKNOWN
        return HealthStatus.HEALTHY
