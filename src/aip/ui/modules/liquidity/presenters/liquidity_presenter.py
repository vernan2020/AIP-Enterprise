from __future__ import annotations

from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.ui.modules.liquidity.models.liquidity_row import LiquidityRow
from aip.ui.modules.liquidity.viewmodels.liquidity_view_model import LiquidityViewModel


class LiquidityPresenter:
    """Presenter that adapts application-layer liquidity results into an immutable view model."""

    def __init__(self, demo_factory: DemoApplicationFactory | None = None) -> None:
        self._demo_factory = demo_factory or DemoApplicationFactory()
        self._correlation_id = "corr-demo-liquidity"

    def build_view_model(self, *, theme: str = "light", filters: dict[str, str] | None = None, selected_section: str | None = None, loading: bool = False, error: str | None = None) -> LiquidityViewModel:
        workflow_result = self._demo_factory.initial_load_workflow().execute(self._correlation_id)
        liquidity = workflow_result["liquidity"]
        summary = type(
            "LiquiditySummary",
            (),
            {
                "liquidity_date": liquidity["liquidity_date"],
                "cash_position": f"{liquidity['cash_position']:.2f}",
                "net_cash_flow": f"{liquidity['net_cash_flow']:.2f}",
                "liquidity_gap": f"{liquidity['liquidity_gap']:.2f}",
                "hqla_capacity": f"{liquidity['hqla_capacity']:.2f}",
                "mil_eligible_capacity": f"{liquidity['mil_eligible_capacity']:.2f}",
                "stress_result": liquidity["stress_result"],
                "policy_status": liquidity["policy_status"],
            },
        )()
        cashflow_rows = tuple(
            LiquidityRow(section=row["section"], label=row["label"], value=row["value"], bucket=row.get("bucket", ""), status=row.get("status", "Healthy"))
            for row in liquidity["cashflows"]
        )
        gap_rows = tuple(
            LiquidityRow(section=row["section"], label=row["label"], value=row["value"], bucket=row.get("bucket", ""), status=row.get("status", "Balanced"))
            for row in liquidity["gaps"]
        )
        hqla_rows = tuple(
            LiquidityRow(section=row["section"], label=row["label"], value=row["value"], policy_reference=row.get("policy_reference", ""), status=row.get("status", "Eligible"))
            for row in liquidity["hqla_rows"]
        )
        mil_rows = tuple(
            LiquidityRow(section=row["section"], label=row["label"], value=row["value"], policy_reference=row.get("policy_reference", ""), status=row.get("status", "Eligible"))
            for row in liquidity["mil_rows"]
        )
        stress_rows = tuple(
            LiquidityRow(section=row["section"], label=row["label"], value=row["value"], status=row.get("status", "Stable"))
            for row in liquidity["stress_rows"]
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
            calculation_id=workflow_result["calculation_references"]["liquidity"],
            correlation_id=self._correlation_id,
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
