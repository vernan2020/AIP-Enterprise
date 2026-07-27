from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.domain.instruments.bonds.government_bond import GovernmentBond
from aip.domain.instruments.bonds.treasury_bill import TreasuryBill
from aip.domain.instruments.bonds.zero_coupon_bond import ZeroCouponBond
from aip.domain.instruments.bonds.floating_rate_bond import FloatingRateBond
from aip.domain.instruments.cash.cash import Cash
from aip.domain.instruments.enums.payment_frequency import PaymentFrequency
from aip.domain.instruments.money_market.certificate_of_deposit import CertificateOfDeposit
from aip.domain.instruments.money_market.commercial_paper import CommercialPaper
from aip.domain.instruments.money_market.repo import Repo
from aip.domain.instruments.money_market.reverse_repo import ReverseRepo
from aip.domain.instruments.issuers.issuer import Issuer
from aip.domain.instruments.issuers.issuer_type import IssuerType
from aip.domain.pricing import (
    PricingEngine,
    PricingMethod,
    PricingRequest,
    PricingResult,
    PricingError,
)


def _issuer() -> Issuer:
    return Issuer(code="GOV1", name="Government", issuer_type=IssuerType.GOVERNMENT)


def _government_bond() -> GovernmentBond:
    return GovernmentBond(
        isin="CR1234567890",
        name="Government Bond",
        issuer=_issuer(),
        currency="USD",
        settlement_calendar="CR",
        business_day_convention="Unadjusted",
        day_count_convention=None,
        issue_date=date(2024, 1, 1),
        settlement_date=date(2024, 1, 3),
        maturity_date=date(2026, 1, 1),
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
        dirty_price=Decimal("0"),
        clean_price=Decimal("0"),
        accrued_interest=Decimal("0"),
        coupon_rate=Decimal("0.04"),
        payment_frequency=PaymentFrequency.SEMIANNUAL,
    )


def _treasury_bill() -> TreasuryBill:
    return TreasuryBill(
        isin="TB1234567890",
        name="Treasury Bill",
        issuer=_issuer(),
        currency="USD",
        settlement_calendar="CR",
        business_day_convention="Unadjusted",
        day_count_convention=None,
        issue_date=date(2024, 1, 1),
        settlement_date=date(2024, 1, 3),
        maturity_date=date(2024, 6, 1),
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
        dirty_price=Decimal("0"),
        clean_price=Decimal("0"),
        accrued_interest=Decimal("0"),
        discount_rate=Decimal("0.04"),
    )


def _zero_coupon() -> ZeroCouponBond:
    return ZeroCouponBond(
        isin="ZC1234567890",
        name="Zero Coupon",
        issuer=_issuer(),
        currency="USD",
        settlement_calendar="CR",
        business_day_convention="Unadjusted",
        day_count_convention=None,
        issue_date=date(2024, 1, 1),
        settlement_date=date(2024, 1, 3),
        maturity_date=date(2025, 1, 1),
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
        dirty_price=Decimal("0"),
        clean_price=Decimal("0"),
        accrued_interest=Decimal("0"),
    )


def _floating_rate_bond() -> FloatingRateBond:
    return FloatingRateBond(
        isin="FR1234567890",
        name="Floating Rate Bond",
        issuer=_issuer(),
        currency="USD",
        settlement_calendar="CR",
        business_day_convention="Unadjusted",
        day_count_convention=None,
        issue_date=date(2024, 1, 1),
        settlement_date=date(2024, 1, 3),
        maturity_date=date(2026, 1, 1),
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
        dirty_price=Decimal("0"),
        clean_price=Decimal("0"),
        accrued_interest=Decimal("0"),
        reference_rate=Decimal("0.03"),
        spread=Decimal("0.01"),
        next_reset_date=date(2024, 7, 1),
    )


def _cash() -> Cash:
    return Cash(
        isin="CASH123456",
        name="Cash",
        issuer=_issuer(),
        currency="USD",
        settlement_calendar="CR",
        business_day_convention="Unadjusted",
        day_count_convention=None,
        issue_date=date(2024, 1, 1),
        settlement_date=date(2024, 1, 3),
        maturity_date=date(2024, 1, 3),
        coupon_schedule=None,
        nominal_value=Decimal("1000"),
        book_value=Decimal("1000"),
        market_value=Decimal("1000"),
        face_value=Decimal("1000"),
        outstanding_amount=Decimal("1000"),
        yield_rate=Decimal("0"),
        duration=Decimal("0"),
        modified_duration=Decimal("0"),
        convexity=Decimal("0"),
        dirty_price=Decimal("0"),
        clean_price=Decimal("0"),
        accrued_interest=Decimal("0"),
    )


