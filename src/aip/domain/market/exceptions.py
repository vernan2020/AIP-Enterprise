from __future__ import annotations


class MarketDataError(Exception):
    """Base exception for market data domain errors."""


class MarketSnapshotError(MarketDataError):
    """Raised when a market snapshot violates invariants."""
