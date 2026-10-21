from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidgetItem

from aip.domain.financial_analysis.models import (
    FinancialAnalysisSnapshot,
    MatrixReferenceBreakdown,
    MatrixReferencePeer,
    RatingLevel,
)
from aip.ui.modules.financial_analysis.presenters.financial_analysis_presenter import (
    FinancialAnalysisPresenter,
)
from aip.ui.modules.financial_analysis.viewmodels.financial_analysis_view_model import (
    FinancialAnalysisViewModel,
    RatingMatrixComparisonRow,
)
from aip.ui.modules.financial_analysis.views.financial_analysis_view import (
    FinancialAnalysisView,
)
from aip.ui.shell.main_window import MainWindow
from aip.ui.widgets.table_csv_export import export_table_csv


class _Presenter:
    def build_view_model(self, **_kwargs) -> FinancialAnalysisViewModel:
        return FinancialAnalysisViewModel()


def test_main_window_opens_financial_analysis_workspace(qt_app) -> None:
    window = MainWindow()
    try:
        window.open_workspace("financial_analysis")
        titles = [window.workspace.tabText(index) for index in range(window.workspace.count())]
        assert "Análisis Financiero" in titles
    finally:
        window.close()
        qt_app.processEvents()


def test_financial_analysis_is_available_in_ribbon_and_sidebar(qt_app) -> None:
    window = MainWindow()
    try:
        assert window._ribbon.action("Análisis Financiero").text() == "Análisis Financiero"
        labels = [
            window._sidebar._tree.item(index).text()
            for index in range(window._sidebar._tree.count())
        ]
        assert "Análisis Financiero" in labels
    finally:
        window.close()
        qt_app.processEvents()


