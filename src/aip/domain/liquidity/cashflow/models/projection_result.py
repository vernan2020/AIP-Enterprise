from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from aip.domain.analytics.explainability.explanation_factor import ExplanationFactor
from aip.domain.financial_math.cashflows.cashflow import CashFlow
from aip.domain.liquidity.cashflow.models.projected_cashflow import ProjectedCashFlow


@dataclass(frozen=True, slots=True)
class ProjectionResult:
    """Aggregated result for a projection run."""

    projection_type: str
    projected_cashflows: tuple[ProjectedCashFlow, ...]
    assumptions: tuple[str, ...] = ()
    behavioral_inputs: tuple[tuple[str, Decimal], ...] = ()
    calculation_path: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    references: tuple[str, ...] = ()
    coverage: Decimal = Decimal("0")
    concentration: Decimal = Decimal("0")
    timing: Decimal = Decimal("0")
    distribution: Decimal = Decimal("0")
    weighted_average: Decimal = Decimal("0")
    percentiles: tuple[Decimal, ...] = ()
    factors: tuple[ExplanationFactor, ...] = ()
    scenario: str = "base"
    aggregation: dict[str, dict[str, Decimal]] = field(default_factory=dict)
