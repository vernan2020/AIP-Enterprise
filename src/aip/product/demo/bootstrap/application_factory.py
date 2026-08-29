from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any

from aip.core.container import Container
from aip.product.demo.bootstrap.dependency_composition import (
    DemoDependencyComposition,
)
from aip.product.demo.configuration.demo_config import DemoConfig
from aip.product.demo.configuration.environment_loader import (
    EnvironmentLoader,
)
from aip.product.demo.status.system_status import SystemStatus
from aip.product.demo.workflows.executive_refresh_workflow import (
    ExecutiveRefreshWorkflow,
)
from aip.product.demo.workflows.initial_load_workflow import (
    InitialLoadWorkflow,
)
from aip.product.demo.workflows.refresh_all_workflow import (
    RefreshAllWorkflow,
)


class DemoApplicationFactory:
    """
    Creates application-facing services for AIP Enterprise.

    En modo CONFIGURED mantiene una instancia de ConfiguredSourceConfig
    y un único container de sesión. Los cambios de fecha se propagan mediante
    un contexto de valoración compartido sin reconstruir infraestructura.
    """

    def __init__(
        self,
        config: DemoConfig | None = None,
        source_config: Any | None = None,
    ) -> None:
        self._config = config or EnvironmentLoader().load()

        self._container = Container()

        self._configured_factory = None
        self._configured_source_config = None

        if self._config.execution_mode == "CONFIGURED":
            self._configure_configured_mode(source_config)

        else:
            DemoDependencyComposition(self._config).compose(self._container)

    # =============================================================
    # CONFIGURED MODE
    # =============================================================

    def _configure_configured_mode(
        self,
        source_config: Any | None = None,
    ) -> None:
        """
        Construye o reconstruye la composición CONFIGURED.

        No modifica ConfiguredSourceConfig en sitio porque dicha
        configuración es inmutable.
        """

        from aip.product.configured.bootstrap.configured_application_factory import (
            ConfiguredApplicationFactory,
        )
        from aip.product.configured.configuration.configured_source_config import (
            ConfiguredSourceConfig,
        )

        configured_source_config = (
            source_config if source_config is not None else self._config.source_config
        )

        if isinstance(
            configured_source_config,
            dict,
        ):
            configured_source_config = ConfiguredSourceConfig.from_safe_dict(
                configured_source_config
            )

        self._configured_source_config = configured_source_config

        self._configured_factory = ConfiguredApplicationFactory(
            self._config,
            configured_source_config,
        )

        self._container = self._configured_factory.container

        self._config = self._configured_factory.config

    # =============================================================
    # VALUATION DATE
    # =============================================================

    def set_data_cutoff_date(
        self,
        value: date,
    ) -> None:
        """Change the active valuation date without rebuilding CONFIGURED.

        CONFIGURED mode keeps the dependency container and long-lived caches
        alive.  A shared ValuationDateContext is the authoritative runtime
        cutoff for providers and valuation-sensitive services.  Immutable
        configuration objects are still replaced so status/diagnostics expose
        the current date, but no infrastructure or historical repository is
        recreated.
        """

        if not isinstance(value, date):
            raise TypeError("value must be datetime.date")

        if value == self._config.data_cutoff_date:
            return

        self._config = replace(
            self._config,
            data_cutoff_date=value,
        )

        if self._config.execution_mode != "CONFIGURED":
            return

        configured_source_config = self._configured_source_config
        if configured_source_config is None:
            raise RuntimeError("Configured source configuration is not available")

        metadata = dict(configured_source_config.metadata or {})
        metadata["data_cutoff_date"] = value.isoformat()
        configured_source_config = replace(
            configured_source_config,
            metadata=metadata,
        )
        self._configured_source_config = configured_source_config

        current_source_payload = self._config.source_config
        if isinstance(current_source_payload, dict):
            new_source_payload = dict(current_source_payload)
            new_source_payload["data_cutoff_date"] = value.isoformat()
            self._config = replace(
                self._config,
                source_config=new_source_payload,
            )

        if self._configured_factory is None:
            raise RuntimeError("Configured application factory is not available")

        # Preserve the container and all long-lived service instances.
        from aip.product.configured.context.valuation_date_context import (
            ValuationDateContext,
        )

        valuation_context = self._container.resolve(ValuationDateContext)
        valuation_context.set(value)

        # Keep factory metadata synchronized for status and diagnostics only.
        self._configured_factory._config = self._config
        self._configured_factory._source_config = configured_source_config

    # =============================================================
    # PUBLIC PROPERTIES
    # =============================================================

    @property
    def config(
        self,
    ) -> DemoConfig:
        return self._config

    @property
    def container(
        self,
    ) -> Container:
        return self._container

    @property
    def configured_source_config(
        self,
    ) -> Any | None:
        return self._configured_source_config

    # =============================================================
    # STATUS
    # =============================================================

    def build_system_status(
        self,
    ) -> SystemStatus:
        if self._configured_factory is not None:
            return self._configured_factory.build_system_status()

        return SystemStatus(
            execution_mode=(self._config.execution_mode),
            environment=(self._config.environment_name),
            source_states={
                "sql_server": "HEALTHY",
                "folder_watch": "HEALTHY",
                "bccr": "HEALTHY",
            },
            last_refresh=None,
            component_details={
                "mode": (self._config.execution_mode),
                "demo_mode_enabled": (self._config.demo_mode_enabled),
            },
        )

    # =============================================================
    # WORKFLOWS
    # =============================================================

    def initial_load_workflow(
        self,
    ) -> InitialLoadWorkflow:
        if self._configured_factory is not None:
            return self._configured_factory.initial_load_workflow()

        return self._container.resolve(InitialLoadWorkflow)

    def refresh_all_workflow(
        self,
    ) -> RefreshAllWorkflow:
        if self._configured_factory is not None:
            return self._configured_factory.refresh_all_workflow()

        return self._container.resolve(RefreshAllWorkflow)

    def executive_refresh_workflow(
        self,
    ) -> ExecutiveRefreshWorkflow:
        if self._configured_factory is not None:
            return self._configured_factory.initial_load_workflow()  # type: ignore[return-value]

        return self._container.resolve(ExecutiveRefreshWorkflow)
