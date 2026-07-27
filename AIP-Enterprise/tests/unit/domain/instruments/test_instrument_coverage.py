from datetime import date
from decimal import Decimal

from aip.domain.instruments.base.financial_instrument import FinancialInstrument
from aip.domain.instruments.bonds.government_bond import GovernmentBond
from aip.domain.instruments.bonds.treasury_bill import TreasuryBill
from aip.domain.instruments.bonds.zero_coupon_bond import ZeroCouponBond
from aip.domain.instruments.cash.cash import Cash
from aip.domain.instruments.enums.amortization_type import AmortizationType
from aip.domain.instruments.enums.coupon_type import CouponType
from aip.domain.instruments.enums.instrument_type import InstrumentType
from aip.domain.instruments.enums.payment_frequency import PaymentFrequency
from aip.domain.instruments.funds.investment_fund import InvestmentFund
from aip.domain.instruments.issuers.credit_rating import CreditRating
from aip.domain.instruments.issuers.issuer import Issuer
from aip.domain.instruments.issuers.issuer_type import IssuerType
from aip.domain.instruments.money_market.certificate_of_deposit import CertificateOfDeposit
from aip.domain.instruments.money_market.commercial_paper import CommercialPaper
from aip.domain.instruments.money_market.repo import Repo
from aip.domain.instruments.money_market.reverse_repo import ReverseRepo
from aip.domain.instruments.schedules.coupon_schedule import CouponSchedule
from aip.domain.instruments.services.instrument_factory import InstrumentFactory
from aip.shared.conventions import DayCountConvention


def make_issuer() -> Issuer:
    return Issuer(
        code="CRGOV",
        name="Costa Rica Government",
        issuer_type=IssuerType.GOVERNMENT,
        credit_rating=CreditRating("AA", "S&P"),
    )


def test_base_instrument_helpers_and_cash_paths() -> None:
    instrument = Cash(
        isin="CR0000000001",
        name="Cash",
        issuer=make_issuer(),
        currency="CRC",
        settlement_calendar="CR",
        business_day_convention="Following",
        day_count_convention=DayCountConvention.ACTUAL_365,
        issue_date=date(2024, 1, 1),
        settlement_date=date(2024, 1, 1),
        maturity_date=date(2024, 1, 1),
        coupon_schedule=CouponSchedule(),
        nominal_value=Decimal("1000"),
        book_value=Decimal("1000"),
        market_value=Decimal("1000"),
        face_value=Decimal("1000"),
        outstanding_amount=Decimal("1000"),
        yield_rate=Decimal("0"),
        duration=Decimal("0"),
        modified_duration=Decimal("0"),
        convexity=Decimal("0"),
        dirty_price=Decimal("1000"),
        clean_price=Decimal("1000"),
        accrued_interest=Decimal("0"),
        settlement_currency="CRC",
    )

    assert isinstance(instrument, FinancialInstrument)
    assert instrument.instrument_name == "Cash"
    assert instrument.settlement_currency_code == "CRC"
    assert instrument.isis == "CR0000000001"
    assert instrument.issuer_name == "Costa Rica Government"
    payload = instrument.to_dict()
    assert payload["name"] == "Cash"
    assert instrument.calculate_price() == Decimal("1000")
    assert instrument.calculate_yield() == Decimal("0")


