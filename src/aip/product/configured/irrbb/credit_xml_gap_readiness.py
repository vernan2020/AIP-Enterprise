from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.application.irrbb import IRRBBSourceExclusion, IRRBBSourceMappingFailure
from aip.product.configured.irrbb.credit_xml_currency_bridge import (
    CreditXMLCanonicalBucketBatchResult,
    CreditXMLCanonicalBucketFact,
)


class CreditXMLGapReadinessStatus(str, Enum):
    """Readiness of one canonical Credit XML fact for SUGEF 19-band GAP exposure."""

    BLOCKED_CONTRACTUAL_SCHEDULE = "BLOCKED_CONTRACTUAL_SCHEDULE"


@dataclass(frozen=True, slots=True)
class CreditXMLGapReadinessAssessment:
    """Explicit blocker preventing a balance-only fact from becoming a GAP exposure."""

    source_record_id: str
    source_reference: str
    operation_id: str
    status: CreditXMLGapReadinessStatus
    missing_capabilities: tuple[str, ...]
    message: str

    def __post_init__(self) -> None:
        if not self.source_record_id.strip():
            raise ValueError("credit GAP readiness source_record_id is required")
        if not self.source_reference.strip():
            raise ValueError("credit GAP readiness source_reference is required")
        if not self.operation_id.strip():
            raise ValueError("credit GAP readiness operation_id is required")
        if not self.missing_capabilities:
            raise ValueError("credit GAP readiness must identify missing capabilities")
        if any(not value.strip() for value in self.missing_capabilities):
            raise ValueError("credit GAP readiness capabilities cannot be blank")
        if not self.message.strip():
            raise ValueError("credit GAP readiness message is required")


@dataclass(frozen=True, slots=True)
class CreditXMLGapReadinessBatchResult:
    """Preserve every physical Credit XML record across GAP-readiness outcomes."""

    source_record_count: int
    assessments: tuple[CreditXMLGapReadinessAssessment, ...]
    source_exclusions: tuple[IRRBBSourceExclusion, ...]
    mapping_failures: tuple[IRRBBSourceMappingFailure, ...]

    def __post_init__(self) -> None:
        represented = (
            len(self.assessments) + len(self.source_exclusions) + len(self.mapping_failures)
        )
        if represented != self.source_record_count:
            raise ValueError("every credit XML source record must have one GAP readiness outcome")

        ids = (
            tuple(item.source_record_id for item in self.assessments)
            + tuple(item.source_record_id for item in self.source_exclusions)
            + tuple(item.source_record_id for item in self.mapping_failures)
        )
        if len(ids) != len(set(ids)):
            raise ValueError("credit GAP readiness outcomes must have unique source_record_id")


class CreditXMLGapReadinessService:
    """Block GAP exposure construction until contractual schedule evidence exists.

    The canonical SUGEF GAP engine distributes fixed-rate credit through contractual
    payment dates and, for floating/semivariable credit, needs the principal residual
    at the next repricing date. A balance-plus-bucket fact is therefore insufficient.
    This service makes that blocker explicit instead of collapsing the whole balance
    into one time bucket.
    """

    _FIXED_CAPABILITIES = (
        "CONTRACTUAL_PAYMENT_SCHEDULE",
        "PAYMENT_AMOUNT_BY_DATE",
    )
    _FLOATING_CAPABILITIES = (
        "CONTRACTUAL_PAYMENT_SCHEDULE_THROUGH_REPRICING",
        "OUTSTANDING_PRINCIPAL_AT_REPRICING_OR_PRINCIPAL_COMPONENTS",
    )

    @classmethod
    def assess_batch(
        cls,
        batch: CreditXMLCanonicalBucketBatchResult,
    ) -> CreditXMLGapReadinessBatchResult:
        return CreditXMLGapReadinessBatchResult(
            source_record_count=batch.source_record_count,
            assessments=tuple(cls.assess_fact(fact) for fact in batch.canonical_bucket_facts),
            source_exclusions=batch.source_exclusions,
            mapping_failures=batch.mapping_failures,
        )

    @classmethod
    def assess_fact(cls, fact: CreditXMLCanonicalBucketFact) -> CreditXMLGapReadinessAssessment:
        rate_indicator = fact.rate_indicator.upper()
        if rate_indicator == "F":
            missing = cls._FIXED_CAPABILITIES
            message = (
                "Fixed-rate credit has an exact IRRBB maturity bucket and governed currency, "
                "but SUGEF GAP requires the contractual future payment schedule. The current "
                "Credit XML fact cannot be collapsed to one maturity bucket without changing "
                "the methodology."
            )
        else:
            missing = cls._FLOATING_CAPABILITIES
            message = (
                "Floating/semivariable credit has an exact IRRBB repricing bucket and governed "
                "currency, but SUGEF GAP requires payments through repricing plus the residual "
                "principal at repricing. Those amounts are not available in the canonical fact "
                "and must not be inferred."
            )

        return CreditXMLGapReadinessAssessment(
            source_record_id=fact.source_record_id,
            source_reference=fact.source_reference,
            operation_id=fact.operation_id,
            status=CreditXMLGapReadinessStatus.BLOCKED_CONTRACTUAL_SCHEDULE,
            missing_capabilities=missing,
            message=message,
        )
