from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest

from aip.ui.modules.price_risk.models.price_risk_row import RiskChartPoint
from aip.ui.modules.price_risk.widgets.risk_charts import (
    ParetoChartWidget,
    RiskBarChartWidget,
)


def test_bar_chart_hover_displays_full_label_and_clears_on_refresh(qt_app) -> None:
    chart = RiskBarChartWidget(show_secondary=True)
    history: list[str] = []
    chart.hover_readout_changed.connect(history.append)
    try:
        chart.resize(540, 240)
        chart.set_data(
            (
                RiskChartPoint("Gobierno de Costa Rica", Decimal("15.75"), Decimal("60")),
                RiskChartPoint("BCCR", Decimal("-2.25"), Decimal("40")),
            )
        )
        chart.show()
        qt_app.processEvents()
        assert len(chart._readout_regions) == 2
        center = chart._readout_regions[0][0].center().toPoint()
        QTest.mouseMove(chart, center)
        qt_app.processEvents()
        assert any("Gobierno de Costa Rica" in value for value in history)
        assert any("15.75" in value and "60.0%" in value for value in history)

        chart.set_data(())
        assert history[-1] == ""
        assert chart._readout_regions == []
    finally:
        chart.close()
        qt_app.processEvents()


def test_pareto_hover_readout_has_contribution_and_cumulative_percent(qt_app) -> None:
    chart = ParetoChartWidget()
    history: list[str] = []
    chart.hover_readout_changed.connect(history.append)
    try:
        chart.resize(540, 240)
        chart.set_data(
            (
                RiskChartPoint("Serie larga G-2026", Decimal("16.5"), Decimal("16.5")),
                RiskChartPoint("Serie B", Decimal("12.4"), Decimal("28.9")),
            )
        )
        chart.show()
        qt_app.processEvents()
        assert len(chart._readout_regions) == 4
        position: QPoint = chart._readout_regions[0][0].center().toPoint()
        QTest.mouseMove(chart, position)
        qt_app.processEvents()
        assert any(
            "Serie larga G-2026" in value
            and "Contribución: 16.50" in value
            and "Acumulado: 16.5%" in value
            for value in history
        )

        chart.set_data(())
        assert history[-1] == ""
        assert not chart._readout_regions
    finally:
        chart.close()
        qt_app.processEvents()
