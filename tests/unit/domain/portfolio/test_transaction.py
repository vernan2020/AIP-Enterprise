"""Tests for Transaction entity and factories."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from src.aip.domain.portfolio.entities.transaction import Transaction
from src.aip.domain.portfolio.enums.transaction_type import TransactionType
from src.aip.domain.portfolio.exceptions import InvalidTransactionError
from src.aip.domain.portfolio.value_objects import (
    PortfolioId,
    PositionId,
    Quantity,
    SettlementDate,
    TransactionId,
)
from src.aip.shared.calendars import CostaRicaCalendar
from src.aip.shared.dates import BusinessDate
from src.aip.shared.money import Currency, Money


def _settlement() -> SettlementDate:
    return SettlementDate(BusinessDate(date(2026, 2, 2), CostaRicaCalendar()))


def test_buy_factory_applies_negative_signs() -> None:
    tx = Transaction.buy(
        transaction_id=TransactionId.new(),
        portfolio_id=PortfolioId.new(),
        position_id=PositionId.new(),
        trade_date=date(2026, 1, 30),
        settlement_date=_settlement(),
        quantity=Quantity(Decimal("5")),
        nominal_amount=Decimal("1000"),
        gross_amount=Decimal("1000"),
        fees=Decimal("5"),
        taxes=Decimal("2"),
        currency=Currency.USD,
        reference="BUY-001",
    )

    assert tx.transaction_type == TransactionType.BUY
    assert tx.gross_amount.amount < 0
    assert tx.net_amount.amount == Decimal("-1007.00")


def test_sell_factory_applies_positive_signs() -> None:
    tx = Transaction.sell(
        transaction_id=TransactionId.new(),
        portfolio_id=PortfolioId.new(),
        position_id=PositionId.new(),
        trade_date=date(2026, 1, 30),
        settlement_date=_settlement(),
        quantity=Quantity(Decimal("5")),
        nominal_amount=Decimal("1000"),
        gross_amount=Decimal("1000"),
        fees=Decimal("5"),
        taxes=Decimal("2"),
        currency=Currency.USD,
        reference="SELL-001",
    )

    assert tx.transaction_type == TransactionType.SELL
    assert tx.gross_amount.amount > 0
    assert tx.net_amount.amount == Decimal("993.00")


def test_coupon_maturity_adjustment_factories() -> None:
    coupon = Transaction.coupon(
        transaction_id=TransactionId.new(),
        portfolio_id=PortfolioId.new(),
        position_id=PositionId.new(),
        trade_date=date(2026, 1, 30),
        settlement_date=_settlement(),
        quantity=Quantity(Decimal("1")),
        gross_amount=Decimal("35"),
        fees=Decimal("0"),
        taxes=Decimal("3"),
        currency=Currency.USD,
        reference="CPN-001",
    )
    assert coupon.net_amount.amount == Decimal("32.00")

    maturity = Transaction.maturity(
        transaction_id=TransactionId.new(),
        portfolio_id=PortfolioId.new(),
        position_id=PositionId.new(),
        trade_date=date(2026, 1, 30),
        settlement_date=_settlement(),
        quantity=Quantity(Decimal("1")),
        nominal_amount=Decimal("100"),
        gross_amount=Decimal("100"),
        fees=Decimal("0"),
        taxes=Decimal("0"),
        currency=Currency.USD,
        reference="MAT-001",
    )
    assert maturity.net_amount.amount == Decimal("100.00")

    adjustment = Transaction.adjustment(
        transaction_id=TransactionId.new(),
        portfolio_id=PortfolioId.new(),
        position_id=PositionId.new(),
        trade_date=date(2026, 1, 30),
        settlement_date=_settlement(),
        quantity=Quantity(Decimal("1")),
        nominal_amount=Decimal("-25"),
        gross_amount=Decimal("-25"),
        fees=Decimal("0"),
        taxes=Decimal("0"),
        currency=Currency.USD,
        reference="ADJ-001",
    )
    assert adjustment.transaction_type == TransactionType.ADJUSTMENT


def test_invalid_sign_consistency_rejected() -> None:
    with pytest.raises(InvalidTransactionError):
        Transaction(
            transaction_id=TransactionId.new(),
            portfolio_id=PortfolioId.new(),
            position_id=PositionId.new(),
            transaction_type=TransactionType.BUY,
            trade_date=date(2026, 1, 30),
            settlement_date=_settlement(),
            quantity=Quantity(Decimal("1")),
            nominal_amount=Money(Decimal("100"), Currency.USD),
            gross_amount=Money(Decimal("100"), Currency.USD),
            fees=Money(Decimal("1"), Currency.USD),
            taxes=Money(Decimal("1"), Currency.USD),
            net_amount=Money(Decimal("98"), Currency.USD),
            currency=Currency.USD,
            reference="BAD-001",
            created_at=datetime.now(timezone.utc),
        )


def test_net_amount_formula_must_match() -> None:
    with pytest.raises(InvalidTransactionError):
        Transaction(
            transaction_id=TransactionId.new(),
            portfolio_id=PortfolioId.new(),
            position_id=PositionId.new(),
            transaction_type=TransactionType.SELL,
            trade_date=date(2026, 1, 30),
            settlement_date=_settlement(),
            quantity=Quantity(Decimal("1")),
            nominal_amount=Money(Decimal("100"), Currency.USD),
            gross_amount=Money(Decimal("100"), Currency.USD),
            fees=Money(Decimal("1"), Currency.USD),
            taxes=Money(Decimal("1"), Currency.USD),
            net_amount=Money(Decimal("100"), Currency.USD),
            currency=Currency.USD,
            reference="BAD-002",
            created_at=datetime.now(timezone.utc),
        )


def test_negative_fees_rejected() -> None:
    with pytest.raises(InvalidTransactionError):
        Transaction(
            transaction_id=TransactionId.new(),
            portfolio_id=PortfolioId.new(),
            position_id=PositionId.new(),
            transaction_type=TransactionType.SELL,
            trade_date=date(2026, 1, 30),
            settlement_date=_settlement(),
            quantity=Quantity(Decimal("1")),
            nominal_amount=Money(Decimal("100"), Currency.USD),
            gross_amount=Money(Decimal("100"), Currency.USD),
            fees=Money(Decimal("-1"), Currency.USD),
            taxes=Money(Decimal("1"), Currency.USD),
            net_amount=Money(Decimal("100"), Currency.USD),
            currency=Currency.USD,
            reference="BAD-003",
            created_at=datetime.now(timezone.utc),
        )


def test_empty_reference_rejected() -> None:
    with pytest.raises(InvalidTransactionError):
        Transaction(
            transaction_id=TransactionId.new(),
            portfolio_id=PortfolioId.new(),
            position_id=PositionId.new(),
            transaction_type=TransactionType.SELL,
            trade_date=date(2026, 1, 30),
            settlement_date=_settlement(),
            quantity=Quantity(Decimal("1")),
            nominal_amount=Money(Decimal("100"), Currency.USD),
            gross_amount=Money(Decimal("100"), Currency.USD),
            fees=Money(Decimal("1"), Currency.USD),
            taxes=Money(Decimal("1"), Currency.USD),
            net_amount=Money(Decimal("98"), Currency.USD),
            currency=Currency.USD,
            reference="",
            created_at=datetime.now(timezone.utc),
        )


def test_adjustment_zero_nominal_and_gross_rejected() -> None:
    with pytest.raises(InvalidTransactionError):
        Transaction.adjustment(
            transaction_id=TransactionId.new(),
            portfolio_id=PortfolioId.new(),
            position_id=PositionId.new(),
            trade_date=date(2026, 1, 30),
            settlement_date=_settlement(),
            quantity=Quantity(Decimal("1")),
            nominal_amount=Decimal("0"),
            gross_amount=Decimal("0"),
            fees=Decimal("0"),
            taxes=Decimal("0"),
            currency=Currency.USD,
            reference="ADJ-0",
        )
