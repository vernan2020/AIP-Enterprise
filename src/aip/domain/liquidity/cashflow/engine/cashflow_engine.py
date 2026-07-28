from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from aip.domain.analytics.explainability.explanation_factor import ExplanationFactor
from aip.domain.analytics.statistics.descriptive_statistics import DescriptiveStatistics
from aip.domain.liquidity.cashflow.exceptions import ScenarioError
from aip.domain.liquidity.cashflow.models.projected_cashflow import ProjectedCashFlow
from aip.domain.liquidity.cashflow.models.projection_request import ProjectionRequest
from aip.domain.liquidity.cashflow.models.projection_result import ProjectionResult
from aip.domain.liquidity.cashflow.engine.aggregation_engine import AggregationEngine
from aip.domain.liquidity.cashflow.engine.projection_engine import ProjectionEngine
from aip.domain.liquidity.cashflow.explainability.projection_explanation import ProjectionExplanation


class CashFlowEngine:
    """High-level orchestration for projected cash flow runs."""

    def __init__(self) -> None:
        self._projection_engine = ProjectionEngine()
        self._aggregation_engine = AggregationEngine()
        self._explanation = ProjectionExplanation()

    def project(self, request: ProjectionRequest) -> ProjectionResult:
        if request.scenario_provider is not None:
            try:
                scenario = request.scenario_provider.get_scenario(request)
            except Exception as exc:
                raise ScenarioError("Scenario provider failed") from exc
        else:
            scenario = request.scenario_name or "base"
        projected = self._projection_engine.project(request)
        aggregation = self._aggregation_engine.aggregate(projected, request)
        values = [cashflow.amount for cashflow in projected]
        stats = DescriptiveStatistics(values)
        factors = [
            ExplanationFactor(name="projected_amount", value=stats.sum(), direction="higher_is_better", contribution=stats.sum(), source_reference="cashflow"),
        ]
        explanation = self._explanation.build(
            "Projected cash flows derived from contractual and behavioral assumptions",
            factors,
            assumptions=request.behavioral_assumptions and tuple(assumption.name for assumption in request.behavioral_assumptions) or request.assumptions,
            warnings=request.warnings,
            references=request.references,
        )
        return ProjectionResult(
            projection_type=self._projection_type(request),
            projected_cashflows=projected,
            assumptions=request.behavioral_assumptions and tuple(assumption.name for assumption in request.behavioral_assumptions) or request.assumptions,
            behavioral_inputs=tuple((assumption.name, assumption.probability) for assumption in request.behavioral_assumptions),
            calculation_path=("contractual", "behavioral") if request.behavioral_assumptions else ("contractual",),
            warnings=request.warnings,
            references=request.references,
            coverage=stats.mean(),
            concentration=stats.maximum() if stats.count() else Decimal("0"),
            timing=stats.median(),
            distribution=stats.standard_deviation(),
            weighted_average=stats.mean(),
            percentiles=(stats.percentile(Decimal("0.25")), stats.percentile(Decimal("0.5")), stats.percentile(Decimal("0.75"))),
            factors=tuple(factors),
            scenario=scenario,
            aggregation=aggregation,
        )

    def _projection_type(self, request: ProjectionRequest) -> str:
        normalized = (request.projection_type or "").strip().lower()
        if normalized == "scenario":
            return "scenario"
        if normalized == "behavioral":
            return "behavioral"
        if request.behavioral_assumptions:
            return "hybrid"
        return "contractual"
