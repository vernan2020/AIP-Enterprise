from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from aip.domain.financial_math.exceptions import InvalidRateError


def dv01(
    cash_flows: Iterable[tuple[Decimal, Decimal]],
    yield_rate: Decimal,
    *,
    shock: Decimal = Decimal("0.0001"),
) -> Decimal:
    if shock <= 0:
        raise InvalidRateError("Shock must be positive")
    price_up = sum(
        amount / ((Decimal("1") + yield_rate + shock) ** period) for period, amount in cash_flows
    )
    price_down = sum(
        amount / ((Decimal("1") + yield_rate - shock) ** period) for period, amount in cash_flows
    )
    return (price_down - price_up) / Decimal("2")
