from __future__ import annotations

from typing import Any

from aip.core.container import Container
from aip.product.demo.bootstrap.dependency_composition import DemoDependencyComposition
from aip.product.demo.configuration.demo_config import DemoConfig
from aip.product.demo.configuration.environment_loader import EnvironmentLoader
from aip.product.demo.status.system_status import SystemStatus
from aip.product.demo.workflows.executive_refresh_workflow import ExecutiveRefreshWorkflow
from aip.product.demo.workflows.initial_load_workflow import InitialLoadWorkflow
from aip.product.demo.workflows.refresh_all_workflow import RefreshAllWorkflow


class DemoApplicationFactory:
    """Creates application-facing demo services for the shell."""

    def __init__(self, config: DemoConfig | None = None) -> None:
        self._config = config or EnvironmentLoader().load()
        self._container = Container()
        DemoDependencyComposition(self._config).compose(self._container)

    @property
    def config(self) -> DemoConfig:
        return self._config

    @property
    def container(self) -> Container:
        return self._container

    def build_system_status(self) -> SystemStatus:
        return SystemStatus(
            execution_mode=self._config.execution_mode,
            environment=self._config.environment_name,
            source_states={"sql_server": "HEALTHY", "folder_watch": "HEALTHY", "bccr": "HEALTHY"},
            last_refresh=None,
            component_details={"mode": self._config.execution_mode, "demo_mode_enabled": self._config.demo_mode_enabled},
        )

    def initial_load_workflow(self) -> InitialLoadWorkflow:
        return self._container.resolve(InitialLoadWorkflow)

    def refresh_all_workflow(self) -> RefreshAllWorkflow:
        return self._container.resolve(RefreshAllWorkflow)

    def executive_refresh_workflow(self) -> ExecutiveRefreshWorkflow:
        return self._container.resolve(ExecutiveRefreshWorkflow)
