from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from math import isfinite
from typing import Sequence

from aip.domain.portfolio.services.markowitz_optimizer import (
    MarkowitzPortfolio,
    MarkowitzResult,
)
from aip.domain.portfolio.services.portfolio_capital_consumption_service import (
    REGULATORY_WEIGHTS,
    ExposureClass,
)


@dataclass(frozen=True, slots=True)
class AssetCapitalAssumption:
    """Verified exposure and classification for the instrument at the same cutoff."""

    asset_name: str
    currency: str
    exposure_to_investment_ratio: Decimal
    exposure_class: ExposureClass
    classification_source: str


@dataclass(frozen=True, slots=True)
class CapitalAdjustedMarkowitzPoint:
    weights: tuple[float, ...]
    volatility: float
    expected_return_before_equity_cost: Decimal
    credit_rwa_to_portfolio_ratio: Decimal
    target_equity_to_portfolio_ratio: Decimal
    annual_equity_charge_ratio: Decimal
    expected_return_after_equity_cost: Decimal


@dataclass(frozen=True, slots=True)
class MarkowitzCapitalImpactResult:
    asset_names: tuple[str, ...]
    annual_cost_of_equity: Decimal
    target_capital_adequacy: Decimal
    minimum_variance: CapitalAdjustedMarkowitzPoint
    frontier: tuple[CapitalAdjustedMarkowitzPoint, ...]


class MarkowitzCapitalImpactService:
    """Evaluate capital-adjusted returns of an already-optimized frontier.

    This is an ex-post economic capital assessment. It does NOT re-optimize
    Markowitz portfolios or convert this proxy into official regulatory SP.
    All classification and regulatory exposure ratios must be verified.
    """

    @staticmethod
    def evaluate(
        result: MarkowitzResult,
        assets: Sequence[AssetCapitalAssumption],
        *,
        annual_cost_of_equity: Decimal,
        target_capital_adequacy: Decimal = Decimal("0.16"),
    ) -> MarkowitzCapitalImpactResult:
        if (
            not annual_cost_of_equity.is_finite()
            or annual_cost_of_equity < 0
            or not target_capital_adequacy.is_finite()
            or not Decimal("0") < target_capital_adequacy <= 1
        ):
            raise ValueError("Invalid editable cost of equity or target capital adequacy")
        assumptions = tuple(assets)
        if len(assumptions) != len(result.asset_names) or tuple(
            asset.asset_name for asset in assumptions
        ) != result.asset_names:
            raise ValueError("Verified capital assumptions must match optimizer asset order")
        for asset in assumptions:
            if not asset.classification_source.strip():
                raise ValueError("Capital classification requires a verified source")
            ratio = asset.exposure_to_investment_ratio
            if not ratio.is_finite() or ratio < 0:
                raise ValueError("Exposure-to-investment ratio must be finite and non-negative")
            currency = asset.currency.strip().upper()
            if asset.exposure_class in (
                ExposureClass.GOVERNMENT_CRC,
                ExposureClass.BCCR_CRC,
            ) and currency != "CRC":
                raise ValueError("Zero-weight sovereign CRC requires CRC exposure")
            if asset.exposure_class in (
                ExposureClass.GOVERNMENT_USD,
                ExposureClass.BCCR_USD,
            ) and currency != "USD":
                raise ValueError("USD sovereign risk class requires USD exposure")

        def evaluate_point(point: MarkowitzPortfolio) -> CapitalAdjustedMarkowitzPoint:
            if len(point.weights) != len(assumptions) or not all(
                isfinite(w) and 0 <= w <= 1 for w in point.weights
            ) or abs(sum(point.weights) - 1) > 1e-6:
                raise ValueError("Invalid long-only allocation weights")
            if not isfinite(point.expected_return) or not isfinite(point.volatility):
                raise ValueError("Invalid optimized return or volatility")
            rwa_ratio = sum(
                (
                    Decimal(str(w))
                    * asset.exposure_to_investment_ratio
                    * REGULATORY_WEIGHTS[asset.exposure_class]
                    for w, asset in zip(point.weights, assumptions, strict=True)
                ),
                Decimal("0"),
            )
            allocated_equity_ratio = rwa_ratio * target_capital_adequacy
            annual_charge = allocated_equity_ratio * annual_cost_of_equity
            gross = Decimal(str(point.expected_return))
            return CapitalAdjustedMarkowitzPoint(
                weights=point.weights,
                volatility=point.volatility,
                expected_return_before_equity_cost=gross,
                credit_rwa_to_portfolio_ratio=rwa_ratio,
                target_equity_to_portfolio_ratio=allocated_equity_ratio,
                annual_equity_charge_ratio=annual_charge,
                expected_return_after_equity_cost=gross - annual_charge,
            )

        return MarkowitzCapitalImpactResult(
            asset_names=result.asset_names,
            annual_cost_of_equity=annual_cost_of_equity,
            target_capital_adequacy=target_capital_adequacy,
            minimum_variance=evaluate_point(result.minimum_variance),
            frontier=tuple(evaluate_point(point) for point in result.efficient_frontier),
        )
