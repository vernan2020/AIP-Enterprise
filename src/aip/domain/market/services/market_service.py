from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from aip.domain.financial_math.curves.curve_point import CurvePoint
from aip.domain.instruments.base.financial_instrument import FinancialInstrument
from aip.domain.market.curves.curve_snapshot import CurveSnapshot
from aip.domain.market.curves.market_curve import MarketCurve
from aip.domain.market.exceptions import MarketSnapshotError
from aip.domain.market.quotes.market_quote import MarketQuote
from aip.domain.market.repositories.market_repository import MarketRepository
from aip.domain.market.snapshots.market_snapshot import MarketSnapshot
from aip.domain.market.versioning.snapshot_version import SnapshotVersion


class MarketService:
    """Application service for creating and retrieving market snapshots."""

    def __init__(self, repository: MarketRepository) -> None:
        self._repository = repository

    def create_snapshot(
        self,
        valuation_date: date,
        market: str,
        source: str,
        currency: str,
        quotes: tuple[MarketQuote, ...],
        curves: tuple[CurveSnapshot, ...],
        version: SnapshotVersion | None = None,
        timestamp: datetime | None = None,
    ) -> MarketSnapshot:
        if not quotes:
            raise MarketSnapshotError("At least one quote is required")
        if not curves:
            raise MarketSnapshotError("At least one curve is required")
        effective_version = version or SnapshotVersion(1, 0, 0)
        latest = self._repository.get_latest(valuation_date, market, source)
        if latest is not None and effective_version == latest.version:
            effective_version = latest.version.next_patch()
        if latest is not None and effective_version < latest.version:
            effective_version = latest.version.next_patch()
        snapshot = MarketSnapshot(
            valuation_date=valuation_date,
            market=market,
            source=source,
            currency=currency,
            quotes=quotes,
            curves=curves,
            version=effective_version,
            timestamp=timestamp or datetime.now(),
        )
        self._repository.add(snapshot)
        return snapshot

    def create_snapshot_from_instrument(
        self,
        valuation_date: date,
        instrument: FinancialInstrument,
        market: str,
        source: str,
        currency: str,
    ) -> MarketSnapshot:
        quote = MarketQuote(
            instrument_id=instrument.isin,
            currency=currency,
            market=market,
            source=source,
            price=instrument.market_value or Decimal("0"),
            yield_rate=instrument.yield_rate or Decimal("0"),
            duration=instrument.duration or Decimal("0"),
            convexity=instrument.convexity or Decimal("0"),
            dv01=Decimal("0"),
            pvbp=Decimal("0"),
            spread=Decimal("0"),
        )
        curve = CurveSnapshot(
            valuation_date=valuation_date,
            curve=MarketCurve(
                name=f"{currency} Curve",
                currency=currency,
                market=market,
                source=source,
                points=(CurvePoint(Decimal("1"), Decimal("0.03")),),
            ),
            version=SnapshotVersion(1, 0, 0),
            timestamp=datetime.now(),
        )
        return self.create_snapshot(
            valuation_date=valuation_date,
            market=market,
            source=source,
            currency=currency,
            quotes=(quote,),
            curves=(curve,),
        )

    def get_latest_snapshot(
        self, valuation_date: date, market: str, source: str
    ) -> MarketSnapshot | None:
        return self._repository.get_latest(valuation_date, market, source)
