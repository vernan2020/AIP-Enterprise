"""Explicit conversion of reconciled, approved monthly plan into dated liquidity.

Input calendar totals are *CRC-million equivalent*, not account-currency
contractual flows. No fractional/daily spread, renewal, FX, or cash forecast is
inferred. Planned amounts are overlays and must be reduced for overlap with
already-scheduled contractual amounts before they can be booked.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from aip.domain.liquidity.cashflow.services.sugef210_projection import (
    LiquidityAssumption,
    LiquidityBalanceArea,
    LiquidityEvidence,
    LiquidityFlowSide,
    LiquidityProjectionFlow,
)
from aip.product.configured.liquidity.financial_plan_source import (
    FinancialPlanSourceAudit,
    MonthlyFinancialPlanInput,
)

_MILLION = Decimal("1000000")
_SCENARIOS = frozenset({"BASE", "IDIOSYNCRATIC", "SYSTEMIC", "COMBINED"})


@dataclass(frozen=True, slots=True)
class ApprovedFinancialPlanAllocation:
    """Individually evidenced payment, not an approval implied by a spreadsheet."""

    driver: str
    year: int
    month: int
    payment_date: date
    currency: str
    incremental_native_amount: Decimal
    overlap_crc_amount: Decimal
    fx_crc_per_usd: Decimal | None
    fx_reference: str
    source_sha256: str
    scenario: str
    assumption_id: str
    approval_reference: str
    plan_document_version: str
    rationale: str
    treasury_reconciliation_reference: str
    nonduplication_reference: str
    valid_from: date
    valid_to: date
    explicitly_approved: bool

    def __post_init__(self) -> None:
        if not all(
            (
                self.driver,
                self.source_sha256,
                self.assumption_id,
                self.approval_reference,
                self.plan_document_version,
                self.rationale,
                self.treasury_reconciliation_reference,
                self.nonduplication_reference,
            )
        ):
            raise ValueError("Plan allocation lacks institutional audit evidence")
        if not self.explicitly_approved:
            raise ValueError("Financial plan allocation is pending institutional approval")
        if self.scenario not in _SCENARIOS:
            raise ValueError("Unsupported planning scenario")
        if self.currency not in {"CRC", "USD"}:
            raise ValueError("Plan allocation requires certified native currency")
        if self.payment_date.year != self.year or self.payment_date.month != self.month:
            raise ValueError("Plan payment date is not inside approved month")
        if self.valid_from > self.valid_to:
            raise ValueError("Plan allocation approval validity is inverted")
        if (
            not self.incremental_native_amount.is_finite()
            or self.incremental_native_amount <= 0
            or not self.overlap_crc_amount.is_finite()
            or self.overlap_crc_amount < 0
        ):
            raise ValueError("Plan allocation amount or reconciled overlap is invalid")
        if self.currency == "USD":
            if (
                self.fx_crc_per_usd is None
                or not self.fx_crc_per_usd.is_finite()
                or self.fx_crc_per_usd <= 0
                or not self.fx_reference
            ):
                raise ValueError("USD plan allocation needs approved CRC FX conversion evidence")
        elif self.fx_crc_per_usd is not None:
            raise ValueError("CRC plan event must not embed a currency conversion")


@dataclass(frozen=True, slots=True)
class ApprovedFinancialPlanEvents:
    cutoff: date
    scenario: str
    events: tuple[LiquidityProjectionFlow, ...]
    assumptions: tuple[LiquidityAssumption, ...]
    source_sha256: str
    status: str = "GOVERNED_PLAN_OVERLAY_NOT_CONTRACTUAL_COVERAGE"


def _plan_key(row: MonthlyFinancialPlanInput) -> tuple[str, int, int]:
    return row.driver, row.year, row.month


def build_approved_financial_plan_events(
    *,
    audit: FinancialPlanSourceAudit,
    cutoff: date,
    scenario: str,
    allocations: Iterable[ApprovedFinancialPlanAllocation],
    existing_contractual_reconciliation_refs: frozenset[str] = frozenset(),
) -> ApprovedFinancialPlanEvents:
    """Convert only separately approved *incremental* dated plan movements."""
    if audit.cutoff != cutoff:
        raise ValueError("Plan audit cutoff differs from projection")
    if scenario not in _SCENARIOS:
        raise ValueError("Unsupported scenario")
    candidates = {
        _plan_key(row): row
        for row in audit.monthly_inputs
        if row.classification == "PLANNED_POTENTIAL_CASHFLOW"
    }
    covered_crc: dict[tuple[str, int, int], Decimal] = defaultdict(Decimal)
    refs: set[str] = set()
    assumptions: dict[str, LiquidityAssumption] = {}
    events: list[LiquidityProjectionFlow] = []

    for approval in allocations:
        key = (approval.driver, approval.year, approval.month)
        source_row = candidates.get(key)
        if source_row is None:
            raise ValueError("Plan driver is noncash, unsupported or absent from monthly calendar")
        if (
            source_row.source_sha256 != approval.source_sha256
            or audit.sha256 != approval.source_sha256
        ):
            raise ValueError("Plan source hash changed after institutional approval")
        if approval.scenario != scenario:
            raise ValueError("Planning approval belongs to a different scenario")
        if not approval.valid_from <= cutoff <= approval.valid_to:
            raise ValueError("Planning approval outside its validity")
        if approval.payment_date <= cutoff:
            raise ValueError("Historical or partial current month cannot be booked as future plan")
        if approval.nonduplication_reference in refs:
            raise ValueError("Duplicate financial plan reconciliation reference")
        if approval.nonduplication_reference in existing_contractual_reconciliation_refs:
            raise ValueError("Plan event overlaps contractual source reconciliation")
        refs.add(approval.nonduplication_reference)
        if approval.assumption_id in assumptions:
            policy = assumptions[approval.assumption_id]
            if policy.approval_reference != approval.approval_reference:
                raise ValueError("Assumption ID used across contradictory approvals")
        else:
            assumptions[approval.assumption_id] = LiquidityAssumption(
                assumption_id=approval.assumption_id,
                rationale=approval.rationale,
                approval_reference=approval.approval_reference,
                valid_from=approval.valid_from,
                valid_to=approval.valid_to,
                source_reference=(
                    f"FINANCIAL_PLAN:{audit.source_name}:{audit.sha256}:"
                    f"{source_row.source_cell}:VERSION:{approval.plan_document_version}"
                ),
                scenario=scenario,
            )
        fx = approval.fx_crc_per_usd if approval.currency == "USD" else Decimal(1)
        assert fx is not None
        gross_equivalent = approval.incremental_native_amount * fx
        covered_crc[key] += gross_equivalent + approval.overlap_crc_amount
        if covered_crc[key] > source_row.reported_value * _MILLION:
            raise ValueError(
                "Allocated plan and overlapping contract exceed monthly planning budget"
            )
        events.append(
            LiquidityProjectionFlow(
                reference=(
                    f"FINPLAN:{audit.sha256}:{source_row.source_cell}:"
                    f"{approval.nonduplication_reference}"
                ),
                source=(
                    f"FINPLAN:{approval.plan_document_version}:{source_row.source_cell}:"
                    f"{approval.treasury_reconciliation_reference}:"
                    f"{approval.fx_reference if approval.currency == 'USD' else 'NATIVE_CRC'}"
                ),
                currency=approval.currency,
                payment_date=approval.payment_date,
                amount=approval.incremental_native_amount,
                side=LiquidityFlowSide(source_row.side),
                area=LiquidityBalanceArea(source_row.area),
                evidence=LiquidityEvidence.GOVERNED_ASSUMPTION,
                assumption_id=approval.assumption_id,
            )
        )
    return ApprovedFinancialPlanEvents(
        cutoff=cutoff,
        scenario=scenario,
        events=tuple(events),
        assumptions=tuple(assumptions.values()),
        source_sha256=audit.sha256,
    )
