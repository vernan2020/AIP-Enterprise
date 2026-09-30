from __future__ import annotations

from PySide6.QtWidgets import QTableWidget

from aip.ui.modules.portfolio.models.portfolio_valuation_comparison import (
    PortfolioValuationComparisonDisplay,
    PortfolioValuationComparisonDisplayRow,
)
from aip.ui.modules.portfolio.views.portfolio_valuation_comparison_view import (
    PortfolioValuationComparisonView,
)


def test_valuation_comparison_view_renders_accumulated_valuation(qt_app) -> None:
    view = PortfolioValuationComparisonView()
    model = PortfolioValuationComparisonDisplay(
        positions=(
            PortfolioValuationComparisonDisplayRow(
                (
                    "CRTEST",
                    "Emisor",
                    "CRC",
                    "+25.50",
                    "Maestro de Inversiones",
                    "Maestro.xlsx · fila 2",
                ),
                "gain",
            ),
        ),
    )

    view.bind(model, "2026-09-30")

    positions = view.findChild(QTableWidget, "portfolioValuationPositions")
    assert positions is not None
    assert positions.columnCount() == 6
    assert positions.rowCount() == 1
    assert positions.item(0, 3).text() == "+25.50"
    assert positions.item(0, 5).text() == "Maestro.xlsx · fila 2"
