from __future__ import annotations

import math

import numpy as np
import pytest

from aip.domain.portfolio.services.markowitz_optimizer import (
    MarkowitzConstraints,
    MarkowitzOptimizer,
)


def _returns() -> np.ndarray:
    days = np.arange(90, dtype=float)
    return np.column_stack(
        (
            0.0003 + np.sin(days * 0.17) * 0.005,
            0.0002 + np.cos(days * 0.11) * 0.003,
            0.0004 + np.sin(days * 0.23 + 0.5) * 0.004,
        )
    )


def test_markowitz_frontier_respects_bounds_and_return_order() -> None:
    limits = MarkowitzConstraints(
        minimum_weights=(0.10, 0.0, 0.0),
        maximum_weights=(0.70, 0.65, 0.60),
    )
    result = MarkowitzOptimizer.optimize(("A", "B", "C"), _returns(), limits, frontier_points=5)
    assert result.observation_count == 90
    assert len(result.efficient_frontier) == 5
    expected_returns = [point.expected_return for point in result.efficient_frontier]
    assert expected_returns == sorted(expected_returns)
    for point in (result.minimum_variance, *result.efficient_frontier):
        assert sum(point.weights) == pytest.approx(1.0, abs=1e-6)
        assert all(
            low - 1e-6 <= weight <= high + 1e-6
            for weight, low, high in zip(
                point.weights, limits.minimum_weights, limits.maximum_weights, strict=True
            )
        )
        assert point.volatility >= 0
        assert math.isfinite(point.expected_return)


def test_markowitz_rejects_missing_prices_or_unaligned_returns() -> None:
    limits = MarkowitzConstraints((0.0, 0.0), (1.0, 1.0))
    with pytest.raises(ValueError, match="Insufficient"):
        MarkowitzOptimizer.optimize(("A", "B"), [[0.02, 0.01]], limits)
    with pytest.raises(ValueError, match="non-finite"):
        MarkowitzOptimizer.optimize(("A", "B"), [[0.02, float("nan")]] * 30, limits)


def test_markowitz_rejects_infeasible_policy_bounds() -> None:
    limits = MarkowitzConstraints((0.8, 0.8), (1.0, 1.0))
    with pytest.raises(ValueError, match="fully invested"):
        MarkowitzOptimizer.optimize(("A", "B"), [[0.02, 0.01]] * 30, limits)
