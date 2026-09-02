from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from aip.ui.modules.price_risk.presenters.price_risk_presenter import PriceRiskPresenter


def _position(
    series: str,
    issuer: str,
    currency: str,
    contribution: str,
    market_value: str,
) -> SimpleNamespace:
    return SimpleNamespace(
        series=series,
        issuer=issuer,
        currency=currency,
        contribution_at_var_scenario_percent=Decimal(contribution),
        market_value_crc=Decimal(market_value),
    )


def test_var_pareto_preserves_signed_contributions_and_reconciles_to_100() -> None:
    positions = (
        _position("A", "G", "CRC", "80", "800"),
        _position("B", "BCCR", "CRC", "30", "100"),
        _position("C", "G", "USD", "-10", "100"),
    )

    top, pareto, issuer, currencies, reconciliation = (
        PriceRiskPresenter._build_var_chart_contracts(positions)
    )

    assert tuple(point.value for point in top) == (
        Decimal("80"),
        Decimal("30"),
        Decimal("-10"),
    )
    assert tuple(point.secondary_value for point in pareto) == (
        Decimal("80"),
        Decimal("110"),
        Decimal("100"),
    )
    assert reconciliation == Decimal("100")
    assert sum((point.value for point in issuer), Decimal("0")) == Decimal("100")
    assert sum((point.secondary_value for point in currencies), Decimal("0")) == Decimal("100")


def test_var_currency_distribution_uses_calculated_market_value() -> None:
    positions = (
        _position("A", "G", "CRC", "60", "900"),
        _position("B", "G", "USD", "40", "100"),
    )

    _top, _pareto, _issuer, currencies, _reconciliation = (
        PriceRiskPresenter._build_var_chart_contracts(positions)
    )

    by_currency = {point.label: point for point in currencies}
    assert by_currency["CRC"].value == Decimal("900")
    assert by_currency["CRC"].secondary_value == Decimal("90")
    assert by_currency["USD"].value == Decimal("100")
    assert by_currency["USD"].secondary_value == Decimal("10")
