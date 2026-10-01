from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import QLabel, QPushButton, QTableWidget

from aip.ui.modules.portfolio.models.portfolio_valuation_comparison import (
    PortfolioValuationChartPoint,
    PortfolioValuationComparisonDisplay,
    PortfolioValuationComparisonDisplayRow,
    PortfolioValuationKpi,
)
from aip.ui.modules.portfolio.views.portfolio_valuation_comparison_view import (
    PortfolioValuationComparisonView,
)


def test_valuation_comparison_view_renders_dashboard_and_top_positions(qt_app) -> None:
    view = PortfolioValuationComparisonView()
    row = PortfolioValuationComparisonDisplayRow(
        (
            "CRTEST",
            "Emisor",
            "CRC",
            "+25.50",
            "Maestro de Inversiones",
            "Maestro.xlsx · fila 2",
        ),
        "gain",
    )
    model = PortfolioValuationComparisonDisplay(
        kpis=(
            PortfolioValuationKpi("gain_total", "Ganancia total", "+25.50", "gain"),
            PortfolioValuationKpi("loss_total", "Pérdida total", "-10.00", "loss"),
        ),
        top_gains=(PortfolioValuationChartPoint("CRTEST", Decimal("25.5")),),
        currency_points=(
            PortfolioValuationChartPoint(
                "CRC",
                Decimal("15.5"),
                positive=Decimal("25.5"),
                negative=Decimal("-10"),
            ),
        ),
        positions=(row,),
        all_positions=(row,),
    )

    view.bind(model, "2026-09-30")

    positions = view.findChild(QTableWidget, "portfolioValuationPositions")
    assert positions is not None
    assert positions.columnCount() == 5
    assert positions.rowCount() == 1
    assert positions.item(0, 1).text() == "CRTEST"
    assert positions.item(0, 4).text() == "+25.50"

    gain_value = view.findChild(QLabel, "portfolioValuationKpiValue_gain_total")
    assert gain_value is not None
    assert gain_value.text() == "+25.50"

    toggle = view.findChild(QPushButton, "portfolioValuationShowAll")
    assert toggle is not None
    assert toggle.text() == "Ver todas las posiciones"


def test_valuation_comparison_view_can_expand_all_positions(qt_app) -> None:
    view = PortfolioValuationComparisonView()
    top = PortfolioValuationComparisonDisplayRow(("TOP", "A", "CRC", "+5.00", "", ""), "gain")
    second = PortfolioValuationComparisonDisplayRow(
        ("SECOND", "B", "USD", "-2.00", "", ""),
        "loss",
    )
    view.bind(
        PortfolioValuationComparisonDisplay(
            positions=(top,),
            all_positions=(top, second),
        ),
        "2026-09-30",
    )

    toggle = view.findChild(QPushButton, "portfolioValuationShowAll")
    positions = view.findChild(QTableWidget, "portfolioValuationPositions")
    assert toggle is not None
    assert positions is not None

    toggle.click()

    assert positions.rowCount() == 2
    assert positions.item(1, 1).text() == "SECOND"
    assert toggle.text() == "Ver Top 10"
