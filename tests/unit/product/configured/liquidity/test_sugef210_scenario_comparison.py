"""Four-scenario SUGEF 2-10 comparison must share a documented source baseline."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from aip.domain.liquidity.cashflow.services.sugef210_projection import (
    LiquidityAssumption,
    LiquidityBalanceArea,
    LiquidityEvidence,
    LiquidityFlowSide,
    LiquidityProjectionFlow,
    project_sugef210,
)
from aip.product.configured.liquidity.sugef210_opening_session import (
    ConfiguredOpeningSession,
)
from aip.product.configured.liquidity.sugef210_projection_assembler import (
    InstitutionalLiquidityAssembly,
    LiquidityAuditedCashEvent,
)
from aip.product.configured.liquidity.sugef210_scenario_comparison import (
    compare_approved_sugef210_scenarios,
)

CUTOFF = date(2026, 9, 30)
SCENARIOS = ("BASE", "IDIOSYNCRATIC", "SYSTEMIC", "COMBINED")


def _session(scenario: str, *, no_opening: bool = False) -> ConfiguredOpeningSession:
    baseline = LiquidityProjectionFlow(
        reference="FIXED-PRINCIPAL-1",
        source="SOURCE-XML-HASH-1",
        currency="CRC",
        payment_date=CUTOFF + timedelta(days=1),
        amount=Decimal("20"),
        side=LiquidityFlowSide.INFLOW,
        area=LiquidityBalanceArea.ASSET,
        evidence=LiquidityEvidence.CONTRACTUAL,
    )
    flows = [baseline]
    assumptions = []
    audited = [
        LiquidityAuditedCashEvent(
            source_group="APPROVED_XML_DATED_CONTRACTS",
            source_status="SELECTED_SOURCE_DATED_PAYMENTS_NOT_COMPLETE_PERIMETER",
            reference=baseline.reference,
            source_reference=baseline.source,
            currency=baseline.currency,
            payment_date=baseline.payment_date,
            native_amount=baseline.amount,
            area=baseline.area,
            side=baseline.side,
            evidence=baseline.evidence,
            assumption_id=None,
            band_key="D01",
            horizon_status="IN_365D",
        )
    ]
    if scenario != "BASE":
        cash = {"IDIOSYNCRATIC": "10", "SYSTEMIC": "20", "COMBINED": "30"}[scenario]
        stress = LiquidityProjectionFlow(
            reference="TEST-STRESS-" + scenario,
            source="GOVERNED-SCENARIO-SOURCE",
            currency="CRC",
            payment_date=CUTOFF + timedelta(days=2),
            amount=Decimal(cash),
            side=LiquidityFlowSide.OUTFLOW,
            area=LiquidityBalanceArea.LIABILITY,
            evidence=LiquidityEvidence.GOVERNED_ASSUMPTION,
            assumption_id="GOVERNED-" + scenario,
        )
        flows.append(stress)
        assumptions.append(
            LiquidityAssumption(
                assumption_id="GOVERNED-" + scenario,
                rationale="Synthetic controlled stress delta",
                approval_reference="TEST-ONLY",
                valid_from=CUTOFF - timedelta(days=1),
                valid_to=CUTOFF + timedelta(days=30),
                source_reference="TEST-APPROVAL",
                scenario=scenario,
            )
        )
        audited.append(
            LiquidityAuditedCashEvent(
                source_group="APPROVED_SCENARIO_EVENTS",
                source_status="APPROVED_SCENARIO_EVENTS_ONLY_NOT_FULL_COVERAGE",
                reference=stress.reference,
                source_reference=stress.source,
                currency=stress.currency,
                payment_date=stress.payment_date,
                native_amount=stress.amount,
                area=stress.area,
                side=stress.side,
                evidence=stress.evidence,
                assumption_id=stress.assumption_id,
                band_key="D02",
                horizon_status="IN_365D",
            )
        )
    projection = project_sugef210(
        cutoff=CUTOFF,
        scenario=scenario,
        flows=flows,
        assumptions=assumptions,
        opening_liquidity=None if no_opening else {"CRC": Decimal("100"), "USD": Decimal("50")},
    )
    assembly = InstitutionalLiquidityAssembly(
        projection=projection,
        source_reconciliations=(),
        missing_institutional_evidence=("UNAPPROVED_PERIMETER",),
        audited_events=tuple(audited),
    )
    return ConfiguredOpeningSession(
        cutoff=CUTOFF,
        scenario=scenario,
        assembly=assembly,
        sight_records_approved=1,
        sight_source_sha256="a" * 64,
        bank_support_sha256="b" * 64,
        bank_document_sha256="c" * 64,
        master_source_sha256="d" * 64,
        xml_contractual_source_coverage=(("CREDIT", 1, 2),),
    )


def test_scenarios_compare_crc_and_usd_without_fake_certification():
    result = compare_approved_sugef210_scenarios(_session(s) for s in SCENARIOS)
    assert len(result.rows) == 136
    assert result.scenarios == SCENARIOS
    assert result.cutoff == CUTOFF.isoformat()
    assert result.status == "FOUR_SCENARIO_COMPARISON_NOT_REGULATORY_CERTIFICATION"
    base = next(row for row in result.rows if row.scenario == "BASE" and row.band_key == "D02" and row.currency == "CRC")
    combined = next(row for row in result.rows if row.scenario == "COMBINED" and row.band_key == "D02" and row.currency == "CRC")
    assert base.projected_liquidity == Decimal("120")
    assert combined.projected_liquidity == Decimal("90")
    assert combined.net_flow_delta_vs_base == Decimal("-30")
    assert combined.accumulated_flow_delta_vs_base == Decimal("-30")
    assert combined.projected_liquidity_delta_vs_base == Decimal("-30")
    assert all(row.projected_liquidity_delta_vs_base == Decimal(0) for row in result.rows if row.scenario == "BASE")
    assert all(row.currency in {"CRC", "USD"} for row in result.rows)
    assert len(result.missing_evidence_by_scenario) == 4


def test_scenario_comparison_rejects_mixed_bank_and_investment_snapshots():
    sessions = [_session(s) for s in SCENARIOS]
    sessions[2] = replace(sessions[2], bank_document_sha256="another-bank-file")
    with pytest.raises(ValueError, match="different opening, evidence"):
        compare_approved_sugef210_scenarios(sessions)
    sessions[2] = replace(_session("SYSTEMIC"), master_source_sha256="another-master")
    with pytest.raises(ValueError, match="different opening, evidence"):
        compare_approved_sugef210_scenarios(sessions)


def test_scenario_comparison_rejects_changed_contractual_baseline():
    sessions = [_session(s) for s in SCENARIOS]
    wrong = sessions[1]
    altered = replace(
        wrong.assembly.audited_events[0],
        native_amount=Decimal("25"),
    )
    sessions[1] = replace(
        wrong,
        assembly=replace(
            wrong.assembly,
            audited_events=(altered,) + wrong.assembly.audited_events[1:],
        ),
    )
    with pytest.raises(ValueError, match="fixed contractual cashflows"):
        compare_approved_sugef210_scenarios(sessions)


def test_scenario_comparison_preserves_unknown_opening_without_zero_substitution():
    result = compare_approved_sugef210_scenarios(
        _session(s, no_opening=True) for s in SCENARIOS
    )
    combined = next(
        row for row in result.rows
        if row.scenario == "COMBINED" and row.currency == "CRC" and row.band_key == "D02"
    )
    assert combined.net_flow_delta_vs_base == Decimal("-30")
    assert combined.projected_liquidity is None
    assert combined.projected_liquidity_delta_vs_base is None
    assert combined.financing_need is None
    assert combined.financing_need_delta_vs_base is None


def test_scenario_comparison_requires_four_unique_correct_cutoffs():
    with pytest.raises(ValueError, match="Four distinct"):
        compare_approved_sugef210_scenarios([_session("BASE")] * 4)
    with pytest.raises(ValueError, match="Four distinct"):
        compare_approved_sugef210_scenarios(_session(s) for s in SCENARIOS[:3])
    sessions = [_session(s) for s in SCENARIOS]
    sessions[-1] = replace(sessions[-1], cutoff=CUTOFF - timedelta(days=1))
    with pytest.raises(ValueError, match="cutoffs and names"):
        compare_approved_sugef210_scenarios(sessions)
