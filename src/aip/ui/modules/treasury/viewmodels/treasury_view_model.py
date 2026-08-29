from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aip.ui.modules.treasury.models.treasury_row import TreasuryRow


@dataclass(frozen=True, slots=True)
class TreasuryViewModel:
    title: str = "Treasury Workspace"
    subtitle: str = "Cash, liquidity and funding oversight"
    summary: tuple[str, ...] = field(default_factory=tuple)
    recommendations: tuple[TreasuryRow, ...] = field(default_factory=tuple)
    alerts: tuple[TreasuryRow, ...] = field(default_factory=tuple)
    opportunities: tuple[TreasuryRow, ...] = field(default_factory=tuple)
    refresh_label: str = "Refresh"
    theme_name: str = "light"
    filters: dict[str, str] = field(default_factory=dict)
    status: str = "ready"
    loading: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "summary": list(self.summary),
            "recommendations": [
                {
                    "title": item.title,
                    "detail": item.detail,
                    "severity": item.severity,
                    "source": item.source,
                    "timestamp": item.timestamp,
                }
                for item in self.recommendations
            ],
            "alerts": [
                {
                    "title": item.title,
                    "detail": item.detail,
                    "severity": item.severity,
                    "source": item.source,
                    "timestamp": item.timestamp,
                }
                for item in self.alerts
            ],
            "opportunities": [
                {
                    "title": item.title,
                    "detail": item.detail,
                    "severity": item.severity,
                    "source": item.source,
                    "timestamp": item.timestamp,
                }
                for item in self.opportunities
            ],
            "refresh_label": self.refresh_label,
            "theme_name": self.theme_name,
            "filters": self.filters,
            "status": self.status,
            "loading": self.loading,
            "error": self.error,
        }
