"""Real-source maturity inventory indexing: fixtures only, no invented AIP cash."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from aip.domain.liquidity.cashflow.services.sugef210_projection import (
    LiquidityBalanceArea,
    LiquidityEvidence,
    LiquidityFlowSide,
    LiquidityProjectionFlow,
    sugef210_windows,
)
from aip.product.configured.liquidity.sugef210_source_audit_cli import (
    native_principal_by_maturity_band,
)


def _principal(cutoff: date, n: int, day: int, currency: str) -> LiquidityProjectionFlow:
    return LiquidityProjectionFlow(
        reference=f"TEST-MASTER-ROW-{n:05d}",
        source="TEST-ONLY-ORIGINAL-MASTER",
        currency=currency,
        payment_date=cutoff + timedelta(days=day),
        amount=Decimal("0.01"),
        side=LiquidityFlowSide.INFLOW,
        area=LiquidityBalanceArea.ASSET,
        evidence=LiquidityEvidence.CONTRACTUAL,
    )


def test_monthly_source_inventory_index_matches_reference_scan_for_all_34_rows() -> None:
    cutoff = date(2026, 9, 30)
    windows = sugef210_windows(cutoff)
    flows = tuple(
        _principal(cutoff, n, n % 367, "CRC" if n % 2 == 0 else "USD")
        for n in range(2040)
    )
    totals = native_principal_by_maturity_band(flows, windows)
    assert len(windows) == 17
    for currency in ("CRC", "USD"):
        for window in windows:
            expected = sum(
                (
                    event.amount
                    for event in flows
                    if event.currency == currency
                    and window.start <= event.payment_date <= window.end
                ),
                Decimal(0),
            )
            assert totals.get((currency, window.key), Decimal(0)) == expected
    assert sum(totals.values(), Decimal(0)) == sum(
        (flow.amount for flow in flows if flow.payment_date <= cutoff + timedelta(days=365)),
        Decimal(0),
    )


def test_maturity_index_exact_boundaries_and_missing_source_are_not_estimated() -> None:
    cutoff = date(2026, 9, 30)
    windows = sugef210_windows(cutoff)
    actual = (0, 1, 7, 8, 30, 31, 60, 90, 365, 366)
    flows = tuple(_principal(cutoff, i, day, "USD") for i, day in enumerate(actual))
    totals = native_principal_by_maturity_band(flows, windows)
    assert totals[("USD", "D00")] == Decimal("0.01")
    assert totals[("USD", "D01")] == Decimal("0.01")
    assert totals[("USD", "D07")] == Decimal("0.01")
    assert totals[("USD", "W08_14")] == Decimal("0.01")
    assert totals[("USD", "W29_30")] == Decimal("0.01")
    assert totals[("USD", "M01")] == Decimal("0.02")
    assert totals[("USD", "M02")] == Decimal("0.01")
    assert totals[("USD", "Q03")] == Decimal("0.01")
    assert sum(totals.values(), Decimal(0)) == Decimal("0.09")
    assert not any(currency == "CRC" for currency, _key in totals)
    assert native_principal_by_maturity_band((), windows) == {}
