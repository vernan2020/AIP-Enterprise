from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from aip.domain.liquidity.cashflow.services.sugef210_projection import (
    LiquidityBalanceArea,
    LiquidityFlowSide,
    project_sugef210,
)
from aip.domain.liquidity.cashflow.services.sugef210_scenario_rules import (
    ApprovedScenarioRule,
    ReconciledBehavioralExposure,
    generate_approved_scenario_events,
)

CUTOFF = date(2026, 9, 30)


def _balance() -> ReconciledBehavioralExposure:
    return ReconciledBehavioralExposure(
        reference="DEPOSIT-SOURCE-1",
        source_reference="CONFIA-210-2026-09",
        source_cutoff=CUTOFF,
        currency="CRC",
        amount=Decimal("100.00"),
        category="DEMAND_DEPOSIT",
        nonduplication_reference="DEPOSIT-RECON-1",
    )


def _rule(scenario: str = "COMBINED") -> ApprovedScenarioRule:
    return ApprovedScenarioRule(
        reference="ALCO-RUNOFF-001",
        scenario=scenario,
        exposure_category="DEMAND_DEPOSIT",
        factor=Decimal("0.12"),
        projection_day=2,
        flow_side=LiquidityFlowSide.OUTFLOW,
        area=LiquidityBalanceArea.LIABILITY,
        rationale="Approved historical outflow study under combined shock",
        approval_reference="ALCO-2026-RUNOFF",
        source_reference="TREASURY-RUNOFF-SERIES",
        version="1.0",
        approved_on=date(2026, 9, 20),
        valid_from=CUTOFF,
        valid_to=date(2026, 12, 31),
        explicitly_approved=True,
    )


def test_governed_scenario_preserves_currency_and_feeds_cashflow_ladder():
    result = generate_approved_scenario_events(
        cutoff=CUTOFF,
        scenario="COMBINED",
        exposures=[_balance()],
        rules=[_rule()],
    )
    assert result.matched_exposure_count == 1
    assert len(result.flows) == 1
    assert result.flows[0].amount == Decimal("12.0000")
    assert result.flows[0].currency == "CRC"
    ladder = project_sugef210(
        cutoff=CUTOFF,
        scenario="COMBINED",
        flows=result.flows,
        opening_liquidity={"CRC": Decimal("80")},
        assumptions=result.assumptions,
    )
    assert ladder.rows[2].liability_outflows == Decimal("12.0000")
    assert ladder.rows[2].projected_liquidity == Decimal("68.0000")
    assert not ladder.certified_comprehensive


def test_unapproved_rule_is_blocked_not_silently_activated():
    with pytest.raises(ValueError, match="Unapproved"):
        replace(_rule(), explicitly_approved=False)


def test_scenario_cannot_reuse_missing_cutoff_or_already_scheduled_exposure():
    with pytest.raises(ValueError, match="already included"):
        generate_approved_scenario_events(
            cutoff=CUTOFF,
            scenario="COMBINED",
            exposures=[_balance()],
            rules=[_rule()],
            contractually_scheduled_exposure_refs=frozenset({_balance().reference}),
        )
    with pytest.raises(ValueError, match="cutoff"):
        generate_approved_scenario_events(
            cutoff=CUTOFF,
            scenario="COMBINED",
            exposures=[replace(_balance(), source_cutoff=date(2026, 8, 31))],
            rules=[_rule()],
        )
    with pytest.raises(ValueError, match="another scenario"):
        generate_approved_scenario_events(
            cutoff=CUTOFF,
            scenario="SYSTEMIC",
            exposures=[_balance()],
            rules=[_rule()],
        )


def test_zero_behavioral_factor_emits_no_fake_cashflow():
    result = generate_approved_scenario_events(
        cutoff=CUTOFF,
        scenario="BASE",
        exposures=[_balance()],
        rules=[replace(_rule("BASE"), factor=Decimal(0))],
    )
    assert result.flows == ()
    assert len(result.assumptions) == 1
