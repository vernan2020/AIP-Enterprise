"""Executive cockpit visual and data-integrity contracts."""

from __future__ import annotations

from PySide6.QtCore import Qt

from aip.ui.modules.executive.models.executive_row import ExecutiveRow
from aip.ui.modules.executive.viewmodels.executive_view_model import ExecutiveViewModel
from aip.ui.modules.executive.views.executive_workspace import ExecutiveWorkspace
from aip.ui.modules.executive.widgets.executive_signal_radar import ExecutiveSignalRadar


def test_executive_radar_counts_source_rows_without_synthetic_metrics(qt_app) -> None:
    radar = ExecutiveSignalRadar()
    try:
        alerts = (
            ExecutiveRow("ICL", "Bajo revisión", severity="High"),
            ExecutiveRow("Otro", "Informativo", severity="Informativa"),
        )
        recommendations = (ExecutiveRow("Valor relativo", "Revisar spreads"),)
        radar.set_rows(alerts, recommendations)
        assert radar._counts["alerts"].text() == "2"
        assert radar._counts["high"].text() == "1"
        assert radar._counts["recommendations"].text() == "1"
        assert radar._bars["alerts"].maximum() == 2
        assert "no magnitudes financieras" in radar.toolTip()
    finally:
        radar.close()


def test_executive_reflows_all_regions_without_changing_financial_kpis(qt_app) -> None:
    view = ExecutiveWorkspace()
    try:
        model = ExecutiveViewModel(
            valuation_date="12/10/2026",
            portfolio_market_value="₡228,899.18 MM",
            icl_total="9.79",
            alerts=(ExecutiveRow("ALCO", "Alerta", severity="Critical"),),
        )
        view.bind_view_model(model)
        for width, counts in (
            (1500, (6, 5, 2)),
            (1050, (3, 3, 2)),
            (690, (2, 1, 1)),
            (1500, (6, 5, 2)),
        ):
            view._arrange_dashboard(width)
            assert (view._kpi_columns, view._context_columns, view._domain_columns) == counts
            assert view._kpis["portfolio"].text() == "₡228,899.18 MM"
            assert view._kpis["icl"].text() == "9.79"
        assert view._radar._counts["high"].text() == "1"
        assert view._kpis["portfolio"].textInteractionFlags() & (
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        assert view._decision_splitter.orientation() == Qt.Orientation.Horizontal
        view._arrange_dashboard(690)
        assert view._decision_splitter.orientation() == Qt.Orientation.Vertical
    finally:
        view.close()
        qt_app.processEvents()


def test_executive_tables_preserve_full_traceability(qt_app) -> None:
    view = ExecutiveWorkspace()
    try:
        rows = (
            ExecutiveRow(
                "Alerta", "Detalle con trazabilidad", category="Liquidez",
                severity="High", source="SUGEF",
            ),
        )
        view._populate_rows(view._alerts_table, rows)
        assert view._alerts_table.item(0, 1).toolTip() == "Detalle con trazabilidad"
        assert view._alerts_table.item(0, 4).text() == "SUGEF"
        assert view._alerts_table.isSortingEnabled()
    finally:
        view.close()
        qt_app.processEvents()
