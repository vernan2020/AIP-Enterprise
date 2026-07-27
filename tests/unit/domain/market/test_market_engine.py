from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from aip.domain.financial_math.curves.curve_point import CurvePoint
from aip.domain.financial_math.curves.yield_curve import YieldCurve
from aip.domain.instruments.bonds.government_bond import GovernmentBond
from aip.domain.instruments.issuers.issuer import Issuer
from aip.domain.instruments.issuers.issuer_type import IssuerType
from aip.domain.market.curves.curve_snapshot import CurveSnapshot
from aip.domain.market.curves.market_curve import MarketCurve
from aip.domain.market.enums.market_type import MarketType
from aip.domain.market.enums.quote_source import QuoteSource
from aip.domain.market.events.quote_updated import QuoteUpdated
from aip.domain.market.events.snapshot_created import SnapshotCreated
from aip.domain.market.exceptions import MarketDataError
from aip.domain.market.providers.market_provider import MarketProvider
from aip.domain.market.quotes.market_quote import MarketQuote
from aip.domain.market.quotes.price_quote import PriceQuote
from aip.domain.market.quotes.yield_quote import YieldQuote
from aip.domain.market.repositories.market_repository import MarketRepository
from aip.domain.market.services.market_service import MarketService
from aip.domain.market.snapshots.market_snapshot import MarketSnapshot
from aip.domain.market.versioning.snapshot_version import SnapshotVersion


class InMemoryMarketRepository(MarketRepository):
    def __init__(self) -> None:
        self._snapshots: list[MarketSnapshot] = []

    def add(self, snapshot: MarketSnapshot) -> None:
        self._snapshots.append(snapshot)

    def get_by_date(self, valuation_date: date) -> list[MarketSnapshot]:
        return [snapshot for snapshot in self._snapshots if snapshot.valuation_date == valuation_date]

    def get_by_market(self, market: str) -> list[MarketSnapshot]:
        return [snapshot for snapshot in self._snapshots if snapshot.market == market]

    def get_by_source(self, source: str) -> list[MarketSnapshot]:
        return [snapshot for snapshot in self._snapshots if snapshot.source == source]

    def get_by_version(self, version: SnapshotVersion) -> list[MarketSnapshot]:
        return [snapshot for snapshot in self._snapshots if snapshot.version == version]

    def get_latest(self, valuation_date: date, market: str, source: str) -> MarketSnapshot | None:
        matches = [
            snapshot
            for snapshot in self._snapshots
            if snapshot.valuation_date == valuation_date
            and snapshot.market == market
            and snapshot.source == source
        ]
        return max(matches, key=lambda item: item.version, default=None)

    def list_all(self) -> list[MarketSnapshot]:
        return list(self._snapshots)


@pytest.fixture
def issuer() -> Issuer:
    return Issuer(code="GOV1", name="Government", issuer_type=IssuerType.GOVERNMENT)


@pytest.fixture
def bond(issuer: Issuer) -> GovernmentBond:
    return GovernmentBond(
        isin="US1234567890",
        name="Treasury Bond",
        issuer=issuer,
        currency="USD",
        settlement_calendar="US",
        business_day_convention="Unadjusted",
        day_count_convention=None,
        issue_date=date(2024, 1, 1),
        settlement_date=date(2024, 1, 3),
        maturity_date=date(2026, 1, 1),
        coupon_schedule=None,
        nominal_value=Decimal("1000"),
        book_value=Decimal("1000"),
        market_value=Decimal("1000"),
        face_value=Decimal("1000"),
        outstanding_amount=Decimal("1000"),
        yield_rate=Decimal("0.05"),
        duration=Decimal("0"),
        modified_duration=Decimal("0"),
        convexity=Decimal("0"),
        dirty_price=Decimal("0"),
        clean_price=Decimal("0"),
        accrued_interest=Decimal("0"),
        coupon_rate=Decimal("0.04"),
    )


