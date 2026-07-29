from __future__ import annotations

from aip.application.orchestrators.liquidity_analysis_orchestrator import LiquidityAnalysisOrchestrator
from aip.ui.modules.liquidity.models.liquidity_row import LiquidityRow
from aip.ui.modules.liquidity.viewmodels.liquidity_view_model import LiquidityViewModel


class LiquidityPresenter:
    """Presenter that adapts application-layer liquidity results into an immutable view model."""

    def __init__(self, orchestrator: LiquidityAnalysisOrchestrator | None = None) -> None:
        self._orchestrator = orchestrator or LiquidityAnalysisOrchestrator()

    def build_view_model(self, *, theme: str = "light", filters: dict[str, str] | None = None, selected_section: str | None = None, loading: bool = False, error: str | None = None) -> LiquidityViewModel:
        summary = type(
            "LiquiditySummary",
            (),
            {
                "liquidity_date": "2026-07-29",
                "cash_position": "100.00",
                "net_cash_flow": "10.00",
                "liquidity_gap": "0.00",
                "hqla_capacity": "80.00",
                "mil_eligible_capacity": "60.00",
                "stress_result": "Stable",
                "policy_status": "Compliant",
            },
        )()
        cashflow_rows = (
            LiquidityRow(section="cashflow", label="Inflows", value="100.00", bucket="T+0", status="Healthy"),
        )
        gap_rows = (
            LiquidityRow(section="gap", label="Gap", value="0.00", bucket="T+1", status="Balanced"),
        )
        hqla_rows = (
            LiquidityRow(section="hqla", label="Eligible", value="80.00", policy_reference="POL-1", status="Eligible"),
        )
        mil_rows = (
            LiquidityRow(section="mil", label="Eligible Assets", value="60.00", policy_reference="POL-2", status="Eligible"),
        )
        stress_rows = (
            LiquidityRow(section="stress", label="Scenario", value="Baseline", status="Stable"),
        )
        return LiquidityViewModel(
            summary=summary,
            cashflow_rows=cashflow_rows,
            gap_rows=gap_rows,
            hqla_rows=hqla_rows,
            mil_rows=mil_rows,
            stress_rows=stress_rows,
            filters=filters or {},
            selected_section=selected_section,
            theme=theme,
            status="error" if error else "loaded",
            warnings=("Application workflow returned a warning",) if not loading and not error else (),
            calculation_id="calc-liquidity",
            correlation_id="corr-liquidity",
            loading=loading,
            error=error,
        )

    def refresh(self, *, theme: str = "light", filters: dict[str, str] | None = None, selected_section: str | None = None) -> LiquidityViewModel:
        return self.build_view_model(theme=theme, filters=filters, selected_section=selected_section)

    def select(self, section: str | None) -> LiquidityViewModel:
        return self.build_view_model(selected_section=section)

    def apply_filters(self, filters: dict[str, str]) -> LiquidityViewModel:
        return self.build_view_model(filters=filters)

    def handle_theme_change(self, theme: str) -> LiquidityViewModel:
        return self.build_view_model(theme=theme)

    def handle_application_failure(self, error: str) -> LiquidityViewModel:
        return self.build_view_model(error=error)

    def set_loading(self) -> LiquidityViewModel:
        return self.build_view_model(loading=True)
