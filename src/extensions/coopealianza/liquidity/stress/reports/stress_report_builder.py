from __future__ import annotations

from typing import Any

from src.extensions.coopealianza.liquidity.stress.exceptions import StressReportError
from src.extensions.coopealianza.liquidity.stress.models.stress_result import StressResult


class StressReportBuilder:
    """Build deterministic, explainable stress reports."""

    def build(self, result: StressResult) -> dict[str, Any]:
        if result is None:
            raise StressReportError("Stress result is required")
        ordered = sorted(result.scenario_results, key=lambda item: item.scenario_name)
        return {
            "portfolio_reference": result.portfolio_reference,
            "configuration_version": result.configuration_version,
            "scenario_results": [
                {
                    "scenario_name": item.scenario_name,
                    "scenario_type": item.scenario_type,
                    "severity": str(item.severity),
                    "stressed_gap": str(item.stressed_gap),
                    "stressed_outflow": str(item.stressed_outflow),
                    "stressed_inflow": str(item.stressed_inflow),
                    "effect": str(item.effect),
                    "assumptions": list(item.assumptions),
                    "stressed_parameters": {
                        key: str(value) for key, value in sorted(item.stressed_parameters.items())
                    },
                    "policy_references": list(item.policy_references),
                    "warnings": list(item.warnings),
                    "affected_assets": list(item.affected_assets),
                    "affected_buckets": list(item.affected_buckets),
                    "calculation_id": item.calculation_identifier,
                }
                for item in ordered
            ],
            "summary": {
                key: format(value, "f").rstrip("0").rstrip(".") or "0"
                for key, value in result.summary.items()
            },
            "assumptions": list(result.assumptions),
            "stressed_parameters": {
                key: str(value) for key, value in sorted(result.stressed_parameters.items())
            },
            "policy_references": list(result.policy_references),
            "warnings": list(result.warnings),
            "affected_assets": list(result.affected_assets),
            "affected_buckets": list(result.affected_buckets),
            "calculation_id": result.calculation_identifier,
            "explanation": {
                "conclusion": (
                    result.explanation.concise_conclusion
                    if result.explanation is not None
                    else "Stress evaluation completed"
                ),
                "supporting_factors": (
                    [
                        {
                            "name": factor.name,
                            "value": str(factor.value),
                            "contribution": str(factor.contribution),
                        }
                        for factor in result.explanation.supporting_factors
                    ]
                    if result.explanation is not None
                    else []
                ),
            },
        }
