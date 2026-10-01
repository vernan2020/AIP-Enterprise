from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import QLabel, QTableWidget

from aip.ui.modules.portfolio.models.portfolio_valuation_comparison import (
    PortfolioValuationBreakdownPoint,
    PortfolioValuationComparisonDisplay,
    PortfolioValuationComparisonDisplayRow,
)
from aip.ui.modules.portfolio.views.portfolio_valuation_comparison_view import (
    PortfolioValuationComparisonView,
)


def _row(
    identity: str,
    issuer: str,
    currency: str,
    amount: str,
    tone: str,
) -> PortfolioValuationComparisonDisplayRow:
    value = Decimal(amount)
    return PortfolioValuationComparisonDisplayRow(
        (
            identity,
            issuer,
            currency,
            f"{value:+,.2f}",
            "Maestro de Inversiones",
            "Maestro.xlsx · fila 2",
        ),
        tone,
        value,
    )


def test_valuation_comparison_view_renders_visual_dashboard(qt_app) -> None:
    gain = _row("CRGAIN", "BCCR", "CRC", "25000000", "gain")
    loss = _row("CRLOSS", "Gobierno", "USD", "-5000000", "loss")
    view = PortfolioValuationComparisonView()
    model = PortfolioValuationComparisonDisplay(
        positions=(gain, loss),
        gain_total=Decimal("25000000"),
        loss_total=Decimal("5000000"),
        net_total=Decimal("20000000"),
        gain_count=1,
        loss_count=1,
        top_gains=(gain,),
        top_losses=(loss,),
        currency_breakdown=(
            PortfolioValuationBreakdownPoint("CRC", Decimal("25000000"), "gain"),
            PortfolioValuationBreakdownPoint("USD", Decimal("-5000000"), "loss"),
        ),
        issuer_breakdown=(
            PortfolioValuationBreakdownPoint("BCCR", Decimal("25000000"), "gain"),
            PortfolioValuationBreakdownPoint("Gobierno", Decimal("-5000000"), "loss"),
        ),
    )

    view.bind(model, "2026-09-30")

    positions = view.findChild(QTableWidget, "portfolioValuationPositions")
    assert positions is not None
    assert positions.columnCount() == 4
    assert positions.rowCount() == 2
    assert positions.item(0, 0).text() == "CRGAIN"
    assert positions.item(0, 3).text() == "₡25.00 MM"
    assert positions.item(1, 3).text() == "₡-5.00 MM"

    caption = view.findChild(QLabel, "portfolioValuationDetailCaption")
    assert caption is not None
    assert "2 de 2 posiciones" in caption.text()


def test_valuation_comparison_view_keeps_authoritative_note(qt_app) -> None:
    view = PortfolioValuationComparisonView()
    view.bind(PortfolioValuationComparisonDisplay(), "2026-09-30")

    labels = [label.text() for label in view.findChildren(QLabel)]
    assert any("Valuación Acumulada del Maestro de Inversiones" in text for text in labels)
