from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from aip.domain.financial_math.bond_metrics.macaulay_duration import macaulay_duration
from aip.domain.financial_math.exceptions import InvalidRateError


def modified_duration(cash_flows: Iterable[tuple[Decimal, Decimal]], yield_rate: Decimal) -> Decimal:
    if yield_rate <= -Decimal("1"):
        raise InvalidRateError("Yield rate is invalid")
    duration = macaulay_duration(cash_flows, yield_rate)
    return duration / (Decimal("1") + yield_rate)
