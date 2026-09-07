from __future__ import annotations

import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from aip.domain.financial_analysis.models import (
    EntityFinancialSummary,
    FinancialEntity,
)
from aip.domain.intelligence.models import (
    FinancialAnalysisContext,
    FinancialIntelligenceContext,
    FinancialMetricContext,
    FinancialPeerContext,
    FinancialRatingIndicatorContext,
    FinancialReconciliationContext,
    MacroIntelligenceContext,
    MacroProjectionPointContext,
    MarketOpportunity,
)
from aip.product.configured.services.configured_financial_analysis_service import (
    ConfiguredFinancialAnalysisService,
)
from aip.product.configured.services.configured_macro_intelligence_service import (
    ConfiguredMacroIntelligenceService,
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

    _MAX_FINANCIAL_PEERS = 12

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

        duration_buckets = {item.label: item.share_percent for item in analytics.duration_buckets}
        cutoff = self._resolve_cutoff(portfolio, liquidity)
        financial_analysis = self._resolve_financial_analysis(cutoff)
        macro_intelligence = self._resolve_macro_intelligence()
        warnings = tuple(str(item) for item in workflow.get("warnings", ()) or ())
        source_states = [
            f"{item.get('name', 'fuente')}={item.get('state', 'N/D')}"
            for item in workflow.get("source_statuses", ())
            if isinstance(item, dict)
        ]
        source_states.extend(
            (
                f"financial_analysis={financial_analysis.status}",
                f"macro_intelligence={macro_intelligence.status}",
            )
        )

        return FinancialIntelligenceContext(
            cutoff_date=cutoff,
            execution_mode=str(self._factory.config.execution_mode),
            data_quality_status=str(
                portfolio.get("data_quality_status") or workflow.get("data_quality_status") or "N/D"
            ),
            source_states=tuple(source_states),
            warnings=warnings,
            market_value_crc=self._decimal(
                portfolio.get("market_value_crc") or portfolio.get("market_value")
            ),
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
            financial_analysis=financial_analysis,
            macro_intelligence=macro_intelligence,
        )

    def _resolve_financial_analysis(self, cutoff: date) -> FinancialAnalysisContext:
        try:
            service = self._factory.container.resolve(ConfiguredFinancialAnalysisService)
            snapshot = service.load(
                selected_entity_id=self._configured_financial_entity_id(),
                cutoff_date=cutoff,
            )
        except Exception:
            return FinancialAnalysisContext(
                status="UNAVAILABLE",
                cutoff_date=None,
                entity_id="",
                entity_name="",
                entity_category="",
            )

        selected = snapshot.selected_entity
        rating = snapshot.rating
        reconciliation_issues = tuple(
            FinancialReconciliationContext(
                code=item.code,
                label=item.label,
                status=item.status.value,
                difference=item.difference,
            )
            for item in snapshot.indicator_reconciliations
            if item.status.value not in {"MATCH", "TOLERANCE"}
        )
        return FinancialAnalysisContext(
            status=snapshot.status,
            cutoff_date=snapshot.cutoff_date,
            entity_id=selected.entity_id if selected is not None else "",
            entity_name=selected.name if selected is not None else "",
            entity_category=selected.category if selected is not None else "",
            metrics=tuple(
                FinancialMetricContext(
                    code=item.code,
                    label=item.label,
                    value=item.value,
                    unit=item.unit,
                    previous_value=item.previous_value,
                    change_percent=item.change_percent,
                    source_account=item.source_account or "",
                )
                for item in snapshot.metrics
            ),
            peers=tuple(
                FinancialPeerContext(
                    entity_name=item.entity.name,
                    category=item.entity.category,
                    assets=item.assets,
                    loans=item.loans,
                    equity=item.equity,
                    net_income=item.net_income,
                    roa_percent=item.roa_percent,
                    roe_percent=item.roe_percent,
                )
                for item in self._select_financial_peers(snapshot.peer_summaries, selected)
            ),
            rating_status=rating.status if rating is not None else "UNAVAILABLE",
            rating_score=rating.score if rating is not None else None,
            rating_grade=rating.grade or "" if rating is not None else "",
            rating_coverage_percent=rating.coverage_percent if rating is not None else None,
            rating_methodology=(
                f"{rating.methodology_code} · {rating.methodology_version}"
                if rating is not None
                else ""
            ),
            rating_indicators=(
                tuple(
                    FinancialRatingIndicatorContext(
                        code=item.code,
                        label=item.label,
                        dimension=item.dimension,
                        direction=item.direction.value,
                        level=item.level.value,
                        value=item.value,
                        peer_count=item.peer_count,
                        percentile_15=item.percentile_15,
                        midpoint=item.midpoint,
                        percentile_85=item.percentile_85,
                    )
                    for item in rating.indicators
                )
                if rating is not None
                else ()
            ),
            reconciliation_issues=reconciliation_issues,
        )

    def _resolve_macro_intelligence(self) -> MacroIntelligenceContext:
        try:
            service = self._factory.container.resolve(ConfiguredMacroIntelligenceService)
            payload = service.get_projection()
        except Exception:
            return MacroIntelligenceContext(
                status="UNAVAILABLE",
                scenario_id="",
                version=0,
                scenario_type="",
                scenario_status="",
                dataset_as_of_date=None,
                horizon=0,
            )

        status = str(payload.get("status") or "UNAVAILABLE").upper()
        rows: list[MacroProjectionPointContext] = []
        if status == "AVAILABLE":
            for raw in payload.get("rows", ()):
                if not isinstance(raw, dict):
                    continue
                period = self._date(raw.get("period"))
                if period is None:
                    continue
                rows.append(
                    MacroProjectionPointContext(
                        period=period,
                        fx_sell=self._optional_decimal(raw.get("fx_sell")),
                        tpm=self._optional_decimal(raw.get("tpm")),
                        tbp=self._optional_decimal(raw.get("tbp")),
                        tri_crc_12m=self._optional_decimal(raw.get("tri_crc_12m")),
                        tri_usd_12m=self._optional_decimal(raw.get("tri_usd_12m")),
                        inflation=self._optional_decimal(raw.get("inflation")),
                        imae=self._optional_decimal(raw.get("imae")),
                    )
                )
            rows.sort(key=lambda item: item.period)

        return MacroIntelligenceContext(
            status=status,
            scenario_id=str(payload.get("scenario_id") or ""),
            version=self._integer(payload.get("version")),
            scenario_type=str(payload.get("scenario_type") or ""),
            scenario_status=str(payload.get("scenario_status") or ""),
            dataset_as_of_date=self._date(payload.get("dataset_as_of_date")),
            horizon=self._integer(payload.get("horizon")) or len(rows),
            rows=tuple(rows),
        )

    def _configured_financial_entity_id(self) -> str | None:
        source_config = self._factory.configured_source_config
        sugef_config = getattr(source_config, "sugef_financial", None)
        entity_codes = tuple(getattr(sugef_config, "api_entity_codes", ()) or ())
        return str(entity_codes[0]).strip() if entity_codes else None

    @classmethod
    def _select_financial_peers(
        cls,
        peers: tuple[EntityFinancialSummary, ...],
        selected: FinancialEntity | None,
    ) -> tuple[EntityFinancialSummary, ...]:
        candidates = [
            item
            for item in peers
            if selected is None or item.entity.entity_id != selected.entity_id
        ]
        same_category = [
            item
            for item in candidates
            if selected is not None and item.entity.category == selected.category
        ]
        same_category.sort(key=cls._peer_sort_key, reverse=True)
        overall = sorted(candidates, key=cls._peer_sort_key, reverse=True)

        result: list[EntityFinancialSummary] = []
        seen: set[str] = set()
        for item in same_category + overall:
            if item.entity.entity_id in seen:
                continue
            result.append(item)
            seen.add(item.entity.entity_id)
            if len(result) >= cls._MAX_FINANCIAL_PEERS:
                break
        return tuple(result)

    @staticmethod
    def _peer_sort_key(item: EntityFinancialSummary) -> Decimal:
        return item.assets if item.assets is not None else Decimal("-1")

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
            value = cls._decimal(position.get("market_value_crc") or position.get("market_value"))
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

    def _resolve_cutoff(
        self,
        portfolio: dict[str, Any],
        liquidity: dict[str, Any],
    ) -> date:
        candidates = (
            portfolio.get("valuation_date"),
            liquidity.get("liquidity_date"),
        )
        for candidate in candidates:
            parsed = self._date(candidate)
            if parsed is not None:
                return parsed
        configured_cutoff = self._factory.config.data_cutoff_date
        if isinstance(configured_cutoff, date):
            return configured_cutoff
        raise RuntimeError("AIP no dispone de una fecha de corte válida para el agente")

    @staticmethod
    def _date(value: object) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None

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
        if value is None or isinstance(value, bool):
            return 0
        try:
            return int(Decimal(str(value)))
        except (InvalidOperation, TypeError, ValueError):
            return 0

    @staticmethod
    def _normalize_text(value: object) -> str:
        decomposed = unicodedata.normalize("NFKD", str(value or ""))
        return " ".join(
            "".join(character for character in decomposed if not unicodedata.combining(character))
            .upper()
            .split()
        )
