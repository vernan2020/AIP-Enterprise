from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from ..exceptions import InvalidRateError
from .dv01 import dv01


def pvbp(
    cash_flows: Iterable[tuple[Decimal, Decimal]],
    yield_rate: Decimal,
    *,
    shock: Decimal = Decimal("0.0001"),
) -> Decimal:
    if shock <= 0:
        raise InvalidRateError("Shock must be positive")
    return dv01(cash_flows, yield_rate, shock=shock) * Decimal("10000")
