from __future__ import annotations

from PySide6.QtWidgets import QApplication

from aip.domain.portfolio.services.portfolio_capital_consumption_service import (
    ExposureClass,
)

from aip.ui.modules.portfolio.models.portfolio_row import PortfolioRow
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
    view._classification.setCurrentIndex(1)
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


def _sample_row(isin: str = "CRTEST000001") -> PortfolioRow:
    return PortfolioRow(
        isin=isin,
        issuer="Gobierno",
        instrument="Bono",
        currency="USD",
        nominal="200000",
        market_value="198000",
        book_value="194000",
        yield_value="8.75",
        modified_duration="3.5",
        classification="government",
        hqla_status="eligible",
        mil_status="available",
        recommendation="hold",
    )


def test_portfolio_identity_does_not_infer_financial_inputs(qt_app: QApplication) -> None:
    view = CapitalEquivalentRateView()
    view._equity_cost.setText("13.5")
    view.bind_positions((_sample_row(),), cutoff="2026-10-02")
    assert view._position.count() == 2
    view._position.setCurrentIndex(1)
    assert "CRTEST000001" in view._position_note.text()
    assert "2026-10-02" in view._position_note.text()
    assert "NO se" in view._position_note.text()
    assert view._invested.text() == ""
    assert view._exposure.text() == ""
    assert view._yield.text() == ""
    assert view._classification.currentData() is None
    assert view._equity_cost.text() == "13.5"


def test_switching_holding_invalidates_prior_capital_scenario(qt_app: QApplication) -> None:
    view = CapitalEquivalentRateView()
    view.bind_positions((_sample_row(), _sample_row("CRTEST000002")), cutoff="2026-10-02")
    view._position.setCurrentIndex(1)
    view._invested.setText("100")
    view._exposure.setText("100")
    view._yield.setText("8")
    view._equity_cost.setText("12")
    view._classification.setCurrentIndex(3)
    view._calculate_equivalent()
    assert "Tasa equivalente" in view._result.text()
    view._position.setCurrentIndex(2)
    assert view._invested.text() == ""
    assert view._exposure.text() == ""
    assert view._yield.text() == ""
    assert view._classification.currentData() is None
    assert view._equity_cost.text() == "12"
    view.bind_positions((_sample_row("CRTEST000003"),), cutoff="2026-10-03")
    assert view._position.currentIndex() == 0
    assert "Tasa equivalente" not in view._result.text()


def test_unverified_risk_weight_is_rejected(qt_app: QApplication) -> None:
    view = CapitalEquivalentRateView()
    view._invested.setText("100")
    view._exposure.setText("100")
    view._yield.setText("8")
    view._equity_cost.setText("12")
    view._calculate_equivalent()
    assert "ponderador regulatorio" in view._result.text()


def test_selected_usd_holding_cannot_use_crc_sovereign_zero_weight(
    qt_app: QApplication,
) -> None:
    view = CapitalEquivalentRateView()
    view.bind_positions((_sample_row(),), cutoff="2026-10-02")
    view._position.setCurrentIndex(1)
    view._invested.setText("100")
    view._exposure.setText("100")
    view._yield.setText("8")
    view._equity_cost.setText("12")
    view._classification.setCurrentIndex(
        view._classification.findText("Gobierno CRC · 0%")
    )
    view._calculate_equivalent()
    assert "0% soberano CRC" in view._result.text()


def test_all_defined_capital_weight_categories_can_be_selected(
    qt_app: QApplication,
) -> None:
    view = CapitalEquivalentRateView()
    actual = {
        view._classification.itemData(index)
        for index in range(view._classification.count())
        if view._classification.itemData(index) is not None
    }
    assert actual == set(ExposureClass)
