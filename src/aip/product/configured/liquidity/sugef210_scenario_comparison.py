"""Controlled four-scenario comparison of already-governed liquidity sessions.

A comparison does not authorize a missing payment, attest source completeness
or certify a regulatory SUGEF 2-10 projection. It only shows scenario effects
when institutional opening balances and fixed contractual evidence match.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from aip.domain.liquidity.cashflow.services.sugef210_projection import (
    LiquidityEvidence,
)
from aip.product.configured.liquidity.sugef210_opening_session import (
    ConfiguredOpeningSession,
)

_REQUIRED_SCENARIOS = ("BASE", "IDIOSYNCRATIC", "SYSTEMIC", "COMBINED")


@dataclass(frozen=True, slots=True)
class LiquidityScenarioDifference:
    scenario: str
    currency: str
    band_key: str
    net_flow: Decimal
    net_flow_delta_vs_base: Decimal
    accumulated_flow_delta_vs_base: Decimal
    projected_liquidity: Decimal | None
    projected_liquidity_delta_vs_base: Decimal | None
    financing_need: Decimal | None
    financing_need_delta_vs_base: Decimal | None


@dataclass(frozen=True, slots=True)
class LiquidityFourScenarioComparison:
    cutoff: str
    scenarios: tuple[str, ...]
    rows: tuple[LiquidityScenarioDifference, ...]
    missing_evidence_by_scenario: tuple[tuple[str, tuple[str, ...]], ...]
    status: str = "FOUR_SCENARIO_COMPARISON_NOT_REGULATORY_CERTIFICATION"


def _fixed_cashflow_identity(session: ConfiguredOpeningSession) -> tuple[tuple[object, ...], ...]:
    """Only source-contractual events are a common scenario baseline."""
    fixed = (
        (
            item.source_group,
            item.reference,
            item.source_reference,
            item.currency,
            item.payment_date,
            item.native_amount,
            item.side,
            item.area,
            item.band_key,
        )
        for item in session.assembly.audited_events
        if item.evidence == LiquidityEvidence.CONTRACTUAL
    )
    return tuple(sorted(fixed, key=lambda item: (str(item[0]), str(item[1]))))


def _source_snapshot(session: ConfiguredOpeningSession) -> tuple[object, ...]:
    projection = session.assembly.projection
    return (
        session.sight_source_sha256,
        session.bank_support_sha256,
        session.bank_document_sha256,
        session.master_source_sha256,
        session.master_coupon_ledger_sha256,
        session.master_coupon_custodian_sha256,
        session.demand_deposit_source_sha256,
        session.financial_plan_source_sha256,
        session.xml_contractual_source_coverage,
        session.sight_records_approved,
        session.sight_added_by_currency,
        session.master_principal_events_approved,
        session.master_coupon_events_approved,
        session.xml_contractual_events_approved,
        tuple((row.currency, row.window.key, row.opening_liquidity) for row in projection.rows),
        projection.unattested_opening_currencies,
        _fixed_cashflow_identity(session),
    )


def compare_approved_sugef210_scenarios(
    sessions: Iterable[ConfiguredOpeningSession],
) -> LiquidityFourScenarioComparison:
    """Require the same real source snapshot before calculating scenario deltas."""
    supplied = tuple(sessions)
    indexed = {session.scenario: session for session in supplied}
    if len(supplied) != 4 or len(indexed) != 4 or set(indexed) != set(_REQUIRED_SCENARIOS):
        raise ValueError(
            "Four distinct BASE, IDIOSYNCRATIC, SYSTEMIC and COMBINED sessions required"
        )
    base = indexed["BASE"]
    common = _source_snapshot(base)
    cutoff = base.cutoff
    base_projection = base.assembly.projection
    baseline_rows = {(row.currency, row.window.key): row for row in base_projection.rows}
    if len(base_projection.rows) != 34 or len(baseline_rows) != 34:
        raise ValueError("Baseline must have 17 unique windows for CRC and USD")
    output: list[LiquidityScenarioDifference] = []
    missing: list[tuple[str, tuple[str, ...]]] = []
    for scenario in _REQUIRED_SCENARIOS:
        session = indexed[scenario]
        projection = session.assembly.projection
        if (
            session.cutoff != cutoff
            or projection.cutoff != cutoff
            or projection.scenario != scenario
        ):
            raise ValueError("Scenario cutoffs and names must match the source session")
        if projection.windows != base_projection.windows or len(projection.rows) != 34:
            raise ValueError("Liquidity scenario windows differ from baseline")
        if _source_snapshot(session) != common:
            raise ValueError(
                "Scenario has different opening, evidence or fixed contractual cashflows"
            )
        unique: set[tuple[str, str]] = set()
        for row in projection.rows:
            key = row.currency, row.window.key
            if key in unique or key not in baseline_rows:
                raise ValueError("Scenario contains duplicate or unsupported liquidity band")
            unique.add(key)
            base_row = baseline_rows[key]
            if row.projected_liquidity is None or base_row.projected_liquidity is None:
                balance_delta = None
            else:
                balance_delta = row.projected_liquidity - base_row.projected_liquidity
            if row.financing_need is None or base_row.financing_need is None:
                funding_delta = None
            else:
                funding_delta = row.financing_need - base_row.financing_need
            output.append(
                LiquidityScenarioDifference(
                    scenario=scenario,
                    currency=row.currency,
                    band_key=row.window.key,
                    net_flow=row.net_flow,
                    net_flow_delta_vs_base=row.net_flow - base_row.net_flow,
                    accumulated_flow_delta_vs_base=(
                        row.accumulated_flow - base_row.accumulated_flow
                    ),
                    projected_liquidity=row.projected_liquidity,
                    projected_liquidity_delta_vs_base=balance_delta,
                    financing_need=row.financing_need,
                    financing_need_delta_vs_base=funding_delta,
                )
            )
        if len(unique) != 34:
            raise ValueError("Scenario liquidity bands are incomplete")
        missing.append((scenario, session.assembly.missing_institutional_evidence))
    return LiquidityFourScenarioComparison(
        cutoff=cutoff.isoformat(),
        scenarios=_REQUIRED_SCENARIOS,
        rows=tuple(output),
        missing_evidence_by_scenario=tuple(missing),
    )
