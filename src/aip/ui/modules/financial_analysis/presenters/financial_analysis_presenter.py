from __future__ import annotations

from decimal import Decimal

from aip.domain.financial_analysis.models import FinancialAnalysisSnapshot
from aip.product.configured.services.configured_financial_analysis_service import (
    ConfiguredFinancialAnalysisService,
)
from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.ui.modules.financial_analysis.viewmodels.financial_analysis_view_model import (
    FinancialAnalysisViewModel,
    FinancialMetricView,
    FinancialStatementRow,
    PeerSummaryRow,
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
    def _from_snapshot(cls, snapshot: FinancialAnalysisSnapshot) -> FinancialAnalysisViewModel:
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
                amount=cls._money(item.amount),
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
        selected = snapshot.selected_entity
        return FinancialAnalysisViewModel(
            status=snapshot.status,
            cutoff_date=snapshot.cutoff_date.strftime("%d/%m/%Y") if snapshot.cutoff_date else "-",
            selected_entity_id=selected.entity_id if selected else "",
            selected_entity_name=selected.name if selected else "Sin datos",
            entities=tuple((item.entity_id, item.name) for item in snapshot.entities),
            metrics=metrics,
            statement_rows=statements,
            peer_rows=peers,
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
