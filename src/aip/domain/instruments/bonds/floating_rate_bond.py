from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from aip.domain.instruments.bonds.bond import Bond
from aip.domain.instruments.exceptions import InstrumentValidationError
from aip.domain.instruments.schedules.coupon_schedule import CouponSchedule


@dataclass
class FloatingRateBond(Bond):
    """Bond whose coupon is linked to a floating reference rate."""

    reference_rate: Decimal = Decimal("0")
    spread: Decimal = Decimal("0")
    next_reset_date: date | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        self.reference_rate = self._ensure_decimal(self.reference_rate)
        self.spread = self._ensure_decimal(self.spread)
        if self.reference_rate < 0:
            raise InstrumentValidationError("Reference rate cannot be negative")
        if self.spread < 0:
            raise InstrumentValidationError("Spread cannot be negative")
        if self.next_reset_date is not None and self.next_reset_date < self.issue_date:
            raise InstrumentValidationError("Next reset date cannot be before the issue date")
        if self.next_reset_date is not None and self.next_reset_date > self.maturity_date:
            raise InstrumentValidationError("Next reset date cannot be after the maturity date")
        self._refresh_coupon_schedule()

    def _refresh_coupon_schedule(self) -> None:
        self.coupon_schedule = CouponSchedule.from_frequency(
            issue_date=self.issue_date,
            maturity_date=self.maturity_date,
            payment_frequency=self.payment_frequency,
            coupon_rate=self.reference_rate + self.spread,
            nominal_value=self.nominal_value,
            include_principal=False,
            include_initial_coupon=False,
        )
        if not self.coupon_schedule.coupons:
            raise InstrumentValidationError("Floating-rate bond schedule could not be generated")

        rate = self.reference_rate + self.spread
        for coupon in self.coupon_schedule.coupons:
            coupon.rate = rate
            year_fraction = Decimal((coupon.period_end - coupon.period_start).days) / Decimal("365")
            coupon.amount = self.nominal_value * rate * year_fraction

    def generate_schedule(self) -> CouponSchedule:
        self._refresh_coupon_schedule()
        return self.coupon_schedule

    def calculate_price(self) -> Decimal:
        return self.face_value * (Decimal("1") + self.reference_rate + self.spread)

    def calculate_yield(self) -> Decimal:
        return self.yield_rate
