from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from aip.domain.irrbb.models import (
    BankingBookPosition,
    BankingBookSide,
    CashFlowDirection,
    IRRBBInstrumentClass,
    IRRBBTimeBucket,
    PaymentStructure,
    RateType,
)
from aip.domain.irrbb.services.sugef_standard_gap_service import SugefStandardGapService
from aip.domain.irrbb.sugef_standard_gap import SugefGapScheduleRecord
from aip.shared.money import Currency, Money

_VALUATION_DATE = date(2023, 10, 31)
_CRC = Currency.CRC


def _position(
    *,
    position_id: str,
    principal: Decimal,
    rate_type: RateType,
    maturity_date: date,
    instrument_class: IRRBBInstrumentClass,
    payment_structure: PaymentStructure,
    next_repricing_date: date | None = None,
    product_type: str = "TEST",
) -> BankingBookPosition:
    return BankingBookPosition(
        position_id=position_id,
        product_type=product_type,
        side=BankingBookSide.ASSET,
        currency=_CRC,
        principal=Money(principal, _CRC),
        rate_type=rate_type,
        maturity_date=maturity_date,
        source_reference=f"SUGEF_TEMPLATE:{position_id}",
        next_repricing_date=next_repricing_date,
        instrument_class=instrument_class,
        payment_structure=payment_structure,
    )


def _record(
    *,
    payment_date: date,
    amount: Decimal,
    flow_type: str,
    source: str,
    outstanding_principal_after: Decimal | None = None,
) -> SugefGapScheduleRecord:
    return SugefGapScheduleRecord(
        payment_date=payment_date,
        amount=Money(amount, _CRC),
        direction=CashFlowDirection.RECEIVABLE,
        flow_type=flow_type,
        source_reference=source,
        outstanding_principal_after=(
            Money(outstanding_principal_after, _CRC)
            if outstanding_principal_after is not None
            else None
        ),
    )


def _bucket_amounts(
    *,
    position: BankingBookPosition,
    schedule: tuple[SugefGapScheduleRecord, ...],
) -> dict[IRRBBTimeBucket, Decimal]:
    exposures = SugefStandardGapService.build_exposures(
        position=position,
        schedule=schedule,
        valuation_date=_VALUATION_DATE,
    )
    totals = SugefStandardGapService.aggregate_by_bucket(
        exposures=exposures,
        valuation_date=_VALUATION_DATE,
    )
    return {item.bucket: item.amount.amount for item in totals}


def _add_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _remaining_monthly_payments(count: int) -> tuple[date, ...]:
    first = date(2023, 11, 15)
    return tuple(_add_months(first, offset) for offset in range(count))


def test_sugef_example_a_zero_coupon_title_goes_to_9_to_12_months() -> None:
    position = _position(
        position_id="EXAMPLE-A",
        principal=Decimal("1000000"),
        rate_type=RateType.FIXED,
        maturity_date=date(2024, 10, 15),
        instrument_class=IRRBBInstrumentClass.INVESTMENT,
        payment_structure=PaymentStructure.BULLET,
        product_type="ZERO_COUPON_SECURITY",
    )
    schedule = (
        _record(
            payment_date=date(2024, 10, 15),
            amount=Decimal("1210000"),
            flow_type="REDEMPTION",
            source="SUGEF_EXAMPLE_A",
        ),
    )

    assert _bucket_amounts(position=position, schedule=schedule) == {
        IRRBBTimeBucket.MONTH_9_TO_YEAR_1: Decimal("1210000")
    }


def test_sugef_example_b_coupon_title_matches_template_bands() -> None:
    position = _position(
        position_id="EXAMPLE-B",
        principal=Decimal("1500000"),
        rate_type=RateType.FIXED,
        maturity_date=date(2024, 7, 15),
        instrument_class=IRRBBInstrumentClass.INVESTMENT,
        payment_structure=PaymentStructure.BULLET,
        product_type="COUPON_SECURITY",
    )
    coupon_dates = tuple(_add_months(date(2023, 11, 15), offset) for offset in range(9))
    schedule = tuple(
        _record(
            payment_date=payment_date,
            amount=Decimal("16250"),
            flow_type="COUPON",
            source=f"SUGEF_EXAMPLE_B:COUPON:{payment_date.isoformat()}",
        )
        for payment_date in coupon_dates
    ) + (
        _record(
            payment_date=date(2024, 7, 15),
            amount=Decimal("1500000"),
            flow_type="PRINCIPAL",
            source="SUGEF_EXAMPLE_B:PRINCIPAL",
        ),
    )

    assert _bucket_amounts(position=position, schedule=schedule) == {
        IRRBBTimeBucket.DAY_1_TO_MONTH_1: Decimal("16250"),
        IRRBBTimeBucket.MONTH_1_TO_3: Decimal("32500"),
        IRRBBTimeBucket.MONTH_3_TO_6: Decimal("48750"),
        IRRBBTimeBucket.MONTH_6_TO_9: Decimal("1548750"),
    }


