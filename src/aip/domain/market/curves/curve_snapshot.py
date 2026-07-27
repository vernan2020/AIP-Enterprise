from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from aip.domain.market.curves.market_curve import MarketCurve
from aip.domain.market.versioning.snapshot_version import SnapshotVersion


@dataclass(frozen=True, slots=True)
class CurveSnapshot:
    """Immutable snapshot for a market curve at a point in time."""

    valuation_date: date
    curve: MarketCurve
    version: SnapshotVersion
    timestamp: datetime
