from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PricingResult:
    """Output of a pricing calculation."""

    clean_price: Decimal
    dirty_price: Decimal
    accrued_interest: Decimal
    market_value: Decimal
    yield_: Decimal
    duration: Decimal
    modified_duration: Decimal
    convexity: Decimal
    dv01: Decimal
    pvbp: Decimal
    warnings: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
