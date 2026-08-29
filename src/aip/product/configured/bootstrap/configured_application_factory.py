from __future__ import annotations

from aip.core.container import Container
from aip.product.configured.bootstrap.configured_dependency_composition import ConfiguredDependencyComposition
from aip.product.configured.configuration.configured_source_config import ConfiguredSourceConfig
from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.product.demo.configuration.demo_config import DemoConfig
from aip.product.demo.status.system_status import SystemStatus
from aip.product.demo.workflows.initial_load_workflow import InitialLoadWorkflow
from aip.product.demo.workflows.refresh_all_workflow import RefreshAllWorkflow
from aip.product.demo.workflows.executive_refresh_workflow import ExecutiveRefreshWorkflow


class ConfiguredApplicationFactory(DemoApplicationFactory):
    def __init__(self, config: DemoConfig | None = None, source_config: ConfiguredSourceConfig | None = None) -> None:
        self._config = config or DemoConfig(execution_mode="CONFIGURED", demo_mode_enabled=False)
        self._source_config = source_config or ConfiguredSourceConfig()
        self._container = Container()
        ConfiguredDependencyComposition(self._config, self._source_config).compose(self._container)

    @property
    def config(self) -> DemoConfig:
        return self._config

    @property
    def container(self) -> Container:
        return self._container

    def update_runtime_metadata(
        self,
        *,
        config: DemoConfig,
        source_config: ConfiguredSourceConfig,
    ) -> None:
        """Synchronize immutable runtime metadata without rebuilding the container."""
        self._config = config
        self._source_config = source_config

    def build_system_status(self) -> SystemStatus:
        return SystemStatus(
            execution_mode=self._config.execution_mode,
            environment=self._config.environment_name,
            source_states={
                "sql_server": "HEALTHY" if self._source_config.sql_server.enabled else "DEGRADED",
                "folder_watch": "HEALTHY" if self._source_config.folder_watch.enabled else "DEGRADED",
                "bccr": "HEALTHY" if self._source_config.bccr.enabled else "DEGRADED",
            },
            last_refresh=None,
            component_details={"mode": self._config.execution_mode, "demo_mode_enabled": self._config.demo_mode_enabled},
        )

    def initial_load_workflow(self) -> InitialLoadWorkflow:
        return self._container.resolve(InitialLoadWorkflow)

    def refresh_all_workflow(self) -> RefreshAllWorkflow:
        return self._container.resolve(RefreshAllWorkflow)

    def executive_refresh_workflow(self) -> ExecutiveRefreshWorkflow:
        return self._container.resolve(ExecutiveRefreshWorkflow)
