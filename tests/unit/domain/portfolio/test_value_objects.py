"""Tests for portfolio value objects."""

from datetime import date
from decimal import Decimal

import pytest

from src.aip.domain.portfolio.exceptions import InvalidPositionError
from src.aip.domain.portfolio.value_objects import (
    AcquisitionCost,
    BookValue,
    Convexity,
    Duration,
    InstrumentName,
    ISIN,
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
from src.aip.shared.math import Percentage
from src.aip.shared.money import Currency, Money


def test_id_generation_and_parsing_roundtrip() -> None:
    portfolio_id = PortfolioId.new()
    parsed = PortfolioId.from_string(str(portfolio_id))
    assert parsed == portfolio_id

    position_id = PositionId.new()
    parsed_position = PositionId.from_string(str(position_id))
    assert parsed_position == position_id

    transaction_id = TransactionId.new()
    parsed_transaction = TransactionId.from_string(str(transaction_id))
    assert parsed_transaction == transaction_id


def test_isin_valid_checksum_accepts_known_code() -> None:
    assert ISIN("US0378331005").value == "US0378331005"


def test_isin_invalid_structure_rejected() -> None:
    with pytest.raises(InvalidPositionError):
        ISIN("BAD")


def test_isin_invalid_checksum_rejected() -> None:
    with pytest.raises(InvalidPositionError):
        ISIN("US0378331004")


def test_instrument_name_normalizes_and_validates() -> None:
    name = InstrumentName("  Treasury Bond  ")
    assert name.value == "Treasury Bond"

    with pytest.raises(InvalidPositionError):
        InstrumentName("   ")


def test_quantity_positive_required() -> None:
    assert Quantity(Decimal("10")).value == Decimal("10")

    with pytest.raises(InvalidPositionError):
        Quantity(Decimal("0"))


def test_money_based_value_objects_reject_negative() -> None:
    with pytest.raises(InvalidPositionError):
        NominalValue(Money(Decimal("-1"), Currency.USD))

    with pytest.raises(InvalidPositionError):
        MarketValue(Money(Decimal("-1"), Currency.USD))

    with pytest.raises(InvalidPositionError):
        BookValue(Money(Decimal("-1"), Currency.USD))

    with pytest.raises(InvalidPositionError):
        AcquisitionCost(Money(Decimal("-1"), Currency.USD))


def test_money_based_value_objects_from_decimal() -> None:
    nominal = NominalValue.from_decimal(Decimal("100"), Currency.USD)
    market = MarketValue.from_decimal(Decimal("95"), Currency.USD)
    book = BookValue.from_decimal(Decimal("97"), Currency.USD)
    acq = AcquisitionCost.from_decimal(Decimal("90"), Currency.USD)

    assert nominal.amount == Decimal("100")
    assert market.currency == Currency.USD
    assert book.amount == Decimal("97")
    assert acq.currency == Currency.USD


def test_yield_rate_boundaries() -> None:
    assert YieldRate(Percentage(Decimal("5.25"))).decimal == Decimal("0.0525")

    with pytest.raises(InvalidPositionError):
        YieldRate(Percentage(Decimal("-100.01")))

    with pytest.raises(InvalidPositionError):
        YieldRate(Percentage(Decimal("1000.01")))


def test_duration_and_convexity_boundaries() -> None:
    assert Duration(Decimal("4.5")).value == Decimal("4.5")
    assert Convexity(Decimal("10")).value == Decimal("10")

    with pytest.raises(InvalidPositionError):
        Duration(Decimal("-0.1"))

    with pytest.raises(InvalidPositionError):
        Convexity(Decimal("-0.1"))


def test_settlement_date_wraps_business_date() -> None:
    calendar = CostaRicaCalendar()
    settlement = SettlementDate(BusinessDate(date(2026, 1, 12), calendar))
    assert settlement.date == date(2026, 1, 12)


def test_decimal_precision_not_lost_in_money_wrappers() -> None:
    value = NominalValue(Money(Decimal("123456789.123456"), Currency.USD))
    assert value.amount == Decimal("123456789.123456")
