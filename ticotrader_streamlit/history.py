"""Fetch only the selected forecast series; store official observations only."""

from datetime import date, timedelta
from pathlib import Path
from tempfile import gettempdir


def forecast_service(settings, indicator):
    from aip.infrastructure.configuration.models import DatabaseSettings
    from aip.integration.bccr.configuration.bccr_config import BCCRConfig
    from aip.product.configured.adapters.configured_economic_indicators_provider import (
        ConfiguredEconomicIndicatorsProvider,
    )
    from aip.product.configured.repositories.economic_historical_repository import (
        EconomicHistoricalRepository,
    )
    from aip.product.configured.repositories.economic_historical_store import (
        EconomicHistoricalStore,
    )
    from aip.product.configured.services.configured_advanced_macro_forecasting_service import (
        ConfiguredAdvancedMacroForecastingService,
    )
    from ticotrader_web.forecast_policy import FORECAST_INDICATORS, lightweight_engine

    if indicator not in FORECAST_INDICATORS:
        raise ValueError("Indicador no permitido")
    store = EconomicHistoricalStore(
        database_settings=DatabaseSettings(
            path=Path(gettempdir()) / "ticotrader_atlas_public_history.duckdb"
        )
    )
    repository = EconomicHistoricalRepository(store=store)
    if settings.get("token"):
        provider = ConfiguredEconomicIndicatorsProvider(
            bccr_config=BCCRConfig(
                base_url="https://apim.bccr.fi.cr",
                token=settings["token"],
                email=settings.get("email"),
                name="TicoTrader Atlas",
                timeout_seconds=20,
                retry_attempts=1,
            )
        )
        mapping = provider._mapper.resolve(indicator, "BCCR")
        end = date.today()
        # Ten years bound the input size; monthly normalization keeps missing values.
        start = end - timedelta(days=3653)
        response = provider._client.fetch_series(
            indicator_code=mapping.source_series_code,
            from_date=start.strftime("%Y/%m/%d"),
            to_date=end.strftime("%Y/%m/%d"),
        )
        observations = tuple(
            x
            for x in provider._parser.parse(response.get("body", {}))
            if x.indicator_code == indicator
        )
        rows = provider._official_history_rows({indicator: observations})
        if rows:
            repository.append(rows)
    return ConfiguredAdvancedMacroForecastingService(
        repository=repository, forecasting_service=lightweight_engine()
    )
