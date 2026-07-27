from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(slots=True)
class Coupon:
    """Represents a single coupon cash flow."""

    payment_date: date
    rate: Decimal
    amount: Decimal
    period_start: date
    period_end: date
