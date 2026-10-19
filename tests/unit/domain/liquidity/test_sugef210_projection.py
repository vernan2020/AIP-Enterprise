from __future__ import annotations

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
    sugef210_windows,
)

CUTOFF = date(2026, 9, 30)


def _flow(
    ref: str,
    days: int,
    amount: str,
    *,
    area: LiquidityBalanceArea = LiquidityBalanceArea.ASSET,
    side: LiquidityFlowSide = LiquidityFlowSide.INFLOW,
    currency: str = "CRC",
    assumption_id: str | None = None,
) -> LiquidityProjectionFlow:
    return LiquidityProjectionFlow(
        reference=ref,
        source="INSTITUTIONAL_XML:2026-09",
        currency=currency,
        payment_date=CUTOFF + timedelta(days=days),
        amount=Decimal(amount),
        area=area,
        side=side,
        evidence=(
            LiquidityEvidence.GOVERNED_ASSUMPTION
            if assumption_id
            else LiquidityEvidence.CONTRACTUAL
        ),
        assumption_id=assumption_id,
    )


def test_horizons_include_intraday_seven_days_four_weeks_months_and_quarters():
    windows = sugef210_windows(CUTOFF)
    assert len(windows) == 17
    assert [w.frequency for w in windows[:8]] == ["DAILY"] * 8
    assert [w.frequency for w in windows[8:12]] == ["WEEKLY"] * 4
    assert [w.frequency for w in windows[12:14]] == ["MONTHLY"] * 2
    assert [w.frequency for w in windows[14:]] == ["QUARTERLY"] * 3
    assert windows[0].start == CUTOFF
    assert windows[8].start == date(2026, 10, 8)
    assert windows[11].end == date(2026, 10, 30)
    assert windows[12].start == date(2026, 10, 31)
    assert windows[12].end == CUTOFF + timedelta(days=60)
    assert windows[13].end == CUTOFF + timedelta(days=90)
    assert windows[14].end == CUTOFF + timedelta(days=180)
    assert windows[15].end == CUTOFF + timedelta(days=270)
    assert windows[-1].end == date(2027, 9, 30)
    assert all(
        left.end + timedelta(days=1) == right.start for left, right in zip(windows, windows[1:])
    )


@pytest.mark.parametrize(
    "cutoff",
    [date(2026, 1, 31), date(2026, 2, 28), date(2028, 2, 29)],
)
def test_calendar_boundaries_always_contiguous(cutoff):
    windows = sugef210_windows(cutoff)
    assert windows[-1].end == cutoff + timedelta(days=365)
    assert all(
        left.end + timedelta(days=1) == right.start for left, right in zip(windows, windows[1:])
    )


def test_explicit_assumptions_off_balance_and_currency_separation():
    policy = LiquidityAssumption(
        assumption_id="P1",
        rationale="Documented business liquidity pressure",
        approval_reference="ALCO-2026-09-P1",
        valid_from=CUTOFF,
        valid_to=date(2026, 12, 31),
        source_reference="BUSINESS-PLAN-2026",
        scenario="STRESS",
    )
    flows = (
        _flow("A1", 0, "100"),
        _flow("L1", 1, "35", area=LiquidityBalanceArea.LIABILITY, side=LiquidityFlowSide.OUTFLOW),
        _flow(
            "OB1", 8, "20", area=LiquidityBalanceArea.OFF_BALANCE, side=LiquidityFlowSide.OUTFLOW
        ),
        _flow(
            "EV1",
            31,
            "15",
            area=LiquidityBalanceArea.BUSINESS_EVENT,
            side=LiquidityFlowSide.OUTFLOW,
            assumption_id="P1",
        ),
        _flow("AUSD", 31, "150", currency="USD"),
    )
    result = project_sugef210(
        cutoff=CUTOFF,
        scenario="STRESS",
        flows=flows,
        opening_liquidity={"CRC": Decimal("50"), "USD": Decimal("10")},
        assumptions=[policy],
        source_areas_covered=list(LiquidityBalanceArea),
        source_certification_references={
            area: f"TEST-SOURCE-EVIDENCE-{area.value}" for area in LiquidityBalanceArea
        },
        opening_certification_references={"CRC": "TEST-OPENING-CRC", "USD": "TEST-OPENING-USD"},
    )
    assert result.certified_comprehensive
    assert len(result.rows) == 34
    assert result.rows[0].net_flow == Decimal("100")
    assert result.rows[0].projected_liquidity == Decimal("150")
    assert result.rows[1].projected_liquidity == Decimal("115")
    assert result.rows[8].net_flow == Decimal("-20")
    assert result.rows[12].net_flow == Decimal("-15")
    assert result.rows[12].projected_liquidity == Decimal("80")
    assert result.rows[17 + 12].projected_liquidity == Decimal("160")
    assert result.off_balance_source_covered


