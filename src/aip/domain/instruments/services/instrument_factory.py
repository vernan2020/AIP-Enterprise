from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from aip.domain.instruments.base.financial_instrument import FinancialInstrument
from aip.domain.instruments.bonds.floating_rate_bond import FloatingRateBond
from aip.domain.instruments.bonds.government_bond import GovernmentBond
from aip.domain.instruments.bonds.treasury_bill import TreasuryBill
from aip.domain.instruments.bonds.zero_coupon_bond import ZeroCouponBond
from aip.domain.instruments.cash.cash import Cash
from aip.domain.instruments.enums.amortization_type import AmortizationType
from aip.domain.instruments.enums.coupon_type import CouponType
from aip.domain.instruments.enums.instrument_type import InstrumentType
from aip.domain.instruments.enums.payment_frequency import PaymentFrequency
from aip.domain.instruments.exceptions import InstrumentFactoryError, InstrumentValidationError
from aip.domain.instruments.funds.investment_fund import InvestmentFund
from aip.domain.instruments.issuers.issuer import Issuer
from aip.domain.instruments.issuers.issuer_type import IssuerType
from aip.domain.instruments.money_market.certificate_of_deposit import CertificateOfDeposit
from aip.domain.instruments.money_market.commercial_paper import CommercialPaper
from aip.domain.instruments.money_market.repo import Repo
from aip.domain.instruments.money_market.reverse_repo import ReverseRepo
from aip.domain.instruments.schedules.coupon_schedule import CouponSchedule
from aip.shared.conventions import DayCountConvention


