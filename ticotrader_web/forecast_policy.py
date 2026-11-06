"""Bounded candidate universe for the Atlas shared-hosting pilot."""

FORECAST_INDICATORS = (
    "TBP",
    "FX_BUY",
    "FX_SELL",
    *(
        f"TRI_{currency}_{term}"
        for currency in ("CRC", "USD")
        for term in ("1W", "1M", "3M", "6M", "9M", "12M", "24M", "36M", "60M")
    ),
)
MODEL_NAMES = frozenset({"NAIVE", "DRIFT", "AR_1", "AR_2"})
MAXIMUM_BACKTEST_ORIGINS = 12


def lightweight_engine():
    from aip.product.economic.advanced_forecasting_service import AdvancedMacroForecastingService
    from aip.product.economic.macro_model_registry import MacroModelRegistry

    registry = MacroModelRegistry(
        tuple(
            model
            for model in MacroModelRegistry.default_specifications()
            if model.name in MODEL_NAMES
        )
    )
    return AdvancedMacroForecastingService(
        registry=registry,
        maximum_backtest_origins=MAXIMUM_BACKTEST_ORIGINS,
        maximum_ensemble_models=3,
    )


def configured_service():
    from aip.product.configured.services.configured_advanced_macro_forecasting_service import (
        ConfiguredAdvancedMacroForecastingService,
    )

    # Univariate candidates need no SUGEF feature downloads. Financial analysis
    # keeps its own full SUGEF connector. Preserve the engine's source-date cache.
    return ConfiguredAdvancedMacroForecastingService(forecasting_service=lightweight_engine())