def test_snapshot_is_immutable_and_history_is_preserved() -> None:
    repository = InMemoryMarketRepository()
    service = MarketService(repository=repository)
    valuation_date = date(2026, 7, 27)

    first = service.create_snapshot(
        valuation_date=valuation_date,
        market=MarketType.GOVERNMENT.value,
        source=QuoteSource.CENTRAL_BANK.value,
        currency="USD",
        quotes=(
            PriceQuote(instrument_id="US123", currency="USD", market=MarketType.GOVERNMENT.value, source=QuoteSource.CENTRAL_BANK.value, price=Decimal("101.25"), yield_rate=Decimal("0.045"), duration=Decimal("4.5"), convexity=Decimal("22.3"), dv01=Decimal("0.015"), pvbp=Decimal("0.012"), spread=Decimal("0.002")),
        ),
        curves=(
            CurveSnapshot(
                valuation_date=valuation_date,
                curve=MarketCurve(
                    name="USD Curve",
                    currency="USD",
                    market=MarketType.GOVERNMENT.value,
                    source=QuoteSource.CENTRAL_BANK.value,
                    points=(CurvePoint(Decimal("1"), Decimal("0.03")),),
                ),
                version=SnapshotVersion(1, 0, 0),
                timestamp=datetime(2026, 7, 27, 9, 0, 0),
            ),
        ),
    )

    second = service.create_snapshot(
        valuation_date=valuation_date,
        market=MarketType.GOVERNMENT.value,
        source=QuoteSource.CENTRAL_BANK.value,
        currency="USD",
        quotes=(
            PriceQuote(instrument_id="US123", currency="USD", market=MarketType.GOVERNMENT.value, source=QuoteSource.CENTRAL_BANK.value, price=Decimal("102.50"), yield_rate=Decimal("0.046"), duration=Decimal("4.6"), convexity=Decimal("22.8"), dv01=Decimal("0.016"), pvbp=Decimal("0.013"), spread=Decimal("0.003")),
        ),
        curves=(
            CurveSnapshot(
                valuation_date=valuation_date,
                curve=MarketCurve(
                    name="USD Curve",
                    currency="USD",
                    market=MarketType.GOVERNMENT.value,
                    source=QuoteSource.CENTRAL_BANK.value,
                    points=(CurvePoint(Decimal("1"), Decimal("0.03")),),
                ),
                version=SnapshotVersion(1, 0, 0),
                timestamp=datetime(2026, 7, 27, 10, 0, 0),
            ),
        ),
    )

    assert first.version == SnapshotVersion(1, 0, 0)
    assert second.version == SnapshotVersion(1, 0, 1)
    assert second.price == Decimal("102.50")
    assert repository.get_by_date(valuation_date)[0].version == SnapshotVersion(1, 0, 0)
    assert repository.get_by_market(MarketType.GOVERNMENT.value)[1].version == SnapshotVersion(1, 0, 1)
    assert repository.get_by_source(QuoteSource.CENTRAL_BANK.value)[0].source == QuoteSource.CENTRAL_BANK.value
    assert repository.get_by_version(SnapshotVersion(1, 0, 1))[0].version == SnapshotVersion(1, 0, 1)
    assert service.get_latest_snapshot(valuation_date, MarketType.GOVERNMENT.value, QuoteSource.CENTRAL_BANK.value) == second


def test_service_can_create_snapshot_from_instrument_and_pricing_engine(bond: GovernmentBond) -> None:
    repository = InMemoryMarketRepository()
    service = MarketService(repository=repository)

    snapshot = service.create_snapshot_from_instrument(
        valuation_date=date(2026, 7, 27),
        instrument=bond,
        market=MarketType.GOVERNMENT.value,
        source=QuoteSource.MARKET_MAKER.value,
        currency="USD",
    )

    assert snapshot.currency == "USD"
    assert snapshot.quotes[0].price >= Decimal("0")
    assert snapshot.quotes[0].yield_rate == Decimal("0.05")
    assert snapshot.curves[0].curve.currency == "USD"
    assert snapshot.version == SnapshotVersion(1, 0, 0)


