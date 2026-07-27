from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from aip.domain.market.snapshots.market_snapshot import MarketSnapshot
from aip.domain.market.versioning.snapshot_version import SnapshotVersion


class MarketRepository(ABC):
    """Repository abstraction for market snapshots."""

    @abstractmethod
    def add(self, snapshot: MarketSnapshot) -> None:
        """Persist a new snapshot."""

    @abstractmethod
    def get_by_date(self, valuation_date: date) -> list[MarketSnapshot]:
        """Retrieve snapshots by valuation date."""

    @abstractmethod
    def get_by_market(self, market: str) -> list[MarketSnapshot]:
        """Retrieve snapshots by market."""

    @abstractmethod
    def get_by_source(self, source: str) -> list[MarketSnapshot]:
        """Retrieve snapshots by source."""

    @abstractmethod
    def get_by_version(self, version: SnapshotVersion) -> list[MarketSnapshot]:
        """Retrieve snapshots by version."""

    @abstractmethod
    def get_latest(self, valuation_date: date, market: str, source: str) -> MarketSnapshot | None:
        """Retrieve the latest snapshot for the supplied keys."""

    @abstractmethod
    def list_all(self) -> list[MarketSnapshot]:
        """List all stored snapshots."""
