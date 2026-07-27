from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from aip.domain.financial_math.exceptions import InvalidRateError


def _normalize_cash_flows(cash_flows: Iterable[tuple[Decimal, Decimal]]) -> list[tuple[Decimal, Decimal]]:
    return [(period, amount) for period, amount in cash_flows]


def macaulay_duration(cash_flows: Iterable[tuple[Decimal, Decimal]], yield_rate: Decimal) -> Decimal:
    if yield_rate <= -Decimal("1"):
        raise InvalidRateError("Yield rate is invalid")
    normalized = _normalize_cash_flows(cash_flows)
    present_value = sum(amount / ((Decimal("1") + yield_rate) ** period) for period, amount in normalized)
    if present_value <= 0:
        raise InvalidRateError("Present value is non-positive")
    return sum(period * amount / ((Decimal("1") + yield_rate) ** period) for period, amount in normalized) / present_value
