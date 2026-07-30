from __future__ import annotations

from decimal import Decimal
from typing import Any


class Formatter:
    """Simple formatting helper used by the reporting platform."""

    def format_value(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, Decimal):
            return f"{value:,.2f}"
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return f"{value:,.2f}"
        return str(value)
