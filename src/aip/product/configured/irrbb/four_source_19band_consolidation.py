"""Read-only four-source contractual 19-band consolidation with separate gates.

Each perimeter must independently certify its dated, fixed-rate source schedule.
This is not a regulatory GAP, repricing residual, behavioral model or EVE/NII.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from aip.application.irrbb.contracts import IRRBBSourceSnapshot
from aip.application.irrbb.source_certification import (
    IRRBBSourceCertificationReport,
    IRRBBSourcePerimeter,
)
from aip.product.configured.irrbb.contractual_cashflow_19band import (
    REQUIRED_SEGMENTS,
    Contractual19BandEvidenceAggregator,
    Contractual19BandEvidenceResult,
    EvidencedFlow,
)
from aip.product.configured.irrbb.source_schedule_19band_adapter import (
    bridge_certified_fixed_schedules,
)
from aip.shared.money import Currency

_PERIMETER = {
    "CREDIT": IRRBBSourcePerimeter.CREDIT,
    "INVESTMENT": IRRBBSourcePerimeter.INVESTMENT,
    "CAPTACIONES": IRRBBSourcePerimeter.LIABILITY,
    "BORROWING": IRRBBSourcePerimeter.LIABILITY,
}


@dataclass(frozen=True, slots=True)
class SourceSchedulePerimeter:
    segment: str
    snapshot: IRRBBSourceSnapshot
    certification: IRRBBSourceCertificationReport

    def __post_init__(self) -> None:
        if self.segment not in REQUIRED_SEGMENTS:
            raise ValueError("Unknown banking-book source segment")


@dataclass(frozen=True, slots=True)
class SourcePrincipalReconciliation:
    segment: str
    currency: Currency
    source_principal: Decimal
    scheduled_principal: Decimal
    difference: Decimal
    position_count: int


@dataclass(frozen=True, slots=True)
class ConsolidatedSourceEvidence:
    cutoff_date: date
    evidence: Contractual19BandEvidenceResult
    reconciliation: tuple[SourcePrincipalReconciliation, ...]
    positions_by_segment: tuple[tuple[str, int], ...]
    flows_by_segment: tuple[tuple[str, int], ...]
    flows: tuple[EvidencedFlow, ...]
    status: str = "FOUR_SOURCE_FIXED_SCHEDULE_EVIDENCE_NOT_CERTIFIED_GAP"

    def __post_init__(self) -> None:
        if self.evidence.total_flows != len(self.flows):
            raise ValueError("Consolidation must retain all traced source flows")

    @property
    def publishable_regulatory_gap(self) -> bool:
        return False


def consolidate_four_certified_sources(
    *,
    cutoff_date: date,
    sources: Iterable[SourceSchedulePerimeter],
) -> ConsolidatedSourceEvidence:
    """Fail atomically on any missing, mixed-cutoff or unapproved source."""
    provided = tuple(sources)
    names = tuple(item.segment for item in provided)
    if len(provided) != len(REQUIRED_SEGMENTS) or set(names) != REQUIRED_SEGMENTS:
        raise ValueError("Four unique certified segments are mandatory")
    all_flows: list[EvidencedFlow] = []
    reconciliations: list[SourcePrincipalReconciliation] = []
    positions_by_segment: list[tuple[str, int]] = []
    flows_by_segment: list[tuple[str, int]] = []

    for item in sorted(provided, key=lambda value: value.segment):
        if item.snapshot.cutoff_date != cutoff_date:
            raise ValueError("All contractual source cutoffs must match")
        expected = _PERIMETER[item.segment]
        actual = {req.perimeter for req in item.certification.profile.requirements}
        if expected not in actual or any(
            perimeter not in {expected, IRRBBSourcePerimeter.COMMON} for perimeter in actual
        ):
            raise ValueError("Source certification profile does not cover its perimeter")

        converted = bridge_certified_fixed_schedules(
            snapshot=item.snapshot,
            certification=item.certification,
        )
        if any(flow.segment != item.segment for flow in converted.flows):
            raise ValueError("Source snapshot mixes incompatible instrument segments")

        per_ccy_principal: dict[Currency, Decimal] = defaultdict(Decimal)
        per_ccy_count: dict[Currency, int] = defaultdict(int)
        scheduled: dict[Currency, Decimal] = defaultdict(Decimal)
        for record in item.snapshot.position_records:
            pos = record.position
            per_ccy_principal[pos.currency] += pos.principal.amount
            per_ccy_count[pos.currency] += 1
        for evidenced in converted.flows:
            flow = evidenced.cashflow
            if flow.flow_type.upper() == "PRINCIPAL":
                scheduled[flow.amount.currency] += flow.amount.amount
        for currency in sorted(per_ccy_principal, key=lambda value: value.value):
            source_amount = per_ccy_principal[currency]
            scheduled_amount = scheduled[currency]
            if source_amount != scheduled_amount:
                raise ValueError("Cross-source contractual principal reconciliation failed")
            reconciliations.append(
                SourcePrincipalReconciliation(
                    segment=item.segment,
                    currency=currency,
                    source_principal=source_amount,
                    scheduled_principal=scheduled_amount,
                    difference=source_amount - scheduled_amount,
                    position_count=per_ccy_count[currency],
                )
            )
        positions_by_segment.append((item.segment, converted.certified_positions))
        flows_by_segment.append((item.segment, converted.source_flows))
        all_flows.extend(converted.flows)

    combined = Contractual19BandEvidenceAggregator().aggregate(
        cutoff_date=cutoff_date, flows=all_flows
    )
    if combined.missing_segments or combined.total_flows != len(all_flows):
        raise ValueError("Four-source contractual flow coverage is incomplete")
    if sum(row.flow_count for row in combined.rows) != len(all_flows):
        raise ValueError("Consolidated 19-band counts do not reconcile")

    asset_expected: dict[Currency, Decimal] = defaultdict(Decimal)
    liability_expected: dict[Currency, Decimal] = defaultdict(Decimal)
    for item in all_flows:
        flow = item.cashflow
        expected_amounts = (
            asset_expected if item.segment in {"CREDIT", "INVESTMENT"} else liability_expected
        )
        expected_amounts[flow.amount.currency] += flow.amount.amount
    for currency in set(asset_expected) | set(liability_expected):
        related = tuple(row for row in combined.rows if row.currency is currency)
        if len(related) != 19:
            raise ValueError("Currency is missing one or more canonical time bands")
        if sum(row.assets for row in related) != asset_expected[currency]:
            raise ValueError("Consolidated assets do not reconcile by currency")
        if sum(row.liabilities for row in related) != liability_expected[currency]:
            raise ValueError("Consolidated liabilities do not reconcile by currency")

    return ConsolidatedSourceEvidence(
        cutoff_date=cutoff_date,
        evidence=combined,
        reconciliation=tuple(reconciliations),
        positions_by_segment=tuple(positions_by_segment),
        flows_by_segment=tuple(flows_by_segment),
        flows=tuple(all_flows),
    )
