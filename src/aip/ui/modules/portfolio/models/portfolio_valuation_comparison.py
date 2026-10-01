from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PortfolioValuationComparisonDisplayRow:
    cells: tuple[str, ...]
    tone: str = "neutral"
    amount: Decimal | None = None


@dataclass(frozen=True, slots=True)
class PortfolioValuationBreakdownPoint:
    label: str
    amount: Decimal
    tone: str = "neutral"


@dataclass(frozen=True, slots=True)
class PortfolioValuationComparisonDisplay:
    totals: tuple[PortfolioValuationComparisonDisplayRow, ...] = ()
    positions: tuple[PortfolioValuationComparisonDisplayRow, ...] = ()
    gain_total: Decimal = Decimal("0")
    loss_total: Decimal = Decimal("0")
    net_total: Decimal = Decimal("0")
    gain_count: int = 0
    loss_count: int = 0
    neutral_count: int = 0
    top_gains: tuple[PortfolioValuationComparisonDisplayRow, ...] = ()
    top_losses: tuple[PortfolioValuationComparisonDisplayRow, ...] = ()
    currency_breakdown: tuple[PortfolioValuationBreakdownPoint, ...] = ()
    issuer_breakdown: tuple[PortfolioValuationBreakdownPoint, ...] = ()
