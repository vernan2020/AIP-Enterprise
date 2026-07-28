from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from aip.domain.analytics.explainability.explanation import Explanation
from aip.domain.analytics.explainability.explanation_factor import ExplanationFactor
from aip.domain.liquidity.cashflow.models.projected_cashflow import ProjectedCashFlow
from aip.domain.liquidity.gap.models.gap_value import GapValue


@dataclass(frozen=True, slots=True)
class GapResult:
    """Result container for a liquidity gap analysis."""

    valuation_date: date
    gap_type: str
    net_gap: Decimal
    gross_inflow: Decimal
    gross_outflow: Decimal
    incremental_gap: Decimal
    cumulative_gap: Decimal
    summary_value: Decimal
    gaps: tuple[GapValue, ...] = ()
    aggregation: dict[str, dict[str, Decimal]] = field(default_factory=dict)
    analytics: dict[str, dict[str, Decimal]] = field(default_factory=dict)
    factors: tuple[ExplanationFactor, ...] = ()
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    references: tuple[str, ...] = ()
    explanation: Explanation | None = None
    opening_liquidity: Decimal = Decimal("0")
    position: str = "neutral"
    projection_type: str = "contractual"
    source_cashflows: tuple[ProjectedCashFlow, ...] = ()
    scenario: str = "base"
    currency: str = "USD"
    bucket_assignments: tuple[str, ...] = ()
    calculation_identifier: str | None = None
