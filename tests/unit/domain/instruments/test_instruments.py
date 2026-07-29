from datetime import date
from decimal import Decimal

from src.aip.domain.instruments.bonds.floating_rate_bond import FloatingRateBond
from src.aip.domain.instruments.bonds.government_bond import GovernmentBond
from src.aip.domain.instruments.bonds.treasury_bill import TreasuryBill
from src.aip.domain.instruments.cash.cash import Cash
from src.aip.domain.instruments.enums.amortization_type import AmortizationType
from src.aip.domain.instruments.enums.coupon_type import CouponType
from src.aip.domain.instruments.enums.instrument_type import InstrumentType
from src.aip.domain.instruments.enums.payment_frequency import PaymentFrequency
from src.aip.domain.instruments.issuers.credit_rating import CreditRating
from src.aip.domain.instruments.issuers.issuer import Issuer
from src.aip.domain.instruments.issuers.issuer_type import IssuerType
from src.aip.domain.instruments.schedules.coupon_schedule import CouponSchedule
from src.aip.domain.instruments.services.instrument_factory import InstrumentFactory
from src.aip.shared.conventions import DayCountConvention


def make_issuer() -> Issuer:
    return Issuer(
        code="CRGOV",
        name="Costa Rica Government",
        issuer_type=IssuerType.GOVERNMENT,
        credit_rating=CreditRating("AA", "S&P"),
    )


def test_government_bond_generates_schedule_and_prices() -> None:
    bond = GovernmentBond(
        isin="US0378331005",
        name="Costa Rica 10Y Bond",
        issuer=make_issuer(),
        currency="CRC",
        settlement_calendar="CR",
        business_day_convention="Following",
        day_count_convention=DayCountConvention.ACTUAL_365,
        issue_date=date(2024, 1, 15),
        settlement_date=date(2024, 1, 16),
        maturity_date=date(2034, 1, 15),
        coupon_schedule=CouponSchedule(),
        nominal_value=Decimal("100000000"),
        book_value=Decimal("100000000"),
        market_value=Decimal("102000000"),
        face_value=Decimal("100000000"),
        outstanding_amount=Decimal("100000000"),
        yield_rate=Decimal("0.07"),
        duration=Decimal("7.5"),
        modified_duration=Decimal("7.2"),
        convexity=Decimal("55.4"),
        dirty_price=Decimal("102.5"),
        clean_price=Decimal("100.0"),
        accrued_interest=Decimal("2.5"),
        coupon_rate=Decimal("0.08"),
        payment_frequency=PaymentFrequency.SEMIANNUAL,
        coupon_type=CouponType.FIXED,
        amortization_type=AmortizationType.BULLET,
        settlement_currency="CRC",
    )

    assert bond.coupon_schedule is not None
    assert len(bond.coupon_schedule.coupons) >= 2
    assert bond.clean_price > Decimal("0")
    assert bond.dirty_price == bond.clean_price + bond.accrued_interest


def test_treasury_bill_pricing_is_discount_based() -> None:
    bill = TreasuryBill(
        isin="US0000000001",
        name="90 Day Treasury Bill",
        issuer=make_issuer(),
        currency="USD",
        settlement_calendar="US",
        business_day_convention="Following",
        day_count_convention=DayCountConvention.ACTUAL_360,
        issue_date=date(2024, 1, 1),
        settlement_date=date(2024, 1, 2),
        maturity_date=date(2024, 4, 1),
        coupon_schedule=CouponSchedule(),
        nominal_value=Decimal("1000"),
        book_value=Decimal("1000"),
        market_value=Decimal("950"),
        face_value=Decimal("1000"),
        outstanding_amount=Decimal("1000"),
        yield_rate=Decimal("0.05"),
        duration=Decimal("0"),
        modified_duration=Decimal("0"),
        convexity=Decimal("0"),
        dirty_price=Decimal("950"),
        clean_price=Decimal("950"),
        accrued_interest=Decimal("0"),
        discount_rate=Decimal("0.05"),
        settlement_currency="USD",
    )

    assert bill.clean_price < bill.face_value
    assert bill.accrued_interest == Decimal("0")


def test_floating_rate_bond_tracks_reference_and_spread() -> None:
    bond = FloatingRateBond(
        isin="US0000000002",
        name="Floating Rate Bond",
        issuer=make_issuer(),
        currency="USD",
        settlement_calendar="US",
        business_day_convention="Following",
        day_count_convention=DayCountConvention.ACTUAL_360,
        issue_date=date(2024, 1, 1),
        settlement_date=date(2024, 1, 2),
        maturity_date=date(2025, 1, 1),
        coupon_schedule=CouponSchedule(),
        nominal_value=Decimal("100000"),
        book_value=Decimal("100000"),
        market_value=Decimal("101000"),
        face_value=Decimal("100000"),
        outstanding_amount=Decimal("100000"),
        yield_rate=Decimal("0.04"),
        duration=Decimal("0.8"),
        modified_duration=Decimal("0.78"),
        convexity=Decimal("1.2"),
        dirty_price=Decimal("101.0"),
        clean_price=Decimal("100.0"),
        accrued_interest=Decimal("1.0"),
        coupon_rate=Decimal("0.03"),
        payment_frequency=PaymentFrequency.QUARTERLY,
        coupon_type=CouponType.FLOATING,
        amortization_type=AmortizationType.BULLET,
        settlement_currency="USD",
        reference_rate=Decimal("0.03"),
        spread=Decimal("0.01"),
        next_reset_date=date(2024, 7, 1),
    )

    assert bond.reference_rate == Decimal("0.03")
    assert bond.spread == Decimal("0.01")
    assert bond.next_reset_date == date(2024, 7, 1)
    assert bond.coupon_schedule.coupons[0].rate == Decimal("0.04")


def test_day_count_convention_and_factory() -> None:
    year_fraction = DayCountConvention.ACTUAL_365.calculate_year_fraction(date(2024, 1, 1), date(2024, 12, 31))
    assert year_fraction == Decimal("1")

    factory = InstrumentFactory()
    cash = factory.create(InstrumentType.CASH, name="Operating Cash", nominal_value=Decimal("1000"))
    assert isinstance(cash, Cash)
    assert cash.nominal_value == Decimal("1000")


def test_coupon_schedule_can_be_built_from_frequency() -> None:
    schedule = CouponSchedule.from_frequency(
        issue_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
        payment_frequency=PaymentFrequency.SEMIANNUAL,
        coupon_rate=Decimal("0.08"),
        nominal_value=Decimal("1000"),
    )

    assert len(schedule.coupons) == 5
    assert schedule.coupons[0].amount == Decimal("40")
