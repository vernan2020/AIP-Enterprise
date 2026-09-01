from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.domain.instruments.base.financial_instrument import FinancialInstrument
from aip.domain.instruments.base.fixed_income_instrument import FixedIncomeInstrument
from aip.domain.instruments.bonds.bond import Bond
from aip.domain.instruments.bonds.floating_rate_bond import FloatingRateBond
from aip.domain.instruments.bonds.government_bond import GovernmentBond
from aip.domain.instruments.bonds.treasury_bill import TreasuryBill
from aip.domain.instruments.bonds.zero_coupon_bond import ZeroCouponBond
from aip.domain.instruments.cash.cash import Cash
from aip.domain.instruments.enums.instrument_type import InstrumentType
from aip.domain.instruments.enums.payment_frequency import PaymentFrequency
from aip.domain.instruments.exceptions import InstrumentFactoryError, InstrumentValidationError
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


class ConcreteFinancialInstrument(FinancialInstrument):
    def calculate_price(self) -> Decimal:
        return self.nominal_value

    def calculate_yield(self) -> Decimal:
        return self.yield_rate


def make_issuer() -> Issuer:
    return Issuer(
        code="CRGOV",
        name="Costa Rica Government",
        issuer_type=IssuerType.GOVERNMENT,
        credit_rating=CreditRating("AA", "S&P"),
    )


def make_common_kwargs(**overrides: object) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "isin": "US0000000001",
        "name": "Test Instrument",
        "issuer": make_issuer(),
        "currency": "USD",
        "settlement_calendar": "US",
        "business_day_convention": "Following",
        "day_count_convention": DayCountConvention.ACTUAL_365,
        "issue_date": date(2024, 1, 1),
        "settlement_date": date(2024, 1, 2),
        "maturity_date": date(2025, 1, 1),
        "coupon_schedule": None,
        "nominal_value": Decimal("1000"),
        "book_value": Decimal("1000"),
        "market_value": Decimal("1000"),
        "face_value": Decimal("1000"),
        "outstanding_amount": Decimal("1000"),
        "yield_rate": Decimal("0.05"),
        "duration": Decimal("0"),
        "modified_duration": Decimal("0"),
        "convexity": Decimal("0"),
        "dirty_price": Decimal("100"),
        "clean_price": Decimal("100"),
        "accrued_interest": Decimal("0"),
        "settlement_currency": "USD",
    }
    kwargs.update(overrides)
    return kwargs


def test_financial_instrument_initializes_defaults_and_accessors() -> None:
    instrument = ConcreteFinancialInstrument(**make_common_kwargs())

    assert instrument.instrument_name == "Test Instrument"
    assert instrument.settlement_currency_code == "USD"
    assert instrument.nominal_value == Decimal("1000")
    assert instrument.clean_price == Decimal("100")
    assert instrument.dirty_price == Decimal("100")
    assert instrument.accrued_interest == Decimal("0")
    assert instrument.issuer_name == "Costa Rica Government"
    assert instrument.isis == "US0000000001"
    assert instrument.to_dict()["settlement_currency"] == "USD"

    instrument.clean_price = Decimal("120")
    instrument.dirty_price = Decimal("125")
    instrument.accrued_interest = Decimal("5")
    instrument.yield_rate = Decimal("0.06")
    instrument.duration = Decimal("1")
    instrument.modified_duration = Decimal("2")
    instrument.convexity = Decimal("3")
    instrument.nominal_value = Decimal("2000")
    instrument.book_value = Decimal("2100")
    instrument.market_value = Decimal("2200")
    instrument.face_value = Decimal("2300")
    instrument.outstanding_amount = Decimal("2400")

    assert instrument.clean_price == Decimal("120")
    assert instrument.dirty_price == Decimal("125")
    assert instrument.accrued_interest == Decimal("5")
    assert instrument.yield_rate == Decimal("0.06")
    assert instrument.duration == Decimal("1")
    assert instrument.modified_duration == Decimal("2")
    assert instrument.convexity == Decimal("3")


