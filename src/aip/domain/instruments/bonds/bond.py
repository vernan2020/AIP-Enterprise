from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.instruments.base.fixed_income_instrument import FixedIncomeInstrument
from aip.domain.instruments.schedules.coupon_schedule import CouponSchedule


@dataclass
class Bond(FixedIncomeInstrument):
    """Generic bond abstraction."""

    def calculate_price(self) -> Decimal:
        if self.coupon_schedule is None:
            return self.clean_price
        annual_coupon = self.nominal_value * self.coupon_rate
        discount_factor = Decimal("1") / (Decimal("1") + self.yield_rate)
        return self.face_value * discount_factor + annual_coupon

    def calculate_yield(self) -> Decimal:
        return self.yield_rate

    def generate_schedule(self) -> CouponSchedule:
        if self.coupon_schedule is None or not self.coupon_schedule.coupons:
            self.coupon_schedule = CouponSchedule.from_frequency(
                issue_date=self.issue_date,
                maturity_date=self.maturity_date,
                payment_frequency=self.payment_frequency,
                coupon_rate=self.coupon_rate,
                nominal_value=self.nominal_value,
            )
        return self.coupon_schedule
