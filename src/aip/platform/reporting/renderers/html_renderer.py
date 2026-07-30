from __future__ import annotations

from src.aip.platform.reporting.engine.renderer import Renderer
from src.aip.platform.reporting.models.report import Report


class HtmlRenderer(Renderer):
    """HTML renderer for reporting content."""

    def render(self, report: Report) -> str:
        sections = "".join(f"<section><h2>{section.title}</h2></section>" for section in report.sections)
        return f"<html><body><h1>{report.title}</h1><h2>{report.subtitle or ''}</h2>{sections}</body></html>"
