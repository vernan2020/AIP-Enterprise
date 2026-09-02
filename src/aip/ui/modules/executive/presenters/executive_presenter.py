from __future__ import annotations

from decimal import Decimal

from aip.product.configured.services.configured_macro_intelligence_service import (
    ConfiguredMacroIntelligenceService,
)
from aip.product.configured.services.configured_treasury_insight_service import (
    ConfiguredTreasuryInsightService,
    TreasuryInsightItem,
)
from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.ui.modules.executive.models.executive_row import ExecutiveRow
from aip.ui.modules.executive.viewmodels.executive_view_model import ExecutiveViewModel


class ExecutivePresenter:
    """Adapta resultados certificados al panel ejecutivo integrado."""

    _STATUS_TRANSLATIONS = {
        "AVAILABLE": "DISPONIBLE",
        "UNAVAILABLE": "NO DISPONIBLE",
        "APPROVED": "APROBADO",
        "DRAFT": "BORRADOR",
        "READY": "LISTO",
        "LOADED": "CARGADO",
        "PASS": "CUMPLE",
        "FAIL": "NO CUMPLE",
        "NOT_CONFIGURED": "NO CONFIGURADO",
    }

    def __init__(self, demo_factory: DemoApplicationFactory | None = None) -> None:
        self._demo_factory = demo_factory or DemoApplicationFactory()
        self._correlation_id = "corr-executive"

    @staticmethod
    def _decimal(value: object) -> Decimal:
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (TypeError, ValueError):
            return Decimal("0")

    @classmethod
    def _translate_status(cls, value: object) -> str:
        text = str(value or "N/D")
        return cls._STATUS_TRANSLATIONS.get(text.strip().upper(), text)

    @classmethod
    def _format_crc_mm(cls, value: object) -> str:
        return f"₡{cls._decimal(value) / Decimal('1000000'):,.2f} MM"

    @staticmethod
    def _executive_row(
        item: TreasuryInsightItem,
        *,
        category: str,
        timestamp: str,
    ) -> ExecutiveRow:
        return ExecutiveRow(
            title=item.title,
            detail=item.detail,
            category=category,
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
    ) -> ExecutiveViewModel:
        workflow_result = self._demo_factory.initial_load_workflow().execute(self._correlation_id)
        portfolio = workflow_result["portfolio"]
        liquidity = workflow_result["liquidity"]
        market = workflow_result["market"]
        valuation_date = str(
            portfolio.get("valuation_date")
            or liquidity.get("liquidity_date")
            or market.get("market_date")
            or "-"
        )

        insights = ConfiguredTreasuryInsightService.build(
            liquidity=liquidity,
            market=market,
        )
        recommendations = tuple(
            self._executive_row(item, category="Tesorería", timestamp=valuation_date)
            for item in insights.observations
        ) + tuple(
            self._executive_row(item, category="Mercado / Valor Relativo", timestamp=valuation_date)
            for item in insights.opportunities
        )
        alerts = list(
            self._executive_row(item, category="Liquidez", timestamp=valuation_date)
            for item in insights.alerts
        )
        for warning in workflow_result.get("warnings", ()) or ():
            alerts.append(
                ExecutiveRow(
                    title="Advertencia de fuente o cálculo",
                    detail=str(warning),
                    category="Sistema",
                    severity="Informativa",
                    source="Entorno AIP",
                    timestamp=valuation_date,
                )
            )

        macro_scenario = "No disponible"
        macro_horizon = "-"
        try:
            macro_service = self._demo_factory.container.resolve(ConfiguredMacroIntelligenceService)
            macro = macro_service.get_projection()
            if str(macro.get("status") or "").upper() == "AVAILABLE":
                macro_scenario = (
                    f"{macro.get('scenario_type', '-')} · v{macro.get('version', '-')} · "
                    f"{self._translate_status(macro.get('scenario_status'))}"
                )
                macro_horizon = f"{int(macro.get('horizon') or 0)} meses"
            else:
                macro_scenario = self._translate_status(macro.get("status") or "No disponible")
        except Exception:
            pass

        summary = (
            f"Portafolio: {self._format_crc_mm(portfolio.get('market_value'))}",
            f"TIR: {self._decimal(portfolio.get('weighted_yield')):.2f}%",
            f"HQLA: {self._decimal(portfolio.get('hqla_percent')):.1f}%",
            f"ICL Total: {self._decimal(liquidity.get('icl_total')):.2f}",
            f"Valor relativo de mercado: {int(market.get('market_relative_value_count') or 0)} títulos",
            f"Escenario macroeconómico: {macro_scenario}",
        )
        portfolio_view = (
            f"Valor de mercado: {self._format_crc_mm(portfolio.get('market_value'))}",
            f"Valor en libros: {self._format_crc_mm(portfolio.get('book_value'))}",
            f"TIR ponderada: {self._decimal(portfolio.get('weighted_yield')):.2f}%",
            f"Duración modificada: {self._decimal(portfolio.get('modified_duration')):.2f}",
            f"HQLA: {self._decimal(portfolio.get('hqla_percent')):.1f}%",
            f"MIL: {self._decimal(portfolio.get('mil_eligible_percent')):.1f}%",
        )
        liquidity_view = (
            f"Posición de caja: {self._format_crc_mm(liquidity.get('cash_position'))}",
            f"Brecha: {self._format_crc_mm(liquidity.get('liquidity_gap'))}",
            f"HQLA: {self._format_crc_mm(liquidity.get('hqla_capacity'))}",
            f"MIL: {self._format_crc_mm(liquidity.get('mil_eligible_capacity'))}",
            f"ICL Total: {self._decimal(liquidity.get('icl_total')):.2f}",
            f"Estrés: {self._translate_status(liquidity.get('stress_result') or 'No configurado')}",
        )
        market_view = (
            f"Curvas: {len(market.get('curves', ()) or ())}",
            f"Valor relativo en portafolio: {int(market.get('relative_value_opportunities') or 0)}",
            f"Valor relativo de mercado: {int(market.get('market_relative_value_count') or 0)}",
            f"Fuera de portafolio: {int(market.get('market_outside_portfolio_count') or 0)}",
            f"Rotaciones: {int(market.get('portfolio_rotation_candidate_count') or 0)}",
            f"Estado: {self._translate_status(market.get('market_status') or 'N/D')}",
        )

        return ExecutiveViewModel(
            title="PANEL EJECUTIVO",
            subtitle="Portafolio · Liquidez · Mercado · Inteligencia Macroeconómica",
            summary=summary,
            portfolio=portfolio_view,
            liquidity=liquidity_view,
            market=market_view,
            recommendations=recommendations,
            alerts=tuple(alerts),
            trends=(),
            filters=filters or {},
            theme_name=theme,
            status="loaded" if not error else "error",
            loading=loading,
            error=error,
            valuation_date=valuation_date,
            portfolio_market_value=self._format_crc_mm(portfolio.get("market_value")),
            weighted_yield=f"{self._decimal(portfolio.get('weighted_yield')):.2f}%",
            modified_duration=f"{self._decimal(portfolio.get('modified_duration')):.2f}",
            hqla_percent=f"{self._decimal(portfolio.get('hqla_percent')):.1f}%",
            mil_percent=f"{self._decimal(portfolio.get('mil_eligible_percent')):.1f}%",
            liquidity_gap=self._format_crc_mm(liquidity.get("liquidity_gap")),
            icl_total=f"{self._decimal(liquidity.get('icl_total')):.2f}",
            relative_value_count=int(market.get("market_relative_value_count") or 0),
            rotation_candidate_count=int(market.get("portfolio_rotation_candidate_count") or 0),
            macro_scenario=macro_scenario,
            macro_horizon=macro_horizon,
            data_quality_status=str(portfolio.get("data_quality_status") or "N/D"),
        )

    def refresh(
        self, *, theme: str = "light", filters: dict[str, str] | None = None
    ) -> ExecutiveViewModel:
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
