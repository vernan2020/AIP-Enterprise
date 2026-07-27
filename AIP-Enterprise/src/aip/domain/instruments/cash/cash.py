from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.instruments.base.financial_instrument import FinancialInstrument


@dataclass(slots=True)
class Cash(FinancialInstrument):
    """Cash or cash-equivalent instrument."""

    def calculate_price(self) -> Decimal:
        return self.nominal_value

    def calculate_yield(self) -> Decimal:
        return Decimal("0")
