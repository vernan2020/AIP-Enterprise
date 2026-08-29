from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aip.ui.modules.executive.models.executive_row import ExecutiveRow


@dataclass(frozen=True, slots=True)
class ExecutiveViewModel:
    """Immutable presentation model for the executive cockpit."""

    title: str = "Executive Cockpit"
    subtitle: str = "Strategic view for management and oversight"
    summary: tuple[str, ...] = field(default_factory=tuple)
    portfolio: tuple[str, ...] = field(default_factory=tuple)
    liquidity: tuple[str, ...] = field(default_factory=tuple)
    market: tuple[str, ...] = field(default_factory=tuple)
    recommendations: tuple[ExecutiveRow, ...] = field(default_factory=tuple)
    alerts: tuple[ExecutiveRow, ...] = field(default_factory=tuple)
    trends: tuple[tuple[str, tuple[str, ...]], ...] = field(default_factory=tuple)
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
            "portfolio": list(self.portfolio),
            "liquidity": list(self.liquidity),
            "market": list(self.market),
            "recommendations": [
                {
                    "title": item.title,
                    "detail": item.detail,
                    "category": item.category,
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
                    "category": item.category,
                    "severity": item.severity,
                    "source": item.source,
                    "timestamp": item.timestamp,
                }
                for item in self.alerts
            ],
            "trends": [{"label": label, "points": list(points)} for label, points in self.trends],
            "refresh_label": self.refresh_label,
            "theme_name": self.theme_name,
            "filters": self.filters,
            "status": self.status,
            "loading": self.loading,
            "error": self.error,
        }
