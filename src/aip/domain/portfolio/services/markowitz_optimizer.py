from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Sequence

import numpy as np
from scipy.optimize import minimize


@dataclass(frozen=True)
class MarkowitzConstraints:
    """Long-only allocation bounds, provided in fraction-of-portfolio units."""

    minimum_weights: tuple[float, ...]
    maximum_weights: tuple[float, ...]

    def validate(self, asset_count: int) -> None:
        if len(self.minimum_weights) != asset_count or len(self.maximum_weights) != asset_count:
            raise ValueError("One lower and upper weight bound is required per asset")
        if any(
            not isfinite(low) or not isfinite(high) or low < 0 or high > 1 or low > high
            for low, high in zip(self.minimum_weights, self.maximum_weights, strict=True)
        ):
            raise ValueError("Invalid long-only weight bounds")
        if sum(self.minimum_weights) > 1 + 1e-9 or sum(self.maximum_weights) < 1 - 1e-9:
            raise ValueError("Weight limits do not permit a fully invested portfolio")


@dataclass(frozen=True)
class MarkowitzPortfolio:
    weights: tuple[float, ...]
    expected_return: float
    volatility: float


@dataclass(frozen=True)
class MarkowitzResult:
    minimum_variance: MarkowitzPortfolio
    efficient_frontier: tuple[MarkowitzPortfolio, ...]
    observation_count: int
    asset_names: tuple[str, ...]


class MarkowitzOptimizer:
    """Long-only mean-variance optimization on aligned observed total returns.

    Returns must be chronological, numeric and expressed as fractions at the
    same frequency and in a common currency. No prices, YTM or implied
    correlations are synthesized by this service.
    """

    @staticmethod
    def optimize(
        asset_names: Sequence[str],
        aligned_returns: Sequence[Sequence[float]],
        constraints: MarkowitzConstraints,
        *,
        frontier_points: int = 12,
        minimum_observations: int = 30,
        periods_per_year: int = 252,
    ) -> MarkowitzResult:
        names = tuple(asset_names)
        if len(names) < 2 or len(set(names)) != len(names):
            raise ValueError("At least two distinct assets are required")
        constraints.validate(len(names))
        if frontier_points < 2 or periods_per_year <= 0 or minimum_observations < 3:
            raise ValueError("Invalid optimization configuration")

        data = np.asarray(aligned_returns, dtype=float)
        if data.ndim != 2 or data.shape[1] != len(names):
            raise ValueError("Aligned returns must have one column per asset")
        if data.shape[0] < minimum_observations or not np.isfinite(data).all():
            raise ValueError("Insufficient or non-finite aligned historical returns")

        expected = data.mean(axis=0) * periods_per_year
        covariance = np.cov(data, rowvar=False, ddof=1) * periods_per_year
        covariance = (covariance + covariance.T) / 2
        bounds = list(zip(constraints.minimum_weights, constraints.maximum_weights, strict=True))
        start = np.asarray(constraints.minimum_weights, dtype=float)
        remaining = 1.0 - float(start.sum())
        for index, (_, high) in enumerate(bounds):
            increase = min(remaining, high - start[index])
            start[index] += increase
            remaining -= increase
        if remaining > 1e-8:
            raise ValueError("No feasible starting portfolio")

        def risk(weights: np.ndarray) -> float:
            return float(weights @ covariance @ weights)

        def solve(target: float | None = None) -> MarkowitzPortfolio:
            conditions = [{"type": "eq", "fun": lambda w: float(w.sum() - 1)}]
            if target is not None:
                conditions.append(
                    {"type": "eq", "fun": lambda w, goal=target: float(w @ expected - goal)}
                )
            result = minimize(
                risk,
                start,
                method="SLSQP",
                bounds=bounds,
                constraints=conditions,
                options={"maxiter": 2000, "ftol": 1e-12},
            )
            if not result.success:
                raise ValueError(f"Markowitz optimization infeasible: {result.message}")
            weights = np.asarray(result.x)
            if (
                abs(weights.sum() - 1) > 1e-6
                or np.any(weights < np.asarray(constraints.minimum_weights) - 1e-6)
                or np.any(weights > np.asarray(constraints.maximum_weights) + 1e-6)
                or (target is not None and abs(weights @ expected - target) > 1e-5)
            ):
                raise ValueError("Optimized weights violate allocation constraints")
            return MarkowitzPortfolio(
                weights=tuple(float(w) for w in weights),
                expected_return=float(weights @ expected),
                volatility=float(np.sqrt(max(risk(weights), 0.0))),
            )

        minimum = solve()
        highest = minimize(
            lambda w: -float(w @ expected),
            start,
            method="SLSQP",
            bounds=bounds,
            constraints=[{"type": "eq", "fun": lambda w: float(w.sum() - 1)}],
            options={"maxiter": 2000, "ftol": 1e-12},
        )
        if not highest.success:
            raise ValueError("Unable to determine feasible maximum return")
        upper = float(highest.x @ expected)
        goals = np.linspace(minimum.expected_return, upper, frontier_points)
        frontier = tuple(solve(float(goal)) for goal in goals)
        return MarkowitzResult(
            minimum_variance=minimum,
            efficient_frontier=frontier,
            observation_count=int(data.shape[0]),
            asset_names=names,
        )
