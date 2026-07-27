from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.instruments.base.financial_instrument import FinancialInstrument
from aip.domain.pricing.exceptions import PricingError


def price_cash(instrument: FinancialInstrument, *, valuation_date: date, market_yield: Decimal) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]:
    if valuation_date > instrument.maturity_date:
        raise PricingError("Valuation date cannot be after maturity date")
    market_value = instrument.nominal_value
    return (Decimal("100"), Decimal("100"), Decimal("0"), market_value, Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"))
