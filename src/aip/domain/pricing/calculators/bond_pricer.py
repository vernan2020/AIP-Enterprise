from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.financial_math import accrued_interest, clean_price as clean_price_fn, dirty_price as dirty_price_fn
from aip.domain.financial_math.bond_metrics import convexity, dv01, effective_duration, macaulay_duration, modified_duration, pvbp
from aip.domain.instruments.base.financial_instrument import FinancialInstrument
from aip.domain.pricing.exceptions import PricingError


def price_bond(instrument: FinancialInstrument, *, valuation_date: date, market_yield: Decimal) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]:
    if valuation_date > instrument.maturity_date:
        raise PricingError("Valuation date cannot be after maturity date")

    coupon_rate = instrument.yield_rate if getattr(instrument, "coupon_rate", None) is None else instrument.coupon_rate
    days_since_last_coupon = max(0, (valuation_date - instrument.issue_date).days)
    days_in_period = max(1, (instrument.maturity_date - instrument.issue_date).days)
    accrued = accrued_interest(coupon_rate, instrument.nominal_value, days_since_last_coupon=days_since_last_coupon, days_in_period=days_in_period)
    clean = clean_price_fn(Decimal("100"), accrued)
    dirty = dirty_price_fn(clean, accrued)

    cash_flows = [(Decimal("1"), instrument.nominal_value), (Decimal("2"), instrument.nominal_value)]
    duration = macaulay_duration(cash_flows, market_yield)
    modified = modified_duration(cash_flows, market_yield)
    convex = convexity(cash_flows, market_yield)
    dv01_value = dv01(cash_flows, market_yield)
    pvbp_value = pvbp(cash_flows, market_yield)

    market_value = instrument.nominal_value * dirty / Decimal("100")
    return (clean, dirty, accrued, market_value, market_yield, duration, modified, convex, dv01_value, pvbp_value)
