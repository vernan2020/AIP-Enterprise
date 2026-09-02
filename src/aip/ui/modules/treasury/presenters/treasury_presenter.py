from __future__ import annotations

from decimal import Decimal

from aip.product.configured.services.configured_treasury_insight_service import (
    ConfiguredTreasuryInsightService,
    TreasuryInsightItem,
)
from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.ui.modules.treasury.models.treasury_row import TreasuryRow
from aip.ui.modules.treasury.viewmodels.treasury_view_model import TreasuryViewModel


class TreasuryPresenter:
    """Adapt certified liquidity and market outputs into a passive treasury view model."""

    def __init__(self, demo_factory: DemoApplicationFactory | None = None) -> None:
        self._demo_factory = demo_factory or DemoApplicationFactory()

    @staticmethod
    def _decimal(value: object) -> Decimal:
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (TypeError, ValueError):
            return Decimal("0")

    @classmethod
    def _format_crc_mm(cls, value: object) -> str:
        return f"₡{cls._decimal(value) / Decimal('1000000'):,.2f} MM"

    @staticmethod
    def _row(item: TreasuryInsightItem, timestamp: str) -> TreasuryRow:
        return TreasuryRow(
            title=item.title,
            detail=item.detail,
            severity=item.severity,
            source=item.source,
            timestamp=timestamp,
        )

    def build_view_model(
        self,
        *,
        theme: str = "light",
        filters: dict[str, str] | None = None,
        loading: bool = False,
        error: str | None = None,
    ) -> TreasuryViewModel:
        workflow_result = self._demo_factory.initial_load_workflow().execute("corr-treasury")
        liquidity = workflow_result["liquidity"]
        market_raw = workflow_result.get("market")
        market = market_raw if isinstance(market_raw, dict) else None
        valuation_date = str(
            liquidity.get("liquidity_date")
            or (market.get("market_date") if market is not None else "-")
            or "-"
        )
        insights = ConfiguredTreasuryInsightService.build(
            liquidity=liquidity,
            market=market,
        )
        rotation_count = (
            int(market.get("portfolio_rotation_candidate_count") or 0) if market is not None else 0
        )
        policy_status = str(liquidity.get("policy_status") or "No evaluado")
        stress_status = str(liquidity.get("stress_result") or "No configurado")
        summary = (
            f"Política de liquidez: {policy_status}",
            f"Stress: {stress_status}",
            f"Oportunidades de rotación: {rotation_count}",
        )
        return TreasuryViewModel(
            title="TESORERÍA",
            subtitle="Liquidez, garantías y oportunidades de mercado",
            summary=summary,
            recommendations=tuple(
                self._row(item, valuation_date) for item in insights.observations
            ),
            alerts=tuple(self._row(item, valuation_date) for item in insights.alerts),
            opportunities=tuple(self._row(item, valuation_date) for item in insights.opportunities),
            filters=filters or {},
            theme_name=theme,
            status="loaded" if not error else "error",
            loading=loading,
            error=error,
            valuation_date=valuation_date,
            cash_position=self._format_crc_mm(liquidity.get("cash_position")),
            liquidity_gap=self._format_crc_mm(liquidity.get("liquidity_gap")),
            hqla_capacity=self._format_crc_mm(liquidity.get("hqla_capacity")),
            mil_capacity=self._format_crc_mm(liquidity.get("mil_eligible_capacity")),
            maturity_30d=self._format_crc_mm(liquidity.get("maturity_30d_crc")),
            icl_total=f"{self._decimal(liquidity.get('icl_total')):.2f}",
            rotation_candidate_count=rotation_count,
            policy_status=policy_status,
            stress_status=stress_status,
        )

    def refresh(
        self, *, theme: str = "light", filters: dict[str, str] | None = None
    ) -> TreasuryViewModel:
        return self.build_view_model(theme=theme, filters=filters)

    def handle_theme_change(self, theme: str) -> TreasuryViewModel:
        return self.build_view_model(theme=theme)

    def handle_refresh(self) -> TreasuryViewModel:
        return self.build_view_model()

    def apply_filters(self, filters: dict[str, str]) -> TreasuryViewModel:
        return self.build_view_model(filters=filters)

    def handle_application_failure(self, error: str) -> TreasuryViewModel:
        return self.build_view_model(error=error)

    def set_loading(self) -> TreasuryViewModel:
        return self.build_view_model(loading=True)