def test_financial_instrument_converts_int_and_float_inputs_and_updates_properties() -> None:
    instrument = ConcreteFinancialInstrument(
        **make_common_kwargs(
            clean_price=1.5,
            dirty_price=2.25,
            accrued_interest=3.5,
            yield_rate=1,
            duration=1.75,
            modified_duration=2.5,
            convexity=3.25,
            nominal_value=1000,
            book_value=1100,
            market_value=1200,
            face_value=1300,
            outstanding_amount=1400,
        )
    )

    assert instrument.clean_price == Decimal("1.5")
    assert instrument.dirty_price == Decimal("2.25")
    assert instrument.accrued_interest == Decimal("3.5")
    assert instrument.yield_rate == Decimal("1")
    assert instrument.duration == Decimal("1.75")
    assert instrument.modified_duration == Decimal("2.5")
    assert instrument.convexity == Decimal("3.25")

    instrument.clean_price = 10.5
    instrument.dirty_price = 11.25
    instrument.accrued_interest = 12
    instrument.yield_rate = Decimal("0.06")
    instrument.duration = 1
    instrument.modified_duration = 2
    instrument.convexity = 3
    instrument.nominal_value = 2000
    instrument.book_value = 2100
    instrument.market_value = 2200
    instrument.face_value = 2300
    instrument.outstanding_amount = 2400

    assert instrument.clean_price == Decimal("10.5")
    assert instrument.dirty_price == Decimal("11.25")
    assert instrument.accrued_interest == Decimal("12")
    assert instrument.yield_rate == Decimal("0.06")
    assert instrument.duration == Decimal("1")
    assert instrument.modified_duration == Decimal("2")
    assert instrument.convexity == Decimal("3")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("isin", "", "ISIN"),
        ("name", "   ", "Instrument name"),
        ("issue_date", date(2026, 1, 1), "Issue date"),
        ("settlement_date", date(2026, 1, 1), "Settlement date"),
        ("nominal_value", Decimal("0"), "Nominal value"),
        ("face_value", Decimal("0"), "Face value"),
        ("outstanding_amount", Decimal("0"), "Outstanding amount"),
        ("yield_rate", Decimal("-0.01"), "Yield rate"),
    ],
)
def test_financial_instrument_validation_errors(field: str, value: object, message: str) -> None:
    kwargs = make_common_kwargs()
    kwargs[field] = value
    with pytest.raises(InstrumentValidationError) as exc_info:
        ConcreteFinancialInstrument(**kwargs)
    assert message in str(exc_info.value)


def test_fixed_income_instrument_builds_coupon_schedule_and_rejects_negative_coupon_rate() -> None:
    instrument = FixedIncomeInstrument(
        **make_common_kwargs(
            coupon_rate=Decimal("0.06"), payment_frequency=PaymentFrequency.SEMIANNUAL
        )
    )
    assert instrument.coupon_schedule is not None
    assert instrument.coupon_schedule.coupons

    with pytest.raises(InstrumentValidationError) as exc_info:
        FixedIncomeInstrument(**make_common_kwargs(coupon_rate=Decimal("-0.01")))
    assert "Coupon rate" in str(exc_info.value)


def test_fixed_income_instrument_normalizes_string_payment_frequency() -> None:
    instrument = FixedIncomeInstrument(
        **make_common_kwargs(coupon_rate=Decimal("0.06"), payment_frequency="quarterly")
    )

    assert instrument.payment_frequency is PaymentFrequency.QUARTERLY
    assert instrument.coupon_schedule is not None
    assert instrument.coupon_schedule.coupons


