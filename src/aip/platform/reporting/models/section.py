from __future__ import annotations

from dataclasses import dataclass, field

from src.aip.platform.reporting.models.attachment import Attachment
from src.aip.platform.reporting.models.chart import Chart
from src.aip.platform.reporting.models.table import Table


@dataclass(frozen=True, slots=True)
class Section:
    """Immutable report section that may contain tables, charts, and attachments."""

    title: str
    content: tuple[str, ...] = field(default_factory=tuple)
    tables: tuple[Table, ...] = field(default_factory=tuple)
    charts: tuple[Chart, ...] = field(default_factory=tuple)
    attachments: tuple[Attachment, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "content", tuple(self.content))
        object.__setattr__(self, "tables", tuple(self.tables))
        object.__setattr__(self, "charts", tuple(self.charts))
        object.__setattr__(self, "attachments", tuple(self.attachments))
