from __future__ import annotations


class AnalyticsError(Exception):
    """Base exception for analytics domain errors."""


class NormalizationError(AnalyticsError):
    """Raised for invalid normalization operations."""


class ScoringError(AnalyticsError):
    """Raised for invalid score calculations."""


class RankingError(AnalyticsError):
    """Raised for invalid ranking operations."""


class InvalidWeightError(AnalyticsError):
    """Raised when component weights are invalid."""


class InvalidScoreBandError(AnalyticsError):
    """Raised when score band configuration is invalid."""


class DuplicateRankItemError(RankingError):
    """Raised when duplicate business identifiers are detected during ranking."""


class StatisticsError(AnalyticsError):
    """Raised for invalid statistical calculations."""


class ExplainabilityError(AnalyticsError):
    """Raised when explanation generation is invalid."""
