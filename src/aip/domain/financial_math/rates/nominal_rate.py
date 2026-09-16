from __future__ import annotations

from dataclasses import dataclass

from .interest_rate import InterestRate


@dataclass(frozen=True)
class NominalRate(InterestRate):
    """Nominal rate with explicit compounding frequency."""

    def __post_init__(self) -> None:
        super().__post_init__()