def test_quote_variants_and_events_are_value_objects() -> None:
    quote = PriceQuote(instrument_id="US123", currency="EUR", market=MarketType.INTERBANK.value, source=QuoteSource.BROKER.value, price=Decimal("100"), yield_rate=Decimal("0.02"), duration=Decimal("3"), convexity=Decimal("10"), dv01=Decimal("0.01"), pvbp=Decimal("0.02"), spread=Decimal("0.005"))
    yield_quote = YieldQuote(instrument_id="US124", currency="USD", market=MarketType.GOVERNMENT.value, source=QuoteSource.CENTRAL_BANK.value, price=Decimal("99"), yield_rate=Decimal("0.03"), duration=Decimal("2"), convexity=Decimal("8"), dv01=Decimal("0.02"), pvbp=Decimal("0.03"), spread=Decimal("0.004"))

    assert quote.price == Decimal("100")
    assert yield_quote.yield_rate == Decimal("0.03")
    assert quote.to_dict()["price"] == Decimal("100")
    assert yield_quote.to_dict()["yield_rate"] == Decimal("0.03")

    event = SnapshotCreated(snapshot_id="snap-1")
    quote_event = QuoteUpdated(quote_id="q-1")
    assert event.snapshot_id == "snap-1"
    assert quote_event.quote_id == "q-1"


def test_market_repository_contract_requires_implementation() -> None:
    with pytest.raises(TypeError):
        MarketRepository()


def test_market_data_error_is_raised_for_invalid_snapshot() -> None:
    with pytest.raises(MarketDataError):
        MarketSnapshot(
            valuation_date=date(2026, 7, 27),
            market=MarketType.GOVERNMENT.value,
            source=QuoteSource.CENTRAL_BANK.value,
            currency="USD",
            quotes=(),
            curves=(),
            version=SnapshotVersion(1, 0, 0),
            timestamp=datetime(2026, 7, 27, 9, 0, 0),
        )

    with pytest.raises(MarketDataError):
        MarketSnapshot(
            valuation_date=date(2026, 7, 27),
            market="",
            source=QuoteSource.CENTRAL_BANK.value,
            currency="USD",
            quotes=(PriceQuote(instrument_id="US123", currency="USD", market=MarketType.GOVERNMENT.value, source=QuoteSource.CENTRAL_BANK.value, price=Decimal("100"), yield_rate=Decimal("0.03"), duration=Decimal("1"), convexity=Decimal("2"), dv01=Decimal("0.01"), pvbp=Decimal("0.02"), spread=Decimal("0.001")),),
            curves=(CurveSnapshot(valuation_date=date(2026, 7, 27), curve=MarketCurve(name="USD Curve", currency="USD", market=MarketType.GOVERNMENT.value, source=QuoteSource.CENTRAL_BANK.value, points=(CurvePoint(Decimal("1"), Decimal("0.03")),)), version=SnapshotVersion(1, 0, 0), timestamp=datetime(2026, 7, 27, 9, 0, 0)),),
            version=SnapshotVersion(1, 0, 0),
            timestamp=datetime(2026, 7, 27, 9, 0, 0),
        )

    with pytest.raises(MarketDataError):
        MarketSnapshot(
            valuation_date=date(2026, 7, 27),
            market=MarketType.GOVERNMENT.value,
            source="",
            currency="USD",
            quotes=(PriceQuote(instrument_id="US123", currency="USD", market=MarketType.GOVERNMENT.value, source=QuoteSource.CENTRAL_BANK.value, price=Decimal("100"), yield_rate=Decimal("0.03"), duration=Decimal("1"), convexity=Decimal("2"), dv01=Decimal("0.01"), pvbp=Decimal("0.02"), spread=Decimal("0.001")),),
            curves=(CurveSnapshot(valuation_date=date(2026, 7, 27), curve=MarketCurve(name="USD Curve", currency="USD", market=MarketType.GOVERNMENT.value, source=QuoteSource.CENTRAL_BANK.value, points=(CurvePoint(Decimal("1"), Decimal("0.03")),)), version=SnapshotVersion(1, 0, 0), timestamp=datetime(2026, 7, 27, 9, 0, 0)),),
            version=SnapshotVersion(1, 0, 0),
            timestamp=datetime(2026, 7, 27, 9, 0, 0),
        )

    with pytest.raises(MarketDataError):
        MarketSnapshot(
            valuation_date=date(2026, 7, 27),
            market=MarketType.GOVERNMENT.value,
            source=QuoteSource.CENTRAL_BANK.value,
            currency="",
            quotes=(PriceQuote(instrument_id="US123", currency="USD", market=MarketType.GOVERNMENT.value, source=QuoteSource.CENTRAL_BANK.value, price=Decimal("100"), yield_rate=Decimal("0.03"), duration=Decimal("1"), convexity=Decimal("2"), dv01=Decimal("0.01"), pvbp=Decimal("0.02"), spread=Decimal("0.001")),),
            curves=(CurveSnapshot(valuation_date=date(2026, 7, 27), curve=MarketCurve(name="USD Curve", currency="USD", market=MarketType.GOVERNMENT.value, source=QuoteSource.CENTRAL_BANK.value, points=(CurvePoint(Decimal("1"), Decimal("0.03")),)), version=SnapshotVersion(1, 0, 0), timestamp=datetime(2026, 7, 27, 9, 0, 0)),),
            version=SnapshotVersion(1, 0, 0),
            timestamp=datetime(2026, 7, 27, 9, 0, 0),
        )


