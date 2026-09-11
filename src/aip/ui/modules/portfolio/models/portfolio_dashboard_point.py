from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PortfolioDashboardPoint:
    """Presentation-only portfolio dashboard point."""

    label: str
    value: Decimal
    secondary_value: Decimal = Decimal("0")
    detail: str = ""
