"""AIP PRO-MAX responsive KPI contracts across institutional pages."""

from __future__ import annotations

from PySide6.QtCore import Qt

from aip.ui.modules.intelligence.views.financial_intelligence_view import (
    FinancialIntelligenceView,
)
from aip.ui.modules.liquidity.views.liquidity_view import LiquidityView
from aip.ui.modules.portfolio.views.portfolio_view import PortfolioView
from aip.ui.modules.rate_risk.views.rate_risk_view import RateRiskView
from aip.ui.modules.treasury.views.treasury_view import TreasuryView


def test_portfolio_kpi_grid_reflows_without_losing_values(qt_app) -> None:
    view = PortfolioView()
    try:
        assert len(view._kpi_cards) == 6
        view._kpis["duration"].setText("2.35")
        for width, columns in ((1450, 6), (950, 3), (620, 2), (1450, 6)):
            view._arrange_kpis(width)
            assert view._kpi_columns == columns
            assert view._kpis["duration"].text() == "2.35"
            for i, card in enumerate(view._kpi_cards):
                assert view._kpi_grid.itemAtPosition(i // columns, i % columns).widget() is card
        assert view._kpis["duration"].textInteractionFlags() & (
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
    finally:
        view.close()
        qt_app.processEvents()


def test_liquidity_kpi_grid_preserves_last_two_long_cards(qt_app) -> None:
    view = LiquidityView()
    try:
        assert len(view._kpi_cards) == 8
        view._kpis["icl_total"].setText("9.79")
        for width, columns in ((900, 4), (620, 2), (1450, 6)):
            view._arrange_kpis(width)
            assert view._kpi_columns == columns
            assert view._kpis["icl_total"].text() == "9.79"
        assert view._kpi_grid.itemAtPosition(1, 0).widget() is view._kpi_cards[6]
        assert view._kpi_grid.itemAtPosition(1, 3).widget() is view._kpi_cards[7]
    finally:
        view.close()
        qt_app.processEvents()


def test_treasury_kpi_grid_is_readable_at_small_widths(qt_app) -> None:
    view = TreasuryView()
    try:
        assert len(view._kpi_cards) == 6
        view._kpis["icl"].setText("10.75")
        view._arrange_kpis(700)
        assert view._kpi_columns == 2
        assert view._kpi_grid.itemAtPosition(2, 1).widget() is view._kpi_cards[5]
        view._arrange_kpis(1000)
        assert view._kpi_columns == 3
        assert view._kpis["icl"].text() == "10.75"
    finally:
        view.close()
        qt_app.processEvents()


def test_rtilb_kpis_use_white_values_on_blue_cards(qt_app) -> None:
    view = RateRiskView()
    try:
        assert len(view._summary_kpi_cards) == 5
        view._arrange_summary_kpis(650)
        assert view._summary_columns == 2
        assert view._summary_kpi_grid.itemAtPosition(2, 0).widget() is (
            view._summary_kpi_cards[4]
        )
        assert "color:#FFFFFF" in view._kpi_values["BASE_EVE"].styleSheet()
        assert "stop:0 #00477F" in view._summary_kpi_cards[0].styleSheet()
    finally:
        view.close()
        qt_app.processEvents()


def test_intelligence_card_presentation_is_consistent_and_selectable(qt_app) -> None:
    assert FinancialIntelligenceView._metric_columns_for_width(620) == 2
    assert FinancialIntelligenceView._metric_columns_for_width(970) == 3
    assert FinancialIntelligenceView._metric_columns_for_width(1450) == 6
