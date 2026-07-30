from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ReportMetadata:
    """Immutable metadata for a report."""

    author: str | None = None
    generated_at: datetime | None = None
    language: str = "en"
    tags: tuple[str, ...] = field(default_factory=tuple)
    custom_fields: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tags", tuple(self.tags))
        object.__setattr__(self, "custom_fields", dict(self.custom_fields))
