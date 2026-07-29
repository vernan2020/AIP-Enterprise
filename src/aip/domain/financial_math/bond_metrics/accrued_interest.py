from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from aip.domain.financial_math.exceptions import InvalidCashFlowError


def accrued_interest(coupon_rate: Decimal, nominal_value: Decimal, *, days_since_last_coupon: int, days_in_period: int) -> Decimal:
    if days_in_period <= 0:
        raise InvalidCashFlowError("Days in coupon period must be positive")
    if days_since_last_coupon < 0:
        raise InvalidCashFlowError("Days since last coupon cannot be negative")
    raw_interest = nominal_value * coupon_rate * Decimal(days_since_last_coupon) / Decimal(days_in_period)
    return raw_interest.quantize(Decimal("1e-18"), rounding=ROUND_HALF_UP)