def test_financial_analysis_exposes_methodology_rating_tab(qt_app) -> None:
    view = FinancialAnalysisView(presenter=_Presenter())  # type: ignore[arg-type]
    titles = [view._tabs.tabText(index) for index in range(view._tabs.count())]
    rating_titles = [
        view._rating_content_tabs.tabText(index)
        for index in range(view._rating_content_tabs.count())
    ]

    assert "Calificación" in titles
    assert rating_titles == [
        "Ranking de entidades",
        "Indicadores y dimensiones",
        "Reconciliación",
        "Auditoría del puntaje",
        "Cohorte metodológica",
    ]
    assert view._rating_heading.text() == "Calificación interna 08ME14-01 · datos SUGEF"
    assert view._rating_methodology.text() == "Metodología: 08ME14-01"
    assert view._rating_grade.text() == "Sin emitir"
    assert view._rating_indicator_table.isColumnHidden(10)
    assert view._peer_rating_table.columnCount() == 8
    assert view._peer_rating_table.horizontalHeaderItem(1).text() == "Entidad"
    assert (
        view._rating_dimension_table.horizontalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert "Calificación oficial" not in view._rating_heading.text()
    assert view._cutoff.text().startswith("Corte SUGEF:")
    assert "corte general de AIP" in view._cutoff.toolTip()
    assert "No es una calificación de riesgo emitida por SUGEF" in (
        view._rating_methodology.toolTip()
    )
    view.close()
    qt_app.processEvents()


def test_presenter_does_not_show_requested_date_as_sugef_cutoff_without_data() -> None:
    snapshot = FinancialAnalysisSnapshot(
        status="UNAVAILABLE",
        cutoff_date=date(2026, 8, 31),
        selected_entity=None,
    )

    view_model = FinancialAnalysisPresenter._from_snapshot(snapshot)

    assert view_model.cutoff_date == "No disponible"


def test_financial_kpis_reflow_without_losing_sugef_values(qt_app) -> None:
    view = FinancialAnalysisView(presenter=_Presenter())  # type: ignore[arg-type]
    try:
        grid = view._kpi_grid
        assert grid is not None
        cards = view._kpi_cards
        assert len(cards) == 7
        tracked = view._kpi_values["ROA"]
        tracked.setText("1.23%")

        for width, columns in ((1400, 7), (960, 4), (650, 2), (1400, 7)):
            view._arrange_kpi_cards(width)
            assert view._kpi_columns == columns
            for index, card in enumerate(cards):
                item = grid.itemAtPosition(index // columns, index % columns)
                assert item is not None
                assert item.widget() is card
            assert view._kpi_values["ROA"] is tracked
            assert tracked.text() == "1.23%"
    finally:
        view.close()
        qt_app.processEvents()


def test_financial_controls_reflow_without_losing_entity_selection(qt_app) -> None:
    view = FinancialAnalysisView(presenter=_Presenter())  # type: ignore[arg-type]
    try:
        grid = view._controls_grid
        widgets = view._controls_widgets
        assert grid is not None
        assert len(widgets) == 4
        assert widgets[0].buddy() is view._entity_selector
        view._building_entity_selector = True
        view._entity_selector.addItem("Entidad financiera de denominación extensa", "E001")
        view._entity_selector.setCurrentIndex(0)
        view._building_entity_selector = False
        view._cutoff.setText("Corte SUGEF: 31/08/2026")

        for width, columns in ((1400, 4), (760, 2), (1400, 4)):
            view._arrange_controls(width)
            assert view._controls_columns == columns
            for index, widget in enumerate(widgets):
                cell = grid.itemAtPosition(index // columns, index % columns)
                assert cell is not None
                assert cell.widget() is widget
            assert view._entity_selector.currentData() == "E001"
            assert view._cutoff.text() == "Corte SUGEF: 31/08/2026"
        assert view._cutoff.wordWrap()
        assert view._entity_selector.accessibleName() == "Entidad financiera supervisada"
        assert view._subtitle.wordWrap()
    finally:
        view.close()
        qt_app.processEvents()


def test_financial_entity_selector_full_name_tooltips(qt_app) -> None:
    view = FinancialAnalysisView(presenter=_Presenter())  # type: ignore[arg-type]
    try:
        name = "Cooperativa de Ahorro y Crédito con Denominación Institucional Larga"
        model = FinancialAnalysisViewModel(
            entities=(("E001", name),),
            selected_entity_id="E001",
        )
        view._bind_entities(model)
        assert view._entity_selector.itemData(0, Qt.ItemDataRole.ToolTipRole) == name
        assert view._entity_selector.toolTip() == name
    finally:
        view.close()
        qt_app.processEvents()


def test_financial_source_footer_reflows_without_losing_trace_or_action(qt_app) -> None:
    view = FinancialAnalysisView(presenter=_Presenter())  # type: ignore[arg-type]
    try:
        grid = view._source_grid
        assert grid is not None
        trace = "SUGEF · datos oficiales · 31/08/2026 · fuente y procedencia"
        view._source_status.setText(trace)
        for width, compact in ((1400, False), (680, True), (1400, False)):
            view._arrange_source(width)
            assert view._source_compact is compact
            source_cell = grid.itemAtPosition(0, 0)
            link_cell = grid.itemAtPosition(1 if compact else 0, 0 if compact else 1)
            assert source_cell is not None
            assert link_cell is not None
            assert source_cell.widget() is view._source_status
            assert link_cell.widget() is view._source_link
            assert view._source_status.text() == trace
            assert view._source_link.text() == "Abrir fuente oficial"
        assert view._source_status.wordWrap()
    finally:
        view.close()
        qt_app.processEvents()


def test_financial_tabs_keep_navigation_accessible_on_narrow_windows(qt_app) -> None:
    view = FinancialAnalysisView(presenter=_Presenter())  # type: ignore[arg-type]
    try:
        bar = view._tabs.tabBar()
        assert bar.usesScrollButtons()
        assert view._tabs.elideMode() == Qt.TextElideMode.ElideRight
        original = view._tabs.tabText(5)
        view.resize(590, 480)
        view._tabs.setCurrentIndex(5)
        assert view._tabs.currentIndex() == 5
        assert view._tabs.tabText(5) == original
        assert view._tabs.tabToolTip(5) == original
        for index in range(view._tabs.count()):
            assert view._tabs.tabToolTip(index) == view._tabs.tabText(index)
    finally:
        view.close()
        qt_app.processEvents()


def test_sugef_statement_search_and_filter_are_accessible(qt_app) -> None:
    view = FinancialAnalysisView(presenter=_Presenter())  # type: ignore[arg-type]
    try:
        assert view._statement_search.accessibleName() == "Buscar cuentas e indicadores SUGEF"
        assert view._statement_search.isClearButtonEnabled()
        assert view._statement_type_filter.accessibleName() == ("Filtrar tipo de estado financiero")
        labels = view._statement_type_filter
        for index in range(labels.count()):
            assert labels.itemData(index, Qt.ItemDataRole.ToolTipRole) == labels.itemText(index)
        view._statement_search.setText("activo")
        view._statement_search.clear()
        assert view._statement_search.text() == ""
    finally:
        view.close()
        qt_app.processEvents()


def test_sugef_source_trace_is_copyable_for_audit(qt_app) -> None:
    view = FinancialAnalysisView(presenter=_Presenter())  # type: ignore[arg-type]
    try:
        flags = view._source_status.textInteractionFlags()
        assert flags & Qt.TextInteractionFlag.TextSelectableByMouse
        assert flags & Qt.TextInteractionFlag.TextSelectableByKeyboard
    finally:
        view.close()
        qt_app.processEvents()


def test_sugef_statement_toolbar_reflows_without_losing_search_or_filter(qt_app) -> None:
    view = FinancialAnalysisView(presenter=_Presenter())  # type: ignore[arg-type]
    try:
        grid = view._statement_controls_grid
        assert grid is not None
        view._statement_search.setText("activos")
        view._statement_type_filter.setCurrentIndex(1)
        view._statement_count.setText("25 registros")

        view._arrange_statement_controls(720)
        assert view._statement_controls_compact
        assert grid.itemAtPosition(0, 0).widget() is view._statement_search
        assert grid.itemAtPosition(0, 2).widget() is view._statement_search
        assert grid.itemAtPosition(1, 1).widget() is view._statement_type_filter
        assert grid.itemAtPosition(1, 2).widget() is view._statement_count

        view._arrange_statement_controls(1400)
        assert not view._statement_controls_compact
        for index, widget in enumerate(view._statement_controls):
            assert grid.itemAtPosition(0, index).widget() is widget
        assert view._statement_search.text() == "activos"
        assert view._statement_type_filter.currentIndex() == 1
        assert view._statement_count.text() == "25 registros"
    finally:
        view.close()
        qt_app.processEvents()


def test_nested_sugef_and_rating_tabs_support_compact_navigation(qt_app) -> None:
    view = FinancialAnalysisView(presenter=_Presenter())  # type: ignore[arg-type]
    try:
        for tabs in (view._statement_content_tabs, view._rating_content_tabs):
            assert tabs.tabBar().usesScrollButtons()
            assert tabs.elideMode() == Qt.TextElideMode.ElideRight
            last = tabs.count() - 1
            title = tabs.tabText(last)
            tabs.setCurrentIndex(last)
            assert tabs.currentIndex() == last
            assert tabs.tabText(last) == title
    finally:
        view.close()
        qt_app.processEvents()


def test_sugef_export_button_tracks_responsive_toolbar(qt_app) -> None:
    view = FinancialAnalysisView(presenter=_Presenter())  # type: ignore[arg-type]
    try:
        grid = view._statement_controls_grid
        assert grid is not None
        assert view._export_statement_button.text() == "Exportar CSV"
        view._arrange_statement_controls(720)
        assert grid.itemAtPosition(2, 0).widget() is view._export_statement_button
        view._arrange_statement_controls(1400)
        assert grid.itemAtPosition(0, 4).widget() is view._export_statement_button
    finally:
        view.close()
        qt_app.processEvents()


def test_sugef_csv_exports_filtered_rows_and_audit_columns(qt_app, tmp_path) -> None:
    view = FinancialAnalysisView(presenter=_Presenter())  # type: ignore[arg-type]
    try:
        table = view._statement_table
        table.setRowCount(2)
        entries = (
            ("Balance de situación", "110", "Activos", "1,200.50", "CRC", "SUGEF 2026-08"),
            ("Estado de resultados", "410", "Ingresos", "150.75", "CRC", "SUGEF 2026-08"),
        )
        for row, values in enumerate(entries):
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(value))
        view._statement_search.setText("Activos")
        path = tmp_path / "sugef-estados.csv"
        count = export_table_csv(table, path, visible_rows_only=True)
        assert count == 1
        import csv

        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream, delimiter=";"))
        assert rows[0] == [
            "Estado",
            "Cuenta",
            "Descripción",
            "Valor",
            "Moneda",
            "Trazabilidad",
        ]
        assert rows[1] == list(entries[0])
        assert len(rows) == 2
    finally:
        view.close()
        qt_app.processEvents()


