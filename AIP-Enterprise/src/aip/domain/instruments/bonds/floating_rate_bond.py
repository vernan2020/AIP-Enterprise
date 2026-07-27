from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from aip.domain.instruments.bonds.bond import Bond
from aip.domain.instruments.schedules.coupon_schedule import CouponSchedule


@dataclass(slots=True)
class FloatingRateBond(Bond):
    """Bond whose coupon is linked to a floating reference rate."""

    reference_rate: Decimal = Decimal("0")
    spread: Decimal = Decimal("0")
    next_reset_date: date | None = None

    def __post_init__(self) -> None:
        from aip.domain.instruments.base.fixed_income_instrument import FixedIncomeInstrument

        FixedIncomeInstrument.__post_init__(self)
        self.reference_rate = self._ensure_decimal(self.reference_rate)
        self.spread = self._ensure_decimal(self.spread)
        self._refresh_coupon_schedule()

    def _refresh_coupon_schedule(self) -> None:
        if self.coupon_schedule is None:
            self.coupon_schedule = CouponSchedule.from_frequency(
                issue_date=self.issue_date,
                maturity_date=self.maturity_date,
                payment_frequency=self.payment_frequency,
                coupon_rate=self.reference_rate + self.spread,
                nominal_value=self.nominal_value,
            )
        elif self.coupon_schedule.coupons:
            rate = self.reference_rate + self.spread
            for coupon in self.coupon_schedule.coupons:
                coupon.rate = rate
                coupon.amount = self.nominal_value * rate / Decimal("2")

    def calculate_price(self) -> Decimal:
        return self.face_value * (Decimal("1") + self.reference_rate + self.spread)

    def calculate_yield(self) -> Decimal:
        return self.yield_rate
