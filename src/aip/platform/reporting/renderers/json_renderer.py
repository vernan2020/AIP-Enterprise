from __future__ import annotations

import json

from src.aip.platform.reporting.engine.renderer import Renderer
from src.aip.platform.reporting.models.report import Report


class JsonRenderer(Renderer):
    """JSON renderer for reporting content."""

    def render(self, report: Report) -> str:
        payload = {
            "title": report.title,
            "subtitle": report.subtitle,
            "sections": [section.title for section in report.sections],
        }
        return json.dumps(payload)
