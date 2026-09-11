from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aip.ui.modules.executive.models.executive_row import ExecutiveRow


@dataclass(frozen=True, slots=True)
class ExecutiveViewModel:
    """Immutable presentation model for the executive cockpit."""

    title: str = "Cockpit Ejecutivo"
    subtitle: str = "Visión integrada de portafolio, liquidez, mercado y macro"
    summary: tuple[str, ...] = field(default_factory=tuple)
    portfolio: tuple[str, ...] = field(default_factory=tuple)
    liquidity: tuple[str, ...] = field(default_factory=tuple)
    market: tuple[str, ...] = field(default_factory=tuple)
    recommendations: tuple[ExecutiveRow, ...] = field(default_factory=tuple)
    alerts: tuple[ExecutiveRow, ...] = field(default_factory=tuple)
    trends: tuple[tuple[str, tuple[str, ...]], ...] = field(default_factory=tuple)
    refresh_label: str = "Actualizar"
    theme_name: str = "light"
    filters: dict[str, str] = field(default_factory=dict)
    status: str = "ready"
    loading: bool = False
    error: str | None = None

    valuation_date: str = "-"
    portfolio_market_value: str = "-"
    weighted_yield: str = "-"
    modified_duration: str = "-"
    hqla_percent: str = "-"
    mil_percent: str = "-"
    liquidity_gap: str = "-"
    icl_total: str = "-"
    relative_value_count: int = 0
    rotation_candidate_count: int = 0
    macro_scenario: str = "-"
    macro_horizon: str = "-"
    data_quality_status: str = "-"

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
            "valuation_date": self.valuation_date,
            "portfolio_market_value": self.portfolio_market_value,
            "weighted_yield": self.weighted_yield,
            "modified_duration": self.modified_duration,
            "hqla_percent": self.hqla_percent,
            "mil_percent": self.mil_percent,
            "liquidity_gap": self.liquidity_gap,
            "icl_total": self.icl_total,
            "relative_value_count": self.relative_value_count,
            "rotation_candidate_count": self.rotation_candidate_count,
            "macro_scenario": self.macro_scenario,
            "macro_horizon": self.macro_horizon,
            "data_quality_status": self.data_quality_status,
        }