def test_sugef_cutoff_lag_is_visible_and_reset_when_new_data_arrives(qt_app) -> None:
    view = FinancialAnalysisView(presenter=_Presenter())  # type: ignore[arg-type]
    try:
        view.bind_view_model(
            FinancialAnalysisViewModel(
                cutoff_date="31/08/2026",
                diagnostics=(
                    "Corte solicitado en AIP: 12/10/2026; "
                    "último corte contable SUGEF completo utilizable: 31/08/2026.",
                ),
            )
        )
        assert not view._cutoff_notice.isHidden()
        assert "31/08/2026" in view._cutoff_notice.text()
        assert "Actualizar fuente" in view._cutoff_notice.text()
        view.bind_view_model(
            FinancialAnalysisViewModel(
                cutoff_date="30/09/2026",
                status="LOADED",
                entities=(("3004045138", "COOPEALIANZA"),),
            )
        )
        assert view._cutoff_notice.isHidden()
        assert view._cutoff_notice.text() == ""
        assert view._cutoff.text() == "Corte SUGEF: 30/09/2026"
    finally:
        view.close()
        qt_app.processEvents()


def test_missing_official_sugef_data_has_explicit_non_demo_warning(qt_app) -> None:
    view = FinancialAnalysisView(presenter=_Presenter())  # type: ignore[arg-type]
    try:
        view.bind_view_model(FinancialAnalysisViewModel(status="UNAVAILABLE", cutoff_date="-"))
        assert "no se recibieron entidades" in view._cutoff_notice.text()
        assert "Calidad y trazabilidad" in view._cutoff_notice.text()
        assert not view._cutoff_notice.isHidden()
    finally:
        view.close()
        qt_app.processEvents()


