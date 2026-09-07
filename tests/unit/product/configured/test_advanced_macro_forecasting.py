from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

import pytest

from aip.product.economic.advanced_forecasting_service import AdvancedMacroForecastingService
from aip.product.economic.econometric_dataset import (
    EconometricMonthlyDataset,
    EconometricMonthlyRow,
)
from aip.product.economic.macro_model_registry import (
    MacroModelRegistry,
    MacroModelSpecification,
)


def _month_end(year: int, month: int) -> date:
    return date(year, month, monthrange(year, month)[1])


def _dataset(months: int = 84) -> EconometricMonthlyDataset:
    rows: list[EconometricMonthlyRow] = []
    year = 2019
    month = 1
    for index in range(months):
        period = _month_end(year, month)
        cycle = Decimal((index % 12) - 6) / Decimal("20")
        inflation = Decimal("2.0") + cycle
        imae = Decimal("3.5") + Decimal(index) / Decimal("100") - cycle / Decimal("2")
        fx = Decimal("570") - Decimal(index) * Decimal("0.45") + cycle * Decimal("2")
        tpm = (
            Decimal("3.0")
            + inflation * Decimal("0.22")
            + imae * Decimal("0.08")
            + Decimal(index) / Decimal("500")
        )
        tbp = tpm * Decimal("0.72") + Decimal("1.05")
        tri_crc = tbp + Decimal("0.85")
        tri_usd = Decimal("4.2") + Decimal(index) / Decimal("600")
        rows.append(
            EconometricMonthlyRow(
                period=period,
                fx_sell=fx,
                tpm=tpm,
                tbp=tbp,
                tri_crc_12m=tri_crc,
                tri_usd_12m=tri_usd,
                inflation=inflation,
                imae=imae,
            )
        )
        month += 1
        if month == 13:
            month = 1
            year += 1
    return EconometricMonthlyDataset(
        rows=tuple(rows),
        indicator_codes=(
            "FX_SELL",
            "TPM",
            "TBP",
            "TRI_CRC_12M",
            "TRI_USD_12M",
            "INFLATION",
            "IMAE",
        ),
        first_period=rows[0].period,
        last_period=rows[-1].period,
    )


def _test_registry() -> MacroModelRegistry:
    return MacroModelRegistry(
        (
            MacroModelSpecification("NAIVE", "NAIVE", "UNIVARIATE", 0),
            MacroModelSpecification("DRIFT", "DRIFT", "UNIVARIATE", 1),
            MacroModelSpecification(
                "ETS_DAMPED",
                "ETS",
                "UNIVARIATE",
                3,
            ),
            MacroModelSpecification(
                "RIDGE_DIRECT",
                "RIDGE",
                "MULTIVARIATE_DIRECT",
                4,
                parameters=(("alpha", "1.0"),),
            ),
            MacroModelSpecification(
                "ELASTIC_NET_DIRECT",
                "ELASTIC_NET",
                "MULTIVARIATE_DIRECT",
                5,
                parameters=(("alpha", "0.05"), ("l1_ratio", "0.25")),
            ),
        )
    )


def test_registry_contains_statistical_econometric_and_machine_learning_candidates() -> None:
    families = {item.family for item in MacroModelRegistry().enabled()}

    assert {"NAIVE", "ARIMA", "ETS", "ARDL", "RIDGE", "ELASTIC_NET"}.issubset(families)
    assert "GRADIENT_BOOSTING" in families


def test_multimodel_engine_produces_governed_12_month_ensemble() -> None:
    service = AdvancedMacroForecastingService(
        registry=_test_registry(),
        minimum_training_observations=24,
        minimum_backtest_observations=4,
    )

    result = service.evaluate(_dataset(), "TPM", forecast_horizon=12)

    assert result.available
    assert result.champion_model_name is not None
    assert result.champion_model_family is not None
    assert len(result.forecast_points) == 12
    assert len(result.ensemble_weights) >= 1
    assert sum(item.weight for item in result.ensemble_weights) == pytest.approx(1.0)
    assert result.confidence_score is not None
    assert 0.0 <= result.confidence_score <= 100.0
    assert result.point_at_horizon(1) is not None
    assert result.point_at_horizon(12) is not None
    assert all(point.lower_95 <= point.point_forecast <= point.upper_95 for point in result.forecast_points)


def test_direct_model_forecast_does_not_use_rows_after_forecast_origin() -> None:
    service = AdvancedMacroForecastingService(
        registry=_test_registry(),
        minimum_training_observations=24,
        minimum_backtest_observations=4,
    )
    frame = service._frame(_dataset())
    specification = service.registry.get("RIDGE_DIRECT")
    origin = 60
    horizon = 6

    base = service._forecast_at_origin(frame, "TPM", specification, origin, horizon)
    altered = frame.copy()
    altered.iloc[origin + 1 :, :] = altered.iloc[origin + 1 :, :] * 1000.0
    repeated = service._forecast_at_origin(altered, "TPM", specification, origin, horizon)

    assert repeated == pytest.approx(base)
