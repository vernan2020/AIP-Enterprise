from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.financial_math.rates.interest_rate import InterestRate


@dataclass(frozen=True, slots=True)
class ZeroRate(InterestRate):
    """Zero rate for a single maturity."""

    maturity: Decimal | None = None
