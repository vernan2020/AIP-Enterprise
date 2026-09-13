from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IntelligenceFindingRow:
    severity: str
    domain: str
    title: str
    summary: str
    recommendation: str
    evidence: str
    policy_reference: str


@dataclass(frozen=True, slots=True)
class FinancialIntelligenceViewModel:
    cutoff_date: str
    mode: str
    llm_provider: str
    llm_available: bool
    coverage: str
    alert_count: int
    opportunity_count: int
    executive_summary: str
    findings: tuple[IntelligenceFindingRow, ...]
    warnings: tuple[str, ...]
