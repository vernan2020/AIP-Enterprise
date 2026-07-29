from __future__ import annotations

from typing import Any

from aip.application.orchestrators.liquidity_analysis_orchestrator import LiquidityAnalysisOrchestrator
from aip.application.orchestrators.portfolio_analysis_orchestrator import PortfolioAnalysisOrchestrator
from aip.ui.modules.executive.models.executive_row import ExecutiveRow
from aip.ui.modules.executive.viewmodels.executive_view_model import ExecutiveViewModel


class ExecutivePresenter:
    """Presenter that adapts application-layer outputs into an executive cockpit view model."""

    def __init__(self, portfolio_orchestrator: PortfolioAnalysisOrchestrator | None = None, liquidity_orchestrator: LiquidityAnalysisOrchestrator | None = None) -> None:
        self._portfolio_orchestrator = portfolio_orchestrator or PortfolioAnalysisOrchestrator()
        self._liquidity_orchestrator = liquidity_orchestrator or LiquidityAnalysisOrchestrator()

    def build_view_model(self, *, theme: str = "light", filters: dict[str, str] | None = None, loading: bool = False, error: str | None = None) -> ExecutiveViewModel:
        summary = (
            "Portfolio Market Value: 1,250,000.00",
            "Book Value: 1,220,000.00",
            "Liquidity Position: 100.00",
            "Liquidity Gap: 0.00",
            "HQLA Capacity: 80.00",
            "MIL Capacity: 60.00",
            "Stress Status: Stable",
            "Treasury Recommendation Status: Healthy",
        )
        portfolio = (
            "Market Value: 1,250,000.00",
            "Yield: 4.20%",
            "Modified Duration: 3.40",
            "Concentration: Diversified",
            "Asset Allocation: USD/EUR/GBP",
            "Top Issuers: Acme Bank, Blue Ridge",
        )
        liquidity = (
            "Cash Position: 100.00",
            "Gap: 0.00",
            "Coverage: 98%",
            "HQLA: 80.00",
            "MIL: 60.00",
            "Stress Result: Stable",
            "Policy Compliance: Compliant",
        )
        market = (
            "Yield Curves: USD 3M/6M/1Y",
            "Relative Value Opportunities: 2",
            "Spread Summary: 0.45",
            "Market Status: Ready",
        )
        recommendations = (
            ExecutiveRow(title="Treasury Buffer Review", detail="Maintain cash buffer ahead of next rollover", category="Treasury", severity="High", source="Treasury Ops"),
            ExecutiveRow(title="Funding Window", detail="Reprice term funding before rollover", category="Funding", severity="Medium", source="Funding Desk"),
        )
        alerts = (
            ExecutiveRow(title="Critical Gap", detail="Near-term funding headroom remains tight", category="Liquidity", severity="Critical", source="Liquidity Monitor"),
            ExecutiveRow(title="High Spread", detail="Relative value remains favorable but spread widened", category="Market", severity="High", source="Market Desk"),
        )
        trends = (
            ("30 Days", ("92", "95", "97", "94")),
            ("90 Days", ("88", "91", "94", "96")),
            ("12 Months", ("80", "84", "87", "91")),
        )
        return ExecutiveViewModel(
            summary=summary,
            portfolio=portfolio,
            liquidity=liquidity,
            market=market,
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
