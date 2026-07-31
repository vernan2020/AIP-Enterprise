from __future__ import annotations

from aip.core.container import Container
from aip.product.configured.adapters.configured_health_provider import ConfiguredHealthProvider
from aip.product.configured.adapters.configured_liquidity_provider import ConfiguredLiquidityProvider
from aip.product.configured.adapters.configured_market_provider import ConfiguredMarketProvider
from aip.product.configured.adapters.configured_portfolio_provider import ConfiguredPortfolioProvider
from aip.product.configured.configuration.configured_source_config import ConfiguredSourceConfig
from aip.product.configured.protocols import MarketDataProvider, LiquidityDataProvider, PortfolioDataProvider, SourceHealthProvider
from aip.product.demo.configuration.demo_config import DemoConfig
from aip.product.demo.workflows.initial_load_workflow import InitialLoadWorkflow
from aip.product.demo.workflows.refresh_all_workflow import RefreshAllWorkflow


class ConfiguredDependencyComposition:
    def __init__(self, config: DemoConfig, source_config: ConfiguredSourceConfig | None = None) -> None:
        self._config = config
        self._source_config = source_config or ConfiguredSourceConfig()

    def compose(self, container: Container) -> Container:
        container.register_instance(DemoConfig, self._config)
        container.register_instance(ConfiguredSourceConfig, self._source_config)
        health_provider = ConfiguredHealthProvider(self._source_config)
        portfolio_provider = ConfiguredPortfolioProvider(self._config, self._source_config, health_provider)
        market_provider = ConfiguredMarketProvider(self._config, self._source_config, health_provider)
        liquidity_provider = ConfiguredLiquidityProvider(self._config, self._source_config, health_provider)

        container.register_instance(SourceHealthProvider, health_provider)
        container.register_instance(PortfolioDataProvider, portfolio_provider)
        container.register_instance(MarketDataProvider, market_provider)
        container.register_instance(LiquidityDataProvider, liquidity_provider)
        container.register_instance(ConfiguredHealthProvider, health_provider)
        container.register_instance(ConfiguredPortfolioProvider, portfolio_provider)
        container.register_instance(ConfiguredMarketProvider, market_provider)
        container.register_instance(ConfiguredLiquidityProvider, liquidity_provider)

        container.register_factory(InitialLoadWorkflow, lambda _container: InitialLoadWorkflow(
            self._config,
            portfolio_provider=_container.resolve(PortfolioDataProvider),
            market_provider=_container.resolve(MarketDataProvider),
            liquidity_provider=_container.resolve(LiquidityDataProvider),
            health_provider=_container.resolve(SourceHealthProvider),
        ))
        container.register_factory(RefreshAllWorkflow, lambda _container: RefreshAllWorkflow(
            self._config,
            portfolio_provider=_container.resolve(PortfolioDataProvider),
            market_provider=_container.resolve(MarketDataProvider),
            liquidity_provider=_container.resolve(LiquidityDataProvider),
            health_provider=_container.resolve(SourceHealthProvider),
        ))
        return container
