from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TreasuryRow:
    title: str
    detail: str
    severity: str = "Info"
    source: str = "Application"
    timestamp: str = "2026-07-29"
