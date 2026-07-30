from __future__ import annotations

from src.aip.platform.reporting.engine.renderer import Renderer
from src.aip.platform.reporting.models.report import Report


class PptRenderer(Renderer):
    """PowerPoint renderer for reporting content."""

    def render(self, report: Report) -> str:
        return f"ppt:{report.title}"