def test_financial_matrix_comparison_shows_all_audit_columns(qt_app) -> None:
    view = FinancialAnalysisView(presenter=_Presenter())  # type: ignore[arg-type]
    try:
        row = RatingMatrixComparisonRow(
            indicator="ROA",
            value="1.20%",
            aip_p15="-0.20%",
            matrix_p15="0.00%",
            aip_p85="3.00%",
            matrix_p85="3.00%",
            matrix_weight="6.670%",
            aip_points="3.3333",
            matrix_points="5.0025",
            delta_points="+1.6692",
            matrix_origin="DATOS_SUGEF",
        )
        model = FinancialAnalysisViewModel(
            score_matrix_summary="Puntaje provisional 66.8825; categoría suspendida",
            score_matrix_notes="Falta cohorte",
            score_matrix_rows=(row,),
        )
        view.bind_view_model(model)
        table = view._matrix_comparison_table
        assert table.rowCount() == 1
        assert table.columnCount() == 11
        assert table.item(0, 0).text() == "ROA"
        assert table.item(0, 3).text() == "0.00%"
        assert table.item(0, 8).text() == "5.0025"
        assert table.item(0, 9).text() == "+1.6692"
        assert "categoría suspendida" in view._score_matrix_summary.text()
        assert "Falta cohorte" in view._score_matrix_summary.toolTip()
    finally:
        view.close()
        qt_app.processEvents()


def test_matrix_breakdown_is_projected_to_user_without_inventing_a_grade() -> None:
    reference = MatrixReferenceBreakdown(
        code="ROA",
        value=Decimal("0.012"),
        p15=Decimal("0"),
        midpoint=Decimal("0.015"),
        p85=Decimal("0.030"),
        weight=Decimal("6.67"),
        contribution=Decimal("5.0025"),
        level=RatingLevel.SATISFACTORY,
        origin="DATOS_SUGEF",
    )
    snapshot = FinancialAnalysisSnapshot(
        status="PARTIAL",
        cutoff_date=date(2026, 8, 31),
        selected_entity=None,
        reference_matrix_score=Decimal("66.8825"),
        reference_matrix_grade=None,
        reference_matrix_coverage="37/38 · Estado: COHORTE_INCOMPLETA",
        reference_matrix_indicators=(reference,),
    )
    vm = FinancialAnalysisPresenter._from_snapshot(snapshot)
    assert len(vm.score_matrix_rows) == 1
    assert vm.score_matrix_rows[0].indicator == "ROA"
    assert vm.score_matrix_rows[0].matrix_points == "5.0025"
    assert vm.score_matrix_rows[0].aip_points == "-"
    assert vm.score_matrix_rows[0].delta_points == "-"
    assert "Puntaje provisional" in vm.score_matrix_summary
    assert "categoría suspendida" in vm.score_matrix_summary


def test_matrix_cohort_tab_reports_per_entity_missing_sugef_inputs(qt_app) -> None:
    snapshot = FinancialAnalysisSnapshot(
        status="PARTIAL",
        cutoff_date=date(2026, 9, 30),
        selected_entity=None,
        reference_matrix_coverage="2/38 entidades · Estado: COHORTE_INCOMPLETA",
        reference_matrix_peers=(
            MatrixReferencePeer(
                entity_id="101",
                entity_name="COOPENAE",
                score=Decimal("60.833"),
                grade=None,
                missing_indicators=(),
                status="COMPLETE",
            ),
            MatrixReferencePeer(
                entity_id="102",
                entity_name="BANCO X",
                score=None,
                grade=None,
                missing_indicators=("ROA", "LIQUIDITY_COVERAGE"),
                status="INCOMPLETE",
            ),
        ),
    )
    vm = FinancialAnalysisPresenter._from_snapshot(snapshot)
    assert len(vm.score_matrix_peer_rows) == 2
    assert vm.score_matrix_peer_rows[0].grade == "Suspendida"
    assert vm.score_matrix_peer_rows[1].missing == "ROA, LIQUIDITY_COVERAGE"
    view = FinancialAnalysisView(presenter=_Presenter())  # type: ignore[arg-type]
    try:
        view.bind_view_model(vm)
        table = view._matrix_cohort_table
        assert table.rowCount() == 2
        assert table.columnCount() == 6
        assert table.item(0, 4).text() == "Suspendida"
        assert table.item(1, 5).text() == "ROA, LIQUIDITY_COVERAGE"
        assert "Pares identificados: 2" in view._matrix_cohort_summary.text()
    finally:
        view.close()
        qt_app.processEvents()
