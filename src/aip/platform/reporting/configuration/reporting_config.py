from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReportingConfig:
    """Configuration for report rendering and export."""

    output_format: str = "html"
    template_name: str = "corporate"
    enable_streaming: bool = True
    page_size: str = "a4"
