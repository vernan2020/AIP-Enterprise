from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.financial_math import accrued_interest, clean_price as clean_price_fn, dirty_price as dirty_price_fn
from aip.domain.instruments.base.financial_instrument import FinancialInstrument
from aip.domain.pricing.exceptions import PricingError


def price_zero_coupon(instrument: FinancialInstrument, *, valuation_date: date, market_yield: Decimal) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]:
    if valuation_date > instrument.maturity_date:
        raise PricingError("Valuation date cannot be after maturity date")
    accrued = Decimal("0")
    clean = clean_price_fn(Decimal("100"), accrued)
    dirty = dirty_price_fn(clean, accrued)
    market_value = instrument.nominal_value * dirty / Decimal("100")
    return (clean, dirty, accrued, market_value, market_yield, Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"))
