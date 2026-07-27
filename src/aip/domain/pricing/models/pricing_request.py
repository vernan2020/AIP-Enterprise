from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from aip.domain.instruments.base.financial_instrument import FinancialInstrument
from aip.domain.pricing.enums.pricing_method import PricingMethod


@dataclass(frozen=True, slots=True)
class PricingRequest:
    """Input for a pricing calculation."""

    valuation_date: date
    instrument: FinancialInstrument
    market_yield: Decimal
    yield_curve: object | None = None
    pricing_method: PricingMethod = PricingMethod.MARKET_VALUE
