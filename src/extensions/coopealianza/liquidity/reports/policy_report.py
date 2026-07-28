from __future__ import annotations

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.analytics.explainability.explanation import Explanation
from aip.domain.analytics.explainability.explanation_builder import ExplanationBuilder
from aip.domain.analytics.explainability.explanation_factor import ExplanationFactor
from aip.domain.policies.evaluation.evaluation_report import EvaluationReport

from ..policies.policy_outcome import LiquidityPolicyOutcome


@dataclass(frozen=True, slots=True)
class CoopealianzaLiquidityPolicyReport:
    """Explainable report for Coopealianza liquidity policies."""

    report: EvaluationReport
    outcomes: tuple[LiquidityPolicyOutcome, ...]
    explanation: Explanation

    @property
    def overall_status(self) -> str:
        return self.report.overall_status

    @property
    def message(self) -> str:
        return self.report.message

    @classmethod
    def from_evaluation_report(
        cls,
        report: EvaluationReport | "CoopealianzaLiquidityPolicyReport",
        outcomes: tuple[LiquidityPolicyOutcome, ...] | None = None,
    ) -> "CoopealianzaLiquidityPolicyReport":
        if isinstance(report, CoopealianzaLiquidityPolicyReport):
            wrapped_report = report
            evaluation_report = wrapped_report.report
            resolved_outcomes = wrapped_report.outcomes if outcomes is None else outcomes
        else:
            evaluation_report = report
            resolved_outcomes = outcomes or ()

        builder = ExplanationBuilder()
        factors = [
            ExplanationFactor(
                name=outcome.policy_id,
                value=Decimal("1") if outcome.status == "PASS" else Decimal("0"),
                direction="higher_is_better",
                contribution=Decimal("1") if outcome.status == "PASS" else Decimal("0"),
                source_reference=outcome.reference.identifier if outcome.reference else outcome.policy_id,
            )
            for outcome in resolved_outcomes
        ]
        explanation = builder.build(
            concise_conclusion=evaluation_report.message,
            factors=factors,
            assumptions=("Policies are evaluated through the shared policy engine",),
            warnings=tuple(outcome.message for outcome in resolved_outcomes if outcome.status == "WARNING"),
            source_references=tuple(outcome.policy_id for outcome in resolved_outcomes),
        )
        return cls(report=evaluation_report, outcomes=resolved_outcomes, explanation=explanation)
