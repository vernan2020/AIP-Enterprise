from __future__ import annotations

from PySide6.QtWidgets import QTableWidget

from aip.ui.modules.portfolio.models.portfolio_valuation_comparison import (
    PortfolioValuationComparisonDisplay,
    PortfolioValuationComparisonDisplayRow,
)
from aip.ui.modules.portfolio.views.portfolio_valuation_comparison_view import (
    PortfolioValuationComparisonView,
)


def test_valuation_comparison_view_renders_totals_and_positions(qt_app) -> None:
    view = PortfolioValuationComparisonView()
    model = PortfolioValuationComparisonDisplay(
        totals=(
            PortfolioValuationComparisonDisplayRow(
                ("CRC", "110.00", "100.00", "+10.00", "+10.00%", "1/1 posiciones"),
                "gain",
            ),
        ),
        positions=(
            PortfolioValuationComparisonDisplayRow(
                (
                    "CRTEST",
                    "Emisor",
                    "CRC",
                    "110.00",
                    "100.00",
                    "+10.00",
                    "+10.00%",
                    "Calculado",
                    "Maestro.xlsx · fila 2",
                ),
                "gain",
            ),
        ),
    )

    view.bind(model, "2026-09-30")

    totals = view.findChild(QTableWidget, "portfolioValuationTotals")
    positions = view.findChild(QTableWidget, "portfolioValuationPositions")
    assert totals is not None
    assert positions is not None
    assert totals.rowCount() == 1
    assert totals.item(0, 3).text() == "+10.00"
    assert positions.rowCount() == 1
    assert positions.item(0, 8).text() == "Maestro.xlsx · fila 2"
