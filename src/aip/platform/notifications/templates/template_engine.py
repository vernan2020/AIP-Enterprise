from __future__ import annotations

from datetime import datetime
from typing import Any


class TemplateEngine:
    def render(self, template: str, context: dict[str, Any]) -> str:
        return template.format(**context)

    def format_severity(self, severity: str) -> str:
        return severity.upper()

    def format_timestamp(self, value: datetime | None = None) -> str:
        if value is None:
            value = datetime.now()
        return value.isoformat()

    def format_correlation_id(self, correlation_id: str | None = None) -> str:
        return correlation_id or "n/a"

    def format_execution_id(self, execution_id: str | None = None) -> str:
        return execution_id or "n/a"
