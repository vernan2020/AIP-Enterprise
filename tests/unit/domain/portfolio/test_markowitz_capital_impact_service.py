from decimal import Decimal

import pytest

from aip.domain.portfolio.services.markowitz_capital_impact_service import (
    AssetCapitalAssumption,
    MarkowitzCapitalImpactService,
)
from aip.domain.portfolio.services.markowitz_optimizer import (
    MarkowitzPortfolio,
    MarkowitzResult,
)
from aip.domain.portfolio.services.portfolio_capital_consumption_service import (
    ExposureClass,
)


def _optimization() -> MarkowitzResult:
    point = MarkowitzPortfolio(
        weights=(0.5, 0.5), expected_return=0.08, volatility=0.11
    )
    return MarkowitzResult(
        minimum_variance=point,
        efficient_frontier=(point,),
        observation_count=120,
        asset_names=("Gov CRC", "Gov USD"),
    )


def _assumptions() -> tuple[AssetCapitalAssumption, ...]:
    return (
        AssetCapitalAssumption(
            "Gov CRC", "CRC", Decimal("1"), ExposureClass.GOVERNMENT_CRC, "Rated mapping at cutoff"
        ),
        AssetCapitalAssumption(
            "Gov USD", "USD", Decimal("1"), ExposureClass.GOVERNMENT_USD, "Rated mapping at cutoff"
        ),
    )


def test_markowitz_capital_adjusts_returns_without_modifying_volatility() -> None:
    result = MarkowitzCapitalImpactService.evaluate(
        _optimization(), _assumptions(), annual_cost_of_equity=Decimal("0.12")
    )
    point = result.minimum_variance
    assert point.credit_rwa_to_portfolio_ratio == Decimal("0.375")
    assert point.target_equity_to_portfolio_ratio == Decimal("0.06000")
    assert point.annual_equity_charge_ratio == Decimal("0.0072000")
    assert point.expected_return_after_equity_cost == Decimal("0.0728000")
    assert point.volatility == pytest.approx(0.11)


def test_editing_equity_cost_recalculates_economic_markowitz_return() -> None:
    first = MarkowitzCapitalImpactService.evaluate(
        _optimization(), _assumptions(), annual_cost_of_equity=Decimal("0.10")
    )
    second = MarkowitzCapitalImpactService.evaluate(
        _optimization(), _assumptions(), annual_cost_of_equity=Decimal("0.20")
    )
    assert first.minimum_variance.expected_return_after_equity_cost > (
        second.minimum_variance.expected_return_after_equity_cost
    )
    assert second.minimum_variance.annual_equity_charge_ratio == Decimal("0.0120000")


def test_capital_impact_rejects_unverified_classification_and_order() -> None:
    with pytest.raises(ValueError, match="match optimizer asset order"):
        MarkowitzCapitalImpactService.evaluate(
            _optimization(), reversed(_assumptions()), annual_cost_of_equity=Decimal("0.12")
        )
    unverified = (
        AssetCapitalAssumption(
            "Gov CRC", "CRC", Decimal("1"), ExposureClass.GOVERNMENT_CRC, ""
        ),
        _assumptions()[1],
    )
    with pytest.raises(ValueError, match="verified source"):
        MarkowitzCapitalImpactService.evaluate(
            _optimization(), unverified, annual_cost_of_equity=Decimal("0.12")
        )


def test_capital_impact_never_uses_crc_zero_weight_for_usd() -> None:
    wrong = (
        _assumptions()[0],
        AssetCapitalAssumption(
            "Gov USD", "USD", Decimal("1"), ExposureClass.GOVERNMENT_CRC, "Test"
        ),
    )
    with pytest.raises(ValueError, match="requires CRC"):
        MarkowitzCapitalImpactService.evaluate(
            _optimization(), wrong, annual_cost_of_equity=Decimal("0.12")
        )
