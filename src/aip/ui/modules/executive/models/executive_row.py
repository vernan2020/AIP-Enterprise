from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExecutiveRow:
    title: str
    detail: str
    category: str = "General"
    severity: str = "Medium"
    source: str = "Application"
    timestamp: str = "2026-07-29"
