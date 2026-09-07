from __future__ import annotations

import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from aip.domain.intelligence.models import (
    FinancialIntelligenceContext,
    MarketOpportunity,
)
from aip.product.configured.services.configured_portfolio_dashboard_analytics_service import (
    ConfiguredPortfolioDashboardAnalyticsService,
)
from aip.product.configured.services.configured_portfolio_dv01_service import (
    ConfiguredPortfolioDV01Service,
)
from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory


class AIPFinancialIntelligenceContextProvider:
    """Build a read-only intelligence context from certified AIP application services."""

    def __init__(self, application_factory: DemoApplicationFactory) -> None:
        self._factory = application_factory

    def load(self) -> FinancialIntelligenceContext:
        workflow = self._factory.initial_load_workflow().execute("corr-financial-intelligence")
        portfolio = self._mapping(workflow.get("portfolio"))
        market = self._mapping(workflow.get("market"))
        liquidity = self._mapping(workflow.get("liquidity"))
        analytics = ConfiguredPortfolioDashboardAnalyticsService.calculate(
            portfolio=portfolio,
            market=market,
        )

        duration_buckets = {
            item.label: item.share_percent for item in analytics.duration_buckets
        }
        cutoff = self._resolve_cutoff(portfolio, liquidity)
        warnings = tuple(str(item) for item in workflow.get("warnings", ()) or ())
        source_states = tuple(
            f"{item.get('name', 'fuente')}={item.get('state', 'N/D')}"
            for item in workflow.get("source_statuses", ())
            if isinstance(item, dict)
        )

        return FinancialIntelligenceContext(
            cutoff_date=cutoff,
            execution_mode=str(self._factory.config.execution_mode),
            data_quality_status=str(
                portfolio.get("data_quality_status")
                or workflow.get("data_quality_status")
                or "N/D"
            ),
            source_states=source_states,
            warnings=warnings,
            market_value_crc=self._decimal(portfolio.get("market_value_crc") or portfolio.get("market_value")),
            weighted_yield_percent=self._optional_decimal(portfolio.get("weighted_yield")),
            modified_duration=self._optional_decimal(portfolio.get("modified_duration")),
            hqla_percent=self._optional_decimal(portfolio.get("hqla_percent")),
            dv01_crc=self._resolve_dv01(),
            issuer_hhi=analytics.hhi,
            government_bccr_share_percent=self._government_bccr_share(portfolio),
            duration_under_1_share_percent=duration_buckets.get("< 1 año"),
            duration_1_5_share_percent=duration_buckets.get("1 a 5 años"),
            duration_over_5_share_percent=duration_buckets.get("> 5 años"),
            icl_total=self._optional_decimal(liquidity.get("icl_total")),
            hqla_capacity_crc=self._optional_decimal(liquidity.get("hqla_capacity")),
            hqla_restricted_count=self._integer(liquidity.get("hqla_restricted_count")),
            liquidity_policy_status=str(liquidity.get("policy_status") or "No evaluado"),
            liquidity_stress_result=str(liquidity.get("stress_result") or "No configurado"),
            opportunities=tuple(
                MarketOpportunity(
                    series=item.series,
                    issuer=item.issuer,
                    spread_bp=item.spread_bp,
                    classification=item.classification,
                )
                for item in analytics.opportunities
            ),
        )

    def _resolve_dv01(self) -> Decimal | None:
        try:
            service = self._factory.container.resolve(ConfiguredPortfolioDV01Service)
            return self._optional_decimal(service.calculate().total_dv01_crc)
        except Exception:
            return None

    @classmethod
    def _government_bccr_share(cls, portfolio: dict[str, Any]) -> Decimal | None:
        positions = [item for item in portfolio.get("positions", ()) if isinstance(item, dict)]
        if not positions:
            return None
        total = Decimal("0")
        sovereign = Decimal("0")
        for position in positions:
            value = cls._decimal(
                position.get("market_value_crc") or position.get("market_value")
            )
            total += value
            issuer = cls._normalize_text(position.get("issuer"))
            if any(
                token in issuer
                for token in (
                    "GOBIERNO",
                    "MINISTERIO DE HACIENDA",
                    "BANCO CENTRAL",
                    "BCCR",
                )
            ):
                sovereign += value
        if total <= 0:
            return None
        return sovereign / total * Decimal("100")

    @staticmethod
    def _resolve_cutoff(
        portfolio: dict[str, Any],
        liquidity: dict[str, Any],
    ) -> date:
        candidates = (
            portfolio.get("valuation_date"),
            liquidity.get("liquidity_date"),
        )
        for candidate in candidates:
            text = str(candidate or "").strip()
            if not text:
                continue
            try:
                return date.fromisoformat(text[:10])
            except ValueError:
                continue
        return date.today()

    @staticmethod
    def _mapping(value: object) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    @staticmethod
    def _decimal(value: object) -> Decimal:
        if isinstance(value, Decimal):
            return value
        if value is None or value == "":
            return Decimal("0")
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal("0")

    @classmethod
    def _optional_decimal(cls, value: object) -> Decimal | None:
        if value is None or value == "":
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None

    @staticmethod
    def _integer(value: object) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _normalize_text(value: object) -> str:
        decomposed = unicodedata.normalize("NFKD", str(value or ""))
        return " ".join(
            "".join(character for character in decomposed if not unicodedata.combining(character))
            .upper()
            .split()
        )
