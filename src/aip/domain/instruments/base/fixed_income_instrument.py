from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.instruments.base.financial_instrument import FinancialInstrument
from aip.domain.instruments.enums.amortization_type import AmortizationType
from aip.domain.instruments.enums.coupon_type import CouponType
from aip.domain.instruments.enums.payment_frequency import PaymentFrequency
from aip.domain.instruments.exceptions import InstrumentValidationError
from aip.domain.instruments.schedules.coupon_schedule import CouponSchedule


@dataclass(slots=True)
class FixedIncomeInstrument(FinancialInstrument):
    """Base class for fixed-income instruments."""

    coupon_rate: Decimal = Decimal("0")
    payment_frequency: PaymentFrequency = PaymentFrequency.SEMIANNUAL
    coupon_type: CouponType = CouponType.FIXED
    amortization_type: AmortizationType = AmortizationType.BULLET

    def __post_init__(self) -> None:
        super().__post_init__()
        self.coupon_rate = self._ensure_decimal(self.coupon_rate)
        self.payment_frequency = PaymentFrequency.from_value(self.payment_frequency)
        self.coupon_type = self.coupon_type
        self.amortization_type = self.amortization_type
        if self.coupon_rate < 0:
            raise InstrumentValidationError("Coupon rate cannot be negative")
        if self.coupon_schedule is None or not self.coupon_schedule.coupons:
            self.coupon_schedule = CouponSchedule.from_frequency(
                issue_date=self.issue_date,
                maturity_date=self.maturity_date,
                payment_frequency=self.payment_frequency,
                coupon_rate=self.coupon_rate,
                nominal_value=self.nominal_value,
            )

    def calculate_price(self) -> Decimal:
        if self.coupon_schedule is None:
            return self.clean_price
        return self.clean_price

    def calculate_yield(self) -> Decimal:
        if self.clean_price <= 0:
            return Decimal("0")
        return self.yield_rate
