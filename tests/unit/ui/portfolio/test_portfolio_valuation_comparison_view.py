from aip.ui.modules.portfolio.presenters.portfolio_presenter import PortfolioPresenter
from aip.ui.modules.portfolio.views.portfolio_valuation_comparison_view import (
    PortfolioValuationComparisonView,
)


def test_comparison_view_formats_coverage_and_rebinds_without_stale_rows(qt_app):
    display = PortfolioPresenter._valuation_comparison(
        {
            "positions": [
                {
                    "isin": "TEST",
                    "issuer": "Issuer",
                    "source_file": "master.xlsx",
                    "source_row": 2,
                    "valuation_comparison_source": {
                        "currency": "USD",
                        "market_value": 90,
                        "book_value": 100,
                    },
                },
                {
                    "valuation_comparison_source": {
                        "currency": "USD",
                        "market_value": None,
                        "book_value": 100,
                    }
                },
            ]
        }
    )
    view = PortfolioValuationComparisonView()
    view.bind(display, "2026-09-30")
    assert view._totals.item(0, 3).text() == "-10.00"
    assert view._totals.item(0, 4).text() == "-10.00%"
    assert view._totals.item(0, 5).text() == "1/2 posiciones · parcial"
    assert view._positions.item(1, 5).text() == "N/D"
    assert view._positions.item(0, 5).foreground().color().name() == "#b42318"
    view.bind(PortfolioPresenter._valuation_comparison({"positions": []}), "2026-09-29")
    assert view._positions.rowCount() == 0
    assert view._totals.rowCount() == 0
    assert "2026-09-29" in view._note.text()
