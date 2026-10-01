from __future__ import annotations

from PySide6.QtWidgets import QTableWidget

from aip.ui.modules.portfolio.models.portfolio_valuation_comparison import (
    PortfolioValuationBreakdownDisplay,
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
                25.5,
            ),
        ),
    )

    view.bind(model, "2026-09-30")

    positions = view.findChild(QTableWidget, "portfolioValuationPositions")
    assert positions is not None
    assert positions.columnCount() == 4
    assert positions.rowCount() == 1
    assert positions.item(0, 3).text() == "+25.50"


def test_valuation_dashboard_keeps_cross_currency_totals_unavailable(qt_app) -> None:
    view = PortfolioValuationComparisonView()
    model = PortfolioValuationComparisonDisplay(
        gain_total=None,
        loss_total=None,
        net_total=None,
        gain_count=1,
        loss_count=1,
        available_count=2,
        currency_breakdown=(
            PortfolioValuationBreakdownDisplay("CRC", 25.0, 0.0, 25.0, 1),
            PortfolioValuationBreakdownDisplay("USD", 10.0, 0.0, 10.0, 1),
        ),
    )

    view.bind(model, "2026-09-30")

    assert "varias monedas" in view._note.text()
    assert view._card_values["gain"].text() == "N/D"
    assert view._card_values["net"].text() == "N/D"
