from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ProjectedCashFlow:
    """A projected cash flow with a projection source and optional metadata."""

    payment_date: date
    amount: Decimal
    currency: str
    cash_flow_type: str
    source: str = "contractual"
    probability: Decimal | None = None
    scenario: str | None = None
    bucket: str = "default"