def test_market_curve_validation_and_zero_rate_lookup() -> None:
    with pytest.raises(ValueError):
        MarketCurve(name="", currency="USD", market=MarketType.GOVERNMENT.value, source=QuoteSource.CENTRAL_BANK.value, points=(CurvePoint(Decimal("1"), Decimal("0.03")),))
    with pytest.raises(ValueError):
        MarketCurve(name="USD Curve", currency="", market=MarketType.GOVERNMENT.value, source=QuoteSource.CENTRAL_BANK.value, points=(CurvePoint(Decimal("1"), Decimal("0.03")),))
    with pytest.raises(ValueError):
        MarketCurve(name="USD Curve", currency="USD", market="", source=QuoteSource.CENTRAL_BANK.value, points=(CurvePoint(Decimal("1"), Decimal("0.03")),))
    with pytest.raises(ValueError):
        MarketCurve(name="USD Curve", currency="USD", market=MarketType.GOVERNMENT.value, source="", points=(CurvePoint(Decimal("1"), Decimal("0.03")),))
    with pytest.raises(ValueError):
        MarketCurve(name="USD Curve", currency="USD", market=MarketType.GOVERNMENT.value, source=QuoteSource.CENTRAL_BANK.value, points=())

    curve = MarketCurve(
        name="USD Curve",
        currency="USD",
        market=MarketType.GOVERNMENT.value,
        source=QuoteSource.CENTRAL_BANK.value,
        points=(CurvePoint(Decimal("1"), Decimal("0.03")), CurvePoint(Decimal("2"), Decimal("0.04"))),
    )
    assert curve.zero_rate(Decimal("1")) == Decimal("0.03")
    with pytest.raises(KeyError):
        curve.zero_rate(Decimal("3"))


def test_snapshot_version_helpers_and_market_provider() -> None:
    version = SnapshotVersion(1, 0, 0)
    assert version.next_patch() == SnapshotVersion(1, 0, 1)
    assert version.next_minor() == SnapshotVersion(1, 1, 0)
    assert version.next_major() == SnapshotVersion(2, 0, 0)

    class TestMarketProvider(MarketProvider):
        def get_spot_rate(self, currency: str, tenor: Decimal) -> Decimal:
            return Decimal("0.02")

    provider = TestMarketProvider()
    assert provider.get_spot_rate("USD", Decimal("1")) == Decimal("0.02")


