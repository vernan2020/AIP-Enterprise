"""Convert governed CAPF/XML joined *principal* into canonical 19-band evidence.

This adapter uses the XML principal, never the colonized XLSX certificate amount.
Coupon frequency and capitalization are not yet converted to interest schedules.
Partial source joins remain visible and never certify the full regulatory GAP.
"""

from __future__ import annotations

from dataclasses import dataclass

from aip.domain.irrbb.models import (
    BankingBookSide,
    CashFlowAmountStatus,
    CashFlowDirection,
    IRRBBCashFlow,
)
from aip.product.configured.irrbb.captaciones_capf_bucket_batch import (
    CaptacionesCAPFPrincipalBucketBatchResult,
)
from aip.product.configured.irrbb.contractual_cashflow_19band import EvidencedFlow


@dataclass(frozen=True, slots=True)
class CAPFPrincipalEvidenceResult:
    source_record_count: int
    converted_principal_count: int
    failed_record_count: int
    flows: tuple[EvidencedFlow, ...]
    status: str = "CAPF_PRINCIPAL_ONLY_NOT_COMPLETE_GAP"

    def __post_init__(self) -> None:
        if self.source_record_count != self.converted_principal_count + self.failed_record_count:
            raise ValueError("Every CAPF source record must be represented exactly once")
        if self.converted_principal_count != len(self.flows):
            raise ValueError("CAPF converted count must match principal flow count")

    @property
    def publishable_regulatory_gap(self) -> bool:
        return False


def adapt_capf_principal(
    batch: CaptacionesCAPFPrincipalBucketBatchResult,
) -> CAPFPrincipalEvidenceResult:
    """Map checked certificate maturities without guessing future interest."""
    converted: list[EvidencedFlow] = []
    for source in batch.bucket_facts:
        joined = source.joined_fact
        if source.assignment.valuation_date != batch.cutoff_date:
            raise ValueError("CAPF bucket cutoffs disagree")
        if source.assignment.risk_date != joined.contractual_fact.maturity_date:
            raise ValueError("CAPF bucket and contractual maturity differ")
        if source.principal != joined.xml_fact.principal:
            raise ValueError("CAPF maturity principal must come from the XML 210")
        converted.append(
            EvidencedFlow(
                segment="CAPTACIONES",
                cashflow=IRRBBCashFlow(
                    position_id=joined.operation_id,
                    side=BankingBookSide.LIABILITY,
                    direction=CashFlowDirection.PAYABLE,
                    amount=joined.xml_fact.principal,
                    cashflow_date=joined.contractual_fact.maturity_date,
                    risk_date=source.assignment.risk_date,
                    flow_type="PRINCIPAL",
                    source_reference=(
                        joined.xml_fact.source_reference
                        + "|"
                        + joined.contractual_fact.source_reference
                    ),
                    amount_status=CashFlowAmountStatus.SOURCE_PROVIDED,
                ),
                validation_reference=source.rule_reference,
            )
        )
    return CAPFPrincipalEvidenceResult(
        source_record_count=batch.source_record_count,
        converted_principal_count=len(converted),
        failed_record_count=len(batch.mapping_failures),
        flows=tuple(converted),
    )
