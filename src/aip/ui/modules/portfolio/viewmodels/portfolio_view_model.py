from __future__ import annotations

from dataclasses import dataclass, field

from aip.ui.modules.portfolio.models.portfolio_row import PortfolioRow
from aip.ui.modules.portfolio.models.portfolio_summary import PortfolioSummary


@dataclass(frozen=True, slots=True)
class PortfolioViewModel:
    """Immutable presentation model for the portfolio workspace."""

    summary: PortfolioSummary
    rows: tuple[PortfolioRow, ...]
    filters: dict[str, str] = field(default_factory=dict)
    selected_isin: str | None = None
    theme: str = "light"
    status: str = "ready"
    warnings: tuple[str, ...] = ()
    calculation_id: str | None = None
    correlation_id: str | None = None
    loading: bool = False
    error: str | None = None
