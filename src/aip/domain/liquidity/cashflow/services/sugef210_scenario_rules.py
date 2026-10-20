"""Approved scenario transformations of real, individually reconciled exposures.

No built-in runoff, renewal or credit recovery percentages. A rule must carry
a dated institutional approval, source and immutable version before generating
a noncontractual liquidity event.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable

from aip.domain.liquidity.cashflow.services.sugef210_projection import (
    LiquidityAssumption,
    LiquidityBalanceArea,
    LiquidityEvidence,
    LiquidityFlowSide,
    LiquidityProjectionFlow,
)

SCENARIOS = frozenset({"BASE", "IDIOSYNCRATIC", "SYSTEMIC", "COMBINED"})


@dataclass(frozen=True, slots=True)
class ReconciledBehavioralExposure:
    reference: str
    source_reference: str
    source_cutoff: date
    currency: str
    amount: Decimal
    category: str
    nonduplication_reference: str

    def __post_init__(self) -> None:
        if not all(
            (self.reference, self.source_reference, self.category, self.nonduplication_reference)
        ):
            raise ValueError("Behavioral source requires provenance and reconciliation")
        if self.currency not in {"CRC", "USD"}:
            raise ValueError("Behavioral source currency must be certified")
        if not self.amount.is_finite() or self.amount < 0:
            raise ValueError("Behavioral source balance is invalid")


@dataclass(frozen=True, slots=True)
class ApprovedScenarioRule:
    reference: str
    scenario: str
    exposure_category: str
    factor: Decimal
    projection_day: int
    flow_side: LiquidityFlowSide
    area: LiquidityBalanceArea
    rationale: str
    approval_reference: str
    source_reference: str
    version: str
    approved_on: date
    valid_from: date
    valid_to: date
    explicitly_approved: bool

    def __post_init__(self) -> None:
        if self.scenario not in SCENARIOS:
            raise ValueError("Unsupported liquidity scenario")
        if not all(
            (
                self.reference,
                self.exposure_category,
                self.rationale,
                self.approval_reference,
                self.source_reference,
                self.version,
            )
        ):
            raise ValueError("Scenario rule requires full auditable provenance")
        if not self.explicitly_approved:
            raise ValueError("Unapproved scenario parameter cannot be activated")
        if not self.factor.is_finite() or not Decimal(0) <= self.factor <= Decimal(1):
            raise ValueError("Scenario factor must be between 0 and 1")
        if not 0 <= self.projection_day <= 365:
            raise ValueError("Scenario day must be inside the requested 365-day horizon")
        if self.valid_from > self.valid_to or self.approved_on > self.valid_from:
            raise ValueError("Scenario approval or validity chronology is inconsistent")
        if self.area == LiquidityBalanceArea.ASSET and self.flow_side != LiquidityFlowSide.INFLOW:
            raise ValueError("Recovery rules must record asset inflows")
        if (
            self.area == LiquidityBalanceArea.LIABILITY
            and self.flow_side != LiquidityFlowSide.OUTFLOW
        ):
            raise ValueError("Liability runoff must record outflows")


@dataclass(frozen=True, slots=True)
class ScenarioGeneratedEvidence:
    cutoff: date
    scenario: str
    flows: tuple[LiquidityProjectionFlow, ...]
    assumptions: tuple[LiquidityAssumption, ...]
    matched_exposure_count: int
    status: str = "APPROVED_SCENARIO_EVENTS_ONLY_NOT_FULL_COVERAGE"


def generate_approved_scenario_events(
    *,
    cutoff: date,
    scenario: str,
    exposures: Iterable[ReconciledBehavioralExposure],
    rules: Iterable[ApprovedScenarioRule],
    contractually_scheduled_exposure_refs: frozenset[str] = frozenset(),
) -> ScenarioGeneratedEvidence:
    """Generate scenario events only from certified source amounts and active rules."""
    if scenario not in SCENARIOS:
        raise ValueError("Unsupported liquidity scenario")
    candidates = tuple(exposures)
    approved = tuple(rules)
    seen_exposures: set[str] = set()
    used_reconciliations: set[str] = set()
    for exposure in candidates:
        if exposure.source_cutoff != cutoff:
            raise ValueError("Behavioral exposure cutoff differs from projection")
        if exposure.reference in seen_exposures:
            raise ValueError("Duplicate behavioral source exposure")
        if exposure.nonduplication_reference in used_reconciliations:
            raise ValueError("Duplicate reconciliation of behavioral source balance")
        if exposure.reference in contractually_scheduled_exposure_refs:
            raise ValueError("Behavioral exposure already included in contractual cashflows")
        seen_exposures.add(exposure.reference)
        used_reconciliations.add(exposure.nonduplication_reference)

    # Scenario rules may have multiple explicit dates. Their cumulative
    # withdrawal/call fraction can never exceed original available exposure.
    approved_factor_by_category: dict[str, Decimal] = {}
    seen_category_day: set[tuple[str, int]] = set()
    for rule in approved:
        approved_factor_by_category[rule.exposure_category] = (
            approved_factor_by_category.get(rule.exposure_category, Decimal(0))
            + rule.factor
        )
        if approved_factor_by_category[rule.exposure_category] > Decimal(1):
            raise ValueError("Cumulative scenario factors exceed original exposure")
        key = (rule.exposure_category, rule.projection_day)
        if key in seen_category_day:
            raise ValueError("Duplicate scenario date for the same exposure category")
        seen_category_day.add(key)

    seen_rules: set[str] = set()
    flows: list[LiquidityProjectionFlow] = []
    policies: list[LiquidityAssumption] = []
    matched: set[str] = set()
    for rule in approved:
        if rule.scenario != scenario:
            raise ValueError("Rule cannot be silently reused in another scenario")
        if rule.reference in seen_rules:
            raise ValueError("Duplicate scenario rule reference")
        seen_rules.add(rule.reference)
        if not rule.valid_from <= cutoff <= rule.valid_to:
            raise ValueError("Scenario rule is outside its approval window")
        policy_id = f"SUGEF210:{scenario}:{rule.reference}:{rule.version}"
        policies.append(
            LiquidityAssumption(
                assumption_id=policy_id,
                rationale=rule.rationale,
                approval_reference=rule.approval_reference,
                valid_from=rule.valid_from,
                valid_to=rule.valid_to,
                source_reference=rule.source_reference,
                scenario=scenario,
            )
        )
        for exposure in candidates:
            if exposure.category != rule.exposure_category:
                continue
            matched.add(exposure.reference)
            amount = exposure.amount * rule.factor
            if amount == 0:
                continue
            flows.append(
                LiquidityProjectionFlow(
                    reference=f"BEHAVIORAL:{policy_id}:{exposure.reference}",
                    source=f"{exposure.source_reference}|{exposure.nonduplication_reference}",
                    currency=exposure.currency,
                    payment_date=cutoff + timedelta(days=rule.projection_day),
                    amount=amount,
                    side=rule.flow_side,
                    area=rule.area,
                    evidence=LiquidityEvidence.GOVERNED_ASSUMPTION,
                    assumption_id=policy_id,
                )
            )
    return ScenarioGeneratedEvidence(
        cutoff=cutoff,
        scenario=scenario,
        flows=tuple(flows),
        assumptions=tuple(policies),
        matched_exposure_count=len(matched),
    )