def test_service_advances_version_for_existing_snapshot() -> None:
    repository = InMemoryMarketRepository()
    service = MarketService(repository=repository)
    with pytest.raises(MarketDataError):
        service.create_snapshot(
            valuation_date=date(2026, 7, 28),
            market=MarketType.GOVERNMENT.value,
            source=QuoteSource.CENTRAL_BANK.value,
            currency="USD",
            quotes=(),
            curves=(CurveSnapshot(valuation_date=date(2026, 7, 28), curve=MarketCurve(name="USD Curve", currency="USD", market=MarketType.GOVERNMENT.value, source=QuoteSource.CENTRAL_BANK.value, points=(CurvePoint(Decimal("1"), Decimal("0.03")),)), version=SnapshotVersion(1, 0, 0), timestamp=datetime(2026, 7, 28, 9, 0, 0)),),
        )
    with pytest.raises(MarketDataError):
        service.create_snapshot(
            valuation_date=date(2026, 7, 28),
            market=MarketType.GOVERNMENT.value,
            source=QuoteSource.CENTRAL_BANK.value,
            currency="USD",
            quotes=(PriceQuote(instrument_id="US123", currency="USD", market=MarketType.GOVERNMENT.value, source=QuoteSource.CENTRAL_BANK.value, price=Decimal("100"), yield_rate=Decimal("0.03"), duration=Decimal("1"), convexity=Decimal("2"), dv01=Decimal("0.01"), pvbp=Decimal("0.02"), spread=Decimal("0.001")),),
            curves=(),
        )

    first = service.create_snapshot(
        valuation_date=date(2026, 7, 28),
        market=MarketType.GOVERNMENT.value,
        source=QuoteSource.CENTRAL_BANK.value,
        currency="USD",
        quotes=(PriceQuote(instrument_id="US123", currency="USD", market=MarketType.GOVERNMENT.value, source=QuoteSource.CENTRAL_BANK.value, price=Decimal("100"), yield_rate=Decimal("0.03"), duration=Decimal("1"), convexity=Decimal("2"), dv01=Decimal("0.01"), pvbp=Decimal("0.02"), spread=Decimal("0.001")),),
        curves=(CurveSnapshot(valuation_date=date(2026, 7, 28), curve=MarketCurve(name="USD Curve", currency="USD", market=MarketType.GOVERNMENT.value, source=QuoteSource.CENTRAL_BANK.value, points=(CurvePoint(Decimal("1"), Decimal("0.03")),)), version=SnapshotVersion(1, 0, 0), timestamp=datetime(2026, 7, 28, 9, 0, 0)),),
        version=SnapshotVersion(1, 0, 1),
    )
    second = service.create_snapshot(
        valuation_date=date(2026, 7, 28),
        market=MarketType.GOVERNMENT.value,
        source=QuoteSource.CENTRAL_BANK.value,
        currency="USD",
        quotes=(PriceQuote(instrument_id="US123", currency="USD", market=MarketType.GOVERNMENT.value, source=QuoteSource.CENTRAL_BANK.value, price=Decimal("101"), yield_rate=Decimal("0.04"), duration=Decimal("2"), convexity=Decimal("3"), dv01=Decimal("0.02"), pvbp=Decimal("0.03"), spread=Decimal("0.002")),),
        curves=(CurveSnapshot(valuation_date=date(2026, 7, 28), curve=MarketCurve(name="USD Curve", currency="USD", market=MarketType.GOVERNMENT.value, source=QuoteSource.CENTRAL_BANK.value, points=(CurvePoint(Decimal("1"), Decimal("0.03")),)), version=SnapshotVersion(1, 0, 0), timestamp=datetime(2026, 7, 28, 10, 0, 0)),),
        version=SnapshotVersion(1, 0, 0),
    )

    assert first.version == SnapshotVersion(1, 0, 1)
    assert second.version == SnapshotVersion(1, 0, 2)

    snapshot = repository.get_latest(date(2026, 7, 28), MarketType.GOVERNMENT.value, QuoteSource.CENTRAL_BANK.value)
    assert snapshot is not None
    assert snapshot.price == Decimal("101")
    assert snapshot.yield_rate == Decimal("0.04")
    assert snapshot.get_quote("US123") is not None
    assert snapshot.get_quote("MISSING") is None
