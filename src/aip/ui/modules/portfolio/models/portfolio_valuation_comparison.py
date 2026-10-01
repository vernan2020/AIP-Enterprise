from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PortfolioValuationComparisonDisplayRow:
    cells: tuple[str, ...]
    tone: str = "neutral"


@dataclass(frozen=True, slots=True)
class PortfolioValuationChartPoint:
    label: str
    value: Decimal = Decimal("0")
    positive: Decimal = Decimal("0")
    negative: Decimal = Decimal("0")


@dataclass(frozen=True, slots=True)
class PortfolioValuationKpi:
    key: str
    title: str
    value: str
    tone: str = "neutral"


@dataclass(frozen=True, slots=True)
class PortfolioValuationComparisonDisplay:
    kpis: tuple[PortfolioValuationKpi, ...] = ()
    top_gains: tuple[PortfolioValuationChartPoint, ...] = ()
    top_losses: tuple[PortfolioValuationChartPoint, ...] = ()
    currency_points: tuple[PortfolioValuationChartPoint, ...] = ()
    issuer_points: tuple[PortfolioValuationChartPoint, ...] = ()
    positions: tuple[PortfolioValuationComparisonDisplayRow, ...] = ()
    all_positions: tuple[PortfolioValuationComparisonDisplayRow, ...] = ()
