from __future__ import annotations

from aip.ui.modules.financial_analysis.viewmodels.financial_analysis_view_model import (
    PeerChartPointView,
    PeerChartSeriesView,
)
from aip.ui.modules.financial_analysis.views.financial_peer_chart import (
    FinancialPeerChartPanel,
)


def test_peer_chart_keeps_selected_entity_and_readable_scroll_height(qt_app) -> None:
    points = tuple(
        PeerChartPointView(
            entity_id=f"ENTITY-{index:02}",
            entity_name=f"Entidad supervisada {index:02}",
            value=float(20 - index),
            display_value=f"{20 - index:.2f}%",
            selected=index == 19,
        )
        for index in range(20)
    )
    panel = FinancialPeerChartPanel()
    try:
        panel.bind_series(
            (
                PeerChartSeriesView(
                    code="ROA",
                    label="Rentabilidad sobre activos",
                    unit="%",
                    chart_type="BAR",
                    points=points,
                ),
            )
        )

        visible = panel._bar_points(panel._series[0])
        assert len(visible) == 15
        assert points[-1] in visible
        assert panel._summary.text() == "15/20 entidades · %"
        assert "entidad seleccionada" in panel._chart_context.text()
        assert panel._chart_scroll.widgetResizable()
        assert panel._chart_view is not None
        assert panel._chart_view.minimumHeight() >= 75 + 32 * 15
    finally:
        panel.close()
        qt_app.processEvents()


def test_peer_chart_shows_source_context_in_pie_mode(qt_app) -> None:
    panel = FinancialPeerChartPanel()
    try:
        panel.bind_series(
            (
                PeerChartSeriesView(
                    code="MARKET",
                    label="Participación de activos",
                    unit="%",
                    chart_type="PIE",
                    points=(
                        PeerChartPointView("1", "Entidad Uno", 60.0, "60.00%"),
                        PeerChartPointView("2", "Entidad Dos", 40.0, "40.00%"),
                    ),
                ),
            )
        )
        assert panel._summary.text() == "2 entidades · %"
        assert "valor completo" in panel._chart_context.text()
        assert panel._chart_view is not None
    finally:
        panel.close()
        qt_app.processEvents()
