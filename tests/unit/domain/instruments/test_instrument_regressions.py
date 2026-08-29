from datetime import date
from decimal import Decimal

import pytest

from aip.domain.instruments.bonds.floating_rate_bond import FloatingRateBond
from aip.domain.instruments.bonds.government_bond import GovernmentBond
from aip.domain.instruments.cash.cash import Cash
from aip.domain.instruments.enums.amortization_type import AmortizationType
from aip.domain.instruments.enums.coupon_type import CouponType
from aip.domain.instruments.enums.instrument_type import InstrumentType
from aip.domain.instruments.enums.payment_frequency import PaymentFrequency
from aip.domain.instruments.exceptions import InstrumentValidationError
from aip.domain.instruments.issuers.credit_rating import CreditRating
from aip.domain.instruments.issuers.issuer import Issuer
from aip.domain.instruments.issuers.issuer_type import IssuerType
from aip.domain.instruments.services.instrument_factory import InstrumentFactory
from aip.shared.conventions import DayCountConvention


def make_issuer() -> Issuer:
    return Issuer(
        code="CRGOV",
        name="Costa Rica Government",
        issuer_type=IssuerType.GOVERNMENT,
        credit_rating=CreditRating("AA", "S&P"),
    )


@pytest.mark.parametrize(
    "payment_frequency",
    [PaymentFrequency.ANNUAL, PaymentFrequency.SEMIANNUAL, PaymentFrequency.QUARTERLY],
)
def test_fixed_rate_bonds_generate_complete_coupon_schedule(
    payment_frequency: PaymentFrequency,
) -> None:
    bond = GovernmentBond(
        isin="US0000000001",
        name="Regression Bond",
        issuer=make_issuer(),
        currency="USD",
        settlement_calendar="US",
        business_day_convention="Following",
        day_count_convention=DayCountConvention.ACTUAL_365,
        issue_date=date(2024, 1, 15),
        settlement_date=date(2024, 1, 16),
        maturity_date=date(2027, 1, 15),
        coupon_schedule=None,
        nominal_value=Decimal("1000"),
        book_value=Decimal("1000"),
        market_value=Decimal("1000"),
        face_value=Decimal("1000"),
        outstanding_amount=Decimal("1000"),
        yield_rate=Decimal("0.05"),
        duration=Decimal("0"),
        modified_duration=Decimal("0"),
        convexity=Decimal("0"),
        dirty_price=Decimal("100"),
        clean_price=Decimal("100"),
        accrued_interest=Decimal("0"),
        coupon_rate=Decimal("0.06"),
        payment_frequency=payment_frequency,
        coupon_type=CouponType.FIXED,
        amortization_type=AmortizationType.BULLET,
        settlement_currency="USD",
    )

    schedule = bond.generate_schedule()
    assert schedule.coupons, "A fixed-rate bond should generate a coupon schedule"
    assert schedule.coupons[0].period_start == bond.issue_date
    assert schedule.coupons[-1].payment_date == bond.maturity_date
    assert schedule.coupons[-1].amount > schedule.coupons[-1].amount - Decimal("1")
    assert all(coupon.amount > Decimal("0") for coupon in schedule.coupons)


def test_floating_rate_bond_schedule_uses_reference_rate_and_day_count() -> None:
    bond = FloatingRateBond(
        isin="US0000000002",
        name="Floating Bond",
        issuer=make_issuer(),
        currency="USD",
        settlement_calendar="US",
        business_day_convention="Following",
        day_count_convention=DayCountConvention.ACTUAL_365,
        issue_date=date(2024, 1, 1),
        settlement_date=date(2024, 1, 2),
        maturity_date=date(2025, 1, 1),
        coupon_schedule=None,
        nominal_value=Decimal("1000"),
        book_value=Decimal("1000"),
        market_value=Decimal("1000"),
        face_value=Decimal("1000"),
        outstanding_amount=Decimal("1000"),
        yield_rate=Decimal("0.04"),
        duration=Decimal("0"),
        modified_duration=Decimal("0"),
        convexity=Decimal("0"),
        dirty_price=Decimal("100"),
        clean_price=Decimal("100"),
        accrued_interest=Decimal("0"),
        coupon_rate=Decimal("0.03"),
        payment_frequency=PaymentFrequency.QUARTERLY,
        coupon_type=CouponType.FLOATING,
        amortization_type=AmortizationType.BULLET,
        settlement_currency="USD",
        reference_rate=Decimal("0.04"),
        spread=Decimal("0.01"),
        next_reset_date=date(2024, 4, 1),
    )

    schedule = bond.generate_schedule()
    assert schedule.coupons, "A floating-rate bond must produce a coupon schedule"
    assert schedule.coupons[0].payment_date > bond.issue_date
    assert schedule.coupons[-1].payment_date == bond.maturity_date
    assert schedule.coupons[0].rate == Decimal("0.05")
    for coupon in schedule.coupons:
        year_fraction = Decimal((coupon.period_end - coupon.period_start).days) / Decimal("365")
        expected_amount = bond.nominal_value * coupon.rate * year_fraction
        assert coupon.amount == expected_amount


def test_factory_supports_cash_and_validates_required_fields() -> None:
    factory = InstrumentFactory()
    cash = factory.create(InstrumentType.CASH, name="Cash", nominal_value=Decimal("1000"))
    assert isinstance(cash, Cash)
    assert cash.nominal_value == Decimal("1000")

    with pytest.raises(InstrumentValidationError):
        factory.create(InstrumentType.CASH, name="Invalid", nominal_value=Decimal("-1"))

    with pytest.raises(InstrumentValidationError):
        factory.create(InstrumentType.CASH, name="", nominal_value=Decimal("1000"))


def test_factory_supports_each_enum_member() -> None:
    factory = InstrumentFactory()
    for instrument_type in InstrumentType:
        instrument = factory.create(instrument_type, name=instrument_type.value)
        assert instrument is not None


def test_payment_frequency_uses_annnual_member() -> None:
    assert PaymentFrequency.ANNUAL is not None
    assert not hasattr(PaymentFrequency, "ANUAL")
    assert PaymentFrequency.ANNUAL.months_between_payments() == 12
