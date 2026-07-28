from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Protocol


class ExchangeRatePolicyProvider(Protocol):
    """Protocol for resolving exchange rates when cross-currency conversion is needed."""

    def get_rate(self, from_currency: str, to_currency: str, valuation_date: date | None = None) -> Decimal:
        ...
