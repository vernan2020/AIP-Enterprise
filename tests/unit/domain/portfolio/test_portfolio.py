"""Tests for Portfolio aggregate root and calculation service integration."""

from datetime import date
from decimal import Decimal

import pytest

from src.aip.domain.portfolio.entities import Portfolio, Position, Transaction
from src.aip.domain.portfolio.enums import PortfolioStatus, ValuationSource
from src.aip.domain.portfolio.exceptions import (
    DuplicatePositionError,
    PortfolioClosedError,
    PositionNotFoundError,
)
from src.aip.domain.portfolio.services import PortfolioCalculationService
from src.aip.domain.portfolio.value_objects import (
    ISIN,
    AcquisitionCost,
    BookValue,
    Convexity,
    Duration,
    InstrumentName,
    MarketValue,
    NominalValue,
    PortfolioId,
    PositionId,
    Quantity,
    SettlementDate,
    TransactionId,
    YieldRate,
)
from src.aip.shared.calendars import CostaRicaCalendar
from src.aip.shared.dates import BusinessDate
from src.aip.shared.money import Currency


def _position(
    isin: str = "US0378331005",
    settlement: date = date(2026, 1, 15),
    market: str = "995",
    book: str = "990",
    nominal: str = "1000",
    yld: str = "4.2",
    dur: str = "5.2",
    conv: str = "11.8",
) -> Position:
    return Position.create(
        position_id=PositionId.new(),
        isin=ISIN(isin),
        instrument_name=InstrumentName("Instrument"),
        currency=Currency.USD,
        quantity=Quantity(Decimal("10")),
        nominal_value=NominalValue.from_decimal(Decimal(nominal), Currency.USD),
        acquisition_cost=AcquisitionCost.from_decimal(Decimal("980"), Currency.USD),
        book_value=BookValue.from_decimal(Decimal(book), Currency.USD),
        market_value=MarketValue.from_decimal(Decimal(market), Currency.USD),
        yield_rate=YieldRate.from_decimal_percentage(Decimal(yld)),
        duration=Duration(Decimal(dur)),
        convexity=Convexity(Decimal(conv)),
        settlement_date=SettlementDate(BusinessDate(settlement, CostaRicaCalendar())),
        valuation_source=ValuationSource.MARKET_FEED,
    )


def _portfolio() -> Portfolio:
    return Portfolio.create(
        portfolio_id=PortfolioId.new(),
        name="Growth Fund",
        description="Treasury and bonds",
        base_currency=Currency.USD,
    )


def _transaction(portfolio_id: PortfolioId, position_id: PositionId) -> Transaction:
    return Transaction.sell(
        transaction_id=TransactionId.new(),
        portfolio_id=portfolio_id,
        position_id=position_id,
        trade_date=date(2026, 1, 20),
        settlement_date=SettlementDate(BusinessDate(date(2026, 1, 22), CostaRicaCalendar())),
        quantity=Quantity(Decimal("2")),
        nominal_amount=Decimal("200"),
        gross_amount=Decimal("210"),
        fees=Decimal("2"),
        taxes=Decimal("1"),
        currency=Currency.USD,
        reference="TX-001",
    )


def test_portfolio_create_and_state_transitions_generate_events() -> None:
    portfolio = _portfolio()
    assert portfolio.status == PortfolioStatus.CREATED

    portfolio.activate()
    portfolio.suspend()
    portfolio.close()

    event_types = [event.event_type for event in portfolio.pull_domain_events()]
    assert "portfolio.created" in event_types
    assert "portfolio.activated" in event_types
    assert "portfolio.suspended" in event_types
    assert "portfolio.closed" in event_types


def test_closed_portfolio_rejects_new_positions_and_transactions() -> None:
    portfolio = _portfolio()
    position = _position()
    portfolio.close()

    with pytest.raises(PortfolioClosedError):
        portfolio.add_position(position)

    with pytest.raises(PortfolioClosedError):
        portfolio.register_transaction(_transaction(portfolio.portfolio_id, position.position_id))


def test_duplicate_positions_rejected_by_business_key() -> None:
    portfolio = _portfolio()
    first = _position(isin="US0378331005", settlement=date(2026, 1, 15))
    second = _position(isin="US0378331005", settlement=date(2026, 1, 15))

    portfolio.add_position(first)
    with pytest.raises(DuplicatePositionError):
        portfolio.add_position(second)


def test_add_remove_position_and_register_transaction_emit_events() -> None:
    portfolio = _portfolio()
    position = _position()
    portfolio.add_position(position)

    tx = _transaction(portfolio.portfolio_id, position.position_id)
    portfolio.register_transaction(tx)
    portfolio.remove_position(position.position_id)

    event_types = [event.event_type for event in portfolio.pull_domain_events()]
    assert "portfolio.position_added" in event_types
    assert "portfolio.transaction_registered" in event_types
    assert "portfolio.position_removed" in event_types


def test_remove_position_not_found_raises() -> None:
    portfolio = _portfolio()

    with pytest.raises(PositionNotFoundError):
        portfolio.remove_position(PositionId.new())


def test_register_transaction_with_wrong_portfolio_id_raises() -> None:
    portfolio = _portfolio()
    position = _position()
    portfolio.add_position(position)

    wrong_transaction = _transaction(PortfolioId.new(), position.position_id)
    with pytest.raises(ValueError):
        portfolio.register_transaction(wrong_transaction)


