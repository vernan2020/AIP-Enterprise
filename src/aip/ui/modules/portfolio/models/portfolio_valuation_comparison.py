from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PortfolioValuationComparisonDisplayRow:
    cells: tuple[str, ...]
    tone: str = "neutral"
    value: Decimal | None = None


@dataclass(frozen=True, slots=True)
class PortfolioValuationBreakdownDisplay:
    label: str
    gain: Decimal
    loss: Decimal
    net: Decimal
    position_count: int


@dataclass(frozen=True, slots=True)
class PortfolioValuationComparisonDisplay:
    totals: tuple[PortfolioValuationComparisonDisplayRow, ...] = ()
    positions: tuple[PortfolioValuationComparisonDisplayRow, ...] = ()
    gain_total: Decimal | None = None
    loss_total: Decimal | None = None
    net_total: Decimal | None = None
    gain_count: int = 0
    loss_count: int = 0
    available_count: int = 0
    currency_breakdown: tuple[PortfolioValuationBreakdownDisplay, ...] = ()
    issuer_breakdown: tuple[PortfolioValuationBreakdownDisplay, ...] = ()
