from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

import numpy as np
import pytest

from aip.domain.portfolio.services.markowitz_comparison_service import (
    MarkowitzComparisonInput,
    MarkowitzComparisonService,
)
from aip.domain.portfolio.services.markowitz_optimizer import (
    MarkowitzConstraints,
    MarkowitzGroupLimit,
)


def _spec() -> MarkowitzComparisonInput:
    days = np.arange(60, dtype=float)
    returns = np.column_stack(
        (
            0.0003 + np.sin(days * 0.17) * 0.005,
            0.0002 + np.cos(days * 0.11) * 0.003,
            0.0004 + np.sin(days * 0.23 + 0.5) * 0.004,
        )
    )
    return MarkowitzComparisonInput(
        asset_names=("Bono A", "Bono B", "Bono C"),
        observation_dates=tuple(date(2026, 7, 1) + timedelta(days=i) for i in range(60)),
        aligned_total_returns=tuple(tuple(float(value) for value in row) for row in returns),
        current_weights=(0.2, 0.2, 0.6),
        constraints=MarkowitzConstraints(
            minimum_weights=(0.0, 0.0, 0.0),
            maximum_weights=(0.75, 0.75, 1.0),
            group_limits=(MarkowitzGroupLimit("Emisor AB", (0, 1), 0.70),),
        ),
        cutoff=date(2026, 10, 2),
        return_currency="CRC",
        return_source="certified observed total-return vector / 2026-10-02",
        frontier_points=5,
    )


def test_current_uses_same_covariance_and_annualization_as_optimizer() -> None:
    spec = _spec()
    result = MarkowitzComparisonService.compare(spec)
    history = np.asarray(spec.aligned_total_returns)
    weights = np.asarray(spec.current_weights)
    expected_return = float(weights @ history.mean(axis=0) * spec.periods_per_year)
    covariance = np.cov(history, rowvar=False, ddof=1) * spec.periods_per_year
    expected_volatility = float(np.sqrt(weights @ covariance @ weights))

    assert result.current_portfolio.expected_return == pytest.approx(expected_return)
    assert result.current_portfolio.volatility == pytest.approx(expected_volatility)
    assert result.current_policy_breaches == ()
    assert result.minimum_variance_volatility_change <= 1e-6
    assert result.observation_count == 60
    assert len(result.optimized.efficient_frontier) == 5
    assert result.return_source == spec.return_source


def test_current_breaches_are_reported_not_silently_reoptimized() -> None:
    spec = replace(_spec(), current_weights=(0.8, 0.1, 0.1))
    result = MarkowitzComparisonService.compare(spec)
    assert result.current_portfolio.weights == spec.current_weights
    assert result.current_policy_breaches == ("maximum:Bono A", "group:Emisor AB")
    for point in result.optimized.efficient_frontier:
        assert point.weights[0] + point.weights[1] <= 0.700001


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"return_source": "   "}, "source"),
        ({"return_currency": ""}, "currency"),
        ({"current_weights": (0.8, 0.8, -0.6)}, "long-only"),
        ({"current_weights": (0.5, 0.3, 0.1)}, "summing"),
        ({"current_weights": (0.2, float("nan"), 0.8)}, "finite"),
        ({"cutoff": date(2026, 7, 1)}, "cutoff"),
        ({"observation_dates": (date(2026, 7, 1),) * 60}, "strictly increasing"),
        ({"observation_dates": (date(2026, 7, 1),)}, "One verified"),
    ],
)
def test_comparison_rejects_unverified_or_invalid_input(changes: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        MarkowitzComparisonService.compare(replace(_spec(), **changes))


def test_comparison_rejects_nonfinite_historical_returns() -> None:
    spec = _spec()
    history = list(spec.aligned_total_returns)
    history[20] = (0.001, float("nan"), 0.004)
    with pytest.raises(ValueError, match="non-finite"):
        MarkowitzComparisonService.compare(replace(spec, aligned_total_returns=tuple(history)))
