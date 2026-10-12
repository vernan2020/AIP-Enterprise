from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import numpy as np

from aip.domain.portfolio.services.markowitz_comparison_service import (
    MarkowitzComparisonInput,
    MarkowitzComparisonResult,
)
from aip.domain.portfolio.services.markowitz_optimizer import MarkowitzPortfolio


@dataclass(frozen=True, slots=True)
class MarkowitzRiskContribution:
    """Euler contribution to annualized portfolio volatility for one instrument."""

    security_key: str
    portfolio_weight: float
    marginal_volatility: float
    component_volatility: float
    percentage_of_volatility: float


@dataclass(frozen=True, slots=True)
class MarkowitzRiskAttribution:
    """Annualized decomposition of a single observed-return portfolio."""

    expected_return: float
    annualized_volatility: float
    status: str
    contributions: tuple[MarkowitzRiskContribution, ...]


@dataclass(frozen=True, slots=True)
class MarkowitzRiskAttributionComparison:
    """Same-date, same-covariance current versus minimum-variance attribution."""

    cutoff: str
    currency: str
    return_source: str
    observation_count: int
    current: MarkowitzRiskAttribution
    minimum_variance: MarkowitzRiskAttribution


class MarkowitzRiskAttributionService:
    """Euler volatility attribution; no VaR, YTM, or inferred historical inputs.

    The covariance is computed from exactly the return observations used for
    the Markowitz comparison, with ddof=1 and the same annualization factor.
    Negative risk contributions are valid for diversifying exposures. This is
    an explanatory decomposition, not another portfolio optimizer or a
    substitute for policy / SUGEF controls.
    """

    @staticmethod
    def compare(
        spec: MarkowitzComparisonInput,
        comparison: MarkowitzComparisonResult,
    ) -> MarkowitzRiskAttributionComparison:
        if (
            spec.asset_names != comparison.asset_names
            or spec.cutoff != comparison.cutoff
            or spec.return_currency.strip().upper() != comparison.return_currency
            or spec.return_source.strip() != comparison.return_source
        ):
            raise ValueError("Risk attribution and optimized comparison metadata do not match")
        if (
            len(spec.observation_dates) != comparison.observation_count
            or len(spec.aligned_total_returns) != comparison.observation_count
            or spec.periods_per_year <= 0
            or comparison.observation_count < 2
        ):
            raise ValueError("Risk attribution requires the verified aligned return observations")
        if (
            not spec.return_source.strip()
            or any(day > spec.cutoff for day in spec.observation_dates)
            or any(a >= b for a, b in zip(spec.observation_dates, spec.observation_dates[1:]))
        ):
            raise ValueError("Historical return cutoff and provenance are invalid")

        data = np.asarray(spec.aligned_total_returns, dtype=float)
        n = len(spec.asset_names)
        if (
            data.ndim != 2
            or data.shape != (comparison.observation_count, n)
            or n < 2
            or not np.isfinite(data).all()
        ):
            raise ValueError("Attribution needs finite, aligned observations for every asset")
        expected = data.mean(axis=0) * spec.periods_per_year
        covariance = np.cov(data, rowvar=False, ddof=1) * spec.periods_per_year
        covariance = (covariance + covariance.T) / 2
        if not np.isfinite(expected).all() or not np.isfinite(covariance).all():
            raise ValueError("Annualized observed moments are not finite")

        def attribute(point: MarkowitzPortfolio) -> MarkowitzRiskAttribution:
            weights = np.asarray(point.weights, dtype=float)
            if (
                weights.shape != (n,)
                or not np.isfinite(weights).all()
                or np.any(weights < -1e-8)
                or np.any(weights > 1 + 1e-8)
                or abs(float(weights.sum()) - 1) > 1e-6
            ):
                raise ValueError("Attribution requires valid long-only portfolio weights")
            annual_return = float(weights @ expected)
            variance = float(weights @ covariance @ weights)
            if not isfinite(annual_return) or not isfinite(variance) or variance < -1e-10:
                raise ValueError("Observed portfolio risk moments are invalid")
            volatility = float(np.sqrt(max(variance, 0.0)))
            if (
                not isfinite(point.expected_return)
                or not isfinite(point.volatility)
                or abs(point.expected_return - annual_return) > 1e-6
                or abs(point.volatility - volatility) > 1e-6
            ):
                raise ValueError("Portfolio statistics differ from verified historical moments")

            # A zero-volatility portfolio has no defined Euler marginal or
            # percentage shares: return explicit zeros rather than 0/0 or NaN.
            zero_risk = volatility <= 1e-14
            marginal = np.zeros(n) if zero_risk else (covariance @ weights) / volatility
            components = np.zeros(n) if zero_risk else weights * marginal
            percentages = np.zeros(n) if zero_risk else components / volatility
            if (
                not np.isfinite(marginal).all()
                or not np.isfinite(components).all()
                or not np.isfinite(percentages).all()
                or (not zero_risk and abs(float(components.sum()) - volatility) > 1e-7)
            ):
                raise ValueError("Euler risk contributions failed reconciliation")
            contributions = tuple(
                MarkowitzRiskContribution(
                    security_key=key,
                    portfolio_weight=float(weights[index]),
                    marginal_volatility=float(marginal[index]),
                    component_volatility=float(components[index]),
                    percentage_of_volatility=float(percentages[index]),
                )
                for index, key in enumerate(spec.asset_names)
            )
            return MarkowitzRiskAttribution(
                expected_return=annual_return,
                annualized_volatility=volatility,
                status="ZERO_VOLATILITY" if zero_risk else "READY",
                contributions=contributions,
            )

        return MarkowitzRiskAttributionComparison(
            cutoff=spec.cutoff.isoformat(),
            currency=comparison.return_currency,
            return_source=comparison.return_source,
            observation_count=comparison.observation_count,
            current=attribute(comparison.current_portfolio),
            minimum_variance=attribute(comparison.optimized.minimum_variance),
        )
