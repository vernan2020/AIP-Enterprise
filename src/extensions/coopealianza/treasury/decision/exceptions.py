from __future__ import annotations


class TreasuryDecisionError(Exception):
    """Base exception for treasury decision evaluation."""


class DecisionConfigurationError(TreasuryDecisionError):
    """Raised for invalid treasury decision configuration."""


class TreasuryDecisionConfigurationError(DecisionConfigurationError):
    """Backward-compatible alias for configuration errors."""


class TreasuryDecisionEvaluationError(TreasuryDecisionError):
    """Raised when a decision request cannot be evaluated."""


class RecommendationError(TreasuryDecisionError):
    """Raised when a recommendation cannot be generated."""


class PrioritizationError(TreasuryDecisionError):
    """Raised when a recommendation priority cannot be derived."""


class DecisionAnalyticsError(TreasuryDecisionError):
    """Raised when analytics cannot be generated."""


class DecisionReportError(TreasuryDecisionError):
    """Raised when a decision report cannot be built."""


class DecisionProviderError(TreasuryDecisionError):
    """Raised when a recommendation provider fails."""


class ConflictingRecommendationError(TreasuryDecisionError):
    """Raised when contradictory recommendations are produced for the same asset and horizon."""