def test_fixed_income_calculate_price_and_yield_cover_branch_paths() -> None:
    instrument = FixedIncomeInstrument(
        **make_common_kwargs(
            coupon_rate=Decimal("0.06"), payment_frequency=PaymentFrequency.SEMIANNUAL
        )
    )
    instrument.coupon_schedule = None
    assert instrument.calculate_price() == instrument.clean_price

    instrument.coupon_schedule = CouponSchedule.from_frequency(
        issue_date=instrument.issue_date,
        maturity_date=instrument.maturity_date,
        payment_frequency=instrument.payment_frequency,
        coupon_rate=instrument.coupon_rate,
        nominal_value=instrument.nominal_value,
    )
    assert instrument.calculate_price() == instrument.clean_price

    instrument.clean_price = Decimal("0")
    assert instrument.calculate_yield() == Decimal("0")

    instrument.clean_price = Decimal("10")
    assert instrument.calculate_yield() == instrument.yield_rate


def test_bond_calculates_price_and_generates_schedule() -> None:
    bond = Bond(
        **make_common_kwargs(coupon_rate=Decimal("0.08"), payment_frequency=PaymentFrequency.ANNUAL)
    )

    assert bond.calculate_yield() == bond.yield_rate
    assert bond.calculate_price() > Decimal("0")
    assert bond.generate_schedule().coupons


def test_bond_calculate_price_and_generate_schedule_cover_none_and_empty_branches() -> None:
    bond = Bond(
        **make_common_kwargs(coupon_rate=Decimal("0.08"), payment_frequency=PaymentFrequency.ANNUAL)
    )
    bond.coupon_schedule = None
    assert bond.calculate_price() == bond.clean_price

    bond.coupon_schedule = CouponSchedule()
    assert bond.generate_schedule().coupons


def test_government_bond_sets_metadata_for_non_government_issuer() -> None:
    issuer = make_issuer()
    issuer = Issuer(
        code=issuer.code,
        name="Private Issuer",
        issuer_type=issuer.issuer_type,
        credit_rating=issuer.credit_rating,
    )
    bond = GovernmentBond(
        **make_common_kwargs(
            coupon_rate=Decimal("0.07"), payment_frequency=PaymentFrequency.QUARTERLY, issuer=issuer
        )
    )

    assert bond.calculate_price() > Decimal("0")
    assert bond.metadata["jurisdiction"] == "CR"


def test_treasury_bill_and_zero_coupon_cover_branch_paths() -> None:
    bill = TreasuryBill(
        **make_common_kwargs(
            discount_rate=Decimal("0.04"),
            issue_date=date(2024, 1, 1),
            settlement_date=date(2024, 1, 1),
            maturity_date=date(2024, 1, 1),
        )
    )
    assert bill.calculate_price() == bill.face_value
    assert bill.calculate_yield() > Decimal("0")

    zero_coupon = ZeroCouponBond(**make_common_kwargs(coupon_rate=Decimal("0")))
    zero_coupon.clean_price = Decimal("0")
    assert zero_coupon.calculate_yield() == Decimal("0")


def test_treasury_bill_rejects_negative_discount_rate_and_prices() -> None:
    bill = TreasuryBill(**make_common_kwargs(discount_rate=Decimal("0.04")))
    assert bill.calculate_price() < bill.face_value
    assert bill.calculate_yield() > Decimal("0")

    with pytest.raises(InstrumentValidationError) as exc_info:
        TreasuryBill(**make_common_kwargs(discount_rate=Decimal("-0.01")))
    assert "Discount rate" in str(exc_info.value)


def test_zero_coupon_bond_prices_and_yields() -> None:
    bond = ZeroCouponBond(**make_common_kwargs(coupon_rate=Decimal("0")))

    assert bond.calculate_price() > Decimal("0")
    assert bond.calculate_yield() > Decimal("0")


