from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum


class IntelligenceSeverity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    ATTENTION = "ATTENTION"
    OPPORTUNITY = "OPPORTUNITY"
    NORMAL = "NORMAL"


class IntelligenceKind(StrEnum):
    ALERT = "ALERT"
    OPPORTUNITY = "OPPORTUNITY"
    STRATEGY = "STRATEGY"
    OBSERVATION = "OBSERVATION"


@dataclass(frozen=True, slots=True)
class IntelligenceEvidence:
    metric: str
    value: str
    source: str
    reference: str = ""


@dataclass(frozen=True, slots=True)
class MarketOpportunity:
    series: str
    issuer: str
    spread_bp: Decimal
    classification: str


@dataclass(frozen=True, slots=True)
class FinancialIntelligenceContext:
    cutoff_date: date
    execution_mode: str
    data_quality_status: str
    source_states: tuple[str, ...]
    warnings: tuple[str, ...]

    market_value_crc: Decimal
    weighted_yield_percent: Decimal | None
    modified_duration: Decimal | None
    hqla_percent: Decimal | None
    dv01_crc: Decimal | None
    issuer_hhi: Decimal | None
    government_bccr_share_percent: Decimal | None
    duration_under_1_share_percent: Decimal | None
    duration_1_5_share_percent: Decimal | None
    duration_over_5_share_percent: Decimal | None

    icl_total: Decimal | None
    hqla_capacity_crc: Decimal | None
    hqla_restricted_count: int
    liquidity_policy_status: str
    liquidity_stress_result: str

    opportunities: tuple[MarketOpportunity, ...]


@dataclass(frozen=True, slots=True)
class IntelligenceFinding:
    finding_id: str
    kind: IntelligenceKind
    severity: IntelligenceSeverity
    domain: str
    title: str
    summary: str
    recommendation: str
    evidence: tuple[IntelligenceEvidence, ...]
    confidence: Decimal
    policy_reference: str = ""


@dataclass(frozen=True, slots=True)
class FinancialIntelligenceReport:
    generated_at: datetime
    cutoff_date: date
    mode: str
    coverage: tuple[str, ...]
    executive_summary: str
    findings: tuple[IntelligenceFinding, ...]
    warnings: tuple[str, ...]

    @property
    def alert_count(self) -> int:
        return sum(
            finding.severity
            in {
                IntelligenceSeverity.CRITICAL,
                IntelligenceSeverity.HIGH,
                IntelligenceSeverity.ATTENTION,
            }
            for finding in self.findings
        )

    @property
    def opportunity_count(self) -> int:
        return sum(
            finding.severity is IntelligenceSeverity.OPPORTUNITY for finding in self.findings
        )
