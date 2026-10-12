from __future__ import annotations

import math

import numpy as np
import pytest

from aip.domain.portfolio.services.markowitz_optimizer import (
    MarkowitzConstraints,
    MarkowitzGroupLimit,
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


def test_markowitz_enforces_issuer_group_limit() -> None:
    limits = MarkowitzConstraints(
        minimum_weights=(0.0, 0.0, 0.0),
        maximum_weights=(1.0, 1.0, 1.0),
        group_limits=(MarkowitzGroupLimit("Gobierno", (0, 1), 0.40),),
    )
    result = MarkowitzOptimizer.optimize(
        ("Bono A", "Bono B", "Bono C"), _returns(), limits, frontier_points=4
    )
    for point in (result.minimum_variance, *result.efficient_frontier):
        assert sum(point.weights[:2]) <= 0.400001
        assert point.weights[2] >= 0.599999


def test_markowitz_rejects_infeasible_group_limits() -> None:
    limits = MarkowitzConstraints(
        minimum_weights=(0.0, 0.0),
        maximum_weights=(1.0, 1.0),
        group_limits=(
            MarkowitzGroupLimit("Grupo A", (0,), 0.30),
            MarkowitzGroupLimit("Grupo B", (1,), 0.30),
        ),
    )
    with pytest.raises(ValueError, match="infeasible"):
        MarkowitzOptimizer.optimize(("A", "B"), _returns()[:, :2], limits)


def test_markowitz_flat_returns_have_stable_degenerate_frontier() -> None:
    constraints = MarkowitzConstraints((0.0, 0.0), (1.0, 1.0))
    result = MarkowitzOptimizer.optimize(
        ("A", "B"), [[0.001, 0.001]] * 40, constraints, frontier_points=8
    )
    assert len(result.efficient_frontier) == 8
    assert all(
        point.weights == result.minimum_variance.weights
        for point in result.efficient_frontier
    )
    assert all(point.volatility == pytest.approx(0.0) for point in result.efficient_frontier)


def test_markowitz_frontier_ends_at_feasible_maximum_return() -> None:
    limits = MarkowitzConstraints(
        minimum_weights=(0.0, 0.0, 0.0),
        maximum_weights=(0.7, 0.7, 0.7),
        group_limits=(MarkowitzGroupLimit("Issuer A", (0, 1), 0.5),),
    )
    result = MarkowitzOptimizer.optimize(
        ("A", "B", "C"), _returns(), limits, frontier_points=7
    )
    highest = result.efficient_frontier[-1]
    assert sum(highest.weights) == pytest.approx(1.0, abs=1e-8)
    assert highest.weights[0] + highest.weights[1] <= 0.500001
    assert highest.expected_return >= result.minimum_variance.expected_return - 1e-9
