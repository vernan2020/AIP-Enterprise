from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Table:
    """Immutable tabular section of a report."""

    title: str | None = None
    columns: tuple[str, ...] = field(default_factory=tuple)
    rows: tuple[tuple[Any, ...], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "columns", tuple(self.columns))
        object.__setattr__(self, "rows", tuple(tuple(row) for row in self.rows))
