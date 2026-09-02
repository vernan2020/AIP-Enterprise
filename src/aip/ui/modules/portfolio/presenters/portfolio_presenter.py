from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from aip.product.configured.services.configured_portfolio_dashboard_analytics_service import (
    ConfiguredPortfolioDashboardAnalyticsService,
)
from aip.product.configured.services.configured_portfolio_dv01_service import (
    ConfiguredPortfolioDV01Service,
)
from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.product.demo.configuration.demo_config import DemoConfig
from aip.ui.modules.portfolio.models.portfolio_dashboard_point import PortfolioDashboardPoint
from aip.ui.modules.portfolio.models.portfolio_row import PortfolioRow
from aip.ui.modules.portfolio.models.portfolio_summary import PortfolioSummary
from aip.ui.modules.portfolio.viewmodels.portfolio_view_model import PortfolioViewModel

logger = logging.getLogger(__name__)


class PortfolioPresenter:
    """Adapt application-layer portfolio results into a passive presentation model."""

    def __init__(self, demo_factory: DemoApplicationFactory | None = None) -> None:
        self._demo_factory = demo_factory or DemoApplicationFactory(
            DemoConfig(execution_mode="DEMO", demo_mode_enabled=True)
        )
        self._correlation_id = "corr-portfolio"

    @staticmethod
    def _format_optional_number(
        value: Any,
        *,
        decimals: int = 2,
        suffix: str = "",
    ) -> str:
        if value is None or value == "":
            return "N/D"
        try:
            return f"{float(value):.{decimals}f}{suffix}"
        except (TypeError, ValueError):
            return "N/D"

    @staticmethod
    def _format_crc_mm(value: object) -> str:
        try:
            amount = Decimal(str(value))
        except (TypeError, ValueError):
            return "N/D"
        return f"₡{amount / Decimal('1000000'):,.2f} MM"

    def build_view_model(
        self,
        *,
        theme: str = "light",
        filters: dict[str, str] | None = None,
        selected_isin: str | None = None,
        loading: bool = False,
        error: str | None = None,
    ) -> PortfolioViewModel:
        workflow_result = self._demo_factory.initial_load_workflow().execute(self._correlation_id)
        portfolio = workflow_result["portfolio"]
        market = workflow_result.get("market")
        market_payload = market if isinstance(market, dict) else None

        rows = tuple(
            PortfolioRow(
                isin=position["isin"],
                issuer=position["issuer"],
                instrument=position["instrument"],
                currency=position["currency"],
                nominal=f"{position['nominal']:.0f}",
                market_value=f"{position['market_value']:.2f}",
                book_value=f"{position['book_value']:.2f}",
                yield_value=f"{position['yield_value']:.2f}%",
                modified_duration=self._format_optional_number(position.get("modified_duration")),
                classification=position["classification"],
                hqla_status=position["hqla_status"],
                mil_status=position["mil_status"],
                recommendation=position["recommendation"],
            )
            for position in portfolio["positions"]
        )
        summary = PortfolioSummary(
            portfolio_name="AIP Core Portfolio",
            valuation_date=portfolio["valuation_date"],
            market_value=f"{portfolio['market_value']:,.2f}",
            book_value=f"{portfolio['book_value']:,.2f}",
            total_positions=len(portfolio["positions"]),
            weighted_yield=f"{portfolio['weighted_yield']:.2f}%",
            modified_duration=self._format_optional_number(portfolio.get("modified_duration")),
            hqla_percent=f"{portfolio['hqla_percent']:.0f}%",
            mil_eligible_percent=f"{portfolio['mil_eligible_percent']:.0f}%",
            currency_distribution=portfolio["currency_distribution"],
        )

        analytics = ConfiguredPortfolioDashboardAnalyticsService.calculate(
            portfolio=portfolio,
            market=market_payload,
        )
        top_issuer_points = tuple(
            PortfolioDashboardPoint(
                label=item.label,
                value=item.share_percent,
                secondary_value=Decimal(item.position_count),
                detail=self._format_crc_mm(item.market_value_crc),
            )
            for item in analytics.top_issuers
        )
        currency_points = tuple(
            PortfolioDashboardPoint(
                label=item.label,
                value=item.share_percent,
                secondary_value=Decimal(item.position_count),
                detail=self._format_crc_mm(item.market_value_crc),
            )
            for item in analytics.currencies
        )
        duration_points = tuple(
            PortfolioDashboardPoint(
                label=item.label,
                value=item.share_percent,
                secondary_value=Decimal(item.position_count),
                detail=self._format_crc_mm(item.market_value_crc),
            )
            for item in analytics.duration_buckets
        )
        opportunity_points = tuple(
            PortfolioDashboardPoint(
                label=item.series or item.issuer,
                value=item.spread_bp,
                detail=f"{item.issuer} · {item.classification}",
            )
            for item in analytics.opportunities
        )

        dv01_total = "N/D"
        dv01_status = "UNAVAILABLE"
        try:
            dv01_service = self._demo_factory.container.resolve(ConfiguredPortfolioDV01Service)
            dv01_result = dv01_service.calculate()
            dv01_total = self._format_crc_mm(dv01_result.total_dv01_crc)
            dv01_status = str(dv01_result.status)
        except Exception as exc:  # demo runtime or unavailable configured dependency
            logger.debug("Portfolio DV01 unavailable in dashboard: %s", exc)

        warnings = tuple(str(item) for item in workflow_result.get("warnings", ()) or ())
        return PortfolioViewModel(
            summary=summary,
            rows=rows,
            filters=filters or {},
            selected_isin=selected_isin,
            theme=theme,
            status="loaded" if not error else "error",
            warnings=warnings,
            calculation_id=workflow_result["calculation_references"]["portfolio"],
            correlation_id=self._correlation_id,
            loading=loading,
            error=error,
            health_score="N/D",
            health_status="Metodología institucional pendiente de certificación",
            dv01_total=dv01_total,
            dv01_status=dv01_status,
            hhi=f"{analytics.hhi:,.0f}",
            data_quality_status=str(portfolio.get("data_quality_status") or "N/D"),
            top_issuer_points=top_issuer_points,
            currency_points=currency_points,
            duration_points=duration_points,
            opportunity_points=opportunity_points,
        )

    def refresh(
        self,
        *,
        theme: str = "light",
        filters: dict[str, str] | None = None,
        selected_isin: str | None = None,
    ) -> PortfolioViewModel:
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
                valuation_date="N/D",
                market_value="0.00",
                book_value="0.00",
                total_positions=0,
                weighted_yield="N/D",
                modified_duration="N/D",
                hqla_percent="N/D",
                mil_eligible_percent="N/D",
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
