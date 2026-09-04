from __future__ import annotations

from decimal import Decimal

from aip.product.configured.services.configured_financial_analysis_service import (
    ConfiguredFinancialAnalysisService,
    FinancialAnalysisApplicationSnapshot,
)
from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.ui.modules.financial_analysis.viewmodels.financial_analysis_view_model import (
    FinancialAnalysisViewModel,
    FinancialMetricView,
    FinancialStatementRow,
    PeerSummaryRow,
    RatingDimensionRow,
    RatingIndicatorRow,
)


class FinancialAnalysisPresenter:
    """Adapta el caso de uso SUGEF sin ejecutar cálculos financieros en la UI."""

    def __init__(self, application_factory: DemoApplicationFactory | None = None) -> None:
        self._factory = application_factory or DemoApplicationFactory()

    def build_view_model(
        self,
        *,
        selected_entity_id: str | None = None,
        force_refresh: bool = False,
    ) -> FinancialAnalysisViewModel:
        try:
            service = self._factory.container.resolve(ConfiguredFinancialAnalysisService)
            snapshot = service.load(
                selected_entity_id=selected_entity_id,
                force_refresh=force_refresh,
            )
        except Exception as exc:
            return FinancialAnalysisViewModel(
                diagnostics=(f"Módulo SUGEF no disponible: {type(exc).__name__}: {exc}",)
            )
        return self._from_snapshot(snapshot)

    @classmethod
    def _from_snapshot(
        cls, snapshot: FinancialAnalysisApplicationSnapshot
    ) -> FinancialAnalysisViewModel:
        metrics = tuple(
            FinancialMetricView(
                code=item.code,
                label=item.label,
                value=cls._metric_value(item.value, item.unit),
                change=cls._change(item.change_percent),
                source_account=item.source_account or "Cuenta no identificada",
            )
            for item in snapshot.metrics
        )
        statements = tuple(
            FinancialStatementRow(
                statement=cls._statement_label(item.statement_type.value),
                account_code=item.account_code,
                account_name=item.account_name,
                amount=cls._statement_value(
                    item.amount,
                    item.statement_type.value,
                    item.account_code,
                ),
                currency=item.currency,
                trace=(
                    f"{item.trace.file_path} · {item.trace.sheet_name} · fila {item.trace.row_number}"
                    if item.trace is not None
                    else "-"
                ),
            )
            for item in snapshot.statement_lines
        )
        peers = tuple(
            PeerSummaryRow(
                entity_id=item.entity.entity_id,
                entity_name=item.entity.name,
                category=item.entity.category,
                assets=cls._money(item.assets),
                loans=cls._money(item.loans),
                equity=cls._money(item.equity),
                net_income=cls._money(item.net_income),
                roa=cls._percent(item.roa_percent),
                roe=cls._percent(item.roe_percent),
            )
            for item in snapshot.peer_summaries
        )
        rating = snapshot.rating
        rating_dimensions = (
            tuple(
                RatingDimensionRow(
                    name=item.name,
                    score=f"{item.score:,.3f}",
                    weight=f"{item.weight_percent:,.2f}%",
                    coverage=f"{item.available_indicators}/{item.total_indicators}",
                )
                for item in rating.dimensions
            )
            if rating is not None
            else ()
        )
        rating_indicators = (
            tuple(
                RatingIndicatorRow(
                    indicator=item.label,
                    dimension=item.dimension,
                    value=cls._rating_value(item.value, item.direction.value),
                    peer_count=(
                        "N/A" if item.direction.value == "BINARY" else str(item.peer_count)
                    ),
                    percentile_15=cls._rating_value(item.percentile_15, item.direction.value),
                    midpoint=cls._rating_value(item.midpoint, item.direction.value),
                    percentile_85=cls._rating_value(item.percentile_85, item.direction.value),
                    direction=cls._direction_label(item.direction.value),
                    level=cls._level_label(item.level.value),
                    contribution=(
                        f"{item.contribution:,.3f}" if item.contribution is not None else "-"
                    ),
                    source_account=item.source_account or "Cuenta no identificada",
                )
                for item in rating.indicators
            )
            if rating is not None
            else ()
        )
        selected = snapshot.selected_entity
        source_cutoff = (
            snapshot.cutoff_date.strftime("%d/%m/%Y")
            if snapshot.cutoff_date is not None and snapshot.available_dates
            else "No disponible"
        )
        return FinancialAnalysisViewModel(
            status=snapshot.status,
            cutoff_date=source_cutoff,
            selected_entity_id=selected.entity_id if selected else "",
            selected_entity_name=selected.name if selected else "Sin datos",
            entities=tuple((item.entity_id, item.name) for item in snapshot.entities),
            metrics=metrics,
            statement_rows=statements,
            peer_rows=peers,
            rating_status=rating.status if rating is not None else "INCOMPLETE",
            rating_score=(f"{rating.score:,.3f}" if rating and rating.score is not None else "-"),
            rating_grade=rating.grade if rating and rating.grade else "Sin emitir",
            rating_coverage=(f"{rating.coverage_percent:,.2f}%" if rating is not None else "0.00%"),
            rating_methodology=(
                f"{rating.methodology_code} · {rating.methodology_version}"
                if rating is not None
                else "08ME14-01"
            ),
            rating_dimensions=rating_dimensions,
            rating_indicators=rating_indicators,
            rating_diagnostics=rating.diagnostics if rating is not None else (),
            diagnostics=snapshot.diagnostics,
            source_name=snapshot.source_name,
            source_url=snapshot.source_url,
            source_file_count=len(snapshot.source_files),
        )

    @staticmethod
    def _money(value: Decimal | None) -> str:
        if value is None:
            return "-"
        return f"₡{value / Decimal('1000000'):,.2f} MM"

    @classmethod
    def _statement_value(cls, value: Decimal, statement_type: str, account_code: str) -> str:
        if statement_type != "INDICATORS":
            return cls._money(value)
        if account_code in {"PROPORTIONAL_SUPERVISION", "EQUITY_COMMITMENT"}:
            return "Sí" if value == Decimal("1") else "No"
        return f"{value * Decimal('100'):,.3f}%"

    @staticmethod
    def _percent(value: Decimal | None) -> str:
        return "-" if value is None else f"{value:,.2f}%"

    @classmethod
    def _metric_value(cls, value: Decimal | None, unit: str) -> str:
        return cls._percent(value) if unit == "PERCENT" else cls._money(value)

    @staticmethod
    def _change(value: Decimal | None) -> str:
        if value is None:
            return "Sin período comparable"
        sign = "+" if value > 0 else ""
        return f"{sign}{value:,.2f}% vs. período anterior"

    @staticmethod
    def _statement_label(value: str) -> str:
        return {
            "BALANCE_SHEET": "Balance de situación",
            "INCOME_STATEMENT": "Estado de resultados",
            "INDICATORS": "Indicadores financieros",
            "TRIAL_BALANCE": "Balanza de comprobación",
            "UNKNOWN": "Estado financiero",
        }.get(value, value)

    @staticmethod
    def _rating_value(value: Decimal | None, direction: str) -> str:
        if value is None:
            return "-"
        if direction == "BINARY":
            return "Sí (1)" if value == Decimal("1") else "No (0)"
        return f"{value * Decimal('100'):,.3f}%"

    @staticmethod
    def _direction_label(value: str) -> str:
        return {
            "HIGHER_IS_BETTER": "Mayor es mejor",
            "LOWER_IS_BETTER": "Menor es mejor",
            "BINARY": "Binario 1/0",
        }.get(value, value)

    @staticmethod
    def _level_label(value: str) -> str:
        return {
            "OUTSTANDING": "Sobresaliente",
            "SATISFACTORY": "Satisfactorio",
            "IMPROVABLE": "Mejorable",
            "CRITICAL": "Crítico",
            "UNAVAILABLE": "Sin datos",
        }.get(value, value)
