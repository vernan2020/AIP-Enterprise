from __future__ import annotations

from src.aip.platform.reporting.engine.renderer import Renderer
from src.aip.platform.reporting.models.report import Report


class PdfRenderer(Renderer):
    """PDF renderer for reporting content."""

    def render(self, report: Report) -> str:
        return f"PDF:{report.title}"
