from __future__ import annotations

from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.ui.modules.executive.models.executive_row import ExecutiveRow
from aip.ui.modules.executive.viewmodels.executive_view_model import ExecutiveViewModel


class ExecutivePresenter:
    """Presenter that adapts application-layer outputs into an executive cockpit view model."""

    def __init__(self, demo_factory: DemoApplicationFactory | None = None) -> None:
        self._demo_factory = demo_factory or DemoApplicationFactory()
        self._correlation_id = "corr-demo-executive"

    def build_view_model(self, *, theme: str = "light", filters: dict[str, str] | None = None, loading: bool = False, error: str | None = None) -> ExecutiveViewModel:
        workflow_result = self._demo_factory.initial_load_workflow().execute(self._correlation_id)
        portfolio = workflow_result["portfolio"]
        liquidity = workflow_result["liquidity"]
        market = workflow_result["market"]
        summary = (
            f"Portfolio Market Value: {portfolio['market_value']:,.2f}",
            f"Book Value: {portfolio['book_value']:,.2f}",
            f"Liquidity Position: {liquidity['cash_position']:.2f}",
            f"Liquidity Gap: {liquidity['liquidity_gap']:.2f}",
            f"HQLA Capacity: {liquidity['hqla_capacity']:.2f}",
            f"MIL Capacity: {liquidity['mil_eligible_capacity']:.2f}",
            f"Stress Status: {liquidity['stress_result']}",
            f"Treasury Recommendation Status: {portfolio['relative_value_opportunity']}",
        )
        portfolio_view = (
            f"Market Value: {portfolio['market_value']:,.2f}",
            f"Yield: {portfolio['weighted_yield']:.2f}%",
            f"Modified Duration: {portfolio['modified_duration']:.2f}",
            f"Concentration: {portfolio['currency_distribution'][0]}",
            f"Asset Allocation: {','.join(portfolio['currency_distribution'])}",
            f"Top Issuers: {portfolio['positions'][0]['issuer']}, {portfolio['positions'][1]['issuer']}",
        )
        liquidity_view = (
            f"Cash Position: {liquidity['cash_position']:.2f}",
            f"Gap: {liquidity['liquidity_gap']:.2f}",
            f"Coverage: {liquidity['policy_status']}",
            f"HQLA: {liquidity['hqla_capacity']:.2f}",
            f"MIL: {liquidity['mil_eligible_capacity']:.2f}",
            f"Stress Result: {liquidity['stress_result']}",
            f"Policy Compliance: {liquidity['policy_status']}",
        )
        market_view = (
            f"Yield Curves: {'/'.join(curve['label'] for curve in market['curves'])}",
            f"Relative Value Opportunities: {market['relative_value_opportunities']}",
            f"Spread Summary: {market['average_spread']:.2f}",
            f"Market Status: {market['market_status']}",
        )
        recommendations = (
            ExecutiveRow(title="Treasury Buffer Review", detail="Maintain cash buffer ahead of next rollover", category="Treasury", severity="High", source="Treasury Ops"),
            ExecutiveRow(title="Funding Window", detail="Reprice term funding before rollover", category="Funding", severity="Medium", source="Funding Desk"),
        )
        alerts = (
            ExecutiveRow(title="Demo Mode Badge", detail="Deterministic demo data is active", category="System", severity="Medium", source="Demo Platform"),
        )
        trends = (
            ("30 Days", ("92", "95", "97", "94")),
            ("90 Days", ("88", "91", "94", "96")),
            ("12 Months", ("80", "84", "87", "91")),
        )
        return ExecutiveViewModel(
            summary=summary,
            portfolio=portfolio_view,
            liquidity=liquidity_view,
            market=market_view,
            recommendations=recommendations,
            alerts=alerts,
            trends=trends,
            filters=filters or {},
            theme_name=theme,
            status="loaded" if not error else "error",
            loading=loading,
            error=error,
        )

    def refresh(self, *, theme: str = "light", filters: dict[str, str] | None = None) -> ExecutiveViewModel:
        return self.build_view_model(theme=theme, filters=filters)

    def handle_theme_change(self, theme: str) -> ExecutiveViewModel:
        return self.build_view_model(theme=theme)

    def handle_refresh(self) -> ExecutiveViewModel:
        return self.build_view_model()

    def apply_filters(self, filters: dict[str, str]) -> ExecutiveViewModel:
        return self.build_view_model(filters=filters)

    def handle_application_failure(self, error: str) -> ExecutiveViewModel:
        return self.build_view_model(error=error)

    def set_loading(self) -> ExecutiveViewModel:
        return self.build_view_model(loading=True)
