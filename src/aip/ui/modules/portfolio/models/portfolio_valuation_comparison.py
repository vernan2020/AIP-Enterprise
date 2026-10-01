from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PortfolioValuationComparisonDisplayRow:
    cells: tuple[str, ...]
    tone: str = "neutral"
    value: float | None = None


@dataclass(frozen=True, slots=True)
class PortfolioValuationBreakdownDisplay:
    label: str
    gain: float
    loss: float
    net: float
    position_count: int


@dataclass(frozen=True, slots=True)
class PortfolioValuationComparisonDisplay:
    totals: tuple[PortfolioValuationComparisonDisplayRow, ...] = ()
    positions: tuple[PortfolioValuationComparisonDisplayRow, ...] = ()
    gain_total: float = 0.0
    loss_total: float = 0.0
    net_total: float = 0.0
    gain_count: int = 0
    loss_count: int = 0
    available_count: int = 0
    currency_breakdown: tuple[PortfolioValuationBreakdownDisplay, ...] = ()
    issuer_breakdown: tuple[PortfolioValuationBreakdownDisplay, ...] = ()
