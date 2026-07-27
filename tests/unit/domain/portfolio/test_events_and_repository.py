"""Tests for domain events and repository abstraction."""

from abc import ABC
from datetime import date
from decimal import Decimal

from src.aip.domain.portfolio.entities import Portfolio, Position
from src.aip.domain.portfolio.enums import PortfolioStatus, ValuationSource
from src.aip.domain.portfolio.events import DomainEvent, PortfolioCreated
from src.aip.domain.portfolio.repositories import PortfolioRepository
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
    YieldRate,
)
from src.aip.shared.calendars import CostaRicaCalendar
from src.aip.shared.dates import BusinessDate
from src.aip.shared.math import Percentage
from src.aip.shared.money import Currency


def _position() -> Position:
    return Position.create(
        position_id=PositionId.new(),
        isin=ISIN("US0378331005"),
        instrument_name=InstrumentName("Instrument"),
        currency=Currency.USD,
        quantity=Quantity(Decimal("10")),
        nominal_value=NominalValue.from_decimal(Decimal("100"), Currency.USD),
        acquisition_cost=AcquisitionCost.from_decimal(Decimal("99"), Currency.USD),
        book_value=BookValue.from_decimal(Decimal("100"), Currency.USD),
        market_value=MarketValue.from_decimal(Decimal("100"), Currency.USD),
        yield_rate=YieldRate(Percentage(Decimal("5"))),
        duration=Duration(Decimal("4")),
        convexity=Convexity(Decimal("8")),
        settlement_date=SettlementDate(BusinessDate(date(2026, 1, 10), CostaRicaCalendar())),
        valuation_source=ValuationSource.MARKET_FEED,
    )


def test_domain_event_create_contains_required_fields() -> None:
    event = DomainEvent.create(
        aggregate_id="agg-1",
        event_type="portfolio.test",
        payload={"key": "value"},
    )

    assert event.event_id
    assert event.occurred_at is not None
    assert event.aggregate_id == "agg-1"
    assert event.event_type == "portfolio.test"
    assert event.payload["key"] == "value"


def test_specific_event_from_payload_has_expected_type() -> None:
    event = PortfolioCreated.from_payload("agg-2", {"name": "p1"})
    assert event.event_type == "portfolio.created"
    assert event.aggregate_id == "agg-2"


def test_repository_is_abstract_contract() -> None:
    assert issubclass(PortfolioRepository, ABC)


class InMemoryPortfolioRepository(PortfolioRepository):
    def __init__(self) -> None:
        self._items: dict[str, Portfolio] = {}

    def add(self, portfolio: Portfolio) -> None:
        self._items[str(portfolio.portfolio_id)] = portfolio

    def update(self, portfolio: Portfolio) -> None:
        self._items[str(portfolio.portfolio_id)] = portfolio

    def get_by_id(self, portfolio_id: PortfolioId) -> Portfolio | None:
        return self._items.get(str(portfolio_id))

    def get_by_name(self, name: str) -> Portfolio | None:
        for item in self._items.values():
            if item.name == name:
                return item
        return None

    def list_all(self) -> list[Portfolio]:
        return list(self._items.values())

    def list_active(self) -> list[Portfolio]:
        return [item for item in self._items.values() if item.status == PortfolioStatus.ACTIVE]

    def exists(self, portfolio_id: PortfolioId) -> bool:
        return str(portfolio_id) in self._items

    def delete(self, portfolio_id: PortfolioId) -> None:
        self._items.pop(str(portfolio_id), None)


def test_repository_contract_can_be_implemented() -> None:
    repo = InMemoryPortfolioRepository()
    portfolio = Portfolio.create(PortfolioId.new(), "P1", "Desc", Currency.USD)
    portfolio.add_position(_position())
    repo.add(portfolio)

    assert repo.exists(portfolio.portfolio_id)
    assert repo.get_by_name("P1") is not None
    assert len(repo.list_all()) == 1

    portfolio.activate()
    repo.update(portfolio)
    assert len(repo.list_active()) == 1

    repo.delete(portfolio.portfolio_id)
    assert repo.get_by_id(portfolio.portfolio_id) is None
