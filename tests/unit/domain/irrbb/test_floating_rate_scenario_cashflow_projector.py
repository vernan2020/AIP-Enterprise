from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.domain.irrbb.models import (
    BankingBookPosition,
    BankingBookSide,
    CashFlowAmountStatus,
    CashFlowDirection,
    IRRBBCashFlow,
    IRRBBInstrumentClass,
    IRRBBScenario,
    PaymentStructure,
    RateType,
)
from aip.domain.irrbb.scenario_repricing import FloatingRateCouponBasis
from aip.domain.irrbb.services.floating_rate_scenario_cashflow_projector import (
    FloatingRateScenarioCashFlowProjector,
)
from aip.shared.money import Currency, Money

_VALUATION_DATE = date(2026, 8, 31)
_CURRENCY = Currency.CRC


class _BasisProvider:
    def __init__(self, basis: FloatingRateCouponBasis | None) -> None:
        self._basis = basis

    def basis_for(
        self,
        *,
        position: BankingBookPosition,
        cashflow: IRRBBCashFlow,
        valuation_date: date,
    ) -> FloatingRateCouponBasis | None:
        del position, cashflow, valuation_date
        return self._basis


class _ReferenceRateProvider:
    def __init__(self, rate: Decimal) -> None:
        self._rate = rate

    def reference_rate(
        self,
        *,
        reference_rate_code: str,
        currency: Currency,
        scenario: IRRBBScenario,
        reset_date: date,
        valuation_date: date,
    ) -> Decimal:
        del reference_rate_code, currency, scenario, reset_date, valuation_date
        return self._rate


def _position(*, rate_type: RateType = RateType.FLOATING) -> BankingBookPosition:
    return BankingBookPosition(
        position_id="LOAN-1",
        product_type="VARIABLE_LOAN",
        side=BankingBookSide.ASSET,
        currency=_CURRENCY,
        principal=Money(Decimal("1000000"), _CURRENCY),
        rate_type=rate_type,
        maturity_date=date(2028, 8, 31),
        source_reference="TEST:LOAN-1",
        contractual_rate=Decimal("0.08"),
        reference_rate="TRI_CRC",
        spread=Decimal("0.02"),
        next_repricing_date=date(2026, 9, 30),
        repricing_frequency_months=3,
        instrument_class=IRRBBInstrumentClass.CREDIT,
        payment_structure=PaymentStructure.AMORTIZING,
    )


def _flow() -> IRRBBCashFlow:
    return IRRBBCashFlow(
        position_id="LOAN-1",
        side=BankingBookSide.ASSET,
        direction=CashFlowDirection.RECEIVABLE,
        amount=Money(Decimal("20000"), _CURRENCY),
        cashflow_date=date(2026, 12, 31),
        risk_date=date(2026, 9, 30),
        flow_type="INTEREST",
        source_reference="TEST:FLOW-1",
        amount_status=CashFlowAmountStatus.PROJECTED_CURRENT_RATE,
        projection_basis="CURRENT_RATE",
    )


def _basis(*, cap: Decimal | None = None) -> FloatingRateCouponBasis:
    return FloatingRateCouponBasis(
        position_id="LOAN-1",
        cashflow_date=date(2026, 12, 31),
        reset_date=date(2026, 9, 30),
        reference_rate_code="TRI_CRC",
        notional=Money(Decimal("1000000"), _CURRENCY),
        accrual_fraction=Decimal("0.25"),
        spread=Decimal("0.02"),
        source_reference="TEST:BASIS-1",
        rate_cap=cap,
    )


def test_stressed_projection_reprices_current_rate_coupon() -> None:
    projector = FloatingRateScenarioCashFlowProjector(
        basis_provider=_BasisProvider(_basis()),
        reference_rates=_ReferenceRateProvider(Decimal("0.06")),
    )

    result = projector.project(
        position=_position(),
        base_cashflows=(_flow(),),
        scenario=IRRBBScenario.PARALLEL_UP,
        valuation_date=_VALUATION_DATE,
    )

    assert result[0].amount == Money(Decimal("20000.0000"), _CURRENCY)
    assert result[0].amount_status is CashFlowAmountStatus.SCENARIO_PROJECTED
    assert "TRI_CRC" in (result[0].projection_basis or "")
    assert "PARALLEL_UP" in (result[0].projection_basis or "")


def test_stressed_projection_applies_contractual_cap() -> None:
    projector = FloatingRateScenarioCashFlowProjector(
        basis_provider=_BasisProvider(_basis(cap=Decimal("0.09"))),
        reference_rates=_ReferenceRateProvider(Decimal("0.10")),
    )

    result = projector.project(
        position=_position(),
        base_cashflows=(_flow(),),
        scenario=IRRBBScenario.PARALLEL_UP,
        valuation_date=_VALUATION_DATE,
    )

    assert result[0].amount == Money(Decimal("22500.0000"), _CURRENCY)


def test_base_scenario_preserves_current_rate_projection() -> None:
    projector = FloatingRateScenarioCashFlowProjector(
        basis_provider=_BasisProvider(None),
        reference_rates=_ReferenceRateProvider(Decimal("0.06")),
    )

    result = projector.project(
        position=_position(),
        base_cashflows=(_flow(),),
        scenario=IRRBBScenario.BASE,
        valuation_date=_VALUATION_DATE,
    )

    assert result == (_flow(),)


def test_fixed_rate_position_is_not_reprojected() -> None:
    projector = FloatingRateScenarioCashFlowProjector(
        basis_provider=_BasisProvider(None),
        reference_rates=_ReferenceRateProvider(Decimal("0.06")),
    )

    result = projector.project(
        position=_position(rate_type=RateType.FIXED),
        base_cashflows=(_flow(),),
        scenario=IRRBBScenario.PARALLEL_UP,
        valuation_date=_VALUATION_DATE,
    )

    assert result == (_flow(),)


def test_stressed_projection_requires_explicit_basis() -> None:
    projector = FloatingRateScenarioCashFlowProjector(
        basis_provider=_BasisProvider(None),
        reference_rates=_ReferenceRateProvider(Decimal("0.06")),
    )

    with pytest.raises(ValueError, match="missing floating-rate coupon basis"):
        projector.project(
            position=_position(),
            base_cashflows=(_flow(),),
            scenario=IRRBBScenario.PARALLEL_UP,
            valuation_date=_VALUATION_DATE,
        )
