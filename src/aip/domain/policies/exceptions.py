from __future__ import annotations


class PolicyError(Exception):
    """Base exception for policy domain errors."""


class PolicyValidationError(PolicyError):
    """Raised when a policy definition is invalid."""


class PolicyDependencyError(PolicyError):
    """Raised when a policy dependency cannot be satisfied."""
