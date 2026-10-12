from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from aip.domain.portfolio.services.portfolio_optimization_preflight_service import (
    HistoryReadiness,
    ObservedTotalReturnSeries,
    PortfolioOptimizationPreflightService,
)

CUTOFF = date(2026, 10, 2)
DATES = tuple(CUTOFF - timedelta(days=39 - i) for i in range(40))


def _series(name: str, **changes: object) -> ObservedTotalReturnSeries:
    return replace(
        ObservedTotalReturnSeries(
            security_key=name,
            instrument_currency="CRC",
            reporting_currency="CRC",
            dates=DATES,
            returns=tuple(Decimal(i % 7 - 3) / Decimal("10000") for i in range(40)),
            frequency="daily",
            source_reference="Approved vector / original cash flow adjusted total returns",
            return_definition="TOTAL_RETURN_WITH_CASHFLOWS",
        ),
        **changes,
    )


def _evaluate(*items: ObservedTotalReturnSeries, policy="approved policy version 2026-10-02"):
    return PortfolioOptimizationPreflightService.evaluate(
        items, cutoff=CUTOFF, reporting_currency="CRC", policy_reference=policy
    )


def test_valid_observed_returns_ready_without_synthetic_fill() -> None:
    first = _series("BOND-A")
    second = _series(
        "BOND-B",
        dates=DATES[5:],
        returns=tuple(Decimal("0.0002") for _ in DATES[5:]),
    )
    result = _evaluate(first, second)
    assert result.ready
    assert result.status is HistoryReadiness.READY
    assert result.observation_dates == DATES[5:]
    assert len(result.aligned_returns) == 35
    assert result.asset_names == ("BOND-A", "BOND-B")
    assert result.periods_per_year == 252
    assert result.aligned_returns[0][1] == pytest.approx(0.0002)


def test_no_policy_no_output() -> None:
    result = _evaluate(_series("A"), _series("B"), policy="")
    assert result.status is HistoryReadiness.POLICY_UNVERIFIED
    assert result.aligned_returns == ()


def test_insufficient_overlap_rejects_even_when_each_history_has_thirty_points() -> None:
    second = _series(
        "B", dates=DATES[15:], returns=tuple(Decimal("0.001") for _ in DATES[15:])
    )
    result = _evaluate(_series("A"), second)
    assert result.status is HistoryReadiness.INSUFFICIENT_HISTORY
    assert result.aligned_returns == ()


@pytest.mark.parametrize(
    ("changes", "status"),
    [
        ({"return_definition": "YTM"}, HistoryReadiness.MISSING_RETURNS),
        ({"source_reference": ""}, HistoryReadiness.MISSING_RETURNS),
        ({"reporting_currency": "USD"}, HistoryReadiness.INCOMPATIBLE_CURRENCY),
        (
            {"instrument_currency": "USD", "fx_source_reference": ""},
            HistoryReadiness.INCOMPATIBLE_CURRENCY,
        ),
        ({"returns": (Decimal("NaN"),) * 40}, HistoryReadiness.INVALID_DATA),
        ({"returns": (Decimal("-1.01"),) * 40}, HistoryReadiness.INVALID_DATA),
        ({"frequency": "monthly"}, HistoryReadiness.INVALID_DATA),
        ({"dates": tuple(reversed(DATES))}, HistoryReadiness.INVALID_DATA),
        ({"dates": DATES[:-1]}, HistoryReadiness.MISSING_RETURNS),
    ],
)
def test_preflight_fails_closed(changes: dict[str, object], status: HistoryReadiness) -> None:
    result = _evaluate(_series("A"), _series("B", **changes))
    assert result.status is status
    assert result.aligned_returns == ()


def test_foreign_currency_can_be_aligned_with_audited_fx_provenance() -> None:
    usd = _series(
        "USD",
        instrument_currency="USD",
        fx_source_reference="BCCR observed FX rate + verified total return translation",
    )
    result = _evaluate(_series("CRC"), usd)
    assert result.ready


def test_allocation_universe_requires_distinct_security_keys() -> None:
    assert _evaluate(_series("A"), _series("A")).status is HistoryReadiness.INVALID_DATA
