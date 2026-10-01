from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCore import QPointF

from aip.ui.modules.portfolio.widgets.portfolio_history_line_chart import (
    PortfolioHistoryLineChart,
)


def test_smooth_path_keeps_first_and_last_points() -> None:
    coordinates = [QPointF(10.0, 20.0), QPointF(30.0, 10.0), QPointF(50.0, 15.0)]

    path = PortfolioHistoryLineChart._smooth_path(coordinates)

    assert path.elementAt(0).x == 10.0
    assert path.elementAt(0).y == 20.0
    assert path.currentPosition() == QPointF(50.0, 15.0)
    assert path.elementCount() > len(coordinates)


def test_chart_renders_modern_history_series(qt_app) -> None:
    chart = PortfolioHistoryLineChart(
        value_formatter=lambda value: f"{value:,.2f}%",
        reference_value=Decimal("3.00"),
        reference_label="Objetivo <= 3,00",
    )
    chart.resize(640, 280)
    chart.set_data(
        (
            (date(2026, 6, 30), Decimal("1.20")),
            (date(2026, 7, 31), Decimal("1.35")),
            (date(2026, 8, 31), Decimal("1.30")),
            (date(2026, 9, 30), Decimal("1.42")),
        ),
        previous_month_value=Decimal("1.30"),
        year_end_value=Decimal("1.25"),
    )

    chart.show()
    qt_app.processEvents()

    pixmap = chart.grab()
    assert not pixmap.isNull()


def test_chart_renders_active_hover_guide(qt_app) -> None:
    chart = PortfolioHistoryLineChart(value_formatter=lambda value: f"{value:,.2f}")
    chart.resize(640, 280)
    chart.set_data(
        (
            (date(2026, 7, 31), Decimal("1.10")),
            (date(2026, 8, 31), Decimal("1.25")),
            (date(2026, 9, 30), Decimal("1.20")),
        )
    )

    chart.show()
    qt_app.processEvents()
    chart.grab()
    assert chart._hover_points

    chart._active_hover = chart._hover_points[1]
    chart.update()
    qt_app.processEvents()

    pixmap = chart.grab()
    assert not pixmap.isNull()
    assert chart._active_hover[1] == date(2026, 8, 31)
