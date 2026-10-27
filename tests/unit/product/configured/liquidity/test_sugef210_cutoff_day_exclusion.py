"""SUGEF 2-10 retains intraday D00; prior days must not enter a new cutoff."""

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


def test_historical_cash_cannot_roll_into_new_cutoff():
    with pytest.raises(ValueError, match="Historical flow"):
        project_sugef210(
            cutoff=CUTOFF,
            scenario="BASE",
            flows=(_flow(-1),),
            opening_liquidity={"CRC": Decimal("200")},
        )


def test_assembler_rejects_historical_cash_before_audit():
    with pytest.raises(ValueError, match="Historical source flow"):
        assemble_partial_institutional_projection(
            cutoff=CUTOFF,
            scenario="BASE",
            off_balance_flows=(_flow(-1),),
            off_balance_certification_reference="SYNTHETIC-REVIEW",
        )


def test_intraday_d00_and_next_day_d01_are_distinct_and_reconciled():
    result = project_sugef210(
        cutoff=CUTOFF,
        scenario="BASE",
        flows=(_flow(0), _flow(1)),
        opening_liquidity={"CRC": Decimal("300")},
    )
    rows = {row.window.key: row for row in result.rows if row.currency == "CRC"}
    assert rows["D00"].event_count == 1
    assert rows["D00"].net_flow == Decimal("-100")
    assert rows["D00"].projected_liquidity == Decimal("200")
    assert rows["D01"].event_count == 1
    assert rows["D01"].net_flow == Decimal("-100")
    assert rows["D01"].accumulated_flow == Decimal("-200")
    assert rows["D01"].projected_liquidity == Decimal("100")
    assert result.source_flow_count == 2
    assert result.excluded_out_of_horizon == 0


def test_assembler_audits_intraday_cash_with_native_d00_band():
    result = assemble_partial_institutional_projection(
        cutoff=CUTOFF,
        scenario="BASE",
        off_balance_flows=(_flow(0),),
        off_balance_certification_reference="SYNTHETIC-REVIEW",
    )
    assert len(result.audited_events) == 1
    assert result.audited_events[0].band_key == "D00"
    assert result.audited_events[0].horizon_status == "IN_365D"
    assert result.projection.source_flow_count == 1
    assert result.projection.certified_comprehensive is False


def _rule(projection_day: int) -> ApprovedScenarioRule:
    return ApprovedScenarioRule(
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


def test_approved_scenario_rule_can_use_intraday_d00():
    assert _rule(0).projection_day == 0


@pytest.mark.parametrize("projection_day", (-1, 366))
def test_governed_scenario_rules_reject_dates_outside_d00_to_day365(projection_day):
    with pytest.raises(ValueError, match="requested 365-day horizon"):
        _rule(projection_day)
