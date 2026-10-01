from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QGroupBox

from aip.ui.modules.portfolio.views.portfolio_history_view import PortfolioHistoryView


def test_history_view_uses_modern_card_and_control_properties(qt_app) -> None:
    view = PortfolioHistoryView()

    assert view.objectName() == "portfolioHistoryWorkspace"

    cards = view.findChildren(QGroupBox)
    assert len(cards) == 6
    assert all(card.property("historyCard") is True for card in cards)

    controls = view.findChildren(QComboBox)
    assert len(controls) == 2
    assert all(control.property("historyControl") is True for control in controls)

    style = view.styleSheet()
    assert 'QGroupBox[historyCard="true"]' in style
    assert 'QComboBox[historyControl="true"]' in style
