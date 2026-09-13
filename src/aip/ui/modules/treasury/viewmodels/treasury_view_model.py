from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aip.ui.modules.treasury.models.treasury_row import TreasuryRow


@dataclass(frozen=True, slots=True)
class TreasuryViewModel:
    title: str = "Tesorería"
    subtitle: str = "Liquidez, garantías y oportunidades de mercado"
    summary: tuple[str, ...] = field(default_factory=tuple)
    recommendations: tuple[TreasuryRow, ...] = field(default_factory=tuple)
    alerts: tuple[TreasuryRow, ...] = field(default_factory=tuple)
    opportunities: tuple[TreasuryRow, ...] = field(default_factory=tuple)
    refresh_label: str = "Actualizar"
    theme_name: str = "light"
    filters: dict[str, str] = field(default_factory=dict)
    status: str = "ready"
    loading: bool = False
    error: str | None = None

    valuation_date: str = "-"
    cash_position: str = "-"
    liquidity_gap: str = "-"
    hqla_capacity: str = "-"
    mil_capacity: str = "-"
    maturity_30d: str = "-"
    icl_total: str = "-"
    rotation_candidate_count: int = 0
    policy_status: str = "-"
    stress_status: str = "-"

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
            "valuation_date": self.valuation_date,
            "cash_position": self.cash_position,
            "liquidity_gap": self.liquidity_gap,
            "hqla_capacity": self.hqla_capacity,
            "mil_capacity": self.mil_capacity,
            "maturity_30d": self.maturity_30d,
            "icl_total": self.icl_total,
            "rotation_candidate_count": self.rotation_candidate_count,
            "policy_status": self.policy_status,
            "stress_status": self.stress_status,
        }
