from __future__ import annotations

from dataclasses import dataclass

from aip.domain.financial_math.rates.interest_rate import InterestRate


@dataclass(frozen=True, slots=True)
class EffectiveRate(InterestRate):
    """Effective annual rate value object."""

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "compounding", "annual")
        object.__setattr__(self, "frequency", 1)
