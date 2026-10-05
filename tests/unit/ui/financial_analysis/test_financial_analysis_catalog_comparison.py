from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCore import Qt

from aip.domain.financial_analysis.models import (
    FinancialAccountCatalogEntry,
    FinancialAnalysisSnapshot,
    FinancialEntity,
    FinancialMetricHistoryPoint,
    FinancialMetricHistorySeries,
    FinancialStatementLine,
    FinancialStatementType,
)
from aip.ui.modules.financial_analysis.presenters.financial_analysis_presenter import (
    FinancialAnalysisPresenter,
)
from aip.ui.modules.financial_analysis.viewmodels.financial_analysis_view_model import (
    FinancialAnalysisViewModel,
    FinancialMetricHistoryPointView,
    FinancialMetricHistorySeriesView,
)
from aip.ui.modules.financial_analysis.views.financial_entity_comparison_panel import (
    FinancialEntityComparisonPanel,
)


def test_presenter_keeps_full_catalog_and_marks_missing_balance_as_nd() -> None:
    entity = FinancialEntity("E1", "Entidad Uno")
    snapshot = FinancialAnalysisSnapshot(
        status="AVAILABLE",
        cutoff_date=date(2026, 9, 30),
        selected_entity=entity,
        entities=(entity,),
        available_dates=(date(2026, 9, 30),),
        statement_lines=(
            FinancialStatementLine(
                entity=entity,
                statement_date=date(2026, 9, 30),
                statement_type=FinancialStatementType.BALANCE_SHEET,
                account_code="10000",
                account_name="ACTIVO TOTAL",
                amount=Decimal("100000000"),
            ),
        ),
        account_catalog=(
            FinancialAccountCatalogEntry(
                account_code="10000",
                catalog_type_code="14",
                catalog_type_name="CATALOGO",
                parent_account_code=None,
                account_name="ACTIVO TOTAL",
                level=Decimal("1"),
                sign=1,
            ),
            FinancialAccountCatalogEntry(
                account_code="11101",
                catalog_type_code="14",
                catalog_type_name="CATALOGO",
                parent_account_code="11000",
                account_name="CARTERA DE CREDITO",
                level=Decimal("3"),
                sign=1,
            ),
        ),
    )

    view_model = FinancialAnalysisPresenter._from_snapshot(snapshot)

    assert len(view_model.account_catalog_rows) == 2
    balances = {row.account_code: row for row in view_model.account_catalog_rows}
    assert balances["10000"].balance == "₡100.00 MM"
    assert balances["10000"].balance_status == "Disponible"
    assert balances["11101"].balance == "N/D"
    assert balances["11101"].balance_status == "Sin saldo publicado"


class _ComparisonService:
    def __init__(self) -> None:
        self.entities = {
            "E1": FinancialEntity("E1", "Entidad Uno"),
            "E2": FinancialEntity("E2", "Entidad Dos"),
        }

    def load(self, *, selected_entity_id: str | None = None, **_kwargs) -> FinancialAnalysisSnapshot:
        assert selected_entity_id is not None
        entity = self.entities[selected_entity_id]
        offset = Decimal("0") if selected_entity_id == "E1" else Decimal("10")
        return FinancialAnalysisSnapshot(
            status="AVAILABLE",
            cutoff_date=date(2026, 9, 30),
            selected_entity=entity,
            entities=tuple(self.entities.values()),
            available_dates=(date(2026, 9, 30),),
            metric_history=(
                FinancialMetricHistorySeries(
                    code="ROA",
                    label="ROA",
                    unit="PERCENT",
                    source_account="ROA",
                    points=(
                        FinancialMetricHistoryPoint(date(2026, 8, 31), Decimal("1.00") + offset),
                        FinancialMetricHistoryPoint(date(2026, 9, 30), Decimal("1.10") + offset),
                    ),
                ),
            ),
        )


class _Container:
    def __init__(self, service: _ComparisonService) -> None:
        self._service = service

    def resolve(self, _type):
        return self._service


class _Factory:
    def __init__(self, service: _ComparisonService) -> None:
        self.container = _Container(service)


def test_presenter_builds_same_series_for_two_entities() -> None:
    presenter = FinancialAnalysisPresenter(
        application_factory=_Factory(_ComparisonService())  # type: ignore[arg-type]
    )

    comparison = presenter.build_comparison_view_model(
        entity_ids=("E1", "E2"),
        series_code="ROA",
    )

    assert comparison.label == "ROA"
    assert comparison.unit == "%"
    assert [item.entity_name for item in comparison.entities] == ["Entidad Uno", "Entidad Dos"]
    assert comparison.entities[0].points[-1].value == 1.1
    assert comparison.entities[1].points[-1].value == 11.1


def test_presenter_rejects_more_than_five_entities_without_querying_service() -> None:
    presenter = FinancialAnalysisPresenter(
        application_factory=_Factory(_ComparisonService())  # type: ignore[arg-type]
    )

    comparison = presenter.build_comparison_view_model(
        entity_ids=("1", "2", "3", "4", "5", "6"),
        series_code="ROA",
    )

    assert comparison.entities == ()
    assert comparison.diagnostics == ("El comparativo admite un máximo de 5 entidades.",)


def test_comparison_panel_enforces_five_checked_entities(qt_app) -> None:
    entities = tuple((f"E{index}", f"Entidad {index}") for index in range(1, 7))
    history = FinancialMetricHistorySeriesView(
        code="ROA",
        label="ROA",
        unit="%",
        latest_value="1.00%",
        period_change="Sin comparación en la ventana",
        source_account="ROA",
        available_points=1,
        total_points=1,
        points=(
            FinancialMetricHistoryPointView(
                iso_date="2026-09-30",
                date_label="09/2026",
                value=1.0,
                display_value="1.00%",
            ),
        ),
    )
    panel = FinancialEntityComparisonPanel()
    panel.bind_context(
        FinancialAnalysisViewModel(
            selected_entity_id="E1",
            entities=entities,
            metric_history=(history,),
        )
    )

    for index in range(1, 6):
        panel._entity_list.item(index).setCheckState(Qt.CheckState.Checked)

    assert len(panel.selected_entity_ids()) == 5
    assert panel._entity_list.item(5).checkState() == Qt.CheckState.Unchecked
    assert panel._selection_summary.text() == "5/5 entidades"
