from __future__ import annotations

from decimal import Decimal

from aip.ui.modules.portfolio.presenters.portfolio_presenter import PortfolioPresenter


def _position(
    isin: str,
    issuer: str,
    currency: str,
    value: str | None,
) -> dict[str, object]:
    return {
        "isin": isin,
        "issuer": issuer,
        "valuation_accumulated_source": {
            "value": value,
            "currency": currency,
            "source_file": "30-09-2026.xlsx",
            "source_row": 2,
        },
    }


def test_valuation_dashboard_aggregates_authoritative_master_values() -> None:
    model = PortfolioPresenter._valuation_comparison(
        {
            "positions": (
                _position("A", "BCCR", "CRC", "100"),
                _position("B", "BCCR", "CRC", "50"),
                _position("C", "Gobierno", "USD", "-40"),
                _position("D", "Gobierno", "USD", None),
            )
        }
    )

    assert model.gain_total == Decimal("150")
    assert model.loss_total == Decimal("40")
    assert model.net_total == Decimal("110")
    assert model.gain_count == 2
    assert model.loss_count == 1
    assert model.neutral_count == 0

    assert [row.cells[0] for row in model.top_gains] == ["A", "B"]
    assert [row.cells[0] for row in model.top_losses] == ["C"]

    assert [(point.label, point.amount) for point in model.currency_breakdown] == [
        ("CRC", Decimal("150")),
        ("USD", Decimal("-40")),
    ]
    assert [(point.label, point.amount) for point in model.issuer_breakdown] == [
        ("BCCR", Decimal("150")),
        ("Gobierno", Decimal("-40")),
    ]


def test_valuation_dashboard_does_not_zero_fill_missing_values() -> None:
    model = PortfolioPresenter._valuation_comparison(
        {"positions": (_position("A", "BCCR", "CRC", None),)}
    )

    assert model.positions[0].amount is None
    assert model.positions[0].cells[3] == "N/D"
    assert model.gain_total == Decimal("0")
    assert model.loss_total == Decimal("0")
    assert model.net_total == Decimal("0")
    assert model.gain_count == 0
    assert model.loss_count == 0
