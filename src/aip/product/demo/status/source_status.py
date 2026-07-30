from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceStatus:
    """Status for an external source."""

    name: str
    state: str
    details: str = ""
    correlation_id: str | None = None
