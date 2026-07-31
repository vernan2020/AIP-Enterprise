from __future__ import annotations

from dataclasses import dataclass

from aip.domain.financial_math.rates.interest_rate import InterestRate


@dataclass(frozen=True)
class NominalRate(InterestRate):
    """Nominal rate with explicit compounding frequency."""

    def __post_init__(self) -> None:
        super().__post_init__()
