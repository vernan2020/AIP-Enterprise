"""Allow only individually approved principal dates from the real investment Master.

Original maturity/principal evidence is independently prepared by the certified
Master reader. Approval references and restrictions are checked before any
principal event is included in the SUGEF210 partial cashflow ladder.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from aip.product.configured.liquidity.sugef210_master_maturity_bridge import (
    MasterPrincipalEvidence,
    MasterPrincipalExclusion,
)


@dataclass(frozen=True, slots=True)
class ApprovedMasterPrincipalPosition:
    """Record-level Treasury evidence; no inferred contractual coupons."""

    cashflow_reference: str
    payment_date: date
    original_principal: Decimal
    currency: str
    approval_reference: str
    settlement_availability_reference: str
    restriction_clearance_reference: str
    nonduplication_reference: str

    def __post_init__(self) -> None:
        if not all(
            (
                self.cashflow_reference,
                self.approval_reference,
                self.settlement_availability_reference,
                self.restriction_clearance_reference,
                self.nonduplication_reference,
            )
        ):
            raise ValueError("Master cash event requires dated approval and settlement evidence")
        if self.currency not in {"CRC", "USD"}:
            raise ValueError("Master principal approval needs original CRC or USD currency")
        if not self.original_principal.is_finite() or self.original_principal <= 0:
            raise ValueError("Master principal approval must have positive source amount")


def admit_approved_master_principal(
    *,
    source: MasterPrincipalEvidence,
    cutoff: date,
    expected_master_sha256: str,
    records: Iterable[ApprovedMasterPrincipalPosition],
) -> MasterPrincipalEvidence:
    """Reconcile exact record, amount, currency and date to unchanged Master."""
    if source.cutoff != cutoff or source.master_sha256 != expected_master_sha256:
        raise ValueError("Master approval cutoff or source hash does not match")
    if source.positions_read != len(source.flows) + len(source.excluded):
        raise ValueError("Master included/excluded source rows do not reconcile")
    approvals = tuple(records)
    if not approvals:
        raise ValueError("Master approval requires actual approved records")
    seen: set[str] = set()
    seen_recon: set[str] = set()
    by_reference = {flow.reference: flow for flow in source.flows}
    if len(by_reference) != len(source.flows):
        raise ValueError("Source Master has duplicated principal references")
    for approval in approvals:
        if approval.cashflow_reference in seen:
            raise ValueError("Master authorization contains repeated source reference")
        if approval.nonduplication_reference in seen_recon:
            raise ValueError("Master authorization reuses a nonduplication reference")
        seen.add(approval.cashflow_reference)
        seen_recon.add(approval.nonduplication_reference)
        original = by_reference.get(approval.cashflow_reference)
        if original is None:
            raise ValueError("Approved principal was not in original Master evidence")
        if (
            approval.payment_date != original.payment_date
            or approval.currency != original.currency
            or approval.original_principal != original.amount
        ):
            raise ValueError("Approved principal date/currency/amount differs from source")
        if approval.payment_date <= cutoff:
            raise ValueError("Matured principal cannot be rolled to opening liquidity")
    kept = tuple(event for event in source.flows if event.reference in seen)
    excluded = source.excluded + tuple(
        MasterPrincipalExclusion(
            row=event.reference,
            reason="NOT_INDIVIDUALLY_APPROVED_FOR_LIQUIDITY",
            currency_original=event.currency,
        )
        for event in source.flows
        if event.reference not in seen
    )
    totals = tuple(
        (currency, sum((event.amount for event in kept if event.currency == currency), Decimal(0)))
        for currency in ("CRC", "USD")
    )
    result = MasterPrincipalEvidence(
        cutoff=cutoff,
        master_sha256=source.master_sha256,
        positions_read=source.positions_read,
        flows=kept,
        excluded=excluded,
        principal_by_currency=totals,
    )
    if len(result.flows) != len(approvals) or result.positions_read != len(result.flows) + len(
        result.excluded
    ):
        raise ValueError("Approved Master principal positions did not reconcile")
    return result
