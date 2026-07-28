from __future__ import annotations


class ProjectionError(Exception):
    """Raised for invalid or unsupported cash flow projection operations."""


class BehavioralError(ProjectionError):
    """Raised when behavioral assumptions cannot be applied."""


class AggregationError(ProjectionError):
    """Raised when aggregation rules are invalid."""


class ScenarioError(ProjectionError):
    """Raised when scenario selection is invalid."""
