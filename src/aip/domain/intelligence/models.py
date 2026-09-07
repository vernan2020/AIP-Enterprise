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
class FinancialMetricContext:
    code: str
    label: str
    value: Decimal | None
    unit: str
    previous_value: Decimal | None = None
    change_percent: Decimal | None = None
    source_account: str = ""


@dataclass(frozen=True, slots=True)
class FinancialPeerContext:
    entity_name: str
    category: str
    assets: Decimal | None = None
    loans: Decimal | None = None
    equity: Decimal | None = None
    net_income: Decimal | None = None
    roa_percent: Decimal | None = None
    roe_percent: Decimal | None = None


@dataclass(frozen=True, slots=True)
class FinancialRatingIndicatorContext:
    code: str
    label: str
    dimension: str
    direction: str
    level: str
    value: Decimal | None
    peer_count: int
    percentile_15: Decimal | None = None
    midpoint: Decimal | None = None
    percentile_85: Decimal | None = None


@dataclass(frozen=True, slots=True)
class FinancialReconciliationContext:
    code: str
    label: str
    status: str
    difference: Decimal | None = None


@dataclass(frozen=True, slots=True)
class FinancialAnalysisContext:
    status: str
    cutoff_date: date | None
    entity_id: str
    entity_name: str
    entity_category: str
    metrics: tuple[FinancialMetricContext, ...] = ()
    peers: tuple[FinancialPeerContext, ...] = ()
    rating_status: str = "UNAVAILABLE"
    rating_score: Decimal | None = None
    rating_grade: str = ""
    rating_coverage_percent: Decimal | None = None
    rating_methodology: str = ""
    rating_indicators: tuple[FinancialRatingIndicatorContext, ...] = ()
    reconciliation_issues: tuple[FinancialReconciliationContext, ...] = ()


@dataclass(frozen=True, slots=True)
class MacroProjectionPointContext:
    period: date
    fx_sell: Decimal | None
    tpm: Decimal | None
    tbp: Decimal | None
    tri_crc_12m: Decimal | None
    tri_usd_12m: Decimal | None
    inflation: Decimal | None
    imae: Decimal | None


@dataclass(frozen=True, slots=True)
class MacroIntelligenceContext:
    status: str
    scenario_id: str
    version: int
    scenario_type: str
    scenario_status: str
    dataset_as_of_date: date | None
    horizon: int
    rows: tuple[MacroProjectionPointContext, ...] = ()


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
    financial_analysis: FinancialAnalysisContext | None = None
    macro_intelligence: MacroIntelligenceContext | None = None


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