def test_floating_rate_bond_supports_reference_rate_spread_and_reset_validation() -> None:
    bond = FloatingRateBond(
        **make_common_kwargs(
            coupon_rate=Decimal("0.03"),
            payment_frequency=PaymentFrequency.QUARTERLY,
            reference_rate=Decimal("0.04"),
            spread=Decimal("0.01"),
            next_reset_date=date(2024, 4, 1),
        )
    )

    assert bond.reference_rate == Decimal("0.04")
    assert bond.spread == Decimal("0.01")
    assert bond.generate_schedule().coupons[0].rate == Decimal("0.05")
    assert bond.generate_schedule().coupons[0].payment_date > bond.issue_date
    assert bond.calculate_price() > Decimal("0")
    assert bond.calculate_yield() == bond.yield_rate

    with pytest.raises(InstrumentValidationError) as exc_info:
        FloatingRateBond(
            **make_common_kwargs(
                reference_rate=Decimal("0.04"),
                spread=Decimal("-0.01"),
                next_reset_date=date(2024, 4, 1),
            )
        )
    assert "Spread" in str(exc_info.value)

    with pytest.raises(InstrumentValidationError) as exc_info:
        FloatingRateBond(
            **make_common_kwargs(
                reference_rate=Decimal("-0.01"),
                spread=Decimal("0.01"),
                next_reset_date=date(2024, 4, 1),
            )
        )
    assert "Reference rate" in str(exc_info.value)

    with pytest.raises(InstrumentValidationError) as exc_info:
        FloatingRateBond(
            **make_common_kwargs(
                reference_rate=Decimal("0.04"),
                spread=Decimal("0.01"),
                next_reset_date=date(2023, 12, 31),
            )
        )
    assert "reset date" in str(exc_info.value)

    with pytest.raises(InstrumentValidationError) as exc_info:
        FloatingRateBond(
            **make_common_kwargs(
                reference_rate=Decimal("0.04"),
                spread=Decimal("0.01"),
                next_reset_date=date(2025, 12, 31),
            )
        )
    assert "reset date" in str(exc_info.value)


def test_floating_rate_bond_raises_when_schedule_generation_returns_no_coupons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_from_frequency(*args: object, **kwargs: object) -> CouponSchedule:
        return CouponSchedule()

    monkeypatch.setattr(
        "aip.domain.instruments.bonds.floating_rate_bond.CouponSchedule.from_frequency",
        fake_from_frequency,
    )

    with pytest.raises(InstrumentValidationError) as exc_info:
        FloatingRateBond(
            **make_common_kwargs(
                reference_rate=Decimal("0.04"),
                spread=Decimal("0.01"),
                next_reset_date=date(2024, 4, 1),
            )
        )
    assert "schedule could not be generated" in str(exc_info.value)


def test_coupon_schedule_supports_multiple_frequencies_and_stubs() -> None:
    monthly = CouponSchedule.from_frequency(
        issue_date=date(2024, 1, 1),
        maturity_date=date(2025, 1, 1),
        payment_frequency=PaymentFrequency.MONTHLY,
        coupon_rate=Decimal("0.06"),
        nominal_value=Decimal("1000"),
    )
    assert len(monthly.coupons) > 1

    quarterly = CouponSchedule.from_frequency(
        issue_date=date(2024, 1, 1),
        maturity_date=date(2025, 1, 1),
        payment_frequency=PaymentFrequency.QUARTERLY,
        coupon_rate=Decimal("0.06"),
        nominal_value=Decimal("1000"),
        include_initial_coupon=False,
    )
    assert quarterly.coupons[0].payment_date > date(2024, 1, 1)

    annual = CouponSchedule.from_frequency(
        issue_date=date(2024, 1, 1),
        maturity_date=date(2025, 1, 1),
        payment_frequency=PaymentFrequency.ANNUAL,
        coupon_rate=Decimal("0.06"),
        nominal_value=Decimal("1000"),
        include_principal=True,
    )
    assert annual.coupons[-1].amount > annual.coupons[0].amount

    one_period = CouponSchedule.from_frequency(
        issue_date=date(2024, 1, 1),
        maturity_date=date(2024, 1, 1),
        payment_frequency=PaymentFrequency.SEMIANNUAL,
        coupon_rate=Decimal("0.06"),
        nominal_value=Decimal("1000"),
    )
    assert one_period.coupons == []


