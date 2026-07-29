"""Tests for Position entity."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from src.aip.domain.portfolio.entities.position import Position
from src.aip.domain.portfolio.enums.position_status import PositionStatus
from src.aip.domain.portfolio.enums.valuation_source import ValuationSource
from src.aip.domain.portfolio.exceptions import InvalidPositionError
from src.aip.domain.portfolio.value_objects import (
    ISIN,
    AcquisitionCost,
    BookValue,
    Convexity,
    Duration,
    InstrumentName,
    MarketValue,
    NominalValue,
    PositionId,
    Quantity,
    SettlementDate,
    YieldRate,
)
from src.aip.shared.calendars import CostaRicaCalendar
from src.aip.shared.dates import BusinessDate
from src.aip.shared.math import Percentage
from src.aip.shared.money import Currency, Money


def _position() -> Position:
    calendar = CostaRicaCalendar()
    return Position.create(
        position_id=PositionId.new(),
        isin=ISIN("US0378331005"),
        instrument_name=InstrumentName("Apple Bond"),
        currency=Currency.USD,
        quantity=Quantity(Decimal("10")),
        nominal_value=NominalValue(Money(Decimal("1000"), Currency.USD)),
        acquisition_cost=AcquisitionCost(Money(Decimal("980"), Currency.USD)),
        book_value=BookValue(Money(Decimal("990"), Currency.USD)),
        market_value=MarketValue(Money(Decimal("995"), Currency.USD)),
        yield_rate=YieldRate(Percentage(Decimal("4.2"))),
        duration=Duration(Decimal("5.2")),
        convexity=Convexity(Decimal("11.8")),
        settlement_date=SettlementDate(BusinessDate(date(2026, 1, 15), calendar)),
        valuation_source=ValuationSource.MARKET_FEED,
    )


def test_position_creation_defaults_to_open_status() -> None:
    position = _position()
    assert position.status == PositionStatus.OPEN


def test_position_business_key_contains_isin_settlement_and_currency() -> None:
    position = _position()
    key = position.business_key()
    assert key[0] == "US0378331005"
    assert key[2] == "USD"


def test_update_market_valuation() -> None:
    position = _position()
    now = datetime.now(timezone.utc)

    position.update_market_valuation(
        market_value=MarketValue(Money(Decimal("1001"), Currency.USD)),
        valuation_source=ValuationSource.MANUAL,
        valued_at=now,
    )

    assert position.market_value.amount == Decimal("1001")
    assert position.valuation_source == ValuationSource.MANUAL
    assert position.last_valuation_timestamp == now


def test_update_book_value_yield_duration_and_convexity() -> None:
    position = _position()
    now = datetime.now(timezone.utc)

    position.update_book_value(BookValue(Money(Decimal("1000"), Currency.USD)), now)
    position.update_yield(YieldRate(Percentage(Decimal("4.3"))), now)
    position.update_duration(Duration(Decimal("5.1")), now)
    position.update_convexity(Convexity(Decimal("12.0")), now)

    assert position.book_value.amount == Decimal("1000")
    assert position.yield_rate.value.value == Decimal("4.3")
    assert position.duration.value == Decimal("5.1")
    assert position.convexity.value == Decimal("12.0")


def test_closed_position_rejects_updates() -> None:
    position = _position()
    position.close_position()

    with pytest.raises(InvalidPositionError):
        position.update_yield(YieldRate(Percentage(Decimal("5"))), datetime.now(timezone.utc))


def test_currency_mismatch_rejected() -> None:
    with pytest.raises(InvalidPositionError):
        Position.create(
            position_id=PositionId.new(),
            isin=ISIN("US0378331005"),
            instrument_name=InstrumentName("Apple Bond"),
            currency=Currency.USD,
            quantity=Quantity(Decimal("10")),
            nominal_value=NominalValue(Money(Decimal("1000"), Currency.EUR)),
            acquisition_cost=AcquisitionCost(Money(Decimal("980"), Currency.USD)),
            book_value=BookValue(Money(Decimal("990"), Currency.USD)),
            market_value=MarketValue(Money(Decimal("995"), Currency.USD)),
            yield_rate=YieldRate(Percentage(Decimal("4.2"))),
            duration=Duration(Decimal("5.2")),
            convexity=Convexity(Decimal("11.8")),
            settlement_date=SettlementDate(BusinessDate(date(2026, 1, 15), CostaRicaCalendar())),
            valuation_source=ValuationSource.MARKET_FEED,
        )