def test_missing_off_balance_and_opening_liquidity_never_fabricated():
    result = project_sugef210(
        cutoff=CUTOFF,
        scenario="BASE",
        flows=[_flow("A1", 1, "100")],
        opening_liquidity={"CRC": Decimal("50")},
        source_areas_covered=[LiquidityBalanceArea.ASSET],
    )
    assert not result.certified_comprehensive
    assert result.status == "PARTIAL_EVIDENCE_NOT_CERTIFIED"
    assert "OFF_BALANCE" in result.missing_source_areas
    assert result.opening_liquidity_missing == ("USD",)
    assert all(row.projected_liquidity is None for row in result.rows if row.currency == "USD")


def test_noncontractual_flow_must_have_approved_current_scenario_policy():
    event = _flow(
        "RUNOFF",
        8,
        "100",
        area=LiquidityBalanceArea.LIABILITY,
        side=LiquidityFlowSide.OUTFLOW,
        assumption_id="NOT_APPROVED",
    )
    with pytest.raises(ValueError, match="Assumption missing"):
        project_sugef210(cutoff=CUTOFF, scenario="BASE", flows=[event], opening_liquidity=None)


def test_rejects_duplicate_cashflows_historical_and_unsupported_currency():
    flow = _flow("ONE", 2, "10")
    with pytest.raises(ValueError, match="Duplicate liquidity event"):
        project_sugef210(cutoff=CUTOFF, scenario="BASE", flows=[flow, flow], opening_liquidity=None)
    with pytest.raises(ValueError, match="Historical flow"):
        project_sugef210(
            cutoff=CUTOFF, scenario="BASE", flows=[_flow("OLD", -2, "10")], opening_liquidity=None
        )
    with pytest.raises(ValueError, match="currency"):
        _flow("EUR", 1, "10", currency="EUR")


def test_complete_area_flags_without_attestations_do_not_certify_projection():
    result = project_sugef210(
        cutoff=CUTOFF,
        scenario="BASE",
        flows=[],
        opening_liquidity={"CRC": Decimal("10"), "USD": Decimal("12")},
        source_areas_covered=list(LiquidityBalanceArea),
    )
    assert result.status == "PARTIAL_EVIDENCE_NOT_CERTIFIED"
    assert len(result.unattested_areas) == 4
    assert result.unattested_opening_currencies == ("CRC", "USD")
    assert all(row.financing_need is not None for row in result.rows)


def test_financing_need_requires_real_opening_balance():
    result = project_sugef210(
        cutoff=CUTOFF,
        scenario="BASE",
        flows=[
            _flow(
                "L2", 1, "75", area=LiquidityBalanceArea.LIABILITY, side=LiquidityFlowSide.OUTFLOW
            )
        ],
        opening_liquidity={"CRC": Decimal("20")},
    )
    assert result.rows[1].projected_liquidity == Decimal("-55")
    assert result.rows[1].financing_need == Decimal("55")
    assert all(row.financing_need is None for row in result.rows if row.currency == "USD")


@pytest.mark.parametrize(
    "day,index",
    [
        (0, 0),
        (7, 7),
        (8, 8),
        (30, 11),
        (31, 12),
        (60, 12),
        (61, 13),
        (90, 13),
        (91, 14),
        (180, 14),
        (181, 15),
        (270, 15),
        (271, 16),
        (365, 16),
    ],
)
def test_fixed_day_boundaries_even_for_leap_year(day, index):
    cutoff = date(2028, 2, 29)
    target = cutoff + timedelta(days=day)
    windows = sugef210_windows(cutoff)
    assert [ix for ix, window in enumerate(windows) if window.start <= target <= window.end] == [
        index
    ]


def test_day_366_is_excluded_and_not_reassigned_to_last_window():
    result = project_sugef210(
        cutoff=CUTOFF,
        scenario="BASE",
        flows=[_flow("DAY366", 366, "100")],
        opening_liquidity=None,
    )
    assert result.excluded_out_of_horizon == 1
    assert all(row.net_flow == 0 for row in result.rows)
