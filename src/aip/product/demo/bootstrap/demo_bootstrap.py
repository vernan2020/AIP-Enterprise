from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.product.demo.configuration.demo_config import DemoConfig
from aip.product.demo.exceptions import DemoBootstrapError
from aip.product.demo.status.startup_status import StartupStatus


class DemoBootstrap:
    """Bootstraps the demo product slice with startup status tracking."""

    def __init__(
        self,
        config: DemoConfig | None = None,
        *,
        source_config: Any | None = None,
    ) -> None:
        self._config = config or DemoConfig()
        # A single application-facing factory owns mode delegation.  This
        # keeps DEMO and CONFIGURED startup on the same composition path and
        # prevents a second, disconnected container from being created.
        self._factory = DemoApplicationFactory(
            self._config,
            source_config=source_config,
        )

    @property
    def factory(self) -> DemoApplicationFactory:
        return self._factory

    def bootstrap(self, correlation_id: str | None = None) -> tuple[DemoApplicationFactory, list[StartupStatus]]:
        correlation = correlation_id or f"demo-{int(time.time())}"
        steps: list[StartupStatus] = []
        for component_name, action in [
            ("configuration", lambda: None),
            ("observability", lambda: None),
            ("correlation_context", lambda: None),
            ("dependency_injection", lambda: None),
            ("security_context", lambda: None),
            ("connectors", lambda: None),
            ("scheduler", lambda: None),
            ("notifications", lambda: None),
        ]:
            started = datetime.now(timezone.utc)
            try:
                action()
                completed = datetime.now(timezone.utc)
                steps.append(
                    StartupStatus(
                        component_name=component_name,
                        status="OK",
                        duration_seconds=(completed - started).total_seconds(),
                        correlation_id=correlation,
                        started_at=started,
                        completed_at=completed,
                    )
                )
            except Exception as exc:  # pragma: no cover - defensive guard
                completed = datetime.now(timezone.utc)
                steps.append(
                    StartupStatus(
                        component_name=component_name,
                        status="FAILED",
                        duration_seconds=(completed - started).total_seconds(),
                        error=str(exc),
                        correlation_id=correlation,
                        started_at=started,
                        completed_at=completed,
                    )
                )
                raise DemoBootstrapError(f"bootstrap failed at {component_name}") from exc
        return self._factory, steps
