from __future__ import annotations

from PySide6.QtWidgets import QApplication

from aip.ui.modules.portfolio.views.capital_equivalent_rate_view import (
    CapitalEquivalentRateView,
)


def test_equity_cost_is_empty_and_editable(qt_app: QApplication) -> None:
    view = CapitalEquivalentRateView()
    assert view._equity_cost.text() == ""
    assert not view._equity_cost.isReadOnly()
    assert view._target.text() == "16,00 %"
    view._invested.setText("100")
    view._exposure.setText("100")
    view._yield.setText("8")
    view._calculate_equivalent()
    assert "costo anual del patrimonio" in view._result.text()


def test_equivalent_rate_recalculates_after_edit(qt_app: QApplication) -> None:
    view = CapitalEquivalentRateView()
    view._invested.setText("100")
    view._exposure.setText("100")
    view._yield.setText("8")
    index = view._classification.findText("Gobierno USD · 75%")
    view._classification.setCurrentIndex(index)

    view._equity_cost.setText("10")
    view._calculate_equivalent()
    assert "6.8000 %" in view._result.text()

    view._equity_cost.setText("20")
    view._calculate_equivalent()
    assert "5.6000 %" in view._result.text()
