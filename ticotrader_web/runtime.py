"""Reuse the audited desktop presenters; never replace missing source values."""

import os
from dataclasses import asdict, replace
from datetime import date
from threading import RLock

from ticotrader_web import connections


class Runtime:
    def __init__(self, source_config=None):
        self._source_config = source_config
        self.lock = RLock()
        self._factory = None

    @property
    def factory(self):
        if self._factory is None:
            from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
            from aip.product.demo.configuration.environment_loader import EnvironmentLoader

            loader = EnvironmentLoader()
            # CONFIGURED only. No synthetic/demo observations in this application.
            if self._source_config is not None:
                source = self._source_config
            else:
                source = loader.load_source_config()
                personal = connections.read()
                source = replace(
                    source,
                    bccr=replace(
                        source.bccr,
                        token=personal.get("bccr_token")
                        or os.getenv("TICOTRADER_BCCR_TOKEN")
                        or source.bccr.token,
                        email=personal.get("bccr_email")
                        or os.getenv("TICOTRADER_BCCR_EMAIL")
                        or source.bccr.email,
                        name=personal.get("bccr_name") or "TicoTrader",
                    ),
                )
            # These two pages require public economic and financial sources, not
            # the user's private portfolio, SQL, CONFIA or investment masters.
            source = replace(
                source,
                sql_server=replace(source.sql_server, enabled=False),
                folder_watch=replace(
                    source.folder_watch, enabled=False, portfolio_root=None, icl_root=None
                ),
                xml_confia=replace(source.xml_confia, enabled=False),
                vector=replace(source.vector, enabled=False),
                curves=replace(source.curves, enabled=False),
            )
            from aip.product.demo.configuration.demo_config import DemoConfig

            config = replace(
                DemoConfig() if self._source_config is not None else loader.load(),
                execution_mode="CONFIGURED",
                demo_mode_enabled=False,
                environment_name="ticotrader",
                sql_connector_enabled=False,
                folder_watch_enabled=False,
                source_config=source.to_safe_dict(),
            )
            self._factory = DemoApplicationFactory(config=config, source_config=source)
            from aip.product.configured.services.configured_advanced_macro_forecasting_service import (
                ConfiguredAdvancedMacroForecastingService,
            )
            from ticotrader_web.forecast_policy import configured_service

            self._factory.container.register_instance(
                ConfiguredAdvancedMacroForecastingService, configured_service()
            )
            from aip.product.configured.context.valuation_date_context import ValuationDateContext
            from aip.product.configured.services.configured_financial_analysis_service import (
                ConfiguredFinancialAnalysisService,
            )

            self._factory.container.register_instance(
                ConfiguredFinancialAnalysisService,
                ConfiguredFinancialAnalysisService(
                    source.sugef_financial,
                    self._factory.container.resolve(ValuationDateContext),
                    comparison_history_only=True,
                ),
            )
        return self._factory

    def financial(self, entity_id=None, cutoff=None, refresh=False):
        from aip.ui.modules.financial_analysis.presenters.financial_analysis_presenter import (
            FinancialAnalysisPresenter,
        )

        factory = self.factory
        factory.set_data_cutoff_date(cutoff or date.today())
        return asdict(
            FinancialAnalysisPresenter(factory).build_view_model(
                selected_entity_id=entity_id, force_refresh=refresh
            )
        )

    def compare(self, entity_ids, series_code, horizon, custom_from=None, custom_to=None):
        from aip.ui.modules.financial_analysis.presenters.financial_analysis_presenter import (
            FinancialAnalysisPresenter,
        )

        self.factory.set_data_cutoff_date(custom_to or date.today())
        return asdict(
            FinancialAnalysisPresenter(self.factory).build_comparison_view_model(
                entity_ids=tuple(entity_ids),
                series_code=series_code,
                horizon=horizon,
                custom_from=custom_from,
                custom_to=custom_to,
            )
        )

    def macro(self, refresh=False):
        from aip.product.configured.protocols import EconomicIndicatorsProvider
        from aip.product.economic.economic_viewmodel import EconomicViewModel
        from aip.ui.modules.macro_intelligence.freshness import economic_source_freshness_notice

        provider = self.factory.container.resolve(EconomicIndicatorsProvider)
        if refresh and callable(getattr(provider, "invalidate_cache", None)):
            provider.invalidate_cache()
        snapshot = EconomicViewModel(provider).load()
        result = asdict(snapshot)
        result["freshness_notice"] = economic_source_freshness_notice(snapshot, as_of=date.today())
        return result

    def projection(self):
        from aip.ui.modules.macro_intelligence.presenters.macro_intelligence_presenter import (
            MacroIntelligencePresenter,
        )

        return asdict(MacroIntelligencePresenter(self.factory).build_projection())

    def forecast(self, indicator, refresh=False):
        from ticotrader_web.forecast_policy import FORECAST_INDICATORS

        if indicator not in FORECAST_INDICATORS:
            raise ValueError("El piloto proyecta únicamente TBP, tipo de cambio y TRI")
        from aip.ui.modules.macro_intelligence.presenters.macro_intelligence_presenter import (
            MacroIntelligencePresenter,
        )

        return asdict(
            MacroIntelligencePresenter(self.factory).build_forecast_lab(
                indicator, force_refresh=refresh
            )
        )
