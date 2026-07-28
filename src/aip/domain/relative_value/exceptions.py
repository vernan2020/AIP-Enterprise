from __future__ import annotations


class RelativeValueError(Exception):
    """Base exception for the relative-value domain."""


class SpreadCalculationError(RelativeValueError):
    """Raised when a spread calculation cannot be completed."""


class BenchmarkNotAvailableError(RelativeValueError):
    """Raised when a benchmark yield is unavailable."""


class CurveNotAvailableError(RelativeValueError):
    """Raised when a required curve is unavailable."""


class UnsupportedSpreadTypeError(RelativeValueError):
    """Raised when the requested spread type is unsupported."""


class RecommendationError(RelativeValueError):
    """Raised when a recommendation cannot be derived."""


class RankingError(RelativeValueError):
    """Raised when ranking cannot be completed."""


class ProviderError(RelativeValueError):
    """Raised when a provider contract is violated."""
