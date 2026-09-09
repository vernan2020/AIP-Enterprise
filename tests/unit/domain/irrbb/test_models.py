from __future__ import annotations

from decimal import Decimal

import pytest

from aip.domain.irrbb.models import (
    BankingBookPosition,
    BankingBookSide,
    IRRBBMethodologyProfile,
    IRRBBMethodologyStatus,
    RateType,
    ScenarioShockCalibration,
)
from aip.shared.money import Currency, Money


def test_floating_position_can_represent_missing_repricing_for_quality_workflow() -> None:
    position = BankingBookPosition(
        position_id="LOAN-1",
        product_type="CREDIT",
        side=BankingBookSide.ASSET,
        currency=Currency.CRC,
        principal=Money(Decimal("1000"), Currency.CRC),
        rate_type=RateType.FLOATING,
        maturity_date=None,
        source_reference="TEST",
        next_repricing_date=None,
    )

    assert position.next_repricing_date is None


def test_position_rejects_currency_mismatch() -> None:
    with pytest.raises(ValueError, match="principal currency"):
        BankingBookPosition(
            position_id="LOAN-1",
            product_type="CREDIT",
            side=BankingBookSide.ASSET,
            currency=Currency.CRC,
            principal=Money(Decimal("1000"), Currency.USD),
            rate_type=RateType.FIXED,
            maturity_date=None,
            source_reference="TEST",
        )


def test_shock_calibration_is_versioned_and_rejects_negative_magnitude() -> None:
    methodology = IRRBBMethodologyProfile(
        code="SUGEF_IRRBB_VEP",
        version="PROPOSAL_2024",
        status=IRRBBMethodologyStatus.PROPOSED,
        source_reference="SUGEF presentation January 2024",
    )

    with pytest.raises(ValueError, match="short_bp"):
        ScenarioShockCalibration(
            methodology=methodology,
            currency=Currency.CRC,
            parallel_bp=Decimal("400"),
            short_bp=Decimal("-1"),
            long_bp=Decimal("250"),
        )
