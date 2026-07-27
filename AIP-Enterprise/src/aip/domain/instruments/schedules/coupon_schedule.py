from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from aip.domain.instruments.enums.payment_frequency import PaymentFrequency
from aip.domain.instruments.schedules.coupon import Coupon


@dataclass(slots=True)
class CouponSchedule:
    """Simple coupon schedule builder for instruments."""

    coupons: list[Coupon] = field(default_factory=list)

    @classmethod
    def from_frequency(
        cls,
        *,
        issue_date: date,
        maturity_date: date,
        payment_frequency: PaymentFrequency,
        coupon_rate: Decimal,
        nominal_value: Decimal,
    ) -> "CouponSchedule":
        schedule = cls()
        current = issue_date
        step = payment_frequency.months_between_payments()
        coupon_rate_decimal = Decimal(coupon_rate)
        amount_factor = Decimal("1")
        if payment_frequency == PaymentFrequency.ANNUAL:
            amount_factor = Decimal("1")
        elif payment_frequency == PaymentFrequency.SEMIANNUAL:
            amount_factor = Decimal("2")
        elif payment_frequency == PaymentFrequency.QUARTERLY:
            amount_factor = Decimal("4")
        elif payment_frequency == PaymentFrequency.MONTHLY:
            amount_factor = Decimal("12")

        while current < maturity_date:
            next_month = current.month + step
            year = current.year + (next_month - 1) // 12
            month = ((next_month - 1) % 12) + 1
            payment_date = date(year, month, min(current.day, 28))
            if payment_date > maturity_date:
                payment_date = maturity_date
            period_start = current
            period_end = payment_date
            coupon_amount = nominal_value * coupon_rate_decimal / amount_factor
            schedule.coupons.append(
                Coupon(
                    payment_date=payment_date,
                    rate=coupon_rate_decimal,
                    amount=coupon_amount,
                    period_start=period_start,
                    period_end=period_end,
                )
            )
            if payment_date >= maturity_date:
                break
            current = date(year, month, 1)
        return schedule
