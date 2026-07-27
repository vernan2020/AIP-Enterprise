from __future__ import annotations

from decimal import Decimal


def dirty_price(clean_price: Decimal, accrued_interest: Decimal) -> Decimal:
    return clean_price + accrued_interest


def clean_price(dirty_price: Decimal, accrued_interest: Decimal) -> Decimal:
    return dirty_price - accrued_interest
