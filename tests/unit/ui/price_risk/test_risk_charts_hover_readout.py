from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QToolTip

from aip.ui.modules.price_risk.models.price_risk_row import RiskChartPoint
from aip.ui.modules.price_risk.widgets.risk_charts import (
    ParetoChartWidget,
    RiskBarChartWidget,
)


def _send_hover(chart: RiskBarChartWidget | ParetoChartWidget, location: QPoint) -> None:
    """Dispatch Qt hover directly; offscreen QTest.mouseMove may not deliver it."""
    chart.mouseMoveEvent(
        QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(location),
            QPointF(chart.mapToGlobal(location)),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
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
        _send_hover(chart, center)
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
        _send_hover(chart, position)
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


def test_risk_chart_refresh_and_leave_dismiss_stale_tooltips(qt_app, monkeypatch) -> None:
    dismissed: list[bool] = []
    monkeypatch.setattr(QToolTip, "hideText", lambda: dismissed.append(True))
    for chart in (RiskBarChartWidget(), ParetoChartWidget()):
        try:
            before_refresh = len(dismissed)
            chart.set_data((RiskChartPoint("BCCR", Decimal("1.0"), Decimal("100")),))
            chart.set_data(())
            assert len(dismissed) == before_refresh + 2
            before_leave = len(dismissed)
            chart.leaveEvent(QEvent(QEvent.Type.Leave))
            assert len(dismissed) == before_leave + 1
        finally:
            chart.close()
    qt_app.processEvents()


def test_risk_bar_layout_preserves_plot_area_on_compact_windows(qt_app) -> None:
    for widget_width in (240, 320, 540, 1200):
        left, right, plot_width = RiskBarChartWidget._responsive_columns(widget_width)
        assert left >= 76
        assert right >= 78
        assert plot_width >= 16
        assert left + right + plot_width <= widget_width


def test_negative_contributions_extend_left_from_zero(qt_app) -> None:
    left = RiskBarChartWidget._bar_rectangle(150.0, 45.0, 10.0, 16.0, True)
    right = RiskBarChartWidget._bar_rectangle(150.0, 45.0, 10.0, 16.0, False)
    assert left.left() == 105.0
    assert left.right() == 150.0
    assert right.left() == 150.0
    assert right.right() == 195.0


def test_dense_risk_bars_have_readable_height_and_full_tooltips(qt_app) -> None:
    chart = RiskBarChartWidget(show_secondary=True)
    try:
        chart.resize(320, 210)
        long_name = "Gobierno de Costa Rica - serie de vencimiento largo"
        chart.set_data(
            tuple(
                RiskChartPoint(f"{long_name} {index}", Decimal("-250000.50"), Decimal("12.5"))
                for index in range(12)
            )
        )
        assert chart.minimumHeight() >= 12 * 30
        chart.show()
        qt_app.processEvents()
        assert len(chart._tooltip_regions) == 12
        assert long_name in chart._tooltip_regions[0][1]
        assert "-250,000.50" in chart._tooltip_regions[0][1]
        assert long_name in chart._readout_regions[0][1]
    finally:
        chart.close()
        qt_app.processEvents()


def test_pareto_labels_reduce_density_in_narrow_windows(qt_app) -> None:
    assert ParetoChartWidget._visible_label_indexes(10, 210) == (0, 9)
    assert ParetoChartWidget._visible_label_indexes(10, 90) == (0,)
    assert ParetoChartWidget._visible_label_indexes(0, 90) == ()
    assert ParetoChartWidget._visible_label_indexes(3, 640) == (0, 1, 2)
