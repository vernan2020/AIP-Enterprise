from __future__ import annotations

from aip.core.container import Container
from aip.product.demo.adapters.demo_health_provider import DemoHealthProvider
from aip.product.demo.adapters.demo_liquidity_provider import DemoLiquidityProvider
from aip.product.demo.adapters.demo_market_provider import DemoMarketProvider
from aip.product.demo.adapters.demo_portfolio_provider import DemoPortfolioProvider
from aip.product.demo.configuration.demo_config import DemoConfig
from aip.product.demo.workflows.executive_refresh_workflow import ExecutiveRefreshWorkflow
from aip.product.demo.workflows.initial_load_workflow import InitialLoadWorkflow
from aip.product.demo.workflows.refresh_all_workflow import RefreshAllWorkflow


class DemoDependencyComposition:
    """Composes demo dependencies for the application."""

    def __init__(self, config: DemoConfig) -> None:
        self._config = config

    def compose(self, container: Container) -> Container:
        container.register_instance(DemoConfig, self._config)
        container.register_instance(DemoPortfolioProvider, DemoPortfolioProvider())
        container.register_instance(DemoMarketProvider, DemoMarketProvider())
        container.register_instance(DemoLiquidityProvider, DemoLiquidityProvider())
        container.register_instance(DemoHealthProvider, DemoHealthProvider())
        container.register_factory(InitialLoadWorkflow, lambda _container: InitialLoadWorkflow(self._config))
        container.register_factory(RefreshAllWorkflow, lambda _container: RefreshAllWorkflow(self._config))
        container.register_factory(ExecutiveRefreshWorkflow, lambda _container: ExecutiveRefreshWorkflow(self._config))
        return container
