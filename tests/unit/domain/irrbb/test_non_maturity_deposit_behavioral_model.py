from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.domain.irrbb.behavioral import (
    NonMaturityDepositAllocation,
    NonMaturityDepositProfile,
)
from aip.domain.irrbb.models import (
    BankingBookPosition,
    BankingBookSide,
    CashFlowAmountStatus,
    CashFlowDirection,
    IRRBBInstrumentClass,
    IRRBBMethodologyProfile,
    IRRBBMethodologyStatus,
    IRRBBScenario,
    OptionalityType,
    PaymentStructure,
    RateType,
)
from aip.domain.irrbb.services.non_maturity_deposit_behavioral_model import (
    NonMaturityDepositBehavioralModel,
)
from aip.shared.money import Currency, Money

_VALUATION_DATE = date(2026, 8, 31)


class _ProfileProvider:
    def __init__(self, profile: NonMaturityDepositProfile) -> None:
        self._profile = profile

    def profile_for(
        self,
        *,
        position: BankingBookPosition,
        scenario: IRRBBScenario,
        valuation_date: date,
    ) -> NonMaturityDepositProfile:
        del position, scenario, valuation_date
        return self._profile


def _methodology() -> IRRBBMethodologyProfile:
    return IRRBBMethodologyProfile(
        code="INTERNAL_NMD",
        version="2026-01",
        status=IRRBBMethodologyStatus.INTERNAL,
        source_reference="ALCO_APPROVED_NMD_PROFILE",
        effective_from=date(2026, 1, 1),
    )


def _profile(*, scenario: IRRBBScenario = IRRBBScenario.BASE) -> NonMaturityDepositProfile:
    return NonMaturityDepositProfile(
        methodology=_methodology(),
        scenario=scenario,
        source_reference="PROFILE:SAVINGS_CRC",
        allocations=(
            NonMaturityDepositAllocation(tenor_months=0, weight=Decimal("0.30")),
            NonMaturityDepositAllocation(tenor_months=12, weight=Decimal("0.70")),
        ),
    )


def _position() -> BankingBookPosition:
    return BankingBookPosition(
        position_id="NMD-1",
        product_type="SAVINGS",
        side=BankingBookSide.LIABILITY,
        currency=Currency.CRC,
        principal=Money(Decimal("1000"), Currency.CRC),
        rate_type=RateType.FLOATING,
        maturity_date=None,
        source_reference="TEST:NMD-1",
        instrument_class=IRRBBInstrumentClass.NON_MATURITY_DEPOSIT,
        payment_structure=PaymentStructure.NON_MATURITY,
        optionality=OptionalityType.NON_MATURITY_DEPOSIT,
    )


def test_nmd_profile_allocates_full_principal_without_overnight_default() -> None:
    model = NonMaturityDepositBehavioralModel(_ProfileProvider(_profile()))

    result = model.apply(
        position=_position(),
        contractual_cashflows=(),
        scenario=IRRBBScenario.BASE,
        valuation_date=_VALUATION_DATE,
    )

    assert tuple(flow.amount.amount for flow in result) == (
        Decimal("300.00"),
        Decimal("700.00"),
    )
    assert tuple(flow.cashflow_date for flow in result) == (
        date(2026, 8, 31),
        date(2027, 8, 31),
    )
    assert all(flow.direction is CashFlowDirection.PAYABLE for flow in result)
    assert all(flow.amount_status is CashFlowAmountStatus.BEHAVIORAL for flow in result)
    assert sum((flow.amount.amount for flow in result), Decimal("0")) == Decimal("1000.00")


def test_nmd_profile_requires_weights_to_sum_to_one() -> None:
    with pytest.raises(ValueError, match="sum exactly to one"):
        NonMaturityDepositProfile(
            methodology=_methodology(),
            scenario=IRRBBScenario.BASE,
            source_reference="INVALID",
            allocations=(
                NonMaturityDepositAllocation(tenor_months=0, weight=Decimal("0.40")),
                NonMaturityDepositAllocation(tenor_months=12, weight=Decimal("0.50")),
            ),
        )


def test_nmd_profile_scenario_must_match_requested_scenario() -> None:
    model = NonMaturityDepositBehavioralModel(
        _ProfileProvider(_profile(scenario=IRRBBScenario.PARALLEL_UP))
    )

    with pytest.raises(ValueError, match="scenario does not match"):
        model.apply(
            position=_position(),
            contractual_cashflows=(),
            scenario=IRRBBScenario.BASE,
            valuation_date=_VALUATION_DATE,
        )


def test_nmd_model_rejects_non_nmd_position() -> None:
    position = BankingBookPosition(
        position_id="TD-1",
        product_type="TERM_DEPOSIT",
        side=BankingBookSide.LIABILITY,
        currency=Currency.CRC,
        principal=Money(Decimal("1000"), Currency.CRC),
        rate_type=RateType.FIXED,
        maturity_date=date(2027, 8, 31),
        source_reference="TEST:TD-1",
        instrument_class=IRRBBInstrumentClass.TERM_DEPOSIT,
        payment_structure=PaymentStructure.BULLET,
    )
    model = NonMaturityDepositBehavioralModel(_ProfileProvider(_profile()))

    with pytest.raises(ValueError, match="non-maturity-deposit"):
        model.apply(
            position=position,
            contractual_cashflows=(),
            scenario=IRRBBScenario.BASE,
            valuation_date=_VALUATION_DATE,
        )
