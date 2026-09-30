from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PortfolioValuationComparisonDisplayRow:
    cells: tuple[str, ...]
    tone: str = "neutral"


@dataclass(frozen=True, slots=True)
class PortfolioValuationComparisonDisplay:
    totals: tuple[PortfolioValuationComparisonDisplayRow, ...] = ()
    positions: tuple[PortfolioValuationComparisonDisplayRow, ...] = ()
