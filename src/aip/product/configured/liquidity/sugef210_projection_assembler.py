"""Assemble independently governed cash events for the SUGEF 2-10 ladder.

This module never treats a regulatory GAP, an unapproved maturity inventory,
an unvalidated sight balance, or unused funding headroom as cash.
Source reconciliation is performed per original currency and event reference.
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
    LiquidityProjectionFlow,
    LiquidityProjectionResult,
    project_sugef210,
)
from aip.domain.liquidity.cashflow.services.sugef210_scenario_rules import (
    ScenarioGeneratedEvidence,
)
from aip.product.configured.liquidity.financial_plan_cashflow_bridge import (
    ApprovedFinancialPlanEvents,
)
from aip.product.configured.liquidity.irrbb_schedule_liquidity_bridge import (
    LiquiditySourceBridgeResult,
)
from aip.product.configured.liquidity.sight_investment_opening_bridge import (
    SightOpeningLiquidityResult,
)
from aip.product.configured.liquidity.sugef210_dated_xml_contracts import (
    ApprovedXMLContractualSchedule,
)
from aip.product.configured.liquidity.sugef210_master_maturity_bridge import (
    MasterPrincipalEvidence,
)


@dataclass(frozen=True, slots=True)
class LiquiditySourceReconciliation:
    source_name: str
    currency: str
    received_events: int
    events_inside_horizon: int
    events_after_horizon: int
    principal_or_flow_total_inside_horizon: Decimal
    status: str


@dataclass(frozen=True, slots=True)
class InstitutionalLiquidityAssembly:
    projection: LiquidityProjectionResult
    source_reconciliations: tuple[LiquiditySourceReconciliation, ...]
    missing_institutional_evidence: tuple[str, ...]
    status: str = "PARTIAL_INSTITUTIONAL_LIQUIDITY_NOT_CERTIFIED"


def assemble_partial_institutional_projection(
    *,
    cutoff: date,
    scenario: str,
    master: MasterPrincipalEvidence | None = None,
    master_maturity_recognition_reference: str | None = None,
    contractual: LiquiditySourceBridgeResult | None = None,
    approved_xml_schedule: ApprovedXMLContractualSchedule | None = None,
    approved_plan: ApprovedFinancialPlanEvents | None = None,
    approved_behavioral: ScenarioGeneratedEvidence | None = None,
    off_balance_flows: Iterable[LiquidityProjectionFlow] = (),
    off_balance_certification_reference: str | None = None,
    opening_by_currency: dict[str, Decimal] | None = None,
    verified_sight_opening: SightOpeningLiquidityResult | None = None,
    opening_certifications: dict[str, str] | None = None,
    opening_nonduplication_reference: str | None = None,
    already_in_opening: frozenset[str] = frozenset(),
) -> InstitutionalLiquidityAssembly:
    """Return 17×2 cashflow bands; do not imply complete regulatory coverage.

    The Master principal schedule may be inspected without being booked. To
    recognize it, an independent settlement/restriction approval is required.
    Scenario and plan events enter only through their already approved bridges.
    """
    groups: list[tuple[str, tuple[LiquidityProjectionFlow, ...], str]] = []
    assumptions: list[LiquidityAssumption] = []
    missing: list[str] = []
    areas: set[LiquidityBalanceArea] = set()

    if master is None:
        missing.append("MASTER_NOT_LOADED")
    else:
        if master.cutoff != cutoff:
            raise ValueError("Investment Master cutoff differs from projection")
        if master.positions_read != len(master.flows) + len(master.excluded):
            raise ValueError("Master source rows do not reconcile to included/excluded records")
        for currency, expected in master.principal_by_currency:
            actual = sum(
                (flow.amount for flow in master.flows if flow.currency == currency),
                Decimal(0),
            )
            if actual != expected:
                raise ValueError("Master principal balance does not reconcile by currency")
        if not master_maturity_recognition_reference:
            missing.append("MASTER_MATURITIES_NOT_APPROVED_AS_LIQUIDITY_EVENTS")
        else:
            groups.append(("MASTER_RECOGNIZED_PRINCIPAL", master.flows, master.status))
            areas.add(LiquidityBalanceArea.ASSET)
        missing.append("INVESTMENT_COUPONS_AND_UNRESOLVED_MATURITIES")

    if contractual is not None and approved_xml_schedule is not None:
        raise ValueError(
            "Certified four-source contractual schedule and selected XML payments "
            "overlap the same credit, deposit and borrowing source perimeter"
        )
    if contractual is None:
        missing.extend(("CREDIT_PAYMENTS", "DEPOSIT_PAYMENTS", "BORROWING_PAYMENTS"))
    else:
        if contractual.source_status != "CERTIFIED_CONTRACTUAL_DATES_ONLY_OFFBALANCE_NOT_INCLUDED":
            raise ValueError("Contractual schedule lacks certified source-date evidence")
        if master_maturity_recognition_reference and master is not None:
            if any(item.reference.startswith("INVESTMENT:") for item in contractual.cashflows):
                raise ValueError("Master principal and contractual investments may overlap")
        groups.append(
            ("CERTIFIED_DATED_SOURCE_SCHEDULE", contractual.cashflows, contractual.source_status)
        )
        areas.update(contractual.covered_balance_areas)

    if approved_xml_schedule is not None:
        source_events = approved_xml_schedule.events
        if approved_xml_schedule.cutoff != cutoff:
            raise ValueError("Contractual XML payment ledger cutoff does not match projection")
        if approved_xml_schedule.status != "SELECTED_SOURCE_DATED_PAYMENTS_NOT_COMPLETE_PERIMETER":
            raise ValueError("Source contractual payments have unapproved coverage status")
        if not source_events or not approved_xml_schedule.source_hashes:
            raise ValueError("Source payment ledger has no reconciled XML cash events")
        groups.append(("APPROVED_XML_DATED_CONTRACTS", source_events, approved_xml_schedule.status))
        areas.update(event.area for event in source_events)
        # Individual validated rows do not attest the entire asset or liability perimeter.
        missing.append("UNSELECTED_CREDIT_DEPOSIT_AND_BORROWING_SOURCE_RECORDS")

    if approved_plan is not None:
        if approved_plan.cutoff != cutoff or approved_plan.scenario != scenario:
            raise ValueError("Plan allocation cut-off or scenario is inconsistent")
        groups.append(("APPROVED_PLAN_EVENTS", approved_plan.events, approved_plan.status))
        assumptions.extend(approved_plan.assumptions)
        areas.add(LiquidityBalanceArea.BUSINESS_EVENT)
    else:
        missing.append("PLAN_SCENARIOS_UNAPPROVED_OR_NOT_LOADED")

    if approved_behavioral is not None:
        if approved_behavioral.cutoff != cutoff or approved_behavioral.scenario != scenario:
            raise ValueError("Behavioral approval cut-off or scenario is inconsistent")
        groups.append(
            ("APPROVED_SCENARIO_EVENTS", approved_behavioral.flows, approved_behavioral.status)
        )
        assumptions.extend(approved_behavioral.assumptions)
    else:
        missing.append("DEPOSIT_RUNOFF_AND_OTHER_BEHAVIORAL_ASSUMPTIONS_NOT_APPROVED")

    outside = tuple(off_balance_flows)
    if outside:
        if not off_balance_certification_reference:
            raise ValueError("Off-balance cash events require independent certification")
        if any(
            event.area != LiquidityBalanceArea.OFF_BALANCE
            or event.evidence != LiquidityEvidence.CONTRACTUAL
            for event in outside
        ):
            raise ValueError("Only contractually evidenced off-balance events can be imported")
        groups.append(("CERTIFIED_OFF_BALANCE", outside, off_balance_certification_reference))
        areas.add(LiquidityBalanceArea.OFF_BALANCE)
    else:
        missing.append("OFF_BALANCE_COMMITMENT_COVERAGE_NOT_CERTIFIED")

    if verified_sight_opening is not None:
        sight = verified_sight_opening
        if sight.cutoff != cutoff:
            raise ValueError("Sight investment opening cutoff differs from projection")
        if sight.status != "OPENING_XML_SIGHT_FUNDS_VERIFIED_NO_FUTURE_CASHFLOW":
            raise ValueError("Sight investment approval is not an opening-cash certification")
        if sight.included_xml_accounts != len(sight.included_source_references):
            raise ValueError("Sight investment opening lacks individual source reconciliation")
        if len(set(sight.included_source_references)) != len(sight.included_source_references):
            raise ValueError("Sight investment account appears more than once")
        if sight.included_xml_accounts and (
            not sight.xml_sha256 or not sight.opening_reconciliation_reference
        ):
            raise ValueError("Sight XML hash and reconciliation reference are mandatory")
        if sight.included_xml_accounts and (
            sight.opening_reconciliation_reference != opening_nonduplication_reference
        ):
            raise ValueError("Sight source and opening cash reconciliation references differ")
        source_totals = dict(sight.added_by_currency)
        if len(source_totals) != len(sight.added_by_currency) or any(
            amount < 0 or not amount.is_finite() for amount in source_totals.values()
        ):
            raise ValueError("Sight source additions are not a valid currency reconciliation")
        if any(
            amount > dict(sight.opening_by_currency).get(currency, Decimal(0))
            for currency, amount in source_totals.items()
        ):
            raise ValueError("Approved sight additions exceed bank-reconciled opening cash")
        if any(source in already_in_opening for source in sight.included_source_references):
            raise ValueError("Sight account already exists in opening balance")
        if any(
            source in {event.reference for group in groups for event in group[1]}
            for source in sight.included_source_references
        ):
            raise ValueError("Sight investment duplicates a scheduled event")
        if opening_by_currency is None or opening_by_currency != dict(sight.opening_by_currency):
            raise ValueError("Opening cash must reconcile exactly to the verified sight bridge")

    if opening_by_currency:
        if not opening_nonduplication_reference:
            raise ValueError("Opening liquidity requires independent nonduplication review")
        if not opening_certifications or any(
            not opening_certifications.get(currency) for currency in opening_by_currency
        ):
            raise ValueError("Opening cash lacks verified source/currency certification")
    else:
        missing.append("OPENING_CASH_UNAVAILABLE_OR_NOT_CERTIFIED")

    all_events: list[LiquidityProjectionFlow] = []
    reconciliations: list[LiquiditySourceReconciliation] = []
    seen: set[str] = set()
    for source_name, flows, status in groups:
        for flow in flows:
            if flow.reference in already_in_opening:
                raise ValueError("Cash event is already present in opening balance")
            if flow.reference in seen:
                raise ValueError("Duplicate cash event across institutional sources")
            seen.add(flow.reference)
            if flow.payment_date < cutoff:
                raise ValueError("Historical source flow cannot enter projected liquidity")
            all_events.append(flow)
        for currency in ("CRC", "USD"):
            selected = tuple(flow for flow in flows if flow.currency == currency)
            inside = tuple(
                flow for flow in selected if flow.payment_date <= cutoff + timedelta(days=365)
            )
            reconciliations.append(
                LiquiditySourceReconciliation(
                    source_name=source_name,
                    currency=currency,
                    received_events=len(selected),
                    events_inside_horizon=len(inside),
                    events_after_horizon=len(selected) - len(inside),
                    principal_or_flow_total_inside_horizon=sum(
                        (flow.amount for flow in inside), Decimal(0)
                    ),
                    status=status,
                )
            )
    expected_ids = [policy.assumption_id for policy in assumptions]
    if len(set(expected_ids)) != len(expected_ids):
        raise ValueError("Assumption identifier reused across incompatible source modules")

    # Full source attestations are intentionally NOT synthesized from partial
    # XML presence, recognition references, or generic area labels.
    projection = project_sugef210(
        cutoff=cutoff,
        scenario=scenario,
        flows=all_events,
        assumptions=assumptions,
        opening_liquidity=opening_by_currency,
        source_areas_covered=areas,
        opening_certification_references=opening_certifications,
    )
    if projection.source_flow_count != len(all_events):
        raise ValueError("Source event count does not reconcile with engine")
    inside_count = sum(row.event_count for row in projection.rows)
    if inside_count + projection.excluded_out_of_horizon != len(all_events):
        raise ValueError("Projected horizon does not reconcile source event counts")
    if projection.certified_comprehensive:
        raise ValueError("Partial assembly must never claim full regulatory certification")
    return InstitutionalLiquidityAssembly(
        projection=projection,
        source_reconciliations=tuple(reconciliations),
        missing_institutional_evidence=tuple(sorted(set(missing))),
    )
