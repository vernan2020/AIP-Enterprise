from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.product.demo.configuration.demo_config import DemoConfig
from aip.ui.modules.liquidity.models.liquidity_row import LiquidityRow
from aip.ui.modules.liquidity.viewmodels.liquidity_view_model import LiquidityViewModel


class LiquidityPresenter:
    """Adapt application-layer liquidity results into an immutable presentation model."""

    def __init__(self, demo_factory: DemoApplicationFactory | None = None) -> None:
        self._demo_factory = demo_factory or DemoApplicationFactory(
            DemoConfig(execution_mode="DEMO", demo_mode_enabled=True)
        )
        self._correlation_id = "corr-demo-liquidity"

    @staticmethod
    def _float(value: object) -> float:
        if value is None:
            return 0.0
        try:
            return float(str(value))
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _row(cls, payload: dict[str, Any], *, default_status: str) -> LiquidityRow:
        value = cls._float(payload.get("value"))
        days = payload.get("days_to_maturity")
        return LiquidityRow(
            section=str(payload.get("section") or ""),
            label=str(payload.get("label") or ""),
            value=f"{value:.2f}",
            bucket=str(payload.get("bucket") or ""),
            status=str(payload.get("status") or default_status),
            policy_reference=str(payload.get("policy_reference") or ""),
            issuer=str(payload.get("issuer") or ""),
            currency=str(payload.get("currency") or ""),
            classification=str(payload.get("classification") or ""),
            market_value_crc=cls._float(payload.get("market_value_crc")),
            factor=cls._float(payload.get("factor")),
            maturity_date=str(payload.get("maturity_date") or ""),
            days_to_maturity=int(days) if isinstance(days, (int, float)) else None,
        )

    def build_view_model(
        self,
        *,
        theme: str = "light",
        filters: dict[str, str] | None = None,
        selected_section: str | None = None,
        loading: bool = False,
        error: str | None = None,
    ) -> LiquidityViewModel:
        workflow_result = self._demo_factory.initial_load_workflow().execute(self._correlation_id)
        liquidity = workflow_result["liquidity"]

        summary = SimpleNamespace(
            liquidity_date=str(liquidity.get("liquidity_date") or "-"),
            cash_position=f"{self._float(liquidity.get('cash_position')):.2f}",
            net_cash_flow=f"{self._float(liquidity.get('net_cash_flow')):.2f}",
            liquidity_gap=f"{self._float(liquidity.get('liquidity_gap')):.2f}",
            hqla_capacity=f"{self._float(liquidity.get('hqla_capacity')):.2f}",
            mil_eligible_capacity=f"{self._float(liquidity.get('mil_eligible_capacity')):.2f}",
            stress_result=str(liquidity.get("stress_result") or "No configurado"),
            policy_status=str(liquidity.get("policy_status") or "No evaluado"),
            icl_total=self._float(liquidity.get("icl_total")),
            icl_mn=self._float(liquidity.get("icl_mn")),
            icl_me=self._float(liquidity.get("icl_me")),
            liquid_asset_fund_total=self._float(liquidity.get("liquid_asset_fund_total")),
            liquid_asset_fund_mn=self._float(liquidity.get("liquid_asset_fund_mn")),
            liquid_asset_fund_me=self._float(liquidity.get("liquid_asset_fund_me")),
            total_outflows_30d=self._float(liquidity.get("total_outflows_30d")),
            total_inflows_30d=self._float(liquidity.get("total_inflows_30d")),
            net_cash_outflow_30d=self._float(liquidity.get("net_cash_outflow_30d")),
            hqla_capacity_value=self._float(liquidity.get("hqla_capacity")),
            hqla_market_value_crc=self._float(liquidity.get("hqla_market_value_crc")),
            hqla_eligible_count=int(liquidity.get("hqla_eligible_count") or 0),
            hqla_restricted_count=int(liquidity.get("hqla_restricted_count") or 0),
            hqla_not_eligible_count=int(liquidity.get("hqla_not_eligible_count") or 0),
            mil_capacity_value=self._float(liquidity.get("mil_eligible_capacity")),
            mil_market_value_crc=self._float(liquidity.get("mil_market_value_crc")),
            mil_eligible_count=int(liquidity.get("mil_eligible_count") or 0),
            mil_restricted_count=int(liquidity.get("mil_restricted_count") or 0),
            mil_not_eligible_count=int(liquidity.get("mil_not_eligible_count") or 0),
            maturity_30d_crc=self._float(liquidity.get("maturity_30d_crc")),
            maturity_90d_crc=self._float(liquidity.get("maturity_90d_crc")),
            maturity_180d_crc=self._float(liquidity.get("maturity_180d_crc")),
            maturity_270d_crc=self._float(liquidity.get("maturity_270d_crc")),
            configuration_message=str(liquidity.get("configuration_message") or ""),
            icl_source_file=str(liquidity.get("icl_source_file") or ""),
            icl_source_date=str(liquidity.get("icl_source_date") or ""),
        )

        cashflow_rows = tuple(
            self._row(row, default_status="Healthy")
            for row in liquidity.get("cashflows", ())
            if isinstance(row, dict)
        )
        gap_rows = tuple(
            self._row(row, default_status="Balanced")
            for row in liquidity.get("gaps", ())
            if isinstance(row, dict)
        )
        hqla_rows = tuple(
            self._row(row, default_status="Eligible")
            for row in liquidity.get("hqla_rows", ())
            if isinstance(row, dict)
        )
        mil_rows = tuple(
            self._row(row, default_status="Eligible")
            for row in liquidity.get("mil_rows", ())
            if isinstance(row, dict)
        )
        stress_rows = tuple(
            self._row(row, default_status="Stable")
            for row in liquidity.get("stress_rows", ())
            if isinstance(row, dict)
        )
        maturity_rows = tuple(
            self._row(row, default_status="AVAILABLE")
            for row in liquidity.get("maturity_rows", ())
            if isinstance(row, dict)
        )

        return LiquidityViewModel(
            summary=summary,
            cashflow_rows=cashflow_rows,
            gap_rows=gap_rows,
            hqla_rows=hqla_rows,
            mil_rows=mil_rows,
            stress_rows=stress_rows,
            maturity_rows=maturity_rows,
            filters=filters or {},
            selected_section=selected_section,
            theme=theme,
            status="error" if error else "loaded",
            warnings=tuple(str(item) for item in workflow_result.get("warnings", ()) or ()),
            calculation_id=str(workflow_result["calculation_references"]["liquidity"]),
            correlation_id=self._correlation_id,
            loading=loading,
            error=error,
        )

    def refresh(
        self,
        *,
        theme: str = "light",
        filters: dict[str, str] | None = None,
        selected_section: str | None = None,
    ) -> LiquidityViewModel:
        return self.build_view_model(
            theme=theme,
            filters=filters,
            selected_section=selected_section,
        )

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
