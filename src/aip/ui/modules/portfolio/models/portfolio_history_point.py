from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PortfolioHistoryPoint:
    """Presentation-ready historical KPI snapshot for the portfolio workspace."""

    valuation_date: date
    market_value_mm: Decimal
    weighted_yield_percent: Decimal
    modified_duration: Decimal | None
    hqla_percent: Decimal
    dv01_mm: Decimal | None
    hhi: Decimal
    data_quality_status: str = "N/D"
