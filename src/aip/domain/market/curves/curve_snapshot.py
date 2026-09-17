from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from ..versioning.snapshot_version import SnapshotVersion
from .market_curve import MarketCurve


@dataclass(frozen=True, slots=True)
class CurveSnapshot:
    """Immutable snapshot for a market curve at a point in time."""

    valuation_date: date
    curve: MarketCurve
    version: SnapshotVersion
    timestamp: datetime
