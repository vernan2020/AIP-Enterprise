from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from ..exceptions import InvalidRateError
from .macaulay_duration import macaulay_duration


def modified_duration(
    cash_flows: Iterable[tuple[Decimal, Decimal]], yield_rate: Decimal
) -> Decimal:
    if yield_rate <= -Decimal("1"):
        raise InvalidRateError("Yield rate is invalid")
    duration = macaulay_duration(cash_flows, yield_rate)
    return duration / (Decimal("1") + yield_rate)
