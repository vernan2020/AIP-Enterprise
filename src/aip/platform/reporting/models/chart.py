from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class Chart:
    """Immutable chart model used in report sections."""

    title: str | None = None
    chart_type: str = "bar"
    categories: tuple[str, ...] = field(default_factory=tuple)
    values: tuple[Decimal | int | float, ...] = field(default_factory=tuple)
    labels: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "categories", tuple(self.categories))
        object.__setattr__(self, "values", tuple(self.values))
        object.__setattr__(self, "labels", tuple(self.labels))
