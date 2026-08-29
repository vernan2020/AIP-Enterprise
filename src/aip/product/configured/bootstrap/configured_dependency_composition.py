from __future__ import annotations

from aip.product.configured.services.configured_portfolio_dv01_service import (
    ConfiguredPortfolioDV01Service,
)
from aip.product.configured.services.configured_portfolio_rate_shock_service import (
    ConfiguredPortfolioRateShockService,
)

from aip.core.container import Container
from aip.integration.bccr.configuration.bccr_config import BCCRConfig
from aip.integration.bccr.connector.bccr_connector import BCCRConnector
from aip.integration.bccr.providers.urllib_http_provider import UrllibHTTPProvider
from aip.product.configured.adapters.configured_economic_indicators_provider import (
    ConfiguredEconomicIndicatorsProvider,
)
from aip.product.configured.adapters.configured_health_provider import (
    ConfiguredHealthProvider,
)
from aip.product.configured.adapters.configured_liquidity_provider import (
    ConfiguredLiquidityProvider,
)
from aip.product.configured.adapters.configured_market_provider import (
    ConfiguredMarketProvider,
)
from aip.product.configured.adapters.configured_portfolio_provider import (
    ConfiguredPortfolioProvider,
)
from aip.product.configured.configuration.configured_source_config import (
    ConfiguredSourceConfig,
)
from aip.product.configured.context.valuation_date_context import ValuationDateContext
from aip.product.configured.protocols import (
    EconomicIndicatorsProvider,
    LiquidityDataProvider,
    MarketDataProvider,
    PortfolioDataProvider,
    SourceHealthProvider,
)
from aip.product.configured.services.configured_macro_intelligence_service import (
    ConfiguredMacroIntelligenceService,
)
from aip.product.configured.services.configured_portfolio_var_service import (
    ConfiguredPortfolioVaRService,
)
from aip.product.demo.configuration.demo_config import DemoConfig
from aip.product.demo.workflows.executive_refresh_workflow import ExecutiveRefreshWorkflow
from aip.product.demo.workflows.initial_load_workflow import (
    InitialLoadWorkflow,
)
from aip.product.demo.workflows.refresh_all_workflow import (
    RefreshAllWorkflow,
)


