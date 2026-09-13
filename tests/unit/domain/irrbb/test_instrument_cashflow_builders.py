from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.domain.irrbb.instruments import (
    ExplicitScheduleCashFlowBuilder,
    InvestmentContractualCashFlowBuilder,
)
from aip.domain.irrbb.models import (
    BankingBookPosition,
    BankingBookSide,
    CashFlowAmountStatus,
    CashFlowDirection,
    ContractualCashFlowRecord,
    IRRBBInstrumentClass,
    PaymentStructure,
    RateType,
)
from aip.shared.money import Currency, Money

_VALUATION_DATE = date(2026, 1, 1)


class _ScheduleProvider:
    def __init__(self, records: tuple[ContractualCashFlowRecord, ...]) -> None:
        self._records = records

    def get_schedule(
        self,
        *,
        position: BankingBookPosition,
        valuation_date: date,
    ) -> tuple[ContractualCashFlowRecord, ...]:
        del position, valuation_date
        return self._records


def _investment(*, rate_type: RateType = RateType.FIXED) -> BankingBookPosition:
    return BankingBookPosition(
        position_id="INV-1",
        product_type="BOND",
        side=BankingBookSide.ASSET,
        currency=Currency.CRC,
        principal=Money(Decimal("1000"), Currency.CRC),
        rate_type=rate_type,
        maturity_date=date(2027, 1, 1),
        source_reference="MASTER:INV-1",
        contractual_rate=Decimal("0.06"),
        next_repricing_date=(date(2026, 4, 1) if rate_type is RateType.FLOATING else None),
        repricing_frequency_months=(3 if rate_type is RateType.FLOATING else None),
        payment_frequency_months=3,
        instrument_class=IRRBBInstrumentClass.INVESTMENT,
        payment_structure=PaymentStructure.BULLET,
        last_interest_payment_date=date(2026, 1, 1),
    )


def test_investment_builder_reuses_portfolio_coupon_and_principal_schedule() -> None:
    cashflows = InvestmentContractualCashFlowBuilder().build(
        position=_investment(),
        valuation_date=_VALUATION_DATE,
    )

    coupons = tuple(flow for flow in cashflows if flow.flow_type == "COUPON")
    principal = tuple(flow for flow in cashflows if flow.flow_type == "PRINCIPAL")

    assert tuple(flow.cashflow_date for flow in coupons) == (
        date(2026, 4, 1),
        date(2026, 7, 1),
        date(2026, 10, 1),
        date(2027, 1, 1),
    )
    assert {flow.amount.amount for flow in coupons} == {Decimal("15.0000")}
    assert len(principal) == 1
    assert principal[0].amount.amount == Decimal("1000")
    assert all(flow.risk_date == flow.cashflow_date for flow in cashflows)


def test_variable_investment_marks_current_rate_coupon_projection_explicitly() -> None:
    cashflows = InvestmentContractualCashFlowBuilder().build(
        position=_investment(rate_type=RateType.FLOATING),
        valuation_date=_VALUATION_DATE,
    )

    coupons = tuple(flow for flow in cashflows if flow.flow_type == "COUPON")
    assert coupons
    assert all(
        flow.amount_status is CashFlowAmountStatus.PROJECTED_CURRENT_RATE for flow in coupons
    )
    assert all(flow.risk_date == date(2026, 4, 1) for flow in coupons)
    assert all(
        flow.projection_basis == "CURRENT_RATE_PROJECTION_VARIABLE_SECURITY" for flow in coupons
    )


def test_explicit_schedule_builder_preserves_source_amount_and_direction() -> None:
    position = BankingBookPosition(
        position_id="LOAN-1",
        product_type="CREDIT",
        side=BankingBookSide.ASSET,
        currency=Currency.CRC,
        principal=Money(Decimal("1000"), Currency.CRC),
        rate_type=RateType.FIXED,
        maturity_date=date(2026, 12, 31),
        source_reference="CREDIT:LOAN-1",
        instrument_class=IRRBBInstrumentClass.CREDIT,
        payment_structure=PaymentStructure.AMORTIZING,
    )
    record = ContractualCashFlowRecord(
        payment_date=date(2026, 2, 1),
        amount=Money(Decimal("125"), Currency.CRC),
        direction=CashFlowDirection.RECEIVABLE,
        flow_type="INSTALLMENT",
        source_reference="CREDIT_SCHEDULE:ROW-1",
    )

    cashflows = ExplicitScheduleCashFlowBuilder(_ScheduleProvider((record,))).build(
        position=position,
        valuation_date=_VALUATION_DATE,
    )

    assert len(cashflows) == 1
    assert cashflows[0].amount == record.amount
    assert cashflows[0].direction is CashFlowDirection.RECEIVABLE
    assert cashflows[0].risk_date == record.payment_date
    assert cashflows[0].amount_status is CashFlowAmountStatus.SOURCE_PROVIDED


def test_explicit_schedule_builder_requires_repricing_date_for_floating_position() -> None:
    position = BankingBookPosition(
        position_id="FLOAT-1",
        product_type="CREDIT",
        side=BankingBookSide.ASSET,
        currency=Currency.CRC,
        principal=Money(Decimal("1000"), Currency.CRC),
        rate_type=RateType.FLOATING,
        maturity_date=date(2027, 1, 1),
        source_reference="CREDIT:FLOAT-1",
        instrument_class=IRRBBInstrumentClass.CREDIT,
        payment_structure=PaymentStructure.AMORTIZING,
    )
    record = ContractualCashFlowRecord(
        payment_date=date(2026, 2, 1),
        amount=Money(Decimal("100"), Currency.CRC),
        direction=CashFlowDirection.RECEIVABLE,
        flow_type="INSTALLMENT",
        source_reference="SCHEDULE",
    )

    with pytest.raises(ValueError, match="next_repricing_date"):
        ExplicitScheduleCashFlowBuilder(_ScheduleProvider((record,))).build(
            position=position,
            valuation_date=_VALUATION_DATE,
        )
