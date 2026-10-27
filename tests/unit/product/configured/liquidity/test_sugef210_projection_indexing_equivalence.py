"""Regression tests: fast distribution must preserve certified cash formulas."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from aip.domain.liquidity.cashflow.services.sugef210_projection import (
    LiquidityBalanceArea,
    LiquidityEvidence,
    LiquidityFlowSide,
    LiquidityProjectionFlow,
    project_sugef210,
    sugef210_windows,
)

CUTOFF = date(2026, 9, 30)


def _events() -> tuple[LiquidityProjectionFlow, ...]:
    areas = tuple(LiquidityBalanceArea)
    sides = tuple(LiquidityFlowSide)
    return tuple(
        LiquidityProjectionFlow(
            reference=f"src-{number}",
            source="APPROVED_TEST_ONLY",
            currency=("CRC", "USD")[number % 2],
            payment_date=CUTOFF + timedelta(days=(number % 366) + 1),
            amount=Decimal(number % 29 + 1) / Decimal("7"),
            side=sides[(number // 2) % len(sides)],
            area=areas[(number // 4) % len(areas)],
            evidence=LiquidityEvidence.CONTRACTUAL,
        )
        for number in range(1000)
    )


def test_one_pass_window_index_matches_independent_reference_sums():
    flows = _events()
    opening = {"CRC": Decimal("175.50"), "USD": Decimal("88.25")}
    actual = project_sugef210(
        cutoff=CUTOFF,
        scenario="BASE",
        flows=flows,
        opening_liquidity=opening,
    )
    assert len(actual.windows) == 17
    assert len(actual.rows) == 34
    assert actual.windows == sugef210_windows(CUTOFF)
    assert actual.source_flow_count == len(flows)
    assert actual.excluded_out_of_horizon == sum(
        event.payment_date > CUTOFF + timedelta(days=365) for event in flows
    )
    for currency in ("CRC", "USD"):
        running = Decimal(0)
        for window in actual.windows:
            selected = [
                event
                for event in flows
                if event.currency == currency and window.start <= event.payment_date <= window.end
            ]

            def subtotal(area: LiquidityBalanceArea, side: LiquidityFlowSide) -> Decimal:
                return sum(
                    (
                        event.amount
                        for event in selected
                        if event.area == area and event.side == side
                    ),
                    Decimal(0),
                )

            asset_in = subtotal(LiquidityBalanceArea.ASSET, LiquidityFlowSide.INFLOW)
            asset_out = subtotal(LiquidityBalanceArea.ASSET, LiquidityFlowSide.OUTFLOW)
            liability_in = subtotal(LiquidityBalanceArea.LIABILITY, LiquidityFlowSide.INFLOW)
            liability_out = subtotal(LiquidityBalanceArea.LIABILITY, LiquidityFlowSide.OUTFLOW)
            off_in = subtotal(LiquidityBalanceArea.OFF_BALANCE, LiquidityFlowSide.INFLOW)
            off_out = subtotal(LiquidityBalanceArea.OFF_BALANCE, LiquidityFlowSide.OUTFLOW)
            business_in = subtotal(LiquidityBalanceArea.BUSINESS_EVENT, LiquidityFlowSide.INFLOW)
            business_out = subtotal(LiquidityBalanceArea.BUSINESS_EVENT, LiquidityFlowSide.OUTFLOW)
            net = (
                asset_in
                + liability_in
                + off_in
                + business_in
                - asset_out
                - liability_out
                - off_out
                - business_out
            )
            running += net
            row = next(
                item for item in actual.rows if item.currency == currency and item.window == window
            )
            assert row.asset_inflows == asset_in
            assert row.asset_outflows == asset_out
            assert row.liability_inflows == liability_in
            assert row.liability_outflows == liability_out
            assert row.off_balance_inflows == off_in
            assert row.off_balance_outflows == off_out
            assert row.other_inflows == business_in
            assert row.other_outflows == business_out
            assert row.net_flow == net
            assert row.accumulated_flow == running
            assert row.projected_liquidity == opening[currency] + running
            assert row.financing_need == max(Decimal(0), -(opening[currency] + running))
            assert row.event_count == len(selected)


def test_fast_index_preserves_unknown_opening_and_source_incompleteness():
    actual = project_sugef210(
        cutoff=CUTOFF, scenario="BASE", flows=_events(), opening_liquidity=None
    )
    assert actual.status == "PARTIAL_EVIDENCE_NOT_CERTIFIED"
    assert actual.opening_liquidity_missing == ("CRC", "USD")
    assert all(row.projected_liquidity is None for row in actual.rows)
    assert all(row.financing_need is None for row in actual.rows)