def test_coupon_schedule_helper_methods_cover_edge_cases() -> None:
    assert CouponSchedule._advance_months(date(2024, 1, 1), 0) is None
    assert CouponSchedule._advance_months(date(2024, 1, 1), 1) == date(2024, 2, 1)
    assert CouponSchedule._adjust_business_day(date(2024, 6, 1)) == date(2024, 6, 3)


def test_money_market_instruments_calculate_prices_and_yields() -> None:
    cd = CertificateOfDeposit(**make_common_kwargs())
    paper = CommercialPaper(**make_common_kwargs())
    repo = Repo(**make_common_kwargs())
    reverse = ReverseRepo(**make_common_kwargs())

    assert cd.calculate_price() == cd.nominal_value
    assert paper.calculate_price() == paper.nominal_value
    assert repo.calculate_price() == repo.nominal_value
    assert reverse.calculate_price() == reverse.nominal_value
    assert cd.calculate_yield() == cd.yield_rate
    assert paper.calculate_yield() == paper.yield_rate
    assert repo.calculate_yield() == repo.yield_rate
    assert reverse.calculate_yield() == reverse.yield_rate


def test_cash_and_investment_fund_concrete_instruments_work() -> None:
    cash = Cash(**make_common_kwargs())
    fund = InvestmentFund(**make_common_kwargs())

    assert cash.calculate_price() == cash.nominal_value
    assert cash.calculate_yield() == Decimal("0")
    assert fund.calculate_price() == fund.clean_price
    assert fund.calculate_yield() == fund.yield_rate


@pytest.mark.parametrize("instrument_type", list(InstrumentType))
def test_factory_creates_every_supported_instrument_type(instrument_type: InstrumentType) -> None:
    factory = InstrumentFactory()
    instrument = factory.create(instrument_type, name=instrument_type.value)
    assert instrument is not None


def test_factory_validates_missing_fields_and_unsupported_types() -> None:
    factory = InstrumentFactory()

    with pytest.raises(InstrumentValidationError) as exc_info:
        factory.create(InstrumentType.CASH, name="", nominal_value=Decimal("1000"))
    assert "Instrument name" in str(exc_info.value)

    with pytest.raises(InstrumentValidationError) as exc_info:
        factory.create(InstrumentType.CASH, name="Cash", nominal_value=Decimal("-1"))
    assert "Nominal value" in str(exc_info.value)

    with pytest.raises((AttributeError, InstrumentFactoryError)) as exc_info:
        factory.create("unsupported", name="Cash")  # type: ignore[arg-type]
    assert "Unsupported" in str(exc_info.value) or "value" in str(exc_info.value)

    with pytest.raises((AttributeError, TypeError)):
        factory.create(InstrumentType.CASH, name=123, nominal_value=Decimal("1000"))


def test_factory_ignores_unexpected_kwargs_and_uses_direct_values() -> None:
    factory = InstrumentFactory()
    cash = factory.create(
        InstrumentType.CASH, name="Cash", nominal_value=Decimal("1200"), unexpected="value"
    )
    assert cash.nominal_value == Decimal("1200")


def test_issuers_and_ratings_preserve_values() -> None:
    rating = CreditRating(value="A", agency="S&P")
    issuer = Issuer(
        code="AAA", name="Issuer", issuer_type=IssuerType.GOVERNMENT, credit_rating=rating
    )

    assert rating.value == "A"
    assert issuer.credit_rating is rating
    assert issuer.issuer_type is IssuerType.GOVERNMENT


def test_domain_exceptions_are_domain_specific_and_have_codes() -> None:
    assert issubclass(InstrumentValidationError, Exception)
    assert issubclass(InstrumentFactoryError, Exception)
    assert InstrumentValidationError.default_code == "INSTRUMENT_VALIDATION_ERROR"
    assert InstrumentFactoryError.default_code == "INSTRUMENT_FACTORY_ERROR"
