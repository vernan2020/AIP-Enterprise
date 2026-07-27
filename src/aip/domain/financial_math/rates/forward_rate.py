from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.financial_math.rates.interest_rate import InterestRate


@dataclass(frozen=True, slots=True)
class ForwardRate(InterestRate):
    """Forward rate between two tenors."""

    start_tenor: Decimal | None = None
    end_tenor: Decimal | None = None
