from __future__ import annotations


class ReportingError(Exception):
    """Base reporting exception."""


class RendererError(ReportingError):
    """Raised when a renderer fails."""