def test_additional_bond_and_bill_paths() -> None:
    bond = GovernmentBond(
        isin="US0000001000",
        name="Bond",
        issuer=make_issuer(),
        currency="USD",
        settlement_calendar="US",
        business_day_convention="Following",
        day_count_convention=DayCountConvention.ACTUAL_365,
        issue_date=date(2024, 1, 1),
        settlement_date=date(2024, 1, 2),
        maturity_date=date(2034, 1, 1),
        coupon_schedule=CouponSchedule(),
        nominal_value=Decimal("100000"),
        book_value=Decimal("100000"),
        market_value=Decimal("102000"),
        face_value=Decimal("100000"),
        outstanding_amount=Decimal("100000"),
        yield_rate=Decimal("0.06"),
        duration=Decimal("5"),
        modified_duration=Decimal("4.8"),
        convexity=Decimal("30"),
        dirty_price=Decimal("102"),
        clean_price=Decimal("100"),
        accrued_interest=Decimal("2"),
        coupon_rate=Decimal("0.05"),
        payment_frequency=PaymentFrequency.SEMIANNUAL,
        coupon_type=CouponType.FIXED,
        amortization_type=AmortizationType.BULLET,
        settlement_currency="USD",
    )
    bond.coupon_schedule = CouponSchedule()
    assert bond.generate_schedule().coupons
    assert bond.calculate_price() > Decimal("0")
    assert bond.calculate_yield() == Decimal("0.06")

    bill = TreasuryBill(
        isin="US0000001001",
        name="Bill",
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
    assert bill.calculate_price() < bill.face_value
    assert bill.calculate_yield() > Decimal("0")

    zero_coupon = ZeroCouponBond(
        isin="US0000001002",
        name="Zero",
        issuer=make_issuer(),
        currency="USD",
        settlement_calendar="US",
        business_day_convention="Following",
        day_count_convention=DayCountConvention.ACTUAL_365,
        issue_date=date(2024, 1, 1),
        settlement_date=date(2024, 1, 2),
        maturity_date=date(2025, 1, 1),
        coupon_schedule=CouponSchedule(),
        nominal_value=Decimal("1000"),
        book_value=Decimal("1000"),
        market_value=Decimal("1000"),
        face_value=Decimal("1000"),
        outstanding_amount=Decimal("1000"),
        yield_rate=Decimal("0.04"),
        duration=Decimal("0"),
        modified_duration=Decimal("0"),
        convexity=Decimal("0"),
        dirty_price=Decimal("1000"),
        clean_price=Decimal("1000"),
        accrued_interest=Decimal("0"),
        coupon_rate=Decimal("0"),
        payment_frequency=PaymentFrequency.ANNUAL,
        coupon_type=CouponType.ZERO,
        amortization_type=AmortizationType.BULLET,
        settlement_currency="USD",
    )
    assert zero_coupon.calculate_price() < zero_coupon.face_value
    assert zero_coupon.calculate_yield() > Decimal("0")


def test_factory_and_other_instrument_variants() -> None:
    factory = InstrumentFactory()
    for instrument_type in [
        InstrumentType.GOVERNMENT_BOND,
        InstrumentType.TREASURY_BILL,
        InstrumentType.ZERO_COUPON_BOND,
        InstrumentType.FLOATING_RATE_BOND,
        InstrumentType.CASH,
        InstrumentType.INVESTMENT_FUND,
        InstrumentType.CERTIFICATE_OF_DEPOSIT,
        InstrumentType.COMMERCIAL_PAPER,
        InstrumentType.REPO,
        InstrumentType.REVERSE_REPO,
    ]:
        instrument = factory.create(instrument_type, name=instrument_type.value)
        assert instrument is not None

    fund = InvestmentFund(
        isin="US0000001003",
        name="Fund",
        issuer=make_issuer(),
        currency="USD",
        settlement_calendar="US",
        business_day_convention="Following",
        day_count_convention=DayCountConvention.ACTUAL_365,
        issue_date=date(2024, 1, 1),
        settlement_date=date(2024, 1, 2),
        maturity_date=date(2024, 2, 2),
        coupon_schedule=CouponSchedule(),
        nominal_value=Decimal("1000"),
        book_value=Decimal("1000"),
        market_value=Decimal("1000"),
        face_value=Decimal("1000"),
        outstanding_amount=Decimal("1000"),
        yield_rate=Decimal("0.05"),
        duration=Decimal("0"),
        modified_duration=Decimal("0"),
        convexity=Decimal("0"),
        dirty_price=Decimal("1000"),
        clean_price=Decimal("1000"),
        accrued_interest=Decimal("0"),
        settlement_currency="USD",
    )
    assert fund.calculate_price() == Decimal("1000")
    assert fund.calculate_yield() == Decimal("0.05")

    for cls in [CertificateOfDeposit, CommercialPaper, Repo, ReverseRepo]:
        instrument = cls(
            isin="US0000001004",
            name=cls.__name__,
            issuer=make_issuer(),
            currency="USD",
            settlement_calendar="US",
            business_day_convention="Following",
            day_count_convention=DayCountConvention.ACTUAL_365,
            issue_date=date(2024, 1, 1),
            settlement_date=date(2024, 1, 2),
            maturity_date=date(2024, 2, 2),
            coupon_schedule=CouponSchedule(),
            nominal_value=Decimal("1000"),
            book_value=Decimal("1000"),
            market_value=Decimal("1000"),
            face_value=Decimal("1000"),
            outstanding_amount=Decimal("1000"),
            yield_rate=Decimal("0.05"),
            duration=Decimal("0"),
            modified_duration=Decimal("0"),
            convexity=Decimal("0"),
            dirty_price=Decimal("1000"),
            clean_price=Decimal("1000"),
            accrued_interest=Decimal("0"),
            settlement_currency="USD",
        )
        assert instrument.calculate_price() == Decimal("1000")
        assert instrument.calculate_yield() == Decimal("0.05")
