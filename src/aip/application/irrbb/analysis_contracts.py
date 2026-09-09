from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from aip.application.irrbb.contracts import (
    IRRBBCurveSourcePoint,
    IRRBBSourceLoadResult,
)
from aip.domain.irrbb.models import (
    STANDARD_STRESS_SCENARIOS,
    IRRBBMethodologyProfile,
    IRRBBScenario,
    IRRBBTimeBucket,
)
from aip.domain.irrbb.scenario_evaluation import IRRBBScenarioEvaluationResult
from aip.domain.irrbb.sugef_standard_gap import (
    SugefGapBucketTotal,
    SugefGapReportLine,
    SugefGapRowClassification,
)
from aip.shared.money import Currency, Money


class IRRBBAnalysisStatus(str, Enum):
    """Application-level outcome of one RTILB calculation request."""

    NO_DATA = "NO_DATA"
    BLOCKED = "BLOCKED"
    CALCULATED = "CALCULATED"
    CALCULATED_WITH_DATA_GAPS = "CALCULATED_WITH_DATA_GAPS"


class IRRBBGapCoverageIssueCode(str, Enum):
    """Stable reasons why a calculation-ready position is absent from SUGEF GAP."""

    ROW_NOT_MAPPED = "ROW_NOT_MAPPED"
    SCHEDULE_MISSING = "SCHEDULE_MISSING"
    SCHEDULE_INVALID = "SCHEDULE_INVALID"


@dataclass(frozen=True, slots=True)
class IRRBBGapCoverageIssue:
    position_id: str
    code: IRRBBGapCoverageIssueCode
    message: str

    def __post_init__(self) -> None:
        if not self.position_id.strip():
            raise ValueError("gap coverage issue position_id is required")
        if not self.message.strip():
            raise ValueError("gap coverage issue message is required")


@dataclass(frozen=True, slots=True)
class IRRBBGapMatrixCell:
    """Application DTO for one SUGEF report-line/time-bucket amount."""

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
class IRRBBGapCurrencyResult:
    """SUGEF GAP output kept in its native currency; currencies are never netted."""

    currency: Currency
    bucket_totals: tuple[SugefGapBucketTotal, ...]
    matrix_cells: tuple[IRRBBGapMatrixCell, ...]
    included_position_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for total in self.bucket_totals:
            if total.amount.currency is not self.currency:
                raise ValueError("gap bucket total currency must match result currency")
        for cell in self.matrix_cells:
            if cell.amount.currency is not self.currency:
                raise ValueError("gap matrix cell currency must match result currency")


@dataclass(frozen=True, slots=True)
class IRRBBAnalysisRequest:
    cutoff_date: date
    reporting_currency: Currency
    methodology: IRRBBMethodologyProfile
    required_scenarios: tuple[IRRBBScenario, ...] = STANDARD_STRESS_SCENARIOS


@dataclass(frozen=True, slots=True)
class IRRBBAnalysisResult:
    """Complete application result before transformation into any UI read-model."""

    status: IRRBBAnalysisStatus
    source_load: IRRBBSourceLoadResult
    evaluation: IRRBBScenarioEvaluationResult | None
    tier_one_capital: Money | None
    gap_classifications: tuple[SugefGapRowClassification, ...]
    gap_results: tuple[IRRBBGapCurrencyResult, ...]
    gap_issues: tuple[IRRBBGapCoverageIssue, ...]
    curve_points: tuple[IRRBBCurveSourcePoint, ...]

    @property
    def is_calculated(self) -> bool:
        return self.evaluation is not None
