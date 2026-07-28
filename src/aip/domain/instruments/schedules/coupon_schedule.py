from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from aip.domain.instruments.enums.payment_frequency import PaymentFrequency
from aip.domain.instruments.schedules.coupon import Coupon


@dataclass(slots=True)
class CouponSchedule:
    """Deterministic coupon schedule builder for instruments."""

    coupons: list[Coupon] = field(default_factory=list)

    @classmethod
    def from_frequency(
        cls,
        *,
        issue_date: date,
        maturity_date: date,
        payment_frequency: PaymentFrequency | str,
        coupon_rate: Decimal,
        nominal_value: Decimal,
        include_principal: bool = True,
        include_initial_coupon: bool = True,
    ) -> "CouponSchedule":
        schedule = cls()
        if maturity_date <= issue_date:
            return schedule

        normalized_payment_frequency = PaymentFrequency.from_value(payment_frequency)
        step = normalized_payment_frequency.months_between_payments()
        payment_dates: list[date] = [issue_date] if include_initial_coupon else []
        current = issue_date
        while True:
            next_payment_date = cls._advance_months(current, step)
            if next_payment_date is None or next_payment_date > maturity_date:
                break
            payment_dates.append(next_payment_date)
            current = next_payment_date

        if not payment_dates or payment_dates[-1] != maturity_date:
            payment_dates.append(maturity_date)

        periods_per_year = Decimal(12) / Decimal(step)
        for index, payment_date in enumerate(payment_dates):
            if index == 0 and include_initial_coupon:
                period_start = issue_date
                period_end = payment_dates[1] if len(payment_dates) > 1 else maturity_date
                coupon_amount = nominal_value * coupon_rate / periods_per_year
            elif index == 0:
                period_start = issue_date
                period_end = payment_date
                year_fraction = Decimal((period_end - period_start).days) / Decimal("365")
                coupon_amount = nominal_value * coupon_rate * year_fraction
            else:
                period_start = payment_dates[index - 1]
                period_end = payment_date
                if include_initial_coupon:
                    coupon_amount = nominal_value * coupon_rate / periods_per_year
                else:
                    year_fraction = Decimal((period_end - period_start).days) / Decimal("365")
                    coupon_amount = nominal_value * coupon_rate * year_fraction
            if include_principal and payment_date == maturity_date and payment_date != issue_date:
                coupon_amount += nominal_value
            schedule.coupons.append(
                Coupon(
                    payment_date=payment_date,
                    rate=coupon_rate,
                    amount=coupon_amount,
                    period_start=period_start,
                    period_end=period_end,
                )
            )

        return schedule

    @staticmethod
    def _advance_months(start: date, months: int) -> date | None:
        if months <= 0:
            return None
        month = start.month + months
        year = start.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        day = min(start.day, 28)
        return date(year, month, day)

    @staticmethod
    def _adjust_business_day(value: date) -> date:
        while value.weekday() >= 5:
            value += timedelta(days=1)
        return value
