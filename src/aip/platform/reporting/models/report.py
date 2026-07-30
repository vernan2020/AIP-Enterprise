from __future__ import annotations

from dataclasses import dataclass, field

from src.aip.platform.reporting.models.attachment import Attachment
from src.aip.platform.reporting.models.chart import Chart
from src.aip.platform.reporting.models.report_metadata import ReportMetadata
from src.aip.platform.reporting.models.section import Section
from src.aip.platform.reporting.models.table import Table


@dataclass(frozen=True, slots=True)
class Report:
    """Immutable report model for rendering and export."""

    title: str
    subtitle: str | None = None
    sections: tuple[Section, ...] = field(default_factory=tuple)
    tables: tuple[Table, ...] = field(default_factory=tuple)
    charts: tuple[Chart, ...] = field(default_factory=tuple)
    attachments: tuple[Attachment, ...] = field(default_factory=tuple)
    metadata: ReportMetadata | None = None
    footer: str | None = None
    page_settings: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "sections", tuple(self.sections))
        object.__setattr__(self, "tables", tuple(self.tables))
        object.__setattr__(self, "charts", tuple(self.charts))
        object.__setattr__(self, "attachments", tuple(self.attachments))
        object.__setattr__(self, "page_settings", tuple(self.page_settings))