def test_aggregate_calculations_and_weighted_metrics() -> None:
    portfolio = _portfolio()
    p1 = _position(market="100", book="90", nominal="100", yld="5", dur="4", conv="10")
    p2 = _position(
        isin="US5949181045",
        settlement=date(2026, 1, 16),
        market="300",
        book="270",
        nominal="300",
        yld="3",
        dur="6",
        conv="14",
    )
    portfolio.add_position(p1)
    portfolio.add_position(p2)

    assert portfolio.total_nominal_value().amount == Decimal("400")
    assert portfolio.total_market_value().amount == Decimal("400")
    assert portfolio.total_book_value().amount == Decimal("360")
    assert portfolio.unrealized_gain_or_loss().amount == Decimal("40.00")
    assert portfolio.weighted_yield() == Decimal("3.5")
    assert portfolio.weighted_duration() == Decimal("5.5")
    assert portfolio.weighted_convexity() == Decimal("13")


def test_weighted_average_effective_yield_prefers_master_tir_and_uses_crc_weights() -> None:
    positions = [
        {
            "currency": Currency.CRC,
            "market_value_crc": Decimal("100"),
            "market_value": Decimal("40"),
            "classification": "active",
            "portfolio_yield": Decimal("5"),
            "nominal_rate": Decimal("4"),
        },
        {
            "currency": Currency.CRC,
            "market_value_crc": Decimal("200"),
            "market_value": Decimal("80"),
            "classification": "active",
            "portfolio_yield": Decimal("0"),
            "nominal_rate": Decimal("4"),
        },
        {
            "currency": Currency.CRC,
            "market_value_crc": Decimal("300"),
            "market_value": Decimal("120"),
            "classification": "active",
            "portfolio_yield": None,
            "nominal_rate": None,
        },
    ]

    assert PortfolioCalculationService.weighted_average_effective_yield(
        positions, Currency.CRC
    ) == Decimal("4.333333333333333333333333333")


def test_weighted_average_effective_yield_falls_back_and_excludes_closed_and_missing_rates() -> (
    None
):
    positions = [
        {
            "currency": Currency.CRC,
            "market_value_crc": Decimal("100"),
            "market_value": Decimal("100"),
            "classification": "active",
            "portfolio_yield": Decimal("0"),
            "nominal_rate": Decimal("4"),
        },
        {
            "currency": Currency.CRC,
            "market_value_crc": Decimal("100"),
            "market_value": Decimal("100"),
            "classification": "active",
            "portfolio_yield": None,
            "nominal_rate": None,
        },
        {
            "currency": Currency.CRC,
            "market_value_crc": Decimal("100"),
            "market_value": Decimal("100"),
            "classification": "closed",
            "portfolio_yield": Decimal("9"),
            "nominal_rate": Decimal("9"),
        },
    ]

    assert PortfolioCalculationService.weighted_average_effective_yield(
        positions, Currency.CRC
    ) == Decimal("4")


def test_institutional_currency_normalization_handles_usd_and_crc_variants() -> None:
    assert PortfolioCalculationService._normalize_institutional_currency("DOLAR") == "USD"
    assert PortfolioCalculationService._normalize_institutional_currency("  dolares  ") == "USD"
    assert PortfolioCalculationService._normalize_institutional_currency("USD") == "USD"
    assert PortfolioCalculationService._normalize_institutional_currency("colon") == "CRC"
    assert PortfolioCalculationService._normalize_institutional_currency("colones") == "CRC"
    assert PortfolioCalculationService._normalize_institutional_currency("CRC") == "CRC"
    assert PortfolioCalculationService._resolve_currency({"currency": "DOLAR"}) == Currency.USD
    assert PortfolioCalculationService._resolve_currency({"currency": "COLON"}) == Currency.CRC
    assert PortfolioCalculationService._resolve_currency({"currency": "COLONES"}) == Currency.CRC
    assert PortfolioCalculationService._resolve_currency({"currency": "CRC"}) == Currency.CRC


def test_currency_exposure_and_mixed_currency_guard() -> None:
    p1 = _position(market="100")
    p2 = Position.create(
        position_id=PositionId.new(),
        isin=ISIN("US5949181045"),
        instrument_name=InstrumentName("Instrument 2"),
        currency=Currency.EUR,
        quantity=Quantity(Decimal("10")),
        nominal_value=NominalValue.from_decimal(Decimal("300"), Currency.EUR),
        acquisition_cost=AcquisitionCost.from_decimal(Decimal("290"), Currency.EUR),
        book_value=BookValue.from_decimal(Decimal("295"), Currency.EUR),
        market_value=MarketValue.from_decimal(Decimal("300"), Currency.EUR),
        yield_rate=YieldRate.from_decimal_percentage(Decimal("3")),
        duration=Duration(Decimal("6")),
        convexity=Convexity(Decimal("14")),
        settlement_date=SettlementDate(BusinessDate(date(2026, 1, 16), CostaRicaCalendar())),
        valuation_source=ValuationSource.MARKET_FEED,
    )

    exposure = PortfolioCalculationService.currency_exposure([p1, p2])
    assert exposure[Currency.USD].amount == Decimal("100")
    assert exposure[Currency.EUR].amount == Decimal("300")

    portfolio = _portfolio()
    portfolio.add_position(p1)
    portfolio.add_position(p2)

    with pytest.raises(Exception):
        portfolio.total_market_value()
