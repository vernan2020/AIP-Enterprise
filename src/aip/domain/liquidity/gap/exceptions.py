from __future__ import annotations


class LiquidityGapError(Exception):
    """Raised for invalid or unsupported liquidity gap operations."""


class GapError(LiquidityGapError):
    """Raised for invalid or unsupported liquidity gap operations."""


class GapProviderError(GapError):
    """Raised when a gap provider fails."""


class CurrencyMismatchError(GapError):
    """Raised when gap inputs use incompatible currencies."""


class CurrencyAggregationError(GapError):
    """Raised when multi-currency aggregation is requested without an explicit conversion policy."""


class AggregationError(GapError):
    """Raised when bucket or aggregation configuration is invalid."""


class ScenarioGapError(GapError):
    """Raised when scenario-specific liquidity gap operations fail."""