def test_sugef_example_c_fixed_rate_loan_matches_remaining_installments() -> None:
    position = _position(
        position_id="EXAMPLE-C",
        principal=Decimal("3740387"),
        rate_type=RateType.FIXED,
        maturity_date=date(2025, 3, 15),
        instrument_class=IRRBBInstrumentClass.CREDIT,
        payment_structure=PaymentStructure.AMORTIZING,
        product_type="FIXED_RATE_LOAN",
    )
    schedule = tuple(
        _record(
            payment_date=payment_date,
            amount=Decimal("254479"),
            flow_type="INSTALLMENT",
            source=f"SUGEF_EXAMPLE_C:{payment_date.isoformat()}",
        )
        for payment_date in _remaining_monthly_payments(17)
    )

    assert _bucket_amounts(position=position, schedule=schedule) == {
        IRRBBTimeBucket.DAY_1_TO_MONTH_1: Decimal("254479"),
        IRRBBTimeBucket.MONTH_1_TO_3: Decimal("508958"),
        IRRBBTimeBucket.MONTH_3_TO_6: Decimal("763437"),
        IRRBBTimeBucket.MONTH_6_TO_9: Decimal("763437"),
        IRRBBTimeBucket.MONTH_9_TO_YEAR_1: Decimal("763437"),
        IRRBBTimeBucket.YEAR_1_TO_1_5: Decimal("1272395"),
    }


def test_sugef_example_d_variable_loan_stops_at_next_repricing() -> None:
    position = _position(
        position_id="EXAMPLE-D",
        principal=Decimal("3740387"),
        rate_type=RateType.FLOATING,
        maturity_date=date(2025, 3, 15),
        instrument_class=IRRBBInstrumentClass.CREDIT,
        payment_structure=PaymentStructure.AMORTIZING,
        next_repricing_date=date(2024, 3, 15),
        product_type="VARIABLE_RATE_LOAN",
    )
    schedule = tuple(
        _record(
            payment_date=payment_date,
            amount=Decimal("254479"),
            flow_type="INSTALLMENT",
            source=f"SUGEF_EXAMPLE_D:{payment_date.isoformat()}",
            outstanding_principal_after=(
                Decimal("2747129") if payment_date == date(2024, 3, 15) else None
            ),
        )
        for payment_date in _remaining_monthly_payments(17)
    )

    assert _bucket_amounts(position=position, schedule=schedule) == {
        IRRBBTimeBucket.DAY_1_TO_MONTH_1: Decimal("254479"),
        IRRBBTimeBucket.MONTH_1_TO_3: Decimal("508958"),
        IRRBBTimeBucket.MONTH_3_TO_6: Decimal("3256087"),
    }


def test_sugef_example_e_semivariable_is_operationally_next_repricing_based() -> None:
    position = _position(
        position_id="EXAMPLE-E",
        principal=Decimal("3740387"),
        rate_type=RateType.FLOATING,
        maturity_date=date(2025, 3, 15),
        instrument_class=IRRBBInstrumentClass.CREDIT,
        payment_structure=PaymentStructure.AMORTIZING,
        next_repricing_date=date(2024, 3, 15),
        product_type="SEMIVARIABLE_RATE_LOAN",
    )
    schedule = tuple(
        _record(
            payment_date=payment_date,
            amount=Decimal("254479"),
            flow_type="INSTALLMENT",
            source=f"SUGEF_EXAMPLE_E:{payment_date.isoformat()}",
            outstanding_principal_after=(
                Decimal("2747129") if payment_date == date(2024, 3, 15) else None
            ),
        )
        for payment_date in _remaining_monthly_payments(17)
    )

    assert _bucket_amounts(position=position, schedule=schedule) == {
        IRRBBTimeBucket.DAY_1_TO_MONTH_1: Decimal("254479"),
        IRRBBTimeBucket.MONTH_1_TO_3: Decimal("508958"),
        IRRBBTimeBucket.MONTH_3_TO_6: Decimal("3256087"),
    }
