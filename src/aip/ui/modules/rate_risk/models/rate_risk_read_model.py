from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from aip.domain.irrbb.models import IRRBBScenario, IRRBBTimeBucket
from aip.domain.irrbb.sugef_standard_gap import SugefGapReportLine
from aip.shared.money import Currency, Money


@dataclass(frozen=True, slots=True)
class RateRiskCurvePointInput:
    """Normalized curve point supplied by the application/market-data boundary.

    The read-model layer does not build, interpolate or shock curves. It only
    carries already-resolved points for visualization and audit disclosure.
    """

    curve_id: str
    as_of_date: date
    currency: Currency
    scenario: IRRBBScenario
    tenor_years: Decimal
    rate: Decimal
    source_reference: str

    def __post_init__(self) -> None:
        if not self.curve_id.strip():
            raise ValueError("curve_id is required")
        if self.tenor_years < 0:
            raise ValueError("curve tenor_years cannot be negative")
        if not self.source_reference.strip():
            raise ValueError("curve source_reference is required")


@dataclass(frozen=True, slots=True)
class RateRiskGapMatrixCellInput:
    """Already-aggregated SUGEF report-line/bucket amount for presentation.

    Aggregation belongs to the application/domain calculation path. The presenter
    must never derive supervisory matrix amounts from UI state.
    """

    report_line: SugefGapReportLine
    bucket: IRRBBTimeBucket
    ordinal: int
    bucket_label: str
    amount: Money

    def __post_init__(self) -> None:
        if self.ordinal <= 0:
            raise ValueError("gap matrix ordinal must be positive")
        if not self.bucket_label.strip():
            raise ValueError("gap matrix bucket_label is required")


@dataclass(frozen=True, slots=True)
class RateRiskMethodologyMetadata:
    code: str
    version: str
    status: str
    source_reference: str
    effective_from: date | None
    valuation_date: date
    reporting_currency: str
    calculated_position_count: int


@dataclass(frozen=True, slots=True)
class RateRiskReadinessSummary:
    calculated_position_count: int
    assessed_position_count: int
    ready_position_count: int
    incomplete_position_count: int
    excluded_position_count: int
    data_issue_count: int
    mapping_pending_count: int
    incomplete_mapping_count: int
    source_mapping_failure_count: int = 0


@dataclass(frozen=True, slots=True)
class RateRiskKpi:
    key: str
    label: str
    value: Decimal
    unit: str
    currency: str | None = None
    scenario: str | None = None
    status: str = "NEUTRAL"


@dataclass(frozen=True, slots=True)
class RateRiskScenarioRow:
    scenario: str
    label: str
    eve: Decimal
    delta_eve: Decimal
    fall_from_base: Decimal
    pv_assets: Decimal
    pv_liabilities: Decimal
    pv_off_balance_net: Decimal
    currency: str
    is_worst: bool


@dataclass(frozen=True, slots=True)
class RateRiskGapBucketRow:
    bucket: str
    ordinal: int
    label: str
    amount: Decimal
    currency: str


@dataclass(frozen=True, slots=True)
class RateRiskGapMatrixCellRow:
    report_line: str
    report_line_label: str
    bucket: str
    ordinal: int
    bucket_label: str
    amount: Decimal
    currency: str


@dataclass(frozen=True, slots=True)
class RateRiskGapCoverageIssueRow:
    """Application-level reason why a ready position is absent from SUGEF GAP."""

    position_id: str
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class RateRiskValuationFlowRow:
    scenario: str
    position_id: str
    side: str
    direction: str
    flow_type: str
    amount_status: str
    cashflow_date: date
    risk_date: date
    amount: Decimal
    amount_currency: str
    discount_factor: Decimal
    exchange_rate: Decimal
    present_value_reporting: Decimal
    signed_eve_contribution: Decimal
    reporting_currency: str
    source_reference: str
    projection_basis: str | None


@dataclass(frozen=True, slots=True)
class RateRiskPositionQualityRow:
    position_id: str
    status: str
    issue_count: int
    error_count: int
    warning_count: int
    info_count: int


@dataclass(frozen=True, slots=True)
class RateRiskDataIssueRow:
    position_id: str
    status: str
    code: str
    field_name: str | None
    severity: str
    message: str


@dataclass(frozen=True, slots=True)
class RateRiskSourceMappingFailureRow:
    """Auditable source record that failed before canonical position validation."""

    source_record_id: str
    source_reference: str
    code: str
    canonical_field: str | None
    message: str


@dataclass(frozen=True, slots=True)
class RateRiskMappingRow:
    position_id: str
    status: str
    report_line: str | None
    report_line_label: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class RateRiskCurvePointRow:
    curve_id: str
    as_of_date: date
    currency: str
    scenario: str
    tenor_years: Decimal
    rate: Decimal
    source_reference: str


@dataclass(frozen=True, slots=True)
class RateRiskReadModel:
    """Complete passive read model for the IRRBB workspace.

    ``analysis_status`` carries the application outcome verbatim. Empty KPI and
    scenario collections therefore mean unavailable/not calculated, never zero.
    """

    methodology: RateRiskMethodologyMetadata
    readiness: RateRiskReadinessSummary
    kpis: tuple[RateRiskKpi, ...]
    scenario_rows: tuple[RateRiskScenarioRow, ...]
    gap_bucket_rows: tuple[RateRiskGapBucketRow, ...]
    gap_matrix_cells: tuple[RateRiskGapMatrixCellRow, ...]
    valuation_flow_rows: tuple[RateRiskValuationFlowRow, ...]
    position_quality_rows: tuple[RateRiskPositionQualityRow, ...]
    data_issue_rows: tuple[RateRiskDataIssueRow, ...]
    mapping_rows: tuple[RateRiskMappingRow, ...]
    curve_rows: tuple[RateRiskCurvePointRow, ...]
    warnings: tuple[str, ...] = ()
    analysis_status: str = "CALCULATED"
    gap_coverage_issue_rows: tuple[RateRiskGapCoverageIssueRow, ...] = ()
    source_mapping_failure_rows: tuple[RateRiskSourceMappingFailureRow, ...] = ()
