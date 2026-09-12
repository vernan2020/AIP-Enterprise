from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class IRRBBDataQualityStatus(str, Enum):
    """Readiness of one canonical position for the requested IRRBB workflow."""

    READY = "READY"
    INCOMPLETE = "INCOMPLETE"
    EXCLUDED = "EXCLUDED"


class IRRBBDataQualitySeverity(str, Enum):
    """Severity of an IRRBB data-quality or strategy-capability finding."""

    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class IRRBBDataIssueCode(str, Enum):
    """Stable machine-readable IRRBB data-quality finding codes."""

    ZERO_PRINCIPAL = "ZERO_PRINCIPAL"
    MATURED_POSITION = "MATURED_POSITION"
    MATURITY_MISSING = "MATURITY_MISSING"
    ORIGINATION_AFTER_VALUATION = "ORIGINATION_AFTER_VALUATION"
    PAYMENT_STRUCTURE_MISSING = "PAYMENT_STRUCTURE_MISSING"
    CONTRACTUAL_RATE_MISSING = "CONTRACTUAL_RATE_MISSING"
    PAYMENT_FREQUENCY_MISSING = "PAYMENT_FREQUENCY_MISSING"
    NEXT_REPRICING_MISSING = "NEXT_REPRICING_MISSING"
    NEXT_REPRICING_BEFORE_VALUATION = "NEXT_REPRICING_BEFORE_VALUATION"
    NEXT_REPRICING_AFTER_MATURITY = "NEXT_REPRICING_AFTER_MATURITY"
    REPRICING_FREQUENCY_MISSING = "REPRICING_FREQUENCY_MISSING"
    FLOATING_RATE_BASIS_MISSING = "FLOATING_RATE_BASIS_MISSING"
    EXPLICIT_SCHEDULE_REQUIRED = "EXPLICIT_SCHEDULE_REQUIRED"
    BEHAVIORAL_MODEL_REQUIRED = "BEHAVIORAL_MODEL_REQUIRED"
    OPTIONALITY_MODEL_REQUIRED = "OPTIONALITY_MODEL_REQUIRED"
    SCENARIO_REPRICING_MODEL_REQUIRED = "SCENARIO_REPRICING_MODEL_REQUIRED"
    UNSUPPORTED_INVESTMENT_PAYMENT_FREQUENCY = "UNSUPPORTED_INVESTMENT_PAYMENT_FREQUENCY"


@dataclass(frozen=True, slots=True)
class IRRBBDataQualityIssue:
    """One explicit reason why a position is not fully calculation-ready."""

    code: IRRBBDataIssueCode
    field_name: str | None
    message: str
    severity: IRRBBDataQualitySeverity = IRRBBDataQualitySeverity.ERROR


@dataclass(frozen=True, slots=True)
class IRRBBValidationContext:
    """Runtime capabilities available for validating one position.

    These booleans describe approved calculation capabilities, not source data.
    They prevent the validator from declaring a position ready merely because
    its raw fields exist when the required schedule or behavioral strategy is absent.
    """

    explicit_schedule_available: bool = False
    behavioral_model_available: bool = False
    scenario_repricing_model_available: bool = False


@dataclass(frozen=True, slots=True)
class IRRBBPositionAssessment:
    """Data-quality and strategy-readiness assessment for one position."""

    position_id: str
    status: IRRBBDataQualityStatus
    issues: tuple[IRRBBDataQualityIssue, ...]

    @property
    def is_ready(self) -> bool:
        return self.status is IRRBBDataQualityStatus.READY
