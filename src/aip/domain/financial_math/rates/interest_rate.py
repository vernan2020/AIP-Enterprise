from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.financial_math.discounting.compounding import accumulation_factor, discount_factor
from aip.domain.financial_math.exceptions import InvalidRateError


@dataclass(frozen=True)
class InterestRate:
    """Immutable interest rate with explicit compounding and frequency."""

    rate: Decimal
    compounding: str = "annual"
    frequency: int = 1
    day_count_convention: str = "ACTUAL_365"

    def __post_init__(self) -> None:
        if self.rate.is_nan() or self.rate.is_infinite():
            raise InvalidRateError("Rate must be finite")
        if self.frequency <= 0:
            raise InvalidRateError("Frequency must be positive")
        if self.compounding.lower() not in {"simple", "annual", "semiannual", "quarterly", "monthly", "continuous"}:
            raise InvalidRateError("Unsupported compounding convention")
        if self.day_count_convention.upper() not in {"ACTUAL_365", "ACTUAL_360"}:
            raise InvalidRateError("Unsupported day-count convention")

    def discount_factor(self, time: Decimal) -> Decimal:
        return discount_factor(self.rate, time, compounding=self.compounding, frequency=self.frequency)

    def accumulation_factor(self, time: Decimal) -> Decimal:
        return accumulation_factor(self.rate, time, compounding=self.compounding, frequency=self.frequency)
