from __future__ import annotations

from dataclasses import dataclass

from src.aip.platform.reporting.engine.renderer import Renderer
from src.aip.platform.reporting.models.report import Report


@dataclass(slots=True)
class ReportEngine:
    """Formatting-only report engine that delegates rendering to an injected renderer."""

    renderer: Renderer

    def render(self, report: Report) -> str:
        return self.renderer.render(report)
