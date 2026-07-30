from __future__ import annotations

from abc import ABC, abstractmethod

from src.aip.platform.reporting.models.report import Report


class Renderer(ABC):
    """Contract for all report renderers."""

    @abstractmethod
    def render(self, report: Report) -> str:
        """Render the report into the target format."""