class ConfiguredDependencyComposition:
    """Composition root for CONFIGURED execution mode."""

    def __init__(
        self,
        config: DemoConfig,
        source_config: ConfiguredSourceConfig | None = None,
    ) -> None:
        self._config = config
        self._source_config = source_config or ConfiguredSourceConfig()

    def compose(
        self,
        container: Container,
    ) -> Container:
        # =========================================================
        # CONFIGURATION
        # =========================================================

        container.register_instance(
            DemoConfig,
            self._config,
        )

        container.register_instance(
            ConfiguredSourceConfig,
            self._source_config,
        )

        # =========================================================
        # INFRASTRUCTURE / DATA PROVIDERS
        # =========================================================

        health_provider = ConfiguredHealthProvider(self._source_config)

        macro_intelligence_service = ConfiguredMacroIntelligenceService()

        bccr_config = BCCRConfig(
            base_url=(self._source_config.bccr.base_url or "https://apim.bccr.fi.cr"),
            indicators=list(
                self._source_config.bccr.series_config
                or self._source_config.bccr.indicator_configuration
                or ("FX",)
            ),
            timeout_seconds=self._source_config.bccr.timeout_seconds,
            retry_attempts=self._source_config.bccr.retries,
            user_agent="Mozilla/5.0",
            name=self._source_config.bccr.name,
            email=self._source_config.bccr.email,
            token=self._source_config.bccr.token,
        )

        bccr_connector = BCCRConnector(
            config=bccr_config,
            provider=UrllibHTTPProvider(),
        )

        economic_indicators_provider = ConfiguredEconomicIndicatorsProvider(
            bccr_config=bccr_config,
        )

        valuation_date_context = ValuationDateContext(self._config.data_cutoff_date)

        portfolio_provider = ConfiguredPortfolioProvider(
            self._config,
            self._source_config,
            health_provider,
            valuation_date_context=valuation_date_context,
        )

        portfolio_var_service = ConfiguredPortfolioVaRService(
            self._config,
            self._source_config,
            portfolio_provider,
            valuation_date_context=valuation_date_context,
        )

        portfolio_dv01_service = ConfiguredPortfolioDV01Service(portfolio_provider)

        portfolio_rate_shock_service = ConfiguredPortfolioRateShockService(portfolio_provider)

        market_provider = ConfiguredMarketProvider(
            self._config,
            self._source_config,
            health_provider,
            portfolio_provider=portfolio_provider,
            valuation_date_context=valuation_date_context,
        )

        liquidity_provider = ConfiguredLiquidityProvider(
            self._config,
            self._source_config,
            health_provider,
            portfolio_provider=portfolio_provider,
            valuation_date_context=valuation_date_context,
        )

        container.register_instance(
            ValuationDateContext,
            valuation_date_context,
        )

        # =========================================================
        # PROTOCOL REGISTRATIONS
        # =========================================================

        container.register_instance(
            SourceHealthProvider,
            health_provider,
        )

        container.register_instance(
            PortfolioDataProvider,
            portfolio_provider,
        )

        container.register_instance(
            MarketDataProvider,
            market_provider,
        )

        container.register_instance(
            LiquidityDataProvider,
            liquidity_provider,
        )

        container.register_instance(
            EconomicIndicatorsProvider,
            economic_indicators_provider,
        )

        # =========================================================
        # CONCRETE REGISTRATIONS
        # =========================================================

        container.register_instance(
            ConfiguredHealthProvider,
            health_provider,
        )

        container.register_instance(
            ConfiguredEconomicIndicatorsProvider,
            economic_indicators_provider,
        )

        container.register_instance(
            BCCRConfig,
            bccr_config,
        )

        container.register_instance(
            BCCRConnector,
            bccr_connector,
        )

        container.register_instance(
            ConfiguredPortfolioProvider,
            portfolio_provider,
        )

        container.register_instance(
            ConfiguredMarketProvider,
            market_provider,
        )

        container.register_instance(
            ConfiguredLiquidityProvider,
            liquidity_provider,
        )
        container.register_instance(
            ConfiguredPortfolioVaRService,
            portfolio_var_service,
        )

        container.register_instance(
            ConfiguredPortfolioDV01Service,
            portfolio_dv01_service,
        )

        container.register_instance(
            ConfiguredPortfolioRateShockService,
            portfolio_rate_shock_service,
        )

        container.register_instance(
            ConfiguredMacroIntelligenceService,
            macro_intelligence_service,
        )

        # =========================================================
        # WORKFLOWS
        # =========================================================

        container.register_factory(
            InitialLoadWorkflow,
            lambda _container: InitialLoadWorkflow(
                self._config,
                portfolio_provider=_container.resolve(PortfolioDataProvider),
                market_provider=_container.resolve(MarketDataProvider),
                liquidity_provider=_container.resolve(LiquidityDataProvider),
                health_provider=_container.resolve(SourceHealthProvider),
            ),
        )

        container.register_factory(
            RefreshAllWorkflow,
            lambda _container: RefreshAllWorkflow(
                self._config,
                portfolio_provider=_container.resolve(PortfolioDataProvider),
                market_provider=_container.resolve(MarketDataProvider),
                liquidity_provider=_container.resolve(LiquidityDataProvider),
                health_provider=_container.resolve(SourceHealthProvider),
                valuation_date_context=_container.resolve(ValuationDateContext),
            ),
        )

        container.register_factory(
            ExecutiveRefreshWorkflow,
            lambda _container: ExecutiveRefreshWorkflow(
                self._config,
                valuation_date_context=_container.resolve(ValuationDateContext),
            ),
        )

        self._validate_required_services(container)
        return container

    @staticmethod
    def _validate_required_services(container: Container) -> None:
        required_services = (
            SourceHealthProvider,
            PortfolioDataProvider,
            MarketDataProvider,
            LiquidityDataProvider,
            EconomicIndicatorsProvider,
            ConfiguredPortfolioVaRService,
            ConfiguredPortfolioDV01Service,
            ConfiguredPortfolioRateShockService,
            BCCRConfig,
            BCCRConnector,
            ValuationDateContext,
            RefreshAllWorkflow,
            ExecutiveRefreshWorkflow,
        )
        for service_type in required_services:
            container.resolve(service_type)
