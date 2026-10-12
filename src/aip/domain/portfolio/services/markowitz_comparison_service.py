from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite

import numpy as np

from aip.domain.portfolio.services.markowitz_optimizer import (
    MarkowitzConstraints,
    MarkowitzOptimizer,
    MarkowitzPortfolio,
    MarkowitzResult,
)


@dataclass(frozen=True, slots=True)
class MarkowitzComparisonInput:
    """Aligned observed total returns, current weights and documented provenance.

    Returns must use the same dates, frequency and currency across all assets.
    The caller must verify the historical source; a bond's YTM is not a return
    observation. Dates prohibit look-ahead relative to the portfolio cutoff.
    """

    asset_names: tuple[str, ...]
    observation_dates: tuple[date, ...]
    aligned_total_returns: tuple[tuple[float, ...], ...]
    current_weights: tuple[float, ...]
    constraints: MarkowitzConstraints
    cutoff: date
    return_currency: str
    return_source: str
    periods_per_year: int = 252
    minimum_observations: int = 30
    frontier_points: int = 12


@dataclass(frozen=True, slots=True)
class MarkowitzComparisonResult:
    """Current portfolio versus unconstrained-by-current minimum risk allocation.

    The optimizer respects the supplied institutional policy. The current
    portfolio may breach policy; all breaches are reported, not hidden.
    Differences use optimized minus current and annual decimal rate units.
    """

    asset_names: tuple[str, ...]
    cutoff: date
    return_currency: str
    return_source: str
    observation_count: int
    current_portfolio: MarkowitzPortfolio
    optimized: MarkowitzResult
    current_policy_breaches: tuple[str, ...]
    minimum_variance_return_change: float
    minimum_variance_volatility_change: float


class MarkowitzComparisonService:
    """Inspect the current allocation with the same moments as Markowitz.

    This comparison is statistical, not an IRR/YTM bond comparison, an
    investment recommendation or an official SUGEF capital computation.
    """

    @staticmethod
    def compare(spec: MarkowitzComparisonInput) -> MarkowitzComparisonResult:
        if not spec.return_source.strip():
            raise ValueError("Historical total-return source is required")
        currency = spec.return_currency.strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("Common historical return currency must be a three-letter code")
        dates = spec.observation_dates
        if len(dates) != len(spec.aligned_total_returns):
            raise ValueError("One verified observation date is required per historical row")
        if not dates or any(day > spec.cutoff for day in dates):
            raise ValueError("Historical observations cannot be dated after the cutoff")
        if any(current >= following for current, following in zip(dates, dates[1:])):
            raise ValueError("Historical observation dates must be strictly increasing")

        weights = np.asarray(spec.current_weights, dtype=float)
        if (
            weights.ndim != 1
            or weights.size != len(spec.asset_names)
            or not np.isfinite(weights).all()
            or np.any(weights < 0)
            or np.any(weights > 1)
            or abs(float(weights.sum()) - 1) > 1e-6
        ):
            raise ValueError("Current allocation must have finite long-only weights summing to 1")

        optimized = MarkowitzOptimizer.optimize(
            spec.asset_names,
            spec.aligned_total_returns,
            spec.constraints,
            frontier_points=spec.frontier_points,
            minimum_observations=spec.minimum_observations,
            periods_per_year=spec.periods_per_year,
        )
        # Use exactly the same annualization, sample covariance (ddof=1)
        # and aligned observations as the optimizer.
        matrix = np.asarray(spec.aligned_total_returns, dtype=float)
        mean = matrix.mean(axis=0) * spec.periods_per_year
        covariance = np.cov(matrix, rowvar=False, ddof=1) * spec.periods_per_year
        variance = float(weights @ covariance @ weights)
        annual_return = float(weights @ mean)
        if not isfinite(variance) or not isfinite(annual_return) or variance < -1e-12:
            raise ValueError("Current allocation produced invalid annualized moments")
        current = MarkowitzPortfolio(
            weights=tuple(float(weight) for weight in weights),
            expected_return=annual_return,
            volatility=float(np.sqrt(max(variance, 0.0))),
        )

        breaches: list[str] = []
        for name, weight, minimum, maximum in zip(
            spec.asset_names,
            weights,
            spec.constraints.minimum_weights,
            spec.constraints.maximum_weights,
            strict=True,
        ):
            if weight < minimum - 1e-6:
                breaches.append(f"minimum:{name}")
            if weight > maximum + 1e-6:
                breaches.append(f"maximum:{name}")
        for group in spec.constraints.group_limits:
            if sum(float(weights[i]) for i in group.asset_indices) > group.maximum_weight + 1e-6:
                breaches.append(f"group:{group.name}")

        return MarkowitzComparisonResult(
            asset_names=optimized.asset_names,
            cutoff=spec.cutoff,
            return_currency=currency,
            return_source=spec.return_source.strip(),
            observation_count=optimized.observation_count,
            current_portfolio=current,
            optimized=optimized,
            current_policy_breaches=tuple(breaches),
            minimum_variance_return_change=(
                optimized.minimum_variance.expected_return - current.expected_return
            ),
            minimum_variance_volatility_change=(
                optimized.minimum_variance.volatility - current.volatility
            ),
        )
