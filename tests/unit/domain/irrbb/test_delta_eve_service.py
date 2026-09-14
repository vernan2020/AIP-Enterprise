from __future__ import annotations

from decimal import Decimal

import pytest

from aip.domain.irrbb.models import EconomicValueResult, IRRBBScenario
from aip.domain.irrbb.services.delta_eve_service import DeltaEVEExposureService
from aip.shared.money import Currency, Money


def _eve(scenario: IRRBBScenario, value: str) -> EconomicValueResult:
    zero = Money(Decimal("0"), Currency.CRC)
    return EconomicValueResult(
        scenario=scenario,
        reporting_currency=Currency.CRC,
        pv_assets=zero,
        pv_liabilities=zero,
        pv_off_balance_net=zero,
        eve=Money(Decimal(value), Currency.CRC),
        discounted_cashflows=(),
    )


def test_calculate_selects_maximum_eve_fall_and_ratio_to_tier_one() -> None:
    result = DeltaEVEExposureService.calculate(
        base=_eve(IRRBBScenario.BASE, "1000"),
        stressed=(
            _eve(IRRBBScenario.PARALLEL_UP, "900"),
            _eve(IRRBBScenario.PARALLEL_DOWN, "1100"),
            _eve(IRRBBScenario.STEEPENER, "950"),
            _eve(IRRBBScenario.FLATTENER, "850"),
            _eve(IRRBBScenario.SHORT_UP, "920"),
            _eve(IRRBBScenario.SHORT_DOWN, "1020"),
        ),
        tier_one_capital=Money(Decimal("1000"), Currency.CRC),
    )

    assert result.worst_scenario is IRRBBScenario.FLATTENER
    assert result.worst_loss.amount == Decimal("150")
    assert result.exposure_ratio_to_tier1 == Decimal("0.15")
    assert next(
        item for item in result.assessments if item.scenario is IRRBBScenario.PARALLEL_DOWN
    ).fall_from_base.amount == Decimal("0")


def test_calculate_requires_all_six_standard_stresses() -> None:
    with pytest.raises(ValueError, match="missing required IRRBB stress scenarios"):
        DeltaEVEExposureService.calculate(
            base=_eve(IRRBBScenario.BASE, "1000"),
            stressed=(_eve(IRRBBScenario.PARALLEL_UP, "900"),),
            tier_one_capital=Money(Decimal("1000"), Currency.CRC),
        )


def test_calculate_rejects_non_positive_tier_one_capital() -> None:
    stresses = tuple(
        _eve(scenario, "1000")
        for scenario in (
            IRRBBScenario.PARALLEL_UP,
            IRRBBScenario.PARALLEL_DOWN,
            IRRBBScenario.STEEPENER,
            IRRBBScenario.FLATTENER,
            IRRBBScenario.SHORT_UP,
            IRRBBScenario.SHORT_DOWN,
        )
    )

    with pytest.raises(ValueError, match="Tier 1 capital must be positive"):
        DeltaEVEExposureService.calculate(
            base=_eve(IRRBBScenario.BASE, "1000"),
            stressed=stresses,
            tier_one_capital=Money(Decimal("0"), Currency.CRC),
        )
