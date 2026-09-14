from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.domain.irrbb.models import (
    IRRBBMethodologyProfile,
    IRRBBMethodologyStatus,
    IRRBBScenario,
    ScenarioShockCalibration,
)
from aip.domain.irrbb.services.parameterized_scenario_curve_shocker import (
    ParallelOnlyScenarioTenorShockProvider,
    ParameterizedScenarioCurveShocker,
)
from aip.shared.money import Currency


def _calibration() -> ScenarioShockCalibration:
    return ScenarioShockCalibration(
        methodology=IRRBBMethodologyProfile(
            code="SUGEF_IRRBB_VEP",
            version="PROPOSAL_2024",
            status=IRRBBMethodologyStatus.PROPOSED,
            source_reference="SUGEF_2024_PRESENTATION",
            effective_from=date(2024, 1, 15),
        ),
        currency=Currency.CRC,
        parallel_bp=Decimal("400"),
        short_bp=Decimal("550"),
        long_bp=Decimal("250"),
    )


def test_parallel_up_adds_calibrated_basis_points() -> None:
    shocker = ParameterizedScenarioCurveShocker(ParallelOnlyScenarioTenorShockProvider())

    result = shocker.shocked_rate(
        base_rate=Decimal("0.05"),
        tenor_years=Decimal("5"),
        scenario=IRRBBScenario.PARALLEL_UP,
        calibration=_calibration(),
    )

    assert result == Decimal("0.09")


def test_parallel_down_subtracts_calibrated_basis_points() -> None:
    shocker = ParameterizedScenarioCurveShocker(ParallelOnlyScenarioTenorShockProvider())

    result = shocker.shocked_rate(
        base_rate=Decimal("0.05"),
        tenor_years=Decimal("5"),
        scenario=IRRBBScenario.PARALLEL_DOWN,
        calibration=_calibration(),
    )

    assert result == Decimal("0.01")


def test_base_scenario_preserves_rate_without_requesting_shock() -> None:
    shocker = ParameterizedScenarioCurveShocker(ParallelOnlyScenarioTenorShockProvider())

    assert shocker.shocked_rate(
        base_rate=Decimal("0.05"),
        tenor_years=Decimal("2"),
        scenario=IRRBBScenario.BASE,
        calibration=_calibration(),
    ) == Decimal("0.05")


def test_non_parallel_scenario_requires_approved_methodology() -> None:
    shocker = ParameterizedScenarioCurveShocker(ParallelOnlyScenarioTenorShockProvider())

    with pytest.raises(ValueError, match="approved non-parallel"):
        shocker.shocked_rate(
            base_rate=Decimal("0.05"),
            tenor_years=Decimal("2"),
            scenario=IRRBBScenario.STEEPENER,
            calibration=_calibration(),
        )


def test_negative_tenor_is_rejected() -> None:
    shocker = ParameterizedScenarioCurveShocker(ParallelOnlyScenarioTenorShockProvider())

    with pytest.raises(ValueError, match="tenor_years"):
        shocker.shocked_rate(
            base_rate=Decimal("0.05"),
            tenor_years=Decimal("-1"),
            scenario=IRRBBScenario.PARALLEL_UP,
            calibration=_calibration(),
        )
