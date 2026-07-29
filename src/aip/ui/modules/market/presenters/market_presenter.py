from __future__ import annotations

from aip.application.orchestrators.portfolio_analysis_orchestrator import PortfolioAnalysisOrchestrator
from aip.ui.modules.market.models.curve_point import CurvePoint
from aip.ui.modules.market.models.market_row import MarketRow
from aip.ui.modules.market.viewmodels.market_view_model import MarketViewModel


class MarketPresenter:
    """Presenter for rendering application-layer market data in the UI."""

    def __init__(self, orchestrator: PortfolioAnalysisOrchestrator | None = None) -> None:
        self._orchestrator = orchestrator or PortfolioAnalysisOrchestrator()

    def build_view_model(self, *, theme: str = "light", filters: dict[str, str] | None = None, selected_curve: str | None = None, loading: bool = False, error: str | None = None) -> MarketViewModel:
        summary = type(
            "MarketSummary",
            (),
            {
                "market_date": "2026-07-29",
                "curves_loaded": 3,
                "pricing_date": "2026-07-29",
                "relative_value_opportunities": 2,
                "average_yield": "3.10%",
                "average_duration": "4.50",
                "average_spread": "0.45",
                "market_status": "Ready",
            },
        )()
        rows = (
            MarketRow(
                issuer="Acme Bank",
                instrument="Treasury Bill",
                currency="USD",
                recommendation="Rich",
                confidence="High",
                spread="0.45",
                z_spread="0.40",
                benchmark_spread="0.05",
                market_value="100.00",
                book_value="98.00",
                clean_price="99.00",
                dirty_price="100.00",
                accrued_interest="1.00",
                duration="4.50",
                modified_duration="4.20",
                convexity="0.10",
                dv01="0.01",
                pvbp="0.02",
            ),
        )
        curve_points = (
            CurvePoint(label="USD 3M", value="3.10", tenor="3M"),
            CurvePoint(label="USD 6M", value="3.20", tenor="6M"),
        )
        return MarketViewModel(
            summary=summary,
            rows=rows,
            curve_points=curve_points,
            filters=filters or {},
            selected_curve=selected_curve,
            theme=theme,
            status="error" if error else "loaded",
            warnings=("Application workflow returned a warning",) if not loading and not error else (),
            calculation_id="calc-market",
            correlation_id="corr-market",
            loading=loading,
            error=error,
        )

    def refresh(self, *, theme: str = "light", filters: dict[str, str] | None = None, selected_curve: str | None = None) -> MarketViewModel:
        return self.build_view_model(theme=theme, filters=filters, selected_curve=selected_curve)

    def select(self, curve: str | None) -> MarketViewModel:
        return self.build_view_model(selected_curve=curve)

    def apply_filters(self, filters: dict[str, str]) -> MarketViewModel:
        return self.build_view_model(filters=filters)

    def handle_theme_change(self, theme: str) -> MarketViewModel:
        return self.build_view_model(theme=theme)

    def handle_application_failure(self, error: str) -> MarketViewModel:
        return self.build_view_model(error=error)

    def set_loading(self) -> MarketViewModel:
        return self.build_view_model(loading=True)
