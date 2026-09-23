from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.application.irrbb import IRRBBSourceMappingFailure
from aip.product.configured.irrbb.captaciones_irrbb_account_classifier import (
    CaptacionesIRRBBAccountClassification,
    CaptacionesIRRBBAccountClassifier,
    CaptacionesIRRBBFundingClass,
)
from aip.product.configured.irrbb.captaciones_xml_currency_bridge import (
    CaptacionesXMLCanonicalCurrencyFact,
    CaptacionesXMLCurrencyBatchResult,
)


class CaptacionesIRRBBReadinessStatus(str, Enum):
    BLOCKED_NMD_BEHAVIORAL_PROFILE = "BLOCKED_NMD_BEHAVIORAL_PROFILE"
    BLOCKED_CONTRACTUAL_SCHEDULE = "BLOCKED_CONTRACTUAL_SCHEDULE"
    BLOCKED_MATURED_TERM_POLICY = "BLOCKED_MATURED_TERM_POLICY"


@dataclass(frozen=True, slots=True)
class CaptacionesIRRBBReadinessAssessment:
    source_record_id: str
    source_reference: str
    operation_id: str
    accounting_account_code: str
    funding_class: CaptacionesIRRBBFundingClass
    status: CaptacionesIRRBBReadinessStatus
    missing_capabilities: tuple[str, ...]
    message: str

    def __post_init__(self) -> None:
        if not self.source_record_id.strip():
            raise ValueError("Captaciones readiness source_record_id is required")
        if not self.source_reference.strip():
            raise ValueError("Captaciones readiness source_reference is required")
        if not self.operation_id.strip():
            raise ValueError("Captaciones readiness operation_id is required")
        if not self.accounting_account_code.strip():
            raise ValueError("Captaciones readiness accounting_account_code is required")
        if not self.missing_capabilities:
            raise ValueError("Captaciones readiness must identify missing capabilities")
        if any(not value.strip() for value in self.missing_capabilities):
            raise ValueError("Captaciones readiness capabilities cannot be blank")
        if not self.message.strip():
            raise ValueError("Captaciones readiness message is required")


@dataclass(frozen=True, slots=True)
class CaptacionesIRRBBReadinessBatchResult:
    source_record_count: int
    assessments: tuple[CaptacionesIRRBBReadinessAssessment, ...]
    mapping_failures: tuple[IRRBBSourceMappingFailure, ...]

    def __post_init__(self) -> None:
        if len(self.assessments) + len(self.mapping_failures) != self.source_record_count:
            raise ValueError("every Captaciones record must have one readiness outcome")
        ids = tuple(item.source_record_id for item in self.assessments) + tuple(
            item.source_record_id for item in self.mapping_failures
        )
        if len(ids) != len(set(ids)):
            raise ValueError("Captaciones readiness outcomes must have unique source_record_id")


class CaptacionesIRRBBReadinessService:
    """Identify the governed capability required before 19-band scheduling.

    Sight balances must enter the existing NMD behavioral-model path. Term deposits
    need contractual cash-flow evidence; accounting account alone cannot infer CAPF
    modality or coupon structure. Matured term funding remains blocked until an
    institutionally approved treatment is supplied.
    """

    @classmethod
    def assess_batch(
        cls,
        batch: CaptacionesXMLCurrencyBatchResult,
    ) -> CaptacionesIRRBBReadinessBatchResult:
        assessments: list[CaptacionesIRRBBReadinessAssessment] = []
        failures = list(batch.mapping_failures)

        for fact in batch.canonical_facts:
            classified = CaptacionesIRRBBAccountClassifier.classify(fact)
            if isinstance(classified, IRRBBSourceMappingFailure):
                failures.append(classified)
            else:
                assessments.append(cls.assess_fact(fact, classified))

        return CaptacionesIRRBBReadinessBatchResult(
            source_record_count=batch.source_record_count,
            assessments=tuple(assessments),
            mapping_failures=tuple(failures),
        )

    @classmethod
    def assess_fact(
        cls,
        fact: CaptacionesXMLCanonicalCurrencyFact,
        classification: CaptacionesIRRBBAccountClassification,
    ) -> CaptacionesIRRBBReadinessAssessment:
        if fact.source_record_id != classification.source_record_id:
            raise ValueError("Captaciones classification changed source_record_id")
        if fact.operation_id != classification.operation_id:
            raise ValueError("Captaciones classification changed operation_id")

        if classification.funding_class is CaptacionesIRRBBFundingClass.SIGHT_NMD:
            return CaptacionesIRRBBReadinessAssessment(
                source_record_id=fact.source_record_id,
                source_reference=fact.source_reference,
                operation_id=fact.operation_id,
                accounting_account_code=fact.accounting_account_code,
                funding_class=classification.funding_class,
                status=CaptacionesIRRBBReadinessStatus.BLOCKED_NMD_BEHAVIORAL_PROFILE,
                missing_capabilities=("APPROVED_NMD_BEHAVIORAL_PROFILE",),
                message=(
                    "Sight Captaciones must be distributed through the governed "
                    "NonMaturityDepositProfileProvider. XML maturity dates must not be "
                    "used as synthetic IRRBB risk dates."
                ),
            )

        if classification.funding_class is CaptacionesIRRBBFundingClass.TERM_MATURED:
            return CaptacionesIRRBBReadinessAssessment(
                source_record_id=fact.source_record_id,
                source_reference=fact.source_reference,
                operation_id=fact.operation_id,
                accounting_account_code=fact.accounting_account_code,
                funding_class=classification.funding_class,
                status=CaptacionesIRRBBReadinessStatus.BLOCKED_MATURED_TERM_POLICY,
                missing_capabilities=("APPROVED_MATURED_TERM_IRRBB_TREATMENT",),
                message=(
                    "Matured term Captaciones require an approved IRRBB treatment before "
                    "they can enter the nineteen time buckets."
                ),
            )

        missing = ["CONTRACTUAL_PAYMENT_SCHEDULE", "TERM_DEPOSIT_CONTRACTUAL_CLASSIFICATION"]
        if fact.rate_type_source_code.upper() != "F":
            missing.extend(
                (
                    "CANONICAL_RATE_TYPE",
                    "NEXT_REPRICING_DATE",
                    "RESIDUAL_PRINCIPAL_AT_REPRICING_OR_PRINCIPAL_COMPONENTS",
                )
            )

        return CaptacionesIRRBBReadinessAssessment(
            source_record_id=fact.source_record_id,
            source_reference=fact.source_reference,
            operation_id=fact.operation_id,
            accounting_account_code=fact.accounting_account_code,
            funding_class=classification.funding_class,
            status=CaptacionesIRRBBReadinessStatus.BLOCKED_CONTRACTUAL_SCHEDULE,
            missing_capabilities=tuple(missing),
            message=(
                "Term Captaciones require governed contractual classification and future "
                "cash-flow evidence before nineteen-band scheduling. Account 213 alone "
                "must not infer CAPF modality, coupon structure, or repricing."
            ),
        )
