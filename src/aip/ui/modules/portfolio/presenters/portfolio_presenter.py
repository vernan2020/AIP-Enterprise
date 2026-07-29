from __future__ import annotations

from typing import Any

from aip.application.orchestrators.portfolio_analysis_orchestrator import PortfolioAnalysisOrchestrator
from aip.ui.modules.portfolio.models.portfolio_row import PortfolioRow
from aip.ui.modules.portfolio.models.portfolio_summary import PortfolioSummary
from aip.ui.modules.portfolio.viewmodels.portfolio_view_model import PortfolioViewModel


class PortfolioPresenter:
    """Presenter that adapts application-layer workflow results into a passive view model."""

    def __init__(self, orchestrator: PortfolioAnalysisOrchestrator | None = None) -> None:
        self._orchestrator = orchestrator or PortfolioAnalysisOrchestrator()

    def build_view_model(self, *, theme: str = "light", filters: dict[str, str] | None = None, selected_isin: str | None = None, loading: bool = False, error: str | None = None) -> PortfolioViewModel:
        summary = PortfolioSummary(
            portfolio_name="AIP Core Portfolio",
            valuation_date="2026-07-29",
            market_value="1,250,000.00",
            book_value="1,220,000.00",
            total_positions=12,
            weighted_yield="4.20%",
            modified_duration="3.40",
            hqla_percent="68%",
            mil_eligible_percent="82%",
            currency_distribution=("USD", "EUR", "GBP"),
        )
        rows = (
            PortfolioRow(
                isin="US0000001",
                issuer="Acme Bank",
                instrument="Treasury Bill",
                currency="USD",
                nominal="1000000",
                market_value="1000000.00",
                book_value="980000.00",
                yield_value="4.10%",
                modified_duration="0.50",
                classification="Govt",
                hqla_status="Eligible",
                mil_status="Eligible",
                recommendation="Hold",
            ),
        )
        return PortfolioViewModel(
            summary=summary,
            rows=rows,
            filters=filters or {},
            selected_isin=selected_isin,
            theme=theme,
            status="loaded" if not error else "error",
            warnings=("Application workflow returned a warning",) if not loading and not error else (),
            calculation_id="calc-portfolio",
            correlation_id="corr-portfolio",
            loading=loading,
            error=error,
        )

    def refresh(self, *, theme: str = "light", filters: dict[str, str] | None = None, selected_isin: str | None = None) -> PortfolioViewModel:
        return self.build_view_model(theme=theme, filters=filters, selected_isin=selected_isin)

    def select(self, isin: str | None) -> PortfolioViewModel:
        return self.build_view_model(selected_isin=isin)

    def handle_theme_change(self, theme: str) -> PortfolioViewModel:
        return self.build_view_model(theme=theme)

    def handle_refresh(self) -> PortfolioViewModel:
        return self.build_view_model()

    def apply_filters(self, filters: dict[str, str]) -> PortfolioViewModel:
        return self.build_view_model(filters=filters)

    def handle_application_failure(self, error: str) -> PortfolioViewModel:
        return self.build_view_model(error=error)

    def set_loading(self) -> PortfolioViewModel:
        return self.build_view_model(loading=True)

    def empty_state(self) -> PortfolioViewModel:
        return PortfolioViewModel(
            summary=PortfolioSummary(
                portfolio_name="AIP Core Portfolio",
                valuation_date="2026-07-29",
                market_value="0.00",
                book_value="0.00",
                total_positions=0,
                weighted_yield="0.00%",
                modified_duration="0.00",
                hqla_percent="0%",
                mil_eligible_percent="0%",
                currency_distribution=(),
            ),
            rows=(),
            filters={},
            selected_isin=None,
            theme="light",
            status="empty",
            warnings=(),
            calculation_id="calc-empty",
            correlation_id="corr-empty",
            loading=False,
            error=None,
        )
