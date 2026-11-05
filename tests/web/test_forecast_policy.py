import pytest
from pydantic import ValidationError

from aip.product.economic.macro_model_registry import MacroModelRegistry
from ticotrader_web.app import Query
from ticotrader_web.forecast_policy import (
    FORECAST_INDICATORS,
    MODEL_NAMES,
    configured_service,
)
from ticotrader_web.runtime import Runtime


@pytest.mark.parametrize("code", ["TPM", "IMAE", "INFLATION", "UNKNOWN"])
def test_pilot_rejects_non_target_forecasts_before_source_access(code):
    with pytest.raises(ValidationError):
        Query(kind="forecast", indicator=code)
    runtime = Runtime()
    with pytest.raises(ValueError):
        runtime.forecast(code)
    assert runtime._factory is None


def test_targets_and_lightweight_service_leave_original_registry_intact():
    assert Query(kind="forecast").indicator == "TBP"
    for code in FORECAST_INDICATORS:
        assert Query(kind="forecast", indicator=code).indicator == code
    service = configured_service()
    engine = service._forecasting_engine()
    assert {model.name for model in engine.registry.enabled()} == MODEL_NAMES
    assert all(model.mode == "UNIVARIATE" for model in engine.registry.enabled())
    assert engine._maximum_backtest_origins == 12
    assert engine._minimum_backtest_observations == 8
    assert service._sugef_reader is None
    assert len(MacroModelRegistry().enabled()) == 16
