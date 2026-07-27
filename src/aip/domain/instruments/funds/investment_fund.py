from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.instruments.base.financial_instrument import FinancialInstrument


@dataclass(slots=True)
class InvestmentFund(FinancialInstrument):
    """Investment fund representation."""

    def calculate_price(self) -> Decimal:
        return self.clean_price

    def calculate_yield(self) -> Decimal:
        return self.yield_rate
