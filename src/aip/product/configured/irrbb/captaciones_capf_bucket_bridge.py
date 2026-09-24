from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from aip.application.irrbb import IRRBBSourceMappingFailure, IRRBBSourceMappingFailureCode
from aip.domain.irrbb.models import RateType, TimeBucketAssignment
from aip.domain.irrbb.services.time_bucket_service import IRRBBTimeBucketService
from aip.product.configured.irrbb.captaciones_capf_operation_binding import (
    CaptacionesCAPFJoinedFact,
)
from aip.product.configured.irrbb.captaciones_irrbb_account_classifier import (
    CaptacionesIRRBBAccountClassifier,
    CaptacionesIRRBBFundingClass,
)
from aip.shared.money import Money


@dataclass(frozen=True, slots=True)
class CaptacionesCAPFPrincipalBucketFact:
    """Temporal principal assignment; preserves both sources, never proves EVE readiness."""

    joined_fact: CaptacionesCAPFJoinedFact
    assignment: TimeBucketAssignment
    rule_reference: str

    def __post_init__(self) -> None:
        if self.assignment.risk_date != self.joined_fact.risk_date:
            raise ValueError("CAPF bucket assignment must preserve contractual risk_date")
        if not self.rule_reference.strip():
            raise ValueError("CAPF principal bucket rule_reference is required")

    @property
    def principal(self) -> Money:
        return self.joined_fact.principal

    @property
    def eve_ready(self) -> Literal[False]:
        return False


class CaptacionesCAPFPrincipalBucketBridge:
    """Assign evidenced fixed CAPF principal through the canonical 19-band service.

    The caller supplies joined facts from the same governed monthly cut. This
    temporal boundary does not ingest files, generate contractual interest or
    publish a complete GAP result. XML accrued product is not a future cash flow.
    """

    RULE_REFERENCE = "CAPF_FIXED_PRINCIPAL_MATURITY@1"

    def __init__(
        self,
        *,
        time_bucket_service: type[IRRBBTimeBucketService] = IRRBBTimeBucketService,
    ) -> None:
        self._time_bucket_service = time_bucket_service

    def assign(
        self, *, fact: CaptacionesCAPFJoinedFact, cutoff_date: date
    ) -> CaptacionesCAPFPrincipalBucketFact | IRRBBSourceMappingFailure:
        classified = CaptacionesIRRBBAccountClassifier.classify(fact.xml_fact)
        if isinstance(classified, IRRBBSourceMappingFailure):
            return classified
        error: str | None = None
        if classified.funding_class is not CaptacionesIRRBBFundingClass.TERM_DEPOSIT:
            error = "CAPF principal bucketing requires governed term-deposit classification."
        elif (
            fact.contractual_rate_type is not RateType.FIXED
            or fact.contractual_fact.contractual_rate_type is not RateType.FIXED
            or fact.xml_fact.rate_type_source_code.strip().upper() != "F"
        ):
            error = "CAPF principal bucketing requires consistent fixed-rate evidence."
        elif (
            fact.xml_fact.maturity_date is not None
            and fact.xml_fact.maturity_date != fact.risk_date
        ):
            error = "Conflicting XML and contractual maturity dates cannot be bucketed."
        elif fact.contractual_fact.issue_date > cutoff_date:
            error = "CAPF issue date follows the requested cutoff."
        elif fact.risk_date < cutoff_date:
            error = (
                "Matured CAPF requires approved treatment; no replacement risk date is assigned."
            )
        if error is not None:
            return IRRBBSourceMappingFailure(
                source_record_id=fact.xml_fact.source_record_id,
                source_reference=fact.xml_fact.source_reference,
                code=IRRBBSourceMappingFailureCode.SOURCE_RECORD_REJECTED,
                canonical_field="capf_principal_bucket",
                message=f"{self.RULE_REFERENCE}: {error}",
            )
        assignment = self._time_bucket_service.assign(
            valuation_date=cutoff_date, risk_date=fact.risk_date
        )
        return CaptacionesCAPFPrincipalBucketFact(
            joined_fact=fact,
            assignment=assignment,
            rule_reference=f"{self.RULE_REFERENCE}|{fact.binding_reference}|{classified.rule_reference}",
        )
