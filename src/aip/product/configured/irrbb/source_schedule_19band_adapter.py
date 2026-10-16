"""Bridge certified source contractual schedules to evidence-only nineteen bands.

No XML 6-band proxy, maturity ballooning, inferred coupons, behavioral deposits
or floating-rate residuals. This converts only *source-provided* fixed-rate dated
schedule entries already admitted by the institutional certification boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from aip.application.irrbb.contracts import IRRBBSourceSnapshot
from aip.application.irrbb.source_certification import IRRBBSourceCertificationReport
from aip.domain.irrbb.models import (
    BankingBookSide,
    CashFlowAmountStatus,
    CashFlowDirection,
    IRRBBCashFlow,
    IRRBBInstrumentClass,
    OptionalityType,
    PaymentStructure,
    RateType,
)
from aip.product.configured.irrbb.contractual_cashflow_19band import (
    Contractual19BandEvidenceAggregator,
    Contractual19BandEvidenceResult,
    EvidencedFlow,
)

_SEGMENT_BY_CLASS = {
    IRRBBInstrumentClass.CREDIT: "CREDIT",
    IRRBBInstrumentClass.INVESTMENT: "INVESTMENT",
    IRRBBInstrumentClass.TERM_DEPOSIT: "CAPTACIONES",
    IRRBBInstrumentClass.BORROWING: "BORROWING",
}
_ALLOWED_STRUCTURES = frozenset(
    (PaymentStructure.BULLET, PaymentStructure.AMORTIZING, PaymentStructure.EXPLICIT_SCHEDULE)
)


@dataclass(frozen=True, slots=True)
class CertifiedScheduleEvidence:
    cutoff_date: date
    certified_positions: int
    source_flows: int
    evidence: Contractual19BandEvidenceResult
    status: str = "FIXED_SCHEDULE_EVIDENCE_ONLY_NOT_CERTIFIED_GAP"

    @property
    def publishable_regulatory_gap(self) -> bool:
        return False


def bridge_certified_fixed_schedules(
    *,
    snapshot: IRRBBSourceSnapshot,
    certification: IRRBBSourceCertificationReport,
) -> CertifiedScheduleEvidence:
    """Fail atomically rather than publishing a partial / mixed-source result."""
    if not certification.is_ready:
        raise ValueError("Source certification is not READY")
    if not snapshot.position_records or not snapshot.source_references:
        raise ValueError("Certified snapshot needs positions and source lineage")
    if snapshot.mapping_failures or snapshot.source_exclusions:
        raise ValueError("Incomplete source snapshot cannot be bridged as fully covered")
    flows: list[EvidencedFlow] = []
    seen_positions: set[str] = set()
    for record in snapshot.position_records:
        position = record.position
        if position.position_id in seen_positions:
            raise ValueError("Duplicate certified position identity")
        seen_positions.add(position.position_id)
        segment = _SEGMENT_BY_CLASS.get(position.instrument_class)
        if segment is None:
            raise ValueError("Unsupported investment / funding instrument class")
        expected_side = (
            BankingBookSide.ASSET if segment in {"CREDIT", "INVESTMENT"}
            else BankingBookSide.LIABILITY
        )
        if position.side is not expected_side:
            raise ValueError("Certified position side contradicts instrument class")
        if position.rate_type is not RateType.FIXED:
            raise ValueError("Floating-rate repricing requires its own certified strategy")
        if position.optionality is not OptionalityType.NONE:
            raise ValueError("Embedded optionality requires approved modeling")
        if position.payment_structure not in _ALLOWED_STRUCTURES:
            raise ValueError("Position payment structure is not certified for scheduling")
        if not record.mapping_rule_reference:
            raise ValueError("Contractual source mapping rule is missing")
        if position.maturity_date is None or position.maturity_date < snapshot.cutoff_date:
            raise ValueError("Certified position maturity is absent or prior to cutoff")
        if not record.gap_schedule:
            raise ValueError("Contractual source payment schedule is missing")
        count_principal = 0
        for payment in record.gap_schedule:
            if payment.amount.currency is not position.currency:
                raise ValueError("Contractual schedule currency contradicts position")
            if payment.payment_date < snapshot.cutoff_date:
                raise ValueError("Historical contractual payment found")
            if payment.payment_date > position.maturity_date:
                raise ValueError("Payment date exceeds certified maturity")
            direction = (
                CashFlowDirection.RECEIVABLE if expected_side is BankingBookSide.ASSET
                else CashFlowDirection.PAYABLE
            )
            if payment.direction is not direction:
                raise ValueError("Payment direction contradicts certified position")
            if payment.flow_type.upper() == "PRINCIPAL":
                count_principal += 1
            flows.append(
                EvidencedFlow(
                    segment=segment,
                    validation_reference=record.mapping_rule_reference,
                    cashflow=IRRBBCashFlow(
                        position_id=position.position_id,
                        side=position.side,
                        direction=payment.direction,
                        amount=payment.amount,
                        cashflow_date=payment.payment_date,
                        risk_date=payment.payment_date,
                        flow_type=payment.flow_type,
                        source_reference=payment.source_reference,
                        amount_status=CashFlowAmountStatus.SOURCE_PROVIDED,
                    ),
                )
            )
        if not count_principal:
            raise ValueError("Certified contractual schedule lacks principal payment")
    result = Contractual19BandEvidenceAggregator().aggregate(
        cutoff_date=snapshot.cutoff_date, flows=flows
    )
    if result.total_flows != len(flows):
        raise ValueError("Contractual source flows did not reconcile")
    return CertifiedScheduleEvidence(
        cutoff_date=snapshot.cutoff_date,
        certified_positions=len(snapshot.position_records),
        source_flows=len(flows),
        evidence=result,
    )