def _cd() -> CertificateOfDeposit:
    return CertificateOfDeposit(
        isin="CD1234567890",
        name="Certificate of Deposit",
        issuer=_issuer(),
        currency="USD",
        settlement_calendar="CR",
        business_day_convention="Unadjusted",
        day_count_convention=None,
        issue_date=date(2024, 1, 1),
        settlement_date=date(2024, 1, 3),
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
        dirty_price=Decimal("0"),
        clean_price=Decimal("0"),
        accrued_interest=Decimal("0"),
    )


def _commercial_paper() -> CommercialPaper:
    return CommercialPaper(
        isin="CP1234567890",
        name="Commercial Paper",
        issuer=_issuer(),
        currency="USD",
        settlement_calendar="CR",
        business_day_convention="Unadjusted",
        day_count_convention=None,
        issue_date=date(2024, 1, 1),
        settlement_date=date(2024, 1, 3),
        maturity_date=date(2024, 6, 1),
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
        dirty_price=Decimal("0"),
        clean_price=Decimal("0"),
        accrued_interest=Decimal("0"),
    )


def _repo() -> Repo:
    return Repo(
        isin="REPO1234567",
        name="Repo",
        issuer=_issuer(),
        currency="USD",
        settlement_calendar="CR",
        business_day_convention="Unadjusted",
        day_count_convention=None,
        issue_date=date(2024, 1, 1),
        settlement_date=date(2024, 1, 3),
        maturity_date=date(2024, 2, 1),
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
        dirty_price=Decimal("0"),
        clean_price=Decimal("0"),
        accrued_interest=Decimal("0"),
    )


def _reverse_repo() -> ReverseRepo:
    return ReverseRepo(
        isin="RREPO123456",
        name="Reverse Repo",
        issuer=_issuer(),
        currency="USD",
        settlement_calendar="CR",
        business_day_convention="Unadjusted",
        day_count_convention=None,
        issue_date=date(2024, 1, 1),
        settlement_date=date(2024, 1, 3),
        maturity_date=date(2024, 2, 1),
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
        dirty_price=Decimal("0"),
        clean_price=Decimal("0"),
        accrued_interest=Decimal("0"),
    )


def test_pricing_engine_supports_all_required_instrument_types() -> None:
    engine = PricingEngine()
    instruments = [
        _government_bond(),
        _treasury_bill(),
        _zero_coupon(),
        _floating_rate_bond(),
        _cash(),
        _cd(),
        _commercial_paper(),
        _repo(),
        _reverse_repo(),
    ]

    for instrument in instruments:
        request = PricingRequest(
            valuation_date=date(2024, 1, 3),
            instrument=instrument,
            market_yield=Decimal("0.05"),
            pricing_method=PricingMethod.MARKET_VALUE,
        )
        result = engine.price(request)
        assert isinstance(result, PricingResult)
        assert result.clean_price >= Decimal("0")
        assert result.dirty_price >= Decimal("0")
        assert result.accrued_interest >= Decimal("0")
        assert result.market_value >= Decimal("0")
        assert result.yield_ >= Decimal("0")


def test_pricing_result_contains_the_requested_metrics() -> None:
    engine = PricingEngine()
    request = PricingRequest(
        valuation_date=date(2024, 1, 3),
        instrument=_government_bond(),
        market_yield=Decimal("0.05"),
        pricing_method=PricingMethod.YIELD_TO_MATURITY,
    )
    result = engine.price(request)

    assert result.clean_price > Decimal("0")
    assert result.dirty_price > Decimal("0")
    assert result.accrued_interest >= Decimal("0")
    assert result.market_value > Decimal("0")
    assert result.yield_ >= Decimal("0")
    assert result.duration >= Decimal("0")
    assert result.modified_duration >= Decimal("0")
    assert result.convexity >= Decimal("0")
    assert result.dv01 >= Decimal("0")
    assert result.pvbp >= Decimal("0")
    assert result.warnings == ()
    assert result.assumptions == ()


def test_pricing_engine_raises_for_unsupported_instruments() -> None:
    engine = PricingEngine()
    request = PricingRequest(
        valuation_date=date(2024, 1, 3),
        instrument=object(),
        market_yield=Decimal("0.05"),
        pricing_method=PricingMethod.YIELD_TO_MATURITY,
    )

    with pytest.raises(PricingError):
        engine.price(request)
