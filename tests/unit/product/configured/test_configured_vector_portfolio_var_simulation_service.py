from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from aip.product.configured.services.configured_vector_portfolio_var_simulation_service import (
    ConfiguredVectorPortfolioVaRSimulationService,
)


class _PortfolioProvider:
    def __init__(self, portfolio: dict[str, Any]) -> None:
        self._portfolio = portfolio

    def get_portfolio(self) -> dict[str, Any]:
        return self._portfolio


class _UnusedVaRService:
    pass


def _portfolio() -> dict[str, Any]:
    return {
        "valuation_date": date(2026, 8, 31),
        "positions": [
            {
                "isin": "CR000AAA",
                "series": "G260831",
                "issuer": "G",
                "currency": "CRC",
                "product_code": "TP",
                "maturity_date": date(2028, 8, 31),
                "market_value_crc": 100_000_000.0,
            },
            {
                "series": "BCCR2701",
                "issuer": "BCCR",
                "currency": "CRC",
                "product_code": "BP",
                "maturity_date": date(2027, 1, 15),
                "market_value_crc": 50_000_000.0,
            },
        ],
        "price_vector": {
            "records": [
                {
                    # Same security as the portfolio, but a different issuer label.
                    # Series+maturity must reconcile it instead of duplicating it.
                    "isin_if_present": "",
                    "series_or_security_code": "G260831",
                    "issuer": "GOBIERNO",
                    "instrument_type_or_mnemonic": "TP",
                    "maturity_date_if_present": date(2028, 8, 31),
                    "market_price": 101.25,
                    "market_yield": 5.10,
                },
                {
                    "series_or_security_code": "G300101",
                    "issuer": "G",
                    "instrument_type_or_mnemonic": "TP",
                    "maturity_date_if_present": date(2030, 1, 1),
                    "market_price": 98.75,
                    "market_yield": 5.75,
                },
                {
                    # Missing current quote must not remove a title from the BUY catalog.
                    "series_or_security_code": "BCCR3101",
                    "issuer": "BCCR",
                    "instrument_type_or_mnemonic": "BP",
                    "maturity_date_if_present": date(2031, 1, 15),
                    "market_price": None,
                    "market_yield": None,
                },
                {
                    # Some normalized vector payloads can carry only normalized issuer.
                    "series_or_security_code": "PRIV2801",
                    "issuer": "",
                    "normalized_issuer_key": "BANCO PRIVADO",
                    "instrument_type_or_mnemonic": "BONO$",
                    "maturity_date_if_present": date(2028, 1, 20),
                    "market_price": 99.50,
                    "market_yield": 6.20,
                },
            ]
        },
    }


def _service() -> ConfiguredVectorPortfolioVaRSimulationService:
    return ConfiguredVectorPortfolioVaRSimulationService(
        _PortfolioProvider(_portfolio()),  # type: ignore[arg-type]
        _UnusedVaRService(),  # type: ignore[arg-type]
    )


def test_buy_catalog_contains_every_resolvable_vector_title() -> None:
    universe = _service().list_securities()
    by_series = {item.series: item for item in universe}

    assert set(by_series) == {
        "G260831",
        "BCCR2701",
        "G300101",
        "BCCR3101",
        "PRIV2801",
    }
    assert by_series["G300101"].source == "PIPCA"
    assert by_series["G300101"].in_portfolio is False
    assert by_series["BCCR3101"].market_price is None
    assert by_series["BCCR3101"].in_portfolio is False
    assert by_series["PRIV2801"].issuer == "BANCO PRIVADO"
    assert by_series["PRIV2801"].currency == "USD"


def test_portfolio_vector_overlap_is_deduplicated_and_enriched_from_vector() -> None:
    universe = _service().list_securities()
    matching = [item for item in universe if item.series == "G260831"]

    assert len(matching) == 1
    security = matching[0]
    assert security.in_portfolio is True
    assert security.source == "PORTFOLIO"
    assert security.current_market_value_crc == Decimal("100000000")
    assert security.market_price == Decimal("101.25")
    assert security.market_yield == Decimal("5.1")


def test_sell_candidates_remain_restricted_to_actual_holdings() -> None:
    universe = _service().list_securities()

    held = {item.series for item in universe if item.in_portfolio}
    vector_only = {item.series for item in universe if not item.in_portfolio}

    assert held == {"G260831", "BCCR2701"}
    assert vector_only == {"G300101", "BCCR3101", "PRIV2801"}


def test_vector_positions_alias_is_supported_when_records_key_is_absent() -> None:
    portfolio = _portfolio()
    vector = portfolio["price_vector"]
    assert isinstance(vector, dict)
    vector["positions"] = vector.pop("records")
    service = ConfiguredVectorPortfolioVaRSimulationService(
        _PortfolioProvider(portfolio),  # type: ignore[arg-type]
        _UnusedVaRService(),  # type: ignore[arg-type]
    )

    assert {item.series for item in service.list_securities()} == {
        "G260831",
        "BCCR2701",
        "G300101",
        "BCCR3101",
        "PRIV2801",
    }
