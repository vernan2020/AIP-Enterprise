from __future__ import annotations

from decimal import Decimal
from typing import Any

from aip.domain.liquidity.cashflow.models.projection_result import ProjectionResult
from aip.domain.liquidity.gap.models.gap_result import GapResult
from src.extensions.coopealianza.liquidity.stress.analytics.stress_analytics import StressAnalytics
from src.extensions.coopealianza.liquidity.stress.configuration.stress_policy_config import (
    StressPolicyConfig,
    StressScenarioConfig,
)
from src.extensions.coopealianza.liquidity.stress.exceptions import (
    StressConfigurationError,
    StressEvaluationError,
    StressProviderError,
)
from src.extensions.coopealianza.liquidity.stress.models.stress_request import StressRequest
from src.extensions.coopealianza.liquidity.stress.models.stress_result import StressResult
from src.extensions.coopealianza.liquidity.stress.models.stress_scenario_result import (
    StressScenarioResult,
)
from src.extensions.coopealianza.liquidity.stress.providers.scenario_provider import (
    StaticScenarioProvider,
)


class StressEngine:
    """Evaluate liquidity stress outcomes from existing gap and cashflow projections."""

    def __init__(self) -> None:
        self._analytics = StressAnalytics()

    def evaluate(self, request: StressRequest) -> StressResult:
        if request.gap_result is None or request.projection_result is None:
            raise StressEvaluationError("Gap and projection results are required")
        if not request.portfolio_reference:
            raise StressEvaluationError("Portfolio reference is required")

        config = self._coerce_config(request.configuration)
        provider = request.scenario_provider or StaticScenarioProvider(config.scenarios)
        try:
            scenarios = provider.get_scenarios() or config.scenarios
        except Exception as exc:  # pragma: no cover - translated in engine
            raise StressProviderError("Scenario provider failed") from exc
        if not scenarios:
            raise StressEvaluationError("At least one scenario is required")

        scenario_lookup = {scenario.scenario_id: scenario for scenario in scenarios}
        scenario_results = [self._evaluate_scenario(scenario, request.gap_result, request.projection_result, scenario_lookup) for scenario in scenarios]
        summary = {
            "max_stressed_gap": max(item.stressed_gap for item in scenario_results),
            "max_stressed_outflow": max(item.stressed_outflow for item in scenario_results),
            "max_effect": max(item.effect for item in scenario_results),
        }
        explanation = self._analytics.build_explanation(
            conclusion="Liquidity stress evaluation completed",
            factors=[
                ("max_stressed_gap", summary["max_stressed_gap"]),
                ("max_effect", summary["max_effect"]),
            ],
        )
        return StressResult(
            portfolio_reference=request.portfolio_reference,
            configuration_version=config.version,
            total_scenarios=len(scenario_results),
            scenario_results=tuple(scenario_results),
            summary=summary,
            explanation=explanation,
            assumptions=tuple({assumption for scenario in scenarios for assumption in scenario.assumptions}),
            stressed_parameters={key: value for scenario in scenarios for key, value in self._scenario_parameters(scenario).items()},
            policy_references=tuple({reference for scenario in scenarios for reference in scenario.policy_references}),
            warnings=tuple({warning for scenario in scenarios for warning in scenario.warnings}),
            affected_assets=tuple({asset for scenario in scenarios for asset in scenario.affected_assets}),
            affected_buckets=tuple({bucket for scenario in scenarios for bucket in scenario.affected_buckets}),
            calculation_identifier=f"stress-{request.portfolio_reference}",
        )

    def _evaluate_scenario(self, scenario: StressScenarioConfig, gap_result: GapResult, projection_result: ProjectionResult, scenario_lookup: dict[str, StressScenarioConfig]) -> StressScenarioResult:
        if scenario.scenario_type == "combined":
            return self._evaluate_combined_scenario(scenario, gap_result, projection_result, scenario_lookup)

        if scenario.scenario_type == "deposit_runoff":
            stressed_gap = gap_result.net_gap + (gap_result.net_gap * scenario.runoff_rate)
            stressed_outflow = gap_result.gross_outflow
            stressed_inflow = gap_result.gross_inflow * (Decimal("1") - scenario.runoff_rate)
            stressed_parameters = {"runoff_rate": scenario.runoff_rate}
        elif scenario.scenario_type == "wholesale_funding_shock":
            stressed_gap = gap_result.net_gap + (gap_result.net_gap * scenario.withdrawal_rate)
            stressed_outflow = gap_result.gross_outflow * (Decimal("1") + scenario.withdrawal_rate)
            stressed_inflow = gap_result.gross_inflow * (Decimal("1") - scenario.withdrawal_rate)
            stressed_parameters = {"withdrawal_rate": scenario.withdrawal_rate}
        elif scenario.scenario_type == "collateral_haircut":
            stressed_gap = gap_result.net_gap + (gap_result.net_gap * (Decimal("1") - scenario.collateral_multiplier))
            stressed_outflow = gap_result.gross_outflow * (Decimal("1") + scenario.severity)
            stressed_inflow = gap_result.gross_inflow
            stressed_parameters = {"collateral_multiplier": scenario.collateral_multiplier}
        elif scenario.scenario_type == "market_liquidity_deterioration":
            stressed_gap = gap_result.net_gap + (gap_result.net_gap * scenario.market_value_multiplier)
            stressed_outflow = gap_result.gross_outflow * (Decimal("1") + scenario.severity)
            stressed_inflow = gap_result.gross_inflow * (Decimal("1") - scenario.market_value_multiplier)
            stressed_parameters = {"market_value_multiplier": scenario.market_value_multiplier}
        else:
            stressed_gap = gap_result.net_gap * (Decimal("1") + scenario.severity + scenario.liquidity_factor + scenario.concentration_factor)
            stressed_outflow = gap_result.gross_outflow * (Decimal("1") + scenario.liquidity_factor)
            stressed_inflow = gap_result.gross_inflow * (Decimal("1") - scenario.severity)
            stressed_parameters = {"severity": scenario.severity, "liquidity_factor": scenario.liquidity_factor}

        effect = stressed_gap - gap_result.net_gap
        return StressScenarioResult(
            scenario_name=scenario.name,
            scenario_type=scenario.scenario_type,
            severity=scenario.severity,
            stressed_gap=stressed_gap,
            stressed_outflow=stressed_outflow,
            stressed_inflow=stressed_inflow,
            effect=effect,
            assumptions=scenario.assumptions,
            stressed_parameters=stressed_parameters,
            policy_references=scenario.policy_references,
            warnings=scenario.warnings,
            affected_assets=scenario.affected_assets,
            affected_buckets=scenario.affected_buckets,
            calculation_identifier=f"stress-{scenario.scenario_id}",
        )

    def _evaluate_combined_scenario(self, scenario: StressScenarioConfig, gap_result: GapResult, projection_result: ProjectionResult, scenario_lookup: dict[str, StressScenarioConfig]) -> StressScenarioResult:
        combined_results = []
        for scenario_id in sorted(scenario.combined_scenario_ids):
            referenced = scenario_lookup.get(scenario_id)
            if referenced is None:
                raise StressEvaluationError(f"Referenced scenario {scenario_id} was not found")
            combined_results.append(self._evaluate_scenario(referenced, gap_result, projection_result, scenario_lookup))
        if not combined_results:
            raise StressEvaluationError("Combined scenarios require at least one contribution")
        aggregate_gap = sum((item.stressed_gap for item in combined_results), Decimal("0"))
        aggregate_outflow = sum((item.stressed_outflow for item in combined_results), Decimal("0"))
        aggregate_inflow = sum((item.stressed_inflow for item in combined_results), Decimal("0"))
        return StressScenarioResult(
            scenario_name=scenario.name,
            scenario_type=scenario.scenario_type,
            severity=scenario.severity,
            stressed_gap=aggregate_gap,
            stressed_outflow=aggregate_outflow,
            stressed_inflow=aggregate_inflow,
            effect=aggregate_gap - gap_result.net_gap,
            assumptions=scenario.assumptions,
            stressed_parameters={"combined_scenario_ids": Decimal(len(scenario.combined_scenario_ids))},
            policy_references=scenario.policy_references,
            warnings=scenario.warnings,
            affected_assets=scenario.affected_assets,
            affected_buckets=scenario.affected_buckets,
            calculation_identifier=f"stress-{scenario.scenario_id}",
        )

    def _scenario_parameters(self, scenario: StressScenarioConfig) -> dict[str, Decimal]:
        return {
            "severity": scenario.severity,
            "liquidity_factor": scenario.liquidity_factor,
            "concentration_factor": scenario.concentration_factor,
            "runoff_rate": scenario.runoff_rate,
            "withdrawal_rate": scenario.withdrawal_rate,
            "collateral_multiplier": scenario.collateral_multiplier,
            "market_value_multiplier": scenario.market_value_multiplier,
        }

    def _coerce_config(self, config: Any) -> StressPolicyConfig:
        if isinstance(config, StressPolicyConfig):
            return config
        if isinstance(config, dict):
            return StressPolicyConfig.from_mapping(config)
        raise StressConfigurationError("Stress configuration must be a StressPolicyConfig or mapping")