class InstrumentFactory:
    """Factory for creating instruments."""

    def create(
        self,
        instrument_type: InstrumentType,
        *,
        name: str,
        isin: str | None = None,
        issuer: Issuer | None = None,
        currency: str = "USD",
        nominal_value: Decimal | None = None,
        **kwargs: Any,
    ) -> FinancialInstrument:
        self._validate_common_inputs(name=name, nominal_value=nominal_value)
        issuer_or_default = issuer or Issuer(
            code="ISSUER",
            name="Issuer",
            issuer_type=IssuerType.GOVERNMENT,
        )
        if instrument_type.value == InstrumentType.GOVERNMENT_BOND.value:
            return GovernmentBond(
                isin=isin or "US0000000000",
                name=name,
                issuer=issuer_or_default,
                currency=currency,
                settlement_calendar=kwargs.get("settlement_calendar", "US"),
                business_day_convention=kwargs.get("business_day_convention", "Following"),
                day_count_convention=kwargs.get("day_count_convention", DayCountConvention.ACTUAL_365),
                issue_date=kwargs.get("issue_date", date(2024, 1, 1)),
                settlement_date=kwargs.get("settlement_date", date(2024, 1, 2)),
                maturity_date=kwargs.get("maturity_date", date(2034, 1, 1)),
                coupon_schedule=kwargs.get("coupon_schedule"),
                nominal_value=nominal_value or Decimal("1000"),
                book_value=kwargs.get("book_value", nominal_value or Decimal("1000")),
                market_value=kwargs.get("market_value", nominal_value or Decimal("1000")),
                face_value=kwargs.get("face_value", nominal_value or Decimal("1000")),
                outstanding_amount=kwargs.get("outstanding_amount", nominal_value or Decimal("1000")),
                yield_rate=kwargs.get("yield_rate", Decimal("0.05")),
                duration=kwargs.get("duration", Decimal("0")),
                modified_duration=kwargs.get("modified_duration", Decimal("0")),
                convexity=kwargs.get("convexity", Decimal("0")),
                dirty_price=kwargs.get("dirty_price", Decimal("100")),
                clean_price=kwargs.get("clean_price", Decimal("100")),
                accrued_interest=kwargs.get("accrued_interest", Decimal("0")),
                coupon_rate=kwargs.get("coupon_rate", Decimal("0.05")),
                payment_frequency=kwargs.get("payment_frequency", PaymentFrequency.SEMIANNUAL),
                coupon_type=kwargs.get("coupon_type", CouponType.FIXED),
                amortization_type=kwargs.get("amortization_type", AmortizationType.BULLET),
                settlement_currency=kwargs.get("settlement_currency", currency),
            )
        if instrument_type.value == InstrumentType.TREASURY_BILL.value:
            return TreasuryBill(
                isin=isin or "US0000000001",
                name=name,
                issuer=issuer_or_default,
                currency=currency,
                settlement_calendar=kwargs.get("settlement_calendar", "US"),
                business_day_convention=kwargs.get("business_day_convention", "Following"),
                day_count_convention=kwargs.get("day_count_convention", DayCountConvention.ACTUAL_360),
                issue_date=kwargs.get("issue_date", date(2024, 1, 1)),
                settlement_date=kwargs.get("settlement_date", date(2024, 1, 2)),
                maturity_date=kwargs.get("maturity_date", date(2024, 4, 1)),
                coupon_schedule=kwargs.get("coupon_schedule"),
                nominal_value=nominal_value or Decimal("1000"),
                book_value=kwargs.get("book_value", nominal_value or Decimal("1000")),
                market_value=kwargs.get("market_value", nominal_value or Decimal("1000")),
                face_value=kwargs.get("face_value", nominal_value or Decimal("1000")),
                outstanding_amount=kwargs.get("outstanding_amount", nominal_value or Decimal("1000")),
                yield_rate=kwargs.get("yield_rate", Decimal("0.05")),
                duration=kwargs.get("duration", Decimal("0")),
                modified_duration=kwargs.get("modified_duration", Decimal("0")),
                convexity=kwargs.get("convexity", Decimal("0")),
                dirty_price=kwargs.get("dirty_price", Decimal("100")),
                clean_price=kwargs.get("clean_price", Decimal("100")),
                accrued_interest=kwargs.get("accrued_interest", Decimal("0")),
                discount_rate=kwargs.get("discount_rate", Decimal("0.05")),
                settlement_currency=kwargs.get("settlement_currency", currency),
            )
        if instrument_type.value == InstrumentType.ZERO_COUPON_BOND.value:
            return ZeroCouponBond(
                isin=isin or "US0000000002",
                name=name,
                issuer=issuer_or_default,
                currency=currency,
                settlement_calendar=kwargs.get("settlement_calendar", "US"),
                business_day_convention=kwargs.get("business_day_convention", "Following"),
                day_count_convention=kwargs.get("day_count_convention", DayCountConvention.ACTUAL_365),
                issue_date=kwargs.get("issue_date", date(2024, 1, 1)),
                settlement_date=kwargs.get("settlement_date", date(2024, 1, 2)),
                maturity_date=kwargs.get("maturity_date", date(2024, 4, 1)),
                coupon_schedule=kwargs.get("coupon_schedule"),
                nominal_value=nominal_value or Decimal("1000"),
                book_value=kwargs.get("book_value", nominal_value or Decimal("1000")),
                market_value=kwargs.get("market_value", nominal_value or Decimal("1000")),
                face_value=kwargs.get("face_value", nominal_value or Decimal("1000")),
                outstanding_amount=kwargs.get("outstanding_amount", nominal_value or Decimal("1000")),
                yield_rate=kwargs.get("yield_rate", Decimal("0.05")),
                duration=kwargs.get("duration", Decimal("0")),
                modified_duration=kwargs.get("modified_duration", Decimal("0")),
                convexity=kwargs.get("convexity", Decimal("0")),
                dirty_price=kwargs.get("dirty_price", Decimal("100")),
                clean_price=kwargs.get("clean_price", Decimal("100")),
                accrued_interest=kwargs.get("accrued_interest", Decimal("0")),
                coupon_rate=kwargs.get("coupon_rate", Decimal("0.05")),
                payment_frequency=kwargs.get("payment_frequency", PaymentFrequency.SEMIANNUAL),
                coupon_type=kwargs.get("coupon_type", CouponType.ZERO),
                amortization_type=kwargs.get("amortization_type", AmortizationType.BULLET),
                settlement_currency=kwargs.get("settlement_currency", currency),
            )
        if instrument_type.value == InstrumentType.FLOATING_RATE_BOND.value:
            return FloatingRateBond(
                isin=isin or "US0000000003",
                name=name,
                issuer=issuer_or_default,
                currency=currency,
                settlement_calendar=kwargs.get("settlement_calendar", "US"),
                business_day_convention=kwargs.get("business_day_convention", "Following"),
                day_count_convention=kwargs.get("day_count_convention", DayCountConvention.ACTUAL_360),
                issue_date=kwargs.get("issue_date", date(2024, 1, 1)),
                settlement_date=kwargs.get("settlement_date", date(2024, 1, 2)),
                maturity_date=kwargs.get("maturity_date", date(2025, 1, 1)),
                coupon_schedule=kwargs.get("coupon_schedule"),
                nominal_value=nominal_value or Decimal("1000"),
                book_value=kwargs.get("book_value", nominal_value or Decimal("1000")),
                market_value=kwargs.get("market_value", nominal_value or Decimal("1000")),
                face_value=kwargs.get("face_value", nominal_value or Decimal("1000")),
                outstanding_amount=kwargs.get("outstanding_amount", nominal_value or Decimal("1000")),
                yield_rate=kwargs.get("yield_rate", Decimal("0.05")),
                duration=kwargs.get("duration", Decimal("0")),
                modified_duration=kwargs.get("modified_duration", Decimal("0")),
                convexity=kwargs.get("convexity", Decimal("0")),
                dirty_price=kwargs.get("dirty_price", Decimal("100")),
                clean_price=kwargs.get("clean_price", Decimal("100")),
                accrued_interest=kwargs.get("accrued_interest", Decimal("0")),
                coupon_rate=kwargs.get("coupon_rate", Decimal("0.03")),
                payment_frequency=kwargs.get("payment_frequency", PaymentFrequency.QUARTERLY),
                coupon_type=kwargs.get("coupon_type", CouponType.FLOATING),
                amortization_type=kwargs.get("amortization_type", AmortizationType.BULLET),
                settlement_currency=kwargs.get("settlement_currency", currency),
                reference_rate=kwargs.get("reference_rate", Decimal("0.02")),
                spread=kwargs.get("spread", Decimal("0.01")),
                next_reset_date=kwargs.get("next_reset_date", date(2024, 7, 1)),
            )
        if instrument_type.value == InstrumentType.CASH.value:
            return Cash(
                isin=isin or "US0000000004",
                name=name,
                issuer=issuer_or_default,
                currency=currency,
                settlement_calendar=kwargs.get("settlement_calendar", "US"),
                business_day_convention=kwargs.get("business_day_convention", "Following"),
                day_count_convention=kwargs.get("day_count_convention", DayCountConvention.ACTUAL_365),
                issue_date=kwargs.get("issue_date", date(2024, 1, 1)),
                settlement_date=kwargs.get("settlement_date", date(2024, 1, 1)),
                maturity_date=kwargs.get("maturity_date", date(2024, 1, 1)),
                coupon_schedule=kwargs.get("coupon_schedule"),
                nominal_value=nominal_value or Decimal("1000"),
                book_value=kwargs.get("book_value", nominal_value or Decimal("1000")),
                market_value=kwargs.get("market_value", nominal_value or Decimal("1000")),
                face_value=kwargs.get("face_value", nominal_value or Decimal("1000")),
                outstanding_amount=kwargs.get("outstanding_amount", nominal_value or Decimal("1000")),
                yield_rate=kwargs.get("yield_rate", Decimal("0")),
                duration=kwargs.get("duration", Decimal("0")),
                modified_duration=kwargs.get("modified_duration", Decimal("0")),
                convexity=kwargs.get("convexity", Decimal("0")),
                dirty_price=kwargs.get("dirty_price", Decimal("100")),
                clean_price=kwargs.get("clean_price", Decimal("100")),
                accrued_interest=kwargs.get("accrued_interest", Decimal("0")),
                settlement_currency=kwargs.get("settlement_currency", currency),
            )
        if instrument_type.value == InstrumentType.INVESTMENT_FUND.value:
            return InvestmentFund(
                isin=isin or "US0000000005",
                name=name,
                issuer=issuer_or_default,
                currency=currency,
                settlement_calendar=kwargs.get("settlement_calendar", "US"),
                business_day_convention=kwargs.get("business_day_convention", "Following"),
                day_count_convention=kwargs.get("day_count_convention", DayCountConvention.ACTUAL_365),
                issue_date=kwargs.get("issue_date", date(2024, 1, 1)),
                settlement_date=kwargs.get("settlement_date", date(2024, 1, 2)),
                maturity_date=kwargs.get("maturity_date", date(2024, 1, 2)),
                coupon_schedule=kwargs.get("coupon_schedule"),
                nominal_value=nominal_value or Decimal("1000"),
                book_value=kwargs.get("book_value", nominal_value or Decimal("1000")),
                market_value=kwargs.get("market_value", nominal_value or Decimal("1000")),
                face_value=kwargs.get("face_value", nominal_value or Decimal("1000")),
                outstanding_amount=kwargs.get("outstanding_amount", nominal_value or Decimal("1000")),
                yield_rate=kwargs.get("yield_rate", Decimal("0.05")),
                duration=kwargs.get("duration", Decimal("0")),
                modified_duration=kwargs.get("modified_duration", Decimal("0")),
                convexity=kwargs.get("convexity", Decimal("0")),
                dirty_price=kwargs.get("dirty_price", Decimal("100")),
                clean_price=kwargs.get("clean_price", Decimal("100")),
                accrued_interest=kwargs.get("accrued_interest", Decimal("0")),
                settlement_currency=kwargs.get("settlement_currency", currency),
            )
        if instrument_type.value == InstrumentType.CERTIFICATE_OF_DEPOSIT.value:
            return CertificateOfDeposit(
                isin=isin or "US0000000006",
                name=name,
                issuer=issuer_or_default,
                currency=currency,
                settlement_calendar=kwargs.get("settlement_calendar", "US"),
                business_day_convention=kwargs.get("business_day_convention", "Following"),
                day_count_convention=kwargs.get("day_count_convention", DayCountConvention.ACTUAL_365),
                issue_date=kwargs.get("issue_date", date(2024, 1, 1)),
                settlement_date=kwargs.get("settlement_date", date(2024, 1, 2)),
                maturity_date=kwargs.get("maturity_date", date(2024, 2, 2)),
                coupon_schedule=kwargs.get("coupon_schedule"),
                nominal_value=nominal_value or Decimal("1000"),
                book_value=kwargs.get("book_value", nominal_value or Decimal("1000")),
                market_value=kwargs.get("market_value", nominal_value or Decimal("1000")),
                face_value=kwargs.get("face_value", nominal_value or Decimal("1000")),
                outstanding_amount=kwargs.get("outstanding_amount", nominal_value or Decimal("1000")),
                yield_rate=kwargs.get("yield_rate", Decimal("0.05")),
                duration=kwargs.get("duration", Decimal("0")),
                modified_duration=kwargs.get("modified_duration", Decimal("0")),
                convexity=kwargs.get("convexity", Decimal("0")),
                dirty_price=kwargs.get("dirty_price", Decimal("100")),
                clean_price=kwargs.get("clean_price", Decimal("100")),
                accrued_interest=kwargs.get("accrued_interest", Decimal("0")),
                settlement_currency=kwargs.get("settlement_currency", currency),
            )
        if instrument_type.value == InstrumentType.COMMERCIAL_PAPER.value:
            return CommercialPaper(
                isin=isin or "US0000000007",
                name=name,
                issuer=issuer_or_default,
                currency=currency,
                settlement_calendar=kwargs.get("settlement_calendar", "US"),
                business_day_convention=kwargs.get("business_day_convention", "Following"),
                day_count_convention=kwargs.get("day_count_convention", DayCountConvention.ACTUAL_365),
                issue_date=kwargs.get("issue_date", date(2024, 1, 1)),
                settlement_date=kwargs.get("settlement_date", date(2024, 1, 2)),
                maturity_date=kwargs.get("maturity_date", date(2024, 2, 2)),
                coupon_schedule=kwargs.get("coupon_schedule"),
                nominal_value=nominal_value or Decimal("1000"),
                book_value=kwargs.get("book_value", nominal_value or Decimal("1000")),
                market_value=kwargs.get("market_value", nominal_value or Decimal("1000")),
                face_value=kwargs.get("face_value", nominal_value or Decimal("1000")),
                outstanding_amount=kwargs.get("outstanding_amount", nominal_value or Decimal("1000")),
                yield_rate=kwargs.get("yield_rate", Decimal("0.05")),
                duration=kwargs.get("duration", Decimal("0")),
                modified_duration=kwargs.get("modified_duration", Decimal("0")),
                convexity=kwargs.get("convexity", Decimal("0")),
                dirty_price=kwargs.get("dirty_price", Decimal("100")),
                clean_price=kwargs.get("clean_price", Decimal("100")),
                accrued_interest=kwargs.get("accrued_interest", Decimal("0")),
                settlement_currency=kwargs.get("settlement_currency", currency),
            )
        if instrument_type.value == InstrumentType.REPO.value:
            return Repo(
                isin=isin or "US0000000008",
                name=name,
                issuer=issuer_or_default,
                currency=currency,
                settlement_calendar=kwargs.get("settlement_calendar", "US"),
                business_day_convention=kwargs.get("business_day_convention", "Following"),
                day_count_convention=kwargs.get("day_count_convention", DayCountConvention.ACTUAL_365),
                issue_date=kwargs.get("issue_date", date(2024, 1, 1)),
                settlement_date=kwargs.get("settlement_date", date(2024, 1, 2)),
                maturity_date=kwargs.get("maturity_date", date(2024, 2, 2)),
                coupon_schedule=kwargs.get("coupon_schedule"),
                nominal_value=nominal_value or Decimal("1000"),
                book_value=kwargs.get("book_value", nominal_value or Decimal("1000")),
                market_value=kwargs.get("market_value", nominal_value or Decimal("1000")),
                face_value=kwargs.get("face_value", nominal_value or Decimal("1000")),
                outstanding_amount=kwargs.get("outstanding_amount", nominal_value or Decimal("1000")),
                yield_rate=kwargs.get("yield_rate", Decimal("0.05")),
                duration=kwargs.get("duration", Decimal("0")),
                modified_duration=kwargs.get("modified_duration", Decimal("0")),
                convexity=kwargs.get("convexity", Decimal("0")),
                dirty_price=kwargs.get("dirty_price", Decimal("100")),
                clean_price=kwargs.get("clean_price", Decimal("100")),
                accrued_interest=kwargs.get("accrued_interest", Decimal("0")),
                settlement_currency=kwargs.get("settlement_currency", currency),
            )
        if instrument_type.value == InstrumentType.REVERSE_REPO.value:
            return ReverseRepo(
                isin=isin or "US0000000009",
                name=name,
                issuer=issuer_or_default,
                currency=currency,
                settlement_calendar=kwargs.get("settlement_calendar", "US"),
                business_day_convention=kwargs.get("business_day_convention", "Following"),
                day_count_convention=kwargs.get("day_count_convention", DayCountConvention.ACTUAL_365),
                issue_date=kwargs.get("issue_date", date(2024, 1, 1)),
                settlement_date=kwargs.get("settlement_date", date(2024, 1, 2)),
                maturity_date=kwargs.get("maturity_date", date(2024, 2, 2)),
                coupon_schedule=kwargs.get("coupon_schedule"),
                nominal_value=nominal_value or Decimal("1000"),
                book_value=kwargs.get("book_value", nominal_value or Decimal("1000")),
                market_value=kwargs.get("market_value", nominal_value or Decimal("1000")),
                face_value=kwargs.get("face_value", nominal_value or Decimal("1000")),
                outstanding_amount=kwargs.get("outstanding_amount", nominal_value or Decimal("1000")),
                yield_rate=kwargs.get("yield_rate", Decimal("0.05")),
                duration=kwargs.get("duration", Decimal("0")),
                modified_duration=kwargs.get("modified_duration", Decimal("0")),
                convexity=kwargs.get("convexity", Decimal("0")),
                dirty_price=kwargs.get("dirty_price", Decimal("100")),
                clean_price=kwargs.get("clean_price", Decimal("100")),
                accrued_interest=kwargs.get("accrued_interest", Decimal("0")),
                settlement_currency=kwargs.get("settlement_currency", currency),
            )
        raise InstrumentFactoryError(f"Unsupported instrument type: {instrument_type}")

    def _validate_common_inputs(self, *, name: str, nominal_value: Decimal | None) -> None:
        if not name.strip():
            raise InstrumentValidationError("Instrument name must be provided")
        if nominal_value is not None and nominal_value <= 0:
            raise InstrumentValidationError("Nominal value must be positive")
