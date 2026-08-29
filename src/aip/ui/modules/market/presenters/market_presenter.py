from __future__ import annotations

from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.product.demo.configuration.demo_config import DemoConfig
from aip.ui.modules.market.models.curve_point import CurvePoint
from aip.ui.modules.market.models.market_row import MarketRow
from aip.ui.modules.market.viewmodels.market_view_model import MarketViewModel


class MarketPresenter:
    """Presenter for rendering application-layer market data in the UI."""

    def __init__(self, demo_factory: DemoApplicationFactory | None = None) -> None:
        self._demo_factory = demo_factory or DemoApplicationFactory(
            DemoConfig(execution_mode="DEMO", demo_mode_enabled=True)
        )
        self._correlation_id = "corr-demo-market"

    def build_view_model(
        self,
        *,
        theme: str = "light",
        filters: dict[str, str] | None = None,
        selected_curve: str | None = None,
        loading: bool = False,
        error: str | None = None,
    ) -> MarketViewModel:
        workflow_result = self._demo_factory.initial_load_workflow().execute(self._correlation_id)
        market = workflow_result["market"]
        summary = type(
            "MarketSummary",
            (),
            {
                "market_date": market["market_date"],
                "curves_loaded": len(market["curves"]),
                "pricing_date": market["market_date"],
                "relative_value_opportunities": market["relative_value_opportunities"],
                "average_yield": f"{market['average_yield']:.2f}%",
                "average_duration": f"{market['average_duration']:.2f}",
                "average_spread": f"{market['average_spread']:.2f}",
                "market_status": market["market_status"],
            },
        )()
        rows = tuple(
            MarketRow(
                issuer=entry["issuer"],
                instrument=entry["instrument"],
                currency="USD",
                recommendation="BUY",
                confidence="High",
                spread=f"{market['average_spread']:.2f}",
                z_spread=f"{market['average_spread']:.2f}",
                benchmark_spread="0.05",
                market_value=f"{market['average_yield']:.2f}",
                book_value="98.00",
                clean_price="99.00",
                dirty_price="100.00",
                accrued_interest="1.00",
                duration=f"{market['average_duration']:.2f}",
                modified_duration="4.20",
                convexity="0.10",
                dv01="0.01",
                pvbp="0.02",
            )
            for entry in market["pricing_results"]
        )
        curve_points = tuple(
            CurvePoint(label=curve["label"], value=f"{curve['value']:.2f}", tenor=curve["tenor"])
            for curve in market["curves"]
        )
        return MarketViewModel(
            summary=summary,
            rows=rows,
            curve_points=curve_points,
            filters=filters or {},
            selected_curve=selected_curve,
            theme=theme,
            status="error" if error else "loaded",
            warnings=(
                ("Application workflow returned a warning",) if not loading and not error else ()
            ),
            calculation_id=workflow_result["calculation_references"]["market"],
            correlation_id=self._correlation_id,
            loading=loading,
            error=error,
        )

    def refresh(
        self,
        *,
        theme: str = "light",
        filters: dict[str, str] | None = None,
        selected_curve: str | None = None,
    ) -> MarketViewModel:
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
