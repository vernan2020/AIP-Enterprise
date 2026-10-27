"""Cutoff-day cash belongs to bank-reconciled opening, never future liquidity bands."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from aip.domain.liquidity.cashflow.services.sugef210_projection import (
    LiquidityBalanceArea,
    LiquidityEvidence,
    LiquidityFlowSide,
    LiquidityProjectionFlow,
    project_sugef210,
)
from aip.domain.liquidity.cashflow.services.sugef210_scenario_rules import (
    ApprovedScenarioRule,
)
from aip.product.configured.liquidity.sugef210_projection_assembler import (
    assemble_partial_institutional_projection,
)

CUTOFF = date(2026, 9, 30)


def _flow(day: int) -> LiquidityProjectionFlow:
    return LiquidityProjectionFlow(
        reference=f"TEST-SOURCE-DAY-{day}",
        source="SYNTHETIC-APPROVED-ONLY",
        currency="CRC",
        payment_date=CUTOFF + timedelta(days=day),
        amount=Decimal("100"),
        side=LiquidityFlowSide.OUTFLOW,
        area=LiquidityBalanceArea.OFF_BALANCE,
        evidence=LiquidityEvidence.CONTRACTUAL,
    )


@pytest.mark.parametrize("day", (-1, 0))
def test_engine_rejects_cutoff_or_historical_cash_instead_of_dropping_event(day):
    with pytest.raises(ValueError, match="opening reconciliation"):
        project_sugef210(
            cutoff=CUTOFF,
            scenario="BASE",
            flows=(_flow(day),),
            opening_liquidity={"CRC": Decimal("200")},
        )


@pytest.mark.parametrize("day", (-1, 0))
def test_assembler_blocks_cutoff_day_prior_to_future_band_audit(day):
    with pytest.raises(ValueError, match="reconcile to opening"):
        assemble_partial_institutional_projection(
            cutoff=CUTOFF,
            scenario="BASE",
            off_balance_flows=(_flow(day),),
            off_balance_certification_reference="SYNTHETIC-REVIEW",
        )


def test_first_future_day_is_included_and_opening_kept_separate():
    result = project_sugef210(
        cutoff=CUTOFF,
        scenario="BASE",
        flows=(_flow(1),),
        opening_liquidity={"CRC": Decimal("200")},
    )
    crc_day_one = next(
        row
        for row in result.rows
        if row.currency == "CRC" and row.window.key == "D01"
    )
    assert crc_day_one.event_count == 1
    assert crc_day_one.net_flow == Decimal("-100")
    assert crc_day_one.opening_liquidity == Decimal("200")
    assert crc_day_one.projected_liquidity == Decimal("100")
    assert result.excluded_out_of_horizon == 0



@pytest.mark.parametrize("projection_day", (0, 366))
def test_governed_scenario_rule_rejects_days_outside_future_bands(projection_day):
    with pytest.raises(ValueError, match="1 to 365"):
        ApprovedScenarioRule(
            reference="TEST-SCENARIO-RULE",
            scenario="BASE",
            exposure_category="TEST-EXPOSURE",
            factor=Decimal("0.1"),
            projection_day=projection_day,
            flow_side=LiquidityFlowSide.OUTFLOW,
            area=LiquidityBalanceArea.LIABILITY,
            rationale="Synthetic scenario boundary check",
            approval_reference="SYNTHETIC-NOT-AN-INSTITUTIONAL-APPROVAL",
            source_reference="SYNTHETIC",
            version="1",
            approved_on=CUTOFF - timedelta(days=2),
            valid_from=CUTOFF - timedelta(days=1),
            valid_to=CUTOFF + timedelta(days=30),
            explicitly_approved=True,
        )
