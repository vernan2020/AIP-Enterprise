from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class GapValue:
    """A single liquidity gap bucket for a period."""

    period_start: date
    period_end: date
    net_gap: Decimal
    gross_inflow: Decimal
    gross_outflow: Decimal
    incremental_gap: Decimal
    cumulative_gap: Decimal
    currency: str = "USD"
    bucket: str = "default"
    scenario: str = "base"
