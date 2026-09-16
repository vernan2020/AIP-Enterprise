from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .interest_rate import InterestRate


@dataclass(frozen=True, slots=True)
class ZeroRate(InterestRate):
    """Zero rate for a single maturity."""

    maturity: Decimal | None = None
