from __future__ import annotations


class StressError(Exception):
    """Base exception for liquidity stress evaluation."""


class StressConfigurationError(StressError):
    """Raised when stress policy configuration is invalid."""


class StressEvaluationError(StressError):
    """Raised when stress evaluation inputs are incomplete."""


class StressProviderError(StressError):
    """Raised when a scenario provider fails."""


class StressReportError(StressError):
    """Raised when a stress report cannot be generated."""


class StressScenarioError(StressError):
    """Raised when a stress scenario cannot be applied."""
