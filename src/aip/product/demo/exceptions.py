from __future__ import annotations


class DemoConfigurationError(ValueError):
    """Raised when demo configuration is invalid."""


class DemoBootstrapError(RuntimeError):
    """Raised when demo bootstrap cannot complete."""


class DemoWorkflowError(RuntimeError):
    """Raised when demo workflow execution fails."""
