from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ExplanationFactor:
    """Immutable factor supporting an analytical explanation."""

    name: str
    value: Decimal
    direction: str
    contribution: Decimal
    source_reference: str | None = None
