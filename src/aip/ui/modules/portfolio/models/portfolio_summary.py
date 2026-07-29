from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PortfolioSummary:
    portfolio_name: str
    valuation_date: str
    market_value: str
    book_value: str
    total_positions: int
    weighted_yield: str
    modified_duration: str
    hqla_percent: str
    mil_eligible_percent: str
    currency_distribution: tuple[str, ...] = ()
