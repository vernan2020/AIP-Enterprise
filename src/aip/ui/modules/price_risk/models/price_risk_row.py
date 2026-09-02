from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PriceRiskRow:
    """Immutable presentation row for one security in the VaR scenario."""

    series: str
    issuer: str
    currency: str
    market_value: str
    pnl_scenario: str
    contribution_percent: str
    individual_var_percent: str
    real_observations: int
    synthetic_observations: int
    security_key: str


@dataclass(frozen=True, slots=True)
class RiskChartPoint:
    """Presentation-only point consumed by price-risk charts."""

    label: str
    value: Decimal
    secondary_value: Decimal = Decimal("0")
